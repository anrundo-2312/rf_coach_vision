"""
disegna_velocita.py - riscrive il video con, per ogni colpo del giocatore,
tipo di colpo, velocita' di uscita in km/h e direzione, piu' una piccola
mappa del campo vista dall'alto con da dove parte il colpo e dove va.

    python velocita/disegna_velocita.py --video inputs/<video>.mp4

Legge outputs/dati/<video>_velocita_punti.json (velocita_uscita.py) e scrive
outputs/video/<video>_velocita.mp4 in H.264, cosi' si vede anche nel browser.
Il video di partenza e' quello originale: niente px/s.
"""

import argparse
import json
import os
import subprocess

import cv2
import numpy as np

DURATA_S = 1.7                 # quanto resta la scritta dopo il contatto
LARGHEZZA_MAX = 1920
COLORI = {"dritto": (60, 200, 60), "rovescio": (255, 170, 60), "servizio": (0, 200, 255)}
F = cv2.FONT_HERSHEY_SIMPLEX


def etichetta(fr, righe, colore):
    """righe: il nome del colpo, poi le righe principali; l'ultima (nota) in piccolo e grigio."""
    x0, y0 = 30, 30
    stili = [(1.5, 3)] + [(2.0 if i == 0 else 1.1, 5 if i == 0 else 3) for i in range(len(righe) - 2)] + [(0.8, 2)]
    dims = [cv2.getTextSize(t, F, s, k)[0] for t, (s, k) in zip(righe, stili)]
    W = max(d[0] for d in dims) + 40
    H = sum(d[1] for d in dims) + 22 * len(dims) + 20
    ov = fr.copy()
    cv2.rectangle(ov, (x0, y0), (x0 + W, y0 + H), (0, 0, 0), -1)
    fr[:] = cv2.addWeighted(ov, 0.6, fr, 0.4, 0)
    cv2.rectangle(fr, (x0, y0), (x0 + 10, y0 + H), colore, -1)
    y = y0 + 10
    for i, (t, (s, k), d) in enumerate(zip(righe, stili, dims)):
        y += d[1] + 22
        cv2.putText(fr, t, (x0 + 25, y), F, s, (200, 200, 200) if i == len(righe) - 1 else (255, 255, 255), k, cv2.LINE_AA)


def mappa(fr, colpo):
    """Campo visto dall'alto (lato del giocatore in basso) con partenza e freccia verso l'arrivo."""
    m = 11                                     # pixel per metro
    w, h = int(13 * m), int(30.5 * m)          # da 5 m dietro il fondo vicino a 1,7 m oltre quello lontano
    img = np.full((h, w, 3), 35, np.uint8)
    px = lambda x, y: (int((x + 1) * m), int(h - (y + 5.0) * m))
    bianco = (230, 230, 230)
    for a, b in [((0, 0), (0, 23.77)), ((10.97, 0), (10.97, 23.77)), ((1.37, 0), (1.37, 23.77)),
                 ((9.60, 0), (9.60, 23.77)), ((0, 0), (10.97, 0)), ((0, 23.77), (10.97, 23.77)),
                 ((1.37, 5.485), (9.60, 5.485)), ((1.37, 18.285), (9.60, 18.285)), ((5.485, 5.485), (5.485, 18.285))]:
        cv2.line(img, px(*a), px(*b), bianco, 1, cv2.LINE_AA)
    cv2.line(img, px(-0.9, 11.885), px(11.9, 11.885), (0, 200, 255), 2)
    # fascia "centrale" nel campo avversario
    ov = img.copy()
    cv2.rectangle(ov, px(5.485 - 1.0, 23.77), px(5.485 + 1.0, 11.885), (120, 120, 120), -1)
    img = cv2.addWeighted(ov, 0.35, img, 0.65, 0)
    xs, ys = colpo["contatto_x_m"], colpo["contatto_y_m"]
    xa, ya = colpo["arrivo_x_m"], 21.0
    col = COLORI.get(colpo["colpo"], (255, 255, 255))
    cv2.circle(img, px(xs, ys), 5, col, -1, cv2.LINE_AA)
    cv2.arrowedLine(img, px(xs, ys), px(xa, ya), col, 2, cv2.LINE_AA, tipLength=0.08)
    H, W = fr.shape[:2]
    s = H / 1080
    img = cv2.resize(img, None, fx=s, fy=s)
    y0, x0 = H - img.shape[0] - int(20 * s), int(20 * s)
    fr[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--dati", default="outputs/dati")
    ap.add_argument("--out")
    a = ap.parse_args()
    nome = os.path.splitext(os.path.basename(a.video))[0]
    colpi = json.load(open(os.path.join(a.dati, nome + "_velocita_punti.json")))
    uscita = a.out or os.path.join(os.path.dirname(a.dati.rstrip("/")) or ".", "video", nome + "_velocita.mp4")
    os.makedirs(os.path.dirname(uscita), exist_ok=True)

    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    W, H = int(cap.get(3)), int(cap.get(4))
    s = min(1.0, LARGHEZZA_MAX / W)
    size = (int(W * s) // 2 * 2, int(H * s) // 2 * 2)
    tmp = uscita + ".tmp.mp4"
    out = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    durata = int(DURATA_S * fps)
    n = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        n += 1
        attivi = [c for c in colpi if c["frame"] < n <= c["frame"] + durata]
        for c in attivi:
            for f, x, y in c.get("_punti", []):
                if f <= n:
                    cv2.circle(fr, (int(x), int(y)), max(4, int(8 / s)), (0, 230, 255), max(2, int(2 / s)), cv2.LINE_AA)
        fr = cv2.resize(fr, size, interpolation=cv2.INTER_AREA)
        for c in attivi:
            colore = COLORI.get(c["colpo"], (200, 200, 200))
            if c.get("velocita_uscita_kmh", "") != "":
                righe = [c["colpo"].upper(), f"uscita {c['velocita_uscita_kmh']} km/h"]
                if c.get("direzione"):
                    righe.append(c["direzione"])
                righe.append("margine circa +-20 km/h")
                etichetta(fr, righe, colore)
                if c.get("direzione"):
                    mappa(fr, c)
            else:
                etichetta(fr, [c["colpo"].upper(), "km/h non disponibile", "pallina coperta dal giocatore"], (150, 150, 150))
        out.write(fr)
    out.release()
    # H.264 (si vede anche nel browser e su Colab) se c'e' ffmpeg; altrimenti resta mp4v,
    # che si apre comunque con il lettore del PC.
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "23", uscita], check=True)
        os.remove(tmp)
    except (FileNotFoundError, subprocess.CalledProcessError):
        os.replace(tmp, uscita)
        print("ffmpeg non disponibile: video salvato in mp4v (si apre con il lettore del PC, non nel browser).")
    print(f"{n} frame scritti in {uscita}")


if __name__ == "__main__":
    main()
