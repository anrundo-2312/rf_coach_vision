"""
riepilogo.py - le metriche della sessione di un video: quanti colpi per tipo,
quanti dentro e quanti fuori, errori, profondita', direzioni, velocita'. E la
scheda da mandare all'allievo.

    python velocita/riepilogo.py --video inputs/<video>.mp4

Legge outputs/dati/<video>_velocita_punti.json (dopo velocita_rimbalzo.py) e
scrive in outputs/dati:
  <video>_riepilogo.csv   una riga per tipo di colpo (servizio, dritto,
                          rovescio) piu' il totale;
  <video>_riepilogo.json  le stesse cose, piu' la lista dei rimbalzi;
  <video>_scheda.png      la scheda per l'allievo: i numeri e la mappa dei
                          rimbalzi.
disegna_velocita.py lo chiama da solo e mette la stessa scheda alla fine del
video: di solito non serve eseguirlo a parte.

Regole (decise il 2 ottobre):
- si contano i colpi con almeno una velocita' o una direzione. Quelli senza
  niente (sul video in grigio, "km/h non disponibile") sono spesso falsi colpi
  (alcaraz 1302: il giocatore cammina) e vanno a parte, "rilevati senza dati";
- colpo buono = rimbalzo DENTRO (dritti e rovesci nel campo singolo, servizio
  nel riquadro in diagonale, la riga conta dentro: velocita_uscita.dentro_fuori);
  errore = FUORI (lunga, larga). Se il rimbalzo non si e' visto l'esito e'
  "non visto": non conta ne' come buono ne' come errore. "3/4 dentro" vuol dire
  3 dentro su 4 colpi con l'esito visto; la percentuale e' su quei 4. La rete
  non si riconosce ancora: un colpo in rete e' "non visto";
- velocita' d'uscita: misurate (velocita_uscita.py) e stimate dal rimbalzo
  (velocita_rimbalzo.py, circa +-15-20%) insieme; si dice quante sono le une e
  le altre. Velocita' media del volo: la colonna velocita_media_kmh (distanza
  dal contatto al rimbalzo / tempo di volo, velocita_rimbalzo.py passo 7).
- percentuale di errori per tipo di colpo: fuori / colpi con l'esito visto
  (errori_percento). Nel servizio "dentro" vuol dire servizio valido (nel
  riquadro in diagonale) e "fuori" fallo: la scheda dice "validi" e "falli".

Correzione delle velocita' (decisa dall'utente il 2 ottobre): le velocita'
MOSTRATE (uscita misurata, stimata dal rimbalzo e media del volo; nel video,
nella scheda e in <video>_riepilogo.csv/.json) sono quelle calcolate per
CORREZIONE_VELOCITA = 0,85, cioe' il 15% in meno: all'utente i valori
sembravano un po' alti. E' una stima a occhio, da verificare (per esempio con
SwingVision accanto). Il calcolo non cambia: in <video>_velocita.csv restano i
valori calcolati. Con 1.0 non si corregge niente.
"""

import argparse
import csv
import json
import os
from collections import Counter

import numpy as np

CORREZIONE_VELOCITA = 0.85   # velocita' mostrate = calcolate x 0,85 (vedi sopra); 1.0 = nessuna correzione

TIPI = ["servizio", "dritto", "rovescio"]
NOMI = {"servizio": "Servizi", "dritto": "Dritti", "rovescio": "Rovesci", "totale": "Totale"}
SINGOLARE = {"servizio": "servizio", "dritto": "dritto", "rovescio": "rovescio"}

# scheda: colori dei tipi di colpo (stesse tinte del video, piu' scure per lo sfondo scuro: verificate
# per chi non distingue i colori; in piu' ogni tipo ha la sua forma sulla mappa)
COLORE_SCHEDA = {"dritto": "#199e70", "rovescio": "#3987e5", "servizio": "#c98500"}
FORMA = {"dritto": "cerchio", "rovescio": "rombo", "servizio": "quadrato"}
SFONDO, SFONDO_2 = "#1a1a19", "#262624"
TESTO, TESTO_2, TESTO_3 = "#ffffff", "#c3c2b7", "#8f8e86"
ROSSO = "#d03b3b"          # fuori
RIGHE = "#8f8e86"


# ------------------------------------------------------------------ metriche
def corretta(kmh):
    """La velocita' da mostrare: quella calcolata per CORREZIONE_VELOCITA, arrotondata (None se manca)."""
    return None if kmh in (None, "") else int(round(float(kmh) * CORREZIONE_VELOCITA))


def velocita_uscita(c):
    """(km/h, "misurata" o "stimata") o None."""
    if c.get("velocita_uscita_kmh", "") not in ("", None):
        return float(c["velocita_uscita_kmh"]), "misurata"
    if c.get("velocita_rimbalzo_kmh", "") not in ("", None):
        return float(c["velocita_rimbalzo_kmh"]), "stimata"
    return None


def ha_dati(c):
    """Il colpo ha almeno una velocita' o una direzione (gli altri non si contano)."""
    return bool(c.get("direzione")) or velocita_uscita(c) is not None


def esito(c):
    """"dentro", "fuori" o None (rimbalzo non visto)."""
    e = c.get("dentro_fuori", "")
    return e if e in ("dentro", "fuori") else None


def motivo_fuori(c):
    """Perche' e' fuori, in parole: lunga, larga, oltre la riga centrale (servizio)."""
    riga = str(c.get("riga_vicina", ""))
    return ("lunga" if riga in ("fondo", "servizio") else "larga" if riga.startswith("laterale")
            else "oltre la riga centrale" if riga == "centrale" else riga or "fuori")


def _media(xs):
    return round(float(np.mean(xs))) if xs else None


def riga_tipo(colpi, tipo):
    """Le metriche di un tipo di colpo ("totale" = tutti)."""
    cs = [c for c in colpi if ha_dati(c) and (tipo == "totale" or c["colpo"] == tipo)]
    dentro = [c for c in cs if esito(c) == "dentro"]
    fuori = [c for c in cs if esito(c) == "fuori"]
    motivi = Counter(motivo_fuori(c) for c in fuori)
    prof = Counter(c.get("profondita", "") for c in dentro if c["colpo"] != "servizio")
    # velocita' mostrate: corrette (CORREZIONE_VELOCITA)
    vel = [(corretta(x[0]), x[1]) for x in map(velocita_uscita, cs) if x is not None]
    volo = [corretta(c["velocita_media_kmh"]) for c in cs if c.get("velocita_media_kmh", "") not in ("", None)]
    con_esito = len(dentro) + len(fuori)
    return {
        "colpo": tipo, "colpi": len(cs),
        "dentro": len(dentro), "fuori": len(fuori), "esito_non_visto": len(cs) - con_esito,
        "dentro_percento": round(100 * len(dentro) / con_esito) if con_esito else None,
        "errori_percento": round(100 * len(fuori) / con_esito) if con_esito else None,
        "fuori_lunga": motivi.get("lunga", 0), "fuori_larga": motivi.get("larga", 0),
        "fuori_altro": sum(n for m, n in motivi.items() if m not in ("lunga", "larga")),
        "profonde": prof.get("profonda", 0), "medie": prof.get("media", 0), "corte": prof.get("corta", 0),
        "palle_corte": prof.get("palla corta", 0),
        "uscita_media_kmh": _media([v for v, _ in vel]),
        "uscita_max_kmh": round(max(v for v, _ in vel)) if vel else None,
        "uscita_misurate": sum(1 for _, k in vel if k == "misurata"),
        "uscita_stimate": sum(1 for _, k in vel if k == "stimata"),
        "volo_media_kmh": _media(volo), "volo_colpi": len(volo),
        "direzioni": dict(Counter(c["direzione"] for c in cs if c.get("direzione")).most_common()),
        # dritti inside-out / inside-in (velocita_uscita.tipo_dritto): quanti, e quanti dentro su quelli con esito
        **{f"{k.replace('-', '_')}{s}": v for k in ("inside-out", "inside-in")
           for s, v in (("", sum(1 for c in cs if c.get("dritto_tipo") == k)),
                        ("_dentro", sum(1 for c in cs if c.get("dritto_tipo") == k and esito(c) == "dentro")),
                        ("_con_esito", sum(1 for c in cs if c.get("dritto_tipo") == k and esito(c))))},
    }


def calcola(colpi, nome="", durata_s=None):
    """Il riepilogo del video (dizionario)."""
    tipi = [riga_tipo(colpi, t) for t in TIPI if any(c["colpo"] == t and ha_dati(c) for c in colpi)]
    rimbalzi = [{"frame": int(c["frame"]), "colpo": c["colpo"], "x_m": float(c["rimbalzo_trovato_x_m"]),
                 "y_m": float(c["rimbalzo_trovato_y_m"]), "esito": esito(c),
                 "come": c.get("rimbalzo_trovato_come", "")}
                for c in colpi if ha_dati(c) and c.get("rimbalzo_trovato_x_m", "") not in ("", None)]
    return {"video": nome, "durata_s": None if durata_s is None else round(float(durata_s), 1),
            "correzione_velocita": CORREZIONE_VELOCITA,
            "tipi": tipi, "totale": riga_tipo(colpi, "totale"),
            "senza_dati": [int(c["frame"]) for c in colpi if not ha_dati(c)],
            "rimbalzi": rimbalzi}


def testo_direzioni(d):
    return "; ".join(f"{k} {n}" for k, n in d.items())


def salva(rie, cartella_dati, sfondo_scheda=None):
    """Scrive <video>_riepilogo.csv, <video>_riepilogo.json e <video>_scheda.png. Ritorna i percorsi."""
    import cv2
    base = os.path.join(cartella_dati, rie["video"])
    campi = [k for k in rie["totale"] if k != "direzioni"] + ["direzioni"]
    with open(base + "_riepilogo.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campi)
        w.writeheader()
        for r in rie["tipi"] + [rie["totale"]]:
            w.writerow({**r, "direzioni": testo_direzioni(r["direzioni"])})
    json.dump(rie, open(base + "_riepilogo.json", "w"), indent=1, ensure_ascii=False)
    cv2.imwrite(base + "_scheda.png", scheda(rie, 1920, 1080, sfondo_scheda))
    return base + "_riepilogo.csv", base + "_riepilogo.json", base + "_scheda.png"


# ------------------------------------------------------------------ scheda (immagine)
def _font(dim, grassetto=False):
    """DejaVu (c'e' con matplotlib, quindi su Colab e sul PC), se no Segoe/Arial di Windows, se no quello di PIL."""
    from PIL import ImageFont
    nomi = ["DejaVuSans-Bold.ttf", "segoeuib.ttf", "arialbd.ttf"] if grassetto else ["DejaVuSans.ttf", "segoeui.ttf", "arial.ttf"]
    cartelle = []
    try:
        import matplotlib
        cartelle.append(os.path.join(matplotlib.get_data_path(), "fonts", "ttf"))
    except ImportError:
        pass
    cartelle += ["/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts", ""]
    for d in cartelle:
        for n in nomi:
            try:
                return ImageFont.truetype(os.path.join(d, n) if d else n, dim)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=dim)
    except TypeError:
        return ImageFont.load_default()


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _num(x, dec=1):
    return f"{x:.{dec}f}".replace(".", ",")


def _marcatore(d, forma, cx, cy, r, colore, pieno=True, bordo=None, spessore=2):
    """Cerchio, rombo o quadrato centrato in (cx, cy)."""
    riemp = colore if pieno else None
    out = colore if not pieno else (bordo or SFONDO)
    if forma == "cerchio":
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=riemp, outline=out, width=spessore)
    elif forma == "rombo":
        r2 = r * 1.2
        d.polygon([(cx, cy - r2), (cx + r2, cy), (cx, cy + r2), (cx - r2, cy)], fill=riemp, outline=out, width=spessore)
    else:
        r2 = r * 0.9
        d.rectangle([cx - r2, cy - r2, cx + r2, cy + r2], fill=riemp, outline=out, width=spessore)


def scheda(rie, W=1920, H=1080, sfondo=None):
    """
    La scheda come immagine BGR (W x H). sfondo: un fotogramma BGR (l'ultimo del video) da sfocare e
    scurire dietro la scheda; None = fondo scuro pieno.
    """
    import cv2
    from PIL import Image, ImageDraw
    k = H / 1080
    if sfondo is not None:
        bg = cv2.GaussianBlur(cv2.resize(sfondo, (W, H)), (0, 0), 25 * k)
        bg = cv2.addWeighted(bg, 0.25, np.full_like(bg, _rgb(SFONDO)[::-1]), 0.75, 0)
        img = Image.fromarray(cv2.cvtColor(bg, cv2.COLOR_BGR2RGB))
    else:
        img = Image.new("RGB", (W, H), SFONDO)
    d = ImageDraw.Draw(img)
    F = lambda n, b=False: _font(int(round(n * k)), b)
    X = lambda v: int(round(v * k))
    m = X(64)

    # intestazione
    tot = rie["totale"]
    d.text((m, X(48)), "Riepilogo della sessione", font=F(52, True), fill=TESTO)
    sotto = [rie["video"]]
    if rie.get("durata_s"):
        sotto.append(f"{_num(rie['durata_s'])} s di video")
    sotto.append(f"{tot['colpi']} colpi" if tot["colpi"] != 1 else "1 colpo")
    d.text((m, X(118)), "  ·  ".join(sotto), font=F(26), fill=TESTO_2)
    # in alto a destra i numeri della sessione: dentro e errori sui colpi con esito, servizi validi
    con_esito = tot["dentro"] + tot["fuori"]
    srv = next((r for r in rie["tipi"] if r["colpo"] == "servizio"), None)
    srv_esito = srv["dentro"] + srv["fuori"] if srv else 0
    riquadri = [("Dentro", f"{tot['dentro']}/{con_esito}" if con_esito else "–",
                 f"{tot['dentro_percento']}% dei colpi" if con_esito else "esito mai visto"),
                ("Errori", f"{tot['fuori']}" if con_esito else "–",
                 f"{tot['errori_percento']}% dei colpi" if con_esito else "esito mai visto"),
                ("Servizi validi", f"{srv['dentro']}/{srv_esito}" if srv_esito else "–",
                 f"{srv['dentro_percento']}%" if srv_esito else ("esito mai visto" if srv else "nessun servizio"))]
    xr = X(1250)
    for titolo, valore, nota in riquadri:
        d.rounded_rectangle([xr, X(40), xr + X(190), X(150)], radius=X(14), fill=SFONDO_2)
        d.text((xr + X(18), X(52)), titolo, font=F(21), fill=TESTO_2)
        d.text((xr + X(18), X(80)), valore, font=F(40, True), fill=TESTO)
        d.text((xr + X(18), X(124)), nota, font=F(17), fill=TESTO_3)
        xr += X(203)

    # una riga per tipo di colpo
    x0, x1 = m, X(1170)
    y = X(186)
    alt = X(232) if len(rie["tipi"]) <= 3 else X(170)
    for r in rie["tipi"]:
        tipo = r["colpo"]
        # righe in fondo: direzioni, profondita' (dritti e rovesci dentro), inside-out / inside-in (dritti)
        sotto = ["Direzioni: " + ("  ·  ".join(f"{t} {n}" for t, n in r["direzioni"].items()) or "–")]
        if tipo != "servizio" and r["dentro"]:
            sotto.append(f"Profondità (dentro): profonde {r['profonde']}  ·  medie {r['medie']}  ·  corte {r['corte']}"
                         f"  ·  palle corte {r['palle_corte']}")
        if r.get("inside_out") or r.get("inside_in"):
            sotto.append("Dal lato del rovescio: " + "  ·  ".join(
                f"{t} {r[k]}" + (f" ({r[k + '_dentro']}/{r[k + '_con_esito']} dentro)" if r[k + "_con_esito"] else "")
                for t, k in (("inside-out", "inside_out"), ("inside-in", "inside_in")) if r[k]))
        alt_r = alt + X(27) * max(0, len(sotto) - 2)
        d.rounded_rectangle([x0, y, x1, y + alt_r - X(18)], radius=X(14), fill=SFONDO_2)
        d.rounded_rectangle([x0, y, x0 + X(8), y + alt_r - X(18)], radius=X(4), fill=COLORE_SCHEDA[tipo])
        _marcatore(d, FORMA[tipo], x0 + X(44), y + X(42), X(11), COLORE_SCHEDA[tipo])
        d.text((x0 + X(68), y + X(22)), NOMI[tipo], font=F(34, True), fill=TESTO)
        d.text((x0 + X(68), y + X(66)), f"{r['colpi']} colpi" if r["colpi"] != 1 else "1 colpo", font=F(22), fill=TESTO_2)

        # colonna 1: dentro / con esito
        cx = x0 + X(290)
        con_esito = r["dentro"] + r["fuori"]
        if con_esito:
            d.text((cx, y + X(14)), f"{r['dentro']}/{con_esito}", font=F(58, True), fill=TESTO)
            d.text((cx, y + X(84)), f"{'validi' if tipo == 'servizio' else 'dentro'}  ·  {r['dentro_percento']}%",
                   font=F(22), fill=TESTO_2)
        else:
            d.text((cx, y + X(14)), "–", font=F(58, True), fill=TESTO_3)
            d.text((cx, y + X(84)), "esito non visto", font=F(22), fill=TESTO_2)
        if r["esito_non_visto"] and con_esito:
            d.text((cx, y + X(112)), f"+{r['esito_non_visto']} con esito non visto", font=F(19), fill=TESTO_3)


        # colonna 2: errori
        cx = x0 + X(540)
        d.text((cx, y + X(20)), "Falli" if tipo == "servizio" else "Errori", font=F(22), fill=TESTO_2)
        if not con_esito:
            d.text((cx, y + X(50)), "–", font=F(40, True), fill=TESTO_3)
        else:
            d.text((cx, y + X(52)), f"{r['fuori']} · {r['errori_percento']}%", font=F(36, True), fill=TESTO)
            motivi = [f"{n} {t}" for t, n in (("lung" + ("o" if tipo == "servizio" else "a"), r["fuori_lunga"]),
                                              ("larg" + ("o" if tipo == "servizio" else "a"), r["fuori_larga"]),
                                              ("altro", r["fuori_altro"])) if n]
            if motivi:
                d.text((cx, y + X(98)), ", ".join(motivi), font=F(20), fill=TESTO_2)

        # colonna 3: velocita' (gia' corrette, CORREZIONE_VELOCITA)
        cx = x0 + X(770)
        d.text((cx, y + X(20)), "Velocità d'uscita", font=F(22), fill=TESTO_2)
        if r["uscita_media_kmh"] is not None:
            d.text((cx, y + X(50)), f"{r['uscita_media_kmh']} km/h", font=F(40, True), fill=TESTO)
            dett = [f"max {r['uscita_max_kmh']}"]
            if r["uscita_misurate"]:
                dett.append(f"{r['uscita_misurate']} misurat{'a' if r['uscita_misurate'] == 1 else 'e'}")
            if r["uscita_stimate"]:
                dett.append(f"{r['uscita_stimate']} stimat{'a' if r['uscita_stimate'] == 1 else 'e'}")
            d.text((cx, y + X(98)), ", ".join(dett), font=F(20), fill=TESTO_2)
            if r["volo_media_kmh"] is not None:
                d.text((cx, y + X(126)), f"media in volo {r['volo_media_kmh']} km/h", font=F(20), fill=TESTO_2)
        else:
            d.text((cx, y + X(50)), "–", font=F(40, True), fill=TESTO_3)

        # righe in fondo
        fy = y + alt_r - X(18) - X(9) - X(27) * len(sotto)
        for riga in sotto:
            d.text((x0 + X(68), fy), _taglia(d, riga, F(20), x1 - x0 - X(90)), font=F(20), fill=TESTO_2)
            fy += X(27)
        y += alt_r

    # mappa dei rimbalzi: meta' campo avversario vista dall'alto, rete in basso
    _mappa_rimbalzi(d, rie, X(1250), X(200), X(1856), X(880), k)

    # note
    note = ["Dentro/fuori dal rimbalzo nel campo avversario; \"esito non visto\" = rimbalzo non trovato, "
            "non conta né come dentro né come fuori.",
            "Velocità stimate dal rimbalzo: margine circa ±15-20%. Media in volo = distanza dal colpo al "
            "rimbalzo / tempo di volo."]
    if rie.get("correzione_velocita", 1.0) != 1.0:
        note.append(f"Velocità mostrate = calcolate × {_num(rie['correzione_velocita'], 2)} "
                    f"(correzione di {round(100 * (1 - rie['correzione_velocita']))}% decisa a occhio, da verificare).")
    if rie["senza_dati"]:
        n = len(rie["senza_dati"])
        note.append(f"Non contati: {n} colp{'o' if n == 1 else 'i'} rilevat{'o' if n == 1 else 'i'} senza dati "
                    f"(frame {', '.join(map(str, rie['senza_dati']))}), spesso falsi colpi.")
    yn = H - X(40) - X(28) * len(note)
    for t in note:
        d.text((m, yn), t, font=F(19), fill=TESTO_3)
        yn += X(28)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _taglia(d, testo, font, larghezza):
    """Accorcia il testo con "..." se non ci sta."""
    if d.textlength(testo, font=font) <= larghezza:
        return testo
    while testo and d.textlength(testo + "…", font=font) > larghezza:
        testo = testo[:-1]
    return testo + "…"


def _mappa_rimbalzi(d, rie, xa, ya, xb, yb, k):
    """Meta' campo avversario (dalla rete a 2,2 m oltre il fondo) con i rimbalzi, e la legenda sotto."""
    F = lambda n, b=False: _font(int(round(n * k)), b)
    X = lambda v: int(round(v * k))
    d.text((xa, ya - X(4)), "Dove è rimbalzata la pallina", font=F(26, True), fill=TESTO)
    top = ya + X(48)
    xm0, xm1, ym0, ym1 = -1.5, 12.47, 11.885, 26.0          # metri mostrati
    scala = min((xb - xa) / (xm1 - xm0), (yb - X(120) - top) / (ym1 - ym0))
    ox = xa + ((xb - xa) - scala * (xm1 - xm0)) / 2
    P = lambda x, y: (ox + (x - xm0) * scala, top + (ym1 - y) * scala)
    # campo
    d.rectangle([*P(0, 23.77), *P(10.97, 11.885)], fill="#1f2a24")
    linee = [((0, 11.885), (0, 23.77)), ((10.97, 11.885), (10.97, 23.77)), ((1.37, 11.885), (1.37, 23.77)),
             ((9.60, 11.885), (9.60, 23.77)), ((0, 23.77), (10.97, 23.77)), ((1.37, 18.285), (9.60, 18.285)),
             ((5.485, 11.885), (5.485, 18.285))]
    for a, b in linee:
        d.line([P(*a), P(*b)], fill=RIGHE, width=max(1, X(2)))
    d.line([P(-0.9, 11.885), P(11.87, 11.885)], fill=TESTO_2, width=max(2, X(4)))
    d.text((P(11.87, 11.885)[0], P(0, 11.885)[1] + X(8)), "rete", font=F(18), fill=TESTO_3, anchor="ra")
    # rimbalzi: forma e colore = tipo di colpo; anello rosso = fuori; vuoto = rimbalzo ricostruito
    r = X(10)
    for b in rie["rimbalzi"]:
        x, y = P(b["x_m"], min(max(b["y_m"], ym0), ym1))
        if b["esito"] == "fuori":
            d.ellipse([x - r - X(7), y - r - X(7), x + r + X(7), y + r + X(7)], outline=ROSSO, width=X(3))
        _marcatore(d, FORMA[b["colpo"]], x, y, r, COLORE_SCHEDA[b["colpo"]], pieno=b["come"] != "ricostruito",
                   spessore=max(2, X(3)) if b["come"] == "ricostruito" else 2)
    # legenda
    yl = P(0, ym0)[1] + X(26)
    xl = xa
    for t in [t["colpo"] for t in rie["tipi"]]:
        _marcatore(d, FORMA[t], xl + X(10), yl + X(12), X(9), COLORE_SCHEDA[t])
        d.text((xl + X(28), yl), NOMI[t], font=F(20), fill=TESTO_2)
        xl += X(28) + d.textlength(NOMI[t], font=F(20)) + X(26)
    yl += X(36)
    d.ellipse([xa + X(1), yl + X(3), xa + X(19), yl + X(21)], outline=ROSSO, width=X(3))
    d.text((xa + X(28), yl), "fuori", font=F(20), fill=TESTO_2)
    xl = xa + X(28) + d.textlength("fuori", font=F(20)) + X(26)
    d.ellipse([xl + X(1), yl + X(3), xl + X(19), yl + X(21)], outline=TESTO_2, width=X(3))
    d.text((xl + X(28), yl), "rimbalzo coperto, ricostruito", font=F(20), fill=TESTO_2)
    if not rie["rimbalzi"]:
        cx, cy = P(5.485, 21)
        d.text((cx, cy), "nessun rimbalzo trovato", font=F(22), fill=TESTO_3, anchor="mm")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--dati", default="outputs/dati")
    a = ap.parse_args()
    import cv2
    nome = os.path.splitext(os.path.basename(a.video))[0]
    colpi = json.load(open(os.path.join(a.dati, nome + "_velocita_punti.json")))
    cap = cv2.VideoCapture(a.video)
    n, fps = cap.get(cv2.CAP_PROP_FRAME_COUNT), cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    rie = calcola(colpi, nome, n / fps if fps else None)
    for p in salva(rie, a.dati):
        print("scritto", p)
    for r in rie["tipi"] + [rie["totale"]]:
        esiti = f"{r['dentro']}/{r['dentro'] + r['fuori']} dentro" if r["dentro"] + r["fuori"] else "esito mai visto"
        print(f"  {NOMI[r['colpo']]:8s} {r['colpi']:2d} colpi, {esiti}, fuori {r['fuori']} ({r['errori_percento']}%), "
              f"non visto {r['esito_non_visto']}, uscita media {r['uscita_media_kmh']} km/h, volo {r['volo_media_kmh']}")


if __name__ == "__main__":
    main()
