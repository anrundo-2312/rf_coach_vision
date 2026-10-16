"""
camera.py - la calibrazione che segue la camera (16 ottobre).

La calibrazione del campo e' fatta su UN fotogramma. Se poi la camera si sposta
un po' (telefono urtato, ripresa a mano dalle tribune: sinner_final_test si
sposta di 180 px a 4K in 35 s) tutto quello che passa dalla calibrazione
sbaglia: rimbalzi che finiscono vicino alla rete, "palle corte" inesistenti,
medie fino al rimbalzo troppo basse, dentro/fuori a caso.

Qui si misura, per ogni fotogramma, di quanto l'immagine si e' spostata
rispetto al fotogramma della calibrazione: allineamento ECC
(cv2.findTransformECC, sola traslazione) della FASCIA ALTA dell'immagine
(campo lontano, rete, recinzione, tribune: cose ferme) ridotta a 480 px di
larghezza, fotogramma dopo fotogramma partendo dallo spostamento del
precedente. La fascia bassa, con il giocatore vicino che e' grande e si muove,
non si usa: con tutta l'immagine la misura saltava (provato su
sinner_final_test). Lo spostamento (dx, dy) in pixel del video si applica alla
calibrazione spostando il centro dell'immagine (camera_al_frame): per piccole
rotazioni del telefono l'immagine trasla quasi rigidamente, quindi la
calibrazione corretta e' quella originale con il centro spostato di (dx, dy).
Non vale per zoom o rotazioni grandi: per quelli c'e' la regola sotto.

Il risultato va in outputs/dati/<video>_camera.csv (frame da 1 come il
tracking, dx, dy in pixel del video, risposta della correlazione). Lo scrive
velocita_uscita.py la prima volta che serve (una lettura in piu' del video, al
ritmo della decodifica); direzione_nascosta.py e velocita_rimbalzo.py lo
leggono. Se il file manca e il video non si apre, niente correzione: tutto
come prima.

REGOLA "CAMERA MOSSA" (decisa con Andrea il 16/10; il 17/10 la soglia della
"moderata" e' passata da 60 a 100 px: con il treppiede non cambia niente, con il
telefono in mano tornano rimbalzo, dentro/fuori e media su piu' colpi).
Spostamento riportato a 1080p, rispetto al fotogramma della calibrazione:
  - fino a MOSSA_MODERATA_PX: corretto, tutto si mostra;
  - oltre MOSSA_MODERATA_PX ("moderata"): i km/h si mostrano (vengono dai
    primi 20 fotogrammi vicino al giocatore, dove l'errore residuo e'
    piccolo), ma niente rimbalzo, dentro/fuori, profondita', media, punto
    sulla mappa;
  - oltre MOSSA_ECCESSIVA_PX, o correlazione debole ("eccessiva"): nessun
    numero che dipende dalla calibrazione. Resta il colpo con il tipo e la
    nota "camera mossa".
Il livello e' nella colonna camera (ok / moderata / eccessiva) e lo spostamento
in camera_px (a 1080p). Con il telefono su treppiede e' sempre "ok".

    python velocita/camera.py --video inputs/<video>.mp4   (solo per rifare il file)
"""

import argparse
import csv
import os
import sys

import cv2
import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
from calibra_campo import carica_per_video  # noqa: E402

LARGHEZZA = 480            # l'immagine ridotta su cui si misura lo spostamento
FASCIA_ALTA = 0.55         # parte alta dell'immagine usata per l'allineamento (il giocatore vicino sta sotto)
ITERAZIONI = 30            # dell'allineamento ECC per fotogramma
MOSSA_MODERATA_PX = 100    # a 1080p: oltre, niente rimbalzo / dentro-fuori / mappa (60 fino al 16/10)
MOSSA_ECCESSIVA_PX = 150   # a 1080p: oltre, nessun numero dalla calibrazione
RISPOSTA_MIN = 0.5         # coefficiente ECC piu' basso di cosi' = allineamento inaffidabile (= eccessiva)
CORREGGI = True            # False = come prima: nessuna correzione e nessuna regola


def fotogramma_calibrazione(cal, fps):
    """Il fotogramma (da 0) su cui e' stata fatta la calibrazione: il numero salvato (clic a mano) oppure
    i secondi della calibrazione geometrica ("mediana da 5.5 s"); se non c'e', il primo."""
    f = cal.get("fotogramma", 0)
    if isinstance(f, (int, float)):
        return int(f)
    try:
        s = float(str(f).split("da")[-1].split("s")[0].strip().replace(",", "."))
        return int(round(s * fps))
    except ValueError:
        return 0


def _fascia(frame):
    """La fascia alta dell'immagine, ridotta e in grigio (float32), su cui si allinea."""
    h = int(round(frame.shape[0] * LARGHEZZA / frame.shape[1]))
    g = cv2.cvtColor(cv2.resize(frame, (LARGHEZZA, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    return g[:max(32, int(round(h * FASCIA_ALTA)))].astype(np.float32)


def misura(video, frame_rif, verbose=True):
    """Lista di (frame da 1, dx, dy, risposta) per tutto il video; dx, dy in pixel del video, risposta =
    coefficiente di correlazione dell'allineamento (1 = perfetto; 0 = allineamento fallito, tenuto il precedente)."""
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        return None
    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_rif))
    ok, fr = cap.read()
    if not ok:
        cap.release()
        return None
    rif = _fascia(fr)
    scala = w / LARGHEZZA
    criterio = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, ITERAZIONI, 1e-3)
    W = np.eye(2, 3, dtype=np.float32)          # si parte ogni volta dallo spostamento del fotogramma prima
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    righe, f = [], 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        f += 1
        try:
            cc, W = cv2.findTransformECC(rif, _fascia(fr), W, cv2.MOTION_TRANSLATION, criterio, None, 5)
        except cv2.error:
            cc = 0.0
        righe.append((f, float(W[0, 2]) * scala, float(W[1, 2]) * scala, float(cc)))
    cap.release()
    if not righe:
        return None
    if verbose:
        sp = np.hypot([r[1] for r in righe], [r[2] for r in righe])
        print(f"camera: spostamento rispetto al fotogramma {frame_rif + 1}: massimo {sp.max():.0f} px, "
              f"mediana {np.median(sp):.0f} px, correlazione minima {min(r[3] for r in righe):.2f} ({len(righe)} fotogrammi)")
    return righe


def percorso(cartella_dati, video):
    nome = os.path.splitext(os.path.basename(video))[0]
    return os.path.join(cartella_dati, nome + "_camera.csv")


def salva(p, righe):
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "dx", "dy", "risposta"])
        for f, dx, dy, r in righe:
            w.writerow([f, f"{dx:.2f}", f"{dy:.2f}", f"{r:.3f}"])


def carica(cartella_dati, video):
    """{frame: (dx, dy, risposta)} dal CSV, o None se non c'e'."""
    p = percorso(cartella_dati, video)
    if not os.path.exists(p):
        return None
    tab = {}
    for r in csv.DictReader(open(p, newline="")):
        tab[int(r["frame"])] = (float(r["dx"]), float(r["dy"]), float(r["risposta"]))
    return tab or None


def tabella(video, cartella_dati, cal, fps, verbose=True):
    """La tabella degli spostamenti: dal CSV se c'e', altrimenti la misura e la salva. None se non si puo'."""
    if not CORREGGI:
        return None
    tab = carica(cartella_dati, video)
    if tab is not None:
        return tab
    righe = misura(video, fotogramma_calibrazione(cal, fps), verbose)
    if righe is None:
        return None
    salva(percorso(cartella_dati, video), righe)
    return {f: (dx, dy, r) for f, dx, dy, r in righe}


def spostamento(tab, f):
    """(dx, dy, risposta) al frame f (da 1); (0, 0, 1) senza tabella."""
    if not tab:
        return 0.0, 0.0, 1.0
    if f in tab:
        return tab[f]
    vicino = min(tab, key=lambda g: abs(g - f))
    return tab[vicino]


def camera_al_frame(cam, tab, f):
    """La calibrazione corretta per il frame f: centro dell'immagine spostato di (dx, dy)."""
    dx, dy, _ = spostamento(tab, f)
    if dx == 0 and dy == 0:
        return cam
    K = np.array(cam["K"], float)
    K[0, 2] += dx
    K[1, 2] += dy
    return {"K": K, "rvec": cam["rvec"], "tvec": cam["tvec"]}


def cal_al_frame(cal, tab, f):
    """Come camera_al_frame, ma sul JSON della calibrazione (per disegna_controllo)."""
    dx, dy, _ = spostamento(tab, f)
    if dx == 0 and dy == 0:
        return cal
    c = dict(cal)
    K = [list(r) for r in cal["K"]]
    K[0][2] += dx
    K[1][2] += dy
    c["K"] = K
    return c


def livello(tab, f, altezza_img):
    """("ok" | "moderata" | "eccessiva", spostamento in px a 1080p) al frame f."""
    dx, dy, ris = spostamento(tab, f)
    px = float(np.hypot(dx, dy) * 1080.0 / altezza_img)
    if not tab:
        return "ok", 0.0
    if ris < RISPOSTA_MIN or px > MOSSA_ECCESSIVA_PX:
        return "eccessiva", px
    if px > MOSSA_MODERATA_PX:
        return "moderata", px
    return "ok", px


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--dati", default="outputs/dati")
    ap.add_argument("--calibrazione")
    a = ap.parse_args()
    cal, _ = carica_per_video(a.video, a.calibrazione)
    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    righe = misura(a.video, fotogramma_calibrazione(cal, fps))
    if righe is None:
        raise SystemExit("Video non leggibile: " + a.video)
    p = percorso(a.dati, a.video)
    salva(p, righe)
    print("Salvato in", p)


if __name__ == "__main__":
    main()
