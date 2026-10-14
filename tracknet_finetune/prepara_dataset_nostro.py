"""
prepara_dataset_nostro.py - converte le NOSTRE etichette (fatte con
etichetta_pallina.py sui tratti di scegli_tratti_addestramento.py) nel formato
che vuole lo script di addestramento di TrackNetV3, lo stesso prodotto da
prepara_dataset_tennis.py per il dataset pubblico. Gira sul PC (solo CPU).

    python tracknet_finetune/prepara_dataset_nostro.py
    python tracknet_finetune/prepara_dataset_nostro.py --cartella "G:\Il mio Drive\rf_coach_vision\tracknet_finetune\addestramento"

--cartella puo' essere una cartella con lista_frame.csv oppure una cartella che
contiene le cartelle dei singoli video (scegli_tratti_addestramento.py
--per_video): in quel caso le prende tutte. Si possono dare piu' cartelle.
Per ognuna legge lista_frame.csv (i tratti), il CSV delle etichette
(etichette_<nome cartella>.csv, se no etichette_addestramento.csv) e le
immagini in fotogrammi/. Ogni TRATTO diventa una clip:

    <uscita>/train/match<k>/frame/<tratto>/0.png 1.png ... median.npz
    <uscita>/train/match<k>/csv/<tratto>_ball.csv      Frame,Visibility,X,Y,Mossa
    <uscita>/val/...

(un "match" per video; fotogrammi gia' a 512x288 e coordinate in quei pixel,
come per il dataset TV; sfondo = mediana della clip).

Regole:
  - una clip deve essere CONTINUA e tutta etichettata con "visibile" (1) o "non
    visibile" (0). Un fotogramma non etichettato o "incerto" (-1) spezza il
    tratto in due; i pezzi piu' corti di 16 fotogrammi vengono scartati;
  - divisione per TRATTO, non per fotogramma: un tratto ogni --val_ogni va nella
    validazione (il primo di ogni video sempre nell'addestramento), gli altri
    nell'addestramento. Per vedere fotogrammi vicini in entrambi non ci sono
    rischi di validazione ottimista: sono tratti diversi;
  - i video del set di test non possono entrare (lo controlla gia'
    scegli_tratti_addestramento.py; qui si ricontrolla).

Alla fine il dataset viene impacchettato in un tar nella cartella temporanea
del sistema e copiato su Drive in rf_coach_vision/tracknet_finetune/<nome>.tar
(il tar NON resta nel progetto: pesa troppo per GitHub). Su Colab la cella 6b
del notebook lo scompatta e la cella 8 lo usa con DATI_RUN = DATI_NOSTRI.
"""

import argparse
import json
import os
import shutil
import sys
import tarfile
import tempfile

import cv2
import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, RADICE)

LARGHEZZA, ALTEZZA = 512, 288          # ingresso di TrackNet, come prepara_dataset_tennis.py
MIN_FOTOGRAMMI = 16                    # 8 di sequenza + scorrimento
VIDEO_TEST = {"nicola_matarese_trim", "zverev_djokovic_trim_swin_like", "alcaraz"}


def pezzi_continui(df):
    """Spezza un tratto (righe ordinate per frame) nei pezzi continui etichettati 0/1."""
    pezzi, corrente = [], []
    atteso = None
    for _, r in df.iterrows():
        ok = r["visibile"] in (0, 1) and (atteso is None or int(r["frame"]) == atteso)
        if ok:
            corrente.append(r)
        else:
            if len(corrente) >= MIN_FOTOGRAMMI:
                pezzi.append(corrente)
            corrente = [r] if r["visibile"] in (0, 1) else []
        atteso = int(r["frame"]) + 1
    if len(corrente) >= MIN_FOTOGRAMMI:
        pezzi.append(corrente)
    return pezzi


def trova_cartelle(radici):
    """Cartelle con lista_frame.csv: le radici stesse, o le loro sottocartelle dirette."""
    out = []
    for r in radici:
        if os.path.exists(os.path.join(r, "lista_frame.csv")):
            out.append(r)
        elif os.path.isdir(r):
            out += sorted(os.path.join(r, d) for d in os.listdir(r)
                          if os.path.exists(os.path.join(r, d, "lista_frame.csv")))
    return out


def file_etichette(cartella):
    """etichette_<nome cartella>.csv (come etichetta_pallina.py), se no etichette_addestramento.csv."""
    for nome in (f"etichette_{os.path.basename(os.path.normpath(cartella))}.csv", "etichette_addestramento.csv"):
        p = os.path.join(cartella, nome)
        if os.path.exists(p):
            return p
    return None


def converti_clip(nome_clip, righe, cartella_img, stem, uscita, split, match):
    dir_match = os.path.join(uscita, split, f"match{match}")
    dir_frame = os.path.join(dir_match, "frame", nome_clip)
    dir_csv = os.path.join(dir_match, "csv")
    os.makedirs(dir_frame, exist_ok=True)
    os.makedirs(dir_csv, exist_ok=True)
    out, piccole = [], []
    for i, r in enumerate(righe):
        p_img = os.path.join(cartella_img, stem, f"{int(r['frame']):06d}.jpg")
        img = cv2.imread(p_img)
        if img is None:
            raise SystemExit(f"Manca l'immagine {p_img}: rilancia scegli_tratti_addestramento.py")
        h, w = img.shape[:2]
        piccola = cv2.resize(img, (LARGHEZZA, ALTEZZA), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(dir_frame, f"{i}.png"), piccola)
        piccole.append(piccola)
        vis = int(r["visibile"]) == 1 and pd.notna(r["x"]) and pd.notna(r["y"])
        # TrackNetV3 fa una heatmap vuota solo se X == Y == 0
        x = round(float(r["x"]) * LARGHEZZA / w, 2) if vis else 0.0
        y = round(float(r["y"]) * ALTEZZA / h, 2) if vis else 0.0
        mossa = int(r["mossa"]) if ("mossa" in r and pd.notna(r["mossa"])) else 0
        out.append({"Frame": i, "Visibility": int(vis), "X": x, "Y": y, "Mossa": int(vis and mossa == 1)})
    pd.DataFrame(out).to_csv(os.path.join(dir_csv, f"{nome_clip}_ball.csv"), index=False)
    mediana = np.median(np.stack(piccole), 0)[..., ::-1]           # RGB, come utils.general.generate_data_frames
    np.savez(os.path.join(dir_frame, "median.npz"), median=mediana)
    return len(out), sum(r["Visibility"] for r in out), sum(r["Mossa"] for r in out)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--cartella", nargs="+", default=[os.path.join(QUI, "addestramento")],
                   help="cartelle con lista_frame.csv, o cartelle che contengono quelle dei singoli video")
    p.add_argument("--etichette", default=None,
                   help="solo con UNA cartella: CSV delle etichette (default: etichette_<nome cartella>.csv)")
    p.add_argument("--uscita", default=os.path.join(QUI, "dati_nostri"),
                   help="cartella del dataset (viene svuotata e rifatta)")
    p.add_argument("--val_ogni", type=int, default=4, help="un tratto ogni N va nella validazione")
    p.add_argument("--max_spostamento", type=float, default=12.0,
                   help="px a 1080p: tratti con la camera che si muove piu' di cosi' vengono scartati")
    p.add_argument("--tieni_mossi", action="store_true", help="tieni anche i tratti con la camera che si muove")
    p.add_argument("--nome_tar", default="dati_nostri.tar")
    p.add_argument("--senza_drive", action="store_true", help="non copiare il tar su Drive")
    a = p.parse_args()

    cartelle = trova_cartelle(a.cartella)
    if not cartelle:
        raise SystemExit(f"Nessuna lista_frame.csv in {a.cartella} (ne' nelle loro sottocartelle).")
    if a.etichette and len(cartelle) > 1:
        raise SystemExit("--etichette vale solo con una cartella.")
    parti = []
    for c in cartelle:
        lista = pd.read_csv(os.path.join(c, "lista_frame.csv"))
        if "tratto" not in lista.columns:
            raise SystemExit(f"{c}: lista_frame.csv senza la colonna 'tratto': non e' una lista di addestramento.")
        if "spostamento_px" not in lista.columns:
            lista["spostamento_px"] = np.nan
        p_et = a.etichette or file_etichette(c)
        if p_et and os.path.exists(p_et):
            et = pd.read_csv(p_et)[["video", "frame", "visibile", "x", "y", "mossa"]]
        else:
            print(f"  {c}: nessuna etichetta ancora")
            et = pd.DataFrame(columns=["video", "frame", "visibile", "x", "y", "mossa"])
        d = lista[["video", "frame", "tratto", "spostamento_px"]].merge(et, on=["video", "frame"], how="left")
        d["cartella"] = c
        fatti = d["visibile"].notna().sum()
        print(f"  {c}: {len(d)} fotogrammi, {fatti} etichettati")
        parti.append(d)
    df = pd.concat(parti, ignore_index=True)
    doppi = df.groupby("video")["cartella"].nunique()
    if (doppi > 1).any():
        raise SystemExit(f"Lo stesso video e' in piu' cartelle: {list(doppi[doppi > 1].index)}")
    df["visibile"] = pd.to_numeric(df["visibile"], errors="coerce").fillna(-2).astype(int)  # -2 = non etichettato
    for v in df["video"].unique():
        if os.path.splitext(v)[0] in VIDEO_TEST:
            raise SystemExit(f"{v} e' nel set di test: non puo' entrare nell'addestramento.")

    if os.path.isdir(a.uscita):
        shutil.rmtree(a.uscita)
    os.makedirs(a.uscita)

    riepilogo = {"origine": cartelle, "val_ogni": a.val_ogni, "dimensione": [LARGHEZZA, ALTEZZA],
                 "split": {"train": {"clip": [], "fotogrammi": 0, "visibili": 0, "mosse": 0},
                           "val": {"clip": [], "fotogrammi": 0, "visibili": 0, "mosse": 0}},
                 "scartati": {"fotogrammi_non_etichettati": int((df["visibile"] == -2).sum()),
                              "fotogrammi_incerti": int((df["visibile"] == -1).sum()), "pezzi_corti": 0,
                              "tratti_camera_mossa": 0}}
    video = list(dict.fromkeys(df["video"]))                       # ordine di apparizione
    for match, v in enumerate(video, 1):
        stem = os.path.splitext(v)[0]
        tratti = list(dict.fromkeys(df[df["video"] == v]["tratto"]))
        k_clip = 0
        for tid in tratti:
            t = df[(df["video"] == v) & (df["tratto"] == tid)].sort_values("frame")
            sp = pd.to_numeric(t["spostamento_px"], errors="coerce").max()
            if not a.tieni_mossi and pd.notna(sp) and sp > a.max_spostamento:
                riepilogo["scartati"]["tratti_camera_mossa"] += 1
                print(f"  [scarto] {v} {tid}: camera mossa di {sp:.0f} px")
                continue
            pezzi = pezzi_continui(t)
            n_buoni = sum(1 for r in t.itertuples() if r.visibile in (0, 1))
            if not pezzi:
                if n_buoni:
                    riepilogo["scartati"]["pezzi_corti"] += n_buoni
                continue
            riepilogo["scartati"]["pezzi_corti"] += n_buoni - sum(len(pz) for pz in pezzi)
            for j, pz in enumerate(pezzi):
                nome_clip = tid if len(pezzi) == 1 else f"{tid}_{j}"
                split = "val" if (k_clip % a.val_ogni == a.val_ogni - 1) else "train"
                k_clip += 1
                n, vis, mossa = converti_clip(nome_clip, pz, os.path.join(t["cartella"].iloc[0], "fotogrammi"),
                                              stem, a.uscita, split, match)
                s = riepilogo["split"][split]
                s["clip"].append(f"{v}/{nome_clip}")
                s["fotogrammi"] += n
                s["visibili"] += vis
                s["mosse"] += mossa
                print(f"  [{split}] {v} {nome_clip}: {n} fotogrammi, pallina visibile {vis}, mossa {mossa}")
    for split in ("train", "val"):
        s = riepilogo["split"][split]
        print(f"{split}: {len(s['clip'])} clip, {s['fotogrammi']} fotogrammi, pallina visibile nel "
              f"{100 * s['visibili'] / max(s['fotogrammi'], 1):.0f}%, mossa nel "
              f"{100 * s['mosse'] / max(s['visibili'], 1):.0f}% dei visibili")
    sc = riepilogo["scartati"]
    print(f"scartati: {sc['fotogrammi_non_etichettati']} non etichettati, {sc['fotogrammi_incerti']} incerti, "
          f"{sc['pezzi_corti']} in pezzi troppo corti, {sc['tratti_camera_mossa']} tratti con la camera mossa")
    if not riepilogo["split"]["train"]["clip"]:
        raise SystemExit("Nessuna clip di addestramento: etichetta i tratti (tutti i fotogrammi, 0 o 1).")
    if not riepilogo["split"]["val"]["clip"]:
        print("ATTENZIONE: nessuna clip di validazione (pochi tratti): addestra.py non potra' scegliere l'epoca. "
              "Etichetta almeno un altro tratto o abbassa --val_ogni.")
    with open(os.path.join(a.uscita, "riepilogo_dataset.json"), "w") as f:
        json.dump(riepilogo, f, indent=1)

    # tar fuori dal progetto (non deve finire su GitHub), poi su Drive
    p_tar = os.path.join(tempfile.gettempdir(), a.nome_tar)
    with tarfile.open(p_tar, "w") as tar:
        tar.add(a.uscita, arcname=os.path.basename(os.path.normpath(a.uscita)))
    print(f"Dataset: {a.uscita}  ({os.path.getsize(p_tar) / 1e6:.0f} MB nel tar {p_tar})")
    if not a.senza_drive:
        try:
            import sincronizza_drive
            if sincronizza_drive.CARTELLA_DRIVE and os.path.isdir(sincronizza_drive.CARTELLA_DRIVE):
                sincronizza_drive.copia(p_tar, "tracknet_finetune")
                print(f"Copiato su Drive: {os.path.join(sincronizza_drive.CARTELLA_DRIVE, 'tracknet_finetune', a.nome_tar)}")
                os.remove(p_tar)
            else:
                print("Drive non trovato: copia il tar a mano in rf_coach_vision/tracknet_finetune/ su Drive.")
        except Exception as e:                                        # Drive non deve bloccare
            print(f"Copia su Drive non riuscita ({e}): copia il tar a mano in tracknet_finetune/ su Drive.")


if __name__ == "__main__":
    main()
