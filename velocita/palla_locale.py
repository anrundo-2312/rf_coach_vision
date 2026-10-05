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

Giallo FERMO: prima di cominciare si calcola lo sfondo del tratto (mediana di
15 fotogrammi) e tutto cio' che e' giallo anche nello sfondo (borse, sedie,
cartelli, palline ferme a terra) non puo' essere la pallina in gioco. Sul video
alcaraz, al dritto del frame 567, senza questo il rilevatore seguiva una borsa
gialla a bordo campo.

Palline FERME viste da TrackNet (tracknet_fermi, 3 ottobre): TrackNet da' un
solo punto per fotogramma e, quando la pallina in gioco non si vede bene (prima
del colpo, vicino al corpo), a volte indica una pallina ferma in campo. Un
punto di TrackNet e' una pallina ferma se nella stessa zona c'e' una pallina
gialla piccola anche 0,4-0,6 s prima e dopo, e il punto sta a meta' tra le due
(ferma, o che rotola piano). velocita_uscita.py li toglie prima di seguire la
pallina; si guardano solo i punti che, portati a terra, cadono in campo o
attorno (non quelli sopra la recinzione, dove alberi e cespugli secchi sono
pieni di giallo). Sul video Giorgio (palline a terra oltre la rete, camera
bassa) TrackNet metteva li' la pallina proprio prima dei colpi. La traccia poi
parte dal primo punto di TrackNet confermato da un altro punto vicino (entro 2
frame), non da un punto isolato.

Ricerca ESTESA (esteso=True), usata da velocita_uscita.py solo per la
DIREZIONE dei colpi che la ricerca normale non riesce a misurare:
  - la pallina "strisciata" dal mosso al colpo (macchia allungata fino a 5
    volte, meno piena) e' accettata;
  - se la pallina era persa, un punto di TrackNet vicino all'ultima posizione
    (entro 0,3 altezze del giocatore per frame passato) la riaggancia, anche se
    e' lontano dalla previsione (dopo il colpo la pallina va nel verso opposto).
Con questi punti la direzione e' giusta ma la velocita' tende a uscire troppo
bassa (alcaraz: servizio 124 km/h e dritto 66 km/h, sotto la velocita' MEDIA
fino al rimbalzo): per questo la ricerca estesa non si usa per i km/h.

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
# Giallo fermo: fotogrammi per lo sfondo del tratto e allargamento della maschera (px)
CAMPIONI_SFONDO = 15
ALLARGA_FERMO = 15
# Ricerca estesa (solo per la direzione): pallina mossa e riaggancio a TrackNet
AREA_MAX_MOSSO = 5.0
PROPORZIONI_MOSSO = (0.2, 5.0)
RIEMPIMENTO_MOSSO = 0.3
RIAGGANCIO_REL = 0.3           # altezze del giocatore per frame passato dall'ultima posizione
# Palline ferme viste da TrackNet (tracknet_fermi): si guarda la stessa zona prima e dopo
FERMA_DT_S = (0.4, 0.6)        # secondi prima e dopo il punto
FERMA_RAGGIO_REL = 0.02        # tremolio del punto, in altezze del giocatore
FERMA_DERIVA_REL = 0.10        # altezze del giocatore al secondo: piu' lenta di cosi' e' una pallina che rotola
FERMA_AREA = (3, 120)          # area della macchia gialla (px quadrati a 1080p): la pallina lontana, un puntino
                               # (quella in mano al giocatore vicino e' piu' grande e non conta)


def giallo_fermo(video, primo, ultimo):
    """Maschera (0/255) del giallo presente nello sfondo del tratto primo..ultimo."""
    cap = cv2.VideoCapture(video)
    imgs = []
    for f in np.linspace(primo, ultimo, CAMPIONI_SFONDO).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f - 1)
        ok, fr = cap.read()
        if ok:
            imgs.append(fr)
    cap.release()
    if not imgs:
        return None
    sfondo = np.median(np.stack(imgs), axis=0).astype(np.uint8)
    m = cv2.inRange(cv2.cvtColor(sfondo, cv2.COLOR_BGR2HSV), HSV_MIN, HSV_MAX)
    return cv2.dilate(m, np.ones((ALLARGA_FERMO, ALLARGA_FERMO), np.uint8))


def candidati(frame, cx, cy, h_giocatore, fermo=None, mosso=False):
    """
    Macchie con colore, dimensione e forma da pallina attorno a (cx, cy).
    fermo: maschera del giallo fermo (giallo_fermo): le macchie li' sopra si scartano.
    mosso: accetta anche la pallina allungata dal mosso (ricerca estesa).
    """
    area_max, proporzioni, riempimento = ((AREA_MAX_MOSSO, PROPORZIONI_MOSSO, RIEMPIMENTO_MOSSO) if mosso
                                          else (AREA_MAX, PROPORZIONI, RIEMPIMENTO))
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
        if not (AREA_MIN * d * d <= a <= area_max * d * d):
            continue
        if not (proporzioni[0] <= bw / bh <= proporzioni[1]) or a < riempimento * bw * bh:
            continue
        x, y = cen[i][0] + x0, cen[i][1] + y0
        if fermo is not None and fermo[min(H - 1, int(y)), min(W - 1, int(x))]:
            continue
        out.append((x, y, min(bw, bh)))
    return out


def macchie_gialle(frame, cx, cy, raggio, scala):
    """Centri delle macchie gialle piccole (anche un puntino lontano) entro raggio da (cx, cy)."""
    H, W = frame.shape[:2]
    r = int(np.ceil(raggio)) + 2
    x0, y0, x1, y1 = max(0, int(cx) - r), max(0, int(cy) - r), min(W, int(cx) + r + 1), min(H, int(cy) + r + 1)
    if x1 <= x0 or y1 <= y0:
        return []
    m = cv2.inRange(cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV), HSV_MIN, HSV_MAX)
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    a_min, a_max = FERMA_AREA[0] * scala ** 2, FERMA_AREA[1] * scala ** 2
    return [(cen[i][0] + x0, cen[i][1] + y0) for i in range(1, n)
            if a_min <= st[i, cv2.CC_STAT_AREA] <= a_max
            and np.hypot(cen[i][0] + x0 - cx, cen[i][1] + y0 - cy) <= raggio]


def tracknet_fermi(video, primo, ultimo, tracknet, altezze, fps, a_terra=None):
    """
    Frame del tratto primo..ultimo in cui il punto di TrackNet e' una pallina FERMA (a terra, o che
    rotola piano), non la pallina in gioco. TrackNet da' un solo punto per fotogramma: quando la
    pallina in gioco non si vede bene (prima del colpo, vicino al corpo) a volte indica una pallina
    ferma in campo. Il punto e' "fermo" se nella stessa zona c'e' una pallina gialla piccola anche
    0,4-0,6 s PRIMA e anche altrettanto DOPO, e il punto sta a meta' tra le due (una pallina ferma, o
    che rotola piano e dritto). La pallina in gioco in quegli istanti e' altrove; se passa vicino a
    una pallina ferma, il punto non sta a meta' tra le due posizioni della pallina ferma.
    Zona: FERMA_RAGGIO_REL + FERMA_DERIVA_REL * secondi, in altezze del giocatore.
    a_terra: funzione pixel -> True se, portato a terra, cade in campo o attorno al campo; gli altri
    punti (sopra la recinzione: alberi, cespugli secchi pieni di giallo) non si guardano.
    """
    fs = [f for f in sorted(tracknet) if primo <= f <= ultimo and (a_terra is None or a_terra(tracknet[f]))]
    if not fs:
        return set()
    passi = sorted({max(1, int(round(s * fps))) for s in FERMA_DT_S})
    richieste = {}
    for f in fs:
        h = altezze.get(f) or altezze.get(f - 1) or 300.0
        x, y = tracknet[f]
        for d in passi:
            raggio = h * (FERMA_RAGGIO_REL + FERMA_DERIVA_REL * d / fps)
            for lato in (-1, 1):
                if f + lato * d >= 1:
                    richieste.setdefault(f + lato * d, []).append((f, d, lato, x, y, raggio))
    macchie = {}                                 # (f, d, lato) -> macchie gialle trovate nella zona
    cap = cv2.VideoCapture(video)
    scala = (cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080) / 1080
    g0, g1 = min(richieste), max(richieste)
    cap.set(cv2.CAP_PROP_POS_FRAMES, g0 - 1)
    for g in range(g0, g1 + 1):
        ok, fr = cap.read()
        if not ok:
            break
        for f, d, lato, x, y, raggio in richieste.get(g, []):
            macchie[(f, d, lato)] = macchie_gialle(fr, x, y, raggio, scala)
    cap.release()
    fermi = set()
    for f in fs:
        h = altezze.get(f) or altezze.get(f - 1) or 300.0
        p = np.array(tracknet[f], float)
        for d in passi:
            for a in macchie.get((f, d, -1), []):
                if any(np.hypot(*((np.array(a) + np.array(b)) / 2 - p)) <= FERMA_RAGGIO_REL * h
                       for b in macchie.get((f, d, 1), [])):
                    fermi.add(f)
                    break
            if f in fermi:
                break
    return fermi


def segui(video, primo, ultimo, tracknet, altezze, seme=None, esteso=False):
    """
    Traccia della pallina nei frame primo..ultimo (numerati da 1 come nel tracking CSV).

    tracknet: {frame: (x, y)} posizioni viste da TrackNet
    altezze:  {frame: altezza del giocatore in pixel}
    seme:     (frame, x, y) da cui partire; di default la prima posizione TrackNet
    esteso:   ricerca estesa (pallina mossa + riaggancio a TrackNet), solo per la direzione
    Restituisce {frame: (x, y, fonte)} con fonte "locale" o "tracknet".
    """
    fermo = giallo_fermo(video, primo, ultimo)
    if seme is None:
        dentro = [f for f in sorted(tracknet) if primo <= f <= ultimo]
        if not dentro:
            return {}
        # si parte dal primo punto di TrackNet confermato da un altro punto vicino (entro 2 frame e
        # 0,3 altezze del giocatore): un punto isolato e' spesso un falso rilevamento
        def confermato(f):
            h = altezze.get(f) or altezze.get(f - 1) or 300.0
            return any(g in tracknet and np.hypot(tracknet[g][0] - tracknet[f][0], tracknet[g][1] - tracknet[f][1]) <= 0.3 * h
                       for g in (f - 2, f - 1, f + 1, f + 2))
        f0 = next((f for f in dentro if confermato(f)), dentro[0])
        seme = (f0, *tracknet[f0])
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
        if esteso and buco > 0 and f in tracknet:
            # pallina persa (di solito proprio al colpo): TrackNet vicino all'ultima posizione
            x, y = tracknet[f]
            if np.hypot(x - xa, y - ya) <= RIAGGANCIO_REL * h * (f - fa):
                scelto = (x, y, "tracknet")
        c = candidati(fr, px, py, h, fermo, esteso) if scelto is None else []
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
