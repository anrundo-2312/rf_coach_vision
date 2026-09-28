"""
velocita_uscita.py - per ogni colpo del giocatore inquadrato (quello vicino
alla camera): velocita' di USCITA della pallina dalla racchetta in km/h e
direzione del colpo (lungo linea / incrociato / centrale).

    python velocita/velocita_uscita.py --video inputs/<video>.mp4

Legge dalla cartella outputs/dati il <video>_tracking.csv (analyze.py) e il
<video>_colpi.csv (classifica_tracking.py), e la calibrazione del campo
velocita/calibrazioni/<video>.json (calibra_campo.py). Scrive
outputs/dati/<video>_velocita.csv, un colpo per riga.

Passi:

1. FINESTRE DEI COLPI, dalla posa. Il classificatore segna frame per frame
   dritto / rovescio / servizio / attesa. I tratti non-attesa vicini (buchi di
   al massimo 5 frame) formano la finestra di un colpo.

2. PALLINA NELLA FINESTRA (palla_locale.py): TrackNet dove c'e', il
   rilevatore di colore attorno al giocatore dove TrackNet la perde.

3. CONTATTO. Cambio brusco del vettore spostamento della pallina (3 frame
   prima contro 3 frame dopo), con la pallina vicina a un polso e che DOPO si
   muove abbastanza veloce nell'immagine. L'ultima condizione scarta il
   rimbalzo della pallina dell'avversario davanti al giocatore, che
   nell'immagine sembra un colpo ma dopo la pallina continua ad arrivare
   lentamente.

4. VELOCITA' E DIREZIONE (rf_ball_exit_speed.exit_speed): traiettoria 3D dei
   ~1/3 di secondo dopo il contatto, con il contatto tenuto entro 1 m dal
   giocatore e la pallina diretta verso il campo avversario. Dalla velocita'
   3D si ricavano i km/h e l'angolo rispetto alle righe laterali.

5. LUNGO LINEA / INCROCIATO / CENTRALE, dalla posizione del giocatore e da
   dove arriverebbe la pallina nel campo avversario (vedi classifica_direzione).

Se in una finestra la posa indica un colpo ma il contatto non si trova (per
esempio la pallina passa dietro il corpo del giocatore), il colpo viene
scritto lo stesso, senza velocita', con una nota.
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter

import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
from rf_ball_exit_speed import exit_speed, ground_from_pixel  # noqa: E402
from calibra_campo import camera_da_json  # noqa: E402
import palla_locale  # noqa: E402

CENTRO_X = 5.485            # riga centrale del campo (m)

# Finestre dei colpi
BUCO_TRATTI = 5             # frame di "attesa" tollerati dentro un colpo
DURATA_MINIMA = 8           # frame non-attesa minimi per considerarlo un colpo
MARGINE_FINESTRA = 10       # frame aggiunti prima e dopo il tratto

# Contatto
PASSI = 3                   # frame prima/dopo per la direzione della pallina
SOGLIA_CAMBIO = 2.5         # cambio di velocita' minimo, altezze del giocatore al secondo
SOGLIA_DOPO = 2.4           # velocita' minima DOPO il contatto (scarta i rimbalzi)
DIST_POLSO = 0.6            # pallina entro 0,6 altezze da un polso
DISTANZA_MINIMA = 20        # due contatti piu' vicini sono lo stesso colpo

# Velocita'
DURATA_DOPO_S = 1 / 3       # traiettoria usata dopo il contatto (20 frame a 60 fps)
TOLLERANZA_PROFONDITA = 1.0 # contatto entro 1 m dalla distanza del giocatore

# Direzione
Y_ARRIVO = 21.0             # dove "arriva" la pallina: tra riga del servizio e fondo lontani (m)
FASCIA_CENTRO = 1.0         # +- metri attorno alla riga centrale considerati "centro"


# ------------------------------------------------------------------ lettura
def leggi_tracking(percorso):
    righe = list(csv.DictReader(open(percorso, newline="")))

    def num(r, c):
        try:
            return float(r[c])
        except (ValueError, KeyError, TypeError):
            return np.nan

    t = {"frame": np.array([int(r["frame"]) for r in righe])}
    t["tempo"] = np.array([num(r, "tempo_s") for r in righe])
    t["vista"] = np.array([r.get("pallina_fonte") == "tracknet" for r in righe])
    t["palla"] = np.array([[num(r, "pallina_x"), num(r, "pallina_y")] for r in righe])
    t["box"] = np.array([[num(r, c) for c in ("giocatore_x1", "giocatore_y1", "giocatore_x2", "giocatore_y2")] for r in righe])
    t["caviglie"] = np.array([[num(r, "caviglia_sx_x"), num(r, "caviglia_sx_y"), num(r, "caviglia_dx_x"), num(r, "caviglia_dx_y")] for r in righe])
    t["polsi"] = np.array([[num(r, "polso_sx_x"), num(r, "polso_sx_y"), num(r, "polso_dx_x"), num(r, "polso_dx_y")] for r in righe])
    t["fps"] = 1 / np.nanmedian(np.diff(t["tempo"]))
    return t


def leggi_colpi(percorso):
    return {int(r["frame"]): r["classe"] for r in csv.DictReader(open(percorso, newline=""))}


# ------------------------------------------------------------------ passo 1
def finestre_colpi(classi, n_frame):
    """Tratti di frame non-attesa, uniti se separati da pochi frame."""
    finestre, inizio, ultimo = [], None, None
    for f in range(1, n_frame + 1):
        c = classi.get(f)
        if c and c != "attesa":
            if inizio is None:
                inizio = f
            elif f - ultimo > BUCO_TRATTI + 1:
                finestre.append((inizio, ultimo))
                inizio = f
            ultimo = f
    if inizio is not None:
        finestre.append((inizio, ultimo))
    return [(a, b) for a, b in finestre
            if sum(1 for f in range(a, b + 1) if classi.get(f) not in (None, "attesa")) >= DURATA_MINIMA]


# ------------------------------------------------------------------ passo 3
def trova_contatti(traccia, t):
    """Frame (l'ultimo PRIMA del contatto) dei colpi del giocatore nella traccia."""
    fs = sorted(traccia)
    pos = {f: np.array(traccia[f][:2]) for f in fs}
    candidati = []
    for f in fs:
        prima = [g for g in fs if f - PASSI - 1 <= g < f][:1]           # punto ~3 frame prima
        dopo = [g for g in fs if f < g <= f + PASSI + 1][-1:]          # punto ~3 frame dopo
        if not prima or not dopo or f - prima[0] < PASSI - 1 or dopo[0] - f < PASSI - 1:
            continue
        i = f - 1
        x1, y1, x2, y2 = t["box"][i]
        h = y2 - y1
        if not np.isfinite(h) or h <= 0:
            continue
        v_prima = (pos[f] - pos[prima[0]]) / (f - prima[0])
        v_dopo = (pos[dopo[0]] - pos[f]) / (dopo[0] - f)
        cambio = np.linalg.norm(v_dopo - v_prima) / h * t["fps"]
        veloce_dopo = np.linalg.norm(v_dopo) / h * t["fps"]
        pol = t["polsi"][i].reshape(2, 2)
        pol = pol[np.all(np.isfinite(pol), axis=1)]
        vicina = len(pol) > 0 and np.min(np.linalg.norm(pol - pos[f], axis=1)) <= DIST_POLSO * h
        if vicina and cambio >= SOGLIA_CAMBIO and veloce_dopo >= SOGLIA_DOPO:
            candidati.append((f, cambio))
    scelti = []
    for f, c in sorted(candidati, key=lambda x: -x[1]):
        if all(abs(f - g) >= DISTANZA_MINIMA for g, _ in scelti):
            scelti.append((f, c))
    return sorted(f for f, _ in scelti)


# ------------------------------------------------------------------ passo 4
def piedi_a_terra(t, f_contatto, cam):
    """Posizione a terra del giocatore prima del colpo: il frame con i piedi piu' in basso
    nell'immagine (nel servizio il giocatore salta, al contatto i piedi sono in aria)."""
    migliore = None
    for f in range(max(1, f_contatto - 20), f_contatto + 1):
        ax, ay, bx, by = t["caviglie"][f - 1]
        if np.all(np.isfinite([ax, ay, bx, by])):
            if migliore is None or max(ay, by) > migliore[1]:
                migliore = (((ax + bx) / 2), max(ay, by))
    if migliore is None:
        x1, _, x2, y2 = t["box"][f_contatto - 1]
        migliore = ((x1 + x2) / 2, y2)
    return ground_from_pixel(migliore, cam)[:2]


def classifica_direzione(x_giocatore, contatto, v0):
    """Lungo linea / incrociato / centrale da dove parte il giocatore e dove arriva la pallina."""
    angolo = float(np.degrees(np.arctan2(v0[0], v0[1])))       # 0 = parallela alle righe laterali
    x_arrivo = contatto[0] + np.tan(np.radians(angolo)) * (Y_ARRIVO - contatto[1])
    lato_partenza = 0 if abs(x_giocatore - CENTRO_X) <= FASCIA_CENTRO else np.sign(x_giocatore - CENTRO_X)
    lato_arrivo = 0 if abs(x_arrivo - CENTRO_X) <= FASCIA_CENTRO else np.sign(x_arrivo - CENTRO_X)
    if lato_arrivo == 0:
        classe = "centrale"
    elif lato_partenza == 0:
        classe = "dal centro verso " + ("destra" if lato_arrivo > 0 else "sinistra")
    elif lato_partenza == lato_arrivo:
        classe = "lungo linea"
    else:
        classe = "incrociato"
    return angolo, float(x_arrivo), classe


def misura(t, traccia, f_contatto, cam):
    fps = t["fps"]
    n_dopo = max(4, int(round(DURATA_DOPO_S * fps)))
    fs = [f for f in sorted(traccia) if f_contatto - 8 <= f <= f_contatto + n_dopo]
    f_arr = np.array(fs)
    p_arr = np.array([traccia[f][:2] for f in fs], float)
    ci = int(np.flatnonzero(f_arr > f_contatto)[0])
    piedi = piedi_a_terra(t, f_contatto, cam)
    r = exit_speed(p_arr, f_arr, fps, cam, ci, impact_mode="visual", n_frames=n_dopo,
                   player_ground_xy=piedi, return_debug=True, forward=True,
                   depth_tol=TOLLERANZA_PROFONDITA)
    angolo, x_arrivo, direzione = classifica_direzione(piedi[0], r["impact_xyz_m"], r["v0_ms"])
    usati = [f for f in fs if f_contatto < f <= f_contatto + n_dopo]
    return r, piedi, angolo, x_arrivo, direzione, usati


def pallina_vicina(traccia, t):
    """Quanti punti della traccia hanno la pallina vicina a un polso del giocatore."""
    n = 0
    for f, (x, y, _) in traccia.items():
        x1, y1, x2, y2 = t["box"][f - 1]
        pol = t["polsi"][f - 1].reshape(2, 2)
        pol = pol[np.all(np.isfinite(pol), axis=1)]
        if len(pol) and np.isfinite(y2 - y1) and np.min(np.linalg.norm(pol - (x, y), axis=1)) <= DIST_POLSO * (y2 - y1):
            n += 1
    return n


def fine_tratto_piu_lungo(classi, a, b, colpo):
    migliore, inizio = (0, b), None
    for f in range(a, b + 2):
        if classi.get(f) == colpo:
            inizio = f if inizio is None else inizio
        elif inizio is not None:
            if f - inizio > migliore[0]:
                migliore = (f - inizio, f - 1)
            inizio = None
    return migliore[1]


# ------------------------------------------------------------------ principale
def analizza(video, cartella_dati="outputs/dati", calibrazione=None, verbose=True):
    nome = os.path.splitext(os.path.basename(video))[0]
    t = leggi_tracking(os.path.join(cartella_dati, nome + "_tracking.csv"))
    classi = leggi_colpi(os.path.join(cartella_dati, nome + "_colpi.csv"))
    pcal = calibrazione or os.path.join(QUI, "calibrazioni", nome + ".json")
    if not os.path.exists(pcal):
        raise SystemExit(f"Manca la calibrazione del campo: {pcal}\n"
                         f"Falla con: python velocita/calibra_campo.py {video}")
    cam = camera_da_json(json.load(open(pcal, encoding="utf-8")))

    n = len(t["frame"])
    tracknet = {int(f): tuple(p) for f, p, v in zip(t["frame"], t["palla"], t["vista"]) if v}
    altezze = {int(f): float(b[3] - b[1]) for f, b in zip(t["frame"], t["box"]) if np.isfinite(b[3] - b[1])}

    colpi = []
    for a, b in finestre_colpi(classi, n):
        primo, ultimo = max(1, a - MARGINE_FINESTRA), min(n, b + MARGINE_FINESTRA)
        traccia = palla_locale.segui(video, primo, ultimo, tracknet, altezze)
        contatti = trova_contatti(traccia, t) if traccia else []
        if verbose:
            print(f"finestra {a}-{b}: pallina in {len(traccia)} frame "
                  f"({sum(1 for v in traccia.values() if v[2] == 'locale')} dal rilevatore locale), contatti {contatti}")
        for fc in contatti:
            voti = [classi[f] for f in range(fc - 15, fc + 1) if classi.get(f) not in (None, "attesa")]
            colpo = Counter(voti).most_common(1)[0][0] if voti else ""
            riga = {"frame": fc, "tempo_s": round(float(t["tempo"][fc - 1]), 3), "colpo": colpo}
            try:
                r, piedi, angolo, x_arr, direzione, usati = misura(t, traccia, fc, cam)
                riga.update({
                    "velocita_uscita_kmh": round(r["exit_kmh"]),
                    "direzione": "" if colpo == "servizio" else direzione,
                    "angolo_gradi": round(angolo, 1),
                    "giocatore_x_m": round(float(piedi[0]), 2), "arrivo_x_m": round(x_arr, 2),
                    "contatto_x_m": round(float(r["impact_xyz_m"][0]), 2),
                    "contatto_y_m": round(float(r["impact_xyz_m"][1]), 2),
                    "contatto_z_m": round(float(r["impact_xyz_m"][2]), 2),
                    "punti_usati": r["n_points"], "errore_px": round(r["rms_px"], 1), "nota": "",
                    "_punti": [(f, *traccia[f][:2]) for f in usati]})
            except (ValueError, IndexError, np.linalg.LinAlgError) as e:
                riga.update({"nota": f"velocita' non calcolabile: {e}"})
            colpi.append(riga)
        if not contatti and pallina_vicina(traccia, t) >= 3:
            # la posa dice che c'e' un colpo e la pallina arriva al giocatore, ma attorno
            # al contatto non si vede (coperta dal corpo o persa): colpo senza velocita'.
            # Il contatto e' circa alla fine del tratto piu' lungo della classe prevalente.
            tratti = Counter(classi.get(f) for f in range(a, b + 1) if classi.get(f) not in (None, "attesa"))
            colpo = tratti.most_common(1)[0][0]
            fine = fine_tratto_piu_lungo(classi, a, b, colpo)
            colpi.append({"frame": fine, "tempo_s": round(float(t["tempo"][fine - 1]), 3), "colpo": colpo,
                          "nota": "contatto non visibile: pallina coperta o persa"})
    return nome, colpi


CAMPI = ["frame", "tempo_s", "colpo", "velocita_uscita_kmh", "direzione", "angolo_gradi", "giocatore_x_m",
         "arrivo_x_m", "contatto_x_m", "contatto_y_m", "contatto_z_m", "punti_usati", "errore_px", "nota"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--dati", default="outputs/dati")
    ap.add_argument("--calibrazione")
    a = ap.parse_args()
    nome, colpi = analizza(a.video, a.dati, a.calibrazione)
    uscita = os.path.join(a.dati, nome + "_velocita.csv")
    with open(uscita, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPI, extrasaction="ignore")
        w.writeheader()
        w.writerows(colpi)
    print()
    for c in colpi:
        if c.get("velocita_uscita_kmh", "") != "":
            print(f"  frame {c['frame']:4d} {c['tempo_s']:5.2f} s  {c['colpo']:9s} {c['velocita_uscita_kmh']:4d} km/h  "
                  f"{c['direzione'] or '-':24s} angolo {c['angolo_gradi']:+5.1f}  giocatore x {c['giocatore_x_m']:.1f} m -> arrivo x {c['arrivo_x_m']:.1f} m")
        else:
            print(f"  frame {c['frame']:4d} {c['tempo_s']:5.2f} s  {c['colpo']:9s}  -   {c['nota']}")
    print(f"\nSalvato in {uscita}")
    # punti della pallina usati per ogni colpo, per disegnarli sul video
    json.dump(colpi, open(uscita.replace(".csv", "_punti.json"), "w"), default=float)


if __name__ == "__main__":
    main()
