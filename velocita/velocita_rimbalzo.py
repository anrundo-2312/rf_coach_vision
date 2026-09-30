"""
velocita_rimbalzo.py - velocita' STIMATA DAL RIMBALZO per i colpi che il
calcolo normale non riesce a misurare.

    python velocita/velocita_rimbalzo.py --video inputs/<video>.mp4

Si esegue DOPO velocita_uscita.py e direzione_nascosta.py e PRIMA di
disegna_velocita.py. Guarda solo i colpi senza velocita' (contatto nascosto,
solo direzione, misura scartata). La velocita' di velocita_uscita.py non viene
mai toccata: quella stimata qui va in una colonna a parte,
velocita_rimbalzo_kmh, e sul video compare come "circa ... km/h (dal
rimbalzo)".

L'idea. Quando la pallina e' mossa o coperta vicino al giocatore, il calcolo
normale non ha punti buoni subito dopo il colpo. Ma spesso si vede dove la
pallina rimbalza nel campo avversario, e quel punto e' a terra: con la
calibrazione si sa esattamente dov'e' (non serve indovinare la distanza, come
per i punti in volo). Sapendo da dove parte la pallina (il giocatore, a 1 m
d'altezza; 2,6 m nel servizio), dove arriva (il rimbalzo) e quanto ci mette
(i frame tra colpo e rimbalzo), c'e' una sola traiettoria con gravita' e
resistenza dell'aria (lo stesso modello di rf_ball_exit_speed.py) che la
spiega: la sua velocita' iniziale e' la velocita' d'uscita stimata.

Passi, per ogni colpo senza velocita':
1. RIMBALZO: nei punti di TrackNet dopo il colpo, il primo punto piu' basso
   nell'immagine dei 3 prima e dei 2 dopo (la pallina scende verso terra e poi
   risale), che a terra cada nel campo avversario (tra 12,5 e 26 m dal fondo
   del giocatore, di lato entro 1,5 m dalle righe).
2. CONTATTO: si risale dal rimbalzo lungo i punti di TrackNet finche' sono
   continui (buchi di al massimo 4 frame, spostamenti di al massimo 0,3
   altezze del giocatore per frame). Il primo punto di questa traiettoria e' la
   pallina appena uscita dalla racchetta: il contatto e' mezzo frame prima. Ci
   si ferma anche dove la pallina cambia bruscamente velocita' o direzione (li'
   c'e' il colpo) e, se la riga viene da un contatto gia' trovato, non si va
   prima di quel frame (nel servizio il lancio che scende e la pallina colpita
   sono quasi in fila). Il primo punto deve cadere entro 25 frame dal colpo
   indicato dalla riga, se no il rimbalzo e' di un altro colpo.
3. VELOCITA' E DIREZIONE dalla traiettoria che va dal giocatore al rimbalzo
   nel tempo misurato (istanti veri se il video ha fotogrammi ripetuti, vedi
   fotogrammi.py). La direzione (lungo linea, incrociato...; nel servizio al T,
   al corpo, esterno) viene dal rimbalzo misurato e sostituisce quella
   ricavata dai punti in volo.

Prove: dove anche il calcolo normale funziona i due metodi vanno d'accordo
(Djokovic, dritto al 65: 123 km/h dal calcolo normale, 132 dal rimbalzo;
alcaraz, dritto al 275: 138 e 128). Precisione attesa circa +-15%: il punto
di contatto e' approssimato (piedi del giocatore e altezza fissa), il tempo di
volo ha un errore di circa un frame, la rotazione non e' nel modello.
Limite: il rimbalzo spesso non si vede (coperto dalla rete, dalla testa del
giocatore o dall'avversario); in quel caso non si stima niente.
"""

import argparse
import csv
import json
import os
import sys

import numpy as np
from scipy.optimize import least_squares

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
import rf_ball_exit_speed as calcolo  # noqa: E402
import velocita_uscita as vu  # noqa: E402
import fotogrammi  # noqa: E402
from calibra_campo import camera_da_json, carica_per_video  # noqa: E402

DURATA_MAX_S = 1.6          # il rimbalzo si cerca fino a 1,6 s dopo il colpo
PRIMA_S = 25                # la traiettoria in uscita deve partire entro 25 frame dal colpo della riga
BUCO_MAX = 6                # buco massimo (frame) nei punti di TrackNet lungo la traiettoria
SALTO_MAX_REL = 0.3         # spostamento massimo per frame, in altezze del giocatore
CAMBIO_MAX = 2.5            # la traiettoria finisce (all'indietro) dove la velocita' cambia di 2,5 volte
ANGOLO_MAX = 60             # ... o gira di piu' di 60 gradi: li' c'e' il colpo
MOTO_MINIMO_REL = 0.03      # i due controlli valgono solo se la pallina si muove abbastanza (altezze/frame)
CAMPO_Y = (12.5, 26.0)      # il rimbalzo deve cadere nel campo avversario (m dal fondo del giocatore)
CAMPO_X = (-1.5, 12.5)
VOLO_S = (0.25, 1.6)
ALTEZZA_CONTATTO = {"servizio": 2.6}   # m; tutti gli altri colpi 1,0 m
NOTA_RIMBALZO = "velocita' stimata dal rimbalzo"


def trova_rimbalzo(tn, da, a, cam):
    """Primo rimbalzo nel campo avversario tra i frame da..a: (frame, pixel, punto a terra) o None."""
    fs = [f for f in range(da, a + 1) if f in tn]
    for i in range(3, len(fs) - 2):
        if fs[i + 2] - fs[i - 3] > 10:
            continue
        y = tn[fs[i]][1]
        prima = [tn[g][1] for g in fs[i - 3:i]]
        dopo = [tn[g][1] for g in fs[i + 1:i + 3]]
        if not (all(y >= p for p in prima) and all(y > q for q in dopo)
                and y - min(prima) > 2 and y - min(dopo) > 3):
            continue
        terra = calcolo.ground_from_pixel(tn[fs[i]], cam)[:2]
        if CAMPO_Y[0] <= terra[1] <= CAMPO_Y[1] and CAMPO_X[0] <= terra[0] <= CAMPO_X[1]:
            return fs[i], tn[fs[i]], terra
    return None


def inizio_traiettoria(tn, f_rimbalzo, limite, altezze, ripetuti=None):
    """
    Primo frame della traiettoria continua di TrackNet che arriva al rimbalzo. Si risale dal
    rimbalzo e ci si ferma a un buco lungo, a un salto troppo grande o dove la pallina cambia
    bruscamente velocita' o direzione (il colpo: prima c'era la pallina in arrivo, o il lancio
    nel servizio). I fotogrammi ripetuti (fotogrammi.py) si saltano.
    """
    f, v_dopo = f_rimbalzo, None
    while True:
        prec = [g for g in range(f - 1, max(limite, f - BUCO_MAX - 1) - 1, -1)
                if g in tn and not (ripetuti is not None and ripetuti[g])]
        if not prec:
            return f
        g = prec[0]
        h = altezze.get(g) or altezze.get(f) or 300.0
        v = (np.asarray(tn[f], float) - np.asarray(tn[g], float)) / (f - g)
        a = float(np.linalg.norm(v))
        if a > SALTO_MAX_REL * h:
            return f
        if v_dopo is not None:
            b = float(np.linalg.norm(v_dopo))
            if max(a, b) > MOTO_MINIMO_REL * h and (max(a, b) > CAMBIO_MAX * max(min(a, b), 1e-6)
                                                   or np.dot(v, v_dopo) < np.cos(np.radians(ANGOLO_MAX)) * a * b):
                return f
        v_dopo = v
        f = g


def stima(t, tn, altezze, cam, riga):
    """Stima dal rimbalzo per una riga senza velocita' (dizionario da aggiungere alla riga) o None."""
    fc = int(riga["frame"])
    fps = t["fps"]
    rimb = trova_rimbalzo(tn, fc - PRIMA_S, fc + int(DURATA_MAX_S * fps), cam)
    if rimb is None:
        return None
    fb, pb, terra = rimb
    ripetuti = None if t.get("tempi") is None else t["tempi"]["dup"]
    # se la riga viene da un contatto trovato (cambio di direzione vicino al polso: righe "solo
    # direzione", "misura scartata"...), la pallina in uscita non puo' partire prima di quel frame.
    # Serve nel servizio, dove il lancio che scende e la pallina colpita sono quasi in fila.
    contatto_trovato = not str(riga.get("nota", "")).startswith("contatto non visibile")
    limite = fc + 1 if contatto_trovato else fc - PRIMA_S - BUCO_MAX
    s = inizio_traiettoria(tn, fb, limite, altezze, ripetuti)
    if abs(s - fc) > PRIMA_S or s >= fb:
        return None
    # contatto mezzo frame prima del primo punto in uscita; istanti veri se ci sono ripetuti
    fps_vero = fps if t.get("tempi") is None else t["tempi"]["fps"]
    t_contatto = vu.istante(t, s) - 0.5 / fps_vero
    volo = vu.istante(t, fb) - t_contatto
    if not VOLO_S[0] <= volo <= VOLO_S[1]:
        return None
    f_contatto = max(1, s - 1)
    piedi = vu.piedi_a_terra(t, f_contatto, cam)
    p0 = np.array([piedi[0], piedi[1], ALTEZZA_CONTATTO.get(riga["colpo"], 1.0)])
    arrivo = np.array([terra[0], terra[1], 0.0])
    sol = least_squares(lambda v: calcolo.simulate(p0, v, np.array([volo]))[-1] - arrivo, (arrivo - p0) / volo)
    v0 = sol.x
    kmh = float(np.linalg.norm(v0) * 3.6)
    media = float(np.linalg.norm(arrivo[:2] - p0[:2]) / volo * 3.6)
    lo, hi = vu.VELOCITA_PLAUSIBILE
    if not lo <= kmh <= hi:
        return None
    angolo, x_arrivo, direzione = vu.classifica_direzione(piedi[0], p0, v0)
    out = {"velocita_rimbalzo_kmh": round(kmh), "angolo_gradi": round(angolo, 1),
           "giocatore_x_m": round(float(piedi[0]), 2), "arrivo_x_m": round(x_arrivo, 2),
           "contatto_x_m": round(float(p0[0]), 2), "contatto_y_m": round(float(p0[1]), 2),
           "contatto_z_m": round(float(p0[2]), 2),
           "rimbalzo_x_m": round(float(terra[0]), 2), "rimbalzo_y_m": round(float(terra[1]), 2),
           "_punti": [(f, float(tn[f][0]), float(tn[f][1])) for f in range(s, fb + 1) if f in tn]}
    if riga["colpo"] == "servizio":
        direzione = vu.classifica_servizio(float(piedi[0]), terra)
    out["direzione"] = direzione
    nota = (f"{NOTA_RIMBALZO} (margine circa +-15%): contatto ~frame {f_contatto}, rimbalzo al frame {fb} "
            f"a ({terra[0]:.1f}; {terra[1]:.1f}) m, volo {volo:.2f} s, media fino al rimbalzo {media:.0f} km/h")
    if riga.get("direzione") and riga["direzione"] != direzione:
        nota += f"; dai punti in volo era \"{riga['direzione']}\""
    if riga.get("nota"):
        nota += f". Prima: {riga['nota']}"
    out["nota"] = nota
    return out


def aggiorna(video, cartella_dati="outputs/dati", calibrazione=None, verbose=True):
    nome = os.path.splitext(os.path.basename(video))[0]
    p_json = os.path.join(cartella_dati, nome + "_velocita_punti.json")
    colpi = json.load(open(p_json))
    t = vu.leggi_tracking(os.path.join(cartella_dati, nome + "_tracking.csv"))
    t["tempi"] = fotogrammi.tempi_reali(video, cartella_dati, t["fps"], verbose=False)
    cal, _ = carica_per_video(video, calibrazione)
    cam = camera_da_json(cal)
    tn = {int(f): tuple(p) for f, p, v in zip(t["frame"], t["palla"], t["vista"]) if v}
    altezze = {int(f): float(b[3] - b[1]) for f, b in zip(t["frame"], t["box"]) if np.isfinite(b[3] - b[1])}
    usati = set()
    for c in colpi:
        if c.get("velocita_uscita_kmh", "") != "":
            continue
        if str(c.get("nota", "")).startswith(NOTA_RIMBALZO):
            continue                                  # gia' stimata (passo rieseguito)
        s = stima(t, tn, altezze, cam, c)
        if s is None:
            if verbose:
                print(f"frame {c['frame']} {c['colpo']}: rimbalzo non visibile o non di questo colpo")
            continue
        chiave = s["nota"].split("rimbalzo al frame ")[1].split()[0]
        if chiave in usati:                           # lo stesso rimbalzo non vale per due colpi
            continue
        usati.add(chiave)
        if c["colpo"] != "servizio":
            s.pop("rimbalzo_x_m"), s.pop("rimbalzo_y_m")
        c.update(s)
        if verbose:
            print(f"frame {c['frame']} {c['colpo']}: circa {s['velocita_rimbalzo_kmh']} km/h, {s['direzione']}")
    with open(os.path.join(cartella_dati, nome + "_velocita.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=vu.CAMPI, extrasaction="ignore")
        w.writeheader()
        w.writerows(colpi)
    json.dump(colpi, open(p_json, "w"), default=float)
    return colpi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--dati", default="outputs/dati")
    ap.add_argument("--calibrazione")
    a = ap.parse_args()
    aggiorna(a.video, a.dati, a.calibrazione)


if __name__ == "__main__":
    main()
