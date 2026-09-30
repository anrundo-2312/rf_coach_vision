"""
direzione_nascosta.py - direzione dei colpi in cui la pallina e' coperta dal
giocatore proprio al contatto (per esempio il rovescio di Nicola al frame 223).

    python velocita/direzione_nascosta.py --video inputs/<video>.mp4

Si esegue DOPO velocita_uscita.py e PRIMA di disegna_velocita.py. Guarda solo i
colpi che velocita_uscita.py ha scritto senza velocita' con la nota "contatto
non visibile", e a quelli aggiunge la direzione, se si riesce a ricavarla con
sicurezza. La velocita' non viene toccata: resta "non disponibile" per questi
colpi e identica per tutti gli altri. Non modifica nessun altro file del
calcolo: aggiorna solo outputs/dati/<video>_velocita.csv e _velocita_punti.json.

Perche' la direzione si puo' avere e la velocita' no. Dopo il colpo, vista
dall'alto, la pallina va praticamente dritta: la gravita' la tira verso il
basso e l'aria la rallenta, ma nessuna delle due la fa girare di lato. Quindi
basta vedere un pezzo di volo DOPO il tratto coperto per sapere dove va,
purche' si sappia da dove parte (vicino al giocatore). La velocita' invece
cala lungo il volo e per risalire a quella di uscita serve l'istante esatto
del contatto, che e' proprio nel tratto coperto: sul rovescio di Nicola,
spostandolo di pochi frame, la velocita' va da 50 a oltre 200 km/h.

Come funziona, per ogni colpo con il contatto nascosto:
1. la pallina in arrivo si perde a un certo frame (l'ultimo punto seguito dal
   rilevatore di colore) e si cercano i punti di TrackNet nei 0,75 s dopo;
2. si tengono solo i punti che stanno su una stessa curva liscia (una
   parabola in x e y nel tempo, quella che passa per piu' punti): gli altri
   sono falsi rilevamenti (nel rovescio di Nicola i frame 232-234);
3. non sapendo quando e dove la racchetta ha colpito, si prova come contatto
   ogni frame del tratto coperto, a ciascuno dei due polsi, e per ognuno si fa
   lo stesso calcolo della traiettoria di velocita_uscita.py (exit_speed del
   file rf_ball_exit_speed.py, non modificato);
4. la direzione si scrive solo se tutti i calcoli che spiegano bene i punti
   (errore fino a 1,5 volte il migliore) danno la stessa risposta, con angoli
   entro 6 gradi. Altrimenti niente.
Prima di tutto pero' il colpo (istante stimato dalla posa) deve cadere nel
tratto in cui la pallina e' coperta, con 0,25 s di tolleranza: se la pallina si
e' persa molto prima del colpo, i punti che si rivedono appartengono a un'altra
parte dello scambio (successo sul video swing_vision_test1_trim: colpo al frame
1379, pallina persa al 1247).
Poi la pallina che ricompare deve allontanarsi dal giocatore PER IL SUO MOTO:
nel tratto usato la sua distanza dai piedi del giocatore deve crescere e lei
deve spostarsi nell'immagine piu' del giocatore. Se la distanza cresce solo
perche' si sposta il giocatore, i punti sono un oggetto quasi fermo, non la
pallina colpita (video alcaraz, frame 1302: giocatore che cammina, pallina
spostata di 37 px contro i 149 px del giocatore; dava un falso "al T").

Se il video ha fotogrammi ripetuti (conversione, vedi fotogrammi.py) il calcolo
usa gli istanti veri: su alcaraz cosi' escono le direzioni dei dritti al 709 e
dei rovesci al 1015 e al 1152, prima non stabili.

Prove: rovescio di Nicola -> "dal centro verso sinistra", arrivo a 3,7 m
dalla riga laterale sinistra; la mappa di SwingVision mette il rimbalzo a
circa 3,3 m. Sul video di Djokovic, cancellando la pallina attorno al
contatto (6 prove, 13-29 frame), non ha mai dato una direzione sbagliata ma
non l'ha nemmeno mai data: quando c'e' e' affidabile, ma spesso manca.
"""

import argparse
import csv
import json
import os
import sys
from itertools import combinations

import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
import rf_ball_exit_speed as calcolo  # noqa: E402
import palla_locale  # noqa: E402
import velocita_uscita as vu  # noqa: E402
import fotogrammi  # noqa: E402
from calibra_campo import camera_da_json, carica_per_video, leggi_fotogramma  # noqa: E402

CERCA_DOPO_S = 0.75         # la pallina deve ricomparire entro 0,75 s da quando si perde
PUNTI_MINIMI = 6            # punti visibili necessari dopo il tratto coperto
SCARTO_CURVA = 6 / 1080     # punti a piu' di 6 px (su 1080) dalla curva liscia: falsi rilevamenti
ERRORE_MAX = 4 / 1080       # il fit migliore deve spiegare i punti entro 4 px (su 1080)
TOLLERANZA_FIT = 1.5        # fit "quasi buoni": errore fino a 1,5 volte il migliore (e almeno +0,5 px)
SPREAD_ANGOLO_MAX = 6.0     # e i loro angoli entro 6 gradi
# Il colpo (istante stimato dalla posa) deve cadere nel tratto in cui la pallina e' coperta,
# con al massimo 0,25 s di tolleranza: se la pallina si e' persa molto prima o ricompare
# molto prima del colpo, i punti visibili appartengono a un'altra parte dello scambio.
TOLLERANZA_POSA_S = 0.25
NOTA_BASE = "contatto non visibile: pallina coperta o persa"


def piedi_px(t, f):
    """Punto a terra del giocatore nell'immagine: media delle caviglie, se no il fondo del box."""
    c = t["caviglie"][f - 1].reshape(2, 2)
    c = c[np.all(np.isfinite(c), axis=1)]
    if len(c):
        return c.mean(axis=0)
    b = t["box"][f - 1]
    return np.array([(b[0] + b[2]) / 2, b[3]])


def si_allontana(t, fs, P):
    """
    (vero/falso, spostamento pallina px, spostamento giocatore px) nel tratto fs:
    vero se la pallina si allontana dal giocatore e si sposta piu' di lui.
    Se la posizione del giocatore manca non si puo' giudicare e si lascia passare.
    """
    g0, g1 = piedi_px(t, fs[0]), piedi_px(t, fs[-1])
    palla = float(np.linalg.norm(P[-1] - P[0]))
    if not (np.all(np.isfinite(g0)) and np.all(np.isfinite(g1))):
        return True, palla, float("nan")
    giocatore = float(np.linalg.norm(g1 - g0))
    cresce = np.linalg.norm(P[-1] - g1) > np.linalg.norm(P[0] - g0)
    return bool(cresce and palla > giocatore), palla, giocatore


def traiettoria_da_contatto(P, fs, fps, cam, t_contatto, pixel_contatto, piedi):
    """
    Lo stesso calcolo di velocita_uscita.misura (exit_speed con forward e depth_tol),
    ma con istante e pixel del contatto dati da noi: exit_speed li ricaverebbe dal
    cambio di direzione della pallina, che qui non si vede. Per non modificare
    rf_ball_exit_speed.py si sostituisce per un momento la sua funzione che trova
    l'impatto, e la si rimette subito dopo.
    """
    originale = calcolo.refine_impact_visual
    calcolo.refine_impact_visual = lambda *a, **k: (t_contatto, np.asarray(pixel_contatto, float),
                                                    float("nan"), None)
    try:
        return calcolo.exit_speed(P, np.asarray(fs), fps, cam, 0, impact_mode="visual", n_frames=len(fs),
                                  player_ground_xy=piedi, return_debug=True, forward=True,
                                  depth_tol=vu.TOLLERANZA_PROFONDITA)
    finally:
        calcolo.refine_impact_visual = originale


def punti_dopo(f_perso, tracknet, fps, altezza_img):
    """Punti di TrackNet dopo il tratto coperto, solo quelli su una stessa curva liscia (RANSAC)."""
    ultimo = f_perso + int(round(CERCA_DOPO_S * fps))
    fs = np.array([f for f in sorted(tracknet) if f_perso < f <= ultimo], float)
    if len(fs) < PUNTI_MINIMI:
        return [], None
    P = np.array([tracknet[int(f)] for f in fs], float)
    soglia = SCARTO_CURVA * altezza_img
    migliore = None
    for terna in combinations(range(len(fs)), 3):
        idx = list(terna)
        curva = np.column_stack([np.polyval(np.polyfit(fs[idx], P[idx, d], 2), fs) for d in (0, 1)])
        scarti = np.linalg.norm(P - curva, axis=1)
        dentro = scarti <= soglia
        chiave = (int(dentro.sum()), -float(scarti[dentro].sum()))
        if migliore is None or chiave > migliore[0]:
            migliore = (chiave, dentro)
    dentro = migliore[1]
    if dentro.sum() < PUNTI_MINIMI:
        return [], None
    n = max(4, int(round(vu.DURATA_DOPO_S * fps)))
    return [int(f) for f in fs[dentro]][:n], P[dentro][:n]


def direzione(t, f_perso, fs, P, cam, altezza_img, servizio=False):
    """
    Prova come contatto ogni frame tra f_perso e fs[0], a ciascun polso. Restituisce
    (fit migliore, piedi, angolo, arrivo, direzione, rimbalzo, angolo min, angolo max)
    oppure None se i fit quasi buoni non sono d'accordo.
    """
    fps = t["fps"]
    fits = []
    for fc in range(f_perso + 1, fs[0]):
        piedi = vu.piedi_a_terra(t, fc, cam)
        for polso in t["polsi"][fc - 1].reshape(2, 2):
            if not np.all(np.isfinite(polso)):
                continue
            try:
                f_fit, fps_fit, tieni = vu.tempi_fit(t, fs)      # istanti veri se ci sono fotogrammi ripetuti
                r = traiettoria_da_contatto(P[tieni], f_fit, fps_fit, cam, vu.istante(t, fc), polso, piedi)
            except (ValueError, IndexError, np.linalg.LinAlgError):
                continue
            angolo, x_arrivo, dire = vu.classifica_direzione(piedi[0], r["impact_xyz_m"], r["v0_ms"])
            _, rimbalzo = calcolo.ground_crossing(r["impact_xyz_m"], r["v0_ms"])
            if servizio:
                dire = vu.classifica_servizio(float(piedi[0]), rimbalzo)
            fits.append((r["rms_px"], r, piedi, angolo, x_arrivo, dire, rimbalzo))
    if not fits:
        return None
    migliore = min(fits, key=lambda x: x[0])
    if migliore[0] > ERRORE_MAX * altezza_img:
        return None
    limite = max(TOLLERANZA_FIT * migliore[0], migliore[0] + 0.5 * altezza_img / 1080)
    buoni = [x for x in fits if x[0] <= limite]
    angoli = [x[3] for x in buoni]
    classi = {x[5].split(",")[0] for x in buoni}          # per il servizio basta la fascia
    if len(classi) > 1 or max(angoli) - min(angoli) > SPREAD_ANGOLO_MAX:
        return None
    _, r, piedi, angolo, x_arrivo, dire, rimbalzo = migliore
    return r, piedi, angolo, x_arrivo, dire, rimbalzo, min(angoli), max(angoli)


def aggiorna(video, cartella_dati="outputs/dati", calibrazione=None, verbose=True):
    nome = os.path.splitext(os.path.basename(video))[0]
    p_json = os.path.join(cartella_dati, nome + "_velocita_punti.json")
    colpi = json.load(open(p_json))
    nascosti = [c for c in colpi if c.get("velocita_uscita_kmh", "") == ""
                and str(c.get("nota", "")).startswith("contatto non visibile")]
    if not nascosti:
        if verbose:
            print("Nessun colpo con il contatto nascosto: niente da fare.")
        return colpi

    t = vu.leggi_tracking(os.path.join(cartella_dati, nome + "_tracking.csv"))
    t["tempi"] = fotogrammi.tempi_reali(video, cartella_dati, t["fps"], verbose=False)
    classi = vu.leggi_colpi(os.path.join(cartella_dati, nome + "_colpi.csv"))
    cal, _ = carica_per_video(video, calibrazione)
    cam = camera_da_json(cal)
    altezza_img = leggi_fotogramma(video, 0)[0].shape[0]
    n = len(t["frame"])
    tracknet = {int(f): tuple(p) for f, p, v in zip(t["frame"], t["palla"], t["vista"]) if v}
    altezze = {int(f): float(b[3] - b[1]) for f, b in zip(t["frame"], t["box"]) if np.isfinite(b[3] - b[1])}
    finestre = vu.finestre_colpi(classi, n)

    campi_direzione = ("direzione", "angolo_gradi", "giocatore_x_m", "arrivo_x_m", "rimbalzo_x_m", "rimbalzo_y_m",
                       "contatto_x_m", "contatto_y_m", "contatto_z_m", "punti_usati", "errore_px", "_punti")
    for c in nascosti:
        fc = int(c["frame"])
        # si riparte dalla riga come l'ha scritta velocita_uscita.py (se il passo viene rieseguito)
        for k in campi_direzione:
            c.pop(k, None)
        c["nota"] = NOTA_BASE
        finestra = [(a, b) for a, b in finestre if a - vu.MARGINE_FINESTRA <= fc <= b + vu.MARGINE_FINESTRA]
        if not finestra:
            continue
        a, b = finestra[0]
        traccia = palla_locale.segui(video, max(1, a - vu.MARGINE_FINESTRA), min(n, b + vu.MARGINE_FINESTRA),
                                     tracknet, altezze)
        f_perso = max((f for f in traccia if f <= fc), default=None)
        fs, P = punti_dopo(f_perso, tracknet, t["fps"], altezza_img) if f_perso else ([], None)
        toll = TOLLERANZA_POSA_S * t["fps"]
        if fs and not (f_perso - toll <= fc <= fs[0] + toll):
            if verbose:
                print(f"frame {fc} {c['colpo']}: la pallina si perde al {f_perso} e ricompare al {fs[0]}, "
                      f"troppo lontano dal colpo: nessuna direzione")
            continue
        if fs:
            ok, sp_palla, sp_gioc = si_allontana(t, fs, P)
            if not ok:
                if verbose:
                    print(f"frame {fc} {c['colpo']}: la pallina che ricompare non si allontana dal giocatore "
                          f"(si sposta di {sp_palla:.0f} px, il giocatore di {sp_gioc:.0f} px): nessuna direzione")
                continue
        m = direzione(t, f_perso, fs, P, cam, altezza_img, c["colpo"] == "servizio") if fs else None
        if m is None:
            if verbose:
                print(f"frame {fc} {c['colpo']}: direzione non affidabile o pallina non ritrovata dopo")
            continue
        r, piedi, angolo, x_arr, dire, rimbalzo, a_min, a_max = m
        if c["colpo"] == "servizio":
            c.update({"rimbalzo_x_m": round(float(rimbalzo[0]), 2), "rimbalzo_y_m": round(float(rimbalzo[1]), 2)})
        c.update({
            "direzione": dire, "angolo_gradi": round(angolo, 1),
            "giocatore_x_m": round(float(piedi[0]), 2), "arrivo_x_m": round(x_arr, 2),
            "contatto_x_m": round(float(r["impact_xyz_m"][0]), 2),
            "contatto_y_m": round(float(r["impact_xyz_m"][1]), 2),
            "contatto_z_m": round(float(r["impact_xyz_m"][2]), 2),
            "punti_usati": r["n_points"], "errore_px": round(r["rms_px"], 1),
            "nota": (f"contatto non visibile (pallina persa al frame {f_perso}, ricompare al {fs[0]}): "
                     f"velocita' non disponibile; direzione dai frame {fs[0]}-{fs[-1]}, "
                     f"angolo tra {a_min:+.1f} e {a_max:+.1f} gradi"),
            "_punti": [(f, float(x), float(y)) for f, (x, y) in zip(fs, P)]})
        if verbose:
            print(f"frame {fc} {c['colpo']}: {dire} (angolo {angolo:+.1f}, tra {a_min:+.1f} e {a_max:+.1f}), "
                  f"dai frame {fs[0]}-{fs[-1]}")

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
