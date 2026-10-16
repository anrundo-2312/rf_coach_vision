"""
segna_rimbalzo.py - indicare a mano il rimbalzo di un colpo, con un clic sul video (17 ottobre).

    python velocita/segna_rimbalzo.py --video inputs/<video>.mp4 --colpo 52 --cartella <cartella dei rimbalzi>

Si usa sul PC (serve una finestra). Si apre il video poco dopo il colpo:
  D o freccia destra    fotogramma dopo          A o freccia sinistra   fotogramma prima
  W o freccia su        10 fotogrammi avanti     S o freccia giu'       10 fotogrammi indietro
  clic sinistro         la pallina tocca terra QUI, in questo fotogramma: si apre lo ZOOM
                        (ingrandito 5 volte) e un clic nello zoom corregge il punto
  C                     questo fotogramma e' il contatto (facoltativo)
  INVIO                 salva e chiudi           ESC o Q                esci senza salvare

Salva una riga in <cartella>/<video>.csv (nome del video senza il suffisso dei
pesi, come la legge rimbalzo_a_mano.py); se il colpo c'era gia', la riga si
sostituisce. Il colpo e' il fotogramma della colonna frame di
<video>_velocita.csv. Poi si esegue rimbalzo_a_mano.py (nel notebook, dopo
velocita_rimbalzo.py) e disegna_velocita.py.
"""

import argparse
import csv
import os
import re

import cv2
import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
CARTELLA = os.path.join(QUI, "rimbalzi_a_mano")          # come in rimbalzo_a_mano.py
SUFFISSO_PESI = re.compile(r"_(run\w+|badminton)$")   # etichetta dei pesi (ball_tracknet.etichetta_pesi): _run3b, _run4...


def nome_base(nome):
    """Il nome del video senza il suffisso dei pesi (come rimbalzo_a_mano.nome_base)."""
    return SUFFISSO_PESI.sub("", nome)


CAMPI = ["colpo", "rimbalzo_frame", "rimbalzo_x", "rimbalzo_y", "contatto_frame"]
SCHERMO = (1500, 850)        # dimensione massima della finestra principale
ZOOM, ZOOM_LATO = 5, (120, 80)
# tasti freccia: Windows (waitKeyEx) e Linux
SINISTRA, DESTRA, SU, GIU = (2424832, 65361), (2555904, 65363), (2490368, 65362), (2621440, 65364)


def salva_riga(percorso, riga):
    """Scrive (o sostituisce, stesso colpo) la riga nel file dei rimbalzi."""
    righe = []
    if os.path.exists(percorso):
        righe = [r for r in csv.DictReader(open(percorso, encoding="utf-8-sig"))
                 if (r.get("colpo") or "").strip() and int(float(r["colpo"])) != int(riga["colpo"])]
    righe.append({k: riga.get(k, "") for k in CAMPI})
    righe.sort(key=lambda r: int(float(r["colpo"])))
    os.makedirs(os.path.dirname(percorso) or ".", exist_ok=True)
    with open(percorso, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPI)
        w.writeheader()
        w.writerows(righe)


class Segna:
    """Stato dello strumento (separato dalla finestra, cosi' si prova anche senza schermo)."""

    def __init__(self, video, colpo, da=None):
        self.cap = cv2.VideoCapture(video)
        if not self.cap.isOpened():
            raise SystemExit(f"Non riesco ad aprire {video}")
        self.n_tot = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.W = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.H = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.s = min(SCHERMO[0] / self.W, SCHERMO[1] / self.H, 1.0)
        self.colpo = colpo
        self.n = min(self.n_tot, max(1, da if da else colpo + int(0.5 * self.fps)))
        self.rimbalzo = None          # (frame, x, y) nei pixel del video
        self.contatto = None
        self._cache = {}

    def fotogramma(self, n):
        if n not in self._cache:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, n - 1)
            ok, f = self.cap.read()
            if not ok:
                f = np.zeros((self.H, self.W, 3), np.uint8)
            if len(self._cache) > 40:
                self._cache.clear()
            self._cache[n] = f
        return self._cache[n]

    def vai(self, passo):
        self.n = int(min(self.n_tot, max(1, self.n + passo)))

    def clic(self, xs, ys):
        """clic nella finestra principale (coordinate dello schermo)"""
        self.rimbalzo = (self.n, xs / self.s, ys / self.s)

    def riquadro_zoom(self):
        _, x, y = self.rimbalzo
        x0 = int(min(max(0, x - ZOOM_LATO[0] / 2), self.W - ZOOM_LATO[0]))
        y0 = int(min(max(0, y - ZOOM_LATO[1] / 2), self.H - ZOOM_LATO[1]))
        return x0, y0

    def clic_zoom(self, xz, yz):
        """clic nello zoom: corregge il punto (nel fotogramma del rimbalzo)"""
        x0, y0 = self.riquadro_zoom()
        self.rimbalzo = (self.rimbalzo[0], x0 + xz / ZOOM, y0 + yz / ZOOM)

    def segna_contatto(self):
        self.contatto = self.n

    def riga(self):
        if self.rimbalzo is None:
            return None
        f, x, y = self.rimbalzo
        return {"colpo": self.colpo, "rimbalzo_frame": f, "rimbalzo_x": round(x), "rimbalzo_y": round(y),
                "contatto_frame": "" if self.contatto is None else self.contatto}

    def immagine(self):
        f = self.fotogramma(self.n).copy()
        if self.rimbalzo is not None and self.rimbalzo[0] == self.n:
            cv2.circle(f, (int(self.rimbalzo[1]), int(self.rimbalzo[2])), 9, (0, 0, 255), 2)
        img = cv2.resize(f, (int(self.W * self.s), int(self.H * self.s)), interpolation=cv2.INTER_AREA)
        righe = [f"colpo {self.colpo} - fotogramma {self.n} ({(self.n - 1) / self.fps:.2f} s)",
                 "rimbalzo: " + ("-" if self.rimbalzo is None else
                                 f"fotogramma {self.rimbalzo[0]}, pixel ({self.rimbalzo[1]:.0f}; {self.rimbalzo[2]:.0f})")
                 + "   contatto: " + ("-" if self.contatto is None else f"fotogramma {self.contatto}"),
                 "D/A +-1   W/S +-10   clic = rimbalzo   C = contatto   INVIO = salva   ESC = esci"]
        for i, t in enumerate(righe):
            cv2.putText(img, t, (10, 28 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 4)
            cv2.putText(img, t, (10, 28 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1)
        return img

    def immagine_zoom(self):
        f = self.fotogramma(self.rimbalzo[0])
        x0, y0 = self.riquadro_zoom()
        z = cv2.resize(f[y0:y0 + ZOOM_LATO[1], x0:x0 + ZOOM_LATO[0]], None, fx=ZOOM, fy=ZOOM,
                       interpolation=cv2.INTER_NEAREST)
        cx, cy = int((self.rimbalzo[1] - x0) * ZOOM), int((self.rimbalzo[2] - y0) * ZOOM)
        cv2.line(z, (cx - 14, cy), (cx + 14, cy), (0, 0, 255), 1)
        cv2.line(z, (cx, cy - 14), (cx, cy + 14), (0, 0, 255), 1)
        return z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--colpo", type=int, required=True, help="fotogramma del colpo (colonna frame di <video>_velocita.csv)")
    ap.add_argument("--cartella", default=CARTELLA)
    ap.add_argument("--da", type=int, help="fotogramma da cui partire (di default mezzo secondo dopo il colpo)")
    a = ap.parse_args()
    st = Segna(a.video, a.colpo, a.da)
    nome = nome_base(os.path.splitext(os.path.basename(a.video))[0])
    percorso = os.path.join(a.cartella, nome + ".csv")
    cv2.namedWindow("rimbalzo", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("rimbalzo", lambda ev, x, y, *_: st.clic(x, y) if ev == cv2.EVENT_LBUTTONDOWN else None)
    zoom_aperto = False
    while True:
        cv2.imshow("rimbalzo", st.immagine())
        if st.rimbalzo is not None:
            cv2.imshow("zoom", st.immagine_zoom())
            if not zoom_aperto:
                cv2.setMouseCallback("zoom", lambda ev, x, y, *_: st.clic_zoom(x, y) if ev == cv2.EVENT_LBUTTONDOWN else None)
                zoom_aperto = True
        k = cv2.waitKeyEx(50)
        if k == -1:
            continue
        if k in (27, ord("q"), ord("Q")):
            print("uscito senza salvare")
            break
        if k in (13, 10):
            r = st.riga()
            if r is None:
                print("nessun rimbalzo indicato: clic sulla pallina dove tocca terra, poi INVIO")
                continue
            salva_riga(percorso, r)
            print(f"salvato in {percorso}: {r}")
            break
        if k in (ord("d"), ord("D")) or k in DESTRA:
            st.vai(1)
        elif k in (ord("a"), ord("A")) or k in SINISTRA:
            st.vai(-1)
        elif k in (ord("w"), ord("W")) or k in SU:
            st.vai(10)
        elif k in (ord("s"), ord("S")) or k in GIU:
            st.vai(-10)
        elif k in (ord("c"), ord("C")):
            st.segna_contatto()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
