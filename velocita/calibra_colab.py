"""
calibra_colab.py - la calibrazione del campo dentro il notebook di Colab.

calibra_campo.py apre una finestra di OpenCV e legge mouse e tastiera: su Colab
non si puo', perche' il codice gira su un server senza schermo. Qui il
fotogramma viene mostrato nella cella del notebook e i clic li legge il
browser (un pezzetto di JavaScript), poi tornano a Python. Punti, calcolo e
file salvati sono gli stessi di calibra_campo.py.

Nel notebook (cella 7c):

    import calibra_colab
    calibra_colab.calibra("inputs/<video>.mp4", fotogramma=0, cartella_drive=DRIVE_DIR)

Comandi nella cella:
    clic sul fotogramma      segna il punto richiesto
    clic nella lente         corregge l'ultimo punto (la lente ingrandisce 5 volte)
    frecce oppure IJKL       spostano di 1 pixel l'ultimo punto
    S                        punto non visibile: salta
    U                        annulla l'ultimo punto
    F                        fine (servono almeno 6 punti)
Se il giocatore copre le righe, si rilancia con un altro fotogramma.

Costo: il calcolo richiede meno di un secondo di CPU (niente GPU). Il tempo e'
quello dei clic, una volta per posizione della camera: la calibrazione viene
salvata anche su Drive in calibrazioni/ e la cella 4 del notebook la riporta
nelle sessioni successive.
"""

import base64
import json
import os
import shutil

import cv2

from calibra_campo import MIN_PUNTI, PUNTI, RIGHE, calcola, leggi_fotogramma, percorsi, salva

LARGHEZZA_VISTA = 1000         # larghezza del fotogramma nella cella, in pixel dello schermo
QUALITA_JPEG = 90              # il fotogramma va al browser come JPEG (4K: circa 2-3 MB)

# Interfaccia nel browser. rfCalibra(dati) costruisce la pagina nella cella e
# restituisce una Promise che si risolve con {nome_punto: [u, v]} quando si
# preme Fine: google.colab.output.eval_js aspetta la Promise.
JS = r"""
async function rfCalibra(d) {
  const L = 220, Z = 5;                                   // lente: lato in pixel, ingrandimento
  const img = new Image();
  img.src = 'data:image/jpeg;base64,' + d.img;
  await img.decode();
  const s = Math.min(1, d.larghezza / d.w);               // scala fotogramma -> schermo

  const box = document.createElement('div');
  box.style.cssText = 'font-family:sans-serif;font-size:14px;color:#111;background:#fff;padding:8px';
  document.body.appendChild(box);
  const info = document.createElement('div');
  info.style.cssText = 'font-size:16px;margin-bottom:6px;min-height:40px';
  box.appendChild(info);
  const barra = document.createElement('div');
  barra.style.marginBottom = '6px';
  box.appendChild(barra);
  const riga = document.createElement('div');
  riga.style.cssText = 'display:flex;flex-wrap:wrap;gap:10px;align-items:flex-start';
  box.appendChild(riga);

  const cv = document.createElement('canvas');
  cv.width = Math.round(d.w * s); cv.height = Math.round(d.h * s);
  cv.style.cssText = 'cursor:crosshair;border:1px solid #888;max-width:100%;height:auto';   // si stringe se la cella e\' stretta
  cv.tabIndex = 0;
  riga.appendChild(cv);
  const destra = document.createElement('div');
  riga.appendChild(destra);
  const lente = document.createElement('canvas');
  lente.width = L; lente.height = L;
  lente.style.cssText = 'cursor:crosshair;border:1px solid #888;display:block;margin-bottom:8px';
  destra.appendChild(lente);
  const schema = document.createElement('canvas');
  schema.width = 165; schema.height = 290;
  schema.style.cssText = 'border:1px solid #888;display:block';
  destra.appendChild(schema);
  const aiuto = document.createElement('div');
  aiuto.style.cssText = 'font-size:12px;color:#444;margin-top:6px;max-width:220px';
  aiuto.innerHTML = 'clic = segna<br>clic nella lente = corregge l\'ultimo<br>frecce / IJKL = 1 pixel<br>S = salta, U = annulla, F = fine';
  destra.appendChild(aiuto);

  const N = d.punti.length;
  let i = 0;                        // punto richiesto
  const fatti = {};                 // nome -> [u, v] in pixel del fotogramma
  const azioni = [];                // storia, per annullare: {nome, tipo: 'punto' | 'salto'}
  const saltati = new Set();
  let centro = [d.w / 2, d.h / 2];  // centro della lente, pixel del fotogramma
  let risolvi;
  const fine = new Promise(r => { risolvi = r; });

  function bottone(testo, f) {
    const b = document.createElement('button');
    b.textContent = testo; b.style.marginRight = '6px'; b.onclick = () => { f(); cv.focus(); };
    barra.appendChild(b);
  }
  bottone('Salta (S)', salta);
  bottone('Annulla (U)', annulla);
  bottone('Fine (F)', termina);

  function ultimo() {
    for (let k = azioni.length - 1; k >= 0; k--) if (azioni[k].tipo === 'punto') return azioni[k].nome;
    return null;
  }
  function contati() { return Object.keys(fatti).length; }

  function disegna() {
    const c = cv.getContext('2d');
    c.drawImage(img, 0, 0, cv.width, cv.height);
    const u = ultimo();
    d.punti.forEach(([nome], k) => {
      if (!(nome in fatti)) return;
      const [x, y] = fatti[nome];
      c.beginPath(); c.arc(x * s, y * s, 6, 0, 2 * Math.PI);
      c.lineWidth = 2; c.strokeStyle = nome === u ? '#ff2020' : '#ffd000'; c.stroke();
      c.fillStyle = '#ffffff'; c.font = 'bold 12px sans-serif'; c.fillText(String(k + 1), x * s + 8, y * s - 8);
    });
    disegnaLente(); disegnaSchema();
    if (i < N) {
      info.innerHTML = '<b>Punto ' + (i + 1) + ' di ' + N + ':</b> ' + d.punti[i][2] +
        '<br><span style="color:#555">segnati ' + contati() + ' (almeno ' + d.min + ')</span>';
    }
  }

  function disegnaLente() {
    const c = lente.getContext('2d');
    c.imageSmoothingEnabled = false;
    c.fillStyle = '#000'; c.fillRect(0, 0, L, L);
    const w = L / Z;
    c.drawImage(img, centro[0] - w / 2, centro[1] - w / 2, w, w, 0, 0, L, L);
    c.strokeStyle = 'rgba(255,40,40,0.9)'; c.lineWidth = 1;
    c.beginPath(); c.moveTo(L / 2, 0); c.lineTo(L / 2, L); c.moveTo(0, L / 2); c.lineTo(L, L / 2); c.stroke();
    const u = ultimo();
    if (u) {                                  // l'ultimo punto, se e' dentro la lente
      const px = (fatti[u][0] - centro[0]) * Z + L / 2, py = (fatti[u][1] - centro[1]) * Z + L / 2;
      c.beginPath(); c.arc(px, py, 4, 0, 2 * Math.PI); c.strokeStyle = '#ffd000'; c.lineWidth = 2; c.stroke();
    }
  }

  function disegnaSchema() {
    const c = schema.getContext('2d'), k = 10.5, m = 12;
    const P = (x, y) => [m + (x + 1.6) * k, schema.height - m - (y + 0.5) * k];
    c.fillStyle = '#2e6b3a'; c.fillRect(0, 0, schema.width, schema.height);
    c.strokeStyle = '#eee'; c.lineWidth = 1;
    d.righe.forEach(([a, b]) => { const p = P(a[0], a[1]), q = P(b[0], b[1]);
      c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(q[0], q[1]); c.stroke(); });
    d.punti.forEach(([nome, xyz], k2) => {
      const p = P(xyz[0], xyz[1]);
      let col = '#9a9a9a', r = 3;
      if (nome in fatti) col = '#40e040';
      if (saltati.has(nome)) col = '#555';
      if (k2 === i) { col = '#ff2020'; r = 6; }
      c.beginPath(); c.arc(p[0], p[1], r, 0, 2 * Math.PI); c.fillStyle = col; c.fill();
      if (xyz[2] > 0) { c.strokeStyle = '#fff'; c.lineWidth = 1; c.stroke(); }   // punti in alto (rete, pali)
    });
    c.fillStyle = '#fff'; c.font = '11px sans-serif'; c.fillText('lato camera', m, schema.height - 2);
  }

  function segna(u, v) {
    if (i >= N) return;
    const nome = d.punti[i][0];
    fatti[nome] = [u, v]; azioni.push({nome, tipo: 'punto'});
    i += 1; centro = [u, v];
    if (i >= N) { termina(); return; }
    disegna();
  }
  function salta() {
    if (i >= N) return;
    const nome = d.punti[i][0];
    saltati.add(nome); azioni.push({nome, tipo: 'salto'});
    i += 1;
    if (i >= N) { termina(); return; }
    disegna();
  }
  function annulla() {
    const a = azioni.pop();
    if (!a) return;
    if (a.tipo === 'punto') delete fatti[a.nome]; else saltati.delete(a.nome);
    i = d.punti.findIndex(p => p[0] === a.nome);
    disegna();
  }
  function sposta(dx, dy) {
    const u = ultimo();
    if (!u) return;
    fatti[u] = [fatti[u][0] + dx, fatti[u][1] + dy]; centro = fatti[u].slice();
    disegna();
  }
  function termina() {
    if (contati() < d.min) {
      if (i >= N) i = N - 1;                  // punti finiti ma troppo pochi: resta sull'ultimo
      disegna();
      info.innerHTML += '<br><b style="color:#c00">Servono almeno ' + d.min + ' punti. U per annullare e rifare.</b>';
      return;
    }
    document.removeEventListener('keydown', tasti);
    box.innerHTML = '<b>' + contati() + ' punti inviati, calcolo della camera...</b>';
    risolvi(fatti);
  }

  // posizione del mouse in pixel del canvas (senza il bordo), anche se il browser lo ridimensiona
  function suCanvas(e, el) {
    const r = el.getBoundingClientRect();
    return [(e.clientX + 0.5 - r.left - el.clientLeft) * el.width / el.clientWidth,     // +0,5: centro del pixel
            (e.clientY + 0.5 - r.top - el.clientTop) * el.height / el.clientHeight];
  }
  cv.addEventListener('mousemove', e => {
    const [x, y] = suCanvas(e, cv);
    centro = [x / s, y / s];
    disegnaLente();
  });
  cv.addEventListener('click', e => {
    const [x, y] = suCanvas(e, cv);
    segna(x / s, y / s);
    cv.focus();
  });
  lente.addEventListener('click', e => {
    const u = ultimo();
    if (!u) return;
    const [lx, ly] = suCanvas(e, lente);
    fatti[u] = [centro[0] + (lx - L / 2) / Z, centro[1] + (ly - L / 2) / Z];
    disegna();
    cv.focus();
  });
  const FRECCE = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1],
                  j: [-1, 0], l: [1, 0], i: [0, -1], k: [0, 1]};
  function tasti(e) {
    const t = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    if (t in FRECCE) { sposta(...FRECCE[t]); e.preventDefault(); }
    else if (t === 's') salta();
    else if (t === 'u' || t === 'Backspace') { annulla(); e.preventDefault(); }
    else if (t === 'f') termina();
  }
  document.addEventListener('keydown', tasti);

  disegna();
  cv.focus();
  return await fine;
}
"""


def calibra(video, fotogramma=0, cartella_drive=None):
    """
    Calibrazione interattiva nella cella del notebook. Salva come calibra_campo.py:
    velocita/calibrazioni/<video>.json e <video>_campo.jpg, e copia il JSON in
    <cartella_drive>/calibrazioni/ perche' valga anche nelle prossime sessioni.
    """
    from google.colab import output                    # solo su Colab
    from IPython.display import Image, Javascript, display

    frame, n, totale = leggi_fotogramma(video, fotogramma)
    h, w = frame.shape[:2]
    ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, QUALITA_JPEG])
    dati = {"img": base64.b64encode(jpg.tobytes()).decode(), "w": w, "h": h, "min": MIN_PUNTI,
            "larghezza": LARGHEZZA_VISTA,
            "punti": [[nome, list(p), descr] for nome, p, descr in PUNTI],
            "righe": [[list(a), list(b)] for a, b in RIGHE]}
    print(f"Fotogramma {n} di {totale} ({w}x{h}). Clicca i punti richiesti; F quando hai finito.")
    display(Javascript(JS + "\nwindow.rfDati = " + json.dumps(dati) + ";"))
    risposta = output.eval_js("rfCalibra(window.rfDati)")

    punti = {nome: (float(u), float(v)) for nome, (u, v) in risposta.items()}
    cal = calcola(punti, (w, h))
    salva(video, n, frame, punti, cal)
    pj, pi, _ = percorsi(video)
    if cartella_drive:
        dest = os.path.join(cartella_drive, "calibrazioni")
        os.makedirs(dest, exist_ok=True)
        shutil.copy(pj, dest)
        print(f"Copiata su Drive: {os.path.join(dest, os.path.basename(pj))}")
    peggiore = max(cal["errore_per_punto_px"].items(), key=lambda t: t[1])
    print(f"{len(punti)} punti, errore medio {cal['errore_rms_px']:.1f} px (il peggiore: {peggiore[0]}, "
          f"{peggiore[1]} px). Camera a {cal['camera_in_metri']} m, focale {cal['focale_px']} px.")
    print("Controllo: le righe verdi devono cadere su quelle vere. Se no, riesegui la cella.")
    display(Image(pi, width=900))
    return cal
