"""
sovrapponi_colpi.py - riscrive un video con sopra la classe prevista
(dritto o rovescio) frame per frame, piu' una striscia temporale in basso
che mostra l'andamento di tutto il video con un cursore sul frame corrente.

Serve a giudicare a occhio se il classificatore ci prende, cosa che una
tabella di numeri non permette.

    python classificazione/sovrapponi_colpi.py --video outputs/<video>_combined_weight.mp4 \
                                               --colpi outputs/<video>_colpi.csv

Se non passi --video, cerca il video combinato con lo stesso nome del CSV.
Con --max-frame 120 elabora solo i primi 120 frame (prova rapida).
"""

import argparse
import csv
import glob
import os

import cv2

COLORI = {"dritto": (80, 220, 80), "rovescio": (255, 170, 60)}  # BGR
FONT = cv2.FONT_HERSHEY_SIMPLEX


def stile(frame):
    """Stessa formula di ultralytics, cosi' le scritte restano leggibili a ogni risoluzione."""
    h, w = frame.shape[:2]
    spessore_linea = max(round((h + w + 3) / 2 * 0.003), 2)
    return spessore_linea / 3, max(spessore_linea - 1, 1)


def disegna_etichetta(frame, testo, colore):
    scala, spessore = stile(frame)
    scala *= 1.6  # l'etichetta del colpo e' l'informazione principale: piu' grande delle altre
    (tw, th), base = cv2.getTextSize(testo, FONT, scala, spessore)
    x, y = 20, 20
    cv2.rectangle(frame, (x, y), (x + tw + 20, y + th + base + 20), colore, -1)
    cv2.putText(frame, testo, (x + 10, y + th + 10), FONT, scala, (0, 0, 0), spessore)


def disegna_striscia(frame, classi_per_frame, frame_corrente, totale):
    """Striscia temporale: una colonna per frame, colorata per classe."""
    h, w = frame.shape[:2]
    alt = max(8, h // 60)
    y0 = h - alt - 10

    for x in range(w):
        n = int(x / w * totale) + 1
        classe = classi_per_frame.get(n)
        colore = COLORI.get(classe, (60, 60, 60))
        cv2.line(frame, (x, y0), (x, y0 + alt), colore, 1)

    x_cursore = int((frame_corrente - 1) / max(1, totale) * w)
    cv2.line(frame, (x_cursore, y0 - 6), (x_cursore, y0 + alt + 6), (255, 255, 255), max(2, w // 900))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--colpi", required=True)
    p.add_argument("--video")
    p.add_argument("--out")
    p.add_argument("--max-frame", type=int, default=0)
    args = p.parse_args()

    righe = list(csv.DictReader(open(args.colpi, newline="")))
    classi = {int(r["frame"]): r["classe"] for r in righe}
    sicurezze = {int(r["frame"]): float(r["sicurezza"]) for r in righe}

    video = args.video
    if not video:
        # i CSV stanno in outputs/dati, i video in outputs/video
        nome = os.path.basename(args.colpi).replace("_colpi.csv", "")
        cartella_video = os.path.join(os.path.dirname(os.path.dirname(args.colpi) or "."), "video")
        candidati = sorted(glob.glob(os.path.join(cartella_video, nome + "_combined*.mp4")))
        if not candidati:
            candidati = sorted(glob.glob(args.colpi.replace("_colpi.csv", "") + "_combined*.mp4"))
        base = os.path.join(cartella_video, nome)
        if not candidati:
            raise SystemExit(f"Non trovo il video: passalo con --video (cercavo {base}_combined*.mp4)")
        video = candidati[-1]

    uscita = args.out or video.replace(".mp4", "_colpi.mp4")
    os.makedirs(os.path.dirname(uscita) or ".", exist_ok=True)

    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise SystemExit(f"Non riesco ad aprire {video}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    totale = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or max(classi)

    writer = cv2.VideoWriter(uscita, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    n = 0

    while True:
        ok, frame = cap.read()
        if not ok or (args.max_frame and n >= args.max_frame):
            break
        n += 1

        classe = classi.get(n)
        if classe:
            disegna_etichetta(frame, f"{classe.upper()} {sicurezze.get(n, 0):.2f}", COLORI.get(classe, (200, 200, 200)))
        disegna_striscia(frame, classi, n, totale)
        writer.write(frame)

    cap.release()
    writer.release()
    print(f"{n} frame scritti in {uscita}")


if __name__ == "__main__":
    main()
