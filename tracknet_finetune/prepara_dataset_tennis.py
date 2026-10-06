"""
prepara_dataset_tennis.py - converte il dataset pubblico del tennis del primo
TrackNet (2019, riprese TV 1280x720 a 30 fps) nel formato che vuole lo script
di addestramento di TrackNetV3, prendendone solo una parte.

    python tracknet_finetune/prepara_dataset_tennis.py --origine /content/tennis_raw \
        --uscita /content/dati_tennis --max_frame 10000 --val_partite 9,10

Il dataset originale e' fatto cosi' (link nel LEGGIMI di questa cartella):

    game1/Clip1/0000.jpg ... game1/Clip1/Label.csv
    ...
    game10/ClipN/...

Label.csv ha le colonne "file name", "visibility", "x-coordinate", "y-coordinate",
"status". Visibilita' (articolo di TrackNet): 0 = pallina fuori dall'immagine,
1 = ben visibile, 2 = visibile ma difficile (tipicamente MOSSA), 3 = coperta.
Qui 1 e 2 diventano "visibile" (2 e' proprio la pallina a striscia che vogliamo
insegnare), 0 e 3 "non visibile" (come nelle nostre etichette: coperta = non
visibile).

Uscita, nel formato di TrackNetV3 (README di qaz812345/TrackNetV3):

    <uscita>/train/match<partita>/frame/<clip>/0.png 1.png ... median.npz
    <uscita>/train/match<partita>/csv/<clip>_ball.csv     Frame,Visibility,X,Y,Mossa
    <uscita>/val/match<partita>/...

I fotogrammi vengono salvati GIA' a 512x288, la dimensione d'ingresso di
TrackNet: occupano ~10 volte meno spazio e non cambia niente per la rete, che
comunque riduce ogni fotogramma a 512x288. Per lo stesso motivo X e Y sono
scritte in pixel 512x288. Lo sfondo (median.npz) e' la mediana dei fotogrammi
della clip: niente mediana della partita, perche' nelle riprese TV
l'inquadratura cambia da una clip all'altra.

La divisione e' PER PARTITA (non per fotogramma): le partite di --val_partite
vanno solo nella validazione, le altre solo nell'addestramento. Due fotogrammi
vicini della stessa clip sono quasi identici: mescolarli renderebbe la
validazione troppo ottimista.
"""

import argparse
import glob
import json
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pandas as pd

LARGHEZZA, ALTEZZA = 512, 288          # ingresso di TrackNet (utils/general.py: WIDTH, HEIGHT)
VISIBILI = {1, 2}                      # 2 = visibile ma difficile (mossa): la vogliamo
MOSSA = 2


# ------------------------------------------------------------------ lettura
def trova_clip(origine):
    """[(partita, nome_clip, cartella)] per ogni Label.csv sotto origine."""
    clip = []
    for etichette in glob.glob(os.path.join(origine, "**", "Label.csv"), recursive=True):
        cartella = os.path.dirname(etichette)
        nome_clip = os.path.basename(cartella)
        m = re.search(r"game\s*(\d+)", os.path.relpath(cartella, origine), re.IGNORECASE)
        if not m:
            print(f"[salto] non capisco la partita di {cartella}")
            continue
        clip.append((int(m.group(1)), nome_clip, cartella))
    return sorted(clip)


def colonna(df, *nomi):
    """Trova una colonna anche con maiuscole/spazi diversi ('file name', 'File Name', 'file_name')."""
    norm = {re.sub(r"[\s_\-]", "", c.lower()): c for c in df.columns}
    for n in nomi:
        k = re.sub(r"[\s_\-]", "", n.lower())
        if k in norm:
            return norm[k]
    raise KeyError(f"nessuna colonna tra {nomi} in {list(df.columns)}")


def leggi_etichette(cartella):
    """DataFrame ordinato: file, vis (0-3), x, y in pixel dell'immagine originale."""
    df = pd.read_csv(os.path.join(cartella, "Label.csv"))
    c_file = colonna(df, "file name", "filename", "file")
    c_vis = colonna(df, "visibility", "visibility class")
    c_x = colonna(df, "x-coordinate", "x")
    c_y = colonna(df, "y-coordinate", "y")
    out = pd.DataFrame({"file": df[c_file].astype(str),
                        "vis": pd.to_numeric(df[c_vis], errors="coerce").fillna(0).astype(int),
                        "x": pd.to_numeric(df[c_x], errors="coerce"),
                        "y": pd.to_numeric(df[c_y], errors="coerce")})
    out = out[out["file"].apply(lambda f: os.path.exists(os.path.join(cartella, f)))]
    return out.sort_values("file").reset_index(drop=True)


# ------------------------------------------------------------------ scelta
def scegli(clip, val_partite, max_frame, max_val, seme):
    """Divide le clip per partita e ne prende fino a max_frame (train) e max_val (val) fotogrammi."""
    rnd = random.Random(seme)
    train = [c for c in clip if c[0] not in val_partite]
    val = [c for c in clip if c[0] in val_partite]
    rnd.shuffle(train)
    rnd.shuffle(val)

    def prendi(lista, limite):
        scelte, tot = [], 0
        for c in lista:
            if limite and tot >= limite:
                break
            n = len(leggi_etichette(c[2]))
            if n < 16:                       # troppo corta per sequenze da 8 + scorrimento
                continue
            scelte.append(c)
            tot += n
        return scelte, tot

    return prendi(train, max_frame), prendi(val, max_val)


# ------------------------------------------------------------------ scrittura
def converti_clip(partita, nome_clip, cartella, uscita, split, thread=16):
    et = leggi_etichette(cartella)
    dir_match = os.path.join(uscita, split, f"match{partita}")
    dir_frame = os.path.join(dir_match, "frame", nome_clip)
    dir_csv = os.path.join(dir_match, "csv")
    os.makedirs(dir_frame, exist_ok=True)
    os.makedirs(dir_csv, exist_ok=True)

    def leggi(nome):
        img = cv2.imread(os.path.join(cartella, nome))
        if img is None:
            raise SystemExit(f"Non riesco a leggere {os.path.join(cartella, nome)}")
        return img.shape[:2], cv2.resize(img, (LARGHEZZA, ALTEZZA), interpolation=cv2.INTER_AREA)

    # letture in parallelo: dal Drive montato su Colab ogni file e' lento da aprire
    with ThreadPoolExecutor(max_workers=thread) as pool:
        lette = list(pool.map(leggi, et["file"]))

    righe, fotogrammi = [], []
    for i, r in et.iterrows():
        (h, w), piccola = lette[i]
        cv2.imwrite(os.path.join(dir_frame, f"{i}.png"), piccola)
        fotogrammi.append(piccola)
        vis = int(r["vis"]) in VISIBILI and np.isfinite(r["x"]) and np.isfinite(r["y"])
        # TrackNetV3 costruisce una heatmap vuota solo se X == Y == 0: per le pallina
        # non visibili le coordinate DEVONO essere 0.
        x = round(float(r["x"]) * LARGHEZZA / w, 2) if vis else 0.0
        y = round(float(r["y"]) * ALTEZZA / h, 2) if vis else 0.0
        righe.append({"Frame": i, "Visibility": int(vis), "X": x, "Y": y,
                      "Mossa": int(vis and int(r["vis"]) == MOSSA)})

    pd.DataFrame(righe).to_csv(os.path.join(dir_csv, f"{nome_clip}_ball.csv"), index=False)
    # sfondo: mediana della clip, RGB, senza perdita (come utils.general.generate_data_frames)
    mediana = np.median(np.stack(fotogrammi), 0)[..., ::-1]
    np.savez(os.path.join(dir_frame, "median.npz"), median=mediana)
    vis = sum(r["Visibility"] for r in righe)
    mossa = sum(r["Mossa"] for r in righe)
    return len(righe), vis, mossa


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--origine", required=True, help="cartella del dataset scompattato (game1, game2, ...)")
    p.add_argument("--uscita", required=True, help="cartella da creare (non deve esistere o deve essere vuota)")
    p.add_argument("--max_frame", type=int, default=10000, help="fotogrammi di addestramento (circa; 0 = tutti)")
    p.add_argument("--val_partite", default="9,10", help="partite tenute per la validazione, es. 9,10")
    p.add_argument("--max_val", type=int, default=2000, help="fotogrammi di validazione (circa; 0 = tutti)")
    p.add_argument("--seme", type=int, default=13)
    p.add_argument("--thread", type=int, default=16, help="letture in parallelo (utile se --origine e' sul Drive)")
    a = p.parse_args()

    if os.path.isdir(a.uscita) and os.listdir(a.uscita):
        raise SystemExit(f"{a.uscita} esiste e non e' vuota: usa una cartella nuova "
                         "(TrackNetV3 tiene dei file di cache che non vanno mescolati).")
    clip = trova_clip(a.origine)
    if not clip:
        raise SystemExit(f"Nessun Label.csv sotto {a.origine}: il dataset e' scompattato li'?")
    val_partite = {int(v) for v in a.val_partite.split(",") if v.strip()}
    partite = sorted({c[0] for c in clip})
    print(f"Trovate {len(clip)} clip in {len(partite)} partite: {partite}")
    if not val_partite & set(partite):
        raise SystemExit(f"Nessuna delle partite di validazione {sorted(val_partite)} c'e' nel dataset.")

    (train, n_train), (val, n_val) = scegli(clip, val_partite, a.max_frame, a.max_val, a.seme)
    print(f"Scelte: addestramento {len(train)} clip (~{n_train} fotogrammi), "
          f"validazione {len(val)} clip (~{n_val} fotogrammi)")

    riepilogo = {"origine": a.origine, "max_frame": a.max_frame, "val_partite": sorted(val_partite),
                 "seme": a.seme, "dimensione": [LARGHEZZA, ALTEZZA], "split": {}}
    for split, lista in (("train", train), ("val", val)):
        tot = vis = mossa = 0
        for k, (partita, nome_clip, cartella) in enumerate(lista, 1):
            n, v, m = converti_clip(partita, nome_clip, cartella, a.uscita, split, a.thread)
            tot, vis, mossa = tot + n, vis + v, mossa + m
            print(f"  [{split} {k}/{len(lista)}] partita {partita} {nome_clip}: {n} fotogrammi, "
                  f"pallina visibile {v}, mossa {m}")
            sys.stdout.flush()
        riepilogo["split"][split] = {"clip": [f"game{p}/{c}" for p, c, _ in lista], "fotogrammi": tot,
                                     "visibili": vis, "mosse": mossa}
        print(f"{split}: {tot} fotogrammi, pallina visibile nel {100 * vis / max(tot, 1):.0f}%, "
              f"mossa nel {100 * mossa / max(vis, 1):.0f}% dei visibili")

    with open(os.path.join(a.uscita, "riepilogo_dataset.json"), "w") as f:
        json.dump(riepilogo, f, indent=1)
    print(f"Fatto: {a.uscita}")


if __name__ == "__main__":
    main()
