"""
addestra_colpi.py - addestra il classificatore dei colpi sulle pose del
dataset pubblico "Tennis Player Actions Dataset" (2000 immagini, camera
dietro il giocatore, 4 classi: dritto, rovescio, servizio, attesa).

Usa SOLO i file JSON delle annotazioni: i keypoint sono gia' li' dentro,
le immagini non servono. Quindi gira in pochi secondi anche senza GPU.

    python classificazione/addestra_colpi.py --annotazioni <cartella_annotations>

Validazione: i frame vicini nello stesso video si somigliano moltissimo.
Divisi a caso finirebbero mezzi in addestramento e mezzi in verifica, e il
punteggio sarebbe gonfiato. Qui si dividono a blocchi di 25 immagini
consecutive, tenendo interi i blocchi (GroupKFold).
"""

import argparse
import json
import os
import re
import sys

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import GroupKFold, cross_val_predict
import joblib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from caratteristiche import CLASSI, da_annotazione_coco

FILE_CLASSI = {"dritto": "forehand", "rovescio": "backhand",
               "servizio": "serve", "attesa": "ready_position"}


def carica(cartella):
    X, y, gruppi = [], [], []
    for classe, nome_file in FILE_CLASSI.items():
        percorso = os.path.join(cartella, f"{nome_file}.json")
        dati = json.load(open(percorso))
        immagini = {i["id"]: i for i in dati["images"]}
        for a in dati["annotations"]:
            v = da_annotazione_coco(a["keypoints"], a["bbox"])
            if v is None:
                continue
            X.append(v)
            y.append(CLASSI.index(classe))
            numero = int(re.findall(r"(\d+)", immagini[a["image_id"]]["file_name"])[-1])
            gruppi.append(f"{classe}_{numero // 25}")
    return np.array(X), np.array(y), np.array(gruppi)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--annotazioni", required=True, help="cartella con forehand.json, backhand.json, ...")
    p.add_argument("--modello", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "modello_colpi.joblib"))
    args = p.parse_args()

    X, y, gruppi = carica(args.annotazioni)
    print(f"{len(X)} esempi, {X.shape[1]} caratteristiche, classi: "
          + ", ".join(f"{CLASSI[i]}={n}" for i, n in enumerate(np.bincount(y))))

    modello = HistGradientBoostingClassifier(random_state=0)
    previsioni = cross_val_predict(modello, X, y, cv=GroupKFold(n_splits=5), groups=gruppi)

    print(f"\nAccuratezza in validazione: {accuracy_score(y, previsioni):.3f}\n")
    print(classification_report(y, previsioni, target_names=CLASSI, digits=3))
    print("Matrice di confusione (righe = vero, colonne = previsto):")
    print("             " + " ".join(f"{c:>9s}" for c in CLASSI))
    for i, riga in enumerate(confusion_matrix(y, previsioni)):
        print(f"{CLASSI[i]:>12s} " + " ".join(f"{v:9d}" for v in riga))

    modello.fit(X, y)
    joblib.dump({"modello": modello, "classi": CLASSI}, args.modello)
    print(f"\nModello salvato in {args.modello}")
