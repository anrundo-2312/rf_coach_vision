"""
prepara_colab.py - crea lo zip da caricare su Google Drive per Colab.

Uso (dalla cartella rfCoach_vision):
    python colab/prepara_colab.py                 -> zip con codice, modelli, cache e il video di prova
    python colab/prepara_colab.py video1.mp4 ...  -> include questi video (presi da inputs/)

Crea colab/rf_coach_vision_colab.zip con SOLO cio' che serve: niente repo
ultralytics clonato, niente backup, niente output.
"""

import os
import sys
import glob
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "colab", "rf_coach_vision_colab.zip")

FILES = [
    "analyze.py",
    "ball_tracknet.py",
    "tennis_yolo11.pt",
    "yolo11n-pose.pt",
    "tracknet3/__init__.py",
    "tracknet3/LICENSE",
    "tracknet3/dataset.py",
    "tracknet3/infer_utils.py",
    "tracknet3/model.py",
    "tracknet3/predict.py",
    "tracknet3/utils/__init__.py",
    "tracknet3/utils/general.py",
    "tracknet3/ckpts/TrackNet_best.pt",
    "tracknet3/ckpts/InpaintNet_best.pt",
]

videos = sys.argv[1:] or ["zverev_djokovic_trim_swin_like.mp4"]
files = FILES + [f"inputs/{os.path.basename(v)}" for v in videos]
files += [os.path.relpath(p, ROOT).replace(os.sep, "/")
          for p in glob.glob(os.path.join(ROOT, "tracknet3", "pred_result", "*.csv"))]

missing = [f for f in files if not os.path.exists(os.path.join(ROOT, f))]
if missing:
    print("File mancanti:", *missing, sep="\n  ")
    sys.exit(1)

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(os.path.join(ROOT, f), f)

print(f"Creato {OUT} ({os.path.getsize(OUT) / 1e6:.0f} MB, {len(files)} file)")
print("Caricalo su Google Drive nella cartella: Il mio Drive/rf_coach_vision/")
