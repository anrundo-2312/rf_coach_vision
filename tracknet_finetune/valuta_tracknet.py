"""
valuta_tracknet.py - il "voto" di TrackNet sul set di test etichettato a mano:
confronta pesi diversi (per esempio quelli del badminton e quelli nuovi) sugli
stessi fotogrammi.

    python tracknet_finetune/valuta_tracknet.py \
        --etichette tracknet_finetune/test/etichette_test.csv --video_dir inputs \
        --pesi badminton=tracknet3/ckpts/TrackNet_best.pt tennis=/content/ft/TrackNet_tennis.pt \
        --uscita /content/valutazione

Per ogni video del set di test e per ogni file di pesi lancia la previsione di
TrackNet ESATTAMENTE come la fa il programma (tracknet3/predict.py, modalita'
"weight", senza InpaintNet: si misura TrackNet da solo) e confronta la
posizione con l'etichetta, fotogramma per fotogramma. I video lunghi (ex.mp4)
vengono prima tagliati attorno ai fotogrammi etichettati, con ffmpeg e senza
perdere la numerazione dei fotogrammi.

Esiti (come nella valutazione di TrackNetV3):
    TP   pallina visibile, TrackNet la trova entro la tolleranza
    FP1  pallina visibile, TrackNet indica un punto lontano (altra cosa)
    FN   pallina visibile, TrackNet non indica niente
    FP2  pallina NON visibile, TrackNet indica qualcosa (riga, pallina ferma, ...)
    TN   pallina non visibile e TrackNet non indica niente
La tolleranza e' in pixel riportati a 1080p (--tolleranza 15 = circa i 4 px a
512x288 usati da TrackNetV3); si riporta anche il richiamo a 8 px e l'errore
mediano dei TP (quanto e' precisa la posizione quando la trova).
Le etichette "incerta" (visibile = -1) non contano.

Le previsioni restano in --uscita/previsioni/<nome>/ e si riusano alla volta
dopo (la previsione di ex.mp4 dura minuti): se il file dei pesi con quel nome
cambia, vengono rifatte da sole.

Gruppi: tutti; vicino al colpo (entro 0,1 s); pallina mossa (segnata con M);
fotogrammi a caso (lontano dai colpi); ogni video.
Uscite in --uscita: confronto_<nome>.csv (fotogramma per fotogramma),
voto.md e voto.json (tabelle riassuntive).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
TRACKNET_DIR = os.path.join(RADICE, "tracknet3")
VIDEO_CORTO = 3000          # fotogrammi: sotto si usa il video intero


def info_video(percorso):
    cap = cv2.VideoCapture(percorso)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return fps, n, w, h


def ritaglio(percorso, primo, ultimo, cartella):
    """Video con i soli fotogrammi primo..ultimo (numerati da 0), scelti per NUMERO di fotogramma
    decodificato (filtro select di ffmpeg): stessa numerazione di una lettura in fila."""
    os.makedirs(cartella, exist_ok=True)
    stem = os.path.splitext(os.path.basename(percorso))[0]
    out = os.path.join(cartella, f"{stem}_{primo}_{ultimo}.mp4")
    if os.path.exists(out):
        return out
    if shutil.which("ffmpeg") is None:
        raise SystemExit("Serve ffmpeg per tagliare i video lunghi (su Colab c'e').")
    filtro = f"select='between(n,{primo},{ultimo})',setpts=N/FRAME_RATE/TB"
    base = ["ffmpeg", "-y", "-loglevel", "error", "-i", percorso, "-vf", filtro, "-an",
            "-c:v", "libx264", "-crf", "12", "-preset", "fast"]
    try:                                    # ffmpeg recente
        subprocess.run(base + ["-fps_mode", "passthrough", out], check=True)
    except subprocess.CalledProcessError:   # ffmpeg vecchio
        subprocess.run(base + ["-vsync", "0", out], check=True)
    n = info_video(out)[1]
    if n != ultimo - primo + 1:
        print(f"   attenzione: il ritaglio ha {n} fotogrammi invece di {ultimo - primo + 1}")
    return out


def controlla_cache(cartella, pesi):
    """Le previsioni gia' fatte si riusano solo se vengono dagli STESSI pesi (stesso file, stessa data)."""
    os.makedirs(cartella, exist_ok=True)
    firma = f"{os.path.abspath(pesi)} {os.path.getsize(pesi)} {int(os.path.getmtime(pesi))}"
    p_firma = os.path.join(cartella, "pesi_usati.txt")
    if os.path.exists(p_firma) and open(p_firma, encoding="utf-8").read().strip() != firma:
        vecchi = [f for f in os.listdir(cartella) if f.endswith("_ball.csv")]
        for f in vecchi:
            os.remove(os.path.join(cartella, f))
        print(f"   {os.path.basename(cartella)}: pesi cambiati, rifaccio le previsioni ({len(vecchi)} vecchie cancellate)")
    open(p_firma, "w", encoding="utf-8").write(firma + "\n")


def previsione(video, pesi, cartella):
    """CSV di TrackNet (Frame da 0, Visibility, X, Y) per video e pesi, come lo fa il programma."""
    stem = os.path.splitext(os.path.basename(video))[0]
    csv = os.path.join(cartella, f"{stem}_ball.csv")
    if os.path.exists(csv):
        return csv
    cmd = [sys.executable, os.path.join(TRACKNET_DIR, "predict.py"), "--video_file", os.path.abspath(video),
           "--tracknet_file", os.path.abspath(pesi), "--save_dir", os.path.abspath(cartella), "--eval_mode", "weight"]
    t0 = time.time()
    subprocess.run(cmd, cwd=TRACKNET_DIR, check=True)
    print(f"   {stem} con {os.path.basename(pesi)}: {time.time() - t0:.0f} s")
    return csv


def esito(gt_vis, gt_x, gt_y, p_vis, p_x, p_y, scala, tol):
    if gt_vis == 1:
        if not p_vis:
            return "FN", np.nan
        d = float(np.hypot(p_x - gt_x, p_y - gt_y)) * scala
        return ("TP" if d <= tol else "FP1"), d
    return ("FP2" if p_vis else "TN"), np.nan


def metriche(df):
    c = df["esito"].value_counts()
    TP, TN, FP1, FP2, FN = (int(c.get(k, 0)) for k in ("TP", "TN", "FP1", "FP2", "FN"))
    n = TP + TN + FP1 + FP2 + FN
    prec = TP / (TP + FP1 + FP2) if TP + FP1 + FP2 else 0.0
    rich = TP / (TP + FN) if TP + FN else 0.0
    f1 = 2 * prec * rich / (prec + rich) if prec + rich else 0.0
    err = df.loc[df["esito"] == "TP", "distanza_px1080"]       # solo dove l'ha trovata davvero
    return {"n": n, "TP": TP, "TN": TN, "FP1": FP1, "FP2": FP2, "FN": FN,
            "accuratezza": (TP + TN) / n if n else 0.0, "precisione": prec, "richiamo": rich, "F1": f1,
            "errore_mediano_px1080": float(err.median()) if len(err) else float("nan")}


def gruppi(df, fps_video):
    vicino = df.apply(lambda r: pd.notna(r["distanza_colpo"]) and r["distanza_colpo"] != ""
                      and abs(float(r["distanza_colpo"])) <= round(0.1 * fps_video[r["video"]]), axis=1)
    out = {"tutti": df, "vicino al colpo (0,1 s)": df[vicino], "pallina mossa": df[df["mossa"] == 1],
           "a caso (lontano dai colpi)": df[df["motivo"] == "casuale"]}
    for v in sorted(df["video"].unique()):
        out[f"video {v}"] = df[df["video"] == v]
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--etichette", default=os.path.join(QUI, "test", "etichette_test.csv"))
    p.add_argument("--video_dir", nargs="+", default=[os.path.join(RADICE, "inputs")])
    p.add_argument("--pesi", nargs="+", required=True, help="nome=percorso, es. badminton=tracknet3/ckpts/TrackNet_best.pt")
    p.add_argument("--uscita", default=os.path.join(QUI, "valutazione"))
    p.add_argument("--tolleranza", type=float, default=15.0, help="px a 1080p")
    p.add_argument("--margine", type=int, default=60, help="fotogrammi in piu' attorno al pezzo tagliato")
    a = p.parse_args()

    et = pd.read_csv(a.etichette)
    et = et[et["visibile"].isin([0, 1])].copy()
    if et.empty:
        raise SystemExit("Nessuna etichetta valida (visibile 0 o 1).")
    pesi = []
    for voce in a.pesi:
        nome, _, percorso = voce.partition("=")
        if not percorso:
            nome, percorso = os.path.splitext(os.path.basename(voce))[0], voce
        if not os.path.exists(percorso):
            raise SystemExit(f"Pesi non trovati: {percorso}")
        pesi.append((nome, percorso))
    os.makedirs(a.uscita, exist_ok=True)
    for nome, percorso in pesi:
        controlla_cache(os.path.join(a.uscita, "previsioni", nome), percorso)

    righe = {nome: [] for nome, _ in pesi}
    fps_video = {}
    for video, gruppo in et.groupby("video"):
        percorso = next((os.path.join(d, video) for d in a.video_dir if os.path.exists(os.path.join(d, video))), None)
        if percorso is None:
            print(f"[{video}] video non trovato in {a.video_dir}: salto {len(gruppo)} etichette")
            continue
        fps, n, w, h = info_video(percorso)
        fps_video[video] = fps
        scala = 1080.0 / h                          # distanze riportate a 1080p
        primo = 0
        if n > VIDEO_CORTO:
            primo = max(0, int(gruppo["frame"].min()) - 1 - a.margine)
            ultimo = min(n - 1, int(gruppo["frame"].max()) - 1 + a.margine)
            percorso = ritaglio(percorso, primo, ultimo, os.path.join(a.uscita, "ritagli"))
            print(f"[{video}] tagliato: fotogrammi {primo + 1}-{ultimo + 1}")
        for nome, file_pesi in pesi:
            csv = previsione(percorso, file_pesi, os.path.join(a.uscita, "previsioni", nome))
            pr = pd.read_csv(csv).set_index("Frame")
            for _, r in gruppo.iterrows():
                f = int(r["frame"]) - 1 - primo                 # etichette da 1, TrackNet da 0
                if f in pr.index:
                    q = pr.loc[f]
                    p_vis, p_x, p_y = int(q["Visibility"]) == 1, float(q["X"]), float(q["Y"])
                else:
                    p_vis, p_x, p_y = False, np.nan, np.nan
                gt_vis = int(r["visibile"])
                e, d = esito(gt_vis, float(r["x"]) if gt_vis else np.nan, float(r["y"]) if gt_vis else np.nan,
                             p_vis, p_x, p_y, scala, a.tolleranza)
                mossa = pd.to_numeric(r.get("mossa", 0), errors="coerce")
                righe[nome].append({"video": video, "frame": int(r["frame"]), "visibile": gt_vis,
                                    "x": r["x"], "y": r["y"], "mossa": 0 if pd.isna(mossa) else int(mossa),
                                    "motivo": r.get("motivo", ""), "distanza_colpo": r.get("distanza_colpo", ""),
                                    "trovata": int(p_vis), "pred_x": p_x, "pred_y": p_y,
                                    "distanza_px1080": d, "esito": e})

    voto, md = {}, []
    tabelle = {}
    for nome, _ in pesi:
        df = pd.DataFrame(righe[nome])
        if df.empty:
            continue
        df.to_csv(os.path.join(a.uscita, f"confronto_{nome}.csv"), index=False)
        tabelle[nome] = df
        voto[nome] = {}
        for g, sotto in gruppi(df, fps_video).items():
            voto[nome][g] = metriche(sotto)
            # anche con tolleranza stretta (8 px)
            stretta = sotto.copy()
            stretta.loc[(stretta["esito"] == "TP") & (stretta["distanza_px1080"] > 8), "esito"] = "FP1"
            voto[nome][g]["richiamo_8px"] = metriche(stretta)["richiamo"]

    nomi = list(voto)
    md.append(f"# Voto di TrackNet sul set di test\n\nTolleranza {a.tolleranza:.0f} px a 1080p. "
              f"Etichette: {os.path.basename(a.etichette)}\n")
    for g in voto[nomi[0]]:
        md.append(f"\n## {g}\n")
        md.append("| pesi | n | richiamo | precisione | F1 | accuratezza | errore mediano dei TP (px 1080p) | richiamo a 8 px | TP | FP1 | FN | FP2 | TN |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for nome in nomi:
            m = voto[nome].get(g)
            if m is None:
                continue
            md.append(f"| {nome} | {m['n']} | {m['richiamo']:.2f} | {m['precisione']:.2f} | {m['F1']:.2f} | "
                      f"{m['accuratezza']:.2f} | {m['errore_mediano_px1080']:.1f} | {m['richiamo_8px']:.2f} | "
                      f"{m['TP']} | {m['FP1']} | {m['FN']} | {m['FP2']} | {m['TN']} |")
    testo = "\n".join(md) + "\n"
    open(os.path.join(a.uscita, "voto.md"), "w", encoding="utf-8").write(testo)
    json.dump(voto, open(os.path.join(a.uscita, "voto.json"), "w"), indent=1)
    print(testo)
    print(f"Dettagli in {a.uscita}")


if __name__ == "__main__":
    main()
