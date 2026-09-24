"""
rileva_impatti.py - trova QUANDO avviene un colpo, usando la traiettoria
della pallina, e dice di che colpo si tratta usando le previsioni per frame.

L'idea: con la camera dietro il giocatore, la pallina che torna verso di lui
scende nell'immagine (y cresce), quella che si allontana risale (y cala).
Un impatto e' quindi un'inversione del verso: il punto piu' BASSO della
traiettoria e' un colpo del nostro giocatore, quello piu' ALTO un colpo
dell'avversario.

    python classificazione/rileva_impatti.py --tracking outputs/<video>_tracking.csv

Se accanto c'e' <video>_colpi.csv (prodotto da classifica_tracking.py), ogni
impatto riceve anche il tipo di colpo, deciso a maggioranza sui frame attorno
all'impatto: un voto solo sarebbe troppo fragile.

Usa SOLO le posizioni viste davvero da TrackNet (colonna pallina_fonte =
tracknet); quelle ricostruite vengono ignorate e riempite per interpolazione,
perche' inventare un'inversione dove la pallina non si vede e' il modo piu'
facile per contare colpi inesistenti.
"""

import argparse
import csv
import os
from collections import Counter

import numpy as np

# Un'inversione conta come colpo solo se la pallina, prima e dopo, percorre
# almeno questa frazione dell'altezza del giocatore: sotto, e' rumore o un
# rimbalzo.
AMPIEZZA_MINIMA = 0.35

# Due impatti piu' vicini di cosi' (in frame) sono lo stesso colpo.
DISTANZA_MINIMA = 20

# Finestra di frame attorno all'impatto su cui votare il tipo di colpo.
FINESTRA_VOTO = 6


def leggi(tracking):
    righe = list(csv.DictReader(open(tracking, newline="")))
    n = len(righe)
    y = np.full(n, np.nan)
    x = np.full(n, np.nan)
    altezza = np.full(n, np.nan)

    for i, r in enumerate(righe):
        if r.get("pallina_fonte") == "tracknet":
            x[i] = float(r["pallina_x"])
            y[i] = float(r["pallina_y"])
        try:
            altezza[i] = float(r["giocatore_y2"]) - float(r["giocatore_y1"])
        except (ValueError, KeyError):
            pass

    return righe, x, y, altezza


def liscia(y, finestra=7):
    idx = np.arange(len(y))
    visti = ~np.isnan(y)
    if visti.sum() < 2:
        return None
    pieno = np.interp(idx, idx[visti], y[visti])
    pad = finestra // 2
    return np.convolve(np.pad(pieno, (pad, pad), "edge"), np.ones(finestra) / finestra, "valid")


def tratti_monotoni(y, soglia):
    """Tratti in cui la pallina va sempre nello stesso verso, fondendo i piccoli."""

    d = np.diff(y)
    segno = np.sign(d)
    tratti, inizio = [], 0
    for i in range(1, len(segno)):
        if segno[i] != 0 and segno[i] != segno[inizio]:
            tratti.append([inizio, i])
            inizio = i
    tratti.append([inizio, len(segno)])

    fuso = True
    while fuso and len(tratti) > 1:
        fuso = False
        for j, (a, b) in enumerate(tratti):
            if abs(y[b] - y[a]) < soglia:
                if j > 0:
                    tratti[j - 1][1] = b
                else:
                    tratti[1][0] = a
                tratti.pop(j)
                fuso = True
                break

    return tratti


def trova_impatti(y, altezza_giocatore):
    soglia = AMPIEZZA_MINIMA * altezza_giocatore
    tratti = tratti_monotoni(y, soglia)
    impatti = []

    for j in range(len(tratti) - 1):
        a1, b1 = tratti[j]
        a2, b2 = tratti[j + 1]
        scende = y[b1] - y[a1] > 0          # la pallina si avvicina al giocatore
        if scende == (y[b2] - y[a2] > 0):
            continue
        if min(abs(y[b1] - y[a1]), abs(y[b2] - y[a2])) < soglia:
            continue

        # il contatto e' l'estremo vero, cercato attorno al cambio di verso
        da, a = max(0, b1 - FINESTRA_VOTO), min(len(y), b1 + FINESTRA_VOTO + 1)
        f = int(np.argmax(y[da:a]) if scende else np.argmin(y[da:a])) + da

        if impatti and f - impatti[-1][0] < DISTANZA_MINIMA:
            continue
        impatti.append((f, "giocatore" if scende else "avversario"))

    return impatti


def tipi_di_colpo(percorso_colpi):
    if not os.path.exists(percorso_colpi):
        return {}
    return {int(r["frame"]): (r["classe"], float(r["sicurezza"]))
            for r in csv.DictReader(open(percorso_colpi, newline=""))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tracking", required=True)
    p.add_argument("--colpi", help="default: <video>_colpi.csv accanto al tracking")
    p.add_argument("--out", help="default: <video>_impatti.csv")
    args = p.parse_args()

    righe, x, y, altezza = leggi(args.tracking)
    ys = liscia(y)
    if ys is None:
        raise SystemExit("Troppo pochi frame con la pallina vista: impossibile cercare gli impatti.")

    altezza_mediana = float(np.nanmedian(altezza))
    impatti = trova_impatti(ys, altezza_mediana)

    classi = tipi_di_colpo(args.colpi or args.tracking.replace("_tracking.csv", "_colpi.csv"))
    uscita = args.out or args.tracking.replace("_tracking.csv", "_impatti.csv")

    with open(uscita, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "tempo_s", "chi", "colpo", "sicurezza", "pallina_x", "pallina_y"])

        print(f"{len(impatti)} impatti rilevati "
              f"(ampiezza minima {AMPIEZZA_MINIMA:.0%} dell'altezza del giocatore, "
              f"cioe' {AMPIEZZA_MINIMA * altezza_mediana:.0f} px):\n")

        for i, chi in impatti:
            r = righe[i]
            colpo, sicurezza = "", ""
            if chi == "giocatore" and classi:
                voti = [classi[int(righe[j]["frame"])]
                        for j in range(max(0, i - FINESTRA_VOTO), min(len(righe), i + FINESTRA_VOTO + 1))
                        if int(righe[j]["frame"]) in classi]
                if voti:
                    colpo, _ = Counter(v[0] for v in voti).most_common(1)[0]
                    sicurezza = round(float(np.mean([s for c, s in voti if c == colpo])), 3)

            w.writerow([r["frame"], r["tempo_s"], chi, colpo, sicurezza,
                        "" if np.isnan(x[i]) else round(x[i], 1),
                        "" if np.isnan(y[i]) else round(y[i], 1)])

            etichetta = f"  {colpo} (sicurezza {sicurezza})" if colpo else ""
            print(f"  frame {r['frame']:>4s}  {float(r['tempo_s']):5.2f}s  {chi}{etichetta}")

    print(f"\nSalvato in {uscita}")


if __name__ == "__main__":
    main()
