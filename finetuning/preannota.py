"""
preannota.py - pre-annotazione automatica dei frame estratti.

Fa girare il rilevatore di racchetta attuale (piu' il filtro "deve toccare
la mano") su ogni immagine di finetuning/dataset/images e scrive le
etichette in formato YOLO in finetuning/dataset/labels.

NON sostituisce il tuo lavoro: serve a partire da riquadri gia' quasi
giusti, che tu correggi (sposti, aggiungi, cancelli) invece di disegnarli
da zero. Le ombre della racchetta, che il modello attuale scambia spesso
per racchette, vanno lasciate SENZA riquadro: cosi' il modello impara a
ignorarle.

Va eseguito dove ci sono torch e ultralytics: su Colab, oppure nel tuo
ambiente Python su Windows.

    python finetuning/preannota.py                # soglia 0.15
    python finetuning/preannota.py --conf 0.10    # piu' candidati, piu' correzioni
    python finetuning/preannota.py --anteprime    # salva anche le immagini con i riquadri

Le funzioni di filtro NON sono duplicate: vengono lette da analyze.py, che
resta l'unica fonte. Se cambiano li', cambiano anche qui.
"""

import ast
import glob
import os
import sys

import cv2
import math
import numpy as np
from ultralytics import YOLO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "finetuning", "dataset", "images")
LBL_DIR = os.path.join(ROOT, "finetuning", "dataset", "labels")
PREVIEW_DIR = os.path.join(ROOT, "finetuning", "dataset", "anteprime")


def carica_da_analyze():
    """
    Prende da analyze.py solo le costanti e le funzioni che servono
    (niente modelli, niente ciclo video: quel file e' uno script, non una
    libreria, quindi ne eseguiamo unicamente le definizioni).
    """

    albero = ast.parse(open(os.path.join(ROOT, "analyze.py"), encoding="utf-8").read())
    ns = {"cv2": cv2, "math": math, "np": np}
    voluti = {"get_player_box", "get_wrist_points", "filter_racket_by_wrist",
              "_dist_point_box", "expand_box", "detect_racket_boxes"}

    for nodo in albero.body:
        if isinstance(nodo, ast.Assign) and isinstance(nodo.value, (ast.Constant, ast.Tuple, ast.List)):
            exec(compile(ast.Module([nodo], []), "analyze.py", "exec"), ns)
        elif isinstance(nodo, ast.FunctionDef) and nodo.name in voluti:
            exec(compile(ast.Module([nodo], []), "analyze.py", "exec"), ns)

    return ns


def main():
    conf = 0.15
    if "--conf" in sys.argv:
        conf = float(sys.argv[sys.argv.index("--conf") + 1])
    anteprime = "--anteprime" in sys.argv

    ns = carica_da_analyze()
    os.makedirs(LBL_DIR, exist_ok=True)
    if anteprime:
        os.makedirs(PREVIEW_DIR, exist_ok=True)

    pose_model = YOLO(os.path.join(ROOT, "yolo11n-pose.pt"))
    racket_model = YOLO(os.path.join(ROOT, "tennis_yolo11.pt"))

    immagini = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))
    con_racchetta = 0

    for path in immagini:
        img = cv2.imread(path)
        h, w = img.shape[:2]

        pose = pose_model(img, verbose=False)[0]
        player_box, _, player_idx = ns["get_player_box"](pose)

        righe = []

        if player_box is not None:
            x1, y1, x2, y2 = ns["expand_box"](player_box, img.shape, ns["CROP_MARGIN"])
            crop = img[y1:y2, x1:x2]

            if crop.size:
                res = racket_model(crop, conf=conf, imgsz=ns["RACKET_IMGSZ"],
                                   classes=[ns["RACKET_CLASS_ID"]], verbose=False)[0]
                det = []
                if res.boxes is not None:
                    for b in res.boxes:
                        bx1, by1, bx2, by2 = b.xyxy[0].tolist()
                        det.append((bx1 + x1, by1 + y1, bx2 + x1, by2 + y1, float(b.conf[0])))

                polsi = ns["get_wrist_points"](pose, player_idx)
                tenute, _ = ns["filter_racket_by_wrist"](det, polsi, player_box)

                for bx1, by1, bx2, by2, _c in tenute[:1]:
                    cx, cy = (bx1 + bx2) / 2 / w, (by1 + by2) / 2 / h
                    bw, bh = (bx2 - bx1) / w, (by2 - by1) / h
                    righe.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

                    if anteprime:
                        cv2.rectangle(img, (int(bx1), int(by1)), (int(bx2), int(by2)), (0, 165, 255), 3)

        nome = os.path.splitext(os.path.basename(path))[0]
        with open(os.path.join(LBL_DIR, nome + ".txt"), "w") as f:
            f.write("\n".join(righe))

        if righe:
            con_racchetta += 1
        if anteprime:
            cv2.imwrite(os.path.join(PREVIEW_DIR, nome + ".jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    print(f"{len(immagini)} immagini, racchetta proposta in {con_racchetta} "
          f"({100 * con_racchetta / max(1, len(immagini)):.0f}%)")
    print(f"Etichette in {LBL_DIR}")
    print("Ora vanno CORRETTE a mano (Roboflow o CVAT): aggiungi le racchette mancanti, "
          "sposta i riquadri storti, cancella quelli sulle ombre.")


if __name__ == "__main__":
    main()
