"""
ball_tracknet.py

Wrapper attorno a tracknet3/predict.py (TrackNetV3, vendorizzato da
https://github.com/qaz812345/TrackNetV3, licenza MIT) per ottenere la
traiettoria della pallina su un intero video.

TrackNet non lavora un frame alla volta come YOLO: guarda sequenze di
frame consecutivi per sfruttare il movimento. Per questo gira UNA volta
sull'intero video (come sotto-processo) prima del ciclo frame per frame
di analyze.py.

CACHE: il risultato viene salvato in tracknet3/pred_result/<video>_ball_<modalita>.csv
(una copia per modalita', "weight" o "nonoverlap", cosi' si possono confrontare).
La prima volta che analizzi un video TrackNet lo calcola (su CPU in 4K
richiede ~20 minuti); le volte successive sullo STESSO video il CSV viene
riusato e la pallina e' disponibile subito. Si ricalcola da solo se il
video viene modificato o se il CSV e' in un formato vecchio; per forzarlo
a mano basta cancellare il CSV.

Ogni posizione restituita e' una tupla (x, y, conf, source):
  source = "tracknet" -> pallina vista da TrackNet, conf = picco heatmap (0-1)
  source = "stimata"  -> posizione ricostruita da InpaintNet (conf = None)

Nota: i pesi pubblici di TrackNetV3 sono addestrati sul badminton, non sul
tennis dalla vostra inquadratura: per una buona precisione servira'
fine-tuning sui vostri video.
"""

import os
import csv
import subprocess
import sys
import time

TRACKNET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracknet3")
TRACKNET_CKPT = os.path.join(TRACKNET_DIR, "ckpts", "TrackNet_best.pt")
INPAINTNET_CKPT = os.path.join(TRACKNET_DIR, "ckpts", "InpaintNet_best.pt")
PRED_DIR = os.path.join(TRACKNET_DIR, "pred_result")


def _cache_valid(csv_path, video_file):
    if not os.path.exists(csv_path):
        return False
    if os.path.getmtime(csv_path) < os.path.getmtime(video_file):
        return False
    with open(csv_path, newline="") as f:
        header = f.readline()
    return "Conf" in header and "Source" in header


def compute_ball_trajectory(video_file, mode="weight", force=False):
    """
    force: se True ignora il risultato salvato, ricalcola e lo sovrascrive.
    mode: "weight" (finestra scorrevole, ~8 analisi per frame mediate) oppure
          "nonoverlap" (una analisi per frame, piu' veloce).
    Restituisce {numero_frame (0-based): (x, y, conf, source) oppure None}.
    Restituisce {} (senza errori) se i pesi mancano o TrackNet fallisce.
    """

    if not os.path.exists(TRACKNET_CKPT):
        print(
            "[pallina] Pesi TrackNet non trovati (vedi tracknet3/ckpts/LEGGIMI.txt): "
            "proseguo senza pallina.\n"
        )
        return {}

    os.makedirs(PRED_DIR, exist_ok=True)

    video_name = os.path.splitext(os.path.basename(video_file))[0]
    if mode not in ("weight", "nonoverlap"):
        print(f"[pallina] TRACKNET_MODE non valido: '{mode}' (usa 'weight' o 'nonoverlap'): proseguo senza pallina.")
        return {}

    raw_csv = os.path.join(PRED_DIR, f"{video_name}_ball.csv")  # nome scritto da predict.py
    csv_path = os.path.join(PRED_DIR, f"{video_name}_ball_{mode}.csv")

    # Un risultato gia' nel formato nuovo ma senza modalita' nel nome e'
    # stato prodotto con la modalita' di default ("weight"): lo adottiamo.
    if mode == "weight" and not os.path.exists(csv_path) and _cache_valid(raw_csv, video_file):
        os.replace(raw_csv, csv_path)

    if not force and _cache_valid(csv_path, video_file):
        return _read_positions(csv_path)

    cmd = [
        sys.executable,
        os.path.join(TRACKNET_DIR, "predict.py"),
        "--video_file", os.path.abspath(video_file),
        "--tracknet_file", TRACKNET_CKPT,
        "--save_dir", PRED_DIR,
        "--eval_mode", mode,
    ]

    if os.path.exists(INPAINTNET_CKPT):
        cmd += ["--inpaintnet_file", INPAINTNET_CKPT]

    # Unico messaggio mostrato: serve perche' questo passaggio dura parecchi
    # minuti e senza avviso sembrerebbe bloccato.
    print(f"Calcolo traiettoria pallina con TrackNet, modalita' '{mode}' "
          "(puo' richiedere diversi minuti)...")

    start = time.time()
    result = subprocess.run(cmd, cwd=TRACKNET_DIR)
    minutes = (time.time() - start) / 60

    if result.returncode == 0 and os.path.exists(raw_csv):
        print(f"TrackNet ({mode}) completato in {minutes:.1f} minuti.")
        try:
            os.replace(raw_csv, csv_path)  # sovrascrive l'eventuale risultato precedente
        except PermissionError:
            # Succede se il CSV vecchio e' aperto in un altro programma (es. Excel).
            print(f"[pallina] Non posso sovrascrivere {os.path.basename(csv_path)}: "
                  "e' aperto in un altro programma? Chiudilo. Per ora uso il risultato "
                  f"nuovo da {os.path.basename(raw_csv)}.")
            return _read_positions(raw_csv)

    if result.returncode != 0 or not os.path.exists(csv_path):
        print(
            "\n[pallina] TrackNet non ha prodotto un risultato valido "
            "(vedi l'errore sopra): proseguo senza pallina.\n"
        )
        return {}

    return _read_positions(csv_path)


def _read_positions(csv_path):
    positions = {}

    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            frame_idx = int(row["Frame"])
            if int(row["Visibility"]):
                source = row.get("Source") or "tracknet"
                conf = float(row["Conf"]) if source == "tracknet" else None
                positions[frame_idx] = (float(row["X"]), float(row["Y"]), conf, source)
            else:
                positions[frame_idx] = None

    return positions
