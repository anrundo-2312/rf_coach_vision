"""
metriche_colpi.py - prime misure per ogni colpo del giocatore.

Prende il <video>_tracking.csv e il <video>_impatti.csv (prodotto da
rileva_impatti.py) e per ogni colpo del NOSTRO giocatore calcola:

  - altezza del contatto, come frazione dell'altezza del giocatore
    (0 = piedi, 1 = testa) e in parole (sotto l'anca / tra anca e spalla /
    sopra la spalla): e' la misura che un maestro usa per dire "l'hai
    presa troppo bassa";
  - lato e distanza dal corpo, cioe' quanto la pallina era lontana dal
    centro del giocatore al contatto, sempre in frazioni della sua altezza;
  - velocita' della pallina prima e dopo l'impatto.

    python classificazione/metriche_colpi.py --tracking outputs/<video>_tracking.csv

ATTENZIONE alla velocita': e' in pixel al secondo, non in km/h. Per i km/h
servirebbe sapere quanti metri vale un pixel, e in prospettiva cambia da
punto a punto del campo: si ricava dalle linee del campo (omografia), ed e'
un lavoro a parte. Cosi' com'e' resta comunque utile per confrontare colpi
dello stesso video.

Tutte le misure sono normalizzate sull'altezza del giocatore, quindi non
cambiano se il giocatore e' piu' vicino o piu' lontano dalla camera.
"""

import argparse
import csv

import numpy as np

# Quanti frame prima e dopo l'impatto guardare per stimare la velocita'.
FINESTRA_VELOCITA = 20


def colonna(righe, nome):
    v = np.full(len(righe), np.nan)
    for i, r in enumerate(righe):
        try:
            v[i] = float(r[nome])
        except (ValueError, KeyError):
            pass
    return v


def velocita(bx, by, frame_impatto, da, a, fps):
    """Velocita' media (pixel al secondo) sui frame con pallina vista."""

    idx = [j for j in range(max(0, frame_impatto + da), min(len(by), frame_impatto + a))
           if not np.isnan(by[j])]
    if len(idx) < 2:
        return np.nan
    spazio = np.hypot(np.diff(bx[idx]), np.diff(by[idx])).sum()
    tempo = (idx[-1] - idx[0]) / fps
    return spazio / tempo if tempo > 0 else np.nan


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tracking", required=True)
    p.add_argument("--impatti", help="default: <video>_impatti.csv accanto al tracking")
    p.add_argument("--out", help="default: <video>_metriche.csv")
    args = p.parse_args()

    righe = list(csv.DictReader(open(args.tracking, newline="")))
    impatti = list(csv.DictReader(open(args.impatti or args.tracking.replace("_tracking.csv", "_impatti.csv"), newline="")))

    bx, by = colonna(righe, "pallina_x"), colonna(righe, "pallina_y")
    vista = np.array([r.get("pallina_fonte") == "tracknet" for r in righe])
    bx[~vista] = np.nan
    by[~vista] = np.nan  # le posizioni ricostruite non sono misure: non ci calcoliamo sopra

    y1, y2 = colonna(righe, "giocatore_y1"), colonna(righe, "giocatore_y2")
    x1, x2 = colonna(righe, "giocatore_x1"), colonna(righe, "giocatore_x2")
    spalla = (colonna(righe, "spalla_sx_y") + colonna(righe, "spalla_dx_y")) / 2
    anca = (colonna(righe, "anca_sx_y") + colonna(righe, "anca_dx_y")) / 2

    tempi = colonna(righe, "tempo_s")
    fps = 1 / np.nanmedian(np.diff(tempi)) if len(tempi) > 1 else 60.0

    uscita = args.out or args.tracking.replace("_tracking.csv", "_metriche.csv")
    with open(uscita, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "tempo_s", "colpo", "altezza_contatto", "zona_contatto",
                    "lato", "distanza_dal_corpo", "velocita_prima_px_s", "velocita_dopo_px_s"])

        print(f"{'colpo':10s} {'tempo':>6s}  {'altezza':>7s}  {'zona':<18s} {'lato':<9s} {'dist':>5s}  velocita' prima/dopo (px/s)")

        for e in impatti:
            if e["chi"] != "giocatore":
                continue

            i = int(e["frame"]) - 1
            visti = [j for j in range(len(by)) if not np.isnan(by[j])]
            if not visti:
                continue
            k = min(visti, key=lambda j: abs(j - i))  # frame con pallina vista piu' vicino all'impatto

            altezza = y2[i] - y1[i]
            rel = (y2[i] - by[k]) / altezza
            if by[k] < spalla[i]:
                zona = "sopra la spalla"
            elif by[k] < anca[i]:
                zona = "tra anca e spalla"
            else:
                zona = "sotto l'anca"

            centro = (x1[i] + x2[i]) / 2
            lato = "destra" if bx[k] > centro else "sinistra"
            distanza = abs(bx[k] - centro) / altezza

            v_prima = velocita(bx, by, i, -FINESTRA_VELOCITA, 0, fps)
            v_dopo = velocita(bx, by, i, 1, FINESTRA_VELOCITA, fps)

            w.writerow([e["frame"], e["tempo_s"], e["colpo"], round(rel, 3), zona, lato,
                        round(distanza, 3),
                        "" if np.isnan(v_prima) else round(v_prima),
                        "" if np.isnan(v_dopo) else round(v_dopo)])

            def fmt(v):
                return "   -  " if np.isnan(v) else f"{v:6.0f}"

            print(f"{e['colpo'] or '?':10s} {float(e['tempo_s']):5.2f}s  {rel:7.2f}  {zona:<18s} {lato:<9s} {distanza:5.2f}  {fmt(v_prima)} / {fmt(v_dopo)}")

    print(f"\nSalvato in {uscita}")
    print("Nota: velocita' in pixel al secondo. Per i km/h serve la calibrazione dal campo.")


if __name__ == "__main__":
    main()
