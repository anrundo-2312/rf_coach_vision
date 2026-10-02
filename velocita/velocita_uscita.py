"""
velocita_uscita.py - per ogni colpo del giocatore inquadrato (quello vicino
alla camera): velocita' di USCITA della pallina dalla racchetta in km/h e
direzione del colpo (lungo linea / incrociato / centrale).

    python velocita/velocita_uscita.py --video inputs/<video>.mp4

Legge dalla cartella outputs/dati il <video>_tracking.csv (analyze.py) e il
<video>_colpi.csv (classifica_tracking.py), e la calibrazione del campo
velocita/calibrazioni/<video>.json (calibra_campo.py); se il video non ce
l'ha, usa quella standard, velocita/calibrazioni/standard.json (telefono messo
come con SwingVision, vedi LEGGIMI.md). Scrive outputs/dati/<video>_velocita.csv,
un colpo per riga, e outputs/dati/<video>_campo.jpg: il campo della
calibrazione usata disegnato sul primo fotogramma, per controllare a colpo
d'occhio che la camera fosse messa bene.

Passi:

1. FINESTRE DEI COLPI, dalla posa. Il classificatore segna frame per frame
   dritto / rovescio / servizio / attesa. I tratti non-attesa vicini (buchi di
   al massimo 5 frame) formano la finestra di un colpo.

2. PALLINA NELLA FINESTRA (palla_locale.py): TrackNet dove c'e', il
   rilevatore di colore attorno al giocatore dove TrackNet la perde. Il
   giallo fermo dello sfondo (borse, cartelli) non viene preso per la pallina.

3. CONTATTO. Cambio brusco del vettore spostamento della pallina (3 frame
   prima contro 3 frame dopo), con la pallina vicina a un polso e che DOPO si
   muove abbastanza veloce nell'immagine. L'ultima condizione scarta il
   rimbalzo della pallina dell'avversario davanti al giocatore, che
   nell'immagine sembra un colpo ma dopo la pallina continua ad arrivare
   lentamente.

4. VELOCITA' E DIREZIONE (rf_ball_exit_speed.exit_speed): traiettoria 3D dei
   ~1/3 di secondo dopo il contatto, con il contatto tenuto entro 1 m dal
   giocatore e la pallina diretta verso il campo avversario. Dalla velocita'
   3D si ricavano i km/h e l'angolo rispetto alle righe laterali. Se il video
   e' una conversione con fotogrammi ripetuti (es. 50 -> 60 fps), si usano
   gli istanti veri dei fotogrammi (fotogrammi.py); altrimenti niente cambia.

5. LUNGO LINEA / INCROCIATO / CENTRALE, da dove parte il colpo e da dove
   arriverebbe la pallina nel campo avversario (vedi classifica_direzione).
   La partenza e' il punto di contatto (vedi punto_di_partenza; colonna
   partenza_da), non piu' i piedi. Le colonne soglia_sx_gradi e
   soglia_dx_gradi dicono la stessa regola in gradi (vedi soglie_angolo).
   Per il servizio invece AL T / AL CORPO / ESTERNO, da dove cade il rimbalzo
   previsto nel riquadro del servizio (vedi classifica_servizio).

6. CONTROLLO DEL RISULTATO. Il calcolo non cambia, si decide solo se
   mostrarlo: se la traiettoria 3D non spiega i punti della pallina (errore
   sopra 6 px, riportato a 1080p) oppure il risultato non e' da tennis
   (velocita' fuori da 30-250 km/h, oppure un colpo da fondo con angolo oltre
   45 gradi), velocita' e direzione non si scrivono e la nota dice il perche'.
   Succede quando i punti non sono la pallina colpita (un'altra pallina, la
   racchetta gialla, un oggetto): vedi controlla_risultato.

Se in una finestra la posa indica un colpo ma il contatto non si trova (per
esempio la pallina passa dietro il corpo del giocatore), il colpo viene
scritto lo stesso, senza velocita', con una nota.

7. SOLO DIREZIONE. Se in una finestra non esce nessuna velocita', si rifa' la
   ricerca della pallina in modo ESTESO (palla_locale.py: pallina mossa dal
   colpo e riaggancio a TrackNet; nel servizio si parte dal lancio). Se la
   traiettoria spiega bene i punti se ne tiene solo la direzione: con la
   pallina mossa al colpo la velocita' esce troppo bassa (vedi solo_direzione).

Dopo questo file si eseguono direzione_nascosta.py (direzione dei colpi con il
contatto coperto) e velocita_rimbalzo.py (velocita' stimata dal rimbalzo per i
colpi ancora senza km/h).
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter

import cv2
import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
from rf_ball_exit_speed import exit_speed, ground_crossing, ground_from_pixel  # noqa: E402
from calibra_campo import camera_da_json, carica_per_video, disegna_controllo, leggi_fotogramma  # noqa: E402
import palla_locale  # noqa: E402
import fotogrammi  # noqa: E402

CENTRO_X = 5.485            # riga centrale del campo (m)

# Finestre dei colpi
BUCO_TRATTI = 5             # frame di "attesa" tollerati dentro un colpo
DURATA_MINIMA = 8           # frame non-attesa minimi per considerarlo un colpo
MARGINE_FINESTRA = 10       # frame aggiunti prima e dopo il tratto

# Contatto
PASSI = 3                   # frame prima/dopo per la direzione della pallina
SOGLIA_CAMBIO = 2.5         # cambio di velocita' minimo, altezze del giocatore al secondo
SOGLIA_DOPO = 2.4           # velocita' minima DOPO il contatto (scarta i rimbalzi)
DIST_POLSO = 0.6            # pallina entro 0,6 altezze da un polso
DISTANZA_MINIMA = 20        # due contatti piu' vicini sono lo stesso colpo

# Velocita'
DURATA_DOPO_S = 1 / 3       # traiettoria usata dopo il contatto (20 frame a 60 fps)
TOLLERANZA_PROFONDITA = 1.0 # contatto entro 1 m dalla distanza del giocatore

# Direzione
Y_ARRIVO = 21.0             # dove "arriva" la pallina: tra riga del servizio e fondo lontani (m)
# "Centro" = terzo centrale del campo singolo (8,23 m diviso in tre fasce da 2,74 m): entro 1,37 m
# dalla riga centrale, per la partenza e per l'arrivo, come le fasce del servizio. Piu' largo non
# conviene: con 2 m, sui video di prova, dritti e rovesci tirati dall'angolo diventano "dal centro".
FASCIA_CENTRO = (CENTRO_X - 1.37) / 3
# Lato di partenza (dritti e rovesci): dal punto di contatto, non dai piedi. In ordine:
#   1. "contatto": il punto di contatto del calcolo (impact_xyz_m), se il contatto e' stato visto;
#   2. "traiettoria": i punti della pallina nel primo 1/6 di secondo dopo il contatto (10 frame a 60 fps,
#      istanti veri nei video convertiti), prolungati all'indietro fino all'istante del contatto e portati
#      alla profondita' del giocatore (almeno 3 punti);
#   3. "piedi": come prima, se non c'e' altro.
# Il servizio resta sui piedi: li' il lato decide il riquadro, cioe' dove sta chi serve.
PARTENZA_S = 1 / 6
PARTENZA_PUNTI_MIN = 3
PARTENZA_DISTANZA_MAX = 2.5  # m: un punto di partenza piu' lontano dai piedi non e' credibile
# Servizio: il riquadro (dalla riga centrale a quella del singolo, 4,115 m) diviso in
# tre fasce uguali: al T (vicino alla riga centrale), al corpo, esterno.
TERZO_RIQUADRO = (CENTRO_X - 1.37) / 3
MARGINE_CONFINE = 0.25      # entro 0,25 m dal confine tra due fasce si dice anche verso quale

# Dentro/fuori e profondita' del rimbalzo trovato (si usano in velocita_rimbalzo.py)
SINGOLO_X = (1.37, 9.60)    # righe laterali del singolo
RETE_Y, SERVIZIO_Y, FONDO_Y = 11.885, 18.285, 23.77   # rete, riga del servizio e fondo avversari
RAGGIO_PALLINA = 0.033      # la pallina che tocca la riga e' dentro
# profondita' dei dritti e rovesci dentro: quattro fasce (utente, 2 ottobre), dalla riga di fondo verso la rete:
# profonda 1,5 m, media fino alla riga del servizio, corta fino a 3 m dalla rete, palla corta (smorzata) gli
# ultimi 3 m. L'utente le aveva date come 1,5 + 3,5 + 3 + 3 m (= 11 m); la meta' campo e' 11,885 m, quindi le due
# fasce in mezzo sono adattate alle righe vere: la media finisce sulla riga del servizio (3,985 m invece di
# 3,5) e la corta va dalla riga del servizio a 3 m dalla rete (3,40 m invece di 3).
PROFONDA_M = 1.5            # "profonda": negli ultimi 1,5 m prima della riga di fondo
PALLA_CORTA_M = 3.0         # "palla corta" (smorzata): entro 3 m dalla rete

# Controllo del risultato (passo 6): solo cosa si mostra, il calcolo resta identico
ERRORE_MAX_1080 = 6.0       # px (riportati a 1080p): oltre, la traiettoria non spiega i punti
# dritto inside-out / inside-in (2 ottobre, soglia decisa dall'utente)
INSIDE_M = 1.0              # piedi almeno 1 m oltre la riga centrale, dalla parte del rovescio
                            # arrivo: nel terzo laterale del campo avversario (FASCIA_CENTRO, regola dell'utente)
SEPARAZIONE_MANO = 0.3      # per capire la mano: contatto ad almeno 0,3 m di lato dai piedi
VELOCITA_PLAUSIBILE = (30, 250)  # km/h
ANGOLO_MAX = 45.0           # gradi rispetto alle righe laterali, colpi da fondo (non il servizio)


# ------------------------------------------------------------------ lettura
def leggi_tracking(percorso):
    righe = list(csv.DictReader(open(percorso, newline="")))

    def num(r, c):
        try:
            return float(r[c])
        except (ValueError, KeyError, TypeError):
            return np.nan

    t = {"frame": np.array([int(r["frame"]) for r in righe])}
    t["tempo"] = np.array([num(r, "tempo_s") for r in righe])
    t["vista"] = np.array([r.get("pallina_fonte") == "tracknet" for r in righe])
    t["palla"] = np.array([[num(r, "pallina_x"), num(r, "pallina_y")] for r in righe])
    t["box"] = np.array([[num(r, c) for c in ("giocatore_x1", "giocatore_y1", "giocatore_x2", "giocatore_y2")] for r in righe])
    t["caviglie"] = np.array([[num(r, "caviglia_sx_x"), num(r, "caviglia_sx_y"), num(r, "caviglia_dx_x"), num(r, "caviglia_dx_y")] for r in righe])
    t["polsi"] = np.array([[num(r, "polso_sx_x"), num(r, "polso_sx_y"), num(r, "polso_dx_x"), num(r, "polso_dx_y")] for r in righe])
    t["fps"] = 1 / np.nanmedian(np.diff(t["tempo"]))
    return t


def leggi_colpi(percorso):
    return {int(r["frame"]): r["classe"] for r in csv.DictReader(open(percorso, newline=""))}


# ------------------------------------------------------------------ passo 1
def finestre_colpi(classi, n_frame):
    """Tratti di frame non-attesa, uniti se separati da pochi frame."""
    finestre, inizio, ultimo = [], None, None
    for f in range(1, n_frame + 1):
        c = classi.get(f)
        if c and c != "attesa":
            if inizio is None:
                inizio = f
            elif f - ultimo > BUCO_TRATTI + 1:
                finestre.append((inizio, ultimo))
                inizio = f
            ultimo = f
    if inizio is not None:
        finestre.append((inizio, ultimo))
    return [(a, b) for a, b in finestre
            if sum(1 for f in range(a, b + 1) if classi.get(f) not in (None, "attesa")) >= DURATA_MINIMA]


# ------------------------------------------------------------------ passo 3
def trova_contatti(traccia, t):
    """Frame (l'ultimo PRIMA del contatto) dei colpi del giocatore nella traccia."""
    fs = sorted(traccia)
    pos = {f: np.array(traccia[f][:2]) for f in fs}
    candidati = []
    for f in fs:
        prima = [g for g in fs if f - PASSI - 1 <= g < f][:1]           # punto ~3 frame prima
        dopo = [g for g in fs if f < g <= f + PASSI + 1][-1:]          # punto ~3 frame dopo
        if not prima or not dopo or f - prima[0] < PASSI - 1 or dopo[0] - f < PASSI - 1:
            continue
        i = f - 1
        x1, y1, x2, y2 = t["box"][i]
        h = y2 - y1
        if not np.isfinite(h) or h <= 0:
            continue
        v_prima = (pos[f] - pos[prima[0]]) / (f - prima[0])
        v_dopo = (pos[dopo[0]] - pos[f]) / (dopo[0] - f)
        cambio = np.linalg.norm(v_dopo - v_prima) / h * t["fps"]
        veloce_dopo = np.linalg.norm(v_dopo) / h * t["fps"]
        pol = t["polsi"][i].reshape(2, 2)
        pol = pol[np.all(np.isfinite(pol), axis=1)]
        vicina = len(pol) > 0 and np.min(np.linalg.norm(pol - pos[f], axis=1)) <= DIST_POLSO * h
        if vicina and cambio >= SOGLIA_CAMBIO and veloce_dopo >= SOGLIA_DOPO:
            candidati.append((f, cambio))
    scelti = []
    for f, c in sorted(candidati, key=lambda x: -x[1]):
        if all(abs(f - g) >= DISTANZA_MINIMA for g, _ in scelti):
            scelti.append((f, c))
    return sorted(f for f, _ in scelti)


# ------------------------------------------------------------------ passo 4
def piedi_a_terra(t, f_contatto, cam):
    """Posizione a terra del giocatore prima del colpo: il frame con i piedi piu' in basso
    nell'immagine (nel servizio il giocatore salta, al contatto i piedi sono in aria)."""
    migliore = None
    for f in range(max(1, f_contatto - 20), f_contatto + 1):
        ax, ay, bx, by = t["caviglie"][f - 1]
        if np.all(np.isfinite([ax, ay, bx, by])):
            if migliore is None or max(ay, by) > migliore[1]:
                migliore = (((ax + bx) / 2), max(ay, by))
    if migliore is None:
        x1, _, x2, y2 = t["box"][f_contatto - 1]
        migliore = ((x1 + x2) / 2, y2)
    return ground_from_pixel(migliore, cam)[:2]


def pixel_a_profondita(px, cam, y):
    """Il punto della linea di vista del pixel px che sta alla profondita' y (m dal fondo del giocatore)."""
    R, _ = cv2.Rodrigues(cam["rvec"])
    C = -R.T @ cam["tvec"].ravel()
    ray = R.T @ np.linalg.inv(cam["K"]) @ np.array([px[0], px[1], 1.0])
    if abs(ray[1]) < 1e-9:
        return None
    s = (y - C[1]) / ray[1]
    return None if s <= 0 else C + s * ray


def partenza_da_traiettoria(t, punti, t_contatto, piedi, cam):
    """
    x di partenza dai punti della pallina nel primo 1/6 di secondo dopo il contatto (punti: frame -> pixel):
    retta nel tempo per x e per y dell'immagine, riportata all'istante del contatto, e quel pixel portato
    alla profondita' del giocatore. None se i punti sono meno di 3 o il risultato non e' credibile.
    """
    rip = None if t.get("tempi") is None else t["tempi"]["dup"]
    fs = [f for f in sorted(punti) if t_contatto < istante(t, f) <= t_contatto + PARTENZA_S + 1e-6
          and not (rip is not None and rip[int(f)])]
    if len(fs) < PARTENZA_PUNTI_MIN:
        return None
    ts = np.array([istante(t, f) for f in fs])
    px = [np.polyval(np.polyfit(ts, [punti[f][d] for f in fs], 1), t_contatto) for d in (0, 1)]
    p = pixel_a_profondita(px, cam, float(piedi[1]))
    if p is None or abs(p[0] - piedi[0]) > PARTENZA_DISTANZA_MAX:
        return None
    return float(p[0])


def punto_di_partenza(t, cam, piedi, contatto=None, punti=None, t_contatto=None):
    """(x di partenza, partenza_da): contatto del calcolo, poi traiettoria dopo il contatto, poi piedi."""
    if contatto is not None:
        return float(contatto[0]), "contatto"
    if punti and t_contatto is not None:
        x = partenza_da_traiettoria(t, punti, t_contatto, piedi, cam)
        if x is not None:
            return x, "traiettoria"
    return float(piedi[0]), "piedi"


def classifica_direzione(x_giocatore, contatto, v0):
    """Lungo linea / incrociato / centrale da dove parte il colpo (x_giocatore: x di partenza,
    vedi punto_di_partenza) e dove arriva la pallina."""
    angolo = float(np.degrees(np.arctan2(v0[0], v0[1])))       # 0 = parallela alle righe laterali
    x_arrivo = contatto[0] + np.tan(np.radians(angolo)) * (Y_ARRIVO - contatto[1])
    lato_partenza = 0 if abs(x_giocatore - CENTRO_X) <= FASCIA_CENTRO else np.sign(x_giocatore - CENTRO_X)
    lato_arrivo = 0 if abs(x_arrivo - CENTRO_X) <= FASCIA_CENTRO else np.sign(x_arrivo - CENTRO_X)
    if lato_arrivo == 0:
        classe = "centrale"
    elif lato_partenza == 0:
        classe = "dal centro verso " + ("destra" if lato_arrivo > 0 else "sinistra")
    elif lato_partenza == lato_arrivo:
        classe = "lungo linea"
    else:
        classe = "incrociato"
    return angolo, float(x_arrivo), classe


def soglie_angolo(contatto):
    """
    Gli angoli (gradi) che separano le classi per un colpo che parte da contatto (x, y in m): le
    direzioni dal contatto ai due confini del centro, a Y_ARRIVO. La pallina arriva al centro se
    l'angolo e' tra soglia_sx e soglia_dx, a sinistra se e' sotto soglia_sx, a destra se e' sopra
    soglia_dx. E' la stessa regola di classifica_direzione, scritta in gradi.
    """
    dy = Y_ARRIVO - contatto[1]
    return (float(np.degrees(np.arctan2(CENTRO_X - FASCIA_CENTRO - contatto[0], dy))),
            float(np.degrees(np.arctan2(CENTRO_X + FASCIA_CENTRO - contatto[0], dy))))


def aggiungi_soglie(colpi):
    """Colonne soglia_sx_gradi e soglia_dx_gradi per dritti e rovesci con una direzione (dal contatto della riga)."""
    for c in colpi:
        c.pop("soglia_sx_gradi", None), c.pop("soglia_dx_gradi", None)
        if c.get("direzione") and c.get("colpo") != "servizio" and c.get("contatto_x_m", "") != "":
            sx, dx = soglie_angolo((float(c["contatto_x_m"]), float(c["contatto_y_m"])))
            c.update({"soglia_sx_gradi": round(sx, 1), "soglia_dx_gradi": round(dx, 1)})
    return colpi


def dentro_fuori(colpo, x, y, x_giocatore):
    """
    Dentro o fuori un rimbalzo in (x, y) m. Dritti e rovesci: campo singolo avversario. Servizio: il
    riquadro in diagonale (chi serve da destra tira nel riquadro di sinistra). Si decide sempre, anche a
    pochi centimetri dalla riga; la riga conta dentro.
    Restituisce (esito, distanza_m, riga, profondita): distanza_m e' quanto il rimbalzo sta dentro
    (positiva) o fuori (negativa) rispetto alla riga piu' vicina o piu' superata; profondita' (solo dritti
    e rovesci dentro), dalla riga di fondo verso la rete: profonda (ultimi PROFONDA_M), media (fino alla riga
    del servizio), corta (dalla riga del servizio a PALLA_CORTA_M dalla rete), palla corta (entro PALLA_CORTA_M).
    """
    if colpo == "servizio":
        if x_giocatore >= CENTRO_X:
            righe = {"laterale": x - SINGOLO_X[0], "centrale": CENTRO_X - x}
        else:
            righe = {"centrale": x - CENTRO_X, "laterale": SINGOLO_X[1] - x}
        righe.update({"servizio": SERVIZIO_Y - y, "rete": y - RETE_Y})
    else:
        righe = {"laterale sinistra": x - SINGOLO_X[0], "laterale destra": SINGOLO_X[1] - x,
                 "fondo": FONDO_Y - y, "rete": y - RETE_Y}
    riga, distanza = min(righe.items(), key=lambda kv: kv[1])     # dentro: la piu' vicina; fuori: la piu' superata
    esito = "dentro" if distanza >= -RAGGIO_PALLINA else "fuori"
    profondita = ""
    if colpo != "servizio" and esito == "dentro":
        profondita = ("palla corta" if y - RETE_Y < PALLA_CORTA_M else "corta" if y < SERVIZIO_Y
                      else "profonda" if FONDO_Y - y < PROFONDA_M else "media")
    return esito, float(distanza), riga, profondita


def aggiungi_dentro_fuori(colpi):
    """Colonne dentro_fuori, distanza_riga_m, riga_vicina, profondita per i colpi con un rimbalzo trovato."""
    for c in colpi:
        for k in ("dentro_fuori", "distanza_riga_m", "riga_vicina", "profondita"):
            c.pop(k, None)
        if c.get("rimbalzo_trovato_x_m", "") in (None, "") or c.get("giocatore_x_m", "") in (None, ""):
            continue
        esito, d, riga, prof = dentro_fuori(c.get("colpo"), float(c["rimbalzo_trovato_x_m"]),
                                            float(c["rimbalzo_trovato_y_m"]), float(c["giocatore_x_m"]))
        c.update({"dentro_fuori": esito, "distanza_riga_m": round(d, 2), "riga_vicina": riga, "profondita": prof})
    return colpi


def mano_dai_colpi(colpi):
    """
    "destra" o "sinistra" dai dritti e rovesci con il contatto visto (partenza_da = "contatto"): nel dritto
    la racchetta colpisce dalla parte della mano (destro: contatto a destra dei piedi), nel rovescio
    dall'altra. Vince la maggioranza; senza voti "destra". Ritorna (mano, voti a favore, voti totali).
    """
    si = n = 0
    for c in colpi:
        if c.get("partenza_da") != "contatto" or c.get("colpo") not in ("dritto", "rovescio"):
            continue
        try:
            d = float(c["contatto_x_m"]) - float(c["giocatore_x_m"])
        except (KeyError, TypeError, ValueError):
            continue
        if abs(d) < SEPARAZIONE_MANO:
            continue
        n += 1
        si += (d > 0) == (c["colpo"] == "dritto")
    if n == 0:
        return "destra", 0, 0
    return ("destra" if si >= n - si else "sinistra"), max(si, n - si), n


def tipo_dritto(c, mano):
    """
    Dritto inside-out / inside-in: colpito con i PIEDI dalla parte del rovescio, almeno INSIDE_M oltre la
    riga centrale (destro: a sinistra). Poi conta dove finisce la pallina, nei tre terzi del singolo
    avversario (gli stessi della direzione, FASCIA_CENTRO; regola dell'utente, 2 ottobre): per un destro
    inside-in se finisce nel terzo di SINISTRA (lungo linea, verso il dritto dell'avversario), inside-out
    se finisce nel terzo di DESTRA (in diagonale, verso il suo rovescio); per un mancino al contrario.
    Se finisce nel terzo centrale non e' ne' l'uno ne' l'altro (""). Dove finisce: il rimbalzo trovato
    se c'e', se no l'arrivo a 21 m. "" anche per gli altri colpi.
    """
    if c.get("colpo") != "dritto" or not c.get("direzione") or c.get("giocatore_x_m", "") in (None, ""):
        return ""
    verso = -1 if mano == "destra" else 1                   # lato del rovescio: x piu' piccole per un destro
    if (float(c["giocatore_x_m"]) - CENTRO_X) * verso < INSIDE_M:
        return ""
    x = c.get("rimbalzo_trovato_x_m", "")
    x = float(x) if x not in (None, "") else float(c["arrivo_x_m"])
    a = (x - CENTRO_X) * verso                              # > 0: dalla parte del rovescio del giocatore
    return "inside-in" if a > FASCIA_CENTRO else "inside-out" if a < -FASCIA_CENTRO else ""


def aggiungi_inside(colpi, mano="auto"):
    """Colonna dritto_tipo (inside-out, inside-in o vuota). mano: "auto", "destra" o "sinistra"."""
    if mano == "auto":
        mano = mano_dai_colpi(colpi)[0]
    for c in colpi:
        c["dritto_tipo"] = tipo_dritto(c, mano)
    return mano


def classifica_servizio(x_giocatore, rimbalzo):
    """
    Al T / al corpo / esterno, da dove cade il rimbalzo previsto. Il servizio va
    in diagonale: da destra nel riquadro di sinistra e viceversa, quindi si misura
    la distanza del rimbalzo dalla riga centrale verso l'esterno di quel riquadro.
    Conta solo la posizione laterale: e' precisa (simulazioni: +-0,1-0,5 m), la
    profondita' del rimbalzo no (+-2-3 m), quindi non diciamo se e' lungo.
    """
    verso_esterno = -1 if x_giocatore >= CENTRO_X else 1
    dal_centro = (rimbalzo[0] - CENTRO_X) * verso_esterno
    fascia = 0 if dal_centro < TERZO_RIQUADRO else 1 if dal_centro < 2 * TERZO_RIQUADRO else 2
    nomi, verso = ["al T", "al corpo", "esterno"], ["verso il T", "verso il corpo", "verso l'esterno"]
    # vicino al confine con la fascia accanto: la precisione e' di qualche decimetro
    for confine, vicina in ((fascia * TERZO_RIQUADRO, fascia - 1), ((fascia + 1) * TERZO_RIQUADRO, fascia + 1)):
        if 0 <= vicina <= 2 and abs(dal_centro - confine) < MARGINE_CONFINE:
            return f"{nomi[fascia]}, {verso[vicina]}"
    return nomi[fascia]


def tempi_fit(t, fs):
    """
    (frame, fps, tieni) da dare al calcolo per i frame fs. Di norma sono gli stessi frame e gli
    stessi fps. Se il video e' una conversione con fotogrammi ripetuti (fotogrammi.py), i ripetuti
    si tolgono (tieni = falso) e agli altri si da' il numero del fotogramma vero, con gli fps veri.
    """
    fs = np.asarray(fs, int)
    tr = t.get("tempi")
    if tr is None:
        return fs, t["fps"], np.ones(len(fs), bool)
    tieni = ~tr["dup"][fs]
    return tr["k"][fs[tieni]], tr["fps"], tieni


def istante(t, f):
    """Istante (s) del frame f, vero anche nei video con fotogrammi ripetuti."""
    tr = t.get("tempi")
    return f / t["fps"] if tr is None else tr["k"][int(f)] / tr["fps"]


def misura(t, traccia, f_contatto, cam):
    fps = t["fps"]
    n_dopo = max(4, int(round(DURATA_DOPO_S * fps)))
    fs = [f for f in sorted(traccia) if f_contatto - 8 <= f <= f_contatto + n_dopo]
    f_arr = np.array(fs)
    p_arr = np.array([traccia[f][:2] for f in fs], float)
    ci = int(np.flatnonzero(f_arr > f_contatto)[0])
    piedi = piedi_a_terra(t, f_contatto, cam)
    # istanti veri se il video ha fotogrammi ripetuti (altrimenti tutto come prima)
    f_fit, fps_fit, tieni = tempi_fit(t, f_arr)
    n_fit = n_dopo if fps_fit == fps else int(round(n_dopo * fps_fit / fps))
    r = exit_speed(p_arr[tieni], f_fit, fps_fit, cam, int(tieni[:ci].sum()), impact_mode="visual", n_frames=n_fit,
                   player_ground_xy=piedi, return_debug=True, forward=True,
                   depth_tol=TOLLERANZA_PROFONDITA)
    r["_partenza"] = punto_di_partenza(t, cam, piedi, contatto=r["impact_xyz_m"])
    angolo, x_arrivo, direzione = classifica_direzione(r["_partenza"][0], r["impact_xyz_m"], r["v0_ms"])
    # rimbalzo previsto (gravita' + aria, senza rotazione): usato solo per il servizio
    _, rimbalzo = ground_crossing(r["impact_xyz_m"], r["v0_ms"])
    usati = [f for f in fs if f_contatto < f <= f_contatto + n_dopo]
    return r, piedi, angolo, x_arrivo, direzione, rimbalzo, usati


def pallina_vicina(traccia, t):
    """Quanti punti della traccia hanno la pallina vicina a un polso del giocatore."""
    n = 0
    for f, (x, y, _) in traccia.items():
        x1, y1, x2, y2 = t["box"][f - 1]
        pol = t["polsi"][f - 1].reshape(2, 2)
        pol = pol[np.all(np.isfinite(pol), axis=1)]
        if len(pol) and np.isfinite(y2 - y1) and np.min(np.linalg.norm(pol - (x, y), axis=1)) <= DIST_POLSO * (y2 - y1):
            n += 1
    return n


def fine_tratto_piu_lungo(classi, a, b, colpo):
    migliore, inizio = (0, b), None
    for f in range(a, b + 2):
        if classi.get(f) == colpo:
            inizio = f if inizio is None else inizio
        elif inizio is not None:
            if f - inizio > migliore[0]:
                migliore = (f - inizio, f - 1)
            inizio = None
    return migliore[1]


# ------------------------------------------------------------------ principale
def controlla_risultato(r, angolo, colpo, altezza_img):
    """
    Motivi per non mostrare velocita' e direzione (lista vuota: risultato da mostrare).
    Sui colpi buoni l'errore della traiettoria e' 1-3 px a 1080p; quando i punti non sono
    la pallina colpita il fit li spiega male (15-35 px) e da' velocita' o angoli assurdi.
    """
    motivi = []
    errore = r["rms_px"] * 1080 / altezza_img
    if errore > ERRORE_MAX_1080:
        motivi.append(f"la traiettoria non spiega i punti (errore {errore:.1f} px a 1080p, massimo {ERRORE_MAX_1080:.0f})")
    lo, hi = VELOCITA_PLAUSIBILE
    if not lo <= r["exit_kmh"] <= hi:
        motivi.append(f"velocita' {r['exit_kmh']:.0f} km/h fuori da {lo}-{hi}")
    if colpo != "servizio" and abs(angolo) > ANGOLO_MAX:
        motivi.append(f"angolo {angolo:+.1f} gradi oltre {ANGOLO_MAX:.0f}")
    return motivi


def analizza(video, cartella_dati="outputs/dati", calibrazione=None, verbose=True):
    nome = os.path.splitext(os.path.basename(video))[0]
    t = leggi_tracking(os.path.join(cartella_dati, nome + "_tracking.csv"))
    t["tempi"] = fotogrammi.tempi_reali(video, cartella_dati, t["fps"], verbose)
    classi = leggi_colpi(os.path.join(cartella_dati, nome + "_colpi.csv"))
    cal, fonte = carica_per_video(video, calibrazione)
    cam = camera_da_json(cal)
    # controllo: il campo della calibrazione usata sopra il primo fotogramma
    frame, _, _ = leggi_fotogramma(video, 0)
    altezza_img = frame.shape[0]
    if fonte == "standard":
        testo = "calibrazione STANDARD: le righe verdi devono cadere su quelle vere"
    else:
        testo = f"calibrazione del video (errore medio {cal['errore_rms_px']:.1f} px)"
    controllo = os.path.join(cartella_dati, nome + "_campo.jpg")
    cv2.imwrite(controllo, disegna_controllo(frame, cal, {}, testo))
    if verbose:
        print(f"Calibrazione: {'standard' if fonte == 'standard' else 'del video'}. Controllo: {controllo}")

    n = len(t["frame"])
    tracknet = {int(f): tuple(p) for f, p, v in zip(t["frame"], t["palla"], t["vista"]) if v}
    altezze = {int(f): float(b[3] - b[1]) for f, b in zip(t["frame"], t["box"]) if np.isfinite(b[3] - b[1])}

    colpi = []
    for a, b in finestre_colpi(classi, n):
        primo, ultimo = max(1, a - MARGINE_FINESTRA), min(n, b + MARGINE_FINESTRA)
        inizio_righe = len(colpi)
        traccia = palla_locale.segui(video, primo, ultimo, tracknet, altezze)
        contatti = trova_contatti(traccia, t) if traccia else []
        if verbose:
            print(f"finestra {a}-{b}: pallina in {len(traccia)} frame "
                  f"({sum(1 for v in traccia.values() if v[2] == 'locale')} dal rilevatore locale), contatti {contatti}")
        for fc in contatti:
            voti = [classi[f] for f in range(fc - 15, fc + 1) if classi.get(f) not in (None, "attesa")]
            colpo = Counter(voti).most_common(1)[0][0] if voti else ""
            riga = {"frame": fc, "tempo_s": round(float(t["tempo"][fc - 1]), 3), "colpo": colpo,
                    "calibrazione": fonte}
            try:
                r, piedi, angolo, x_arr, direzione, rimbalzo, usati = misura(t, traccia, fc, cam)
                motivi = controlla_risultato(r, angolo, colpo, altezza_img)
                if motivi:
                    # calcolo fatto ma non credibile: niente velocita' ne' direzione
                    riga.update({"punti_usati": r["n_points"], "errore_px": round(r["rms_px"], 1),
                                 "nota": "misura scartata: " + "; ".join(motivi)})
                    colpi.append(riga)
                    continue
                partenza = r["_partenza"]
                if colpo == "servizio":
                    direzione = classifica_servizio(float(piedi[0]), rimbalzo)
                    partenza = (float(piedi[0]), "piedi")
                    riga.update({"rimbalzo_x_m": round(float(rimbalzo[0]), 2),
                                 "rimbalzo_y_m": round(float(rimbalzo[1]), 2)})
                riga.update({"partenza_da": partenza[1], "_partenza_x_m": round(partenza[0], 2)})
                riga.update({
                    "velocita_uscita_kmh": round(r["exit_kmh"]),
                    "direzione": direzione,
                    "angolo_gradi": round(angolo, 1),
                    "giocatore_x_m": round(float(piedi[0]), 2), "arrivo_x_m": round(x_arr, 2),
                    "contatto_x_m": round(float(r["impact_xyz_m"][0]), 2),
                    "contatto_y_m": round(float(r["impact_xyz_m"][1]), 2),
                    "contatto_z_m": round(float(r["impact_xyz_m"][2]), 2),
                    "punti_usati": r["n_points"], "errore_px": round(r["rms_px"], 1), "nota": "",
                    "_punti": [(f, *traccia[f][:2]) for f in usati]})
            except (ValueError, IndexError, np.linalg.LinAlgError) as e:
                riga.update({"nota": f"velocita' non calcolabile: {e}"})
            colpi.append(riga)
        if not contatti and pallina_vicina(traccia, t) >= 3:
            # la posa dice che c'e' un colpo e la pallina arriva al giocatore, ma attorno
            # al contatto non si vede (coperta dal corpo o persa): colpo senza velocita'.
            # Il contatto e' circa alla fine del tratto piu' lungo della classe prevalente.
            tratti = Counter(classi.get(f) for f in range(a, b + 1) if classi.get(f) not in (None, "attesa"))
            colpo = tratti.most_common(1)[0][0]
            fine = fine_tratto_piu_lungo(classi, a, b, colpo)
            colpi.append({"frame": fine, "tempo_s": round(float(t["tempo"][fine - 1]), 3), "colpo": colpo,
                          "calibrazione": fonte, "nota": "contatto non visibile: pallina coperta o persa"})
        if not any(r.get("velocita_uscita_kmh", "") != "" for r in colpi[inizio_righe:]):
            solo_direzione(video, t, classi, a, b, primo, ultimo, tracknet, altezze, cam, fonte,
                           altezza_img, colpi, inizio_righe, verbose)
    colpi.sort(key=lambda r: r["frame"])
    return nome, colpi


def seme_lancio(t, tracknet, primo, ultimo):
    """
    Servizio: il lancio e' l'ultima serie (almeno 3 punti) di punti TrackNet sopra la testa e
    sopra il giocatore. Da li' parte la ricerca, invece che dai palleggi di inizio finestra.
    """
    serie, cur = [], []
    for f in range(primo, ultimo + 1):
        b = t["box"][f - 1]
        if f in tracknet and np.all(np.isfinite(b)):
            x, y = tracknet[f]
            if y < b[1] and abs(x - (b[0] + b[2]) / 2) < 0.6 * (b[3] - b[1]):
                if cur and f - cur[-1] > 3:
                    serie.append(cur)
                    cur = []
                cur.append(f)
    if cur:
        serie.append(cur)
    serie = [x for x in serie if len(x) >= 3]
    return (serie[-1][0], *tracknet[serie[-1][0]]) if serie else None


def solo_direzione(video, t, classi, a, b, primo, ultimo, tracknet, altezze, cam, fonte, altezza_img,
                   colpi, inizio_righe, verbose):
    """
    Finestra senza nessuna velocita' misurata: ricerca ESTESA della pallina (palla_locale:
    pallina mossa + riaggancio a TrackNet; per il servizio si parte dal lancio). Se il
    calcolo spiega bene i punti se ne tiene SOLO la direzione: con la pallina mossa al colpo
    la velocita' esce troppo bassa (alcaraz: 124 e 66 km/h, sotto la media fino al rimbalzo).
    """
    voti = Counter(classi.get(f) for f in range(a, b + 1) if classi.get(f) not in (None, "attesa"))
    seme = seme_lancio(t, tracknet, primo, ultimo) if voti and voti.most_common(1)[0][0] == "servizio" else None
    traccia = palla_locale.segui(video, primo, ultimo, tracknet, altezze, seme=seme, esteso=True)
    contatti = trova_contatti(traccia, t) if traccia else []
    righe = colpi[inizio_righe:]
    for fc in contatti:
        voti_c = [classi[f] for f in range(fc - 15, fc + 1) if classi.get(f) not in (None, "attesa")]
        colpo = Counter(voti_c).most_common(1)[0][0] if voti_c else ""
        riga = {"frame": fc, "tempo_s": round(float(t["tempo"][fc - 1]), 3), "colpo": colpo, "calibrazione": fonte}
        try:
            r, piedi, angolo, x_arr, direzione, rimbalzo, usati = misura(t, traccia, fc, cam)
        except (ValueError, IndexError, np.linalg.LinAlgError):
            if not righe:
                # la posa dice colpo e la pallina c'e': riga senza misura (per direzione_nascosta.py
                # e velocita_rimbalzo.py)
                riga["nota"] = "contatto non visibile: pallina coperta o persa"
                colpi.append(riga)
                righe = [riga]
            continue
        if controlla_risultato(r, angolo, colpo, altezza_img):
            continue
        partenza = r["_partenza"]
        if colpo == "servizio":
            direzione = classifica_servizio(float(piedi[0]), rimbalzo)
            partenza = (float(piedi[0]), "piedi")
            riga.update({"rimbalzo_x_m": round(float(rimbalzo[0]), 2), "rimbalzo_y_m": round(float(rimbalzo[1]), 2)})
        riga.update({"partenza_da": partenza[1], "_partenza_x_m": round(partenza[0], 2)})
        riga.update({
            "direzione": direzione, "angolo_gradi": round(angolo, 1),
            "giocatore_x_m": round(float(piedi[0]), 2), "arrivo_x_m": round(x_arr, 2),
            "contatto_x_m": round(float(r["impact_xyz_m"][0]), 2),
            "contatto_y_m": round(float(r["impact_xyz_m"][1]), 2),
            "contatto_z_m": round(float(r["impact_xyz_m"][2]), 2),
            "punti_usati": r["n_points"], "errore_px": round(r["rms_px"], 1),
            "nota": "pallina mossa al colpo: solo direzione (velocita' non affidabile)",
            "_punti": [(f, *traccia[f][:2]) for f in usati]})
        # sostituisce le righe senza misura dello stesso colpo trovate dalla ricerca normale
        for vecchia in [x for x in righe if abs(x["frame"] - fc) <= 15 and x.get("velocita_uscita_kmh", "") == ""]:
            colpi.remove(vecchia)
        colpi.append(riga)
        if verbose:
            print(f"  ricerca estesa: frame {fc} {colpo}, solo direzione: {direzione}")


CAMPI = ["frame", "tempo_s", "colpo", "velocita_uscita_kmh", "velocita_rimbalzo_kmh", "direzione", "dritto_tipo", "angolo_gradi",
         "soglia_sx_gradi", "soglia_dx_gradi", "giocatore_x_m", "partenza_da", "arrivo_x_m", "rimbalzo_x_m", "rimbalzo_y_m", "contatto_x_m", "contatto_y_m", "contatto_z_m",
         "punti_usati", "errore_px", "calibrazione", "nota"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--dati", default="outputs/dati")
    ap.add_argument("--calibrazione")
    a = ap.parse_args()
    nome, colpi = analizza(a.video, a.dati, a.calibrazione)
    aggiungi_soglie(colpi)
    uscita = os.path.join(a.dati, nome + "_velocita.csv")
    with open(uscita, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPI, extrasaction="ignore")
        w.writeheader()
        w.writerows(colpi)
    print()
    for c in colpi:
        if c.get("velocita_uscita_kmh", "") != "":
            dove = (f"rimbalzo ({c['rimbalzo_x_m']:.1f}; {c['rimbalzo_y_m']:.1f}) m" if "rimbalzo_x_m" in c
                    else f"arrivo x {c['arrivo_x_m']:.1f} m")
            print(f"  frame {c['frame']:4d} {c['tempo_s']:5.2f} s  {c['colpo']:9s} {c['velocita_uscita_kmh']:4d} km/h  "
                  f"{c['direzione'] or '-':24s} angolo {c['angolo_gradi']:+5.1f}  giocatore x {c['giocatore_x_m']:.1f} m -> {dove}")
        else:
            print(f"  frame {c['frame']:4d} {c['tempo_s']:5.2f} s  {c['colpo']:9s}  -   {c['nota']}")
    print(f"\nSalvato in {uscita}")
    # punti della pallina usati per ogni colpo, per disegnarli sul video
    json.dump(colpi, open(uscita.replace(".csv", "_punti.json"), "w"), default=float)


if __name__ == "__main__":
    main()
