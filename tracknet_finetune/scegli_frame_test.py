"""
scegli_frame_test.py - sceglie i fotogrammi del SET DI TEST da etichettare a
mano e li estrae come immagini, pronti per etichetta_pallina.py.

    python tracknet_finetune/scegli_frame_test.py

Il set di test serve a dare il voto a TrackNet prima e dopo il fine-tuning: va
fatto su video che NON vengono mai usati per addestrare. Di default:
nicola_matarese_trim, zverev_djokovic_trim_swin_like, swing_vision_test1_trim,
alcaraz e un pezzo di ex.mp4 (--ex_da / --ex_a, in secondi).

Quali fotogrammi:
  - attorno a ogni colpo trovato dal programma (colonna "frame" di
    outputs/dati/<video>_velocita.csv): +-0,12 s (--mezza_finestra_s), cioe'
    proprio dove TrackNet sbaglia di piu' (pallina mossa, pallina che arriva
    lungo la linea di vista);
  - qualche fotogramma a caso lontano dai colpi (--casuali), per contare anche
    i punti falsi (righe del campo, palline ferme).

I numeri dei fotogrammi partono da 1, come in outputs/dati/<video>_tracking.csv
e _velocita.csv (TrackNet nel suo CSV parte da 0: Frame = frame - 1).

Uscite (nella cartella tracknet_finetune/test/):
  lista_frame.csv              video, frame, motivo (colpo/casuale), colpo_frame,
                               distanza_colpo, suggerimenti (TrackNet e colore)
  fotogrammi/<video>/<frame>.jpg   i fotogrammi da etichettare e quelli accanto
                               (+-1, per guardare il movimento). Le immagini non
                               vanno su GitHub (.gitignore: *.jpg).

I fotogrammi si estraggono leggendo il video DALL'INIZIO, uno dopo l'altro
(come fanno TrackNet e analyze.py): saltare con CAP_PROP_POS_FRAMES a volte
sbaglia di qualche fotogramma e le etichette finirebbero sul fotogramma sbagliato.
"""

import argparse
import json
import os
import random
import sys

import cv2
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, RADICE)
try:
    from sincronizza_drive import CARTELLA_DRIVE
except ImportError:
    CARTELLA_DRIVE = ""

VIDEO_TEST = ["nicola_matarese_trim.mp4", "zverev_djokovic_trim_swin_like.mp4", "swing_vision_test1_trim.mp4",
              "alcaraz.mp4", "ex.mp4"]


def trova(nome, cartelle):
    for c in cartelle:
        p = os.path.join(c, nome)
        if c and os.path.exists(p):
            return p
    return None


def info_video(percorso):
    cap = cv2.VideoCapture(percorso)
    if not cap.isOpened():
        raise SystemExit(f"Non riesco ad aprire {percorso}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return fps, n


def suggerimenti(stem, cartelle_dati):
    """{frame: (x, y)} di TrackNet (dal tracking CSV) e {frame: (x, y)} dei punti usati nei calcoli."""
    tn, col = {}, {}
    p = trova(f"{stem}_tracking.csv", cartelle_dati)
    if p:
        t = pd.read_csv(p, usecols=lambda c: c in ("frame", "pallina_x", "pallina_y", "pallina_fonte"))
        if "pallina_fonte" in t.columns:
            t = t[t["pallina_fonte"] == "tracknet"]
        t = t[t["pallina_x"].notna()]
        tn = {int(f): (float(x), float(y)) for f, x, y in zip(t["frame"], t["pallina_x"], t["pallina_y"])}
    p = trova(f"{stem}_velocita_punti.json", cartelle_dati)
    if p:
        for colpo in json.load(open(p, encoding="utf-8")):
            for f, x, y in colpo.get("_punti", []):
                col[int(f)] = (float(x), float(y))
    return tn, col


def scegli_video(nome, percorso, cartelle_dati, a, rnd):
    stem = os.path.splitext(nome)[0]
    fps, n = info_video(percorso)
    p = trova(f"{stem}_velocita.csv", cartelle_dati)
    if not p:
        print(f"[{nome}] manca {stem}_velocita.csv in {cartelle_dati}: solo fotogrammi a caso")
        colpi = []
    else:
        colpi = sorted({int(f) for f in pd.read_csv(p)["frame"].dropna()})
    da, a_ = 1, n
    if stem == "ex":
        da, a_ = int(a.ex_da * fps) + 1, min(n, int(a.ex_a * fps))
        colpi = [c for c in colpi if da <= c <= a_][: a.ex_max_colpi]
    meta = max(1, round(a.mezza_finestra_s * fps))
    scelti = {}
    for c in colpi:
        for f in range(max(da, c - meta), min(a_, c + meta) + 1):
            if f not in scelti or abs(f - c) < abs(scelti[f]["distanza_colpo"]):
                scelti[f] = {"motivo": "colpo", "colpo_frame": c, "distanza_colpo": f - c}
    lontano = round(0.5 * fps)
    candidati = [f for f in range(da, a_ + 1) if all(abs(f - c) > lontano for c in colpi)]
    k = a.casuali_ex if stem == "ex" else a.casuali
    for f in sorted(rnd.sample(candidati, min(k, len(candidati)))):
        scelti[f] = {"motivo": "casuale", "colpo_frame": "", "distanza_colpo": ""}
    tn, col = suggerimenti(stem, cartelle_dati)
    righe = []
    for f in sorted(scelti):
        r = {"video": nome, "frame": f, **scelti[f]}
        r["sugg_tracknet_x"], r["sugg_tracknet_y"] = tn.get(f, ("", ""))
        r["sugg_colore_x"], r["sugg_colore_y"] = col.get(f, ("", ""))
        righe.append(r)
    print(f"[{nome}] {fps:.2f} fps, {n} fotogrammi: {len(colpi)} colpi, {len(righe)} fotogrammi da etichettare")
    return righe


def estrai(nome, percorso, frames, cartella):
    """Salva come JPG i fotogrammi richiesti (e +-1), leggendo il video in fila dall'inizio."""
    stem = os.path.splitext(nome)[0]
    voluti = set()
    for f in frames:
        voluti.update((f - 1, f, f + 1))
    os.makedirs(os.path.join(cartella, stem), exist_ok=True)
    mancano = {f for f in voluti if f >= 1 and not os.path.exists(os.path.join(cartella, stem, f"{f:06d}.jpg"))}
    if not mancano:
        return
    ultimo = max(mancano)
    cap = cv2.VideoCapture(percorso)
    f = 0
    while f < ultimo:
        f += 1
        if f in mancano:
            ok, img = cap.read()
            if not ok:
                break
            cv2.imwrite(os.path.join(cartella, stem, f"{f:06d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        elif not cap.grab():
            break
        if f % 3000 == 0:
            print(f"   {nome}: letti {f}/{ultimo}")
    cap.release()
    print(f"   {nome}: estratti {len(mancano)} fotogrammi")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--video", nargs="*", default=VIDEO_TEST)
    p.add_argument("--video_dir", nargs="*", default=None,
                   help="dove cercare i video (default: Drive inputs/, poi inputs/ del progetto)")
    p.add_argument("--dati_dir", nargs="*", default=None,
                   help="dove cercare _velocita.csv e _tracking.csv (default: Drive outputs/dati, poi outputs/dati)")
    p.add_argument("--uscita", default=os.path.join(QUI, "test"))
    p.add_argument("--mezza_finestra_s", type=float, default=0.12)
    p.add_argument("--casuali", type=int, default=10, help="fotogrammi a caso per video")
    p.add_argument("--casuali_ex", type=int, default=20)
    p.add_argument("--ex_da", type=float, default=60.0, help="inizio del pezzo di ex.mp4 (s)")
    p.add_argument("--ex_a", type=float, default=150.0, help="fine del pezzo di ex.mp4 (s)")
    p.add_argument("--ex_max_colpi", type=int, default=10)
    p.add_argument("--seme", type=int, default=13)
    a = p.parse_args()

    drive = CARTELLA_DRIVE if CARTELLA_DRIVE and os.path.isdir(CARTELLA_DRIVE) else ""
    cartelle_video = a.video_dir or [os.path.join(drive, "inputs") if drive else "", os.path.join(RADICE, "inputs")]
    cartelle_dati = a.dati_dir or [os.path.join(drive, "outputs", "dati") if drive else "",
                                   os.path.join(RADICE, "outputs", "dati")]
    os.makedirs(a.uscita, exist_ok=True)
    p_lista = os.path.join(a.uscita, "lista_frame.csv")
    if os.path.exists(p_lista):
        raise SystemExit(f"{p_lista} esiste gia': non la riscrivo (le etichette fatte si riferiscono a quella). "
                         "Per rifarla cancellala o usa --uscita.")
    rnd = random.Random(a.seme)
    tutte = []
    for nome in a.video:
        percorso = trova(nome, cartelle_video)
        if not percorso:
            print(f"[{nome}] video non trovato in {cartelle_video}: salto")
            continue
        righe = scegli_video(nome, percorso, cartelle_dati, a, rnd)
        estrai(nome, percorso, [r["frame"] for r in righe], os.path.join(a.uscita, "fotogrammi"))
        tutte += righe
    if not tutte:
        raise SystemExit("Nessun fotogramma scelto.")
    pd.DataFrame(tutte).to_csv(p_lista, index=False)
    print(f"\n{len(tutte)} fotogrammi da etichettare in {p_lista}")
    print("Ora: python tracknet_finetune/etichetta_pallina.py")


if __name__ == "__main__":
    main()
