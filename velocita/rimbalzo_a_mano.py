"""
rimbalzo_a_mano.py - rimbalzi indicati a mano, dove il programma non li trova (17 ottobre).

    python velocita/rimbalzo_a_mano.py --video inputs/<video>.mp4 --cartella <cartella dei rimbalzi>

Si esegue DOPO velocita_rimbalzo.py e PRIMA di disegna_velocita.py. Se per il video
non c'e' nessun rimbalzo indicato, non fa niente.

Il file e' <cartella>/<video>.csv, con il nome del video senza il suffisso dei
pesi (jimmy_mnason_final_test2.csv vale anche per jimmy_mnason_final_test2_run3b).
Una riga per colpo:

    colpo,rimbalzo_frame,rimbalzo_x,rimbalzo_y,contatto_frame
    52,118,922,413,55.5

  colpo           fotogramma del colpo (colonna frame di <video>_velocita.csv); si prende la
                  riga piu' vicina, entro TOLLERANZA_COLPO fotogrammi
  rimbalzo_frame  fotogramma (numerato da 1, come nel tracking) in cui la pallina tocca terra
  rimbalzo_x/_y   pixel del centro della pallina in quel fotogramma, nella risoluzione del video
  contatto_frame  facoltativo: fotogramma del contatto (anche con il mezzo, 55.5). Se manca,
                  come il passo 5 di velocita_rimbalzo.py: meta' del tratto coperto, o il
                  fotogramma della riga + 0,5

Il file si scrive a mano o con velocita/segna_rimbalzo.py (clic sul video).

Il rimbalzo indicato vale come un RIMBALZO RICOSTRUITO del passo 5 di
velocita_rimbalzo.py: stesse formule, stessa nota iniziale (NOTA_RICOSTRUITO),
velocita_fonte "stimata, rimbalzo ricostruito", rimbalzo_trovato_come
"ricostruito". Quindi sul video e nella scheda compare come gli altri rimbalzi
ricostruiti: "circa X km/h (rimbalzo ricostruito)", margine circa +-20%,
cerchio vuoto sulla mappa. Solo il resto della nota nel CSV, che non si
mostra, dice che il punto viene da questo file (serve per non contarlo
quando si valuta il programma).

  - colpi senza velocita' d'uscita: velocita' stimata dal rimbalzo, media del volo,
    direzione dal rimbalzo, dentro/fuori (come il passo 5);
  - colpi con la velocita' d'uscita misurata: rimbalzo, media del volo (come il
    passo 7, mai piu' alta dell'uscita) e dentro/fuori; la velocita' non cambia.
  - camera mossa ("moderata" o "eccessiva", camera.py): niente, come nel resto
    del programma (la calibrazione al fondo non e' affidabile).
"""

import argparse
import csv
import json
import os
import re
import sys

import cv2
import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
import camera  # noqa: E402
import fotogrammi  # noqa: E402
import velocita_rimbalzo as vr  # noqa: E402
import velocita_uscita as vu  # noqa: E402
from calibra_campo import camera_da_json, carica_per_video  # noqa: E402

CARTELLA = os.path.join(QUI, "rimbalzi_a_mano")
SUFFISSO_PESI = re.compile(r"_(run\w+|badminton)$")   # etichetta dei pesi (ball_tracknet.etichetta_pesi): _run3b, _run4...
TOLLERANZA_COLPO = 12           # fotogrammi tra il colpo indicato e la riga del CSV
NOTA_FILE = "dal file dei rimbalzi a mano"


def nome_base(nome):
    """Il nome del video senza il suffisso dei pesi (copia fatta dal notebook: <video>_run3b)."""
    return SUFFISSO_PESI.sub("", nome)


def file_rimbalzi(nome, cartella):
    for n in (nome, nome_base(nome)):
        p = os.path.join(cartella, n + ".csv")
        if os.path.exists(p):
            return p
    return None


def leggi_rimbalzi(percorso):
    out = []
    for r in csv.DictReader(open(percorso, encoding="utf-8-sig")):
        if not (r.get("colpo") or "").strip():
            continue
        fc = (r.get("contatto_frame") or "").strip()
        out.append({"colpo": int(float(r["colpo"])), "fb": int(float(r["rimbalzo_frame"])),
                    "px": (float(r["rimbalzo_x"]), float(r["rimbalzo_y"])),
                    "fc": float(fc) if fc else None})
    return out


def applica(video, cartella_dati="outputs/dati", cartella=CARTELLA, calibrazione=None, verbose=True):
    nome = os.path.splitext(os.path.basename(video))[0]
    p = file_rimbalzi(nome, cartella)
    if p is None:
        if verbose:
            print(f"nessun rimbalzo indicato a mano per {nome} (cartella {cartella})")
        return None
    indicati = leggi_rimbalzi(p)
    p_json = os.path.join(cartella_dati, nome + "_velocita_punti.json")
    colpi = json.load(open(p_json))
    t = vu.leggi_tracking(os.path.join(cartella_dati, nome + "_tracking.csv"))
    t["tempi"] = fotogrammi.tempi_reali(video, cartella_dati, t["fps"], verbose=False)
    fps_vero = t["fps"] if t.get("tempi") is None else t["tempi"]["fps"]
    cal, _ = carica_per_video(video, calibrazione)
    cam = camera_da_json(cal)
    tab_cam = camera.carica(cartella_dati, video)
    cap = cv2.VideoCapture(video)
    altezza_img = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    cap.release()
    tn = {int(f): tuple(q) for f, q, v in zip(t["frame"], t["palla"], t["vista"]) if v}
    ferme = vu.leggi_palline_ferme(os.path.join(cartella_dati, nome + "_palline_ferme.csv"))
    tn = {f: q for f, q in tn.items() if f not in ferme}
    cambiati = 0
    for m in indicati:
        c = min(colpi, key=lambda c: abs(int(c["frame"]) - m["colpo"]))
        fr = int(c["frame"])
        if abs(fr - m["colpo"]) > TOLLERANZA_COLPO:
            print(f"colpo {m['colpo']}: nessuna riga entro {TOLLERANZA_COLPO} fotogrammi, saltato")
            continue
        liv, px_cam = camera.livello(tab_cam, fr, altezza_img)
        if liv != "ok":
            print(f"colpo {fr}: camera {liv} ({px_cam:.0f} px a 1080p), rimbalzo non usato")
            continue
        # una seconda esecuzione riparte dalla riga com'era prima (stesso risultato a ogni giro)
        if "_riga_prima_a_mano" in c:
            prima = c["_riga_prima_a_mano"]
            c.clear()
            c.update(json.loads(json.dumps(prima)))
            c["_riga_prima_a_mano"] = prima
        else:
            c["_riga_prima_a_mano"] = json.loads(json.dumps(c, default=float))
        fb = m["fb"]
        terra = vr.rimbalzo_a_terra(m["px"], camera.camera_al_frame(cam, tab_cam, fb))
        if not (vr.CAMPO_Y[0] <= terra[1] <= vr.CAMPO_Y[1] and vr.CAMPO_X[0] <= terra[0] <= vr.CAMPO_X[1]):
            print(f"colpo {fr}: il punto indicato cade fuori dal campo avversario ({terra[0]:.1f}; {terra[1]:.1f}) m, "
                  "saltato (controlla fotogramma e pixel)")
            continue
        t_b = vu.istante(t, fb)
        x, y = float(terra[0]), float(terra[1])
        if c.get("velocita_uscita_kmh", "") in ("", None):
            # come il passo 5 (stima_ricostruita), con il rimbalzo indicato al posto di quello delle curve
            f_c = m["fc"] if m["fc"] is not None else (vr.contatto_per_ricostruito(c) or fr + 0.5)
            cam_c = camera.camera_al_frame(cam, tab_cam, fr)
            v = vr.velocita_da_volo(t, cam_c, c, f_c, t_b, terra, tn)
            if v is None:
                print(f"colpo {fr}: volo non plausibile con il contatto al {f_c} e il rimbalzo al {fb}, saltato")
                continue
            v0, kmh, media, volo, piedi, p0, partenza = v
            nota = (f"{vr.NOTA_RICOSTRUITO} (margine circa +-20%): rimbalzo ricostruito {NOTA_FILE} "
                    f"(rimbalzo al frame {fb}) a ({x:.1f}; {y:.1f}) m, contatto ~frame {f_c:.0f}, "
                    f"volo {volo:.2f} s, media fino al rimbalzo {media:.0f} km/h")
            punti = [(f, float(tn[f][0]), float(tn[f][1])) for f in range(int(np.ceil(f_c)), fb + 1) if f in tn]
            campi = vr.riga_stima(c, v0, kmh, piedi, p0, terra, punti, nota, partenza, media)
            for k in ("velocita_rimbalzo_kmh", "velocita_media_kmh", "rimbalzo_trovato_x_m", "rimbalzo_trovato_y_m",
                      "rimbalzo_trovato_frame", "rimbalzo_trovato_come"):
                c.pop(k, None)
            # come applica() di velocita_rimbalzo.aggiorna
            c.update({"rimbalzo_trovato_x_m": campi["rimbalzo_x_m"], "rimbalzo_trovato_y_m": campi["rimbalzo_y_m"],
                      "rimbalzo_trovato_frame": int(fb), "rimbalzo_trovato_come": "ricostruito"})
            if c["colpo"] != "servizio":
                campi.pop("rimbalzo_x_m"), campi.pop("rimbalzo_y_m")
            c.update(campi)
            c["velocita_fonte"] = vu.FONTE_RICOSTRUITA
            c["velocita_media_fonte"] = getattr(vr, "FONTE_MEDIA_MISURATA", "misurata")
            if verbose:
                print(f"colpo {fr} {c['colpo']}: circa {campi['velocita_rimbalzo_kmh']} km/h (rimbalzo ricostruito), "
                      f"media {campi['velocita_media_kmh']} km/h, {campi['direzione']}; rimbalzo al {fb} a "
                      f"({x:.2f}; {y:.2f}) m, contatto ~{f_c}")
        else:
            # velocita' d'uscita misurata: solo rimbalzo, media del volo (come il passo 7) e dentro/fuori
            f_c = m["fc"] if m["fc"] is not None else fr + 0.5
            t_c = vu.istante(t, int(f_c)) + (f_c - int(f_c)) / fps_vero
            volo = t_b - t_c
            if not vr.VOLO_S[0] <= volo <= vr.VOLO_S[1] or c.get("contatto_x_m", "") in ("", None):
                print(f"colpo {fr}: volo di {volo:.2f} s o contatto mancante, saltato")
                continue
            media = float(np.hypot(x - float(c["contatto_x_m"]), y - float(c["contatto_y_m"]))) / volo * 3.6
            if media > float(c["velocita_uscita_kmh"]):
                print(f"colpo {fr}: media {media:.0f} km/h piu' alta dell'uscita {c['velocita_uscita_kmh']}: "
                      "rimbalzo non usato (controlla fotogramma e pixel)")
                continue
            c.update({"rimbalzo_trovato_x_m": round(x, 2), "rimbalzo_trovato_y_m": round(y, 2),
                      "rimbalzo_trovato_frame": int(fb), "rimbalzo_trovato_come": "ricostruito",
                      "velocita_media_kmh": round(media),
                      "velocita_media_fonte": getattr(vr, "FONTE_MEDIA_MISURATA", "misurata")})
            nota = c.get("nota", "")
            c["nota"] = (nota + "; " if nota else "") + (
                f"rimbalzo ricostruito {NOTA_FILE} (rimbalzo al frame {fb}) a ({x:.1f}; {y:.1f}) m, "
                f"media del volo {media:.0f} km/h (volo {volo:.2f} s)")
            if verbose:
                print(f"colpo {fr} {c['colpo']}: rimbalzo ricostruito al {fb} a ({x:.2f}; {y:.2f}) m, "
                      f"media del volo {media:.0f} km/h (uscita {c['velocita_uscita_kmh']})")
        cambiati += 1
    if not cambiati:
        return colpi
    # colonne che dipendono dal rimbalzo e dal contatto, come alla fine di velocita_rimbalzo.aggiorna
    vu.aggiungi_soglie(colpi)
    vu.aggiungi_dentro_fuori(colpi)
    for c in colpi:                      # passo 6b: dalla serie di rimbalzi solo la zona, non dentro/fuori
        if c.get("rimbalzo_trovato_come") == "serie":
            for k in ("dentro_fuori", "distanza_riga_m", "riga_vicina"):
                c.pop(k, None)
            c["profondita"] = "palla corta"
    vu.aggiungi_inside(colpi)
    with open(os.path.join(cartella_dati, nome + "_velocita.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=vr.CAMPI, extrasaction="ignore")
        w.writeheader()
        w.writerows(colpi)
    json.dump(colpi, open(p_json, "w"), default=float)
    return colpi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--dati", default="outputs/dati")
    ap.add_argument("--cartella", default=CARTELLA, help="cartella dei file <video>.csv con i rimbalzi indicati")
    ap.add_argument("--calibrazione")
    a = ap.parse_args()
    applica(a.video, a.dati, a.cartella, a.calibrazione)


if __name__ == "__main__":
    main()
