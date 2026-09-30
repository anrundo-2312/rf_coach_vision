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

`calibra_campo.py` apre una finestra di OpenCV e legge mouse e tastiera, cosa che richiede uno schermo collegato al computer su cui gira il programma. Colab gira su un server di Google senza schermo, quindi lì la finestra non si apre. Per i video girati fuori dalla posizione standard c'è `calibra_colab.py`, la cella 7c del notebook, che cambia solo il modo di cliccare:

1. Python legge il fotogramma e lo manda al browser come JPEG, insieme all'elenco dei punti del campo (gli stessi 23 di `calibra_campo.py`).
2. Un pezzetto di JavaScript disegna nella cella il fotogramma, la lente e lo schema del campo, e raccoglie i clic e i tasti. Le coordinate del clic vengono riportate ai pixel del fotogramma originale, anche se nel notebook l'immagine è rimpicciolita.
3. Quando si preme F, i punti tornano a Python (`google.colab.output.eval_js` aspetta la fine dei clic). Da qui calcolo e salvataggio sono quelli di `calibra_campo.py`: stesso JSON, stessa immagine di controllo. Il JSON viene copiato anche su Drive in `calibrazioni/`, così la cella 4 lo riporta nelle sessioni successive.

Il costo di calcolo è trascurabile: la stima della camera richiede circa 0,1 secondi di CPU e non usa la GPU. Il tempo è quello dei clic, una volta per ogni posizione della camera.

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
6. **Lungo linea, incrociato, centrale.** Si guarda da dove parte il giocatore (a sinistra, al centro o a destra della riga centrale, con ±1 m di margine per il centro) e dove arriverebbe la pallina, prolungando la direzione fino a 21 m, tra riga del servizio e fondo lontani:
   - lungo linea: parte da un lato e arriva sulla metà dello stesso lato;
   - incrociato: arriva sulla metà opposta;
   - centrale: arriva entro 1 m dalla riga centrale;
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

8. **Controllo del risultato.** Il calcolo resta identico: si decide solo se mostrarlo. Sul video alcaraz alcuni colpi davano 4, 377 e 25 km/h, con angoli fino a 85°. In tutti e tre la traiettoria 3D spiegava male i punti: 17–35 px di errore, contro 1–3 px dei colpi buoni (riportati a 1080p: Nicola 2,0, Djokovic 2,0 e 0,8, swing_vision 0,7, il dritto buono di Alcaraz 2,8). Il motivo è che i punti seguiti non erano la pallina colpita: la racchetta gialla di Alcaraz presa dal rilevatore di colore, altre palline, l'altro giocatore. Ora velocità e direzione non si scrivono se l'errore supera 6 px a 1080p, oppure se la velocità è fuori da 30–250 km/h, oppure se un colpo da fondo ha un angolo oltre 45°. La riga resta nel CSV con la nota "misura scartata" e i motivi, e sul video compare "misura non affidabile". Sui colpi di Nicola, Djokovic e swing_vision non cambia niente.

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

### 8.4 Cosa ho provato e scartato

- **Ripartire a cercare la pallina dopo 8 frame vuoti** invece di arrendersi: rompeva il rovescio di Nicola.
- **Usare la ricerca estesa anche per i km/h**: velocità troppo basse (vedi sopra).
- **Controllo di stabilità** (ricalcolare spostando il contatto di un frame): anche i colpi buoni cambiano molto, mentre un valore sbagliato può restare stabile. Non distingue.
- **Controllo col rimbalzo sui km/h misurati** (non mostrarli se sotto la media fino al rimbalzo): proposto, non adottato per scelta.
