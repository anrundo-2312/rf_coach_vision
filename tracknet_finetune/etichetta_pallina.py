"""
etichetta_pallina.py - etichettatura a mano della pallina nei fotogrammi del
set di test (scelti ed estratti da scegli_frame_test.py). Gira sul PC.

    python tracknet_finetune/etichetta_pallina.py

Per ogni fotogramma si segna il CENTRO della pallina con un clic (la lente in
alto ingrandisce attorno al mouse). Regole:
  - pallina nitida: il centro della pallina;
  - pallina MOSSA (una striscia): il centro della striscia, e premi M;
  - pallina coperta, fuori dall'immagine o non c'e': N (non visibile);
  - le palline FERME a terra non contano: si segna solo la pallina in gioco;
    se l'unica pallina visibile e' ferma, N;
  - se non sei sicuro: S (incerto: il fotogramma non conta nel voto).

Tasti:
    clic sinistro      segna la pallina
    frecce / IJKL      sposta il punto di 1 pixel
    Invio o Spazio     conferma e passa al successivo
    N                  pallina non visibile (e passa al successivo)
    S                  incerto, salta (non conta)
    M                  pallina mossa si'/no
    H                  mostra/nasconde i suggerimenti (giallo = TrackNet, azzurro = punti
                       usati dal programma). Spenti di default: il set di test deve
                       essere indipendente da TrackNet, altrimenti il voto si gonfia.
    A / D              guarda il fotogramma prima / dopo (solo per vedere il movimento)
    U o Backspace      torna al fotogramma precedente della lista
    Esc o Q            salva ed esci (la volta dopo riparte da dove eri)

Ogni conferma salva subito tracknet_finetune/test/etichette_test.csv (e lo copia
su Drive in rf_coach_vision/tracknet_finetune/). Il pallino blu tenue e'
l'etichetta del fotogramma prima, se e' il fotogramma accanto: aiuta a trovare
la pallina.
"""

import argparse
import datetime
import os
import sys

import cv2
import numpy as np
import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, RADICE)

FRECCE = {2424832: (-1, 0), 2555904: (1, 0), 2490368: (0, -1), 2621440: (0, 1),     # Windows
          65361: (-1, 0), 65363: (1, 0), 65362: (0, -1), 65364: (0, 1),             # Linux
          ord("j"): (-1, 0), ord("l"): (1, 0), ord("i"): (0, -1), ord("k"): (0, 1)}
ROSSO, GIALLO, AZZURRO, BLU = (0, 0, 255), (0, 230, 255), (255, 200, 0), (200, 120, 60)
COLONNE = ["video", "frame", "visibile", "x", "y", "mossa", "motivo", "colpo_frame", "distanza_colpo", "ora"]


def lente(img, u, v, raggio, zoom=5):
    """Ingrandimento attorno a (u, v) in pixel pieni, con mirino (come calibra_campo.py)."""
    pad = cv2.copyMakeBorder(img, raggio, raggio, raggio, raggio, cv2.BORDER_CONSTANT)
    u, v = int(round(u)), int(round(v))
    g = cv2.resize(pad[v:v + 2 * raggio + 1, u:u + 2 * raggio + 1], None, fx=zoom, fy=zoom,
                   interpolation=cv2.INTER_NEAREST)
    c = raggio * zoom + zoom // 2
    cv2.line(g, (c, 0), (c, g.shape[0]), (0, 255, 255), 1)
    cv2.line(g, (0, c), (g.shape[1], c), (0, 255, 255), 1)
    cv2.rectangle(g, (0, 0), (g.shape[1] - 1, g.shape[0] - 1), (255, 255, 255), 1)
    return g


def num(v):
    try:
        f = float(v)
        return None if np.isnan(f) else f
    except (TypeError, ValueError):
        return None


def carica_etichette(percorso):
    if not os.path.exists(percorso):
        return {}
    df = pd.read_csv(percorso)
    return {(r["video"], int(r["frame"])): r.to_dict() for _, r in df.iterrows()}


def salva(percorso, etichette, lista):
    ordine = {(r["video"], int(r["frame"])): i for i, r in enumerate(lista)}
    righe = sorted(etichette.values(), key=lambda r: ordine.get((r["video"], int(r["frame"])), 1e9))
    pd.DataFrame(righe, columns=COLONNE).to_csv(percorso, index=False)
    try:
        import sincronizza_drive
        sincronizza_drive.copia(percorso, "tracknet_finetune")
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--cartella", default=os.path.join(QUI, "test"),
                   help="cartella con lista_frame.csv e fotogrammi/")
    p.add_argument("--etichette", default=None, help="default: <cartella>/etichette_test.csv")
    a = p.parse_args()
    p_lista = os.path.join(a.cartella, "lista_frame.csv")
    p_et = a.etichette or os.path.join(a.cartella, "etichette_test.csv")
    if not os.path.exists(p_lista):
        raise SystemExit(f"Manca {p_lista}: prima lancia scegli_frame_test.py")
    lista = pd.read_csv(p_lista).to_dict("records")
    etichette = carica_etichette(p_et)
    i = next((k for k, r in enumerate(lista) if (r["video"], int(r["frame"])) not in etichette), len(lista))
    if i >= len(lista):
        print(f"Tutti i {len(lista)} fotogrammi sono gia' etichettati ({p_et}). Per rivederli usa U.")
        i = len(lista) - 1

    finestra = "Etichetta la pallina"
    cv2.namedWindow(finestra, cv2.WINDOW_AUTOSIZE)
    stato = {"u": 0.0, "v": 0.0, "clic": None}
    s = 1.0

    def callback(evento, x, y, flags, param):
        stato["u"], stato["v"] = x / s, y / s
        if evento == cv2.EVENT_LBUTTONDOWN:
            stato["clic"] = (x / s, y / s)

    cv2.setMouseCallback(finestra, callback)

    def immagine(riga, scarto=0):
        stem = os.path.splitext(riga["video"])[0]
        f = int(riga["frame"]) + scarto
        img = cv2.imread(os.path.join(a.cartella, "fotogrammi", stem, f"{f:06d}.jpg"))
        return img

    corrente = None          # (indice) per cui sono caricati punto/mossa
    punto, mossa, scarto, suggerimenti = None, 0, 0, False
    while True:
        riga = lista[i]
        chiave = (riga["video"], int(riga["frame"]))
        if corrente != i:
            vecchia = etichette.get(chiave)
            punto = (num(vecchia["x"]), num(vecchia["y"])) if vecchia is not None and int(vecchia["visibile"]) == 1 else None
            mossa = int(vecchia["mossa"]) if vecchia is not None else 0
            scarto, corrente = 0, i
        img = immagine(riga, scarto)
        if img is None:
            img = immagine(riga, 0)
            scarto = 0
        if img is None:
            raise SystemExit(f"Manca l'immagine di {chiave}: rilancia scegli_frame_test.py")
        h, w = img.shape[:2]
        s = min(1.0, 1500 / w, 850 / h)
        if stato["clic"] is not None:
            punto, stato["clic"] = stato["clic"], None

        disegno = img.copy()
        # etichetta del fotogramma accanto (stesso video), come aiuto per trovare la pallina
        for k in (i - 1, i + 1):
            if 0 <= k < len(lista) and lista[k]["video"] == riga["video"] \
                    and abs(int(lista[k]["frame"]) - int(riga["frame"])) == 1:
                e = etichette.get((lista[k]["video"], int(lista[k]["frame"])))
                if e is not None and int(e["visibile"]) == 1:
                    cv2.circle(disegno, (int(e["x"]), int(e["y"])), max(4, int(6 / s)), BLU, max(1, int(1 / s)))
        if suggerimenti:
            for (cx, cy), col in (((riga.get("sugg_tracknet_x"), riga.get("sugg_tracknet_y")), GIALLO),
                                  ((riga.get("sugg_colore_x"), riga.get("sugg_colore_y")), AZZURRO)):
                if num(cx) is not None and num(cy) is not None:
                    cv2.circle(disegno, (int(num(cx)), int(num(cy))), max(8, int(12 / s)), col, max(1, int(2 / s)))
        if punto is not None and scarto == 0:
            u, v = int(round(punto[0])), int(round(punto[1]))
            cv2.circle(disegno, (u, v), max(6, int(9 / s)), ROSSO, max(1, int(2 / s)))
            cv2.drawMarker(disegno, (u, v), ROSSO, cv2.MARKER_CROSS, max(6, int(8 / s)), 1)

        vis = cv2.resize(disegno, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        fatti = sum(1 for r in lista if (r["video"], int(r["frame"])) in etichette)
        d = riga.get("distanza_colpo")
        colpo = f" | colpo al {int(riga['colpo_frame'])} ({int(d):+d})" if num(d) is not None else " | a caso"
        titolo = (f"{riga['video']}  fotogramma {int(riga['frame'])}{colpo}  |  {i + 1}/{len(lista)}  "
                  f"fatti {fatti}  |  MOSSA: {'SI' if mossa else 'no'}"
                  + (f"  |  GUARDI {scarto:+d} (solo per vedere)" if scarto else ""))
        gia = etichette.get(chiave)
        if gia is not None:
            titolo += "  |  gia': " + {1: "visibile", 0: "non visibile", -1: "incerto"}[int(gia["visibile"])]
        aiuto = ("clic = pallina | Invio/Spazio = conferma | N = non visibile | S = incerto | M = mossa | "
                 "H = suggerimenti | A/D = guarda -1/+1 | U = indietro | frecce = 1 px | Esc = esci")
        cv2.rectangle(vis, (0, 0), (vis.shape[1], 52), (0, 0, 0), -1)
        cv2.putText(vis, titolo, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(vis, aiuto, (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
        L = lente(disegno, stato["u"], stato["v"], raggio=40 if w > 2500 else 30)
        x0 = vis.shape[1] - L.shape[1] - 10 if stato["u"] * s < vis.shape[1] / 2 else 10
        if L.shape[0] + 60 <= vis.shape[0] and L.shape[1] + 10 <= vis.shape[1]:
            vis[60:60 + L.shape[0], x0:x0 + L.shape[1]] = L
        cv2.imshow(finestra, vis)

        k = cv2.waitKeyEx(20)
        if k == -1:
            if cv2.getWindowProperty(finestra, cv2.WND_PROP_VISIBLE) < 1:
                break
            continue
        kk = k & 0xFF if k < 256 else k
        if kk in (27, ord("q"), ord("Q")):
            break

        def registra(visibile, x="", y=""):
            etichette[chiave] = {"video": riga["video"], "frame": int(riga["frame"]), "visibile": visibile,
                                 "x": "" if x == "" else round(float(x), 1), "y": "" if y == "" else round(float(y), 1),
                                 "mossa": mossa if visibile == 1 else 0, "motivo": riga.get("motivo", ""),
                                 "colpo_frame": riga.get("colpo_frame", ""),
                                 "distanza_colpo": riga.get("distanza_colpo", ""),
                                 "ora": datetime.datetime.now().isoformat(timespec="seconds")}
            salva(p_et, etichette, lista)

        avanti = False
        if kk in (13, 10, 32):
            if punto is None:
                print("Prima clicca sulla pallina, oppure N se non si vede.")
            else:
                registra(1, *punto)
                avanti = True
        elif kk in (ord("n"), ord("N")):
            registra(0)
            avanti = True
        elif kk in (ord("s"), ord("S")):
            registra(-1)
            avanti = True
        elif kk in (ord("m"), ord("M")):
            mossa = 0 if mossa else 1
        elif kk in (ord("h"), ord("H")):
            suggerimenti = not suggerimenti
        elif kk in (ord("a"), ord("A")):
            scarto = max(-1, scarto - 1)
        elif kk in (ord("d"), ord("D")):
            scarto = min(1, scarto + 1)
        elif kk in (ord("u"), ord("U"), 8):
            i = max(0, i - 1)
        elif k in FRECCE and punto is not None:
            du, dv = FRECCE[k]
            punto = (punto[0] + du, punto[1] + dv)
        if avanti:
            if i + 1 < len(lista):
                i += 1
            else:
                print(f"Finito! {len(etichette)} fotogrammi etichettati in {p_et}")

    cv2.destroyAllWindows()
    salva(p_et, etichette, lista)
    fatti = sum(1 for r in lista if (r["video"], int(r["frame"])) in etichette)
    print(f"Salvato {p_et}: {fatti}/{len(lista)} fotogrammi etichettati.")


if __name__ == "__main__":
    main()
