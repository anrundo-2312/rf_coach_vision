# Velocità d'uscita in km/h: come l'abbiamo ottenuta

Questo documento spiega il lavoro fatto sui video di Nicola e di Djokovic per passare dalla velocità in pixel al secondo alla **velocità d'uscita della pallina dalla racchetta, in km/h**, per i colpi del giocatore vicino alla camera.

Il calcolo in km/h è separato da `analyze.py`, che continua a calcolare i px/s: sta tutto nella cartella `velocita/`. Come si usa è in `velocita/LEGGIMI.md`; qui si spiega come funziona e come ci siamo arrivati.

---

## 1. Perché i px/s non bastano

`analyze.py` misura di quanti pixel si sposta la pallina da un frame all'altro. Con la camera dietro al giocatore questo numero non dice quanto va veloce la pallina, per due motivi.

- **La scala cambia con la distanza.** Vicino alla camera un metro occupa molti più pixel che lontano, quindi alla stessa velocità vera corrispondono molti più px/s vicino al giocatore.
- **Il movimento in profondità non si vede.** Dopo il colpo la pallina si allontana quasi lungo la linea di vista della camera. Gran parte della strada che fa è "dentro" l'immagine e nei pixel non compare.

Esempio dal rovescio di Nicola: in 15 frame (0,25 s) la pallina si sposta di 70 pixel. Se li converto con la scala del giocatore (351 pixel per 1,80 m) ottengo circa **5 km/h**, mentre SwingVision indica **59 km/h**. Nessun fattore di conversione può correggere questa differenza: bisogna ricostruire la traiettoria in 3D.

Per ricostruirla servono due cose:

1. sapere **dov'è la camera** rispetto al campo, cioè la calibrazione;
2. un **modello fisico** del volo della pallina: gravità e resistenza dell'aria.

---

## 2. Come si collegano i pezzi

```
video ──> analyze.py (già esistente) ──> tracking.csv: posa del giocatore, pallina di TrackNet
  │
  ├──> calibrazione del campo ──────────> dov'è la camera, con che zoom
  │
  ├──> rilevatore locale della pallina ─> pallina frame per frame vicino al colpo,
  │                                       dove TrackNet la perde
  │
  └──> file dell'amico (rf_ball_exit_speed.py)
            usa: pallina nei ~20 frame dopo il contatto + calibrazione + posizione del giocatore
            dà:  velocità d'uscita in km/h, punto di contatto in metri, rimbalzo previsto
                   │
                   └──> video con la scritta in km/h
                          + metriche della sessione e scheda per l'allievo (riepilogo.py, 8.9)
```

---

## 3. La calibrazione del campo

### Cosa vuol dire calibrare

Una camera si può descrivere con pochi numeri:

- **dove si trova**, in metri, rispetto al campo (x, y, altezza);
- **dove guarda** (orientamento);
- **la focale**, cioè quanto è "zoomata", espressa in pixel.

Conoscendo questi numeri, ogni punto del campo in metri corrisponde a un pixel preciso nell'immagine, e ogni pixel corrisponde a una retta che parte dalla camera. Il modello è quello della fotocamera ideale ("pinhole"): punto principale al centro dell'immagine, pixel quadrati, nessuna distorsione della lente.

### Da dove si ricavano

Da punti del campo di cui conosciamo le misure (regolamento ITF). Le coordinate sono in metri: x lungo la larghezza (0 = riga del doppio a sinistra nell'immagine), y lungo la lunghezza (0 = linea di fondo dal lato della camera), z in altezza.

| Punto | x | y | z |
|---|---|---|---|
| angoli e incroci del fondo vicino | 0 / 1,37 / 5,485 / 9,60 / 10,97 | 0 | 0 |
| riga del servizio vicina (estremi e T) | 1,37 / 5,485 / 9,60 | 5,485 | 0 |
| righe sotto la rete | 0 … 10,97 | 11,885 | 0 |
| cima della rete al centro | 5,485 | 11,885 | **0,914** |
| cima dei pali (doppio) | −0,914 e 11,884 | 11,885 | **1,07** |
| riga del servizio lontana | 1,37 / 5,485 / 9,60 | 18,285 | 0 |
| fondo lontano | 0 / 1,37 / 9,60 / 10,97 | 23,77 | 0 |

I punti che non stanno a terra (rete e pali) sono i più preziosi, perché aiutano a stimare la focale.

Il calcolo vero e proprio è la funzione `calibrate_camera` del file del tuo amico. Prova 60 focali diverse. Per ciascuna trova la posizione e l'orientamento della camera che meglio spiegano i punti (con `solvePnP` di OpenCV, metodo SQPNP, poi un raffinamento) e misura l'**errore di riproiezione**, cioè quanti pixel separano i punti veri da quelli ricalcolati. Tiene la focale con l'errore più piccolo e la raffina.

### Due modi di ottenere i punti

**A mano: `calibra_campo.py`.** Si apre un fotogramma e il programma chiede i punti uno alla volta. Uno schema del campo mostra quale punto cliccare e una lente ingrandisce attorno al mouse. Con le frecce si sposta l'ultimo punto di un pixel, e con S si salta un punto che non si vede. Alla fine il campo viene ridisegnato in verde sopra il fotogramma: se le righe verdi cadono su quelle vere, la calibrazione è buona. Per il video di Nicola ho preso 7 punti a occhio da immagini ingrandite.

**Semi-automatica dalle righe (video di Djokovic).** Le righe bianche sul cemento blu sono molto nette:

1. costruisco una maschera dei pixel bianchi (poco saturi e molto luminosi), togliendo il giocatore e la scritta in sovraimpressione;
2. con la trasformata di Hough vedo quali righe ci sono; indico io approssimativamente quale riga è quale (fondo, servizio, singolo, doppio, centrale);
3. per ogni riga il programma prende tutti i pixel bianchi vicini e calcola la **retta di best fit**, con precisione sotto il pixel;
4. i punti del campo sono gli **incroci** di queste rette. Si possono usare anche incroci che cadono fuori dall'immagine (gli angoli del fondo vicino), perché le righe sono dritte;
5. la cima della rete e dei pali li ho letti da ritagli ingranditi.

In totale: 15 incroci di righe, più rete e pali.

### Controlli

| | Nicola | Djokovic |
|---|---|---|
| punti usati | 7, presi a occhio | 18, dalle righe |
| errore medio di riproiezione | 2,6 px (su 1920 × 1080) | 6,7 px (su 3840 × 2160) |
| camera (x, y, altezza) | 5,5 / −6,7 / 2,2 m | 5,6 / −13,6 / 3,2 m |
| focale | 1419 px | 7181 px (zoom) |

- **Controllo indipendente con SwingVision.** Il pixel in cui rimbalza il dritto dell'avversario di Nicola, riportato a terra con la nostra calibrazione, cade a **(3,4 m; 6,0 m)**. La minimappa di SwingVision mette quel rimbalzo a **(3,5 m; 5,9 m)**.
- **Sensibilità.** Spostando a caso di 3 pixel i punti cliccati, la velocità del servizio di Nicola cambia di circa ±2 km/h. La calibrazione non è il punto debole del metodo.

Una volta calibrato il campo, `ground_from_pixel` trasforma in metri qualsiasi pixel **che si trovi a terra**: i piedi del giocatore, un rimbalzo. Non vale per la pallina in volo.

---

## 4. Il file del tuo amico: `rf_ball_exit_speed.py`

È il cuore del calcolo. Lo descrivo nella versione che mi hai dato (versione 2).

### La fisica

- Costanti: gravità 9,81 m/s², densità dell'aria 1,20 kg/m³, pallina ITF da 57,7 g e 6,7 cm di diametro, coefficiente di resistenza Cd = 0,55. Ne viene un coefficiente di frenata `K_DRAG` ≈ 0,020 1/m.
- `simulate` calcola la traiettoria con gravità e resistenza dell'aria (metodo Runge-Kutta, passo di 5 ms).
- **Non c'è l'effetto della rotazione** (effetto Magnus): topspin e slice non sono nel modello.

### L'istante dell'impatto: `refine_impact_visual`

Parte dal primo punto dopo il cambio di direzione della pallina. Adatta una curva ai 4 punti prima e una ai 4 punti dopo, e cerca l'istante, *tra due frame*, in cui le due curve si incontrano. Così l'impatto ha una precisione migliore di un frame.

### La velocità d'uscita: `exit_speed`

Questa è l'idea centrale. Il punto di contatto sta sicuramente sulla retta che va dalla camera al pixel in cui vediamo la pallina all'impatto, ma non sappiamo a che distanza. Le incognite sono cinque:

- **s**: a che distanza lungo quella retta avviene il contatto;
- **vx, vy, vz**: la velocità della pallina appena colpita, in m/s;
- **dt**: una piccola correzione dell'istante di impatto (al massimo mezzo frame).

Il programma prova combinazioni di questi numeri. Per ciascuna simula il volo, lo proietta nell'immagine con la calibrazione e confronta i pixel simulati con quelli osservati nei frame dopo l'impatto. Cerca la combinazione che rende minima la differenza (`least_squares` di SciPy, partendo da 16 punti di partenza diversi per non fermarsi in una soluzione sbagliata).

Perché funziona: **la gravità fa da metro**. La pallina cade sempre con la stessa accelerazione, e quanto quella caduta appare grande nei pixel dice quanto è lontana la pallina. Da lì si ricava la velocità.

Aiutano anche alcuni vincoli:

- la **posizione a terra del giocatore**: il contatto deve essere vicino ai suoi piedi, che ricaviamo dalle caviglie della posa con `ground_from_pixel`;
- l'**altezza del contatto** fra 0 e 3,4 m;
- facoltativo, il **punto di rimbalzo** se è visto.

Il risultato è la velocità in km/h con un'**incertezza** (sigma). Attenzione: quel sigma misura solo quanto sono coerenti i pixel, e non tiene conto degli errori del modello (rotazione, pallina nascosta, contatto sbagliato). L'errore vero è più grande.

### La modalità audio

Il file può prendere l'istante dell'impatto dal suono della pallina sulla racchetta. Filtra le basse frequenze, cerca l'inizio del colpo e corregge per il tempo che il suono impiega ad arrivare alla camera (distanza / 343 m/s). **Non l'abbiamo ancora provata**, perché nel video di Nicola l'audio è muto. Il file stesso conclude che la fonte principale di errore non è l'istante dell'impatto ma la profondità.

### Le mie verifiche sul file

Ho rifatto la sua simulazione e i suoi numeri tornano: servizio a 180 km/h entro ±33, dritto a 120 km/h entro ±19. Poi l'ho provato nelle nostre condizioni (60 fps, colpi amatoriali):

| | TrackNet preciso (2 px) | TrackNet meno preciso (4 px) |
|---|---|---|
| servizio a 90 km/h, 20 frame | ±15 km/h | ±27 km/h |
| dritto a 65 km/h, 20 frame | ±15 km/h | ±28 km/h |

- A 60 fps servono circa 20 frame dopo l'impatto: con 10 il servizio sale a ±36/±74 km/h.
- Il punto di rimbalzo migliora molto il servizio (±27 diventa ±9), mentre sul dritto lungo non ha aiutato.
- Senza modellare il topspin la velocità esce sottostimata di circa 12 km/h in media.

### Le due aggiunte fatte per il progetto

- **`forward=True`**: la pallina deve andare verso il campo avversario. Evita soluzioni "all'indietro" che spiegano gli stessi pixel.
- **`depth_tol=1.0`**: il punto di contatto deve stare entro 1 m dalla distanza del giocatore. È servito sul dritto di Djokovic (vedi sotto).

---

## 5. La calibrazione del campo: come l'ho fatta

Il paragrafo 3 spiega cos'è la calibrazione. Qui racconto in pratica come l'ho ottenuta: prima lo strumento scritto per farla a mano, poi i due video, che ho calibrato in due modi diversi.

### 5.1 Lo strumento: `calibra_campo.py`

È un programma nuovo che usa `calibrate_camera` del file del tuo amico per il calcolo. Le parti principali:

- **`PUNTI`**: l'elenco dei 23 punti noti del campo, nell'ordine in cui vengono chiesti, ciascuno con le coordinate in metri e una descrizione per chi clicca. Rispetto ai 13 punti del file del tuo amico ho aggiunto gli incroci delle righe con la linea della rete a terra, il segno centrale del fondo vicino, i due incroci del fondo lontano con le righe del singolo e le cime dei pali del doppio (1,07 m). Sono punti spesso visibili con la camera dietro al giocatore.
- **La finestra per cliccare** (`interattivo`). Mostra il fotogramma rimpicciolito per stare nello schermo (al massimo 1500 × 850). Ogni clic viene riportato alla risoluzione piena, quindi il punto non perde precisione. In alto c'è scritto quale punto cliccare. In basso a sinistra c'è lo schema del campo visto dall'alto (`schema_campo`): punto richiesto in rosso, segnati in verde, saltati in grigio. In alto c'è una **lente** (`lente`) che ingrandisce 5 volte i 60 × 60 pixel attorno al mouse, con un mirino.
- **I tasti**: S salta un punto non visibile, U annulla l'ultimo, frecce o IJKL spostano di 1 pixel l'ultimo punto, `,` e `.` cambiano fotogramma se il giocatore copre le righe (la camera è ferma, quindi i punti restano validi), F chiude. Servono almeno 6 punti.
- **Il calcolo** (`calcola`). Passa i punti a `calibrate_camera`, ricalcola dove cadrebbero secondo la calibrazione trovata e dà l'errore di ogni punto in pixel. Con questo si vede subito un punto cliccato male. Calcola anche la posizione della camera in metri, utile come controllo di buon senso: deve risultare dietro la linea di fondo e a un'altezza credibile.
- **Il controllo visivo** (`disegna_controllo`). Ridisegna sopra il fotogramma tutte le righe del campo in verde, il profilo della rete in giallo, i punti cliccati in rosso e quelli ricalcolati in blu. Se il verde cade sulle righe vere, la calibrazione è buona.
- **Il salvataggio**. Scrive un file JSON con i punti in pixel e in metri e la calibrazione, più l'immagine di controllo. Con `--verifica` si rifà il calcolo da un JSON salvato senza aprire finestre, quindi anche su Colab.

Prima di usarlo sui video l'ho provato su dati inventati. Ho messo una camera virtuale in un punto noto (x 4,0, y −7,0 m, altezza 2,5 m, focale 1500 px), ho calcolato dove cadrebbero 10 punti del campo, li ho sporcati con 1,5 pixel di errore a caso e li ho dati allo strumento. Ha ritrovato la camera a (3,98; −6,92; 2,49) m e la focale a 1491 px.

### 5.2 Il video di Nicola: punti presi a occhio

Sulla terra rossa le righe sono sporche e poco contrastate. Ho provato a isolarle automaticamente con una maschera dei pixel bianchi, ma venivano fuori a pezzi. Quindi ho letto i punti a occhio:

1. ho scelto il **frame 120**, dove il giocatore non copre le righe vicine;
2. ho ritagliato le zone interessanti (rete a sinistra, rete a destra, parte vicina del campo) con sopra una griglia ogni 20 pixel per leggere le coordinate; le zone della rete le ho ingrandite 2 volte;
3. ho segnato i 7 punti più chiari:

| Punto | pixel |
|---|---|
| riga del servizio vicina, estremo sinistro | (617, 869) |
| T del servizio vicina | (1096, 880) |
| riga del servizio vicina, estremo destro | (1600, 900) |
| riga centrale sotto la rete | (1094, 797) |
| cima del palo sinistro | (614, 700) |
| cima della rete al centro | (1094, 722) |
| cima del palo destro | (1607, 716) |

Risultato: camera a x 5,46, y −6,66, altezza 2,17 m (centrata, circa 6,7 m dietro la linea di fondo), focale 1419 px, errore medio 2,6 px. Il punto peggiore è la riga centrale sotto la rete, a 3,9 px, com'era prevedibile perché si vede attraverso la rete.

Controlli fatti:

- **Campo ridisegnato**: le righe verdi cadono sulle righe vere, comprese quelle che non avevo cliccato (fondo vicino, righe del doppio).
- **Confronto con SwingVision**: la minimappa in alto a destra del video mostra dove rimbalzano i colpi. Ho misurato in pixel il rettangolo del campo nella minimappa e l'ho convertito in metri. Il rimbalzo del dritto dell'avversario risulta a (3,5; 5,9) m. Ho preso il pixel in cui la pallina tocca terra nel video (frame 183, (862, 866)) e l'ho riportato a terra con la nostra calibrazione (`ground_from_pixel`): esce (3,4; 6,0) m.
- **Sensibilità**: ho spostato a caso i 7 punti di circa 3 pixel, per 20 volte, e ho ricalcolato ogni volta la velocità del servizio. È rimasta tra 113 e 121 km/h. La calibrazione a occhio basta, e cliccare più preciso cambierebbe pochi km/h.

### 5.3 Il video di Djokovic: punti dalle righe

Qui le righe bianche sul cemento blu sono nette e il video è in 4K (3840 × 2160). Ho quindi fatto trovare le righe al programma e ho calcolato i punti come incroci. È semi-automatico: il programma misura le righe con precisione, ma sono io a dirgli quale riga è quale.

1. **Scelta del fotogramma.** Frame 90: Djokovic è sulla destra (il suo riquadro dal tracking va da x 2391 a 3026) e lascia libera la riga centrale.
2. **Maschera del bianco.** Tengo i pixel poco saturi e molto luminosi (in HSV: saturazione sotto 60, luminosità sopra 200). Tolgo tutto ciò che sta sopra il campo (sopra y 560), il riquadro del giocatore allargato di 120 pixel ai lati e la scritta COURT LEVEL TENNIS in basso a destra.
3. **Vedere le righe.** Con la trasformata di Hough di OpenCV (`HoughLinesP`) il programma trova i tratti rettilinei e li disegna in rosso. Guardando l'immagine ho indicato, per ciascuna riga, due punti approssimativi: fondo vicino, riga del servizio vicina, righe del singolo e del doppio a sinistra e a destra, riga centrale, riga del servizio lontana (vista attraverso la rete) e fondo lontano (una riga sottile a y ≈ 697, appena sopra la rete).
4. **Misura precisa di ogni riga.** Per ogni riga il programma prende tutti i pixel bianchi entro una fascia attorno al tratto indicato (±14 px per le righe vicine, ±5–6 px per quelle lontane, che sono sottili). Poi calcola la retta che passa meglio in mezzo a loro, cioè il centro dei pixel e la direzione principale della loro distribuzione. Usando migliaia di pixel per riga, la posizione della retta è precisa a meno di un pixel. Il programma stampa anche lo spessore medio della riga (5–7 px vicino, 1–2,5 px lontano) come controllo.
   Un inciampo utile: per la riga centrale la mia prima indicazione (x = 1990) non trovava nessun pixel. Cercando il punto più bianco su tre righe dell'immagine ho visto che la riga stava a x ≈ 1971–1976, e ho corretto.
5. **Incroci.** Ogni punto del campo è l'incrocio di due rette, trovato risolvendo un piccolo sistema di due equazioni. Sono venuti 15 punti: i 3 della riga del servizio vicina, 5 sul fondo vicino, 3 sulla riga del servizio lontana e 4 sul fondo lontano. Alcuni incroci cadono **fuori dall'immagine**, come l'angolo sinistro del fondo vicino a x = −874. Si possono usare lo stesso, perché le righe del campo sono dritte e la loro continuazione è esatta.
6. **Rete e pali.** La cima della rete al centro (1969, 720) e le cime dei pali (176, 681) e (3785, 675) le ho lette da ritagli ingranditi 5 volte con una griglia ogni 10 pixel.

Risultato con 18 punti: camera a x 5,58, y −13,62, altezza 3,18 m, focale 7181 px, errore medio 6,7 px su un'immagine 4K. La focale corrisponde a un campo visivo orizzontale di circa 30°, cioè una ripresa zoomata da lontano. Gli errori più grandi (11–15 px) sono sugli incroci estrapolati più a sinistra, segno di una leggera distorsione della lente ai bordi.

Controllo di buon senso: Djokovic, alto 1,88 m e a circa 12 m dalla camera, con questa focale dovrebbe apparire alto circa 1,88 × 7181 / 12 ≈ 1125 pixel. Nel video il suo riquadro è alto circa 1090 pixel.

### 5.4 La calibrazione standard: una per tutti i video

Calibrare ogni video non scala. Per questo facciamo come SwingVision: il telefono va messo sempre nello stesso modo (in orizzontale, zoom 1x, centrato dietro il fondo, in alto sulla recinzione) e si usa sempre la stessa calibrazione. È `calibrazioni/standard.json`, cioè la calibrazione del video di Nicola (§5.2), registrato proprio con SwingVision.

Tre cose fanno funzionare questa scelta:

- **Risoluzione diversa.** Se il video è 720p o 4K invece di 1080p, cambia solo la scala dei pixel. Si scalano focale e centro dell'immagine (`adatta_risoluzione` in `calibra_campo.py`), mentre posizione e orientamento della camera restano gli stessi. Con proporzioni diverse, per esempio un video verticale, non si può, e il programma chiede una calibrazione propria.
- **Quanto deve essere precisa la posizione.** Ho simulato colpi visti da una camera spostata rispetto allo standard e ricostruiti con la calibrazione standard. Spostare la camera avanti o indietro di 1,5 m cambia la velocità di meno di 1 km/h: si sposta tutta la scena, ma la forma della traiettoria resta. Contano invece l'altezza (1 m più in alto: fino a −8 km/h), lo zoom (focale +15%: −7/−10 km/h) e il centramento (1 m di lato: +3° sulla direzione). Rispettando zoom 1x, centro e altezza simile, l'errore resta dentro il margine di ±20 km/h. La tabella completa è in `LEGGIMI.md`.
- **Controllo a colpo d'occhio.** `velocita_uscita.py` disegna ogni volta il campo della calibrazione usata sul primo fotogramma del video (`outputs/dati/<video>_campo.jpg`). Se le righe verdi non cadono su quelle vere, il telefono era messo diversamente e quel video ha bisogno della sua calibrazione. Sul video di Djokovic, con la calibrazione standard, la rete disegnata cade circa a metà del campo vicino: l'errore si vede subito.

Se un video ha la sua calibrazione (`calibrazioni/<video>.json`), si usa quella. Per questo i video di Nicola e di Djokovic continuano a dare gli stessi risultati.

### 5.5 Calibrare su Colab: `calibra_colab.py`

`calibra_campo.py` apre una finestra di OpenCV e legge mouse e tastiera, cosa che richiede uno schermo collegato al computer su cui gira il programma. Colab gira su un server di Google senza schermo, quindi lì la finestra non si apre. Per i video girati fuori dalla posizione standard c'è `calibra_colab.py`, la cella 4b del notebook, che cambia solo il modo di cliccare:

1. Python legge il fotogramma e lo manda al browser come JPEG, insieme all'elenco dei punti del campo (gli stessi 23 di `calibra_campo.py`).
2. Un pezzetto di JavaScript disegna nella cella il fotogramma, la lente e lo schema del campo, e raccoglie i clic e i tasti. Le coordinate del clic vengono riportate ai pixel del fotogramma originale, anche se nel notebook l'immagine è rimpicciolita.
3. Quando si preme F, i punti tornano a Python (`google.colab.output.eval_js` aspetta la fine dei clic). Da qui calcolo e salvataggio sono quelli di `calibra_campo.py`: stesso JSON, stessa immagine di controllo. Il JSON viene copiato anche su Drive in `calibrazioni/`, così la cella 4 lo riporta nelle sessioni successive.

Il costo di calcolo è trascurabile: la stima della camera richiede circa 0,1 secondi di CPU e non usa la GPU. Il tempo è quello dei clic, una volta per ogni posizione della camera.

**Prima dell'analisi (5 ottobre).** All'inizio la calibrazione era la cella 7c, dopo l'analisi: per vedere l'immagine di controllo e capire se serviva bisognava aspettare la fine dell'analisi, circa mezz'ora per video. Ora è la cella 4b, subito dopo la copia dei file da Drive: mostra il campo con la calibrazione che verrebbe usata e, se il video non ne ha una sua, chiede se le righe tornano (s = sì, n = calibro adesso, un numero = un altro fotogramma). Con «Esegui tutto», dopo questa risposta non serve toccare più niente.

Prova: ho cliccato in un browser automatico i 7 punti del video di Nicola nelle posizioni già note. I punti sono tornati entro 1 pixel e la camera è uscita uguale: (5,44; −6,66; 2,16) m e focale 1418 px, contro (5,46; −6,66; 2,17) m e 1419 px.

---

## 6. Il rilevatore locale della pallina: come l'ho fatto

### 6.1 Da dove nasce

Guardando dove TrackNet vede la pallina (la colonna `pallina_fonte` del tracking CSV) e confrontandolo con i fotogrammi, i buchi cadono proprio attorno ai colpi:

- **Djokovic**: TrackNet perde la pallina nei frame 46–69 (arrivo e contatto del dritto) e 204–219 (arrivo e contatto del rovescio), anche se nei fotogrammi si vede benissimo;
- **Nicola**: la perde dal frame 199 al 231, cioè tutto l'arrivo del rovescio e il contatto.

Il motivo è la geometria. Prima del colpo la pallina viene verso la camera e nell'immagine quasi non si muove, e TrackNet, che si basa sul movimento ed è addestrato sul badminton, non la riconosce. Il calcolo della velocità però ha bisogno proprio dei punti subito prima e subito dopo il contatto. Serviva quindi un modo diverso per trovare la pallina, da usare solo lì.

### 6.2 L'idea

Vicino al giocatore la pallina è grande (su Djokovic 20–30 pixel di diametro), di un colore preciso (giallo-verde) e si sposta poco da un frame all'altro. Basta quindi:

- guardare solo **attorno a dove ci si aspetta la pallina**;
- cercare **macchie di quel colore**;
- tenere quella con **forma e dimensioni da pallina** più vicina alla posizione prevista.

### 6.3 Come funziona, passo per passo

Per ogni frame, a partire da un punto di partenza:

1. **Previsione.** La pallina dovrebbe essere dove era nel frame prima, più lo spostamento dell'ultimo frame, perché si muove con continuità.
2. **Finestra.** Il programma guarda solo un riquadro attorno alla previsione: ±260 pixel sul video 4K di Djokovic, ±70 su quello di Nicola. Tutto il resto dell'immagine (spalti, cartelloni, altre persone) non entra in gioco.
3. **Colore.** Converte il riquadro in HSV, che separa il colore dalla luminosità, e tiene i pixel con tinta tra 25 e 45 (giallo-verde), saturazione almeno 90 e luminosità almeno 140. Il cemento blu, la maglia rossa, il bianco delle righe e della maglietta restano fuori.
4. **Pulizia.** Un'"apertura" morfologica (3 × 3 pixel) toglie i puntini isolati di rumore.
5. **Macchie.** Il programma separa le macchie rimaste (componenti connesse) e per ognuna misura area, larghezza, altezza e centro.
6. **Filtri.** Tiene solo le macchie con:
   - area plausibile per la pallina (su Djokovic tra 120 e 5000 pixel);
   - proporzioni non troppo allungate (rapporto larghezza/altezza tra 0,35 e 2,8, per ammettere la sfocatura di movimento);
   - forma "piena": l'area occupa almeno il 45% del rettangolo che la contiene, come fa un cerchio e non una riga o un logo.
7. **Scelta.** Fra le macchie che passano i filtri prende la più vicina alla posizione prevista.
8. **Risultato.** Posizione della pallina e diametro apparente (il lato più corto della macchia). Se non trova niente salta il frame e continua dalla previsione.

Nelle prime prove il punto di partenza l'ho dato io, leggendo la posizione della pallina da un fotogramma: frame 56 a (3000, 1415) per il dritto di Djokovic, frame 204 a (1685, 1175) per il rovescio. Nella versione automatica (`palla_locale.py`) parte dalla prima posizione vista da TrackNet nella finestra del colpo, e nei frame in cui il rilevatore non trova niente usa TrackNet se ha una posizione compatibile con la previsione. Le dimensioni (area della macchia, raggio della zona di ricerca) sono in proporzione all'altezza del giocatore nell'immagine, così le stesse soglie valgono sul video di Nicola e su quello 4K di Djokovic. Per il colore usa le soglie più larghe della prima versione (tinta 22–48, saturazione ≥ 70, luminosità ≥ 110), che hanno funzionato su entrambi i campi.

Su Nicola avevo usato una prima versione più semplice: finestra di ±70 px, soglie di colore un po' più larghe (tinta 22–48, saturazione ≥ 70, luminosità ≥ 110) perché sulla terra rossa la pallina è più piccola e meno satura, nessuna previsione del movimento, nessuna pulizia morfologica e nessun filtro sulla forma piena. La versione per Djokovic aggiunge queste tre cose.

### 6.4 Cosa ha trovato

**Djokovic, dritto** (frame 56–77). Nei frame 56–65 la pallina arriva spostandosi di circa 11 pixel per frame verso destra. Tra il 65 e il 66 c'è un salto netto, da (3086, 1448) a (3016, 1348): è il **contatto**, che nel fotogramma 66 si vede con la pallina sulle corde. Dal 66 al 77 la pallina si allontana verso l'alto a sinistra, sempre più piccola.

**Djokovic, rovescio** (frame 204–232). Nei frame 204–217 la pallina scende, sempre più veloce nell'immagine (da circa 9 a 32 pixel per frame). Tra il 217 e il 218 inverte di colpo, da (1694, 1419) a (1701, 1324): **contatto**. Poi sale fino al frame 232, e il diametro apparente passa da 26 a 10 pixel mentre si allontana.

**Nicola, rovescio.** La pallina viene trovata nei frame 199–209 (6–8 pixel di diametro) mentre arriva. Poi sparisce dietro la racchetta e il corpo del giocatore, e dopo il colpo non ricompare in tempo utile.

### 6.5 Come si unisce al calcolo della velocità

Per ogni colpo costruisco un'unica traccia della pallina:

- **prima del contatto**: i punti del rilevatore locale;
- **dopo il contatto**: i punti del rilevatore locale dove ci sono, e quelli di TrackNet per i frame in cui il rilevatore non ha trovato niente, fino a circa 20 frame dopo il colpo.

Il primo punto dopo il salto di direzione è quello che `exit_speed` si aspetta come inizio del volo (`change_idx`). Da lì il calcolo procede come descritto nel paragrafo 4.

Sul dritto di Djokovic è servita l'aggiunta `depth_tol=1.0` del paragrafo 4. Senza vincolo il calcolo metteva il contatto 3,4 m dietro i piedi del giocatore, cosa impossibile, e dava 87 km/h. Tenendo il contatto entro 1 m dal giocatore esce 116 km/h, anche se la curva segue la pallina un po' peggio, probabilmente per il topspin che il modello non considera. Sul rovescio il vincolo non cambia niente: 117–118 km/h in entrambi i casi.

### 6.6 Il diametro della pallina: non ancora usato

Il rilevatore misura anche quanto è grande la pallina nell'immagine, e questo potrebbe dire direttamente quanto è lontana. Oggi però la misura è troppo grezza. Su Djokovic, a circa 12 m, la pallina dovrebbe apparire di circa 40 pixel, e il rilevatore ne misura 24–28: la soglia di colore prende solo il centro più saturo, non i bordi sfumati. Per usarla bisogna misurare il contorno in modo più accurato.

### 6.7 Limiti

- Le soglie di colore sono state provate solo su **terra rossa e cemento blu**: su altri campi (erba, cemento verde) vanno verificate.
- Oggetti dello **stesso colore** vicino alla pallina (magliette lime, scritte, palline a terra) possono ingannarlo. La finestra piccola e la previsione riducono il rischio ma non lo eliminano.
- Se la pallina è **coperta** dal giocatore o dalla racchetta non c'è niente da trovare, come nel rovescio di Nicola.
- Se la pallina resta coperta per più di 8 frame di fila, il rilevatore si ferma.

---

## 7. Il programma automatico e la direzione

I passaggi che nelle prime prove facevo a mano ora li fa `velocita/velocita_uscita.py`:

1. **Colpi dalla posa.** Il classificatore segna frame per frame dritto, rovescio, servizio o attesa. I tratti che non sono attesa, con buchi fino a 5 frame e lunghi almeno 8 frame, sono le finestre in cui cercare un colpo.
2. **Pallina nella finestra.** È il rilevatore locale del paragrafo 6, con TrackNet dove c'è.
3. **Contatto.** Cambio brusco della direzione della pallina, con la pallina vicina a un polso. Serve anche un'altra condizione: subito dopo, la pallina deve allontanarsi abbastanza veloce nell'immagine (almeno 2,4 altezze del giocatore al secondo). È quella che scarta il rimbalzo della pallina dell'avversario davanti al giocatore: dopo quel rimbalzo la pallina continua ad arrivare lentamente.
4. **Velocità**, come nel paragrafo 4, con `forward` e `depth_tol=1.0`. La posizione a terra del giocatore si prende nel frame, fra i 20 prima del contatto, in cui i piedi sono più in basso nell'immagine: nel servizio, al contatto, il giocatore è in aria.
5. **Direzione.** Dalla velocità 3D si ricava l'angolo della pallina rispetto alle righe laterali (0° = parallela). Nelle simulazioni l'angolo è molto più preciso della velocità: ±1° con TrackNet preciso, ±2–3° con TrackNet meno preciso, anche con il topspin. L'errore del metodo sta soprattutto nella *distanza* della pallina, che cambia la velocità ma poco la direzione.
6. **Lungo linea, incrociato, centrale.** Si guarda da dove parte il giocatore (a sinistra, al centro o a destra della riga centrale; il centro è il terzo centrale del campo singolo, entro 1,37 m dalla riga centrale, vedi 8.5) e dove arriverebbe la pallina, prolungando la direzione fino a 21 m, tra riga del servizio e fondo lontani:
   - lungo linea: parte da un lato e arriva sulla metà dello stesso lato;
   - incrociato: arriva sulla metà opposta;
   - centrale: arriva entro 1,37 m dalla riga centrale (terzo centrale del singolo);
   - dal centro verso destra o sinistra: parte dal centro e va verso un lato.

   Ragionare su dove arriva la pallina, invece che solo sui gradi, evita di chiamare "lungo linea" un colpo dritto tirato dal centro del campo.

   **Servizio: al T, al corpo, esterno.** Per il servizio conta dove rimbalza la pallina nel riquadro del servizio. Dalla traiettoria stimata (punto di contatto e velocità 3D) si calcola il rimbalzo con `ground_crossing` del file del tuo amico, cioè con gravità e resistenza dell'aria. Il servizio va in diagonale, quindi si guarda il riquadro opposto al lato da cui serve il giocatore. Quel riquadro, dalla riga centrale a quella del singolo (4,115 m), è diviso in tre fasce uguali da 1,37 m: al T vicino alla riga centrale, al corpo, esterno. Se il rimbalzo cade entro 25 cm dal confine con la fascia accanto, si scrive anche verso quale fascia, per esempio "al corpo, verso il T".

   Simulazioni (servizio da destra, camera standard, 60 fps, 20 frame, rimbalzi veri al T, al corpo ed esterno): la posizione LATERALE del rimbalzo esce entro ±0,1–0,4 m nel 90% dei casi con TrackNet preciso (2 px) ed entro ±0,1–0,5 m con 4 px. La PROFONDITÀ invece è imprecisa, ±2–3 m, perché la pallina si allontana lungo la linea di vista. Per questo la classificazione usa solo la posizione laterale e non dice se il servizio è lungo. La rotazione non è nel modello: un servizio in slice curva di lato e può spostare il rimbalzo vero rispetto a quello calcolato.
7. **Colpi senza misura.** Se la posa indica un colpo e la pallina arriva al giocatore, ma il contatto non si vede, il colpo viene scritto lo stesso, senza velocità.

   Per questi colpi c'è un passo separato, `velocita/direzione_nascosta.py`, che prova a ricavare almeno la direzione senza toccare la velocità. È il caso del rovescio di Nicola: la pallina si vede in arrivo fino al frame 208, poi sparisce dietro il corpo e ricompare al 237, già lontana. Il contatto è nel buco, intorno al 223.

   - **Perché la direzione sì e la velocità no.** Vista dall'alto, dopo il colpo la pallina va praticamente dritta: la gravità la tira giù e l'aria la rallenta, ma nessuna delle due la fa girare di lato. Basta quindi vedere un pezzo di volo dopo il buco, sapendo che parte vicino al giocatore. La velocità invece cala lungo il volo, e per risalire a quella di uscita serve l'istante esatto del contatto, che è proprio nel buco.
   - **Punti dopo il buco.** I punti di TrackNet nei 0,75 s dopo il frame in cui la pallina si è persa, tenendo solo quelli su una stessa curva liscia (una parabola in x e y nel tempo, quella che passa per più punti). Nel rovescio di Nicola si scartano così i frame 232-234, 60-150 px fuori dalla traiettoria.
   - **Contatto provato ovunque.** Si prova come contatto ogni frame del buco (209-236) e ciascuno dei due polsi, e per ognuno si fa lo stesso calcolo della traiettoria di `velocita_uscita.py`. Il file del tuo amico non è modificato: per quel calcolo si sostituisce per un momento la sua funzione che trova l'impatto (`refine_impact_visual`), che qui non può lavorare perché mancano i punti attorno al contatto.
   - **Il colpo deve stare nel buco.** L'istante del colpo stimato dalla posa deve cadere tra il frame in cui la pallina si perde e quello in cui ricompare, con 0,25 s di tolleranza. Senza questo controllo, sul video swing_vision_test1_trim un rovescio al frame 1379, con la pallina persa già al 1247, riceveva una direzione calcolata su frame di prima del colpo.
   - **La pallina deve allontanarsi per conto suo.** Nel tratto usato la distanza tra la pallina e i piedi del giocatore deve crescere e la pallina deve spostarsi nell'immagine più del giocatore. Sul video alcaraz, al frame 1302, il giocatore camminava (149 px) mentre la "pallina" restava quasi ferma (37 px): la distanza cresceva solo perché si muoveva lui. Una pallina quasi ferma dietro al giocatore si può spiegare come un colpo che va dritto lontano dalla camera, e senza questo controllo usciva un falso "al T".
   - **Solo se stabile.** I calcoli con il contatto dal 223 al 229 spiegano i punti quasi allo stesso modo (1,2-1,5 px), ma la velocità va da 50 a oltre 200 km/h: per questo non si scrive. La direzione si scrive solo se tutti i calcoli quasi buoni quanto il migliore (errore fino a 1,5 volte) danno la stessa risposta, con angoli entro 6°.

   Risultato sul rovescio di Nicola: "dal centro verso sinistra", angolo tra −4,7° e −0,4°, arrivo a 3,7 m dalla riga laterale sinistra. La mappa di SwingVision mette il rimbalzo di quel rovescio a circa 3,3 m.

   Prova al contrario sul video di Djokovic, dove la direzione vera è nota: ho cancellato la pallina attorno al contatto del dritto e del rovescio, da 13 a 29 frame, in 6 prove. Il programma non ha mai dato una direzione sbagliata, ma in tutte e 6 ha preferito non darla (una versione senza il controllo sui 6° dava in un caso "dal centro verso sinistra" invece di "centrale": è il motivo di quel controllo). Quando la direzione c'è è affidabile, ma spesso manca.

8. **Controllo del risultato.** Il calcolo resta identico: si decide solo se mostrarlo. Sul video alcaraz alcuni colpi davano 4, 377 e 25 km/h, con angoli fino a 85°. In tutti e tre la traiettoria 3D spiegava male i punti: 17–35 px di errore, contro 1–3 px dei colpi buoni (riportati a 1080p: Nicola 2,0, Djokovic 2,0 e 0,8, swing_vision 0,7, il dritto buono di Alcaraz 2,8). Il motivo è che i punti seguiti non erano la pallina colpita: la racchetta gialla di Alcaraz presa dal rilevatore di colore, altre palline, l'altro giocatore. Ora velocità e direzione non si scrivono se l'errore supera 6 px a 1080p, oppure se la velocità è fuori da 30–250 km/h, oppure se un colpo da fondo ha un angolo oltre 45° (dal 4 ottobre il limite dipende dal punto di contatto, vedi 8.11). La riga resta nel CSV con la nota "misura scartata" e i motivi, e sul video compare "misura non affidabile". Sui colpi di Nicola, Djokovic e swing_vision non cambia niente.

`velocita/disegna_velocita.py` riscrive il video originale con tipo di colpo, km/h, direzione e una piccola mappa del campo vista dall'alto: punto di contatto, freccia della direzione e fascia centrale in grigio. Per il servizio la mappa mostra il riquadro diviso in tre fasce, con la fascia colpita evidenziata, e la freccia che arriva al rimbalzo previsto. Se due colpi sono vicini, l'etichetta del più recente sostituisce quella del precedente, così non si sovrappongono.

Risultati senza nessun intervento a mano:

| Video | Colpo | Contatto | Uscita | Direzione |
|---|---|---|---|---|
| Nicola | servizio | frame 15 | 116 km/h | al corpo, verso il T (rimbalzo previsto x 3,96 m) |
| Nicola | rovescio | frame 223 | non disponibile | dal centro verso sinistra (solo direzione, `direzione_nascosta.py`) |
| Djokovic | dritto | frame 65 | 123 km/h | centrale (−5,6°) |
| Djokovic | rovescio | frame 217 | 114 km/h | centrale (−0,8°) |
| Alcaraz | dritto | frame 275 | 147 km/h | dal centro verso destra (+3,9°) |
| Alcaraz | 8 colpi | vedi il paragrafo 8 | | |

I frame di contatto coincidono con quelli verificati a occhio. Le velocità differiscono di 5–7 km/h dalle prove fatte a mano, per piccole differenze nei punti usati e nella posizione dei piedi: è dentro il margine di circa ±20 km/h. Le soglie sono state provate solo su questi due video e vanno verificate su altri.

Confronto del servizio di Nicola con SwingVision: la sua mappa mette il rimbalzo a (4,2; 15,9) m, 1,28 m dalla riga centrale, cioè al T ma a 9 cm dal confine con il corpo. Noi lo mettiamo a 3,96 m, 1,52 m dalla riga centrale: al corpo, 15 cm oltre il confine, e per questo scriviamo "al corpo, verso il T". La differenza laterale è di 24 cm, dentro la precisione attesa. La profondità invece differisce di 2,3 m (18,2 contro 15,9), come previsto dalle simulazioni e forse anche per lo slice.

## 8. Il video di Alcaraz: cosa non andava e cosa è cambiato

Sul video `alcaraz.mp4` all'inizio usciva una sola misura credibile su 8 colpi, contro risultati perfetti sui video di Nicola e di Djokovic. Il confronto fotogramma per fotogramma con Djokovic ha mostrato quattro differenze reali (non la dimensione del giocatore, simile, né la velocità della pallina nell'immagine, simile anche quella):

1. **Il mosso.** Djokovic è ripreso all'aperto in piena luce: la pallina resta un pallino nitido anche al colpo. Alcaraz è indoor: al colpo la racchetta è una macchia e la pallina diventa una striscia 3–4 volte più lunga che larga, che il rilevatore di colore (che cerca "una macchia tonda e piena") scarta.
2. **I fotogrammi ripetuti.** Il video è girato a 50 fps e convertito a 60 ripetendo un fotogramma ogni 6: il calcolo credeva che tra due fotogrammi passasse sempre 1/60 s.
3. **Gli oggetti gialli.** Borse e sedie a bordo campo, la racchetta gialla di Alcaraz.
4. **La scelta del video.** Djokovic: 4 s con 2 colpi puliti. Alcaraz: 22 s con 8 colpi, servizio, camminate, altre palline.

### 8.1 La scheda di verifica

Per misurare i miglioramenti ho fatto una scheda: gli 8 colpi veri con il contatto controllato a occhio (servizio 141; dritti 275, 419, 569, 717; rovesci 871, 1017, 1168, uno ogni 2,5 s circa) e, dove si vede, il rimbalzo nel campo avversario, da cui la direzione e una velocità di riferimento indipendente dalla pallina mossa. Il dritto al 246 non è un colpo; al 1302 Alcaraz cammina.

### 8.2 Le modifiche adottate

- **Istanti veri dei fotogrammi** (`fotogrammi.py`). Il video si legge ridotto a 192×108 in grigi; un fotogramma è ripetuto se è molto più simile al precedente dei vicini. Si attiva solo con ripetizioni regolari (almeno l'8% dei fotogrammi, passo fisso): su alcaraz 214 ripetuti su 1315, uno ogni 6, 50,2 fotogrammi veri al secondo; su Nicola, Djokovic e swing_vision non si attiva. I ripetuti si tolgono dal calcolo e agli altri si dà l'istante vero. Dritto al 275: errore della traiettoria da 2,8 a 1,1 px, da 147 a 138 km/h. Con gli istanti veri anche `direzione_nascosta.py` trova la direzione di altri due colpi (717 lungo linea, 1017 incrociato).
- **Giallo fermo ignorato** (`palla_locale.py`). Mediana di 15 fotogrammi del tratto; il giallo dello sfondo, allargato di 15 px, non è pallina. Il dritto al 569 non segue più la borsa e ha la direzione giusta (incrociato).
- **Ricerca estesa, solo per la direzione** (`palla_locale.py` con `esteso=True`, `velocita_uscita.solo_direzione`). Solo nei colpi senza nessuna velocità: si accetta la pallina strisciata dal mosso, la si riaggancia a TrackNet quando si perde e, nel servizio, si parte dal lancio. La direzione esce giusta (servizio 141 al T, dritto 418 lungo linea), ma la velocità no: 124 e 66 km/h, sotto la velocità *media* fino al rimbalzo (137 e circa 105 km/h), cosa impossibile perché la pallina rallenta. Per questo se ne tiene solo la direzione.
- **Velocità stimata dal rimbalzo** (`velocita_rimbalzo.py`). Per i colpi rimasti senza km/h: se si vede il rimbalzo nel campo avversario, la traiettoria (gravità + aria) dal giocatore al rimbalzo nel tempo misurato dà la velocità d'uscita. Dove anche il calcolo normale funziona i due metodi concordano (Djokovic 65: 123 e 132 km/h; alcaraz 275: 138 e 128). Colonna a parte nel CSV, "circa ... km/h (dal rimbalzo)" sul video, margine circa ±15%.

### 8.3 Risultato

| Colpo | Prima | Dopo |
|---|---|---|
| servizio 141 | niente | circa 166 km/h (dal rimbalzo), al T |
| dritto 275 | 147 km/h, dal centro verso destra | 138 km/h, dal centro verso destra |
| dritto 418 | niente | lungo linea (solo direzione) |
| dritto 569 | scartato (seguiva una borsa) | circa 153 km/h (dal rimbalzo), incrociato |
| dritto 717 | niente | lungo linea (contatto coperto) |
| rovescio 871 | scartato | circa 127 km/h (dal rimbalzo), centrale |
| rovescio 1017 | niente | incrociato (contatto coperto) |
| rovescio 1168 | niente, nemmeno la riga | circa 152 km/h (dal rimbalzo), lungo linea |

Direzioni 8 su 8, tutte uguali a quelle della scheda. Velocità: 1 misurata e 4 stimate dal rimbalzo. Nicola e Djokovic restano identici; su swing_vision il dritto resta 90 km/h e compaiono la direzione del servizio (esterno) e un rovescio che prima mancava (centrale), senza km/h.

### 8.4 Dopo: colore nel campo lontano e rimbalzo ricostruito (1° ottobre)

Restavano 3 colpi senza km/h perché il rimbalzo non si vedeva in TrackNet. Due modi nuovi, provati prima come prototipi e poi messi in `velocita_rimbalzo.py` (passi 4 e 5):

- **Colore nel campo lontano.** Nel dritto al 418/419 TrackNet perde la pallina per 30 fotogrammi proprio prima del rimbalzo, ma a occhio si vede, attraverso le maglie della rete. Nei fotogrammi in cui TrackNet l'ha persa si cercano macchie gialle piccole (3-120 px quadrati a 1080p, la pallina lontana è un puntino) vicino all'ultima posizione nota, in un raggio che parte da 12 px e cresce di 8 px per ogni fotogramma di buco, ignorando il giallo fermo. Sulla traccia completata si rifà la ricerca del rimbalzo. Risultato: rimbalzo a (2,9; 24,5) m, circa 149 km/h, lungo linea (con la regola di allora; con i terzi è "dal centro verso sinistra", vedi 8.5).
- **Rimbalzo ricostruito.** Nel dritto al 709/717 il rimbalzo è coperto dalla testa del giocatore, ma la pallina si vede scendere prima e risalire dopo. Si adattano due curve ai punti prima (almeno 5, in discesa) e dopo (almeno 3, in risalita) e si cerca dove si incontrano, se il buco è tra 4 e 20 fotogrammi. Se le curve passano a più di 20 px (su 1080) i punti dopo non sono la stessa pallina (per esempio è già la risposta dell'avversario). Contatto: il frame della riga, o la metà del tratto coperto se il contatto era coperto. Risultato: rimbalzo a (8,0; 20,6) m, curve a 6 px, circa 118 km/h, lungo linea. Prova: nascondendo apposta il rimbalzo nei 5 colpi in cui si vede, in 4 la stima resta entro il 7% (157 contro 166, 133 contro 131, 137 contro 148, 144 contro 152 km/h); nel quinto le curve passano a 102 px e il controllo lo scarta.

Prova A/B sui quattro video: cambiano solo tre righe, alcaraz 418 (circa 149 km/h, colore), alcaraz 709 (circa 118 km/h, ricostruito) e swing_vision 553 (circa 120 km/h, colore); tutto il resto è identico. Su alcaraz ora le velocità sono 1 misurata e 6 stimate dal rimbalzo; resta senza km/h il rovescio al 1015/1017, dove l'avversario ribatte la pallina prima che rimbalzi in vista.

### 8.5 Direzione: il centro diventa il terzo centrale del campo (1° ottobre)

Il dritto al 418/419 usciva "lungo linea", ma a vederlo la pallina parte dal centro e va verso sinistra. La misura era giusta (tre metodi diversi mettono l'arrivo 2,4-2,6 m a sinistra della riga centrale); era la regola a dargli il nome sbagliato:

- la partenza si misura dai piedi: Alcaraz aveva i piedi a x 4,24 (1,25 m a sinistra della riga centrale), ma nel dritto la racchetta colpisce lontano dal corpo e il contatto era a x 5,41, praticamente sulla riga centrale;
- con un centro di ±1 m bastavano 25 cm per passare da "dal centro" a "da sinistra".

Ora il centro è il terzo centrale del campo singolo, entro 1,37 m dalla riga centrale (`FASCIA_CENTRO = (CENTRO_X - 1.37) / 3`, la stessa misura delle fasce del servizio), per la partenza e per l'arrivo. Il 418 diventa "dal centro verso sinistra". Prova A/B sui quattro video: cambia solo quella riga. Ho provato anche a misurare la partenza dal punto di contatto invece che dai piedi: nelle stime dal rimbalzo il contatto non si misura (si usano i piedi), quindi il 418 non cambiava, mentre il rovescio di Nicola diventava "lungo linea"; scartato in quella forma (ripresa poi in un'altra forma, vedi 8.7).

Sulla mappa del video la fascia grigia del centro è ora larga 2,74 m.

### 8.6 Il punto del rimbalzo sulla mappa (1° ottobre)

Sulla mappa del video ora compare anche dove la pallina rimbalza nel campo avversario: pallino giallo bordato di nero se il rimbalzo si vede (TrackNet o colore), cerchio giallo vuoto se è ricostruito. Per i colpi stimati dal rimbalzo (passi 1-5) il punto c'era già; per tutti gli altri colpi con una direzione `velocita_rimbalzo.py` lo cerca con un passo nuovo (passo 6): nei 1,6 s dopo il colpo, con TrackNet, poi il colore nel campo lontano, poi il rimbalzo ricostruito. Il passo 6 non cambia né la velocità né la direzione: dà il punto e un controllo, e se la direzione che darebbe il rimbalzo è diversa la nota lo dice. Colonne nuove: `rimbalzo_trovato_x_m`, `rimbalzo_trovato_y_m`, `rimbalzo_trovato_frame`, `rimbalzo_trovato_come`.

Poi, su richiesta, la freccia della mappa arriva fino al pallino del rimbalzo quando c'è (la punta si ferma sul bordo del pallino); se il rimbalzo non c'è resta fino a 21 m, il punto usato per la classe. È solo il disegno: la classe e i numeri del CSV non cambiano.

Controllo sui colpi con la velocità misurata: il rimbalzo si trova in 3 su 5 (alcaraz 275 e Djokovic 65 con TrackNet, swing_vision 412 con il colore) e in tutti e 3 la direzione è la stessa del calcolo normale. Su swing_vision 412 il punto cade dove nell'immagine si vede rimbalzare la pallina, a destra del centro. Prova A/B sui quattro video: le colonne di prima restano identiche, cambiano solo le colonne nuove.

Per il tempo: la ricerca col colore leggeva ogni fotogramma con un salto (circa 0,5 s a fotogramma in 4K); ora legge in fila (0,02 s). Stessi risultati, da circa 50 a 15 s a colpo in 4K; il resto è il calcolo del giallo fermo.

Nota: con il programma di oggi i confronti tra le due velocità dove funzionano entrambe sono alcaraz 275: 138 misurati e 131 dal rimbalzo; Djokovic 65: 123 e 144 dal rimbalzo trovato col colore (con la partenza dal contatto, 8.7: 130 e 145) (i passi 1-3 non trovano più l'inizio della traiettoria). I 132 e 128 del paragrafo 8.2 erano del programma del 30/09.

### 8.7 Il colpo parte dal punto di contatto, non dai piedi (1° ottobre)

Sul video il dritto 418 aveva l'etichetta calcolata dai piedi e la freccia della mappa disegnata dal contatto: le due cose potevano non andare d'accordo. Ora il lato di partenza dei dritti e dei rovesci viene dal punto di contatto, in quest'ordine:

1. **contatto**: il punto di contatto del calcolo (`impact_xyz_m`), quando il contatto si è visto (calcolo normale e ricerca estesa). Il contatto di `direzione_nascosta.py` è un'ipotesi (messo al polso in un fotogramma del tratto coperto), quindi non conta.
2. **traiettoria**: i punti della pallina nel primo 1/6 di secondo dopo il contatto (10 frame a 60 fps, con gli istanti veri nei video convertiti; almeno 3), con una retta nel tempo per x e y dell'immagine riportata all'istante del contatto; quel pixel si porta alla profondità del giocatore con la calibrazione. Non il primo punto così com'è. Se il punto viene a più di 2,5 m dai piedi si scarta. Siccome il contatto di solito è un po' davanti al corpo, il punto si sposta leggermente verso l'asse della camera (circa 0,15-0,3 m per metro di differenza).
3. **piedi**: come prima, se non c'è nient'altro.

Il servizio resta sui piedi (il lato decide il riquadro: dove sta chi serve). Nelle stime dal rimbalzo il volo parte da questo punto invece che dai piedi, quindi cambiano un po' `contatto_x_m`, `arrivo_x_m` e `angolo_gradi`, e i km/h di ±1. Nuove colonne: `partenza_da` (contatto / traiettoria / piedi) e, per leggere la regola in gradi, `soglia_sx_gradi` e `soglia_dx_gradi`: gli angoli dal contatto ai due confini del terzo centrale a 21 m.

Prova A/B, prima con il centro di 1 m: sui quattro video cambia solo il 418 ("lungo linea" → "dal centro verso sinistra"); Nicola, Djokovic e swing_vision restano con le stesse direzioni (su swing_vision 553 cambiano solo contatto, arrivo e angolo, perché la stima dal rimbalzo ora parte dal contatto della ricerca estesa). Il 717 resta "lungo linea": contatto coperto, partenza dalla traiettoria a x 7,69 (piedi 7,53). Poi la larghezza del centro: con 1 m, con i terzi e con 1,6 m le classi sui quattro video sono uguali; con 2 m quattro colpi cambiano in peggio (alcaraz 577 e 1152, tirati dall'angolo, diventano "dal centro"; Nicola 223 e swing 412 diventano "centrale"). Resta quindi il terzo centrale.

### 8.8 Dentro o fuori e palla corta (1° ottobre)

Dal rimbalzo trovato si dice dove è caduta la pallina: dentro o fuori (dritti e rovesci sul campo singolo avversario; servizio nel riquadro in diagonale; la riga conta dentro; si decide sempre, scelta dell'utente) e la profondità. Il 2 ottobre l'utente ha dato quattro fasce, dalla riga di fondo verso la rete: profonda 1,5 m, media 3,5 m, corta 3 m, palla corta (smorzata) gli ultimi 3 m prima della rete. Sommate fanno 11 m, mentre la metà campo è 11,885 m: le due fasce in mezzo le ho adattate alle righe vere, così la media finisce sulla riga del servizio (3,985 m) e la corta va dalla riga del servizio a 3 m dalla rete (3,40 m). Prima erano tre fasce: corta entro 3 m dalla rete, profonda negli ultimi 3 m (poi 2), media in mezzo. Nuove colonne `dentro_fuori`, `distanza_riga_m`, `riga_vicina`, `profondita`; sul video una riga in più nell'etichetta e il bordo rosso del pallino se è fuori.

Il punto debole è la profondità vicino al fondo lontano. Con la camera a 2,2 m il campo lontano è schiacciato contro la rete: nell'immagine di alcaraz la riga di fondo lontana è a 3 pixel dal punto in cui il dritto 418 rimbalza, e 3 pixel lì valgono 0,7 m. Per questo quel "fuori lungo di 0,7 m" non è sicuro. Un pixel vale circa 0,27-0,30 m vicino al fondo, 0,15 m vicino alla rete; di lato circa 2 cm. Con una camera più alta e più indietro (Djokovic: 3,2 m, 13,6 m dietro il fondo, 4K) un pixel vale 0,06 m. Risultati: tutti i rimbalzi trovati sono dentro tranne alcaraz 418; nessuna palla corta nei video di prova (sono scambi da fondo).

### 8.9 Velocità media, metriche della sessione e scheda (2 ottobre)

Tre richieste dell'utente, insieme.

**La velocità media del volo.** È la distanza a terra dal contatto al rimbalzo diviso il tempo di volo: quella che mostra SwingVision (per il servizio di Nicola 83 km/h, contro i nostri 116 d'uscita). Non serviva un calcolo nuovo: nelle stime dal rimbalzo è il dato di partenza ("media fino al rimbalzo" nella nota); per i colpi misurati bastano il contatto del calcolo e il rimbalzo del passo 6. `velocita_rimbalzo.py` la scrive nella colonna `velocita_media_kmh` (passo 7). Sul video sta in piccolo sotto la velocità d'uscita. La media è sempre più bassa dell'uscita, perché l'aria frena la pallina: sui video di prova il 76-87%. Su swing_vision 412 invece viene 93 contro 90 misurati: una delle due misure è sbagliata (dalla media il dritto sarebbe sui 120 km/h, quindi probabilmente i 90 sono bassi). Lì la media non si mostra e la nota lo dice; i 90 km/h restano, come deciso (vedi 8.22, il controllo col rimbalzo sui km/h misurati).

**Le metriche.** `riepilogo.py` conta per tipo di colpo dentro, fuori ed esito non visto, con queste scelte dell'utente: buono = dentro, errore = fuori, rimbalzo non visto = non conta. Restano fuori dal conto i colpi senza velocità né direzione (sul video in grigio), che nei video di prova sono falsi colpi (alcaraz 246 e 1302) o un colpo coperto del tutto (swing_vision 1379). Alcaraz: 6 dentro su 7 con esito (dritti 3/4, rovesci 2/2, servizio 1/1), 1 errore (il 418, lungo, che però è al limite della precisione: 8.8).

**Il video e la scheda.** Sulla mappa la freccia ora si allunga dal colpo al rimbalzo con il tempo vero del volo, e il pallino del rimbalzo spunta nel fotogramma in cui la pallina tocca terra, con un'onda attorno; nello stesso momento compaiono nell'etichetta dentro/fuori e la media (il loro posto è riservato da prima, così non si sposta niente). In alto a destra un contatore (dentro, fuori, colpi per tipo) che si aggiorna a ogni colpo e a ogni rimbalzo. Alla fine del video 6 secondi con la scheda della sessione, che viene salvata anche come `<video>_scheda.png` per l'allievo. La scheda usa i colori del video un po' più scuri, controllati con un programma per chi confonde i colori, e in più forme diverse sulla mappa (cerchio dritto, rombo rovescio, quadrato servizio). Per le scritte usa il carattere DejaVu, che c'è con matplotlib sia su Colab sia sul PC (serve per le lettere accentate, che i caratteri di OpenCV non hanno).

Prova A/B sui quattro video con la catena completa: tutte le colonne di prima identiche; cambiano solo la colonna nuova e la nota di swing_vision 412.

Poi, lo stesso giorno, tre aggiunte chieste dall'utente. **Percentuale di errori e servizi validi**: nel riepilogo e nella scheda, per ogni tipo di colpo, gli errori (fuori) divisi i colpi con l'esito visto; nel servizio si parla di servizi validi e falli. **Correzione delle velocità**: all'utente i valori sembrano un po' alti e ha deciso, a occhio, di mostrarli ridotti del 15% (`CORREZIONE_VELOCITA = 0.85` in `riepilogo.py`): video, scheda e riepilogo mostrano i valori corretti, il calcolo e `<video>_velocita.csv` restano come sono. Un indizio nella stessa direzione è il servizio di Nicola (media del volo nostra circa 90-98 km/h, SwingVision 83), ma il numero va verificato con SwingVision o un radar accanto. **Dritto inside-out / inside-in**: dritto con i piedi almeno 1 m oltre la riga centrale dalla parte del rovescio (soglia dell'utente); poi, sempre su indicazione dell'utente, conta in quale dei tre terzi del campo avversario finisce la pallina: per un destro inside-in nel terzo di sinistra, inside-out nel terzo di destra, niente se finisce al centro. La mano si ricava dai contatti visti (nel dritto la racchetta è dalla parte della mano). Sui video di prova solo alcaraz 418 è inside-in.

Nota dell'utente: a occhio i colpi di Alcaraz sono tutti dentro, anche il 418 che il programma dà fuori lungo di 0,7 m (2,5 pixel, dentro l'errore della profondità: 8.8). Rifacendo la calibrazione senza il punto sbagliato (fondo lontano destro, 32,6 px) il 418 resta fuori di 0,7 m: con il telefono a 2,2 m la profondità vicino al fondo lontano non basta per decidere a meno di circa un metro.

### 8.10 Palline ferme in campo (3 ottobre)

Sul video Giorgio (telefono Android, 1080p a 30 fps, camera bassa a 1,71 m, palline a terra oltre la rete) il programma dava i km/h in 3 colpi su 12. Guardando i punti di TrackNet attorno ai colpi: prima del contatto TrackNet non vedeva la pallina vicino alla racchetta (che a occhio si vede benissimo) e indicava invece una pallina ferma a terra oltre la rete. Il 18% dei suoi punti erano palline a terra o che rotolavano piano. Siccome TrackNet "una pallina la vedeva", il rilevatore di colore non partiva; la traccia non arrivava al polso e il contatto non si trovava. Tre colpi veri (14,1, 24,7 e 37,0 s) non avevano nemmeno la riga.

**Il filtro.** `palla_locale.tracknet_fermi`: per ogni punto di TrackNet nella finestra di un colpo si guarda nei fotogrammi 0,4 e 0,6 s prima e dopo, nella stessa zona (0,02 altezze del giocatore più 0,1 altezze al secondo, per le palline che rotolano). Se c'è una pallina gialla piccola sia prima sia dopo, e il punto sta a metà tra le due, è una pallina ferma e si toglie. Tre accorgimenti, ciascuno nato da un errore della prova:
- **solo macchie piccole** (3-120 px quadrati a 1080p): la pallina in mano al giocatore vicino, più grande, veniva presa per ferma;
- **solo punti che, portati a terra, cadono in campo o attorno**: sopra la recinzione i cespugli secchi al sole sono pieni di giallo e la pallina in volo lì davanti (dopo il dritto delle 37,0 s) veniva tolta;
- **il punto deve stare a metà tra le due**: la pallina in gioco che rimbalza vicino a una pallina ferma (24,6 s) veniva tolta, perché nella stessa zona c'era giallo prima e dopo.

Controllo a occhio su 18 punti tolti: 16 palline a terra nella fascia della rete; gli altri due ora non vengono più tolti (la pallina che rimbalza e quella in mano).

**Il punto di partenza.** Senza le palline ferme, nel rovescio delle 18,2 s la traccia partiva da un punto isolato di TrackNet (un'altra pallina, vista un solo fotogramma) e si fermava subito: prima la direzione usciva solo perché la ricerca estesa si riagganciava per caso. Ora la traccia parte dal primo punto di TrackNet confermato da un altro vicino (entro 2 frame e 0,3 altezze del giocatore). Così segue la pallina lanciata, lasciata cadere, rimbalzata e colpita: contatto al 547, 62 km/h.

**Prova A/B** (catena completa): Nicola, Djokovic, swing_vision, alcaraz e test_tennis_1 identici. Giorgio: km/h da 3 a 5 colpi su 12 (dritto 37,0 s circa 130 km/h dal rimbalzo; rovescio 18,2 s 62 km/h misurati), solo direzione da 3 a 2, colpi veri senza riga da 3 a 1; in più una riga falsa senza dati a 16,5 s.

**Cosa resta.** Il rovescio delle 24,7 s (pallina dietro il giocatore per 5 frame proprio al colpo). I dritti con la pallina lasciata cadere: da dietro la pallina sale nell'immagine sia prima (dopo il rimbalzo) sia dopo il colpo, il cambio di direzione è piccolo (al 14,0 s 1,7 altezze al secondo contro la soglia di 2,5) e il contatto non si riconosce anche con la traccia giusta. E i 30 fps.

### 8.11 Il limite dell'angolo dal punto di contatto (4 ottobre)

Il controllo del risultato (punto 8 della sezione 7) scartava i dritti e i rovesci con un angolo oltre 45° rispetto alle righe laterali. Dal fondo è giusto: da lì, anche dall'angolo del campo verso la riga laterale opposta appena dopo la rete, si arriva al massimo a circa 34°. Ma uno strettino colpito da dentro il campo, per esempio dalla riga del servizio verso la riga laterale opposta appena dopo la rete, arriva a circa 50° e sarebbe stato scartato a torto.

Ora il limite si calcola dal punto di contatto (`limite_angolo`): l'angolo dal contatto alla riga laterale del singolo, dalla parte dove va la pallina, 0,5 m dopo la rete, più 10° di margine, mai sotto 45°. Esempi: dal fondo 45° (come prima); dalla riga del servizio a 0,6 m dalla riga laterale, verso l'altra riga laterale, 58°; dallo stesso punto ma a 4 m dalla rete, 70°. Il servizio resta escluso. Vale nella ricerca normale e in quella estesa.

Prova A/B (catena completa) su Nicola, Djokovic, swing_vision, alcaraz, test_tennis_1 e Giorgio: risultati identici. I colpi che superavano 45° erano tre (alcaraz 246 a −63°, alcaraz 867 a +85°, test_tennis_1 431 a +65°), tutti scartati anche per l'errore della traiettoria (21–37 px) e per velocità assurde: restano scartati. Il solo limite diverso da 45° sui video di prova è Giorgio 1806 (contatto a 3,4 m dal fondo, 0,5 m dentro la riga laterale destra, pallina verso sinistra: 50,8°), con un angolo di −18°.

### 8.12 Il servizio si colpisce sopra la testa (5 ottobre)

Sul video Giorgio, a 45,7 s, il programma scriveva un "servizio" con la misura scartata. Guardando i punti della pallina: Giorgio se la lancia sopra la testa (44,4-45,0 s), la pallina scende fino all'altezza della vita e lì cambia direzione (tocca terra o la racchetta), risale, riscende e a 46,5 s lui la gioca corta. Il classificatore della posa vede il braccio alzato del lancio e dice "servizio"; il cambio di direzione del tocco veniva preso per il contatto.

**Perché non "lanciata in alto e colpita mentre scende".** Vista da dietro, anche la pallina che arriva dal campo lontano sta sopra la testa del giocatore nell'immagine e scende verso di lui: la regola scatterebbe sui colpi di scambio. E nel video di Nicola il lancio comincia prima dell'inizio del video: si vede solo la discesa.

**La regola.** Il servizio si colpisce sopra la testa. `colpo_al_contatto` prende come prima la classe più votata nei 16 frame fino al contatto; se è "servizio" ma nel frame del contatto e nei 2 prima la pallina è sotto il bordo alto del riquadro del giocatore di almeno 0,05 altezze (in tutti i frame in cui si vede), il colpo prende la classe più votata tra le altre. Misure in altezze del giocatore, quindi uguali a ogni risoluzione. Sui video di prova la pallina al contatto è sopra la testa in tutti i servizi veri (Nicola +0,24, swing_vision +0,32, alcaraz +0,16 altezze) e sotto nel falso servizio di Giorgio (−0,43).

**Prova A/B** (catena completa, 6 video): cambia solo Giorgio 1373, da "servizio" a "dritto", sempre con la misura scartata (il tocco non è un colpo). Le righe senza contatto visibile (falsi servizi alcaraz 1302 e Giorgio 32,3 s) non si possono controllare e restano come prima. `SERVIZIO_SOPRA_TESTA = False` spegne la regola.

### 8.13 La velocità dal rimbalzo per i colpi «solo direzione» (5 ottobre)

Nei colpi «solo direzione» il contatto c'è: l'ha trovato la ricerca estesa di `velocita_uscita.py`, che però dà una velocità troppo bassa e quindi non si mostra. La stima dal rimbalzo dei passi 1-5 di `velocita_rimbalzo.py` invece cerca il contatto risalendo dal rimbalzo lungo i punti di TrackNet, e qui spesso si ferma nel posto sbagliato. Sul dritto di Giorgio a 39,8 s prendeva come rimbalzo il salto da una pallina ferma alla pallina vera subito dopo il colpo, e si fermava lì; il rimbalzo vero (40,5 s) lo trovava solo il passo 6, che serviva solo per la mappa. In una prova senza palline ferme sul rovescio delle 18,4 s la risalita si fermava 0,7 s dopo il contatto vero e dava 231 km/h: sbagliato, ma dentro i limiti 30-250, quindi sarebbe stato mostrato.

**La regola.** Se in un colpo «solo direzione» il passo 6 trova il rimbalzo, la velocità si stima dal contatto della riga (mezzo fotogramma dopo il frame della riga) al rimbalzo, con lo stesso calcolo dei passi 4-5 (`stima_da_contatto_esteso`): niente risalita. Sul video «circa X km/h (dal rimbalzo)», la direzione dal rimbalzo; con il rimbalzo ricostruito «(rimbalzo ricostruito)» e margine ±20%.

**Prova A/B** (catena completa, 6 video): cambia solo Giorgio 39,8 s, da solo direzione a circa 108 km/h, media del volo 86 (rapporto 0,80, normale), direzione invariata. Le altre righe «solo direzione» (swing_vision 302, Giorgio 49,7 s) non hanno rimbalzo e restano così. **Controllo del metodo** sui 5 colpi dove i passi 1-5 funzionano già, rifacendo il calcolo con il contatto della riga: swing_vision 553 120 → 111, alcaraz 141 166 → 166, alcaraz 418 149 → 146, Giorgio 904 108 → 98, 1806 101 → 94. Stesso valore o fino al 9% in meno: il contatto della riga è 2-5 fotogrammi prima di quello trovato risalendo, quindi il volo è un po' più lungo. Quei colpi non cambiano: la regola vale solo dove prima non c'era nessuna velocità. `PUNTO4 = False` la spegne.

### 8.14 La riga al picco del polso nelle finestre lunghe (5 ottobre)

Quando la posa dice che c'è un colpo e la pallina arriva al giocatore ma il contatto non si vede, `velocita_uscita.py` scrive una riga «contatto non visibile» alla fine del tratto più lungo della classe prevalente. Sul video Giorgio la prima finestra va da 1,5 a 9,4 s: il classificatore vede «dritto» già nella preparazione e nei palleggi, e la riga cadeva a 5,9 s, quando Giorgio non colpisce nessuna pallina. Il dritto vero è a circa 8,8 s.

**Il picco del polso** (`picco_polso`). Per ogni fotogramma: lo spostamento del polso più veloce rispetto al fotogramma prima, diviso l'altezza del riquadro del giocatore e moltiplicato per gli fps (altezze al secondo, uguale a ogni risoluzione), media su 3 fotogrammi. Il massimo nella finestra è lo swing. Confronto sui colpi di Giorgio con il contatto controllato a occhio:

| Colpo | Riga di prima | Picco del polso | Contatto vero |
|---|---|---|---|
| dritto, finestra di 7,9 s | 179 | 263 | circa 263 |
| dritto 11,5 s | 346 | 357 | circa 333 |
| dritto 13,4 s | 403 | 423 | circa 424 |

Nella finestra lunga il picco è molto meglio; su un colpo normale può allontanarsi dal contatto (11,5 s).

**La regola.** Solo se la finestra dura più di `FINESTRA_LUNGA_S` = 3 s la riga va al picco del polso; il colpo è il più votato dalla posa nei 16 fotogrammi fino al picco (`colpo_vicino`). Con la riga al momento giusto anche `direzione_nascosta.py` e `velocita_rimbalzo.py` guardano il momento giusto.

**Prova A/B** (catena completa, 6 video): cambiano solo Giorgio, da 179 a 263, e swing_vision, da 1379 a 1377 (sempre senza dati). Nessuna riga con la velocità cambia. Sul dritto di Giorgio la stima dal rimbalzo ora trova il rimbalzo: circa 68 km/h, dal centro verso sinistra, dentro, corta. Probabilmente un po' alta: la stima prende come contatto il primo punto in cui TrackNet rivede la pallina (frame 272, 9,05 s), perché subito dopo il colpo TrackNet non la vede; con il contatto a 8,8 s il volo dura 1,39 s invece di 1,12 e verrebbe circa 58 km/h. Swing_vision 302 e Giorgio 49,7 s sono finestre lunghe, ma hanno un contatto trovato dalla ricerca estesa e non cambiano. Il calcolo usa i polsi già letti: tempo trascurabile. `FINESTRA_LUNGA_S = None` spegne la regola.

### 8.15 Una sola riga per colpo nella ricerca estesa (5 ottobre)

Su video_alcaraz_palline_sparse il rovescio a 13,3 s aveva due scritte: la ricerca normale non vedeva il contatto e metteva la riga «contatto non visibile» alla fine della finestra (frame 835, 13,9 s); poi la ricerca estesa trovava il contatto vero al frame 800 e scriveva la sua riga. La riga della ricerca estesa sostituiva quelle senza misura solo entro 15 frame (0,25 s a 60 fps): qui erano 35, quindi restavano tutte e due, la seconda senza dati.

La riga «contatto non visibile» è solo il segnaposto del colpo che la posa vede nella finestra: ora (`STESSA_FINESTRA`) la riga della ricerca estesa la sostituisce a qualunque distanza, sempre nella stessa finestra. Le righe «misura scartata» restano sostituite solo entro 15 frame, come prima.

**Prova A/B** (catena completa, 7 video: i 6 di sempre più video_alcaraz_palline_sparse): sparisce solo la riga doppia al 835 di video_alcaraz_palline_sparse; tutto il resto identico. `STESSA_FINESTRA = False` torna a prima.

### 8.16 Il rimbalzo a 3,3 cm da terra (6 ottobre)

Sul video Giorgio due rimbalzi profondi buoni erano chiamati fuori: il rovescio delle 18,2 s (0,69 m lungo) e il dritto delle 60,2 s (2,16 m). Tre cose spostano il rimbalzo sempre verso il fondo, mai verso la rete:
1. **Il raggio della pallina.** Il punto più basso visto veniva portato a terra come se il centro della pallina toccasse il campo; al rimbalzo invece il centro è a 3,3 cm. Con la camera bassa e lontana quei 3,3 cm diventano lunghezza: circa distanza × 3,3 cm / altezza della camera, 0,6 m su Giorgio (camera a 1,72 m, fondo lontano a circa 31 m).
2. **I fotogrammi.** A 30 fps il fotogramma più vicino può essere fino a 1/60 s prima o dopo il rimbalzo, con la pallina ancora qualche centimetro sopra il campo.
3. **Il rimbalzo non visto.** Se TrackNet perde la pallina proprio quando tocca terra, il punto più basso visto è ancora in aria. Alle 60,2 s l'ultimo punto visto in discesa è il 1843, poi un buco fino al 1848 e la risalita: il rimbalzo ricostruito unendo discesa e risalita sarebbe a circa 20,2 m, dentro. Alle 18,2 s, prima del rimbalzo, TrackNet era su un'altra pallina ferma e ha ritrovato quella giusta già in risalita.

**Adottato il punto 1** (`rimbalzo_a_terra`): il raggio della camera si interseca con il piano a 3,3 cm d'altezza (`RAGGIO_PALLINA`) e il rimbalzo è il punto a terra proprio sotto. Vale per il rimbalzo trovato con TrackNet, con il colore e per quello ricostruito.

**Prova A/B** (catena completa, 7 video: i 6 di prova e video_alcaraz_palline_sparse): tutti i rimbalzi 0,3-0,6 m più corti (di più con la camera più bassa); nessun dentro/fuori cambia: Giorgio 18,2 s da 0,71 a 0,10 m fuori, 60,2 s da 2,07 a 1,43 m, alcaraz 418 da 0,70 a 0,20 m (per l'utente è dentro); «profonda» diventa «media» su Giorgio 30,1 s, Djokovic 65, alcaraz 275 e 1152, video_alcaraz_palline_sparse 13,3 s. Le velocità stimate dal rimbalzo scendono di 2-4 km/h (la distanza è più corta), le medie del volo di 1-3 km/h; le velocità misurate non cambiano. Su Giorgio 18,2 s la media del volo (61 km/h) ora si mostra, perché non supera più i 62 misurati. Una direzione cambia: il dritto di Giorgio delle 60,2 s passa da «centrale» a «incrociato» (angolo da −15,0° a −15,2°, proprio sul confine; i punti in volo dicevano già incrociato). I due fuori di Giorgio si avvicinano alla riga ma restano fuori: alle 60,2 s conta il punto 3. `RIMBALZO_SUL_RAGGIO = False` torna a prima.

### 8.17 Il filtro delle palline ferme anche per direzione e rimbalzo (6 ottobre)

Il filtro dell'8.10 era nato per il contatto e valeva solo in `velocita_uscita.py`. `direzione_nascosta.py` (direzione dei colpi con il contatto coperto) e `velocita_rimbalzo.py` (rimbalzo e stima dal rimbalzo) usavano tutti i punti di TrackNet, anche quelli su palline ferme. Sul dritto di Giorgio delle 11,2 s, per esempio, mentre la pallina colpita rimbalzava TrackNet guardava per 12 fotogrammi una pallina ferma vicino alla rete.

**La regola.** `velocita_uscita.py` cerca le palline ferme anche fino a 1,6 s dopo ogni colpo (`FERME_DOPO_S`, lo stesso tempo in cui si cerca il rimbalzo) e scrive tutti i punti tolti in `<video>_palline_ferme.csv`; gli altri due file li leggono (`leggi_palline_ferme`) e li tolgono prima di tutto. Il filtro resta quello dell'8.10: pallina ferma o che rotola piano, nella zona del campo. Le palline in movimento (un'altra pallina che rotola veloce o che rimbalza) non le toglie.

**Perché non era stato adottato il 5 ottobre.** Nella prima prova la stima dal rimbalzo del rovescio delle 18,4 s («solo direzione») risaliva la traiettoria e si fermava 0,7 s dopo il contatto vero: 231 km/h, sbagliati ma dentro i limiti 30-250. Con la velocità dal rimbalzo per i colpi «solo direzione» (8.13) quella risalita non si fa più.

**Prova A/B** (catena completa, 7 video: i 6 di prova e video_alcaraz_palline_sparse): cambia solo Giorgio. Il dritto delle 11,5 s prende la direzione «dal centro verso sinistra» (`direzione_nascosta.py`, dai frame 341-350, errore 2,1 px); il rimbalzo del rovescio delle 18,2 s resta nello stesso punto (23,87 m), trovato con il colore invece che con TrackNet. Tutto il resto identico, JSON compresi. Tempo: qualche decina di secondi in più per video, per i fotogrammi letti dopo i colpi.

### 8.18 La direzione dalla pallina in uscita (6 ottobre)

Sul video Giorgio i primi dritti (pallina lasciata cadere dal giocatore, vista da dietro) avevano la riga «contatto non visibile» ma spesso nessuna direzione. `direzione_nascosta.py` parte dall'ultimo punto della pallina IN ARRIVO e cerca i punti dopo il tratto coperto: se la pallina in arrivo non si vede (cade vicino al corpo e TrackNet la perde) o ricompare lontano dal colpo, si ferma. Il dritto delle 14,0 s era così: la pallina colpita si vede bene subito dopo il colpo (frame 423-432), ma il metodo non arrivava a guardarla.

**La regola** (`USCITA`), solo quando il metodo normale non dà la direzione:

1. I punti di TrackNet attorno al colpo si dividono in tracce coerenti (`tracce`): in ordine di tempo ogni punto va alla traccia il cui ultimo punto, o la posizione prevista con l'ultima velocità, è più vicino, entro 0,08 altezze dell'immagine per fotogramma (fino a 3 fotogrammi) e con al massimo 0,5 s senza punti; se no comincia una traccia nuova. Così i punti di una pallina ferma o di un'altra pallina non si mescolano con quella colpita.
2. `pallina_in_uscita`: la prima traccia che comincia tra l'inizio della finestra della posa e 10 frame dopo la fine, con il primo punto entro 0,8 altezze del giocatore da un polso, almeno 6 punti e che si allontana dal giocatore per il suo moto (lo stesso controllo di prima, `si_allontana`).
3. `direzione_in_uscita`: il contatto si prova a 0,5, 1, 1,5, 2 e 2,5 fotogrammi prima del primo punto, nel pixel dove porta la retta dei primi 4 punti. Al polso no: la racchetta è più in là, e nelle prime prove con il pixel del polso i calcoli sbagliavano di 14-41 px. Poi lo stesso calcolo e le stesse condizioni di prima: il migliore entro 4 px, tutti quelli buoni d'accordo entro 6 gradi e sulla stessa direzione.
4. Se la direzione esce, la riga va al fotogramma prima del primo punto (se non c'è già un'altra riga entro 15 frame), così anche `velocita_rimbalzo.py` cerca il rimbalzo dal momento giusto. La nota dice da quale frame viene la pallina e da dove è stata spostata la riga. Se il passo si riesegue, la riga riparte dal frame di prima.

**Differenza dalla prova scartata dell'8.22** (ripartire dalla pallina vista col colore vicino al polso): quella cercava il contatto per avere i km/h, e trovava contatti falsi. Qui il contatto resta sconosciuto, i km/h misurati non si calcolano e la direzione si scrive solo se tutti i calcoli possibili sono d'accordo.

**Prova A/B** (catena completa, 7 video: i 6 di prova e video_alcaraz_palline_sparse, contro la versione con il filtro dell'8.17): cambiano 2 righe.

| Video | Prima | Ora |
|---|---|---|
| Giorgio, dritto 14,0 s | riga a 13,4 s (frame 403), senza dati | riga a 14,03 s (frame 422), «lungo linea» (+8,6°, dai frame 423-432, errore 1,2 px); rimbalzo visto da TrackNet al frame 451, fuori di lato di 0,94 m |
| video_alcaraz_palline_sparse, dritto 0,5 s | riga a 0,52 s (frame 32) | riga a 0,77 s (frame 47); 134 km/h dal rimbalzo, direzione e rimbalzo identici |

Il contatto del dritto di Giorgio controllato a occhio è circa al 424 (tabella dell'8.14). Il rimbalzo l'ho controllato a occhio con le righe del campo proiettate sul fotogramma: la pallina rimbalza nel corridoio del doppio, quindi fuori è giusto. Su video_alcaraz_palline_sparse la stima dal rimbalzo usava già il contatto al frame 47: ora la scritta è allo stesso istante. Tutto il resto identico, comprese le righe false di Giorgio (16,5, 32,3, 35,0 s), che restano senza direzione; su swing_vision 1377 e Giorgio 263 e 1052 (la riga falsa delle 35,0 s) la pallina in uscita si trova, ma i calcoli non sono d'accordo e non si scrive niente. Tempo trascurabile.

**Il rischio.** Una riga falsa (la posa vede un colpo che non c'è) proprio mentre parte una pallina vicino al polso che si allontana: pallina lanciata o palleggiata con la racchetta, cesto del maestro. Prenderebbe una direzione, forse un rimbalzo, e nelle metriche conterebbe come colpo. Sui 7 video non è successo, ma sono pochi e nessuno è una lezione con il cesto. `USCITA = False` spegne la regola.

### 8.19 La palla corta dalla serie di rimbalzi (6 ottobre)

Su Giorgio non usciva nessuna palla corta, e giustamente: nel video non ce ne sono (il rimbalzo più vicino alla rete è a 16,4 m, 4,5 m dalla rete, «corta»). Ma se il primo rimbalzo di una smorzata è coperto dalla rete o TrackNet lo perde, il programma non dice niente. L'idea dell'utente: guardare il secondo, il terzo, il quarto rimbalzo.

**La prima versione** (palla corta se il primo rimbalzo visto dopo il colpo cade entro 3 m dalla rete) l'ho scartata guardando tutti i rimbalzi di Giorgio: i tre «entro 3 m» del campo lontano sono tutti falsi (39,7 s: TrackNet salta da una pallina ferma alla rete a quella vera; 49,6 s: prima del colpo; 55,6 s: proprio al colpo). Sul dritto delle 39,7 s avrebbe scritto «palla corta» se il passo 6 non avesse trovato il rimbalzo vero al 1218.

**La serie.** Un rimbalzo falso è isolato; una smorzata invece rimbalza 2-3 volte prima della riga del servizio, sempre più bassa e in avanti. `tutti_i_rimbalzi` trova tutti i punti più bassi (stessa regola di `trova_rimbalzo`) nel campo avversario dalla rete in poi; `serie_di_rimbalzi` li mette in fila e accetta il rimbalzo dopo solo se è la stessa pallina: traiettoria continua tra i due (`_tratto_continuo`: almeno il 60% dei frame visti, buchi di al massimo 3 frame, niente salti oltre 40 px per frame a 1080p), volo al massimo 1,2 s e non più lungo del precedente (+2 frame), risalita non più alta del 125% della precedente, in avanti (al massimo 0,5 m indietro), meno di 2 m di lato e di 4 m tra uno e l'altro. Al primo rimbalzo che non torna la serie si chiude (una serie non salta rimbalzi). Palla corta (`palla_corta_da_serie`) se la serie ha almeno 2 rimbalzi e il primo visto cade prima della riga del servizio: con il primo rimbalzo nascosto, il primo visto è di solito il secondo vero, che in una smorzata cade 2-3 m più avanti del primo; chiedere 2 rimbalzi visti prima della riga voleva dire 3 rimbalzi veri, e nella simulazione la smorzata normale non passava.

**Quando finisce un colpo** (macchina a stati decisa con l'utente: COLPO → VOLO → PRIMO RIMBALZO → rimbalzo nascosto → PALLINA CHE MUORE → FINE COLPO). Negli 8 video si colpisce ogni 1,8-2,9 s (alcaraz 2,2-2,6; palline sparse 2,3-2,9; swing 1,8-2,3; Giorgio 2,4-6,7) e TrackNet dà una sola pallina per fotogramma. Con una finestra fissa di 4 s, nella simulazione una palla corta tirata 1,8-2,2 s dopo un colpo profondo finiva nella serie del colpo prima (10 volte su 10); con 2,5 s la regola non scattava mai, perché il terzo rimbalzo arriva 2,8-3 s dopo il colpo. Ora la serie deve **cominciare** entro 2,5 s dal contatto (`CORTA_INIZIO_MAX_S`) e il colpo **finisce a un evento** (`fine_dei_colpi`): il contatto del colpo dopo (qualsiasi riga) o, se quel colpo non ha una riga, il picco del polso (`picco_polso`) di uno swing della posa che comincia dopo il contatto. L'inizio dello swing non va bene: la posa vede la preparazione già 1,1-2 s dopo il colpo prima (alcaraz 1,4-2,0 s, palline sparse 1,6-1,9, Giorgio 1,1) e avrebbe tagliato il rimbalzo vero del dritto di Giorgio delle 8,7 s (a 1,4 s). Con contatto e picco del polso la fine cade 1,8-2,9 s dopo il colpo nei video a ritmo di cesto, e nessuno dei rimbalzi trovati dai passi 1-6 cade dopo la fine del suo colpo. `CORTA_SICUREZZA_S` = 6 s è solo un limite di sicurezza. Senza `<video>_colpi.csv` (risultati vecchi) valgono solo i contatti.

**Cosa scrive.** `rimbalzo_trovato_come` = «serie», il punto del primo rimbalzo visto, `profondita` = «palla corta», niente dentro/fuori né velocità media; la nota elenca i frame. `rimbalzi_prima_servizio` (anche per i dritti e rovesci con il primo rimbalzo di TrackNet prima della riga): quanti rimbalzi visti prima della riga del servizio. `disegna_velocita.py` scrive «palla corta (1o rimbalzo non visto)»; `riepilogo.py` la conta tra le palle corte.

**Simulazione** (camera di Giorgio, 30 fps, griglia di TrackNet 3,75 px, rumore 1 px, un frame su dieci perso, primo rimbalzo nascosto per ±4 frame; 10 prove per caso): smorzata (primo rimbalzo a 1,6 m dalla rete) 9/10; smorzata con molto backspin 10/10; con il colpo dopo a 3,5 s 9/10; smorzata lunga (secondo rimbalzo oltre la riga), palla corta-media e profonda 0/10; salti tra palline ferme vicino alla rete e la pallina vera 0/10; palla profonda seguita da una palla corta da metà campo a 1,8 o 2,2 s 0/10, anche se il colpo dopo ha solo la finestra della posa. Restano: smorzata a ritmo di cesto (colpo dopo a 2,5 s) 0/10, persa perché TrackNet passa alla pallina nuova; colpo dopo che non vede nessuno (né riga né posa) 9/10 falsi. A 60 fps non cambia molto; il quarto rimbalzo (circa 5 cm, 4-5 px) a 30 fps quasi non si vede.

**Prova A/B** (catena del PC con la pallina in uscita dell'8.18 fino a `direzione_nascosta.py`, poi `velocita_rimbalzo.py` senza e con il passo 6b, 8 video: i 6 di prova, video_alcaraz_palline_sparse e Giorgio): la regola entra in 6 colpi (Giorgio 11,5 e 49,7 s, alcaraz 1015, Nicola 223, palline sparse 656, Djokovic 217) e non trova nessuna serie; CSV e JSON identici a parte la colonna nuova, che compare in 2 colpi con valore 1 (Giorgio 8,7 s, rimbalzo a 16,4 m; palline sparse 0,8 s, frame 47, 17,85 m). Le misure di controllo non cambiano (Nicola 114, Djokovic 129 e 121, swing_vision 90). In piu' ho guardato tutti i 40 rimbalzi del campo lontano degli 8 video, non solo quelli dopo i colpi: nessuno forma una serie da palla corta, nemmeno i tre falsi di Giorgio. Resta da provare su smorzate vere.

### 8.20 Il rimbalzo cercato sulla pallina del colpo (8 ottobre)

Dalla validazione a occhio dell'identità della pallina (7 ottobre, `Claude outputs/validazione_identita_pallina.pdf`): su 38 righe con punti scritti, 37 giuste e una sbagliata (Giorgio, dritto delle 39,7 s: 6 dei 26 `_punti` erano palline ferme alla rete); su 30 rimbalzi, uno su una pallina ferma (video_alcaraz_palline_sparse, rovescio delle 13,3 s: il colore la trovava nel buco di TrackNet, 139 km/h) e uno in un buco (Giorgio 60,2 s, vedi 8.21). Il motivo è lo stesso dell'8.18: `velocita_rimbalzo.py` cercava il rimbalzo su tutti i punti di TrackNet attorno al colpo, e un punto di un'altra pallina può passare i controlli.

**La regola.** Tre cose, ognuna con la sua costante per spegnerla.

1. **La traccia della pallina del colpo** (`traccia_del_colpo`, `TRACCIA_DEL_COLPO`). I punti di TrackNet filtrati attorno al colpo si dividono in tracce coerenti con la stessa `tracce` di `direzione_nascosta.py` (salto massimo 0,08 altezze dell'immagine per fotogramma, buchi fino a 0,75 s). Si prende la traccia che contiene più punti del colpo (`_punti` scritti da `velocita_uscita.py` o `direzione_nascosta.py`: stesso fotogramma, entro 0,1 altezze del giocatore). Tutti i passi (1-3, 4, 5, 6 e `PUNTO4`) cercano il rimbalzo solo lì, e i `_punti` scritti con la stima vengono da lì. Se il colpo non ha `_punti` o nessuna traccia li contiene: tutti i punti, come prima. Il passo 6b (serie di rimbalzi) resta su tutti i punti: ha già i suoi controlli di continuità.
2. **Palline ferme nel colore** (`COLORE_FERME`). Nel passo 4 una macchia gialla trovata in un buco si prende come prima se sta sulla strada prevista dagli ultimi due punti (entro 12 px + 4 px per fotogramma di buco, a 1080p). Se è fuori strada si guarda il fotogramma di 0,4 s prima: se lì c'era già una macchia nello stesso punto è una pallina ferma e si scarta (la pallina in volo in quell'istante era altrove). Serve perché la maschera del giallo fermo (8.10) non vede le palline attraverso le maglie della rete: nella mediana il loro colore è fuori soglia.
3. **Rimbalzo ricostruito solo se la pallina continua** (`RIC_VELOCITA_MIN`). Nel passo 5 le due curve valgono solo se dopo il buco la pallina va almeno 0,3 volte la velocità di prima (nell'immagine): dopo un rimbalzo la velocità resta simile (alcaraz 709: rapporto 0,9), dopo un colpo dell'avversario no (alcaraz 1015: 0,21).

**Prova A/B** (passo del rimbalzo sui 7 video, dal JSON scritto da `direzione_nascosta.py`; `velocita_uscita.py` e `direzione_nascosta.py` non cambiano): 5 video identici (Nicola, Djokovic, swing_vision, alcaraz, test_tennis_1), 3 righe cambiano, controllate a occhio.

| Video | Prima | Ora |
|---|---|---|
| Giorgio, dritto 39,7 s | rimbalzo 1218, 26 `_punti` di cui 6 su palline ferme alla rete; 104 km/h, media 84 | rimbalzo 1218 uguale, 18 `_punti` tutti sulla pallina colpita; 108 km/h, media 87 (la partenza laterale del volo ora si calcola dalla pallina giusta) |
| Giorgio, dritto 14,0 s | rimbalzo 451 visto da TrackNet, (10,5; 21,3) m, fuori di 0,94 m, nessuna velocità | rimbalzo 452 trovato con il colore, (10,0; 18,1) m, fuori di 0,43 m, circa 84 km/h |
| video_alcaraz_palline_sparse, rovescio 13,3 s | rimbalzo «colore» al 855 su una pallina ferma, 139 km/h, (6,7; 22,1) m | la macchia ferma viene riconosciuta e scartata; il rimbalzo ricostruito fallisce per 10 px; la riga resta «solo direzione», senza km/h |

Giorgio 14,0 s: il 451 passava il controllo «scende poi risale» grazie ai punti delle palline ferme ai frame 452-453 (dopo il 451 TrackNet perde la pallina per 10 fotogrammi). Sulla traccia della pallina quei punti non ci sono, e il colore la trova al 452 un po' più in basso (y 573 → 588): è il punto più basso in cui si vede, dal 453 risale. Di lato resta fuori, nel corridoio del doppio; in profondità 3,2 m per un fotogramma di differenza: a quella distanza, con la camera a 1,7 m, un fotogramma di discesa vale 15 px e 3 m. Una sola riga con la velocità cambia (Giorgio 39,7 s, 104 → 108 km/h, per il motivo detto: i `_punti` giusti); il numero che sparisce (sparse 13,3 s) era sbagliato di circa 10 km/h e 0,6 m; tutte le altre velocità restano identiche. Costo: il passo del rimbalzo dura il 40% in più (Giorgio 111 → 164 s, palline_sparse 89 → 126 s), quasi tutto nei salti a un fotogramma precedente per il controllo delle macchie ferme (`cap.set`, circa 0,4 s l'uno su HEVC); sulla catena completa circa il 6%.

**Cosa non risolve.** I colpi senza riga (posa, contatto) e le righe false; il rimbalzo nel buco di TrackNet (8.21). Il caso d'uso vero, le palline ferme vicino all'impatto nel cesto, non c'è in nessuno dei 7 video: da riprovare sul video del test cesto.

### 8.21 Il punto del rimbalzo nel buco di TrackNet (8 ottobre)

Giorgio, dritto delle 60,2 s: il rimbalzo visto da TrackNet al frame 1843 cadeva a 25,2 m, fuori di 1,4 m, ma a occhio la pallina rimbalza dentro. Guardando i fotogrammi: la pallina passa dietro la rete ai frame 1844-1847, è più bassa al 1845-1846 e dal 1847 risale. Il 1843, l'ultimo punto che TrackNet vede prima del buco, è ancora in discesa, in aria; portato a terra dalla camera dietro il giocatore un punto in aria cade più lungo del vero (a quella distanza un fotogramma di discesa vale circa 3 m). Il passo 5 non lo copriva: serve solo quando TrackNet non ha nessun punto basso, e qui ne aveva uno, sbagliato.

**La regola** (passo 6c, `correggi_punti_nel_buco`, `PUNTO_NEL_BUCO`). Per i rimbalzi «tracknet» (passi 1 e 6) si guarda se subito prima o subito dopo il punto più basso c'è un buco di più di 0,067 s (`RIMB_BUCO_S`: 2 frame a 30 fps, 4 a 60). Se sì, il punto si ricostruisce come al passo 5 (`cerca_rimbalzo_coperto_da`: curva della discesa sui punti prima del buco, curva della risalita su quelli dopo, il rimbalzo dove si incontrano, entro 20 px a 1080p), sulla traccia della pallina del colpo (8.20). Il punto ricostruito sostituisce quello visto per la mappa, dentro/fuori, distanza dalla riga e profondità; `rimbalzo_trovato_come` = «ricostruito» (nel video e nel riepilogo il cerchio vuoto, come per i rimbalzi coperti) e la nota dice tra quali frame TrackNet ha perso la pallina e dov'era il punto visto. Velocità, media del volo e direzione restano come prima: i km/h già scritti non si toccano.

**Prova A/B** (passo del rimbalzo sui 7 video, da sola e insieme all'8.20): cambiano 5 righe su 51, e sono esattamente i 5 rimbalzi «tracknet» accanto a un buco (gli altri 16 non ne hanno e restano uguali). Guardati fotogramma per fotogramma (`Claude outputs/prova_AP_e_B_rimbalzo.pdf`): in tutti e 5 la pallina tocca terra dentro il buco, nascosta dalla rete o dal nastro, e il punto che si prendeva prima era in aria; il fotogramma ricostruito coincide con il punto più basso che si intravede tra le maglie (±1).

| Video | Buco di TrackNet | Prima (in aria) | Ora (nel buco) |
|---|---|---|---|
| Giorgio, dritto 60,2 s | 1844-1847, dietro la rete | frame 1843, (3,0; 25,2) m, **fuori** | frame 1845, (3,2; 20,2) m, **dentro**, media |
| alcaraz, rovescio 14,4 s | 919-923, dietro il nastro | frame 924, (6,7; 23,1) m, profonda | frame 921, (6,5; 21,2) m, media |
| video_alcaraz_palline_sparse, dritto 3,0 s | 243-247, dietro la rete | frame 248, (5,6; 22,4) m, profonda | frame 246, (5,6; 20,1) m, media |
| video_alcaraz_palline_sparse, dritto 18,3 s | 1138-1142, dietro la rete | frame 1143, (5,8; 21,5) m | frame 1141, (5,8; 19,0) m |
| video_alcaraz_palline_sparse, dritto 23,1 s | 1431-1435, dietro il nastro | frame 1430, (6,6; 20,5) m | frame 1433, (6,5; 18,4) m |

La correzione va sempre nello stesso verso, più corto, e il perché è geometrico. Quanto più corto (2-5 m) lo dicono le due curve: non c'è una verità a terra per nessuno dei 5, si sa che il punto vecchio era in aria, non di quanto il nuovo sia giusto; se le curve si incontrano qualche pixel più su o più giù del vero, a quella distanza sono 2-3 m. Insieme all'8.20 le righe che cambiano sono esattamente la somma (8 su 51), nessuna interazione. Costo trascurabile. Con 7 video è poco: da tenere d'occhio sui prossimi, soprattutto i rimbalzi vicino al fondo lontano.

### 8.22 Cosa ho provato e scartato

- **Ripartire a cercare la pallina dopo 8 frame vuoti** invece di arrendersi: rompeva il rovescio di Nicola.
- **Usare la ricerca estesa anche per i km/h**: velocità troppo basse (vedi sopra).
- **Controllo di stabilità** (ricalcolare spostando il contatto di un frame): anche i colpi buoni cambiano molto, mentre un valore sbagliato può restare stabile. Non distingue.
- **Controllo col rimbalzo sui km/h misurati** (non mostrarli se sotto la media fino al rimbalzo): proposto, non adottato per scelta.
- **Palline ferme riconosciute solo dai punti di TrackNet** (stesso punto per più di 1-1,5 s, senza guardare l'immagine): prendeva per ferma anche la pallina vera nel tratto alto della parabola (alcaraz, dopo il dritto del 275, 0,38 s quasi ferma) e perdeva le palline ferme viste da TrackNet per pochi frame proprio prima del colpo (Giorgio 24,6 s). Sostituito dal controllo nell'immagine (8.10).
- **Palla corta con la soglia della velocità dopo il contatto più bassa** (5 ottobre): contatti anche con la pallina che dopo va piano (da 1 a 2,4 altezze al secondo) e sale nell'immagine, tenuti solo se il calcolo li accetta. Su 6 video 8 candidati, tutti scartati dal calcolo (9-18 km/h, angoli fino a 82°); la palla corta di Giorgio a 46,5 s dà 18 km/h e −70°. Con la camera bassa una pallina lenta che si allontana non si misura. Non adottato.
- **Palla corta dal solo primo rimbalzo visto entro 3 m dalla rete** (6 ottobre): tre rimbalzi falsi su Giorgio, vedi 8.19. Sostituita dalla serie.
- **Finestra fissa per la serie di rimbalzi** (4 s o 2,5 s dal colpo, 6 ottobre): con 4 s la pallina del colpo dopo finiva nel colpo prima, con 2,5 s la regola non scattava mai (8.19). Sostituita dalla fine del colpo a un evento.
- **Fine del colpo all'inizio dello swing dopo** (6 ottobre): la posa vede la preparazione già 1-2 s dopo il colpo prima, avrebbe tagliato rimbalzi veri (8.19). Usati il contatto e il picco del polso.
- **Ripartire dalla pallina vista col colore vicino al polso, e contatto anche per accelerazione** (pallina che riparte almeno 2 volte più veloce nella stessa direzione), quando la traccia normale non trova il contatto: su Giorgio trova il dritto delle 14,0 s e quello delle 39,8 s, ma dà contatti falsi nel dritto delle 11,2 s (traccia saltata su una pallina ferma) e in quello delle 37,0 s. Non adottato.
- **Nel colore, la macchia deve stare vicino alla posizione prevista** dagli ultimi due punti (8 ottobre, prima versione dell'8.20): perdeva il rimbalzo giusto di alcaraz 418 (al 470 la pallina risale e la previsione va dall'altra parte; su alcaraz i fotogrammi ripetuti danno velocità zero) e non recuperava palline_sparse 13,3 s. Una previsione da due punti non distingue «pallina ferma» da «pallina che ha appena rimbalzato». Sostituita dal controllo della macchia 0,4 s prima.
- **Solo la traccia della pallina del colpo, senza la guardia del passo 5** (8 ottobre): su alcaraz 1015 il passo 5 trovava un buco pulito (1052-1069) con la pallina che scende prima e «risale» dopo, ma dopo è il colpo dell'avversario ai piedi: rimbalzo ricostruito falso al 1061, 184 km/h, fuori. Prima lo evitava per caso (un punto di un'altra pallina rompeva la discesa). Da qui `RIC_VELOCITA_MIN`.
