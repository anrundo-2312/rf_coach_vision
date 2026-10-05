"""
velocita_rimbalzo.py - velocita' STIMATA DAL RIMBALZO per i colpi che il
calcolo normale non riesce a misurare.

    python velocita/velocita_rimbalzo.py --video inputs/<video>.mp4

Si esegue DOPO velocita_uscita.py e direzione_nascosta.py e PRIMA di
disegna_velocita.py. Guarda solo i colpi senza velocita' (contatto nascosto,
solo direzione, misura scartata). La velocita' di velocita_uscita.py non viene
mai toccata: quella stimata qui va in una colonna a parte,
velocita_rimbalzo_kmh, e sul video compare come "circa ... km/h (dal
rimbalzo)".

L'idea. Quando la pallina e' mossa o coperta vicino al giocatore, il calcolo
normale non ha punti buoni subito dopo il colpo. Ma spesso si vede dove la
pallina rimbalza nel campo avversario, e quel punto e' a terra: con la
calibrazione si sa esattamente dov'e' (non serve indovinare la distanza, come
per i punti in volo). Sapendo da dove parte la pallina (a 1 m d'altezza; 2,6
m nel servizio; di lato il punto di contatto, vedi partenza_stima), dove
arriva (il rimbalzo) e quanto ci mette
(i frame tra colpo e rimbalzo), c'e' una sola traiettoria con gravita' e
resistenza dell'aria (lo stesso modello di rf_ball_exit_speed.py) che la
spiega: la sua velocita' iniziale e' la velocita' d'uscita stimata.

Passi, per ogni colpo senza velocita':
1. RIMBALZO: nei punti di TrackNet dopo il colpo, il primo punto piu' basso
   nell'immagine dei 3 prima e dei 2 dopo (la pallina scende verso terra e poi
   risale), che a terra cada nel campo avversario (tra 12,5 e 26 m dal fondo
   del giocatore, di lato entro 1,5 m dalle righe).
2. CONTATTO: si risale dal rimbalzo lungo i punti di TrackNet finche' sono
   continui (buchi di al massimo 6 frame, spostamenti di al massimo 0,3
   altezze del giocatore per frame). Il primo punto di questa traiettoria e' la
   pallina appena uscita dalla racchetta: il contatto e' mezzo frame prima. Ci
   si ferma anche dove la pallina cambia bruscamente velocita' o direzione (li'
   c'e' il colpo) e, se la riga viene da un contatto gia' trovato, non si va
   prima di quel frame (nel servizio il lancio che scende e la pallina colpita
   sono quasi in fila). Il primo punto deve cadere entro 25 frame dal colpo
   indicato dalla riga, se no il rimbalzo e' di un altro colpo.
3. VELOCITA' E DIREZIONE dalla traiettoria che va dal giocatore al rimbalzo
   nel tempo misurato (istanti veri se il video ha fotogrammi ripetuti, vedi
   fotogrammi.py). La direzione (lungo linea, incrociato...; nel servizio al T,
   al corpo, esterno) viene dal rimbalzo misurato e sostituisce quella
   ricavata dai punti in volo.

Se TrackNet non vede il rimbalzo si provano altri due modi, in quest'ordine:
4. COLORE NEL CAMPO LONTANO: nei fotogrammi dopo il colpo in cui TrackNet ha
   perso la pallina si cercano macchie gialle piccole (3-120 px quadrati a
   1080p) vicino all'ultima posizione nota, in un raggio che parte da 12 px e
   cresce di 8 px per ogni fotogramma di buco, ignorando il giallo fermo dello
   sfondo. Sulla traccia completata si rifanno i passi 1-3. Se la riga viene da
   direzione_nascosta.py (contatto coperto) il contatto e' a meta' del tratto
   in cui la pallina era coperta.
5. RIMBALZO RICOSTRUITO: se il rimbalzo e' coperto (testa del giocatore, rete,
   avversario) ma la pallina si vede scendere prima e risalire dopo, con un
   buco di 4-20 fotogrammi, si adattano due curve ai punti prima (almeno 5) e
   dopo (almeno 3) e il rimbalzo e' dove si incontrano. Se passano a piu' di
   20 px (su 1080) i punti dopo non sono la stessa pallina e non si stima
   niente. Contatto: il frame della riga (contatto trovato) o la meta' del
   tratto coperto. Margine circa +-20%; sul video "rimbalzo ricostruito".
Un rimbalzo non vale per due colpi.

6. PUNTO DEL RIMBALZO PER LA MAPPA: per tutti gli altri colpi con una
   direzione (velocita' misurata, solo direzione, contatto coperto) si cerca
   solo il punto in cui la pallina rimbalza nel campo avversario, nei 1,6 s
   dopo il colpo (dopo la ricomparsa, se il contatto era coperto), con gli
   stessi tre modi: TrackNet, colore nel campo lontano, rimbalzo ricostruito.
   Non cambia ne' la velocita' ne' la direzione: il punto compare sulla mappa
   del video e serve da controllo. Se la direzione data dal rimbalzo e'
   diversa, la nota lo dice ("il rimbalzo trovato darebbe ...").
   Eccezione: nei colpi "solo direzione" (contatto trovato dalla ricerca
   estesa di velocita_uscita.py, velocita' non affidabile) il rimbalzo trovato
   qui serve anche per la velocita': dal contatto della riga al rimbalzo, come
   nei passi 4-5, senza risalire la traiettoria dal rimbalzo (che palline
   ferme o un falso rimbalzo possono interrompere o allungare). Sul video
   "circa X km/h (dal rimbalzo)", la direzione dal rimbalzo. PUNTO4 = False:
   come prima.
7. VELOCITA' MEDIA DEL VOLO (velocita_media_kmh): distanza a terra dal
   contatto al rimbalzo trovato diviso il tempo di volo, in km/h. Nelle stime
   dei passi 1-5 e' il dato da cui si ricava la velocita' d'uscita ("media fino
   al rimbalzo" nella nota); nei colpi con la velocita' misurata da
   velocita_uscita.py si calcola con il contatto del calcolo e il rimbalzo del
   passo 6. La pallina in volo rallenta sempre (aria), quindi la media e' piu'
   bassa della velocita' d'uscita (di solito 75-85%): se viene piu' alta una
   delle due misure e' sbagliata, la media non si scrive e la nota lo dice.
   Senza rimbalzo trovato o senza velocita' non c'e'.
DRITTO INSIDE-OUT / INSIDE-IN (colonna dritto_tipo, velocita_uscita.tipo_dritto):
dritto colpito con i piedi almeno 1 m oltre la riga centrale dalla parte del
rovescio; per un destro inside-in se la pallina finisce nel terzo di sinistra
del campo avversario, inside-out se finisce nel terzo di destra (mancino al
contrario); nel terzo centrale nessuno dei due. La mano si ricava dai contatti visti
(--mano auto) o si indica (--mano destra / sinistra).
Il rimbalzo trovato (passi 1-6) e' nelle colonne rimbalzo_trovato_x_m,
rimbalzo_trovato_y_m, rimbalzo_trovato_frame e rimbalzo_trovato_come
(tracknet, colore, ricostruito). rimbalzo_x_m e rimbalzo_y_m restano quelle
del servizio, usate per la fascia (previsto o trovato).
Dal rimbalzo trovato: dentro_fuori (campo singolo; servizio: riquadro in
diagonale; si decide sempre, la riga conta dentro), distanza_riga_m (+ dentro,
- fuori), riga_vicina e profondita (dalla riga di fondo: profonda negli ultimi
1,5 m, media fino alla riga del servizio, corta fino a 3 m dalla rete, palla
corta entro 3 m dalla rete): vedi velocita_uscita.dentro_fuori. Precisione: di lato
buona; in profondita' vicino al fondo lontano scarsa con la camera bassa
(alcaraz: circa 0,25 m per pixel), vedi LEGGIMI.

Prove del rimbalzo ricostruito: nascondendo apposta il rimbalzo nei 5 colpi di
alcaraz in cui si vede, in 4 la stima resta entro il 7%; nel quinto le curve
passano a 102 px e il controllo la scarta.
Prove: dove anche il calcolo normale funziona i due metodi vanno abbastanza
d'accordo (alcaraz, dritto al 275: 138 km/h dal calcolo normale, 130 dal
rimbalzo; Djokovic, dritto al 65: 123 e 145 con il colore, perche' i passi 1-3
non trovano l'inizio della traiettoria). Precisione attesa circa +-15%: il punto
di contatto e' approssimato (piedi del giocatore e altezza fissa), il tempo di
volo ha un errore di circa un frame, la rotazione non e' nel modello.
Limite: il rimbalzo spesso non si vede (coperto dalla rete, dalla testa del
giocatore o dall'avversario); in quel caso non si stima niente.
"""

import argparse
import csv
import json
import os
import sys

import re

import cv2
import numpy as np
from scipy.optimize import least_squares, minimize_scalar

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
import rf_ball_exit_speed as calcolo  # noqa: E402
import velocita_uscita as vu  # noqa: E402
import fotogrammi  # noqa: E402
import palla_locale  # noqa: E402
from calibra_campo import camera_da_json, carica_per_video  # noqa: E402

DURATA_MAX_S = 1.6          # il rimbalzo si cerca fino a 1,6 s dopo il colpo
PRIMA_S = 25                # la traiettoria in uscita deve partire entro 25 frame dal colpo della riga
BUCO_MAX = 6                # buco massimo (frame) nei punti di TrackNet lungo la traiettoria
SALTO_MAX_REL = 0.3         # spostamento massimo per frame, in altezze del giocatore
CAMBIO_MAX = 2.5            # la traiettoria finisce (all'indietro) dove la velocita' cambia di 2,5 volte
ANGOLO_MAX = 60             # ... o gira di piu' di 60 gradi: li' c'e' il colpo
MOTO_MINIMO_REL = 0.03      # i due controlli valgono solo se la pallina si muove abbastanza (altezze/frame)
CAMPO_Y = (12.5, 26.0)      # il rimbalzo deve cadere nel campo avversario (m dal fondo del giocatore)
CAMPO_X = (-1.5, 12.5)
VOLO_S = (0.25, 1.6)
ALTEZZA_CONTATTO = {"servizio": 2.6}   # m; tutti gli altri colpi 1,0 m
NOTA_RIMBALZO = "velocita' stimata dal rimbalzo"
NOTA_RICOSTRUITO = "velocita' stimata dal rimbalzo ricostruito"   # comincia come NOTA_RIMBALZO
NOTA_ESTESA = "pallina mossa al colpo"     # righe "solo direzione" della ricerca estesa (velocita_uscita.py)
PUNTO4 = True               # "solo direzione" + rimbalzo del passo 6 -> velocita' dal contatto della riga

# passo 4: colore nel campo lontano (misure in px a 1080p, scalate con l'altezza del video)
COLORE_HSV = ((22, 60, 100), (48, 255, 255))
COLORE_AREA = (3, 120)      # px quadrati: la pallina lontana e' un puntino
COLORE_RAGGIO = (12, 8)     # raggio di ricerca: 12 px + 8 px per ogni fotogramma di buco

# passo 5: rimbalzo ricostruito
RIC_BUCO = (4, 20)          # fotogrammi del buco attorno al rimbalzo
RIC_SCARTO_MAX = 20 / 1080  # le due curve devono incontrarsi entro 20 px (su 1080)
RIC_PUNTI = (5, 3)          # punti minimi prima (in discesa) e dopo (in risalita)

# passo 6 e colonne del rimbalzo trovato (dopo rimbalzo_y_m nel CSV)
CAMPI_TROVATO = ["rimbalzo_trovato_x_m", "rimbalzo_trovato_y_m", "rimbalzo_trovato_frame", "rimbalzo_trovato_come",
                 "dentro_fuori", "distanza_riga_m", "riga_vicina", "profondita"]
_i = vu.CAMPI.index("rimbalzo_y_m") + 1
CAMPI = vu.CAMPI[:_i] + CAMPI_TROVATO + vu.CAMPI[_i:]
_i = CAMPI.index("velocita_rimbalzo_kmh") + 1
CAMPI = CAMPI[:_i] + ["velocita_media_kmh"] + CAMPI[_i:]      # passo 7


def partenza_stima(t, cam, riga, piedi, punti, t_contatto):
    """
    (x di partenza, partenza_da) per la stima dal rimbalzo. Il servizio parte dai piedi. Se la riga ha
    un contatto visto dal calcolo (ricerca estesa, partenza_da = "contatto") si tiene quello; se no i
    punti nel primo 1/6 s dopo il contatto (vu.punto_di_partenza); se no i piedi.
    """
    if riga["colpo"] == "servizio":
        return float(piedi[0]), "piedi"
    if riga.get("partenza_da") == "contatto" and riga.get("contatto_x_m") not in (None, ""):
        return float(riga["contatto_x_m"]), "contatto"
    return vu.punto_di_partenza(t, cam, piedi, punti=punti, t_contatto=t_contatto)


def trova_rimbalzo(tn, da, a, cam):
    """Primo rimbalzo nel campo avversario tra i frame da..a: (frame, pixel, punto a terra) o None."""
    fs = [f for f in range(da, a + 1) if f in tn]
    for i in range(3, len(fs) - 2):
        if fs[i + 2] - fs[i - 3] > 10:
            continue
        y = tn[fs[i]][1]
        prima = [tn[g][1] for g in fs[i - 3:i]]
        dopo = [tn[g][1] for g in fs[i + 1:i + 3]]
        if not (all(y >= p for p in prima) and all(y > q for q in dopo)
                and y - min(prima) > 2 and y - min(dopo) > 3):
            continue
        terra = calcolo.ground_from_pixel(tn[fs[i]], cam)[:2]
        if CAMPO_Y[0] <= terra[1] <= CAMPO_Y[1] and CAMPO_X[0] <= terra[0] <= CAMPO_X[1]:
            return fs[i], tn[fs[i]], terra
    return None


def inizio_traiettoria(tn, f_rimbalzo, limite, altezze, ripetuti=None):
    """
    Primo frame della traiettoria continua di TrackNet che arriva al rimbalzo. Si risale dal
    rimbalzo e ci si ferma a un buco lungo, a un salto troppo grande o dove la pallina cambia
    bruscamente velocita' o direzione (il colpo: prima c'era la pallina in arrivo, o il lancio
    nel servizio). I fotogrammi ripetuti (fotogrammi.py) si saltano.
    """
    f, v_dopo = f_rimbalzo, None
    while True:
        prec = [g for g in range(f - 1, max(limite, f - BUCO_MAX - 1) - 1, -1)
                if g in tn and not (ripetuti is not None and ripetuti[g])]
        if not prec:
            return f
        g = prec[0]
        h = altezze.get(g) or altezze.get(f) or 300.0
        v = (np.asarray(tn[f], float) - np.asarray(tn[g], float)) / (f - g)
        a = float(np.linalg.norm(v))
        if a > SALTO_MAX_REL * h:
            return f
        if v_dopo is not None:
            b = float(np.linalg.norm(v_dopo))
            if max(a, b) > MOTO_MINIMO_REL * h and (max(a, b) > CAMBIO_MAX * max(min(a, b), 1e-6)
                                                   or np.dot(v, v_dopo) < np.cos(np.radians(ANGOLO_MAX)) * a * b):
                return f
        v_dopo = v
        f = g


def stima(t, tn, altezze, cam, riga):
    """Stima dal rimbalzo per una riga senza velocita' (dizionario da aggiungere alla riga) o None."""
    fc = int(riga["frame"])
    fps = t["fps"]
    rimb = trova_rimbalzo(tn, fc - PRIMA_S, fc + int(DURATA_MAX_S * fps), cam)
    if rimb is None:
        return None
    fb, pb, terra = rimb
    ripetuti = None if t.get("tempi") is None else t["tempi"]["dup"]
    # se la riga viene da un contatto trovato (cambio di direzione vicino al polso: righe "solo
    # direzione", "misura scartata"...), la pallina in uscita non puo' partire prima di quel frame.
    # Serve nel servizio, dove il lancio che scende e la pallina colpita sono quasi in fila.
    contatto_trovato = not str(riga.get("nota", "")).startswith("contatto non visibile")
    limite = fc + 1 if contatto_trovato else fc - PRIMA_S - BUCO_MAX
    s = inizio_traiettoria(tn, fb, limite, altezze, ripetuti)
    if abs(s - fc) > PRIMA_S or s >= fb:
        return None
    # contatto mezzo frame prima del primo punto in uscita; istanti veri se ci sono ripetuti
    fps_vero = fps if t.get("tempi") is None else t["tempi"]["fps"]
    t_contatto = vu.istante(t, s) - 0.5 / fps_vero
    volo = vu.istante(t, fb) - t_contatto
    if not VOLO_S[0] <= volo <= VOLO_S[1]:
        return None
    f_contatto = max(1, s - 1)
    piedi = vu.piedi_a_terra(t, f_contatto, cam)
    x0, partenza_da = partenza_stima(t, cam, riga, piedi, {f: tn[f] for f in range(s, fb + 1) if f in tn}, t_contatto)
    p0 = np.array([x0, piedi[1], ALTEZZA_CONTATTO.get(riga["colpo"], 1.0)])
    arrivo = np.array([terra[0], terra[1], 0.0])
    sol = least_squares(lambda v: calcolo.simulate(p0, v, np.array([volo]))[-1] - arrivo, (arrivo - p0) / volo)
    v0 = sol.x
    kmh = float(np.linalg.norm(v0) * 3.6)
    media = float(np.linalg.norm(arrivo[:2] - p0[:2]) / volo * 3.6)
    lo, hi = vu.VELOCITA_PLAUSIBILE
    if not lo <= kmh <= hi:
        return None
    angolo, x_arrivo, direzione = vu.classifica_direzione(x0, p0, v0)
    out = {"velocita_rimbalzo_kmh": round(kmh), "velocita_media_kmh": round(media), "angolo_gradi": round(angolo, 1),
           "giocatore_x_m": round(float(piedi[0]), 2), "arrivo_x_m": round(x_arrivo, 2),
           "partenza_da": partenza_da, "_partenza_x_m": round(x0, 2),
           "contatto_x_m": round(float(p0[0]), 2), "contatto_y_m": round(float(p0[1]), 2),
           "contatto_z_m": round(float(p0[2]), 2),
           "rimbalzo_x_m": round(float(terra[0]), 2), "rimbalzo_y_m": round(float(terra[1]), 2),
           "_punti": [(f, float(tn[f][0]), float(tn[f][1])) for f in range(s, fb + 1) if f in tn]}
    if riga["colpo"] == "servizio":
        direzione = vu.classifica_servizio(float(piedi[0]), terra)
    out["direzione"] = direzione
    nota = (f"{NOTA_RIMBALZO} (margine circa +-15%): contatto ~frame {f_contatto}, rimbalzo al frame {fb} "
            f"a ({terra[0]:.1f}; {terra[1]:.1f}) m, volo {volo:.2f} s, media fino al rimbalzo {media:.0f} km/h")
    if riga.get("direzione") and riga["direzione"] != direzione:
        nota += f"; dai punti in volo era \"{riga['direzione']}\""
    if riga.get("nota"):
        nota += f". Prima: {riga['nota']}"
    out["nota"] = nota
    return out


def velocita_da_volo(t, cam, riga, f_c, t_rimbalzo, terra, punti=None):
    """
    Il calcolo comune ai passi 4 e 5: partenza dal punto di partenza (partenza_stima; a 1 m, 2,6 m nel servizio)
    all'istante del contatto f_c (anche frazionario), arrivo al rimbalzo a terra all'istante
    t_rimbalzo. (v0, km/h, media fino al rimbalzo, volo, piedi, p0, partenza) o None se il volo non e' plausibile.
    """
    fps_vero = t["fps"] if t.get("tempi") is None else t["tempi"]["fps"]
    t_c = vu.istante(t, int(f_c)) + (f_c - int(f_c)) / fps_vero
    volo = t_rimbalzo - t_c
    if not VOLO_S[0] <= volo <= VOLO_S[1]:
        return None
    piedi = vu.piedi_a_terra(t, max(1, int(f_c)), cam)
    partenza = partenza_stima(t, cam, riga, piedi, punti, t_c)
    p0 = np.array([partenza[0], piedi[1], ALTEZZA_CONTATTO.get(riga["colpo"], 1.0)])
    arrivo = np.array([terra[0], terra[1], 0.0])
    v0 = least_squares(lambda v: calcolo.simulate(p0, v, np.array([volo]))[-1] - arrivo, (arrivo - p0) / volo).x
    kmh = float(np.linalg.norm(v0) * 3.6)
    lo, hi = vu.VELOCITA_PLAUSIBILE
    if not lo <= kmh <= hi:
        return None
    media = float(np.linalg.norm(arrivo[:2] - p0[:2]) / volo * 3.6)
    return v0, kmh, media, volo, piedi, p0, partenza


def riga_stima(riga, v0, kmh, piedi, p0, terra, punti, nota, partenza, media):
    """Campi da aggiungere alla riga (come in stima)."""
    angolo, x_arrivo, direzione = vu.classifica_direzione(partenza[0], p0, v0)
    if riga["colpo"] == "servizio":
        direzione = vu.classifica_servizio(float(piedi[0]), terra)
    if riga.get("direzione") and riga["direzione"] != direzione:
        nota += f"; dai punti in volo era \"{riga['direzione']}\""
    if riga.get("nota"):
        nota += f". Prima: {riga['nota']}"
    return {"velocita_rimbalzo_kmh": round(kmh), "velocita_media_kmh": round(media),
            "angolo_gradi": round(angolo, 1), "direzione": direzione,
            "giocatore_x_m": round(float(piedi[0]), 2), "arrivo_x_m": round(x_arrivo, 2),
            "partenza_da": partenza[1], "_partenza_x_m": round(partenza[0], 2),
            "contatto_x_m": round(float(p0[0]), 2), "contatto_y_m": round(float(p0[1]), 2),
            "contatto_z_m": round(float(p0[2]), 2),
            "rimbalzo_x_m": round(float(terra[0]), 2), "rimbalzo_y_m": round(float(terra[1]), 2),
            "_punti": punti, "nota": nota}


def tratto_coperto(riga):
    """(frame in cui la pallina si perde, frame in cui ricompare) dalla nota di direzione_nascosta.py, o None."""
    m = re.search(r"pallina persa al frame (\d+), ricompare al (\d+)", str(riga.get("nota", "")))
    return (int(m.group(1)), int(m.group(2))) if m else None


# ------------------------------------------------------------------ passo 4
def macchie_lontane(frame, cx, cy, raggio, fermo, scala):
    """Centri delle macchie gialle piccole entro raggio da (cx, cy), escluso il giallo fermo."""
    h, w = frame.shape[:2]
    x0, y0 = max(0, int(cx - raggio)), max(0, int(cy - raggio))
    x1, y1 = min(w, int(cx + raggio)), min(h, int(cy + raggio))
    if x1 <= x0 or y1 <= y0:
        return []
    m = cv2.inRange(cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV), *COLORE_HSV)
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    out = []
    for i in range(1, n):
        if COLORE_AREA[0] * scala ** 2 <= st[i, cv2.CC_STAT_AREA] <= COLORE_AREA[1] * scala ** 2:
            x, y = cen[i][0] + x0, cen[i][1] + y0
            if fermo is None or not fermo[min(h - 1, int(y)), min(w - 1, int(x))]:
                out.append((float(x), float(y)))
    return out


def estendi_col_colore(video, cap, tn, da, a, scala):
    """Punti di TrackNet tra da e a, con i buchi riempiti dal colore; (traccia, frame aggiunti)."""
    fermo, fermo_pronto = None, False           # il giallo fermo si calcola solo se serve
    traccia = {f: tn[f] for f in range(da, a + 1) if f in tn}
    aggiunti, ultimo = set(), None
    pos = None                                  # prossimo frame che cap legge: leggere in fila e' molto
    for f in range(da, a + 1):                  # piu' veloce che saltare (4K: 0,5 s a salto, 0,02 s in fila)
        if f in tn:
            ultimo = (f, tn[f])
            if pos == f:
                cap.grab()
                pos = f + 1
            continue
        if ultimo is None:
            continue
        if not fermo_pronto:
            fermo, fermo_pronto = palla_locale.giallo_fermo(video, da, a), True
        if pos != f:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f - 1)
        ok, frame = cap.read()
        pos = f + 1
        if not ok:
            break
        raggio = (COLORE_RAGGIO[0] + COLORE_RAGGIO[1] * (f - ultimo[0])) * scala
        c = macchie_lontane(frame, ultimo[1][0], ultimo[1][1], raggio, fermo, scala)
        if c:
            p = min(c, key=lambda q: np.hypot(q[0] - ultimo[1][0], q[1] - ultimo[1][1]))
            traccia[f] = p
            aggiunti.add(f)
            ultimo = (f, p)
    return traccia, aggiunti


def stima_colore(t, tn, altezze, cam, riga, video, cap, scala, usati):
    """Passo 4: stima dal rimbalzo sulla traccia completata dal colore. (campi, frame del rimbalzo) o None."""
    fc = int(riga["frame"])
    da, a = fc - PRIMA_S, fc + int(DURATA_MAX_S * t["fps"])
    est, aggiunti = estendi_col_colore(video, cap, tn, da, a, scala)
    if not aggiunti:
        return None
    rimb = trova_rimbalzo(est, da, a, cam)
    if rimb is None or rimb[0] in usati:
        return None
    fb, pb, terra = rimb
    ripetuti = None if t.get("tempi") is None else t["tempi"]["dup"]
    coperto = tratto_coperto(riga)
    if coperto:                                   # contatto coperto: meta' del tratto coperto
        f_c = (coperto[0] + coperto[1]) / 2
    else:
        contatto_trovato = not str(riga.get("nota", "")).startswith("contatto non visibile")
        limite = fc + 1 if contatto_trovato else fc - PRIMA_S - BUCO_MAX
        f_c = inizio_traiettoria(est, fb, limite, altezze, ripetuti) - 0.5
    if abs(f_c - fc) > PRIMA_S or f_c >= fb:
        return None
    r = velocita_da_volo(t, cam, riga, f_c, vu.istante(t, fb), terra,
                         {f: est[f] for f in range(int(np.ceil(f_c)), fb + 1) if f in est})
    if r is None:
        return None
    v0, kmh, media, volo, piedi, p0, partenza = r
    nota = (f"{NOTA_RIMBALZO}, trovato con il colore nel campo lontano (margine circa +-15%): contatto ~frame "
            f"{f_c:.0f}, rimbalzo al frame {fb} a ({terra[0]:.1f}; {terra[1]:.1f}) m, volo {volo:.2f} s, "
            f"media fino al rimbalzo {media:.0f} km/h, {len(aggiunti)} punti aggiunti dal colore")
    punti = [(f, float(est[f][0]), float(est[f][1])) for f in range(int(np.ceil(f_c)), fb + 1) if f in est]
    return riga_stima(riga, v0, kmh, piedi, p0, terra, punti, nota, partenza, media), fb


# ------------------------------------------------------------------ passo 5
def contatto_per_ricostruito(riga):
    """Frame (anche frazionario) del contatto per il rimbalzo ricostruito, o None."""
    coperto = tratto_coperto(riga)
    if coperto:
        return (coperto[0] + coperto[1]) / 2
    if str(riga.get("nota", "")).startswith(("pallina mossa", "misura scartata")):
        return int(riga["frame"]) + 0.5
    return None


def cerca_rimbalzo_coperto(t, tn, ripetuti, fc, cam, altezza_img):
    """Il primo buco dopo il contatto con la pallina in discesa prima e in risalita dopo: dict o None."""
    fs = [f for f in range(int(fc) + 2, int(fc) + int(DURATA_MAX_S * t["fps"])) if f in tn and not ripetuti[f]]
    for a, b in zip(fs, fs[1:]):
        if not RIC_BUCO[0] <= b - a <= RIC_BUCO[1]:
            continue
        prima = [f for f in fs if f <= a][-8:]
        dopo = [f for f in fs if f >= b][:6]
        if len(prima) < RIC_PUNTI[0] or len(dopo) < RIC_PUNTI[1]:
            continue
        # prima in discesa verso terra (y cresce), dopo in risalita (y cala)
        if not (tn[prima[-1]][1] > tn[prima[-4]][1] + 2 and tn[dopo[0]][1] > tn[dopo[2]][1] + 2):
            continue
        istanti = lambda xs: np.array([vu.istante(t, f) for f in xs])
        curva = lambda xs: [np.polyfit(istanti(xs), [tn[f][d] for f in xs], 2 if len(xs) >= 5 else 1) for d in (0, 1)]
        cp, cd = curva(prima), curva(dopo)
        punto = lambda c, x: np.array([np.polyval(c[0], x), np.polyval(c[1], x)])
        r = minimize_scalar(lambda x: np.sum((punto(cp, x) - punto(cd, x)) ** 2),
                            bounds=(vu.istante(t, a), vu.istante(t, b)), method="bounded")
        scarto = float(np.sqrt(r.fun))
        pixel = 0.5 * (punto(cp, r.x) + punto(cd, r.x))
        terra = calcolo.ground_from_pixel(pixel, cam)[:2]
        ok = (scarto <= RIC_SCARTO_MAX * altezza_img and CAMPO_Y[0] <= terra[1] <= CAMPO_Y[1]
              and CAMPO_X[0] <= terra[0] <= CAMPO_X[1])
        return {"t": float(r.x), "terra": terra, "scarto": scarto, "ok": ok, "buco": (a, b),
                "punti": prima + dopo}
    return None


def stima_ricostruita(t, tn, cam, riga, altezza_img, usati):
    """Passo 5: stima dal rimbalzo ricostruito. (campi, frame del rimbalzo) o None."""
    fc = contatto_per_ricostruito(riga)
    if fc is None:
        return None
    ripetuti = t["tempi"]["dup"] if t.get("tempi") is not None else np.zeros(len(t["frame"]) + 300, bool)
    r = cerca_rimbalzo_coperto(t, tn, ripetuti, fc, cam, altezza_img)
    if r is None or not r["ok"]:
        return None
    a, b = r["buco"]
    if any(a <= f <= b for f in usati):
        return None
    fps_vero = t["fps"] if t.get("tempi") is None else t["tempi"]["fps"]
    fb = a + int(round((r["t"] - vu.istante(t, a)) * fps_vero))
    v = velocita_da_volo(t, cam, riga, fc, r["t"], r["terra"], tn)
    if v is None:
        return None
    v0, kmh, media, volo, piedi, p0, partenza = v
    terra = r["terra"]
    nota = (f"{NOTA_RICOSTRUITO} (margine circa +-20%): rimbalzo coperto tra i frame {a} e {b}, ricostruito "
            f"(rimbalzo al frame {fb}) a ({terra[0]:.1f}; {terra[1]:.1f}) m, curve a "
            f"{r['scarto'] * 1080 / altezza_img:.0f} px (1080p), contatto ~frame {fc:.0f}, volo {volo:.2f} s, "
            f"media fino al rimbalzo {media:.0f} km/h")
    punti = [(f, float(tn[f][0]), float(tn[f][1])) for f in r["punti"]]
    return riga_stima(riga, v0, kmh, piedi, p0, terra, punti, nota, partenza, media), fb


# ------------------------------------------------------------------ passo 6
def stima_da_contatto_esteso(t, tn, cam, c, x, y, fb, come):
    """
    Riga "solo direzione" (contatto trovato dalla ricerca estesa) con il rimbalzo trovato al passo 6:
    velocita' dal contatto della riga (frame + 0,5) al rimbalzo, come nei passi 4-5 (velocita_da_volo). Non si
    risale la traiettoria dal rimbalzo. (campi, frame del rimbalzo) o None se il volo o la velocita' non sono
    plausibili.
    """
    fc = int(c["frame"])
    v = velocita_da_volo(t, cam, c, fc + 0.5, vu.istante(t, fb), (x, y), tn)
    if v is None:
        return None
    v0, kmh, media, volo, piedi, p0, partenza = v
    ricostruito = come == "ricostruito"
    nota = (f"{NOTA_RICOSTRUITO if ricostruito else NOTA_RIMBALZO} (margine circa {'+-20' if ricostruito else '+-15'}%), "
            f"dal contatto della ricerca estesa: contatto ~frame {fc}, rimbalzo al frame {fb} a ({x:.1f}; {y:.1f}) m"
            + (" (trovato con il colore)" if come == "colore" else "")
            + f", volo {volo:.2f} s, media fino al rimbalzo {media:.0f} km/h")
    punti = [(f, float(tn[f][0]), float(tn[f][1])) for f in range(fc + 1, fb + 1) if f in tn]
    return riga_stima(c, v0, kmh, piedi, p0, (x, y), punti, nota, partenza, media), fb


def rimbalzo_dopo_colpo(t, tn, cam, riga, video, cap, scala, altezza_img, usati):
    """
    Passo 6: solo il punto del rimbalzo nel campo avversario per un colpo che ha gia' una direzione.
    (x, y, frame, come) o None. Ne' velocita' ne' direzione: serve per la mappa e come controllo.
    """
    fc = int(riga["frame"])
    coperto = tratto_coperto(riga)
    da = coperto[1] if coperto else fc + 1          # dopo la ricomparsa, se il contatto era coperto
    a = fc + int(DURATA_MAX_S * t["fps"])
    r = trova_rimbalzo(tn, da, a, cam)
    if r is not None and r[0] not in usati:
        return float(r[2][0]), float(r[2][1]), r[0], "tracknet"
    est, aggiunti = estendi_col_colore(video, cap, tn, da, a, scala)
    if aggiunti:
        r = trova_rimbalzo(est, da, a, cam)
        if r is not None and r[0] not in usati:
            return float(r[2][0]), float(r[2][1]), r[0], "colore"
    ripetuti = t["tempi"]["dup"] if t.get("tempi") is not None else np.zeros(len(t["frame"]) + 300, bool)
    r = cerca_rimbalzo_coperto(t, tn, ripetuti, da - 1, cam, altezza_img)
    if r is not None and r["ok"]:
        a_, b_ = r["buco"]
        if not any(a_ <= f <= b_ for f in usati):
            fps_vero = t["fps"] if t.get("tempi") is None else t["tempi"]["fps"]
            fb = a_ + int(round((r["t"] - vu.istante(t, a_)) * fps_vero))
            return float(r["terra"][0]), float(r["terra"][1]), fb, "ricostruito"
    return None


def direzione_dal_rimbalzo(riga, x, y):
    """La direzione che darebbe il rimbalzo trovato (stesse regole di velocita_uscita.py), o None."""
    try:
        xg = float(riga.get("_partenza_x_m", riga["giocatore_x_m"]))
    except (KeyError, TypeError, ValueError):
        return None
    if riga["colpo"] == "servizio":
        return vu.classifica_servizio(xg, np.array([x, y]))
    try:
        xc, yc = float(riga["contatto_x_m"]), float(riga["contatto_y_m"])
    except (KeyError, TypeError, ValueError):
        return None
    if y <= yc:
        return None
    ang = np.arctan2(x - xc, y - yc)        # vista dall'alto la pallina va dritta dal contatto al rimbalzo
    return vu.classifica_direzione(xg, np.array([xc, yc, 1.0]), np.array([np.sin(ang), np.cos(ang), 0.0]))[2]


# ------------------------------------------------------------------ passo 7
NOTA_MEDIA = "media fino al rimbalzo"


def aggiungi_media(t, colpi, verbose=False):
    """
    velocita_media_kmh per i colpi con la velocita' misurata (velocita_uscita.py) e il rimbalzo trovato:
    distanza a terra dal contatto al rimbalzo / tempo di volo, come nelle stime dei passi 1-5 (li' e' gia'
    scritta). Il contatto e' tra il frame della riga e il successivo (come nel calcolo), quindi mezzo frame
    dopo. Se la media viene piu' alta della velocita' d'uscita non si scrive: la pallina in volo rallenta
    sempre, quindi una delle due misure e' sbagliata.
    """
    fps_vero = t["fps"] if t.get("tempi") is None else t["tempi"]["fps"]
    for c in colpi:
        if c.get("velocita_uscita_kmh", "") == "" or c.get("rimbalzo_trovato_frame") in (None, ""):
            continue
        t_c = vu.istante(t, int(c["frame"])) + 0.5 / fps_vero
        volo = vu.istante(t, int(c["rimbalzo_trovato_frame"])) - t_c
        if not VOLO_S[0] <= volo <= VOLO_S[1]:
            continue
        d = float(np.hypot(float(c["rimbalzo_trovato_x_m"]) - float(c["contatto_x_m"]),
                           float(c["rimbalzo_trovato_y_m"]) - float(c["contatto_y_m"])))
        media = d / volo * 3.6
        if media > float(c["velocita_uscita_kmh"]):
            c.pop("velocita_media_kmh", None)
            nota = str(c.get("nota", ""))
            if NOTA_MEDIA not in nota:
                c["nota"] = (nota + "; " if nota else "") + (
                    f"{NOTA_MEDIA} {media:.0f} km/h (volo {volo:.2f} s), piu' della velocita' d'uscita: "
                    f"non mostrata (la pallina in volo rallenta, una delle due misure e' sbagliata)")
            if verbose:
                print(f"frame {c['frame']} {c['colpo']}: media {media:.0f} km/h > uscita {c['velocita_uscita_kmh']}: non mostrata")
            continue
        c["velocita_media_kmh"] = round(media)
        if verbose:
            print(f"frame {c['frame']} {c['colpo']}: media del volo {media:.0f} km/h (volo {volo:.2f} s, {d:.1f} m)")


def aggiorna(video, cartella_dati="outputs/dati", calibrazione=None, verbose=True, mano="auto"):
    nome = os.path.splitext(os.path.basename(video))[0]
    p_json = os.path.join(cartella_dati, nome + "_velocita_punti.json")
    colpi = json.load(open(p_json))
    t = vu.leggi_tracking(os.path.join(cartella_dati, nome + "_tracking.csv"))
    t["tempi"] = fotogrammi.tempi_reali(video, cartella_dati, t["fps"], verbose=False)
    cal, _ = carica_per_video(video, calibrazione)
    cam = camera_da_json(cal)
    tn = {int(f): tuple(p) for f, p, v in zip(t["frame"], t["palla"], t["vista"]) if v}
    altezze = {int(f): float(b[3] - b[1]) for f, b in zip(t["frame"], t["box"]) if np.isfinite(b[3] - b[1])}
    # i rimbalzi gia' usati (passo rieseguito) non valgono per altri colpi
    usati = set()
    for c in colpi:
        m = re.search(r"rimbalzo al frame (\d+)", str(c.get("nota", "")))
        if m and str(c.get("nota", "")).startswith(NOTA_RIMBALZO):
            usati.add(int(m.group(1)))
        if c.get("rimbalzo_trovato_frame") not in (None, ""):
            usati.add(int(c["rimbalzo_trovato_frame"]))
    da_stimare = lambda c: (c.get("velocita_uscita_kmh", "") == "" and c.get("velocita_rimbalzo_kmh", "") == ""
                            and not str(c.get("nota", "")).startswith(NOTA_RIMBALZO))

    def applica(c, risultato, come, come_breve):
        campi, fb = risultato
        usati.add(fb)
        c.update({"rimbalzo_trovato_x_m": campi["rimbalzo_x_m"], "rimbalzo_trovato_y_m": campi["rimbalzo_y_m"],
                  "rimbalzo_trovato_frame": int(fb), "rimbalzo_trovato_come": come_breve})
        if c["colpo"] != "servizio":
            campi.pop("rimbalzo_x_m"), campi.pop("rimbalzo_y_m")
        c.update(campi)
        if verbose:
            print(f"frame {c['frame']} {c['colpo']}: circa {campi['velocita_rimbalzo_kmh']} km/h ({come}), {campi['direzione']}")

    # passi 1-3: rimbalzo visto da TrackNet
    for c in colpi:
        if not da_stimare(c):
            continue
        s = stima(t, tn, altezze, cam, c)
        if s is None:
            continue
        fb = int(s["nota"].split("rimbalzo al frame ")[1].split()[0])
        if fb in usati:                               # lo stesso rimbalzo non vale per due colpi
            continue
        applica(c, (s, fb), "rimbalzo visto da TrackNet", "tracknet")

    # passo 4: buchi di TrackNet riempiti con il colore nel campo lontano
    cap = cv2.VideoCapture(video)
    altezza_img = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    for c in colpi:
        if da_stimare(c):
            r = stima_colore(t, tn, altezze, cam, c, video, cap, altezza_img / 1080, usati)
            if r is not None:
                applica(c, r, "rimbalzo trovato con il colore", "colore")

    # passo 5: rimbalzo coperto, ricostruito dalle curve prima e dopo
    for c in colpi:
        if da_stimare(c):
            r = stima_ricostruita(t, tn, cam, c, altezza_img, usati)
            if r is not None:
                applica(c, r, "rimbalzo ricostruito", "ricostruito")
            elif verbose:
                print(f"frame {c['frame']} {c['colpo']}: rimbalzo non visibile ne' ricostruibile")

    # passo 6: solo il punto del rimbalzo, per la mappa, nei colpi con una direzione che ne restano senza
    for c in colpi:
        if not c.get("direzione") or "rimbalzo_trovato_x_m" in c:
            continue
        nota = str(c.get("nota", ""))
        m = re.search(r"rimbalzo al frame (\d+)\)? a \(([-\d.]+); ([-\d.]+)\) m", nota)
        if nota.startswith(NOTA_RIMBALZO) and m:      # stima di un giro precedente: il rimbalzo e' nella nota
            come = "ricostruito" if nota.startswith(NOTA_RICOSTRUITO) else ("colore" if "con il colore" in nota else "tracknet")
            c.update({"rimbalzo_trovato_x_m": float(m.group(2)), "rimbalzo_trovato_y_m": float(m.group(3)),
                      "rimbalzo_trovato_frame": int(m.group(1)), "rimbalzo_trovato_come": come})
            continue
        r = rimbalzo_dopo_colpo(t, tn, cam, c, video, cap, altezza_img / 1080, altezza_img, usati)
        if r is None:
            if verbose:
                print(f"frame {c['frame']} {c['colpo']}: punto del rimbalzo non trovato")
            continue
        x, y, fb, come = r
        usati.add(fb)
        if (PUNTO4 and nota.startswith(NOTA_ESTESA) and c.get("velocita_uscita_kmh", "") == ""
                and c.get("velocita_rimbalzo_kmh", "") == ""):
            s4 = stima_da_contatto_esteso(t, tn, cam, c, x, y, fb, come)
            if s4 is not None:
                applica(c, s4, "rimbalzo del passo 6 e contatto della ricerca estesa", come)
                continue
        c.update({"rimbalzo_trovato_x_m": round(x, 2), "rimbalzo_trovato_y_m": round(y, 2),
                  "rimbalzo_trovato_frame": int(fb), "rimbalzo_trovato_come": come})
        d = direzione_dal_rimbalzo(c, x, y)
        if d and d != c["direzione"]:
            c["nota"] = (nota + "; " if nota else "") + f"il rimbalzo trovato a ({x:.1f}; {y:.1f}) m darebbe \"{d}\""
        if verbose:
            print(f"frame {c['frame']} {c['colpo']}: punto del rimbalzo ({x:.1f}; {y:.1f}) m, frame {fb} ({come})"
                  + (f", darebbe \"{d}\"" if d and d != c["direzione"] else ""))
    cap.release()
    aggiungi_media(t, colpi, verbose)
    vu.aggiungi_soglie(colpi)
    vu.aggiungi_dentro_fuori(colpi)
    # dritto inside-out / inside-in (dopo il rimbalzo trovato, che e' l'arrivo piu' sicuro)
    m = vu.aggiungi_inside(colpi, mano)
    if verbose:
        voti = vu.mano_dai_colpi(colpi)
        print(f"giocatore {'destro' if m == 'destra' else 'mancino'}" +
              (f" (dai contatti visti: {voti[1]} su {voti[2]})" if mano == "auto" else " (indicato)") +
              "".join(f"; dritto {c['frame']} {c['dritto_tipo']}" for c in colpi if c.get("dritto_tipo")))
    with open(os.path.join(cartella_dati, nome + "_velocita.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPI, extrasaction="ignore")
        w.writeheader()
        w.writerows(colpi)
    json.dump(colpi, open(p_json, "w"), default=float)
    return colpi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--dati", default="outputs/dati")
    ap.add_argument("--calibrazione")
    ap.add_argument("--mano", default="auto", choices=["auto", "destra", "sinistra"],
                    help="mano del giocatore, per inside-out/inside-in (auto: dai contatti visti)")
    a = ap.parse_args()
    aggiorna(a.video, a.dati, a.calibrazione, mano=a.mano)


if __name__ == "__main__":
    main()
