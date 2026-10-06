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

I punti di TrackNet su palline ferme in campo si tolgono prima di tutto, gli
stessi di velocita_uscita.py (<video>_palline_ferme.csv); se il file manca
(risultati vecchi) si usano tutti i punti, come prima.

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

La pallina in uscita (6 ottobre, USCITA). Se cosi' la direzione non esce
(la pallina in arrivo non si vede, o ricompare troppo lontano dal colpo), si
cerca la pallina colpita che esce dal giocatore: la prima traccia coerente di
TrackNet (tracce: un punto per fotogramma, salti piccoli, una pallina per
traccia) che comincia durante il colpo, con il primo punto entro 0,8 altezze
del giocatore da un polso, almeno 6 punti e che si allontana dal giocatore.
Il contatto si prova da 0,5 a 2,5 fotogrammi prima del primo punto, nel
pixel dove portano i primi punti; stesse condizioni di sopra (4 px, 6 gradi).
Se la direzione esce, la riga va al fotogramma prima del primo punto (se non
c'e' gia' un'altra riga entro 15 frame). Sul video Giorgio da' il dritto
delle 14,0 s ("lungo linea"; riga da 13,4 a 14,03 s).
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
# Se il metodo normale non da' la direzione, si prova con la pallina IN USCITA (pallina_in_uscita,
# direzione_in_uscita): la direzione dai primi punti del volo, e la riga va li'. False = come prima (6 ottobre).
USCITA = True
USCITA_DIST_POLSO = 0.8     # primo punto della pallina in uscita entro 0,8 altezze del giocatore da un polso
USCITA_PASSI = (0.5, 1.0, 1.5, 2.0, 2.5)   # contatto provato a questi fotogrammi prima del primo punto
TRACCIA_SALTO = 0.08        # tracce coerenti: spostamento massimo per fotogramma, in altezze dell'immagine
TRACCIA_BUCO_S = 0.5        # tracce coerenti: secondi massimi senza punti dentro una traccia


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
    # lato di partenza (dritti e rovesci): il contatto qui e' un'ipotesi (coperto), quindi non vale come
    # "contatto"; si prova con i punti nel primo 1/6 s dopo il contatto, preso a meta' del tratto coperto
    # (come in velocita_rimbalzo.py), altrimenti i piedi
    f_meta = (f_perso + fs[0]) / 2
    piedi_meta = vu.piedi_a_terra(t, int(f_meta), cam)
    t_meta = (vu.istante(t, f_perso) + vu.istante(t, fs[0])) / 2
    partenza = vu.punto_di_partenza(t, cam, piedi_meta, punti={int(f): tuple(p) for f, p in zip(fs, P)},
                                    t_contatto=t_meta)
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
            # partenza dalla traiettoria, se c'e'; se no i piedi di questo tentativo, come prima
            x_part = partenza[0] if partenza[1] == "traiettoria" else float(piedi[0])
            angolo, x_arrivo, dire = vu.classifica_direzione(x_part, r["impact_xyz_m"], r["v0_ms"])
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
    if servizio or partenza[1] == "piedi":
        partenza = (float(piedi[0]), "piedi")
    return r, piedi, angolo, x_arrivo, dire, rimbalzo, min(angoli), max(angoli), partenza


def tracce(tn, da, a, h_img, fps):
    """
    Punti di TrackNet tra i frame da e a divisi in tracce coerenti, una pallina per traccia (dict frame -> punto):
    in ordine di tempo ogni punto va alla traccia il cui ultimo punto (o la posizione prevista con l'ultima
    velocita') e' piu' vicino, entro TRACCIA_SALTO altezze dell'immagine per fotogramma passato (al massimo 3) e con
    al massimo TRACCIA_BUCO_S secondi dall'ultimo punto; se no comincia una traccia nuova.
    """
    elenco = []
    for f in range(da, a + 1):
        if f not in tn:
            continue
        p = np.asarray(tn[f][:2], float)
        migliore, dist = None, None
        for tr in elenco:
            g = tr["ultimo"]
            salto = f - g
            if salto > TRACCIA_BUCO_S * fps:
                continue
            q = np.asarray(tn[g][:2], float)
            dd = float(np.linalg.norm(p - q))
            prec = [h for h in tr["punti"] if h < g]
            if prec:
                h = max(prec)
                v = (q - np.asarray(tn[h][:2], float)) / (g - h)
                dd = min(dd, float(np.linalg.norm(p - (q + v * salto))))
            if dd <= TRACCIA_SALTO * h_img * min(salto, 3) and (dist is None or dd < dist):
                migliore, dist = tr, dd
        if migliore is None:
            elenco.append({"punti": {f: tn[f]}, "ultimo": f})
        else:
            migliore["punti"][f] = tn[f]
            migliore["ultimo"] = f
    return [tr["punti"] for tr in elenco]


def pallina_in_uscita(t, tracknet, a, b, altezza_img):
    """
    La pallina colpita vista da TrackNet quando il contatto e' coperto: la prima traccia coerente (tracce) che
    comincia durante il colpo (tra l'inizio della finestra della posa e MARGINE_FINESTRA frame dopo la fine), con il
    primo punto entro USCITA_DIST_POLSO altezze del giocatore da un polso, almeno PUNTI_MINIMI punti e che si
    allontana dal giocatore (si_allontana). (frame dei punti, punti) dei primi 1/3 s, o None.
    """
    fps = t["fps"]
    n = max(4, int(round(vu.DURATA_DOPO_S * fps)))
    for tr in tracce(tracknet, a, b + vu.MARGINE_FINESTRA + int(round(CERCA_DOPO_S * fps)), altezza_img, fps):
        fs = sorted(tr)
        s0 = fs[0]
        if not (a <= s0 <= b + vu.MARGINE_FINESTRA) or len(fs) < PUNTI_MINIMI:
            continue
        box = t["box"][s0 - 1]
        h = box[3] - box[1]
        pol = t["polsi"][s0 - 1].reshape(2, 2)
        pol = pol[np.all(np.isfinite(pol), axis=1)]
        if not np.isfinite(h) or not len(pol):
            continue
        if np.min(np.linalg.norm(pol - np.asarray(tr[s0][:2], float), axis=1)) > USCITA_DIST_POLSO * h:
            continue
        fs = fs[:n]
        P = np.array([tr[f][:2] for f in fs], float)
        if not si_allontana(t, fs, P)[0]:
            continue
        return fs, P
    return None


def direzione_in_uscita(t, fs, P, cam, altezza_img, servizio=False):
    """
    Come direzione(), ma il contatto e' tra 0,5 e 2,5 fotogrammi prima del primo punto della pallina in uscita, nel
    pixel dove portano i suoi primi punti (non al polso: la racchetta e' piu' in la'). Stesse condizioni: fit
    migliore entro ERRORE_MAX, fit quasi buoni d'accordo entro SPREAD_ANGOLO_MAX. Stesso risultato di direzione()
    o None.
    """
    fps = t["fps"]
    k = min(4, len(fs))
    retta = [np.polyfit(fs[:k], P[:k, d], 1) for d in (0, 1)]
    fits = []
    for passo in USCITA_PASSI:
        fc = fs[0] - passo
        pixel = (np.polyval(retta[0], fc), np.polyval(retta[1], fc))
        piedi = vu.piedi_a_terra(t, max(1, int(fc)), cam)
        t_c = vu.istante(t, fs[0]) - passo / fps
        try:
            f_fit, fps_fit, tieni = vu.tempi_fit(t, fs)
            r = traiettoria_da_contatto(P[tieni], f_fit, fps_fit, cam, t_c, pixel, piedi)
        except (ValueError, IndexError, np.linalg.LinAlgError):
            continue
        partenza = vu.punto_di_partenza(t, cam, piedi, punti={int(f): tuple(p) for f, p in zip(fs, P)}, t_contatto=t_c)
        angolo, x_arrivo, dire = vu.classifica_direzione(partenza[0], r["impact_xyz_m"], r["v0_ms"])
        _, rimbalzo = calcolo.ground_crossing(r["impact_xyz_m"], r["v0_ms"])
        if servizio:
            dire = vu.classifica_servizio(float(piedi[0]), rimbalzo)
            partenza = (float(piedi[0]), "piedi")
        fits.append((r["rms_px"], r, piedi, angolo, x_arrivo, dire, rimbalzo, partenza))
    if not fits:
        return None
    migliore = min(fits, key=lambda x: x[0])
    if migliore[0] > ERRORE_MAX * altezza_img:
        return None
    limite = max(TOLLERANZA_FIT * migliore[0], migliore[0] + 0.5 * altezza_img / 1080)
    buoni = [x for x in fits if x[0] <= limite]
    angoli = [x[3] for x in buoni]
    if len({x[5].split(",")[0] for x in buoni}) > 1 or max(angoli) - min(angoli) > SPREAD_ANGOLO_MAX:
        return None
    _, r, piedi, angolo, x_arrivo, dire, rimbalzo, partenza = migliore
    return r, piedi, angolo, x_arrivo, dire, rimbalzo, min(angoli), max(angoli), partenza


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
    # i punti di TrackNet su palline ferme (velocita_uscita.py) si tolgono anche qui
    ferme = vu.leggi_palline_ferme(os.path.join(cartella_dati, nome + "_palline_ferme.csv"))
    tracknet = {f: p for f, p in tracknet.items() if f not in ferme}
    altezze = {int(f): float(b[3] - b[1]) for f, b in zip(t["frame"], t["box"]) if np.isfinite(b[3] - b[1])}
    finestre = vu.finestre_colpi(classi, n)

    campi_direzione = ("direzione", "angolo_gradi", "giocatore_x_m", "partenza_da", "_partenza_x_m", "arrivo_x_m",
                       "rimbalzo_x_m", "rimbalzo_y_m",
                       "contatto_x_m", "contatto_y_m", "contatto_z_m", "punti_usati", "errore_px", "_punti")
    def prova_in_uscita(c, a, b):
        """Il colpo c e' rimasto senza direzione: prova con la pallina in uscita (pallina_in_uscita). Se la
        direzione esce, la scrive e sposta la riga al contatto trovato (se non c'e' gia' un'altra riga entro 15
        frame). True se ha scritto la direzione."""
        if not USCITA:
            return False
        u = pallina_in_uscita(t, tracknet, a, b, altezza_img)
        if u is None:
            return False
        fs_u, P_u = u
        m_u = direzione_in_uscita(t, fs_u, P_u, cam, altezza_img, c["colpo"] == "servizio")
        if m_u is None:
            if verbose:
                print(f"frame {c['frame']} {c['colpo']}: pallina in uscita dal frame {fs_u[0]}, direzione non affidabile")
            return False
        r, piedi, angolo, x_arr, dire, rimbalzo, a_min, a_max, partenza = m_u
        vecchio = int(c["frame"])
        nuovo = fs_u[0] - 1
        if not any(x is not c and abs(int(x["frame"]) - nuovo) <= 15 for x in colpi):
            c["_riga_posa"] = (c["frame"], c["tempo_s"])     # per ripartire da qui se il passo viene rieseguito
            c.update({"frame": nuovo, "tempo_s": round(float(t["tempo"][nuovo - 1]), 3)})
        c.update({"partenza_da": partenza[1], "_partenza_x_m": round(partenza[0], 2)})
        if c["colpo"] == "servizio":
            c.update({"rimbalzo_x_m": round(float(rimbalzo[0]), 2), "rimbalzo_y_m": round(float(rimbalzo[1]), 2)})
        c.update({
            "direzione": dire, "angolo_gradi": round(angolo, 1),
            "giocatore_x_m": round(float(piedi[0]), 2), "arrivo_x_m": round(x_arr, 2),
            "contatto_x_m": round(float(r["impact_xyz_m"][0]), 2),
            "contatto_y_m": round(float(r["impact_xyz_m"][1]), 2),
            "contatto_z_m": round(float(r["impact_xyz_m"][2]), 2),
            "punti_usati": r["n_points"], "errore_px": round(r["rms_px"], 1),
            "nota": (f"contatto non visibile (pallina in uscita dal frame {fs_u[0]}, riga spostata dal {vecchio}): "
                     f"velocita' non disponibile; direzione dai frame {fs_u[0]}-{fs_u[-1]}, "
                     f"angolo tra {a_min:+.1f} e {a_max:+.1f} gradi"),
            "_punti": [(f, float(x), float(y)) for f, (x, y) in zip(fs_u, P_u)]})
        if verbose:
            print(f"frame {vecchio} {c['colpo']}: {dire} dalla pallina in uscita (frame {fs_u[0]}-{fs_u[-1]}, angolo "
                  f"{angolo:+.1f}, tra {a_min:+.1f} e {a_max:+.1f}); riga al frame {c['frame']}")
        return True

    for c in nascosti:
        # si riparte dalla riga come l'ha scritta velocita_uscita.py (se il passo viene rieseguito),
        # anche dal suo frame se la pallina in uscita l'aveva spostata
        if "_riga_posa" in c:
            c["frame"], c["tempo_s"] = c.pop("_riga_posa")
        fc = int(c["frame"])
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
        if not fs:
            prova_in_uscita(c, a, b)
            continue
        toll = TOLLERANZA_POSA_S * t["fps"]
        if fs and not (f_perso - toll <= fc <= fs[0] + toll):
            if verbose:
                print(f"frame {fc} {c['colpo']}: la pallina si perde al {f_perso} e ricompare al {fs[0]}, "
                      f"troppo lontano dal colpo: nessuna direzione")
            prova_in_uscita(c, a, b)
            continue
        if fs:
            ok, sp_palla, sp_gioc = si_allontana(t, fs, P)
            if not ok:
                if verbose:
                    print(f"frame {fc} {c['colpo']}: la pallina che ricompare non si allontana dal giocatore "
                          f"(si sposta di {sp_palla:.0f} px, il giocatore di {sp_gioc:.0f} px): nessuna direzione")
                prova_in_uscita(c, a, b)
                continue
        m = direzione(t, f_perso, fs, P, cam, altezza_img, c["colpo"] == "servizio") if fs else None
        if m is None:
            if verbose:
                print(f"frame {fc} {c['colpo']}: direzione non affidabile o pallina non ritrovata dopo")
            prova_in_uscita(c, a, b)
            continue
        r, piedi, angolo, x_arr, dire, rimbalzo, a_min, a_max, partenza = m
        c.update({"partenza_da": partenza[1], "_partenza_x_m": round(partenza[0], 2)})
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

    colpi.sort(key=lambda r: int(r["frame"]))      # una riga puo' essere stata spostata (pallina in uscita)
    vu.aggiungi_soglie(colpi)
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
