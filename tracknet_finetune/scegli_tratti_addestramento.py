"""
scegli_tratti_addestramento.py - sceglie i TRATTI CONTINUI di fotogrammi da
etichettare per ADDESTRARE TrackNet sui nostri video, e li estrae come immagini
pronte per etichetta_pallina.py (con i suggerimenti del programma).

    python tracknet_finetune/scegli_tratti_addestramento.py --video nome.mp4
    python tracknet_finetune/scegli_tratti_addestramento.py --video a.mp4 b.mp4 --max_colpi 15

Diverso dal set di test (scegli_frame_test.py): li' si prendono fotogrammi
sparsi attorno ai colpi; qui servono tratti SENZA BUCHI, perche' TrackNet si
addestra su finestre di 8 fotogrammi consecutivi. Per ogni colpo trovato dal
programma (colonna "frame" di outputs/dati/<video>_velocita.csv) si prende il
tratto da --prima_s secondi prima a --dopo_s secondi dopo il contatto (default
0,5 + 0,5 s = 61 fotogrammi a 60 fps), al massimo --max_colpi colpi per video,
scelti distribuiti lungo tutto il video. In piu' --tratti_casuali tratti di un
secondo lontani dai colpi: insegnano alla rete cosa NON e' la pallina (palline
ferme, righe).

Colpi dell'avversario: velocita.csv ha solo i colpi del giocatore vicino alla
camera, ma la pallina che TrackNet perde di piu' e' quella LONTANA e piccola.
Per questo si aggiungono i colpi dell'avversario (e quelli del giocatore che
velocita.csv non ha) da outputs/dati/<video>_impatti.csv (rileva_impatti.py,
inversioni della traiettoria): tratti "a<frame>", motivo "colpo_lontano".
Stesse regole degli altri (durata, --max_colpi, camera ferma, niente
sovrapposizioni). --solo_vicini per farne a meno.

I video del set di test (nicola_matarese_trim, zverev_djokovic_trim_swin_like,
alcaraz) vengono RIFIUTATI, e di ex.mp4 si salta il pezzo 60-150 s usato nel
test (con 5 s di margine): il test deve restare mai visto dalla rete.

Lo script si puo' rilanciare con video nuovi: le righe dei video gia' nella
lista restano (le etichette fatte si riferiscono a quelle), i video nuovi si
aggiungono in coda.

Quanti fotogrammi ha un video: si CONTANO leggendolo, non si prende il numero
scritto nel file. I video tagliati con "ffmpeg -c copy" dichiarano piu'
fotogrammi di quelli che si leggono (il pezzo prima del fotogramma chiave resta
nel file ma non viene mostrato): fidandosi del numero dichiarato, i tratti a
caso potevano cadere oltre la fine del video, senza immagine. Per sicurezza,
dopo l'estrazione si tolgono comunque le righe senza immagine e i tratti
rimasti piu' corti di 16 fotogrammi.

    python tracknet_finetune/scegli_tratti_addestramento.py --pulisci
fa solo questa pulizia sulla lista gia' fatta, senza aggiungere video.

Camera che si muove: per ogni tratto si misura lo spostamento dell'immagine tra
il primo e l'ultimo fotogramma (colonna "spostamento_px", a 1080p). Lo sfondo
mediano della clip regge piccoli spostamenti; prepara_dataset_nostro.py scarta
i tratti oltre --max_spostamento (default 12 px), a meno di --tieni_mossi.
Lo stesso controllo si fa GIA' QUI, prima di proporre i tratti: un colpo con la
camera che si muove non viene proposto (si passa ad altri colpi, se ce ne sono)
e i tratti a caso mossi vengono sostituiti da altri fermi. Cosi' non si
etichettano fotogrammi che poi verrebbero buttati (video girati a mano).
Stesse opzioni: --max_spostamento 12 e --tieni_mossi.

Meno fotogrammi, uguale per tutti i video: --percentuale 65 accorcia OGNI
tratto (di colpo e a caso) al 65% della sua durata, attorno allo stesso
contatto (0,4 + 0,6 s diventano 0,26 + 0,39 s). Ogni video perde la stessa
percentuale e tutti i colpi restano, quindi la varieta' non cambia. Togliere
tratti interi non darebbe la stessa percentuale: con 2-7 tratti per video gli
arrotondamenti pesano troppo. Sotto i 16 fotogrammi per tratto lo script si
ferma (a 30 fps succede sotto circa il 50%).

Uscite (in --uscita, default tracknet_finetune/addestramento/):
  lista_frame.csv              come per il test, piu' le colonne "tratto" (= clip),
                               "tempo_s" e "spostamento_px"
  fotogrammi/<video>/<frame>.jpg   i fotogrammi dei tratti (e +-1 ai bordi)

Poi:  python tracknet_finetune/etichetta_pallina.py --cartella tracknet_finetune/addestramento --suggerimenti

Un video per cartella (per etichettare un video alla volta, anche da computer
diversi): con --per_video ogni video va in una sua sottocartella di --uscita,
con la sua lista e le sue immagini. Mettendo --uscita su Drive, ogni computer
con Drive apre la cartella di un video e la etichetta; le etichette restano in
quella cartella (etichette_<video>.csv), quindi due computer non scrivono mai
lo stesso file. Per esempio:

    python tracknet_finetune/scegli_tratti_addestramento.py --per_video ^
        --uscita "G:\Il mio Drive\rf_coach_vision\tracknet_finetune\addestramento" --video a.mp4 b.mp4
    python tracknet_finetune/etichetta_pallina.py --suggerimenti ^
        --cartella "G:\Il mio Drive\rf_coach_vision\tracknet_finetune\addestramento\a"
"""

import argparse
import os
import random
import sys

import cv2
import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, RADICE)
sys.path.insert(0, QUI)
from scegli_frame_test import CARTELLA_DRIVE, estrai, info_video, suggerimenti, trova  # stesse funzioni del test

# Mai nell'addestramento: sono il set di test (LEGGIMI, "Scelte").
VIDEO_TEST = {"nicola_matarese_trim", "zverev_djokovic_trim_swin_like", "alcaraz"}
EX_TEST_S = (60.0, 150.0)       # pezzo di ex.mp4 nel test
MARGINE_S = 5.0
MIN_TRATTO = 16                 # come prepara_dataset_nostro.py: 8 di sequenza + scorrimento


def conta_fotogrammi(percorso):
    """Fotogrammi che si LEGGONO davvero, in fila dall'inizio (come analyze.py ed estrai)."""
    cap = cv2.VideoCapture(percorso)
    n = 0
    while cap.grab():
        n += 1
    cap.release()
    return n


def togli_senza_immagine(df, cartella_img):
    """Toglie le righe senza immagine estratta e i tratti rimasti piu' corti di MIN_TRATTO."""
    def c_e(r):
        stem = os.path.splitext(r["video"])[0]
        return os.path.exists(os.path.join(cartella_img, stem, f"{int(r['frame']):06d}.jpg"))
    ok = df.apply(c_e, axis=1)
    if (~ok).any():
        print(f"   tolte {int((~ok).sum())} righe senza immagine (oltre la fine del video)")
    df = df[ok]
    lunghezza = df.groupby("tratto")["frame"].transform("size")
    corti = df[lunghezza < MIN_TRATTO]["tratto"].unique()
    if len(corti):
        print(f"   tolti {len(corti)} tratti rimasti troppo corti: {', '.join(corti)}")
    return df[lunghezza >= MIN_TRATTO].reset_index(drop=True)


def spostamenti(percorso, coppie):
    """{(da, a): px a 1080p} tra i due fotogrammi di ogni coppia, leggendo il video in fila
    (stessa misura di spostamento_px, ma sui fotogrammi del video invece che sui JPG)."""
    voluti = {f for c in coppie for f in c if f >= 1}
    if not voluti:
        return {}
    piccoli = {}
    ultimo = max(voluti)
    cap = cv2.VideoCapture(percorso)
    f = 0
    while f < ultimo:
        f += 1
        if f in voluti:
            ok, img = cap.read()
            if not ok:
                break
            piccoli[f] = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (384, 216)).astype(np.float32)
        elif not cap.grab():
            break
    cap.release()
    out = {}
    for da, a_ in coppie:
        if da in piccoli and a_ in piccoli:
            (dx, dy), _ = cv2.phaseCorrelate(piccoli[da], piccoli[a_])
            out[(da, a_)] = round(float(np.hypot(dx, dy)) * 1080 / 216, 1)
    return out


def tratti_video(nome, percorso, cartelle_dati, a, rnd):
    stem = os.path.splitext(nome)[0]
    if stem in VIDEO_TEST:
        raise SystemExit(f"{nome} e' nel SET DI TEST: non si usa per addestrare.")
    fps, dichiarati = info_video(percorso)
    n = conta_fotogrammi(percorso)
    if n != dichiarati:
        print(f"[{nome}] il file dichiara {dichiarati} fotogrammi ma se ne leggono {n} "
              f"(taglio senza ricodifica): uso {n}")
    q = a.percentuale / 100                         # --percentuale: tutti i tratti accorciati allo stesso modo
    prima, dopo = round(a.prima_s * q * fps), round(a.dopo_s * q * fps)
    if prima + dopo + 1 < MIN_TRATTO or round(q * fps) + 1 < MIN_TRATTO:
        raise SystemExit(f"[{nome}] con --percentuale {a.percentuale:g} a {fps:.0f} fps i tratti restano sotto "
                         f"i {MIN_TRATTO} fotogrammi: alza la percentuale (o --prima_s/--dopo_s).")
    vietato = None
    if stem == "ex":
        vietato = (int((EX_TEST_S[0] - MARGINE_S) * fps), int((EX_TEST_S[1] + MARGINE_S) * fps))

    p = trova(f"{stem}_velocita.csv", cartelle_dati)
    lontano_colpo = {}                              # frame del colpo -> True se e' dell'avversario (pallina lontana)
    if p:
        for f in pd.read_csv(p)["frame"].dropna():
            lontano_colpo[int(f)] = False
    # Colpi dell'AVVERSARIO (e del giocatore che velocita' non ha) da <video>_impatti.csv: la pallina
    # lontana e piccola e' il caso piu' difficile per TrackNet, e da velocita.csv non arriva mai.
    pi = None if a.solo_vicini else trova(f"{stem}_impatti.csv", cartelle_dati)
    if pi:
        imp = pd.read_csv(pi)
        if len(imp) and {"frame", "chi"} <= set(imp.columns):
            stesso = round(0.7 * fps)                # un impatto del giocatore cosi' vicino a un colpo di velocita' e' lo stesso
            for chi, f in sorted(zip(imp["chi"], imp["frame"].astype(int)), key=lambda t: t[1]):
                if chi == "avversario":
                    lontano_colpo.setdefault(f, True)
                elif all(abs(f - g) > stesso for g, lon in lontano_colpo.items() if not lon):
                    lontano_colpo.setdefault(f, False)
    colpi = sorted(lontano_colpo)
    if not colpi:
        print(f"[{nome}] nessun colpo in {stem}_velocita.csv / _impatti.csv ({cartelle_dati}): solo tratti a caso")

    def ammesso(da, a_):
        return da >= 1 and a_ <= n and not (vietato and da <= vietato[1] and a_ >= vietato[0])

    # colpi distribuiti lungo il video, senza tratti sovrapposti
    candidati = [c for c in colpi if ammesso(c - prima, c + dopo)]
    colpi_mossi = 0
    if candidati and not a.tieni_mossi:             # niente colpi con la camera che si muove
        sp = spostamenti(percorso, [(c - prima, c + dopo) for c in candidati])
        fermi = [c for c in candidati if sp.get((c - prima, c + dopo), 0) <= a.max_spostamento]
        colpi_mossi = len(candidati) - len(fermi)
        candidati = fermi
    scelti_colpi = []
    if candidati:
        k = min(a.max_colpi, len(candidati))
        passo = len(candidati) / k
        ultimo_fine = -1
        for j in range(k):
            c = candidati[int(j * passo)]
            if c - prima <= ultimo_fine:            # si sovrappone al tratto precedente
                continue
            scelti_colpi.append(c)
            ultimo_fine = c + dopo

    tratti = []                                     # (id, da, a, colpo_frame o None)
    for c in scelti_colpi:
        tratti.append((f"{stem}_{'a' if lontano_colpo[c] else 'c'}{c:06d}", c - prima, c + dopo, c))

    lontano = round(0.5 * fps)
    lungo = round(1.0 * q * fps)
    occupati = [(da, a_) for _, da, a_, _ in tratti]
    liberi = [f for f in range(1, n - lungo)
              if all(abs(f - c) > lontano and abs(f + lungo - c) > lontano for c in colpi)
              and all(f + lungo < da or f > a_ for da, a_ in occupati)
              and ammesso(f, f + lungo)]
    # tratti a caso che non si sovrappongono tra loro; senza --tieni_mossi se ne
    # mettono da parte di piu' e si tengono i primi con la camera ferma
    quanti = a.tratti_casuali if a.tieni_mossi else max(10, 10 * a.tratti_casuali)
    riserva = []
    for f in rnd.sample(liberi, len(liberi)):
        if len(riserva) >= quanti:
            break
        if all(f + lungo < g or f > g + lungo for g in riserva):
            riserva.append(f)
    if a.tieni_mossi:
        presi = riserva
    else:
        sp = spostamenti(percorso, [(f, f + lungo) for f in riserva])
        presi = [f for f in riserva if sp.get((f, f + lungo), 0) <= a.max_spostamento][:a.tratti_casuali]
    for f in sorted(presi):
        tratti.append((f"{stem}_r{f:06d}", f, f + lungo, None))

    tn, col = suggerimenti(stem, cartelle_dati)
    righe = []
    for tid, da, a_, c in tratti:
        for f in range(da, a_ + 1):
            r = {"video": nome, "frame": f, "tempo_s": round((f - 1) / fps, 3),
                 "motivo": ("colpo_lontano" if lontano_colpo[c] else "colpo") if c else "casuale", "tratto": tid,
                 "colpo_frame": c if c else "", "distanza_colpo": f - c if c else ""}
            r["sugg_tracknet_x"], r["sugg_tracknet_y"] = tn.get(f, ("", ""))
            r["sugg_colore_x"], r["sugg_colore_y"] = col.get(f, ("", ""))
            righe.append(r)
    n_colpi = sum(1 for t in tratti if t[3])
    n_lontani = sum(1 for t in tratti if t[3] and lontano_colpo[t[3]])
    print(f"[{nome}] {fps:.2f} fps, {n} fotogrammi, {len(colpi)} colpi trovati dal programma "
          f"({sum(lontano_colpo.values())} dell'avversario): {n_colpi - n_lontani} tratti di colpo vicino + "
          f"{n_lontani} di colpo lontano + {len(tratti) - n_colpi} a caso = {len(righe)} fotogrammi da etichettare")
    if colpi_mossi:
        print(f"   {colpi_mossi} colpi non proposti: la camera si muove (> {a.max_spostamento:g} px)")
    if len(presi) < a.tratti_casuali:
        print(f"   solo {len(presi)} tratti a caso su {a.tratti_casuali}: non ci sono altri pezzi fermi lontani dai colpi")
    return righe


def spostamento_px(cartella_img, stem, da, a_):
    """Spostamento dell'immagine (px a 1080p) tra primo e ultimo fotogramma del tratto, per correlazione di fase."""
    def grigio(f):
        img = cv2.imread(os.path.join(cartella_img, stem, f"{f:06d}.jpg"), cv2.IMREAD_GRAYSCALE)
        return None if img is None else cv2.resize(img, (384, 216)).astype(np.float32)
    g0, g1 = grigio(da), grigio(a_)
    if g0 is None or g1 is None:
        return ""
    (dx, dy), _ = cv2.phaseCorrelate(g0, g1)
    return round(float(np.hypot(dx, dy)) * 1080 / 216, 1)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--video", nargs="*", default=[], help="nomi dei video (in inputs/ su Drive o nel progetto)")
    p.add_argument("--pulisci", action="store_true",
                   help="solo: togli dalla lista esistente le righe senza immagine e i tratti troppo corti")
    p.add_argument("--video_dir", nargs="*", default=None)
    p.add_argument("--dati_dir", nargs="*", default=None,
                   help="dove cercare _velocita.csv e _tracking.csv (default: Drive outputs/dati, poi outputs/dati)")
    p.add_argument("--uscita", default=os.path.join(QUI, "addestramento"))
    p.add_argument("--per_video", action="store_true",
                   help="ogni video in una sottocartella di --uscita (per etichettare un video alla volta)")
    p.add_argument("--prima_s", type=float, default=0.5, help="secondi prima del contatto")
    p.add_argument("--dopo_s", type=float, default=0.5, help="secondi dopo il contatto")
    p.add_argument("--max_colpi", type=int, default=10, help="colpi per video (distribuiti lungo il video)")
    p.add_argument("--tratti_casuali", type=int, default=1, help="tratti di 1 s lontani dai colpi, per video")
    p.add_argument("--solo_vicini", action="store_true",
                   help="solo i colpi del giocatore vicino (velocita.csv), senza quelli dell'avversario da _impatti.csv")
    p.add_argument("--percentuale", type=float, default=100.0,
                   help="accorcia TUTTI i tratti (di colpo e a caso) a questa percentuale della durata: "
                        "stessa riduzione per ogni video, tutti i colpi restano")
    p.add_argument("--max_spostamento", type=float, default=12.0,
                   help="px a 1080p: i tratti con la camera che si muove piu' di cosi' non vengono proposti")
    p.add_argument("--tieni_mossi", action="store_true", help="proponi anche i tratti con la camera che si muove")
    p.add_argument("--seme", type=int, default=13)
    a = p.parse_args()
    if not 0 < a.percentuale <= 100:
        raise SystemExit("--percentuale va da 1 a 100")

    drive = CARTELLA_DRIVE if CARTELLA_DRIVE and os.path.isdir(CARTELLA_DRIVE) else ""
    cartelle_video = a.video_dir or [os.path.join(drive, "inputs") if drive else "", os.path.join(RADICE, "inputs")]
    cartelle_dati = a.dati_dir or [os.path.join(drive, "outputs", "dati") if drive else "",
                                   os.path.join(RADICE, "outputs", "dati")]
    if a.per_video:
        if a.pulisci:
            raise SystemExit("--pulisci va usato su una cartella alla volta (--uscita <cartella del video>).")
        if not a.video:
            raise SystemExit("Indica i video con --video.")
        rnd = random.Random(a.seme)
        for nome in a.video:
            elabora(a, [nome], os.path.join(a.uscita, os.path.splitext(nome)[0]),
                    cartelle_video, cartelle_dati, rnd)
        return
    if a.pulisci:
        os.makedirs(a.uscita, exist_ok=True)
        p_lista = os.path.join(a.uscita, "lista_frame.csv")
        vecchia = pd.read_csv(p_lista) if os.path.exists(p_lista) else None
        if vecchia is None:
            raise SystemExit(f"Non c'e' {p_lista}: niente da pulire.")
        pulita = togli_senza_immagine(vecchia, os.path.join(a.uscita, "fotogrammi"))
        pulita.to_csv(p_lista, index=False)
        print(f"{p_lista}: {len(vecchia)} -> {len(pulita)} righe")
        return
    if not a.video:
        raise SystemExit("Indica i video con --video (oppure --pulisci).")
    elabora(a, a.video, a.uscita, cartelle_video, cartelle_dati, random.Random(a.seme))


def elabora(a, video, uscita, cartelle_video, cartelle_dati, rnd):
    """Sceglie ed estrae i tratti dei video in una cartella (lista_frame.csv + fotogrammi/)."""
    os.makedirs(uscita, exist_ok=True)
    p_lista = os.path.join(uscita, "lista_frame.csv")
    vecchia = pd.read_csv(p_lista) if os.path.exists(p_lista) else None
    gia = set(vecchia["video"].unique()) if vecchia is not None else set()
    nuove = []
    for nome in video:
        if nome in gia:
            print(f"[{nome}] gia' nella lista: lo salto (le etichette fatte si riferiscono a quella). "
                  "Per rifarlo togli le sue righe da lista_frame.csv e le sue immagini.")
            continue
        percorso = trova(nome, cartelle_video)
        if not percorso:
            print(f"[{nome}] video non trovato in {cartelle_video}: salto")
            continue
        righe = tratti_video(nome, percorso, cartelle_dati, a, rnd)
        estrai(nome, percorso, [r["frame"] for r in righe], os.path.join(uscita, "fotogrammi"))
        stem = os.path.splitext(nome)[0]
        per_tratto = {}
        for r in righe:
            per_tratto.setdefault(r["tratto"], []).append(r["frame"])
        mossi = 0
        for tid, frames in per_tratto.items():
            s = spostamento_px(os.path.join(uscita, "fotogrammi"), stem, min(frames), max(frames))
            for r in righe:
                if r["tratto"] == tid:
                    r["spostamento_px"] = s
            mossi += 1 if (s != "" and s > a.max_spostamento) else 0
        if mossi:
            print(f"   {nome}: {mossi} tratti con la camera che si muove (> {a.max_spostamento:g} px): "
                  "prepara_dataset_nostro.py li scarta, a meno di --tieni_mossi anche li'")
        nuove += righe
    if not nuove:
        print(f"{uscita}: nessun fotogramma nuovo.")
        return
    df = togli_senza_immagine(pd.DataFrame(nuove), os.path.join(uscita, "fotogrammi"))
    if df.empty:
        print(f"{uscita}: nessun fotogramma nuovo con immagine.")
        return
    if vecchia is not None:
        df = pd.concat([vecchia, df], ignore_index=True)
    df.to_csv(p_lista, index=False)
    print(f"\n{len(df) - (len(vecchia) if vecchia is not None else 0)} fotogrammi nuovi, {len(df)} in tutto in {p_lista}")
    print(f'Ora: python tracknet_finetune/etichetta_pallina.py --suggerimenti --cartella "{uscita}"')


if __name__ == "__main__":
    main()
