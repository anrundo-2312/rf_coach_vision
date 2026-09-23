"""
estrai_frame.py - estrae dai video i fotogrammi da annotare per il
fine-tuning del rilevatore di racchetta.

Uso (dalla cartella rfCoach_vision):
    python finetuning/estrai_frame.py                 # tutti i video in inputs/
    python finetuning/estrai_frame.py video1.mp4 ...  # solo questi
    python finetuning/estrai_frame.py --per-video 40  # quanti frame per video (default 60)

I frame finiscono in finetuning/dataset/images/, ridimensionati a 1920 px
di larghezza: piu' leggeri da caricare su Roboflow/CVAT e comunque molto
piu' grandi della risoluzione a cui lavora il modello (960).

Perche' non prendere frame consecutivi: sarebbero quasi identici e il
modello imparerebbe poco. Meglio pochi frame distribuiti su tutta la
durata di piu' video. Per questo si sceglie QUANTI frame prendere per
video, e il passo viene calcolato di conseguenza.
"""

import os
import sys
import glob
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "finetuning", "dataset", "images")
MAX_WIDTH = 1920


def estrai(video_path, quanti):
    nome = os.path.splitext(os.path.basename(video_path))[0]
    cap = cv2.VideoCapture(video_path)
    totale_frame = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if totale_frame <= 0:
        cap.release()
        return 0

    passo = max(1, totale_frame // quanti)
    salvati = 0

    for i in range(0, totale_frame, passo):
        # Salto diretto al frame: molto piu' veloce che decodificare tutto
        # il video, soprattutto in 4K.
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            break

        h, w = frame.shape[:2]
        if w > MAX_WIDTH:
            frame = cv2.resize(frame, (MAX_WIDTH, round(h * MAX_WIDTH / w)), interpolation=cv2.INTER_AREA)

        cv2.imwrite(os.path.join(OUT_DIR, f"{nome}_f{i:05d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        salvati += 1

    cap.release()
    return salvati


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quanti = 60
    if "--per-video" in sys.argv:
        quanti = int(sys.argv[sys.argv.index("--per-video") + 1])
        args = [a for a in args if a != str(quanti)]

    video = [a if os.path.exists(a) else os.path.join(ROOT, "inputs", a) for a in args]
    if not video:
        video = sorted(glob.glob(os.path.join(ROOT, "inputs", "*.mp4")))

    os.makedirs(OUT_DIR, exist_ok=True)
    totale = 0
    for v in video:
        n = estrai(v, quanti)
        totale += n
        print(f"{os.path.basename(v)}: {n} frame")

    print(f"\nTotale: {totale} frame in {OUT_DIR}")
    print("Prossimo passo: pre-annotazione (finetuning/preannota.py, va eseguito su Colab o dove c'e' ultralytics).")
