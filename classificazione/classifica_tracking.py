"""
classifica_tracking.py - applica il classificatore dei colpi a un video
gia' analizzato, partendo dal suo <video>_tracking.csv.

    python classificazione/classifica_tracking.py --tracking outputs/<video>_tracking.csv

Produce <video>_colpi.csv con, per ogni frame: classe prevista e quanto il
modello e' sicuro. Stampa anche i tratti continui, che sono la base per il
rilevamento dei colpi veri e propri.

ATTENZIONE: il modello guarda un frame alla volta, quindi dice "in questo
istante la posa somiglia a un dritto", non "qui c'e' stato un colpo".
L'istante dell'impatto lo troveremo incrociando questa informazione con la
traiettoria della pallina.
"""

import argparse
import csv
import os
import sys

import numpy as np
import joblib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from caratteristiche import da_riga_tracking

QUI = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tracking", required=True)
    p.add_argument("--modello", default=os.path.join(QUI, "modello_colpi.joblib"))
    p.add_argument("--min-tratto", type=int, default=5, help="lunghezza minima di un tratto da stampare")
    args = p.parse_args()

    salvato = joblib.load(args.modello)
    modello, classi = salvato["modello"], salvato["classi"]

    righe = list(csv.DictReader(open(args.tracking, newline="")))
    frame, X = [], []
    for r in righe:
        v = da_riga_tracking(r)
        if v is not None:
            frame.append(int(r["frame"]))
            X.append(v)

    if not X:
        print("Nessun frame con giocatore rilevato: niente da classificare.")
        return

    X = np.array(X)
    previsioni = modello.predict(X)
    probabilita = modello.predict_proba(X).max(axis=1)

    uscita = args.tracking.replace("_tracking.csv", "_colpi.csv")
    with open(uscita, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "classe", "sicurezza"])
        for i, c, s in zip(frame, previsioni, probabilita):
            w.writerow([i, classi[c], round(float(s), 3)])

    print(f"{len(X)} frame classificati su {len(righe)} (gli altri senza giocatore rilevato)")
    print("Salvato in", uscita)

    tratti = []
    for i, c in zip(frame, previsioni):
        if tratti and tratti[-1][2] == c and i == tratti[-1][1] + 1:
            tratti[-1][1] = i
        else:
            tratti.append([i, i, c])

    print(f"\nTratti continui di almeno {args.min_tratto} frame:")
    for a, b, c in tratti:
        if b - a + 1 >= args.min_tratto:
            print(f"  frame {a:4d}-{b:4d}  {classi[c]}")


if __name__ == "__main__":
    main()
