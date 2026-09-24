"""
caratteristiche.py - come si trasforma una posa in numeri per il classificatore.

Stessa funzione usata sia sul dataset pubblico (annotazioni COCO) sia sui
nostri video (tracking CSV): se le due parti calcolassero le caratteristiche
in modo diverso, il modello addestrato sull'uno non funzionerebbe sull'altro.

Per ogni frame: 17 keypoint COCO normalizzati rispetto al riquadro del
giocatore (x e y tra 0 e 1, quindi invarianti alla posizione sul campo e
alla distanza dalla camera) piu' un indicatore di visibilita' per punto.
Totale 51 numeri.
"""

import numpy as np

# Ordine COCO, lo stesso di yolo11n-pose. Il dataset pubblico ha un 18esimo
# punto (neck) in fondo, che ignoriamo.
NOMI_COCO = ["nose", "left_eye", "right_eye", "left_ear", "right_ear",
             "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
             "left_wrist", "right_wrist", "left_hip", "right_hip",
             "left_knee", "right_knee", "left_ankle", "right_ankle"]

# Gli stessi punti come si chiamano nelle colonne del nostro tracking CSV.
NOMI_CSV = ["naso", "occhio_sx", "occhio_dx", "orecchio_sx", "orecchio_dx",
            "spalla_sx", "spalla_dx", "gomito_sx", "gomito_dx",
            "polso_sx", "polso_dx", "anca_sx", "anca_dx",
            "ginocchio_sx", "ginocchio_dx", "caviglia_sx", "caviglia_dx"]

# Tutte le classi disponibili nel dataset. Quali usare davvero si sceglie al
# momento dell'addestramento (opzione --classi di addestra_colpi.py): il
# modello salva l'elenco di quelle con cui e' stato addestrato, e il resto
# della pipeline lo legge da li'.
CLASSI = ["dritto", "rovescio", "servizio", "attesa"]


def caratteristiche(nx, ny, visibile):
    return np.concatenate([np.asarray(nx, float), np.asarray(ny, float), np.asarray(visibile, float)])


def da_annotazione_coco(keypoints, bbox):
    """keypoints: lista piatta x,y,v (18 punti); bbox: [x, y, larghezza, altezza]."""

    kp = np.asarray(keypoints, float).reshape(-1, 3)[:17]
    x0, y0, w, h = bbox
    if w <= 0 or h <= 0:
        return None
    return caratteristiche((kp[:, 0] - x0) / w, (kp[:, 1] - y0) / h, kp[:, 2] > 0)


def da_riga_tracking(riga, conf_minima=0.3):
    """riga: un dizionario letto dal nostro <video>_tracking.csv."""

    try:
        nx = [float(riga[f"{n}_nx"]) for n in NOMI_CSV]
        ny = [float(riga[f"{n}_ny"]) for n in NOMI_CSV]
        vis = [float(riga[f"{n}_conf"]) > conf_minima for n in NOMI_CSV]
    except (ValueError, KeyError):
        return None  # frame senza giocatore rilevato
    return caratteristiche(nx, ny, vis)
