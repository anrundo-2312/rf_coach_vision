"""
fotogrammi.py - fotogrammi ripetuti e istanti veri dei fotogrammi.

Alcuni video non sono l'originale della camera ma una conversione: per
esempio alcaraz.mp4 e' stato girato a 50 fps e convertito a 60 ripetendo un
fotogramma ogni 6. Il calcolo della velocita' assume che tra un fotogramma e
l'altro passi sempre lo stesso tempo (1/60 s): nel fotogramma ripetuto la
pallina sembra ferma e in quello dopo salta, e la traiettoria non torna. Sul
dritto al frame 275 di alcaraz, con gli istanti veri l'errore della
traiettoria scende da 2,8 a 1,1 px e la velocita' da 147 a 139 km/h (dal
rimbalzo si stimano circa 128 km/h).

Qui si trovano i fotogrammi ripetuti e si da' a ogni fotogramma il suo
istante vero. Si attiva SOLO se le ripetizioni sono regolari: almeno l'8%
dei fotogrammi, quasi sempre con lo stesso passo. Nei video del telefono non
succede (nicola, djokovic, swing_vision: nessuna ripetizione regolare) e il
calcolo resta identico.

Come si riconosce un fotogramma ripetuto: il video si legge ridotto a
192x108 in grigi (con ffmpeg, veloce); un fotogramma e' ripetuto se e' molto
piu' simile al precedente di quanto lo siano, in media, i fotogrammi vicini
(differenza sotto 1/4 della mediana locale). Poi, trovato il passo (es. 6),
si cercano i ripetuti sfuggiti dove il ritmo li aspetta (scene quasi ferme).

Per non leggere il video piu' volte il risultato si salva in
outputs/dati/<video>_fotogrammi.csv. Per non perdere tempo sui video
normali si guardano prima i primi 600 fotogrammi: se li' non ci sono
ripetizioni regolari ci si ferma.
"""

import csv
import os
import subprocess
from collections import Counter

import cv2
import numpy as np

LARGHEZZA, ALTEZZA = 192, 108   # risoluzione ridotta per confrontare i fotogrammi
PRIMA_PROVA = 600               # fotogrammi guardati prima di decidere se leggere tutto
QUOTA_MINIMA = 0.08             # almeno l'8% dei fotogrammi ripetuti
SOGLIA_RELATIVA = 0.25          # ripetuto: differenza < 1/4 della mediana locale
SOGLIA_RITMO = 0.7              # ripetuto "sfuggito" dove il ritmo lo aspetta: < 0,7 della mediana locale


def _differenze(video, massimo=None):
    """Differenza media (0-255) di ogni fotogramma dal precedente, a bassa risoluzione."""
    comando = ["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={LARGHEZZA}:{ALTEZZA},format=gray",
               "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    dim = LARGHEZZA * ALTEZZA
    d, prev = [], None
    try:
        proc = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except FileNotFoundError:                     # niente ffmpeg: si legge con OpenCV (piu' lento)
        proc = None
    if proc is not None:
        while massimo is None or len(d) < massimo:
            buf = proc.stdout.read(dim)
            if len(buf) < dim:
                break
            g = np.frombuffer(buf, np.uint8).astype(np.float32)
            if prev is not None:
                d.append(float(np.abs(g - prev).mean()))
            prev = g
        proc.kill()
        proc.wait()
    else:
        cap = cv2.VideoCapture(video)
        while massimo is None or len(d) < massimo:
            ok, fr = cap.read()
            if not ok:
                break
            g = cv2.cvtColor(cv2.resize(fr, (LARGHEZZA, ALTEZZA), interpolation=cv2.INTER_AREA),
                             cv2.COLOR_BGR2GRAY).astype(np.float32)
            if prev is not None:
                d.append(float(np.abs(g - prev).mean()))
            prev = g
        cap.release()
    return np.array(d)


def _ripetuti(d):
    """
    (ripetuti, passo) con ripetuti[n] vero se il fotogramma n (numerato da 1) ripete il n-1;
    passo None se le ripetizioni non sono regolari.
    """
    n = len(d) + 1
    rip = np.zeros(n + 1, bool)
    for i in range(len(d)):
        rip[i + 2] = d[i] < SOGLIA_RELATIVA * np.median(d[max(0, i - 6): i + 7])
    fr = np.flatnonzero(rip)
    if len(fr) < QUOTA_MINIMA * n:
        return rip, None
    passo, quanti = Counter(np.diff(fr)).most_common(1)[0]
    if quanti < 0.5 * (len(fr) - 1):
        return rip, None
    # ripetuti sfuggiti (scena quasi ferma): il fotogramma piu' simile al precedente dove il ritmo lo aspetta
    for a, b in zip(fr, fr[1:]):
        m = a + passo
        while b - m >= passo - 1:
            candidati = [x for x in (m - 1, m, m + 1) if 2 <= x < b]
            x = min(candidati, key=lambda x: d[x - 2])
            if d[x - 2] < SOGLIA_RITMO * np.median(d[max(0, x - 8): x + 6]):
                rip[x] = True
            m = x + passo
    return rip, int(passo)


def tempi_reali(video, cartella_dati, fps_video, verbose=True):
    """
    None se il video non ha fotogrammi ripetuti regolari (caso normale: niente cambia).
    Altrimenti {"dup": array di bool per frame (indice = numero del frame, da 1),
                "k": indice del fotogramma vero mostrato in ogni frame,
                "fps": fotogrammi veri al secondo}.
    """
    nome = os.path.splitext(os.path.basename(video))[0]
    percorso = os.path.join(cartella_dati, nome + "_fotogrammi.csv")
    if os.path.exists(percorso) and os.path.getmtime(percorso) >= os.path.getmtime(video):
        d = np.array([float(r["differenza"]) for r in csv.DictReader(open(percorso)) if r["differenza"] != ""])
    else:
        d = _differenze(video, PRIMA_PROVA)
        if len(d) >= PRIMA_PROVA - 1 and _ripetuti(d)[1] is not None:
            d = _differenze(video)                # ripetizioni regolari: si legge tutto il video
        with open(percorso, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "differenza"])
            w.writerow([1, ""])
            w.writerows([[i + 2, round(float(x), 4)] for i, x in enumerate(d)])
    rip, passo = _ripetuti(d)
    if passo is None:
        return None
    n = len(d) + 1
    fps = fps_video * (n - rip[1:].sum()) / n
    rip = np.r_[rip, np.zeros(100, bool)]         # margine se il tracking conta qualche frame in piu'
    if verbose:
        print(f"Video convertito: {int(rip.sum())} fotogrammi ripetuti su {n} (uno ogni {passo}), "
              f"{fps:.1f} fotogrammi veri al secondo: si usano gli istanti veri.")
    return {"dup": rip, "k": np.cumsum(~rip) - 1, "fps": float(fps)}
