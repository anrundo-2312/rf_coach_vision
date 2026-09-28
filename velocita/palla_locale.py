"""
palla_locale.py - segue la pallina vicino al giocatore, dove TrackNet la perde.

TrackNet si basa sul movimento: quando la pallina arriva verso il giocatore
lungo la linea di vista della camera, nell'immagine quasi non si muove e
TrackNet non la vede, anche se e' grande e ben visibile. Qui la cerchiamo per
COLORE, solo attorno al giocatore e solo nei frame di un colpo.

Per ogni frame:
  1. dove dovrebbe essere la pallina: ultima posizione + ultimo spostamento;
  2. nel riquadro attorno alla previsione, pixel giallo-verdi (HSV);
  3. pulizia dei puntini, macchie separate, filtri su area, forma e
     riempimento (una pallina e' una macchia tonda e piena);
  4. la macchia piu' vicina alla previsione.
Se il rilevatore non trova niente ma TrackNet ha una posizione compatibile,
si usa quella; se non c'e' nessuno dei due il frame resta vuoto (pallina
coperta dal giocatore) e si continua dalla previsione.

Le dimensioni sono in frazioni dell'altezza del giocatore nell'immagine,
cosi' valgono per video di risoluzione e inquadratura diverse.
"""

import cv2
import numpy as np

# Colore della pallina (OpenCV: tinta 0-180). Largo abbastanza per terra rossa e cemento.
HSV_MIN, HSV_MAX = (22, 70, 110), (48, 255, 255)
# Diametro atteso della pallina: 6,7 cm su un giocatore di ~1,80 m.
DIAMETRO_REL = 0.067 / 1.80
# Area ammessa, in multipli del diametro atteso al quadrato (la soglia di
# colore prende solo il centro della pallina; la sfocatura la allunga).
AREA_MIN, AREA_MAX = 0.05, 3.0
PROPORZIONI = (0.35, 2.8)      # larghezza / altezza della macchia
RIEMPIMENTO = 0.45             # area / rettangolo che la contiene
FINESTRA_REL = 0.30            # raggio della zona di ricerca, in altezze del giocatore
BUCO_MAX = 8                   # frame di fila senza pallina prima di arrendersi


def candidati(frame, cx, cy, h_giocatore):
    """Macchie con colore, dimensione e forma da pallina attorno a (cx, cy)."""
    H, W = frame.shape[:2]
    R = max(60, FINESTRA_REL * h_giocatore)
    x0, y0 = max(0, int(cx - R)), max(0, int(cy - R))
    x1, y1 = min(W, int(cx + R)), min(H, int(cy + R))
    if x1 <= x0 or y1 <= y0:
        return []
    hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, HSV_MIN, HSV_MAX)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    d = DIAMETRO_REL * h_giocatore
    out = []
    for i in range(1, n):
        a, bw, bh = st[i, cv2.CC_STAT_AREA], st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
        if not (AREA_MIN * d * d <= a <= AREA_MAX * d * d):
            continue
        if not (PROPORZIONI[0] <= bw / bh <= PROPORZIONI[1]) or a < RIEMPIMENTO * bw * bh:
            continue
        out.append((cen[i][0] + x0, cen[i][1] + y0, min(bw, bh)))
    return out


def segui(video, primo, ultimo, tracknet, altezze, seme=None):
    """
    Traccia della pallina nei frame primo..ultimo (numerati da 1 come nel tracking CSV).

    tracknet: {frame: (x, y)} posizioni viste da TrackNet
    altezze:  {frame: altezza del giocatore in pixel}
    seme:     (frame, x, y) da cui partire; di default la prima posizione TrackNet
    Restituisce {frame: (x, y, fonte)} con fonte "locale" o "tracknet".
    """
    if seme is None:
        dentro = [f for f in sorted(tracknet) if primo <= f <= ultimo]
        if not dentro:
            return {}
        seme = (dentro[0], *tracknet[dentro[0]])
    f0, sx, sy = seme
    traccia = {f0: (sx, sy, "tracknet" if f0 in tracknet else "locale")}

    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)          # il frame successivo al seme (0-based = f0)
    ultimi = [(f0, sx, sy)]
    buco = 0
    for f in range(f0 + 1, ultimo + 1):
        ok, fr = cap.read()
        if not ok:
            break
        h = altezze.get(f) or altezze.get(f - 1) or 300.0
        # previsione a velocita' costante dagli ultimi due punti
        (fa, xa, ya) = ultimi[-1]
        if len(ultimi) >= 2:
            (fb, xb, yb) = ultimi[-2]
            vx, vy = (xa - xb) / (fa - fb), (ya - yb) / (fa - fb)
        else:
            vx = vy = 0.0
        px, py = xa + vx * (f - fa), ya + vy * (f - fa)
        passo = np.hypot(vx, vy) * (f - fa)
        cancello = max(0.12 * h, 2.5 * passo)     # quanto lontano dalla previsione accettiamo

        scelto = None
        c = candidati(fr, px, py, h)
        if c:
            x, y, _ = min(c, key=lambda t: np.hypot(t[0] - px, t[1] - py))
            if np.hypot(x - px, y - py) <= cancello:
                scelto = (x, y, "locale")
        if scelto is None and f in tracknet:
            x, y = tracknet[f]
            if np.hypot(x - px, y - py) <= cancello:
                scelto = (x, y, "tracknet")
        if scelto is None:
            buco += 1
            if buco > BUCO_MAX:
                break
            continue
        buco = 0
        traccia[f] = scelto
        ultimi.append((f, scelto[0], scelto[1]))
    cap.release()
    return traccia
