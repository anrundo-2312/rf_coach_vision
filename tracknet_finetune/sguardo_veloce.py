"""
sguardo_veloce.py - sguardo RAPIDO, senza etichette, a come pesi diversi di
TrackNet vedono la pallina nei nostri video. NON e' il voto (quello e'
valuta_tracknet.py, con le etichette a mano): serve a farsi un'idea in dieci
minuti, prima di spendere un'ora a etichettare.

    python tracknet_finetune/sguardo_veloce.py --video_dir inputs --dati_dir outputs/dati \
        --pesi badminton=tracknet3/ckpts/TrackNet_best.pt run1=<Drive>/tracknet_finetune/run1/TrackNet_tennis.pt \
        --uscita /content/valutazione

Per ogni video (di default i tre corti del set di test) e per ogni file di
pesi:
  - lancia la previsione come nel programma (tracknet3/predict.py, modalita'
    weight, senza InpaintNet), riusando le previsioni gia' fatte: e' la stessa
    cache di valuta_tracknet.py, che poi non le rifa';
  - conta in quanti fotogrammi la pallina viene vista, in tutto e attorno ai
    colpi trovati dal programma (+-0,12 s, la stessa finestra del set di test);
  - conta i segnali di punti falsi: salti > 120 px (a 1080p) fra due fotogrammi
    consecutivi e punti isolati (visti in un fotogramma ma non in quelli accanto);
  - disegna le traiettorie sul primo fotogramma e i ritagli attorno ai colpi
    (fotogrammi -4, 0, +4) con il punto di ogni file di pesi.

ATTENZIONE: "vista piu' spesso" non vuol dire "giusta". Senza etichette non si
distingue una pallina trovata da un punto falso: guardare i ritagli.

Uscite in --uscita/sguardo/: <video>_traiettorie.png, <video>_colpi.png, sguardo.md
"""

import argparse
import json
import os
import sys

import cv2
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

QUI = os.path.dirname(os.path.abspath(__file__))
VIDEO_DEFAULT = ["nicola_matarese_trim.mp4", "zverev_djokovic_trim_swin_like.mp4", "alcaraz.mp4"]
COLORI = ["#ffd400", "#00c8ff", "#ff50a0", "#80ff80"]          # giallo, azzurro, rosa, verde
SALTO_PX = 120            # a 1080p: piu' di cosi' fra due fotogrammi consecutivi e' sospetto
RITAGLIO_PX = 500         # lato del ritaglio attorno al colpo, a 1080p
MAX_FOTOGRAMMI = 3000     # oltre, il video andrebbe tagliato (lo fa valuta_tracknet.py): qui si salta


def trova(nome, cartelle):
    for c in cartelle:
        p = os.path.join(c, nome)
        if c and os.path.exists(p):
            return p
    return None


def leggi_fotogrammi(percorso, voluti):
    """{numero (da 1): immagine} leggendo il video in fila dall'inizio (saltare non e' affidabile)."""
    voluti = {int(f) for f in voluti if f >= 1}
    out = {}
    if not voluti:
        return out
    cap = cv2.VideoCapture(percorso)
    f, ultimo = 0, max(voluti)
    while f < ultimo:
        f += 1
        if f in voluti:
            ok, img = cap.read()
            if not ok:
                break
            out[f] = img
        elif not cap.grab():
            break
    cap.release()
    return out


def posizioni_programma(stem, cartelle_dati):
    """{frame: (x, y)} di dove il programma ha messo la pallina (tracking CSV e punti usati per la velocita')."""
    pos = {}
    p = trova(f"{stem}_velocita_punti.json", cartelle_dati)
    if p:
        for colpo in json.load(open(p, encoding="utf-8")):
            for f, x, y in colpo.get("_punti", []):
                pos[int(f)] = (float(x), float(y))
    p = trova(f"{stem}_tracking.csv", cartelle_dati)
    if p:
        t = pd.read_csv(p, usecols=lambda c: c in ("frame", "pallina_x", "pallina_y"))
        t = t[t["pallina_x"].notna()]
        for f, x, y in zip(t["frame"], t["pallina_x"], t["pallina_y"]):
            pos[int(f)] = (float(x), float(y))
    return pos


def statistiche(pr, n, colpi, meta, scala):
    """pr: DataFrame con Frame (da 0), Visibility, X, Y[, Conf]."""
    visto = np.zeros(n + 2, bool)                   # indice = fotogramma da 1
    xy = np.full((n + 2, 2), np.nan)
    conf = []
    for fr, v, x, y, c in zip(pr["Frame"], pr["Visibility"], pr["X"], pr["Y"],
                              pr["Conf"] if "Conf" in pr.columns else [np.nan] * len(pr)):
        f = int(fr) + 1
        if 1 <= f <= n and int(v) == 1:
            visto[f] = True
            xy[f] = (float(x), float(y))
            conf.append(float(c))
    vicino = np.zeros(n + 2, bool)
    for c in colpi:
        vicino[max(1, c - meta):min(n, c + meta) + 1] = True
    d = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1])) * scala          # fra f e f+1
    entrambi = visto[:-1] & visto[1:]
    salti = int(np.sum(entrambi & (d > SALTO_PX)))
    isolati = int(np.sum(visto[1:n + 1] & ~visto[0:n] & ~visto[2:n + 2]))
    return {"visto": visto, "xy": xy, "vicino": vicino,
            "pct": 100 * visto[1:n + 1].mean(),
            "pct_colpi": 100 * visto[vicino].mean() if vicino.any() else float("nan"),
            "n_colpi": int(vicino.sum()),
            "conf": float(np.nanmedian(conf)) if conf and np.isfinite(conf).any() else float("nan"),
            "salti": salti, "isolati": isolati}


def disegna_traiettorie(nome, sfondo, risultati, percorso_png):
    h, w = sfondo.shape[:2]
    s = 960 / w
    piccolo = cv2.resize(sfondo, (960, round(h * s)))[..., ::-1]
    fig, assi = plt.subplots(1, len(risultati), figsize=(7 * len(risultati), 4.4))
    assi = np.atleast_1d(assi)
    for ax, (pesi, r), colore in zip(assi, risultati.items(), COLORI):
        ax.imshow(piccolo)
        xy, visto, vicino = r["xy"] * s, r["visto"], r["vicino"]
        for f in range(1, len(visto) - 1):
            if visto[f] and visto[f + 1]:
                ax.plot(xy[f:f + 2, 0], xy[f:f + 2, 1], color=colore, lw=0.8, alpha=0.8)
        idx = np.where(visto)[0]
        ax.scatter(xy[idx, 0], xy[idx, 1], s=6, color=colore, label="pallina vista")
        idc = idx[vicino[idx]]
        ax.scatter(xy[idc, 0], xy[idc, 1], s=14, color="red", label="vicino ai colpi")
        ax.set_title(f"{pesi}: vista nel {r['pct']:.0f}% dei fotogrammi, {r['pct_colpi']:.0f}% attorno ai colpi\n"
                     f"salti sospetti {r['salti']}, punti isolati {r['isolati']}", fontsize=10)
        ax.axis("off")
        ax.legend(loc="lower right", fontsize=8, markerscale=2)
    fig.suptitle(nome, fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(percorso_png, dpi=110)
    plt.close(fig)


def disegna_colpi(nome, percorso, colpi, risultati, pos_programma, h, percorso_png, max_colpi):
    if not colpi:
        return False
    if len(colpi) > max_colpi:
        colpi = [colpi[i] for i in np.linspace(0, len(colpi) - 1, max_colpi).round().astype(int)]
    scarti = (-4, 0, 4)
    voluti = {c + d for c in colpi for d in scarti}
    immagini = leggi_fotogrammi(percorso, voluti)
    lato = int(RITAGLIO_PX * h / 1080)
    raggio = max(6, int(22 * h / 1080))
    nomi = list(risultati)

    def centro(g, f):
        """Dove centrare: posizione del programma, poi una previsione (al fotogramma g, poi al colpo f)."""
        for k in (g, f):
            if k in pos_programma:
                return pos_programma[k]
            for r in risultati.values():
                if 0 <= k < len(r["visto"]) and r["visto"][k]:
                    return tuple(r["xy"][k])
        return None

    fig, assi = plt.subplots(len(colpi), len(scarti), figsize=(3.3 * len(scarti), 3.5 * len(colpi)))
    assi = np.array(assi).reshape(len(colpi), len(scarti))
    for i, c in enumerate(colpi):
        for j, d in enumerate(scarti):
            g, ax = c + d, assi[i, j]
            ax.axis("off")
            img = immagini.get(g)
            if img is None:
                ax.set_title(f"f {g}: non leggibile", fontsize=8)
                continue
            cen = centro(g, c)
            if cen is None:
                cen = (img.shape[1] / 2, img.shape[0] / 2)
            x0 = int(np.clip(cen[0] - lato / 2, 0, max(0, img.shape[1] - lato)))
            y0 = int(np.clip(cen[1] - lato / 2, 0, max(0, img.shape[0] - lato)))
            rit = img[y0:y0 + lato, x0:x0 + lato].copy()
            stato = []
            for k, (pesi, r) in enumerate(risultati.items()):
                col = tuple(int(COLORI[k % len(COLORI)].lstrip("#")[m:m + 2], 16) for m in (4, 2, 0))  # BGR
                if 0 <= g < len(r["visto"]) and r["visto"][g]:
                    px, py = int(r["xy"][g, 0] - x0), int(r["xy"][g, 1] - y0)
                    if k % 2 == 0:
                        cv2.circle(rit, (px, py), raggio, col, 2)
                    else:
                        cv2.rectangle(rit, (px - raggio, py - raggio), (px + raggio, py + raggio), col, 2)
                    stato.append(f"{pesi}: vista")
                else:
                    stato.append(f"{pesi}: no")
            ax.imshow(rit[..., ::-1])
            ax.set_title(f"colpo {c}, fotogramma {g} ({d:+d})\n" + "  |  ".join(stato), fontsize=8)
    forme = ", ".join(f"{n} = {'cerchio' if k % 2 == 0 else 'quadrato'} {['giallo', 'azzurro', 'rosa', 'verde'][k % 4]}"
                      for k, n in enumerate(nomi))
    fig.suptitle(f"{nome}: ritagli attorno ai colpi del programma ({forme})", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    fig.savefig(percorso_png, dpi=110)
    plt.close(fig)
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--video", nargs="*", default=VIDEO_DEFAULT)
    p.add_argument("--video_dir", nargs="+", required=True)
    p.add_argument("--dati_dir", nargs="+", required=True, help="dove stanno <video>_velocita.csv (colpi del programma)")
    p.add_argument("--pesi", nargs="+", required=True, help="nome=percorso, es. badminton=tracknet3/ckpts/TrackNet_best.pt")
    p.add_argument("--uscita", required=True, help="stessa cartella di valuta_tracknet.py: le previsioni si riusano")
    p.add_argument("--repo", default=os.path.dirname(QUI), help="cartella del progetto (con tracknet3/)")
    p.add_argument("--mezza_finestra_s", type=float, default=0.12)
    p.add_argument("--max_colpi", type=int, default=4, help="colpi disegnati nei ritagli, per video")
    a = p.parse_args()

    repo = os.path.abspath(a.repo)
    if not os.path.exists(os.path.join(repo, "tracknet3", "predict.py")):
        raise SystemExit(f"Non trovo tracknet3/predict.py in {repo}: passa --repo <cartella del progetto>")
    sys.path.insert(0, os.path.join(repo, "tracknet_finetune"))
    import valuta_tracknet as vt
    vt.TRACKNET_DIR = os.path.join(repo, "tracknet3")

    pesi = []
    for voce in a.pesi:
        nome, _, percorso = voce.partition("=")
        if not percorso:
            nome, percorso = os.path.splitext(os.path.basename(voce))[0], voce
        if not os.path.exists(percorso):
            raise SystemExit(f"Pesi non trovati: {percorso}")
        pesi.append((nome, os.path.abspath(percorso)))
    cartella_sguardo = os.path.join(a.uscita, "sguardo")
    os.makedirs(cartella_sguardo, exist_ok=True)
    for nome, percorso in pesi:
        vt.controlla_cache(os.path.join(a.uscita, "previsioni", nome), percorso)

    righe_md = ["# Sguardo veloce (senza etichette)\n",
                "Quante volte TrackNet vede la pallina. NON e' il voto: senza etichette un punto falso conta come "
                "\"vista\". I salti (> 120 px a 1080p fra fotogrammi consecutivi) e i punti isolati sono indizi di punti falsi.\n",
                "| video | pesi | fotogrammi | vista | vista attorno ai colpi | conf. mediana | salti sospetti | punti isolati |",
                "|---|---|---|---|---|---|---|---|"]
    for video in a.video:
        percorso = trova(video, a.video_dir)
        if not percorso:
            print(f"[{video}] non trovato in {a.video_dir}: salto")
            continue
        stem = os.path.splitext(video)[0]
        fps, n, w, h = vt.info_video(percorso)
        if n > MAX_FOTOGRAMMI:
            print(f"[{video}] {n} fotogrammi: troppo lungo per lo sguardo veloce, salto")
            continue
        scala = 1080.0 / h
        meta = max(1, round(a.mezza_finestra_s * fps))
        p_vel = trova(f"{stem}_velocita.csv", a.dati_dir)
        colpi = sorted({int(f) for f in pd.read_csv(p_vel)["frame"].dropna()}) if p_vel else []
        if not p_vel:
            print(f"[{video}] manca {stem}_velocita.csv: niente colpi, solo le traiettorie")
        print(f"[{video}] {n} fotogrammi a {fps:.0f} fps, {len(colpi)} colpi del programma")
        risultati = {}
        for nome, file_pesi in pesi:
            csv = vt.previsione(percorso, file_pesi, os.path.join(a.uscita, "previsioni", nome))
            risultati[nome] = statistiche(pd.read_csv(csv), n, colpi, meta, scala)
            r = risultati[nome]
            print(f"   {nome:>10}: vista {r['pct']:.0f}% ({r['pct_colpi']:.0f}% attorno ai colpi, {r['n_colpi']} fotogrammi), "
                  f"conf {r['conf']:.2f}, salti {r['salti']}, isolati {r['isolati']}")
            righe_md.append(f"| {video} | {nome} | {n} | {r['pct']:.0f}% | {r['pct_colpi']:.0f}% ({r['n_colpi']}) | "
                            f"{r['conf']:.2f} | {r['salti']} | {r['isolati']} |")
        primo = leggi_fotogrammi(percorso, {1}).get(1)
        if primo is not None:
            disegna_traiettorie(video, primo, risultati, os.path.join(cartella_sguardo, f"{stem}_traiettorie.png"))
        disegna_colpi(video, percorso, colpi, risultati, posizioni_programma(stem, a.dati_dir), h,
                      os.path.join(cartella_sguardo, f"{stem}_colpi.png"), a.max_colpi)
    testo = "\n".join(righe_md) + "\n"
    open(os.path.join(cartella_sguardo, "sguardo.md"), "w", encoding="utf-8").write(testo)
    print("\n" + testo)
    print(f"Immagini in {cartella_sguardo}")


if __name__ == "__main__":
    main()
