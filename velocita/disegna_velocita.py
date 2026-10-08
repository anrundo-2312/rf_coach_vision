"""
disegna_velocita.py - riscrive il video con, per ogni colpo del giocatore,
tipo di colpo, velocita' di uscita in km/h e direzione, piu' una piccola
mappa del campo vista dall'alto con da dove parte il colpo e dove va, un
contatore dei colpi in alto a destra e, alla fine, la scheda della sessione.

    python velocita/disegna_velocita.py --video inputs/<video>.mp4

Legge outputs/dati/<video>_velocita_punti.json (velocita_uscita.py,
direzione_nascosta.py, velocita_rimbalzo.py), e per il tracking della pallina
<video>_tracking.csv e <video>_palline_ferme.csv, e scrive
outputs/video/<video>_velocita.mp4 in H.264, cosi' si vede anche nel browser.
Il video di partenza e' quello originale: niente px/s. Le velocita' scritte
sono quelle calcolate per riepilogo.CORREZIONE_VELOCITA (0,85: il 15% in meno,
deciso dall'utente il 2 ottobre); nel CSV dei colpi restano quelle calcolate.
Con riepilogo.py
scrive anche, in outputs/dati, <video>_riepilogo.csv/.json e
<video>_scheda.png (le metriche della sessione e la scheda per l'allievo).

Cosa compare per ogni colpo:
  - "uscita X km/h": velocita' misurata subito dopo il colpo (velocita_uscita.py);
  - "circa X km/h (dal rimbalzo)": stimata dal rimbalzo nel campo avversario
    (velocita_rimbalzo.py), meno precisa: margine circa +-15%;
  - "circa X km/h (rimbalzo ricostruito)": il rimbalzo era coperto ed e' stato
    ricostruito dalle curve prima e dopo (velocita_rimbalzo.py): margine circa +-20%;
  - sotto, in piccolo, "media X km/h": la velocita' media del volo, dal colpo
    al rimbalzo (velocita_media_kmh), se il rimbalzo e' stato trovato;
  - "km/h non disponibile" con la direzione: la velocita' non si puo' misurare
    (pallina coperta o mossa al colpo) ma la direzione si';
  - "km/h non disponibile" in grigio: niente di affidabile.
  - sotto la direzione, dove e' caduta la pallina se il rimbalzo e' stato trovato:
    "dentro" con la fascia (profonda, media, corta, palla corta), "fuori: lunga", "fuori: larga"...;
    "palla corta (1o rimbalzo non visto)": la pallina e' morta davanti alla riga del servizio ma il
    primo rimbalzo non si e' visto (velocita_rimbalzo.py passo 6b): dentro o fuori non si sa;
  La riga dentro/fuori e la media compaiono quando la pallina tocca terra
  (RIVELA_AL_RIMBALZO; il loro posto nell'etichetta c'e' gia' da prima, cosi'
  le righe non si spostano).
Il tracking della pallina (MOSTRA_TRACKING = True, acceso di default): per capire dove TrackNet
vede la pallina e dove no, e quali punti sono entrati nel calcolo.
  - anelli gialli: i punti visti da TrackNet (<video>_tracking.csv, solo fonte "tracknet": le
    posizioni stimate da InpaintNet no) che il calcolo non ha usato, a scia: l'ultimo secondo
    (SCIA_S), i piu' vecchi sbiaditi;
  - anelli rossi: i punti usati per il calcolo del colpo (TrackNet o rilevatore di colore, sul video
    non si distinguono), al posto dell'anello giallo, visibili per tutta la durata dell'etichetta.
    Anelli gialli attorno al contatto senza anelli rossi = TrackNet c'era ma il calcolo non li ha usati;
  - anelli grigi: punti di TrackNet scartati come palline ferme in campo (<video>_palline_ferme.csv,
    scritto da velocita_uscita.py; si controllano solo nelle finestre dei colpi).
  Il rosso nella mappa (bordo e onda del rimbalzo "fuori") e nel contatore resta com'e'.
Con MOSTRA_TRACKING = False il video e' come prima: anelli gialli solo sui punti usati per il calcolo.

La mappa in basso a sinistra: campo visto dall'alto, giocatore in basso. Pallino
del colore del colpo = contatto; la freccia parte al colpo e si allunga mentre
la pallina vola, fino al punto del rimbalzo se e' stato trovato (arriva li'
nel fotogramma del rimbalzo), altrimenti fino a 21 m in mezzo secondo (nel
servizio fino al rimbalzo previsto); fascia grigia = centro (terzo centrale
del singolo); nel servizio il riquadro diviso in tre, con la fascia colpita
evidenziata. Quando la pallina tocca terra spunta il pallino del rimbalzo,
con un'onda che si allarga: giallo bordato di nero = rimbalzo visto (TrackNet
o colore; nella palla corta dalla serie di rimbalzi il primo visto), cerchio giallo vuoto = rimbalzo ricostruito (era coperto), bordo
rosso = fuori; pallino bianco = rimbalzo del servizio previsto dal calcolo,
quando quello vero non si trova.

Il contatore in alto a destra: per ogni tipo di colpo quanti dentro, quanti
fuori e quanti colpi finora (riepilogo.py: si contano i colpi con una velocita'
o una direzione). "colpi" sale al colpo, "dentro"/"fuori" quando la pallina
tocca terra; il numero che cambia si illumina per un attimo. I colpi con
l'esito non visto contano solo in "colpi".

Alla fine del video, per FINALE_S secondi, la scheda della sessione
(riepilogo.scheda) sopra l'ultimo fotogramma sfocato.
"""

import argparse
import csv
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import riepilogo  # noqa: E402

DURATA_S = 1.7                 # quanto resta la scritta dopo il contatto...
DOPO_RIMBALZO_S = 1.0          # ...e almeno quanto dopo il rimbalzo trovato
FRECCIA_SENZA_RIMBALZO_S = 0.5 # senza rimbalzo trovato la freccia arriva a 21 m in mezzo secondo
SPUNTA_S = 0.35                # pallino del rimbalzo: si gonfia e torna normale in 0,35 s
ONDA_S = 0.6                   # l'onda attorno al pallino si allarga e sparisce in 0,6 s
COMPARSA_S = 0.25              # dentro/fuori e media: dissolvenza in entrata
RIVELA_AL_RIMBALZO = True      # False: dentro/fuori e media compaiono subito, al colpo
LAMPO_S = 0.7                  # contatore: quanto resta illuminato il numero che cambia
FINALE_S = 6.0                 # scheda della sessione alla fine del video
MOSTRA_TRACKING = True         # scia dei punti di TrackNet, punti usati in rosso, palline ferme in grigio; False = come prima
SCIA_S = 1.0                   # la scia dei punti di TrackNet: l'ultimo secondo...
SCIA_MIN = 0.15                # ...con i punti piu' vecchi quasi trasparenti
LARGHEZZA_MAX = 1920
ALTEZZA_MIN = 720              # i video piu' piccoli (es. 640x360) si ingrandiscono a 720p: scritte e scheda leggibili
COLORI = {"dritto": (60, 200, 60), "rovescio": (255, 170, 60), "servizio": (0, 200, 255)}
F = cv2.FONT_HERSHEY_SIMPLEX
GIALLO = (0, 230, 255)         # anelli dei punti di TrackNet (con MOSTRA_TRACKING False: i punti usati)
ROSSO = (0, 0, 230)
GRIGIO_FERMA = (170, 170, 170) # punti di TrackNet su palline ferme scartati
VERDE_OK = (12, 163, 12)       # contatore: dentro
ROSSO_KO = (59, 59, 208)       # contatore: fuori

# stili delle righe dell'etichetta: (scala, spessore, grigio del testo)
STILI = {"nome": (1.5, 3, 255), "valore": (2.0, 5, 255), "sotto": (1.0, 2, 215),
         "riga": (1.1, 3, 255), "nota": (0.8, 2, 200)}


def etichetta(fr, righe, colore):
    """
    righe: lista di (testo, stile, visibilita' 0-1). Una riga con visibilita' 0 tiene il suo posto ma
    non si vede (compare piu' tardi, al rimbalzo); tra 0 e 1 e' in dissolvenza.
    Le misure sono pensate per 1080 righe e si scalano con l'altezza del fotogramma (a 1080p identiche).
    """
    k = fr.shape[0] / 1080
    px = lambda v: int(round(v * k))
    stile = lambda s: (STILI[s][0] * k, max(1, int(round(STILI[s][1] * k))), STILI[s][2])
    x0, y0 = px(30), px(30)
    dims = [cv2.getTextSize(t, F, stile(s)[0], stile(s)[1])[0] for t, s, _ in righe]
    W = max(d[0] for d in dims) + px(40)
    H = sum(d[1] for d in dims) + px(22) * len(dims) + px(20)
    ov = fr.copy()
    cv2.rectangle(ov, (x0, y0), (x0 + W, y0 + H), (0, 0, 0), -1)
    fr[:] = cv2.addWeighted(ov, 0.6, fr, 0.4, 0)
    cv2.rectangle(fr, (x0, y0), (x0 + px(10), y0 + H), colore, -1)
    y = y0 + px(10)
    for (t, s, vis), d in zip(righe, dims):
        y += d[1] + px(22)
        if vis <= 0:
            continue
        scala, spess, g = stile(s)
        if vis >= 1:
            cv2.putText(fr, t, (x0 + px(25), y), F, scala, (g, g, g), spess, cv2.LINE_AA)
        else:
            a, b = y - d[1] - px(6), y + px(10)   # solo la striscia della riga
            ov = fr[a:b].copy()
            cv2.putText(ov, t, (x0 + px(25), d[1] + px(6)), F, scala, (g, g, g), spess, cv2.LINE_AA)
            fr[a:b] = cv2.addWeighted(ov, vis, fr[a:b], 1 - vis, 0)


def esito_rimbalzo(c):
    """Riga di testo sul rimbalzo trovato (velocita_rimbalzo.py) o None."""
    if c.get("rimbalzo_trovato_come") == "serie":      # passo 6b: primo rimbalzo non visto
        return "palla corta (1o rimbalzo non visto)"
    esito = c.get("dentro_fuori", "")
    if esito == "dentro":
        return "dentro" + (", " + c["profondita"] if c.get("profondita") else "")
    if esito == "fuori":
        return "fuori: " + riepilogo.motivo_fuori(c)
    return None


def rimbalzo_frame(c):
    """Frame del rimbalzo trovato o None."""
    f = c.get("rimbalzo_trovato_frame")
    return None if f in (None, "") else int(f)


def comparsa(c, n, fps):
    """Visibilita' (0-1) di dentro/fuori e media: dissolvenza dal fotogramma del rimbalzo."""
    fb = rimbalzo_frame(c)
    if not RIVELA_AL_RIMBALZO or fb is None:
        return 1.0
    return float(np.clip((n - fb) / max(1.0, COMPARSA_S * fps) + 1e-9, 0, 1)) if n >= fb else 0.0


def righe_colpo(c, n, fps):
    """(righe dell'etichetta, colore) per un colpo, all'istante n."""
    vis = comparsa(c, n, fps)
    media = c.get("velocita_media_kmh", "")
    riga_media = [(f"media {riepilogo.corretta(media)} km/h", "sotto", vis)] if media not in ("", None) else []
    e = esito_rimbalzo(c)
    riga_esito = [(e, "riga", vis)] if e else []
    colore = COLORI.get(c["colpo"], (200, 200, 200))
    nome = ((c["colpo"] + (" " + c["dritto_tipo"] if c.get("dritto_tipo") else "")).upper(), "nome", 1)
    if c.get("velocita_uscita_kmh", "") != "":
        righe = [nome, (f"uscita {riepilogo.corretta(c['velocita_uscita_kmh'])} km/h", "valore", 1)] + riga_media
        if c.get("direzione"):
            righe.append((c["direzione"], "riga", 1))
        nota = "margine circa +-20 km/h" + (" - calibrazione standard" if c.get("calibrazione") == "standard" else "")
        return righe + riga_esito + [(nota, "nota", 1)], colore
    if c.get("velocita_rimbalzo_kmh", "") != "":
        # stima dal rimbalzo nel campo avversario (velocita_rimbalzo.py)
        if str(c.get("nota", "")).startswith("velocita' stimata dal rimbalzo ricostruito"):
            v, nota = f"circa {riepilogo.corretta(c['velocita_rimbalzo_kmh'])} km/h (rimbalzo ricostruito)", "rimbalzo coperto, ricostruito: margine circa +-20%"
        else:
            v, nota = f"circa {riepilogo.corretta(c['velocita_rimbalzo_kmh'])} km/h (dal rimbalzo)", "stima dal rimbalzo: margine circa +-15%"
        return [nome, (v, "valore", 1)] + riga_media + [(c["direzione"], "riga", 1)] + riga_esito + [(nota, "nota", 1)], colore
    if c.get("direzione"):
        # niente km/h, ma la direzione (direzione_nascosta.py o ricerca estesa)
        perche = ("pallina mossa al colpo: solo direzione" if str(c.get("nota", "")).startswith("pallina mossa")
                  else "pallina coperta al contatto: solo direzione")
        return [nome, ("km/h non disponibile", "valore", 1), (c["direzione"], "riga", 1)] + riga_esito + [(perche, "nota", 1)], colore
    motivo = ("misura non affidabile" if str(c.get("nota", "")).startswith("misura scartata")
              else "pallina coperta dal giocatore")
    return [nome, ("km/h non disponibile", "valore", 1), (motivo, "nota", 1)], (150, 150, 150)


def _blend(img, disegna, alfa):
    """Disegna su una copia e mescola con trasparenza alfa."""
    if alfa <= 0:
        return img
    ov = img.copy()
    disegna(ov)
    return cv2.addWeighted(ov, alfa, img, 1 - alfa, 0)


def _spunta(dt, r):
    """Raggio del pallino dt secondi dopo il rimbalzo: si gonfia fino a 1,5 volte e torna normale."""
    if dt < 0.12:
        return max(1, int(round(r * (0.3 + 1.2 * dt / 0.12))))
    if dt < SPUNTA_S:
        return max(1, int(round(r * (1.5 - 0.5 * (dt - 0.12) / (SPUNTA_S - 0.12)))))
    return r


def mappa(fr, colpo, n, fps):
    """Campo visto dall'alto (lato del giocatore in basso) con partenza e freccia fino al rimbalzo
    trovato o, se non c'e', fino a 21 m (servizio: fino al rimbalzo previsto). n = fotogramma attuale:
    la freccia cresce dal colpo al rimbalzo e il pallino spunta quando la pallina tocca terra."""
    m = 11                                     # pixel per metro
    w, h = int(13 * m), int(30.5 * m)          # da 5 m dietro il fondo vicino a 1,7 m oltre quello lontano
    img = np.full((h, w, 3), 35, np.uint8)
    pxf = lambda x, y: ((x + 1) * m, h - (y + 5.0) * m)
    px = lambda x, y: tuple(int(round(v)) for v in pxf(x, y))
    bianco = (230, 230, 230)
    for a, b in [((0, 0), (0, 23.77)), ((10.97, 0), (10.97, 23.77)), ((1.37, 0), (1.37, 23.77)),
                 ((9.60, 0), (9.60, 23.77)), ((0, 0), (10.97, 0)), ((0, 23.77), (10.97, 23.77)),
                 ((1.37, 5.485), (9.60, 5.485)), ((1.37, 18.285), (9.60, 18.285)), ((5.485, 5.485), (5.485, 18.285))]:
        cv2.line(img, px(*a), px(*b), bianco, 1, cv2.LINE_AA)
    cv2.line(img, px(-0.9, 11.885), px(11.9, 11.885), (0, 200, 255), 2)
    fb = rimbalzo_frame(colpo)
    trovato = fb is not None and colpo.get("rimbalzo_trovato_x_m") not in (None, "")
    servizio = colpo["colpo"] == "servizio" and "rimbalzo_x_m" in colpo
    if servizio:
        # riquadro del servizio diviso in tre: al T, al corpo, esterno
        terzo = (5.485 - 1.37) / 3
        for k in (1, 2):
            for x in (5.485 - k * terzo, 5.485 + k * terzo):
                cv2.line(img, px(x, 11.885), px(x, 18.285), (150, 150, 150), 1, cv2.LINE_AA)
        xa, ya = colpo["rimbalzo_x_m"], colpo["rimbalzo_y_m"]
        # evidenzia la fascia colpita (conta la posizione laterale; la profondita' e' imprecisa)
        verso = -1 if colpo["giocatore_x_m"] >= 5.485 else 1
        k = min(2, max(0, int((xa - 5.485) * verso // terzo)))
        xa0, xa1 = 5.485 + verso * k * terzo, 5.485 + verso * (k + 1) * terzo
        ov = img.copy()
        cv2.rectangle(ov, px(min(xa0, xa1), 18.285), px(max(xa0, xa1), 11.885), (0, 200, 255), -1)
        img = cv2.addWeighted(ov, 0.3, img, 0.7, 0)
    else:
        # fascia "centrale" nel campo avversario
        ov = img.copy()
        fascia = (5.485 - 1.37) / 3       # terzo centrale del singolo, come FASCIA_CENTRO in velocita_uscita.py
        cv2.rectangle(ov, px(5.485 - fascia, 23.77), px(5.485 + fascia, 11.885), (120, 120, 120), -1)
        img = cv2.addWeighted(ov, 0.35, img, 0.65, 0)
        xa, ya = colpo["arrivo_x_m"], 21.0
    # la freccia parte dallo stesso punto usato per il lato di partenza (partenza_da)
    xs, ys = colpo.get("_partenza_x_m", colpo["contatto_x_m"]), colpo["contatto_y_m"]
    col = COLORI.get(colpo["colpo"], (255, 255, 255))
    cv2.circle(img, px(xs, ys), 5, col, -1, cv2.LINE_AA)
    f0 = int(colpo["frame"])
    p0 = np.array(pxf(xs, ys))
    if trovato:
        xf, yf = float(colpo["rimbalzo_trovato_x_m"]), float(colpo["rimbalzo_trovato_y_m"])
        p1 = np.array(pxf(xf, yf))
        lung = np.linalg.norm(p1 - p0)
        fine = p1 - (p1 - p0) / lung * 7 if lung > 14 else p1      # la punta si ferma sul bordo del pallino
        f_arrivo = max(fb, f0 + 1)
    else:
        fine = np.array(pxf(xa, ya))
        f_arrivo = f0 + max(1, int(round(FRECCIA_SENZA_RIMBALZO_S * fps)))
    # la freccia si allunga mentre la pallina vola (un po' piu' piano alla fine: l'aria la frena)
    p = float(np.clip((n - f0) / (f_arrivo - f0), 0, 1))
    p = 1 - (1 - p) ** 1.25
    punta = p0 + (fine - p0) * p
    lung = float(np.linalg.norm(punta - p0))
    if lung >= 2:
        cv2.arrowedLine(img, px(xs, ys), tuple(int(round(v)) for v in punta), col, 2, cv2.LINE_AA,
                        tipLength=min(0.5, 9 / lung))
    if servizio and not trovato and n >= f_arrivo:
        dt = (n - f_arrivo) / fps
        cv2.circle(img, px(xa, ya), _spunta(dt, 4), (255, 255, 255), -1, cv2.LINE_AA)     # rimbalzo previsto
    if trovato and n >= fb:
        # dove la pallina ha rimbalzato davvero: spunta quando tocca terra, con un'onda attorno
        dt = (n - fb) / fps
        pb = px(xf, yf)
        fuori = colpo.get("dentro_fuori") == "fuori"
        if dt < ONDA_S:
            raggio = int(round(7 + 20 * dt / ONDA_S))
            img = _blend(img, lambda o: cv2.circle(o, pb, raggio, ROSSO if fuori else GIALLO, 2, cv2.LINE_AA),
                         1 - dt / ONDA_S)
        bordo = ROSSO if fuori else (0, 0, 0)
        if colpo.get("rimbalzo_trovato_come") == "ricostruito":
            r = _spunta(dt, 6)
            cv2.circle(img, pb, r, bordo, 4, cv2.LINE_AA)
            cv2.circle(img, pb, r, GIALLO, 2, cv2.LINE_AA)
        else:
            # bordo rosso se la pallina e' fuori
            cv2.circle(img, pb, _spunta(dt, 7), bordo, -1, cv2.LINE_AA)
            cv2.circle(img, pb, _spunta(dt, 5), GIALLO, -1, cv2.LINE_AA)
    H, W = fr.shape[:2]
    s = H / 1080
    img = cv2.resize(img, None, fx=s, fy=s)
    y0, x0 = H - img.shape[0] - int(20 * s), int(20 * s)
    fr[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img


# ------------------------------------------------------------------ tracking della pallina
def leggi_punti(percorso, solo_tracknet=True):
    """{frame: (x, y)} dal tracking CSV (solo i punti visti da TrackNet) o dal CSV delle palline ferme."""
    if not os.path.exists(percorso):
        return {}
    punti = {}
    for r in csv.DictReader(open(percorso, newline="")):
        if solo_tracknet and r.get("pallina_fonte") != "tracknet":
            continue
        try:
            punti[int(r["frame"])] = (float(r["pallina_x"]), float(r["pallina_y"]))
        except (ValueError, KeyError, TypeError):
            continue
    return punti


def cerchio(img, centro, raggio, colore, spessore, alfa=1.0):
    """Cerchio (spessore -1 = pieno) con trasparenza alfa, mescolato solo nel riquadro attorno."""
    x, y = int(round(centro[0])), int(round(centro[1]))
    if alfa >= 1:
        cv2.circle(img, (x, y), raggio, colore, spessore, cv2.LINE_AA)
        return
    m = raggio + max(spessore, 0) + 2
    x0, y0, x1, y1 = max(0, x - m), max(0, y - m), min(img.shape[1], x + m + 1), min(img.shape[0], y + m + 1)
    if x1 <= x0 or y1 <= y0:
        return
    roi = img[y0:y1, x0:x1]
    ov = roi.copy()
    cv2.circle(ov, (x - x0, y - y0), raggio, colore, spessore, cv2.LINE_AA)
    roi[:] = cv2.addWeighted(ov, alfa, roi, 1 - alfa, 0)


def disegna_tracking(fr, n, tracknet, ferme, attivi, fps, s):
    """Scia dei punti di TrackNet (anelli gialli, grigi se palline ferme) e punti usati per il calcolo
    (anelli rossi, al posto di quelli gialli). Coordinate del video originale; s = scala del video in
    uscita (per tenere le misure uguali)."""
    r, spess = max(4, int(8 / s)), max(2, int(2 / s))
    usati = {}                                  # frame -> posizioni usate dal calcolo, fino a questo frame
    for c in attivi:
        for f, x, y in c.get("_punti", []):
            if f <= n:
                usati.setdefault(int(f), []).append((x, y))
    scia = max(1, int(round(SCIA_S * fps)))
    for f in range(n - scia + 1, n + 1):
        p = tracknet.get(f)
        if p is None:
            continue
        if any(abs(p[0] - x) <= 2 and abs(p[1] - y) <= 2 for x, y in usati.get(f, [])):
            continue                            # punto usato: anello rosso qui sotto, non giallo
        alfa = 1 - (1 - SCIA_MIN) * (n - f) / scia
        cerchio(fr, p, r, GRIGIO_FERMA if f in ferme else GIALLO, spess, alfa)
    for punti in usati.values():
        for x, y in punti:
            cerchio(fr, (x, y), r, ROSSO, spess)


# ------------------------------------------------------------------ contatore
def eventi_contatore(colpi):
    """Per ogni colpo contato (riepilogo.ha_dati): (tipo, frame del colpo, esito, frame del rimbalzo)."""
    ev = []
    for c in colpi:
        if riepilogo.ha_dati(c):
            ev.append((c["colpo"], int(c["frame"]), riepilogo.esito(c), rimbalzo_frame(c)))
    return ev


def contatore(fr, tipi, eventi, n, fps):
    """Tabellina in alto a destra: per tipo di colpo dentro, fuori e colpi fino al fotogramma n."""
    if not tipi:
        return
    H, W = fr.shape[:2]
    s = H / 1080
    cols = ["dentro", "fuori", "colpi"]
    # conteggi e ultimo cambiamento di ogni casella
    val, ultimo = {}, {}
    for t in tipi:
        for k in cols:
            val[t, k], ultimo[t, k] = 0, -10 ** 9
    for tipo, f, esito, fb in eventi:
        if tipo not in tipi:
            continue
        if f < n:                                   # l'etichetta compare dal fotogramma dopo il colpo
            val[tipo, "colpi"] += 1
            ultimo[tipo, "colpi"] = max(ultimo[tipo, "colpi"], f + 1)
        if esito and fb is not None and fb <= n:
            val[tipo, esito] += 1
            ultimo[tipo, esito] = max(ultimo[tipo, esito], fb)
    nome_w, col_w, riga_h, testa_h, pad = int(170 * s), int(100 * s), int(52 * s), int(38 * s), int(18 * s)
    Wb = pad * 2 + nome_w + col_w * len(cols)
    Hb = pad * 2 + testa_h + riga_h * len(tipi)
    x0, y0 = W - Wb - int(30 * s), int(30 * s)
    box = fr[y0:y0 + Hb, x0:x0 + Wb]
    box[:] = (box * 0.3).astype(np.uint8)          # fondo nero al 70%: qui i numeri sono piccoli
    # intestazione delle colonne
    for j, k in enumerate(cols):
        cx = x0 + pad + nome_w + col_w * j + col_w // 2
        tw = cv2.getTextSize(k, F, 0.7 * s, max(1, int(round(s))))[0][0]
        cv2.putText(fr, k, (cx - tw // 2, y0 + pad + int(24 * s)), F, 0.7 * s, (190, 190, 190), max(1, int(round(s))), cv2.LINE_AA)
    for i, t in enumerate(tipi):
        yc = y0 + pad + testa_h + riga_h * i + riga_h // 2
        q = int(7 * s)
        cv2.rectangle(fr, (x0 + pad, yc - q), (x0 + pad + 2 * q, yc + q), COLORI.get(t, (200, 200, 200)), -1)
        cv2.putText(fr, riepilogo.NOMI[t], (x0 + pad + int(26 * s), yc + int(11 * s)), F, 0.95 * s, (255, 255, 255),
                    max(1, int(round(2 * s))), cv2.LINE_AA)
        for j, k in enumerate(cols):
            cx = x0 + pad + nome_w + col_w * j + col_w // 2
            # il numero appena cambiato si illumina e torna normale in LAMPO_S
            dt = (n - ultimo[t, k]) / fps
            if 0 <= dt < LAMPO_S:
                lampo = {"dentro": VERDE_OK, "fuori": ROSSO_KO, "colpi": (200, 200, 200)}[k]
                a = 0.85 * (1 - dt / LAMPO_S)
                xa_, xb_ = cx - col_w // 2 + int(8 * s), cx + col_w // 2 - int(8 * s)
                ya_, yb_ = yc - riga_h // 2 + int(5 * s), yc + riga_h // 2 - int(5 * s)
                cella = fr[ya_:yb_, xa_:xb_]
                cella[:] = cv2.addWeighted(np.full_like(cella, lampo), a, cella, 1 - a, 0)
            testo = str(val[t, k])
            tw = cv2.getTextSize(testo, F, 1.2 * s, max(1, int(round(3 * s))))[0][0]
            cv2.putText(fr, testo, (cx - tw // 2, yc + int(14 * s)), F, 1.2 * s, (255, 255, 255),
                        max(1, int(round(3 * s))), cv2.LINE_AA)


def fine_colpo(c, fps):
    """Ultimo fotogramma in cui si vede l'etichetta del colpo."""
    fb = rimbalzo_frame(c)
    fine = int(c["frame"]) + int(DURATA_S * fps)
    return max(fine, fb + int(DOPO_RIMBALZO_S * fps)) if fb is not None else fine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--dati", default="outputs/dati")
    ap.add_argument("--out")
    a = ap.parse_args()
    nome = os.path.splitext(os.path.basename(a.video))[0]
    colpi = json.load(open(os.path.join(a.dati, nome + "_velocita_punti.json")))
    uscita = a.out or os.path.join(os.path.dirname(a.dati.rstrip("/")) or ".", "video", nome + "_velocita.mp4")
    os.makedirs(os.path.dirname(uscita), exist_ok=True)

    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    W, H = int(cap.get(3)), int(cap.get(4))
    s = min(1.0, LARGHEZZA_MAX / W)
    if H * s < ALTEZZA_MIN:                    # video piccolo: si ingrandisce (le scritte restano leggibili)
        s = ALTEZZA_MIN / H
    size = (int(W * s) // 2 * 2, int(H * s) // 2 * 2)
    tmp = uscita + ".tmp.mp4"
    out = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    fine = {id(c): fine_colpo(c, fps) for c in colpi}
    rie = riepilogo.calcola(colpi, nome)
    tipi = [r["colpo"] for r in rie["tipi"]]
    eventi = eventi_contatore(colpi)
    tracknet = leggi_punti(os.path.join(a.dati, nome + "_tracking.csv")) if MOSTRA_TRACKING else {}
    ferme = leggi_punti(os.path.join(a.dati, nome + "_palline_ferme.csv"), solo_tracknet=False) if MOSTRA_TRACKING else {}
    n, ultimo = 0, None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        n += 1
        attivi = [c for c in colpi if c["frame"] < n <= fine[id(c)]]
        if MOSTRA_TRACKING:
            disegna_tracking(fr, n, tracknet, ferme, attivi, fps, s)
        else:
            for c in attivi:
                for f, x, y in c.get("_punti", []):
                    if f <= n:
                        cv2.circle(fr, (int(x), int(y)), max(4, int(8 / s)), (0, 230, 255), max(2, int(2 / s)), cv2.LINE_AA)
        fr = cv2.resize(fr, size, interpolation=cv2.INTER_AREA if s <= 1 else cv2.INTER_LINEAR)
        ultimo = fr.copy()                      # senza le scritte: sfondo della scheda finale
        # se due colpi sono vicini, l'etichetta del piu' recente sostituisce l'altra (non si sovrappongono)
        for c in sorted(attivi, key=lambda c: c["frame"])[-1:]:
            righe, colore = righe_colpo(c, n, fps)
            etichetta(fr, righe, colore)
            if c.get("direzione"):
                mappa(fr, c, n, fps)
        contatore(fr, tipi, eventi, n, fps)
        out.write(fr)
    # scheda della sessione alla fine, sopra l'ultimo fotogramma sfocato (dissolvenza di mezzo secondo)
    rie["durata_s"] = round(n / fps, 1) if fps else None
    if ultimo is not None and FINALE_S > 0:
        sch = riepilogo.scheda(rie, size[0], size[1], sfondo=ultimo)
        dissolvenza = max(1, int(0.5 * fps))
        for i in range(int(FINALE_S * fps)):
            out.write(sch if i >= dissolvenza else cv2.addWeighted(sch, i / dissolvenza, ultimo, 1 - i / dissolvenza, 0))
    out.release()
    for p in riepilogo.salva(rie, a.dati):
        print("scritto", p)
    # H.264 (si vede anche nel browser e su Colab) se c'e' ffmpeg; altrimenti resta mp4v,
    # che si apre comunque con il lettore del PC.
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "23", uscita], check=True)
        os.remove(tmp)
    except (FileNotFoundError, subprocess.CalledProcessError):
        os.replace(tmp, uscita)
        print("ffmpeg non disponibile: video salvato in mp4v (si apre con il lettore del PC, non nel browser).")
    print(f"{n} frame scritti in {uscita} (+ {FINALE_S:.0f} s di scheda finale)")


if __name__ == "__main__":
    main()
