"""
calibra_campo.py - calibrazione della camera dalle righe del campo.

Serve a passare dai pixel ai metri: e' il primo passo per la velocita' della
pallina in km/h (vedi LEGGIMI.md in questa cartella). Si fa UNA volta per ogni
posizione della camera: finche' la camera non si muove, vale per tutto il video.

Non e' obbligatoria: i video senza calibrazione propria usano quella standard,
calibrazioni/standard.json, pensata per il telefono messo sempre allo stesso
modo, come con SwingVision (LEGGIMI.md, "Calibrazione standard"). Qui si fa
la calibrazione per i video girati diversamente. Su Colab, dove le finestre non
si aprono, c'e' calibra_colab.py (cella 7c del notebook).

    python velocita/calibra_campo.py inputs/<video>.mp4
    python velocita/calibra_campo.py inputs/<video>.mp4 --frame 120
    python velocita/calibra_campo.py inputs/<video>.mp4 --verifica     (solo immagine di controllo)

Si apre un fotogramma del video. In alto e' scritto quale punto del campo
cliccare, e lo schemino in basso a sinistra mostra dov'e'. Per ogni punto:

    clic sinistro        segna il punto (la lente in alto aiuta a essere precisi)
    frecce oppure IJKL   spostano di 1 pixel l'ultimo punto segnato
    S                    punto non visibile: salta
    U o Backspace        annulla l'ultimo punto
    , e .                cambia fotogramma (indietro / avanti di 10), se il
                         giocatore copre le righe
    F                    ho finito (anche prima dell'ultimo punto)
    Esc                  esci senza salvare

Servono almeno 6 punti, sparsi il piu' possibile (vicino, rete, lontano). La
cima della rete e dei pali, che non sono a terra, aiutano molto.

Alla fine il programma ridisegna tutto il campo sopra il fotogramma: se le
righe verdi cadono sulle righe vere, la calibrazione e' buona. Invio salva,
R ricomincia. Il risultato va in velocita/calibrazioni/<video>.json con
un'immagine di controllo <video>_campo.jpg accanto, e il JSON viene copiato
anche su Drive in rf_coach_vision/calibrazioni/, da dove lo prende Colab.
Il video puo' stare anche solo su Drive:
    python velocita/calibra_campo.py "G:/Il mio Drive/rf_coach_vision/inputs/<video>.mp4"
"""

import argparse
import datetime
import json
import os
import sys

import cv2
import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
from rf_ball_exit_speed import calibrate_camera, project  # file di calcolo della velocita'

CARTELLA_CALIBRAZIONI = os.path.join(QUI, "calibrazioni")
# Usata per i video senza calibrazione propria (vedi carica_per_video).
STANDARD = os.path.join(CARTELLA_CALIBRAZIONI, "standard.json")

# Punti noti del campo, in metri: x = larghezza (0 = riga del doppio a SINISTRA
# nell'immagine, 10.97 = a destra), y = lunghezza (0 = fondo dal lato della
# camera, 23.77 = fondo opposto), z = altezza. Misure del regolamento ITF.
# Nell'ordine in cui vengono chiesti, con la descrizione mostrata a video.
PUNTI = [
    ("fondo_vicino_sx_doppio", (0.0, 0.0, 0.0), "fondo vicino, angolo a sinistra (riga del doppio)"),
    ("fondo_vicino_sx_singolo", (1.37, 0.0, 0.0), "fondo vicino, incrocio con la riga del singolo a sinistra"),
    ("fondo_vicino_centro", (5.485, 0.0, 0.0), "fondo vicino, segno centrale"),
    ("fondo_vicino_dx_singolo", (9.60, 0.0, 0.0), "fondo vicino, incrocio con la riga del singolo a destra"),
    ("fondo_vicino_dx_doppio", (10.97, 0.0, 0.0), "fondo vicino, angolo a destra (riga del doppio)"),
    ("servizio_vicino_sx", (1.37, 5.485, 0.0), "riga del servizio vicina, estremo sinistro"),
    ("T_vicino", (5.485, 5.485, 0.0), "T del servizio vicina"),
    ("servizio_vicino_dx", (9.60, 5.485, 0.0), "riga del servizio vicina, estremo destro"),
    ("rete_terra_sx_doppio", (0.0, 11.885, 0.0), "sotto la rete: riga del doppio a sinistra"),
    ("rete_terra_sx_singolo", (1.37, 11.885, 0.0), "sotto la rete: riga del singolo a sinistra"),
    ("rete_terra_centro", (5.485, 11.885, 0.0), "sotto la rete: riga centrale del servizio"),
    ("rete_terra_dx_singolo", (9.60, 11.885, 0.0), "sotto la rete: riga del singolo a destra"),
    ("rete_terra_dx_doppio", (10.97, 11.885, 0.0), "sotto la rete: riga del doppio a destra"),
    ("palo_sx_alto", (-0.914, 11.885, 1.07), "cima del palo della rete a sinistra (pali del doppio)"),
    ("rete_centro_alto", (5.485, 11.885, 0.914), "cima della rete al centro (sopra la fascia centrale)"),
    ("palo_dx_alto", (11.884, 11.885, 1.07), "cima del palo della rete a destra (pali del doppio)"),
    ("servizio_lontano_sx", (1.37, 18.285, 0.0), "riga del servizio lontana, estremo sinistro"),
    ("T_lontano", (5.485, 18.285, 0.0), "T del servizio lontana"),
    ("servizio_lontano_dx", (9.60, 18.285, 0.0), "riga del servizio lontana, estremo destro"),
    ("fondo_lontano_sx_doppio", (0.0, 23.77, 0.0), "fondo lontano, angolo a sinistra (riga del doppio)"),
    ("fondo_lontano_sx_singolo", (1.37, 23.77, 0.0), "fondo lontano, incrocio con la riga del singolo a sinistra"),
    ("fondo_lontano_dx_singolo", (9.60, 23.77, 0.0), "fondo lontano, incrocio con la riga del singolo a destra"),
    ("fondo_lontano_dx_doppio", (10.97, 23.77, 0.0), "fondo lontano, angolo a destra (riga del doppio)"),
]
MONDO = {n: p for n, p, _ in PUNTI}

# Righe del campo da ridisegnare per il controllo (a terra) e profilo della rete.
RIGHE = [
    ((0, 0), (0, 23.77)), ((10.97, 0), (10.97, 23.77)),              # doppio
    ((1.37, 0), (1.37, 23.77)), ((9.60, 0), (9.60, 23.77)),          # singolo
    ((0, 0), (10.97, 0)), ((0, 23.77), (10.97, 23.77)),              # fondi
    ((1.37, 5.485), (9.60, 5.485)), ((1.37, 18.285), (9.60, 18.285)),  # servizio
    ((5.485, 5.485), (5.485, 18.285)),                                # centrale
    ((5.485, 0), (5.485, 0.2)), ((5.485, 23.77), (5.485, 23.57)),     # segni centrali
    ((-0.914, 11.885), (11.884, 11.885)),                             # rete a terra
]
RETE_ALTA = [(-0.914, 11.885, 1.07), (5.485, 11.885, 0.914), (11.884, 11.885, 1.07)]

MIN_PUNTI = 6
VERDE, ROSSO, BLU, GIALLO, GRIGIO = (60, 220, 60), (40, 40, 230), (230, 140, 30), (0, 220, 255), (150, 150, 150)
FRECCE = {2424832: (-1, 0), 2555904: (1, 0), 2490368: (0, -1), 2621440: (0, 1),     # Windows
          65361: (-1, 0), 65363: (1, 0), 65362: (0, -1), 65364: (0, 1),             # Linux
          ord("j"): (-1, 0), ord("l"): (1, 0), ord("i"): (0, -1), ord("k"): (0, 1)}


# ------------------------------------------------------------------ calcolo
def calcola(punti_px, dimensioni):
    """punti_px: {nome: (u, v)} -> dizionario della calibrazione (serializzabile)."""
    nomi = [n for n, _, _ in PUNTI if n in punti_px]
    img = np.array([punti_px[n] for n in nomi], float)
    mondo = np.array([MONDO[n] for n in nomi], float)
    cam = calibrate_camera(img, mondo, dimensioni)
    riproiettati = project(mondo, cam)
    errori = np.linalg.norm(riproiettati - img, axis=1)
    R, _ = cv2.Rodrigues(cam["rvec"])
    centro = (-R.T @ cam["tvec"]).ravel()
    return {
        "K": cam["K"].tolist(), "rvec": cam["rvec"].ravel().tolist(), "tvec": cam["tvec"].ravel().tolist(),
        "errore_rms_px": float(cam["reproj_rms_px"]),
        "errore_per_punto_px": {n: round(float(e), 2) for n, e in zip(nomi, errori)},
        "camera_in_metri": [round(float(c), 2) for c in centro],
        "focale_px": round(float(cam["K"][0, 0]), 1),
    }


def camera_da_json(cal):
    """Dal JSON salvato al formato usato da rf_ball_exit_speed (K, rvec, tvec)."""
    return {"K": np.array(cal["K"], float), "rvec": np.array(cal["rvec"], float).reshape(3, 1),
            "tvec": np.array(cal["tvec"], float).reshape(3, 1)}


def adatta_risoluzione(cal, larghezza, altezza):
    """
    La stessa calibrazione per un video della stessa camera ma di risoluzione diversa
    (per esempio 1280x720 invece di 1920x1080): cambia solo la scala dei pixel, quindi
    si scalano focale e centro dell'immagine. Posizione e orientamento restano uguali.
    Con proporzioni diverse (video verticale, 4:3) non si puo': serve una calibrazione propria.
    """
    w0, h0 = cal["dimensioni"]
    if (w0, h0) == (larghezza, altezza):
        return cal
    if abs(larghezza / altezza - w0 / h0) > 0.02:
        raise SystemExit(f"Il video e' {larghezza}x{altezza}, la calibrazione e' per {w0}x{h0}: proporzioni "
                         f"diverse. Serve una calibrazione per questo video (calibra_campo.py).")
    s = larghezza / w0
    K = np.array(cal["K"], float)
    K[:2] *= s
    return {**cal, "K": K.tolist(), "dimensioni": [larghezza, altezza], "focale_px": round(float(K[0, 0]), 1)}


def carica_per_video(video, calibrazione=None):
    """
    Calibrazione da usare per un video:
      - quella indicata (calibrazione), se c'e';
      - altrimenti quella del video, calibrazioni/<video>.json, se esiste;
      - altrimenti quella standard, calibrazioni/standard.json (telefono messo come
        con SwingVision: vedi LEGGIMI.md, "Calibrazione standard").
    Restituisce (calibrazione adattata alla risoluzione del video, "video" o "standard").
    """
    nome = os.path.splitext(os.path.basename(video))[0]
    if calibrazione:
        if not os.path.exists(calibrazione):
            raise SystemExit(f"Calibrazione non trovata: {calibrazione}")
        percorso = calibrazione
    else:
        percorso = os.path.join(CARTELLA_CALIBRAZIONI, nome + ".json")
        if not os.path.exists(percorso):
            percorso = STANDARD
    cal = json.load(open(percorso, encoding="utf-8"))
    fonte = "standard" if cal.get("video") == "standard" else "video"
    cap = cv2.VideoCapture(video)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return adatta_risoluzione(cal, w, h), fonte


# ------------------------------------------------------------------ disegno
def disegna_controllo(frame, cal, punti_px, testo=None):
    """Campo ridisegnato (verde), profilo della rete (giallo), punti cliccati (rosso) e riproiettati (blu)."""
    out = frame.copy()
    cam = camera_da_json(cal)
    spessore = max(1, frame.shape[1] // 800)
    for a, b in RIGHE:
        p = project(np.array([[a[0], a[1], 0.0], [b[0], b[1], 0.0]]), cam)
        cv2.line(out, tuple(np.round(p[0]).astype(int)), tuple(np.round(p[1]).astype(int)), VERDE, spessore, cv2.LINE_AA)
    rete = np.round(project(np.array(RETE_ALTA), cam)).astype(int)
    cv2.polylines(out, [rete.reshape(-1, 1, 2)], False, GIALLO, spessore, cv2.LINE_AA)
    for n, (u, v) in punti_px.items():
        q = project(np.array(MONDO[n]), cam)[0]
        cv2.circle(out, (int(round(u)), int(round(v))), 6, ROSSO, 2, cv2.LINE_AA)
        cv2.circle(out, (int(round(q[0])), int(round(q[1]))), 3, BLU, -1, cv2.LINE_AA)
    if testo is None:
        testo = (f"errore medio {cal['errore_rms_px']:.1f} px  |  camera a x={cal['camera_in_metri'][0]} "
                 f"y={cal['camera_in_metri'][1]} z={cal['camera_in_metri'][2]} m  |  focale {cal['focale_px']} px")
    s = max(0.8, out.shape[1] / 2400)                 # scritta leggibile anche in 4K
    alto = int(40 * s)
    cv2.rectangle(out, (0, 0), (out.shape[1], alto), (0, 0, 0), -1)
    cv2.putText(out, testo, (12, int(28 * s)), cv2.FONT_HERSHEY_SIMPLEX, 0.8 * s, (255, 255, 255),
                max(2, int(2 * s)), cv2.LINE_AA)
    return out


def schema_campo(stato, corrente, larghezza=210):
    """Campo visto dall'alto: punto richiesto in rosso, segnati in verde, saltati in grigio."""
    m = larghezza / 14.0
    alt = int(26.5 * m)
    img = np.full((alt, larghezza, 3), 40, np.uint8)

    def px(x, y):
        return int((x + 1.5) * m), int(alt - (y + 1.2) * m)

    for a, b in RIGHE:
        cv2.line(img, px(*a), px(*b), (220, 220, 220), 1, cv2.LINE_AA)
    cv2.line(img, px(-0.914, 11.885), px(11.884, 11.885), (0, 200, 255), 2)
    cv2.putText(img, "camera", (int(larghezza / 2) - 30, alt - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    for i, (n, (x, y, z), _) in enumerate(PUNTI):
        colore = {"fatto": VERDE, "saltato": GRIGIO}.get(stato.get(n), (90, 90, 90))
        r = 4
        if i == corrente:
            colore, r = ROSSO, 7
        cv2.circle(img, px(x, y), r, colore, -1 if i != corrente else 2, cv2.LINE_AA)
    return img


def lente(frame, u, v, raggio=30, zoom=5):
    """Ingrandimento attorno a (u, v) in pixel pieni, con mirino al centro."""
    h, w = frame.shape[:2]
    pad = cv2.copyMakeBorder(frame, raggio, raggio, raggio, raggio, cv2.BORDER_CONSTANT)
    u, v = int(round(u)), int(round(v))
    ritaglio = pad[v:v + 2 * raggio + 1, u:u + 2 * raggio + 1]
    g = cv2.resize(ritaglio, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST)
    c = raggio * zoom + zoom // 2
    cv2.line(g, (c, 0), (c, g.shape[0]), (0, 255, 255), 1)
    cv2.line(g, (0, c), (g.shape[1], c), (0, 255, 255), 1)
    cv2.rectangle(g, (0, 0), (g.shape[1] - 1, g.shape[0] - 1), (255, 255, 255), 1)
    return g


# ------------------------------------------------------------------ video
def leggi_fotogramma(video, n):
    cap = cv2.VideoCapture(video)
    totale = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    n = max(0, min(n, totale - 1))
    cap.set(cv2.CAP_PROP_POS_FRAMES, n)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"Non riesco a leggere il fotogramma {n} di {video}")
    return frame, n, totale


def percorsi(video):
    nome = os.path.splitext(os.path.basename(video))[0]
    os.makedirs(CARTELLA_CALIBRAZIONI, exist_ok=True)
    return (os.path.join(CARTELLA_CALIBRAZIONI, nome + ".json"),
            os.path.join(CARTELLA_CALIBRAZIONI, nome + "_campo.jpg"), nome)


def salva(video, n_frame, frame, punti_px, cal):
    pj, pi, nome = percorsi(video)
    dati = {"video": nome, "fotogramma": n_frame, "dimensioni": [frame.shape[1], frame.shape[0]],
            "data": datetime.date.today().isoformat(),
            "punti_px": {n: [round(float(u), 1), round(float(v), 1)] for n, (u, v) in punti_px.items()},
            "punti_metri": {n: list(MONDO[n]) for n in punti_px}, **cal}
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(dati, f, indent=1, ensure_ascii=False)
    cv2.imwrite(pi, disegna_controllo(frame, cal, punti_px))
    print(f"Salvato: {pj}\nImmagine di controllo: {pi}")
    # copia su Drive in calibrazioni/: il notebook di Colab la prende da li', senza passare da GitHub
    try:
        sys.path.insert(0, os.path.dirname(QUI))
        import sincronizza_drive
        sincronizza_drive.copia(pj, "calibrazioni")
    except ImportError:
        pass


# ------------------------------------------------------------------ interattivo
def interattivo(video, n_frame):
    frame, n_frame, totale = leggi_fotogramma(video, n_frame)
    h, w = frame.shape[:2]
    s = min(1.0, 1500 / w, 850 / h)                    # scala di visualizzazione
    finestra = "Calibrazione campo"
    cv2.namedWindow(finestra, cv2.WINDOW_AUTOSIZE)
    mouse = {"u": w / 2, "v": h / 2, "clic": None}

    def callback(evento, x, y, flags, param):
        mouse["u"], mouse["v"] = x / s, y / s
        if evento == cv2.EVENT_LBUTTONDOWN:
            mouse["clic"] = (x / s, y / s)

    cv2.setMouseCallback(finestra, callback)
    punti, stato, storia, i = {}, {}, [], 0

    while True:
        if mouse["clic"] is not None and i < len(PUNTI):
            nome = PUNTI[i][0]
            punti[nome] = list(mouse["clic"]); stato[nome] = "fatto"; storia.append(nome); i += 1
        mouse["clic"] = None

        vis = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        for n, (u, v) in punti.items():
            cv2.circle(vis, (int(u * s), int(v * s)), 5, ROSSO, 2, cv2.LINE_AA)
        if i < len(PUNTI):
            titolo = f"Punto {i + 1}/{len(PUNTI)}: {PUNTI[i][2]}"
        else:
            titolo = "Tutti i punti chiesti. Premi F per calcolare."
        aiuto = "clic = segna | S = non visibile | U = annulla | frecce/IJKL = sposta di 1 px | , . = fotogramma | F = fine | Esc = esci"
        cv2.rectangle(vis, (0, 0), (vis.shape[1], 52), (0, 0, 0), -1)
        cv2.putText(vis, titolo, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(vis, aiuto + f" | segnati {len(punti)} | fotogramma {n_frame}",
                    (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
        sc = schema_campo(stato, i if i < len(PUNTI) else -1)
        vis[vis.shape[0] - sc.shape[0]:, :sc.shape[1]] = sc
        cont = frame.copy()
        for n, (u, v) in punti.items():
            cv2.circle(cont, (int(round(u)), int(round(v))), 2, ROSSO, -1)
        L = lente(cont, mouse["u"], mouse["v"])
        x0 = vis.shape[1] - L.shape[1] - 10 if mouse["u"] * s < vis.shape[1] / 2 else 10
        vis[60:60 + L.shape[0], x0:x0 + L.shape[1]] = L
        cv2.imshow(finestra, vis)

        k = cv2.waitKeyEx(20)
        if cv2.getWindowProperty(finestra, cv2.WND_PROP_VISIBLE) < 1 or k == 27:
            cv2.destroyAllWindows()
            print("Uscito senza salvare.")
            return
        if k == -1:
            continue
        kk = k & 0xFF if k < 256 else k
        if kk in (ord("s"), ord("S")) and i < len(PUNTI):
            stato[PUNTI[i][0]] = "saltato"; storia.append(None); i += 1
        elif kk in (ord("u"), ord("U"), 8) and storia:
            ultimo = storia.pop(); i -= 1
            stato.pop(PUNTI[i][0], None)
            if ultimo:
                punti.pop(ultimo, None)
        elif k in FRECCE and storia and storia[-1]:
            du, dv = FRECCE[k]
            punti[storia[-1]][0] += du; punti[storia[-1]][1] += dv
        elif kk in (ord(","), ord(".")):
            frame, n_frame, _ = leggi_fotogramma(video, n_frame + (10 if kk == ord(".") else -10))
        elif kk in (ord("f"), ord("F")):
            if len(punti) < MIN_PUNTI:
                print(f"Servono almeno {MIN_PUNTI} punti (ne hai {len(punti)}).")
                continue
            cal = calcola(punti, (w, h))
            print(f"Errore medio di riproiezione: {cal['errore_rms_px']:.2f} px")
            for n, e in sorted(cal["errore_per_punto_px"].items(), key=lambda t: -t[1]):
                print(f"   {n:26s} {e:6.2f} px")
            controllo = cv2.resize(disegna_controllo(frame, cal, punti), None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            cv2.putText(controllo, "Le righe verdi cadono su quelle vere?  Invio = salva   R = ricomincia   Esc = esci",
                        (10, controllo.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.imshow(finestra, controllo)
            while True:
                k2 = cv2.waitKeyEx(50)
                if k2 in (13, 10):
                    salva(video, n_frame, frame, punti, cal)
                    cv2.destroyAllWindows()
                    return
                if k2 in (ord("r"), ord("R")):
                    punti, stato, storia, i = {}, {}, [], 0
                    break
                if k2 == 27 or cv2.getWindowProperty(finestra, cv2.WND_PROP_VISIBLE) < 1:
                    cv2.destroyAllWindows()
                    print("Uscito senza salvare.")
                    return


def verifica(video):
    """Rifa' calcolo e immagine di controllo da una calibrazione gia' salvata (niente finestre)."""
    pj, _, _ = percorsi(video)
    if not os.path.exists(pj):
        raise SystemExit(f"Nessuna calibrazione per questo video: {pj}")
    dati = json.load(open(pj, encoding="utf-8"))
    frame, n, _ = leggi_fotogramma(video, dati.get("fotogramma", 0))
    punti = {k: tuple(v) for k, v in dati["punti_px"].items()}
    cal = calcola(punti, (frame.shape[1], frame.shape[0]))
    print(f"Errore medio di riproiezione: {cal['errore_rms_px']:.2f} px, camera a {cal['camera_in_metri']} m")
    salva(video, n, frame, punti, cal)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Calibrazione della camera dalle righe del campo")
    p.add_argument("video")
    p.add_argument("--frame", type=int, default=0, help="fotogramma da cui partire (default 0)")
    p.add_argument("--verifica", action="store_true", help="solo ricalcolo e immagine di controllo, senza finestre")
    a = p.parse_args()
    verifica(a.video) if a.verifica else interattivo(a.video, a.frame)
