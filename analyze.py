"""
RF Coach Vision - analyze.py

Pipeline modulare: Pose (yolo11n-pose) + Racchetta (yolo11 tennis, solo
classe racket) + Pallina (TrackNetV3, vendorizzato in tracknet3/).

Uso (invariato):
    python analyze.py <file_immagine_o_video>

Il comando da terminale resta identico a prima: un solo file in input,
un solo output combinato. Internamente ora orchestriamo piu' modelli
invece di uno solo, ma l'interfaccia non cambia.

Nota sulla pallina: TrackNet non lavora un frame alla volta come YOLO,
ma guarda sequenze di frame consecutivi per sfruttare il movimento.
Per questo, sui video, la traiettoria della pallina viene calcolata
UNA VOLTA SOLA sull'intero file (vedi ball_tracknet.py) prima del ciclo
che disegna pose+racchetta+pallina, invece che dentro quel ciclo.
Sulle singole immagini la pallina non viene cercata: non c'e' movimento
da cui TrackNet possa dedurre nulla da un solo frame.
"""

from ultralytics import YOLO
import sys
import os
import csv
import math
from collections import deque
import cv2
import numpy as np

import ball_tracknet
import sincronizza_drive

# =========================
# CONFIGURAZIONE
# =========================

# ID della classe "racket" nel modello tennis_yolo11 (ultralytics/model.pt).
RACKET_CLASS_ID = 0  # verificato: nel modello la classe 0 e' 'racket'

# Soglie per la racchetta. Niente piu' conf=0.05 / imgsz=4096 su tutto il
# frame: lavoriamo su un ritaglio attorno al giocatore, quindi bastano
# soglie normali.
RACKET_CONF = 0.25
RACKET_IMGSZ = 960

# Margine di ritaglio attorno al box del giocatore (percentuale di
# larghezza/altezza del box), per essere sicuri di includere la racchetta
# anche a braccio disteso durante uno swing.
CROP_MARGIN = 0.6

# Se True, stampa anche i tensori pose completi (conf, data, xy, ...)
# come faceva lo script originale sulle immagini. Utile per debug o per
# preparare il dataset della classificazione colpi, spento di default
# perche' molto verboso.
DEBUG_POSE_TENSORS = False

# =========================
# MODALITA' TRACKNET (pallina)  <-- QUI SCEGLI
# =========================
#   "weight"     -> finestra scorrevole: ogni frame viene analizzato ~8 volte
#                   e le previsioni vengono mediate. Piu' preciso, piu' lento.
#   "nonoverlap" -> ogni frame viene analizzato una volta sola. Circa 8 volte
#                   meno calcolo sulla rete, traiettoria meno affidabile.
# I risultati delle due modalita' vengono salvati separatamente (cache), e
# anche il video di output porta la modalita' nel nome, cosi' puoi
# confrontarli fianco a fianco.
TRACKNET_MODE = "weight"       # USA QUI NON OVERLAP o WEIGHT

# Sovrascrittura del risultato della pallina:
#   False -> se TrackNet ha gia' analizzato questo video in questa modalita',
#            riusa il risultato salvato (pallina pronta subito).
#   True  -> ricalcola TrackNet a ogni esecuzione e sovrascrive il risultato
#            salvato (lento: su CPU in 4K circa 20 minuti in weight).
# Nota: il video di output in outputs/ viene sempre sovrascritto a ogni
# esecuzione, indipendentemente da questa opzione.
TRACKNET_FORCE_RECOMPUTE = True

# Riempimento dei buchi della racchetta: se la racchetta sparisce per al
# massimo questo numero di frame e poi ricompare, le posizioni mancanti
# vengono stimate interpolando tra l'ultimo e il nuovo rilevamento
# (etichetta "racket stimata"). A 60 fps, 6 frame = 0,1 secondi.
# Metti 0 per disattivare.
RACKET_MAX_GAP_FRAMES = 6

# Finestra di anteprima durante l'analisi del video. Su Colab o su qualsiasi
# macchina senza schermo viene disattivata automaticamente.
SHOW_PREVIEW = True

# Salvataggio dei dati grezzi: un CSV per video, una riga per frame, con
# posa, racchetta e pallina. E' il file su cui lavoreranno il rilevamento
# dei colpi e la classificazione (dritto/rovescio).
SAVE_TRACKING_CSV = True

# Disegnare anche le posizioni STIMATE della pallina (quelle ricostruite da
# InpaintNet quando TrackNet non la vede)? Spento: sui video di prova erano
# spesso lontane dalla pallina vera e davano l'illusione di un tracciamento
# continuo. Se acceso, vengono disegnate come cerchio vuoto per distinguerle.
BALL_DRAW_ESTIMATED = False

# Nel terminale viene segnalato quando la pallina "salta" piu' di questi
# pixel rispetto all'ultima posizione nota: una pallina vera non si sposta
# cosi' tanto in 1/60 di secondo, quindi quasi sempre e' un errore di TrackNet.
BALL_JUMP_WARN_PX = 500

# Indici dei keypoint dei polsi nello scheletro COCO-17 usato da
# yolo11n-pose (0=naso, ..., 9=polso sinistro, 10=polso destro, ...).
# Filmando da dietro non sappiamo a priori se il giocatore e' destro o
# mancino, quindi controlliamo entrambi i polsi.
POSE_WRIST_LEFT = 9
POSE_WRIST_RIGHT = 10

# Confidenza minima del keypoint del polso perche' venga usato per
# filtrare la racchetta. Sotto questa soglia la posizione del polso non
# e' abbastanza affidabile da fidarcisi.
WRIST_CONF_THRESHOLD = 0.3

# La racchetta si impugna: il suo riquadro deve toccare (o quasi) un polso.
# Distanza massima polso <-> bordo del riquadro racchetta, come frazione
# dell'altezza del giocatore (0 = il polso deve stare dentro il riquadro).
# Il margine assorbe il ritardo del keypoint durante gli swing veloci.
# Prima usavamo la distanza dal CENTRO della racchetta con 0.9: troppo
# permissivo, passavano l'ombra della racchetta sul campo (vicino ai piedi)
# e perfino la racchetta dell'avversario in fondo al campo.
RACKET_HAND_MARGIN_RATIO = 0.12

# Coerenza nel tempo della racchetta (come fa TrackNet per la pallina, ma
# con una regola semplice): la racchetta e' impugnata, quindi da un frame
# all'altro la sua posizione RISPETTO AL POLSO che la tiene cambia poco,
# anche durante uno swing veloce (si muovono insieme). Prevediamo dove
# dovrebbe essere (polso attuale + distanza polso-racchetta del frame
# precedente) e scartiamo i rilevamenti troppo lontani da quella previsione.
# Spostamento massimo accettato per frame, come frazione dell'altezza del
# giocatore (0.25 = un quarto del giocatore per frame, a 60 fps).
RACKET_MAX_JUMP_RATIO = 0.25

# Se per questo numero di frame di fila la racchetta rilevata e' incoerente
# con la precedente, ci fidiamo del nuovo rilevamento: vuol dire che era
# sbagliata la racchetta precedente, non quella nuova.
RACKET_OUTLIER_RESET_FRAMES = 3

# =========================
# MODELLI
# =========================

pose_model = YOLO("yolo11n-pose.pt")
racket_model = YOLO("tennis_yolo11.pt")  # identico a ultralytics/model.pt



# =========================
# UTILITY
# =========================

def get_player_box(pose_result):
    """
    Restituisce (box, conf, idx) del "giocatore principale", cioe' la
    persona rilevata dal pose model con l'area maggiore. Evita di
    scambiare per giocatore uno spettatore o un raccattapalle sullo
    sfondo (capitava analizzando tutte le persone rilevate
    indistintamente).

    box e' una tupla (x1, y1, x2, y2), conf e' la confidenza della
    detection scelta, idx e' l'indice della persona scelta dentro
    pose_result (serve poi per prendere i SUOI keypoint, non quelli di
    un'altra persona rilevata nello stesso frame). Restituisce
    (None, None, None) se non viene rilevata nessuna persona.
    """

    if pose_result.boxes is None or len(pose_result.boxes) == 0:
        return None, None, None

    boxes = pose_result.boxes.xyxy.cpu().numpy()
    confs = pose_result.boxes.conf.cpu().numpy()
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    idx = int(np.argmax(areas))

    return boxes[idx], float(confs[idx]), idx


def get_wrist_points(pose_result, player_idx):
    """
    Restituisce i polsi del giocatore (indice player_idx, lo stesso di
    get_player_box) come lista di (x, y, affidabile). Filmando da dietro non
    sappiamo se e' destro o mancino, quindi usiamo entrambi i polsi.
    affidabile = confidenza del keypoint >= WRIST_CONF_THRESHOLD. I polsi poco
    affidabili (tipicamente coperti dal corpo, visto che riprendiamo di
    spalle) vengono restituiti lo stesso: YOLO ne stima comunque la
    posizione, e il filtro li usa con un margine piu' largo.
    """

    if player_idx is None or pose_result.keypoints is None:
        return []

    kpts_conf = pose_result.keypoints.conf
    if kpts_conf is None:
        return []

    kpts_xy = pose_result.keypoints.xy.cpu().numpy()
    kpts_conf = kpts_conf.cpu().numpy()

    if player_idx >= len(kpts_xy):
        return []

    wrist_points = []
    for wrist_idx in (POSE_WRIST_LEFT, POSE_WRIST_RIGHT):
        x, y = kpts_xy[player_idx][wrist_idx]
        conf = kpts_conf[player_idx][wrist_idx]
        if x > 0 or y > 0:  # (0, 0) = keypoint non stimato affatto
            wrist_points.append((float(x), float(y), bool(conf >= WRIST_CONF_THRESHOLD), wrist_idx))

    return wrist_points


def _dist_point_box(px, py, det):
    """Distanza da un punto al riquadro (0 se il punto e' dentro)."""
    x1, y1, x2, y2 = det[:4]
    dx = max(x1 - px, 0, px - x2)
    dy = max(y1 - py, 0, py - y2)
    return math.hypot(dx, dy)


def filter_racket_by_wrist(racket_detections, wrist_points, player_box):
    """
    Tiene AL MASSIMO UNA racchetta per frame: quella impugnata dal giocatore.

    1) Scarta ogni racchetta il cui riquadro non tocca (entro il margine
       RACKET_HAND_MARGIN_RATIO) almeno un polso. Elimina l'ombra della
       racchetta sul campo, racchette di altre persone, rumore.
    2) Tra quelle rimaste tiene la piu' vicina alla mano (a parita', quella
       con confidenza piu' alta) e scarta le altre come doppioni.

    Senza giocatore o senza polsi non tiene nessuna racchetta: non potremmo
    sapere se e' davvero quella del giocatore.

    Restituisce (tenute, scartate); scartate e' una lista di (det, motivo),
    usata solo per la stampa a terminale.
    """

    if not racket_detections:
        return [], []

    if player_box is None or not wrist_points:
        return [], [(d, "nessun polso del giocatore visibile") for d in racket_detections]

    player_height = player_box[3] - player_box[1]
    margin = RACKET_HAND_MARGIN_RATIO * player_height

    candidates, discarded = [], []

    for det in racket_detections:
        dists = [
            _dist_point_box(wx, wy, det) / (1.0 if reliable else 2.0)
            for wx, wy, reliable, _ in wrist_points
        ]
        d = min(dists)  # per i polsi poco affidabili il margine vale il doppio
        if d <= margin:
            candidates.append((d, det))
        else:
            discarded.append((det, "lontana dalla mano"))

    if not candidates:
        return [], discarded

    # Tutti i candidati vicini alla mano, dal piu' vicino. La scelta finale
    # (una sola racchetta) la fa RacketTracker nei video, guardando anche il
    # frame precedente; sulle immagini si prende semplicemente il primo.
    candidates.sort(key=lambda c: (c[0], -c[1][4]))
    return [det for _, det in candidates], discarded


class RacketTracker:
    """
    Sceglie al massimo una racchetta per frame, coerente con quella del
    frame precedente. Posizione prevista = polso che la impugnava + stessa
    distanza polso-racchetta dell'ultimo frame valido (se quel polso non si
    vede, l'ultima posizione della racchetta).
    """

    def __init__(self):
        self.last = None       # dict(frame, center, wrist_idx, offset)
        self.rejected_streak = 0
        self.restarted = False  # True se l'ultima scelta ha interrotto la traccia precedente

    def _predict(self, wrist_points):
        for wx, wy, _, idx in wrist_points:
            if idx == self.last["wrist_idx"] and self.last["offset"] is not None:
                return wx + self.last["offset"][0], wy + self.last["offset"][1]
        return self.last["center"]

    def _update(self, frame_n, det, wrist_points):
        cx, cy = (det[0] + det[2]) / 2, (det[1] + det[3]) / 2
        wrist_idx, offset = None, None
        if wrist_points:
            wx, wy, _, wrist_idx = min(wrist_points, key=lambda w: _dist_point_box(w[0], w[1], det))
            offset = (cx - wx, cy - wy)
        self.last = {"frame": frame_n, "center": (cx, cy), "wrist_idx": wrist_idx, "offset": offset}

    def select(self, frame_n, candidates, wrist_points, player_box):
        self.restarted = False

        if not candidates:
            return None

        recent = self.last is not None and frame_n - self.last["frame"] <= RACKET_MAX_GAP_FRAMES + 1

        if not recent:
            chosen = candidates[0]  # nessun riferimento recente: la piu' vicina alla mano
        else:
            px, py = self._predict(wrist_points)
            elapsed = frame_n - self.last["frame"]
            player_height = player_box[3] - player_box[1]
            max_jump = player_height * min(RACKET_MAX_JUMP_RATIO * elapsed, 0.5)

            def dist(det):
                return math.hypot((det[0] + det[2]) / 2 - px, (det[1] + det[3]) / 2 - py)

            best = min(candidates, key=dist)

            if dist(best) <= max_jump:
                chosen = best
            else:
                self.rejected_streak += 1
                if self.rejected_streak < RACKET_OUTLIER_RESET_FRAMES:
                    return None  # salto impossibile: probabile falso positivo
                chosen = candidates[0]  # troppi scarti di fila: riparto da qui
                self.restarted = True

        self.rejected_streak = 0
        self._update(frame_n, chosen, wrist_points)
        return chosen


def expand_box(box, frame_shape, margin):
    """
    Allarga una bounding box di una percentuale 'margin' su ogni lato,
    restando dentro i bordi del frame. Serve per ritagliare attorno al
    giocatore una regione abbastanza ampia da contenere anche la
    racchetta a braccio disteso, ma non l'intero campo.
    """

    x1, y1, x2, y2 = box
    w = x2 - x1
    h = y2 - y1

    x1 -= w * margin
    x2 += w * margin
    y1 -= h * margin
    y2 += h * margin

    height, width = frame_shape[:2]

    x1 = max(0, int(x1))
    y1 = max(0, int(y1))
    x2 = min(width, int(x2))
    y2 = min(height, int(y2))

    return x1, y1, x2, y2


def detect_racket(frame, player_box):
    """
    Esegue la detection della racchetta SOLO nella regione ritagliata
    attorno al giocatore (se disponibile), poi rimappa le coordinate nel
    sistema di riferimento del frame originale. Senza un box giocatore
    ripiega sull'intero frame (piu' lento, meno preciso).

    Restituisce una lista di tuple (x1, y1, x2, y2, conf).
    """

    if player_box is not None:
        crop_x1, crop_y1, crop_x2, crop_y2 = expand_box(player_box, frame.shape, CROP_MARGIN)
        crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]

        if crop.size == 0:
            crop = frame
            offset_x, offset_y = 0, 0
        else:
            offset_x, offset_y = crop_x1, crop_y1
    else:
        crop = frame
        offset_x, offset_y = 0, 0

    result = racket_model(
        crop,
        conf=RACKET_CONF,
        imgsz=RACKET_IMGSZ,
        classes=[RACKET_CLASS_ID],
        verbose=False,
    )[0]

    detections = []

    if result.boxes is not None:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])

            detections.append((
                x1 + offset_x,
                y1 + offset_y,
                x2 + offset_x,
                y2 + offset_y,
                conf,
            ))

    return detections


RACKET_COLOR = (0, 165, 255)  # arancione (BGR)
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX


def _label_style(frame):
    """
    Calcola scala/spessore del font con la STESSA formula che usa
    internamente ultralytics in Annotator per le etichette di
    pose_result.plot() (proporzionale alle dimensioni del frame). Cosi'
    la scritta della racchetta e' sempre della stessa dimensione di
    quella della persona, invece di restare fissa a prescindere dalla
    risoluzione del video.
    """

    # Stessa identica formula di ultralytics.utils.plotting.Annotator
    # (sum(im.shape) include anche i 3 canali colore).
    h, w = frame.shape[:2]
    line_width = max(round((h + w + 3) / 2 * 0.003), 2)
    font_scale = line_width / 3
    thickness = max(line_width - 1, 1)

    return font_scale, thickness


def draw_racket(frame, detections, estimated=False):
    label_scale, label_thickness = _label_style(frame)

    for x1, y1, x2, y2, conf in detections:
        p1 = (int(x1), int(y1))
        p2 = (int(x2), int(y2))

        cv2.rectangle(frame, p1, p2, RACKET_COLOR, 2)

        # Etichetta con sfondo pieno dietro al testo, altrimenti il
        # testo arancione si perde su sfondi chiari/simili (es. il
        # rosso della terra battuta): stesso trucco usato da
        # ultralytics nel suo .plot().
        label = "racket stimata" if estimated else f"racket {conf:.2f}"
        (text_w, text_h), baseline = cv2.getTextSize(
            label, LABEL_FONT, label_scale, label_thickness
        )

        label_x1 = p1[0]
        label_y2 = max(text_h + baseline + 4, p1[1])
        label_y1 = label_y2 - text_h - baseline - 4
        label_x2 = label_x1 + text_w + 6

        cv2.rectangle(
            frame,
            (label_x1, label_y1),
            (label_x2, label_y2),
            RACKET_COLOR,
            -1,
        )
        cv2.putText(
            frame,
            label,
            (label_x1 + 3, label_y2 - baseline - 2),
            LABEL_FONT,
            label_scale,
            (0, 0, 0),  # testo nero: molto piu' leggibile sul riquadro arancione pieno
            label_thickness,
        )

    return frame


BALL_COLOR = (0, 255, 255)  # giallo (BGR)


def interpolate_box(box_a, box_b, t):
    """Box intermedia tra box_a (t=0) e box_b (t=1), confidenza None."""
    return tuple(a + (b - a) * t for a, b in zip(box_a[:4], box_b[:4])) + (None,)


def draw_ball(frame, position):
    """
    position = (x, y, conf, source) oppure None.
    Etichetta con la stessa dimensione di "person" e "racket" (_label_style)
    e sfondo pieno: "ball 0.87" se vista da TrackNet, "ball stimata" se la
    posizione e' ricostruita da InpaintNet (li' non esiste una confidenza).
    """

    if position is None:
        return frame

    x, y, conf, source = position

    if conf is None and not BALL_DRAW_ESTIMATED:
        return frame  # posizione ricostruita: non la disegniamo (vedi config)
    x, y = int(x), int(y)
    label_scale, label_thickness = _label_style(frame)
    radius = 6  # pallino piccolo come in origine, per non coprire la pallina vera

    if conf is None:
        cv2.circle(frame, (x, y), radius, BALL_COLOR, 2)  # stimata: cerchio vuoto
    else:
        cv2.circle(frame, (x, y), radius, BALL_COLOR, -1)

    label = f"ball {conf:.2f}" if conf is not None else "ball stimata"
    (text_w, text_h), baseline = cv2.getTextSize(label, LABEL_FONT, label_scale, label_thickness)

    label_x1 = x + radius + 4
    label_y2 = max(text_h + baseline + 4, y - radius)
    label_y1 = label_y2 - text_h - baseline - 4
    label_x2 = label_x1 + text_w + 6

    cv2.rectangle(frame, (label_x1, label_y1), (label_x2, label_y2), BALL_COLOR, -1)
    cv2.putText(frame, label, (label_x1 + 3, label_y2 - baseline - 2),
                LABEL_FONT, label_scale, (0, 0, 0), label_thickness)

    return frame


def print_pose_tensors(pose_result):
    print("\n=== POSE (debug) ===")
    print("\nConfidence:")
    print(pose_result.keypoints.conf)
    print("\nData:")
    print(pose_result.keypoints.data)
    print("\nXY:")
    print(pose_result.keypoints.xy)
    print("\nXY normalized:")
    print(pose_result.keypoints.xyn)
    print("\nHas visible:")
    print(pose_result.keypoints.has_visible)
    print("\nOriginal shape:")
    print(pose_result.keypoints.orig_shape)
    print("\nShape:")
    print(pose_result.keypoints.data.shape)


# Nomi dei 17 keypoint nello schema COCO usato da yolo11n-pose.
KEYPOINT_NAMES = [
    "naso", "occhio_sx", "occhio_dx", "orecchio_sx", "orecchio_dx",
    "spalla_sx", "spalla_dx", "gomito_sx", "gomito_dx", "polso_sx", "polso_dx",
    "anca_sx", "anca_dx", "ginocchio_sx", "ginocchio_dx", "caviglia_sx", "caviglia_dx",
]


def tracking_header():
    cols = ["frame", "tempo_s", "giocatore_conf", "giocatore_x1", "giocatore_y1",
            "giocatore_x2", "giocatore_y2"]
    for name in KEYPOINT_NAMES:
        # x,y in pixel; nx,ny normalizzati rispetto al box del giocatore
        # (0-1: invarianti alla posizione sul campo e alla distanza dalla
        # camera, sono questi che useremo per classificare i colpi); conf.
        cols += [f"{name}_x", f"{name}_y", f"{name}_nx", f"{name}_ny", f"{name}_conf"]
    cols += ["racchetta_x1", "racchetta_y1", "racchetta_x2", "racchetta_y2",
             "racchetta_conf", "racchetta_fonte",
             "pallina_x", "pallina_y", "pallina_conf", "pallina_fonte"]
    return cols


def tracking_row(item, fps):
    """Una riga di dati grezzi per il frame corrente (vedi tracking_header)."""

    box = item["player_box"]
    row = [item["n"], round((item["n"] - 1) / fps, 4) if fps else "",
           round(item["player_conf"], 4) if item["player_conf"] is not None else ""]
    row += [round(float(v), 1) for v in box] if box is not None else ["", "", "", ""]

    kpts = item["keypoints"]  # lista di (x, y, conf) oppure None
    for i in range(len(KEYPOINT_NAMES)):
        if kpts is None:
            row += ["", "", "", "", ""]
            continue
        x, y, conf = kpts[i]
        if box is not None and box[2] > box[0] and box[3] > box[1]:
            nx = (x - box[0]) / (box[2] - box[0])
            ny = (y - box[1]) / (box[3] - box[1])
            row += [round(x, 1), round(y, 1), round(nx, 4), round(ny, 4), round(conf, 4)]
        else:
            row += [round(x, 1), round(y, 1), "", "", round(conf, 4)]

    if item["rackets"]:
        x1, y1, x2, y2, conf = item["rackets"][0]
        row += [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1), round(conf, 4), "rilevata"]
    elif item["rackets_est"]:
        x1, y1, x2, y2, _ = item["rackets_est"][0]
        row += [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1), "", "stimata"]
    else:
        row += ["", "", "", "", "", ""]

    if item["ball"] is None:
        row += ["", "", "", ""]
    else:
        bx, by, bconf, bsource = item["ball"]
        row += [round(bx, 1), round(by, 1), round(bconf, 4) if bconf is not None else "", bsource]

    return row


def get_keypoints(pose_result, player_idx):
    """Lista di (x, y, conf) per i 17 keypoint del giocatore, o None."""

    if player_idx is None or pose_result.keypoints is None:
        return None

    xy = pose_result.keypoints.xy.cpu().numpy()
    conf = pose_result.keypoints.conf
    if player_idx >= len(xy):
        return None

    conf = conf.cpu().numpy() if conf is not None else None
    return [
        (float(xy[player_idx][i][0]), float(xy[player_idx][i][1]),
         float(conf[player_idx][i]) if conf is not None else 0.0)
        for i in range(len(KEYPOINT_NAMES))
    ]


def _center(det):
    x1, y1, x2, y2 = det[:4]
    return int((x1 + x2) / 2), int((y1 + y2) / 2)


def print_detection_summary(player_conf, racket_detections, racket_discarded=(), ball_position=None,
                            ball_searched=True, racket_estimated=(), prev_ball=None):
    """
    Stampa per il frame corrente confidenza e posizione (in pixel del video,
    x da sinistra, y dall'alto) di giocatore, racchetta e pallina.
    prev_ball = (numero frame, x, y) dell'ultima pallina nota, per segnalare
    i salti impossibili.
    """

    if player_conf is not None:
        print(f"Giocatore: conf={player_conf:.2f}")
    else:
        print("Giocatore: non rilevato")

    if racket_detections:
        for i, det in enumerate(racket_detections, start=1):
            print(f"Racchetta {i}: conf={det[4]:.2f}  centro={_center(det)}")
    elif racket_estimated:
        print(f"Racchetta: posizione stimata (buco riempito)  centro={_center(racket_estimated[0])}")
    else:
        print("Racchetta: non rilevata")


    if not ball_searched:
        print("Pallina: non cercata (serve un video, non un'immagine)")
    elif ball_position is None:
        print("Pallina: non rilevata")
    else:
        x, y, conf, source = ball_position
        pos = (int(x), int(y))
        if conf is not None:
            print(f"Pallina: conf={conf:.2f}  pos={pos}")
        else:
            print(f"Pallina: posizione stimata (ricostruita dalla traiettoria)  pos={pos}")

        if prev_ball is not None:
            jump = math.hypot(x - prev_ball[1], y - prev_ball[2])
            if jump > BALL_JUMP_WARN_PX:
                print(f"  ATTENZIONE: salto di {jump:.0f} px dal frame {prev_ball[0]}, probabile errore di TrackNet")


# =========================
# INPUT
# =========================

if len(sys.argv) < 2:
    print("Uso: python analyze.py <file>")
    sys.exit(1)

input_file = sys.argv[1]

if not os.path.exists(input_file):
    print(f"File non trovato: {input_file}")
    sys.exit(1)

extension = os.path.splitext(input_file)[1].lower()

image_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]

# =========================
# OUTPUT
# =========================

# I risultati sono divisi per tipo: i video da guardare in outputs/video,
# i dati su cui si calcola in outputs/dati.
output_dir = os.path.join("outputs", "video")
dati_dir = os.path.join("outputs", "dati")
os.makedirs(output_dir, exist_ok=True)
os.makedirs(dati_dir, exist_ok=True)

input_name = os.path.splitext(os.path.basename(input_file))[0]

# ============================================================
# IMMAGINE
# ============================================================

if extension in image_extensions:


    image = cv2.imread(input_file)

    pose_result = pose_model(image, verbose=False)[0]
    player_box, player_conf, player_idx = get_player_box(pose_result)

    racket_detections = detect_racket(image, player_box)
    wrist_points = get_wrist_points(pose_result, player_idx)
    racket_detections, racket_discarded = filter_racket_by_wrist(racket_detections, wrist_points, player_box)
    racket_detections = racket_detections[:1]

    ball_position = None

    # Disegno
    image = pose_result.plot(img=image)
    image = draw_racket(image, racket_detections)
    image = draw_ball(image, ball_position)

    output_file = os.path.join(output_dir, f"{input_name}_combined.jpg")
    cv2.imwrite(output_file, image)

    print(f"Output salvato in: {output_file}")

    if DEBUG_POSE_TENSORS:
        print_pose_tensors(pose_result)

    # =========================
    # RIEPILOGO
    # =========================

    print_detection_summary(player_conf, racket_detections, racket_discarded, ball_searched=False)


# ============================================================
# VIDEO
# ============================================================

elif extension in video_extensions:


    cap = cv2.VideoCapture(input_file)

    if not cap.isOpened():
        print("Errore: impossibile aprire il video.")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))


    # =========================
    # PALLINA (TrackNet, sull'intero video, un'unica volta)
    # =========================

    ball_positions = ball_tracknet.compute_ball_trajectory(input_file, TRACKNET_MODE, force=TRACKNET_FORCE_RECOMPUTE)

    output_file = os.path.join(output_dir, f"{input_name}_combined_{TRACKNET_MODE}.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

    if not writer.isOpened():
        print("Errore: impossibile creare il video di output.")
        cap.release()
        sys.exit(1)

    window_name = "RF Coach - Pose + Racchetta + Pallina"

    # Niente schermo (Colab, server Linux): niente finestra, altrimenti
    # OpenCV si blocca provando ad aprirla.
    has_display = not (
        os.environ.get("COLAB_RELEASE_TAG")
        or (sys.platform.startswith("linux") and not os.environ.get("DISPLAY"))
    )
    show_video = SHOW_PREVIEW and has_display

    if show_video:
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        except cv2.error:
            show_video = False

    max_window_width = 1280
    max_window_height = 720

    scale = min(max_window_width / width, max_window_height / height, 1.0)
    window_width = max(1, int(width * scale))
    window_height = max(1, int(height * scale))
    if show_video:
        cv2.resizeWindow(window_name, window_width, window_height)


    frame_number = 0

    tracking_path = os.path.join(dati_dir, f"{input_name}_tracking.csv")
    tracking_file = open(tracking_path, "w", newline="") if SAVE_TRACKING_CSV else None
    tracking_writer = csv.writer(tracking_file) if tracking_file else None
    if tracking_writer:
        tracking_writer.writerow(tracking_header())

    last_ball = {"value": None}  # (numero frame, x, y) dell'ultima pallina stampata

    def emit(item):
        """
        Disegna racchetta/pallina sul frame (la posa e' gia' disegnata),
        lo scrive nel video, lo mostra e stampa il riepilogo.
        Restituisce True se l'utente ha premuto 'q'.
        """

        global show_video

        frame = item["frame"]
        frame = draw_racket(frame, item["rackets"])
        frame = draw_racket(frame, item["rackets_est"], estimated=True)
        frame = draw_ball(frame, item["ball"])

        writer.write(frame)

        if tracking_writer:
            tracking_writer.writerow(tracking_row(item, fps))

        print(f"\n--- FRAME {item['n']}/{total_frames} ---")
        print_detection_summary(
            item["player_conf"], item["rackets"], item["discarded"],
            item["ball"], racket_estimated=item["rackets_est"],
            prev_ball=last_ball["value"],
        )
        if item["ball"] is not None:
            last_ball["value"] = (item["n"], item["ball"][0], item["ball"][1])

        if show_video:

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                print("\nElaborazione interrotta dall'utente.")
                return True

            try:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    print("\nFinestra chiusa dall'utente. L'elaborazione continua in background.")
                    cv2.destroyAllWindows()
                    show_video = False
            except cv2.error:
                show_video = False

        return False

    # I frame non vengono scritti subito: restano in attesa per
    # RACKET_MAX_GAP_FRAMES frame. Se nel frattempo la racchetta ricompare,
    # i frame del buco (ancora in attesa) ricevono la posizione interpolata.
    # Per questo l'anteprima e le stampe sono in ritardo di qualche frame.
    pending = deque()
    last_racket = None  # (numero frame, box) dell'ultima racchetta rilevata davvero
    racket_tracker = RacketTracker()
    stopped = False

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        frame_number += 1

        # POSE (e box giocatore)
        pose_result = pose_model(frame, verbose=False)[0]
        player_box, player_conf, player_idx = get_player_box(pose_result)

        # RACCHETTA: ritaglio attorno al giocatore + filtro vicino al polso
        racket_detections = detect_racket(frame, player_box)
        wrist_points = get_wrist_points(pose_result, player_idx)
        racket_candidates, racket_discarded = filter_racket_by_wrist(racket_detections, wrist_points, player_box)
        chosen = racket_tracker.select(frame_number, racket_candidates, wrist_points, player_box)
        racket_detections = [chosen] if chosen is not None else []

        # PALLINA (posizione gia' calcolata da TrackNet)
        ball_position = ball_positions.get(frame_number - 1)

        item = {
            "n": frame_number,
            "player_box": player_box,
            "keypoints": get_keypoints(pose_result, player_idx),
            "frame": pose_result.plot(img=frame),
            "player_conf": player_conf,
            "rackets": racket_detections,
            "discarded": racket_discarded,
            "rackets_est": [],
            "ball": ball_position,
        }

        # RIEMPIMENTO BUCHI RACCHETTA
        if racket_detections:
            primary = racket_detections[0]

            # Niente riempimento se il tracker ha appena cambiato traccia:
            # collegheremmo due racchette diverse con una linea inventata.
            if last_racket is not None and not racket_tracker.restarted:
                gap = frame_number - last_racket[0] - 1
                if 0 < gap <= RACKET_MAX_GAP_FRAMES:
                    for waiting in pending:
                        if last_racket[0] < waiting["n"] < frame_number:
                            t = (waiting["n"] - last_racket[0]) / (gap + 1)
                            waiting["rackets_est"] = [interpolate_box(last_racket[1], primary, t)]

            last_racket = (frame_number, primary)

        pending.append(item)

        while len(pending) > RACKET_MAX_GAP_FRAMES:
            if emit(pending.popleft()):
                stopped = True
                break

        if stopped:
            break

    # Scrive gli ultimi frame rimasti in attesa
    while pending and not stopped:
        if emit(pending.popleft()):
            break

    cap.release()
    writer.release()

    if tracking_file:
        tracking_file.close()
        print(f"Dati per frame salvati in: {tracking_path}")
        sincronizza_drive.copia(tracking_path, "outputs")
    try:
        cv2.destroyAllWindows()
    except cv2.error:
        pass  # OpenCV senza interfaccia grafica (es. Colab)

    print(f"\nVideo salvato in: {output_file}")


# ============================================================
# FORMATO NON SUPPORTATO
# ============================================================

else:
    print(f"Formato non supportato: {extension}")
    sys.exit(1)
