# Velocita' e direzione dei colpi

Per ogni colpo del giocatore inquadrato (quello vicino alla camera):

- la velocita' di USCITA della pallina dalla racchetta, in km/h (quella che
  misurerebbe un radar, la massima del colpo: dopo la pallina rallenta);
- la direzione: lungo linea, incrociato o centrale.

Non la velocita' in tutto il video: solo al colpo. I px/s di analyze.py
restano come sono, questo e' un calcolo separato.

Perche' i px/s non bastano: vicino alla camera un metro occupa piu' pixel
che lontano, e con la camera dietro al giocatore la pallina, dopo il colpo,
si allontana quasi lungo la linea di vista, quindi gran parte del suo
movimento nei pixel non si vede. Serve ricostruire la traiettoria in 3D, e
per farlo bisogna sapere dov'e' la camera rispetto al campo.

Spiegazione completa di come funziona: `COME_FUNZIONA.md` in questa cartella.

## File

- `rf_ball_exit_speed.py` - il calcolo fisico, scritto da un collaboratore del
  progetto: calibrazione della camera dai punti noti del campo, istante
  dell'impatto, traiettoria 3D (gravita' + resistenza dell'aria, senza
  rotazione) sui frame dopo l'impatto, velocita' di uscita. Due parametri
  aggiunti per noi: `forward` e `depth_tol`.
- `calibra_campo.py` - la calibrazione: si cliccano i punti del campo visibili
  su un fotogramma. Serve solo per i video girati con la camera in una
  posizione diversa da quella standard (vedi sotto).
- `calibra_colab.py` - la stessa calibrazione dentro il notebook di Colab
  (cella 7c): i clic li legge il browser, calcolo e file sono quelli di
  `calibra_campo.py`.
- `palla_locale.py` - rilevatore della pallina per colore, attorno al
  giocatore, dove TrackNet la perde. Ignora il giallo fermo dello sfondo
  (borse, cartelli) e ha una ricerca "estesa" usata solo per la direzione.
- `fotogrammi.py` - riconosce i video convertiti con fotogrammi ripetuti (es.
  50 -> 60 fps) e da' a ogni fotogramma il suo istante vero. Sui video del
  telefono non si attiva.
- `velocita_uscita.py` - il programma principale: trova i colpi e calcola
  velocita' e direzione.
- `direzione_nascosta.py` - solo per i colpi in cui la pallina e' coperta dal
  giocatore al contatto: prova a ricavare la direzione dal volo che si vede
  dopo. Non tocca la velocita'.
- `velocita_rimbalzo.py` - per i colpi rimasti senza km/h: velocita' STIMATA
  dal rimbalzo nel campo avversario, quando si vede. Va in una colonna a
  parte e sul video compare come "circa ... km/h (dal rimbalzo)". Per tutti
  gli altri colpi con una direzione cerca solo il punto del rimbalzo, per la
  mappa.
- `disegna_velocita.py` - riscrive il video con colpo, km/h, direzione e una
  piccola mappa del campo, con il punto in cui la pallina rimbalza.
- `calibrazioni/` - `standard.json`, la calibrazione standard, e quelle dei
  singoli video: `<video>.json` e `<video>_campo.jpg`, l'immagine di
  controllo (resta sul PC). Il JSON di un video viene copiato anche su Drive
  in `rf_coach_vision/calibrazioni/`, da dove lo prende Colab.

## Calibrazione standard (come SwingVision)

Per passare dai pixel ai metri serve sapere dov'e' la camera rispetto al
campo (la calibrazione). Invece di calibrare ogni video, come fa SwingVision
si mette il telefono sempre nello stesso modo e si usa sempre la stessa
calibrazione: `calibrazioni/standard.json`. Viene dal video di Nicola,
registrato con SwingVision: camera centrata, 6,7 m dietro il fondo, 2,2 m di
altezza, focale da zoom 1x (circa 68 gradi di campo orizzontale).

Come mettere il telefono:
- in orizzontale, zoom 1x (non 0,5x ne' 2x);
- dietro il fondo, centrato sulla riga centrale;
- in alto, sulla recinzione, all'incirca all'altezza standard;
- con il campo intero inquadrato, e fermo per tutta la registrazione.

`velocita_uscita.py` usa la calibrazione del video se c'e'
(`calibrazioni/<video>.json`), altrimenti quella standard, adattata alla
risoluzione del video (720p, 1080p, 4K: basta che sia 16:9). Nel CSV la
colonna `calibrazione` dice quale ha usato, e sul video compare
"calibrazione standard".

**Controllo.** Ogni volta viene scritto `outputs/dati/<video>_campo.jpg`: il
primo fotogramma con il campo della calibrazione disegnato in verde (su Colab
compare sotto la cella 7b). Se le righe verdi cadono su quelle vere il
telefono era messo bene; se no, le velocita' di quel video non sono
affidabili e serve una calibrazione propria (cella 7c su Colab, oppure
`calibra_campo.py` sul PC).

Quanto conta mettere il telefono esattamente come lo standard (simulazione:
calibrazione standard, camera vera spostata, un servizio a 90 km/h e un
dritto a 65 km/h, senza rumore):

| Camera vera rispetto allo standard | Servizio | Dritto | Angolo della direzione |
|---|---|---|---|
| 1,5 m piu' indietro o piu' avanti | meno di 1 km/h | meno di 1 km/h | 0 gradi |
| 1 m piu' in alto | -2 km/h | -8 km/h | 0 gradi |
| 1 m di lato | 0 | 0 | +3 gradi |
| telefono con zoom diverso (+15% di focale) | -10 km/h | -7 km/h | -1 grado |

La distanza dal fondo conta pochissimo; contano zoom 1x, camera centrata e
altezza simile. Rispettando questi tre punti l'errore resta dentro il
margine di +-20 km/h mostrato sul video.

I video girati in un altro modo (per esempio il video di Djokovic: camera
13,6 m dietro e molto zoomata) hanno bisogno della loro calibrazione.

## Come si usa

### Su Colab (consigliato: l'analisi su CPU e' lenta)

Nel notebook `colab/rf_coach_colab.ipynb` le celle 6 (analisi) e 7 (colpi)
come sempre, poi la 7b (velocita' e direzione), la 8 (salvataggio su Drive) e
la 9 (anteprima). Se il telefono era messo nella posizione standard non serve
altro: la 7b usa la calibrazione standard e mostra l'immagine di controllo.

Solo se l'immagine di controllo non torna, o per i video girati in un altro
modo, serve la calibrazione del video. Si fa nella cella 7c, direttamente su
Colab: si mette `CALIBRA = True`, si cliccano i punti sul fotogramma che
compare nella cella, e la cella salva la calibrazione anche su Drive in
`calibrazioni/` (vale per le sessioni successive) e rifa' velocita' e video.
Il calcolo dura meno di un secondo e non usa la GPU: il tempo e' solo quello
dei clic, una volta per posizione della camera.

In alternativa si puo' fare sul PC (anche con il video solo su Drive):

```
python velocita/calibra_campo.py "G:/Il mio Drive/rf_coach_vision/inputs/<video>.mp4"
```

Il JSON finisce da solo su Drive in `calibrazioni/`; se la cella 4 era gia'
stata eseguita, rieseguirla per portarlo su Colab, poi la 7b.

### Sul PC

Servono il tracking e i colpi del video (come sempre):

```
python analyze.py inputs/<video>.mp4
python classificazione/classifica_tracking.py --tracking outputs/dati/<video>_tracking.csv
```

Poi, solo se la camera non era nella posizione standard, la calibrazione del
campo (una volta per ogni posizione della camera):

```
python velocita/calibra_campo.py inputs/<video>.mp4
```

E infine velocita', direzione e video:

```
python velocita/velocita_uscita.py --video inputs/<video>.mp4
python velocita/direzione_nascosta.py --video inputs/<video>.mp4
python velocita/velocita_rimbalzo.py --video inputs/<video>.mp4
python velocita/disegna_velocita.py --video inputs/<video>.mp4
```

Risultati: `outputs/dati/<video>_velocita.csv` (un colpo per riga),
`outputs/dati/<video>_campo.jpg` (controllo della calibrazione) e
`outputs/video/<video>_velocita.mp4`.

### Calibrazione del campo di un video

Si apre un fotogramma: in alto c'e' scritto quale punto cliccare, lo schema
in basso a sinistra mostra dov'e' sul campo, la lente in alto ingrandisce
attorno al mouse. Tasti: clic = segna, S = non visibile, U = annulla,
frecce o IJKL = sposta di un pixel l'ultimo punto, `,` e `.` = fotogramma
precedente/successivo (se il giocatore copre le righe), F = fine, Esc = esci.

Su Colab (cella 7c) i punti e i tasti sono gli stessi, con due differenze:
il fotogramma si cambia con `FOTOGRAMMA` nella cella, e si puo' cliccare
nella lente per correggere l'ultimo punto.

Consigli:
- almeno 6 punti, sparsi: vicino, rete, lontano. Le cime della rete e dei pali
  non sono a terra e aiutano molto a stimare la camera;
- si clicca il centro dell'incrocio delle righe, e per le righe sotto la rete
  il punto in cui la riga tocca la linea della rete a terra;
- le cime dei pali valgono solo per i pali del doppio (1,07 m di altezza,
  0,914 m fuori dalla riga del doppio): con i paletti del singolo, saltarle.

Alla fine il campo viene ridisegnato in verde sopra il fotogramma, con
l'errore medio in pixel: la calibrazione e' buona se le righe verdi cadono su
quelle vere e l'errore e' di pochi pixel. Invio salva, R ricomincia. Con
`--verifica` si rifanno calcolo e immagine di controllo da una calibrazione
salvata, senza finestre (anche su Colab).

## Cosa fa velocita_uscita.py

1. **Colpi dalla posa.** I tratti dritto / rovescio / servizio del
   classificatore (buchi di "attesa" fino a 5 frame tollerati, almeno 8 frame)
   sono le finestre in cui cercare i colpi.
2. **Pallina nella finestra.** TrackNet dove la vede, il rilevatore di colore
   (`palla_locale.py`) dove la perde: succede proprio attorno al colpo,
   quando la pallina arriva lungo la linea di vista e nell'immagine quasi non
   si muove. Il giallo presente anche nello sfondo del tratto (mediana di 15
   fotogrammi: borse, sedie, cartelli) non viene preso per la pallina: sul
   video alcaraz, al dritto del frame 567, prima seguiva una borsa gialla.
3. **Contatto.** Cambio brusco della direzione della pallina (3 frame prima
   contro 3 dopo) con la pallina entro 0,6 altezze del giocatore da un polso,
   e pallina che DOPO si allontana veloce. L'ultima condizione scarta il
   rimbalzo della pallina dell'avversario davanti al giocatore, che
   nell'immagine sembra un colpo.
4. **Velocita'.** `exit_speed` sui ~1/3 di secondo dopo il contatto (20 frame
   a 60 fps), con la posizione a terra del giocatore (caviglie della posa,
   nel frame in cui i piedi sono piu' in basso: nel servizio al contatto sono
   in aria), il contatto entro 1 m dal giocatore (`depth_tol`) e la pallina
   diretta verso il campo avversario (`forward`). Se il video e' una
   conversione con fotogrammi ripetuti (`fotogrammi.py`: almeno l'8% dei
   fotogrammi, a passo regolare, es. uno ogni 6 in un video a 50 fps portato
   a 60), i ripetuti si tolgono e si usano gli istanti veri: sul dritto al 275
   di alcaraz l'errore della traiettoria scende da 2,8 a 1,1 px (147 -> 138
   km/h). Sugli altri video non cambia niente.
5. **Direzione.** Angolo della pallina rispetto alle righe laterali; la
   direzione viene prolungata fino a 21 m (tra riga del servizio e fondo
   lontani) per vedere in che meta' arriva:
   - *lungo linea*: parte da un lato e arriva sulla meta' dello stesso lato;
   - *incrociato*: arriva sulla meta' opposta;
   - *centrale*: arriva nel terzo centrale del campo singolo, cioe' entro
     1,37 m dalla riga centrale;
   - *dal centro verso destra/sinistra*: parte dal terzo centrale (entro
     1,37 m) e va verso un lato.
   Il "centro" e' quindi il terzo centrale del singolo, come le fasce del
   servizio. Fino al 1/10 era 1 m: il dritto 418 di alcaraz (piedi 1,25 m a
   sinistra della riga centrale, ma contatto praticamente sulla riga
   centrale) usciva "lungo linea"; con i terzi esce "dal centro verso
   sinistra", e sui quattro video di prova non cambia nient'altro.
   Per il servizio invece: *al T*, *al corpo* o *esterno*, secondo dove cade
   il rimbalzo previsto nel riquadro del servizio opposto (diviso in tre
   fasce uguali da 1,37 m, dalla riga centrale a quella del singolo). Entro
   25 cm dal confine con la fascia accanto si aggiunge verso quale fascia
   (es. "al corpo, verso il T"). Conta solo la posizione laterale del
   rimbalzo, che e' precisa; la profondita' no (vedi sotto), quindi non
   diciamo se il servizio e' lungo. Nel CSV ci sono `rimbalzo_x_m` e
   `rimbalzo_y_m`.
6. Se la posa indica un colpo, la pallina arriva al giocatore ma il contatto
   non si vede (pallina coperta dal corpo), il colpo viene scritto lo stesso,
   senza velocita', con una nota.
7. **Controllo del risultato.** Il calcolo non cambia: si decide solo se
   mostrarlo. Velocita' e direzione NON si scrivono quando la traiettoria 3D
   non spiega i punti della pallina (errore sopra 6 px, riportato a 1080p;
   sui colpi buoni e' 1-3 px), oppure il risultato non e' da tennis:
   velocita' fuori da 30-250 km/h, oppure un colpo da fondo con angolo oltre
   45 gradi. Nel CSV la riga resta, con `punti_usati`, `errore_px` e la nota
   "misura scartata: ..." con i motivi; sul video compare "km/h non
   disponibile - misura non affidabile". Succede quando i punti seguiti non
   sono la pallina colpita: sul video alcaraz la racchetta gialla presa dal
   rilevatore di colore, altre palline, l'altro giocatore.

8. **Solo direzione.** Se in un colpo non esce nessuna velocita', la
   pallina si cerca di nuovo in modo esteso: si accetta anche la pallina
   "strisciata" dal mosso al colpo, e se si perde si riaggancia al punto di
   TrackNet vicino all'ultima posizione; nel servizio si parte dal lancio
   (punti sopra la testa del giocatore) invece che dai palleggi. Se la
   traiettoria spiega bene i punti se ne tiene SOLO la direzione: con la
   pallina mossa al colpo la velocita' esce troppo bassa (alcaraz: servizio
   124 km/h e dritto 66 km/h, sotto la velocita' media fino al rimbalzo, 137
   e circa 105 km/h). Nel CSV la nota e' "pallina mossa al colpo: solo
   direzione".

Tutte le soglie sono in cima al file.

## Velocita' stimata dal rimbalzo

`velocita_rimbalzo.py` si esegue dopo `direzione_nascosta.py` e guarda solo i
colpi ancora senza km/h. Quando la pallina e' mossa o coperta vicino al
giocatore i punti subito dopo il colpo non sono buoni, ma spesso si vede dove
la pallina rimbalza nel campo avversario: quel punto e' a terra, quindi con
la calibrazione si sa esattamente dov'e'. Sapendo da dove parte la pallina
(il giocatore, a 1 m d'altezza; 2,6 m nel servizio), dove arriva e in quanto
tempo, c'e' una sola traiettoria con gravita' e resistenza dell'aria (lo
stesso modello del calcolo normale) che la spiega.

1. Rimbalzo: nei punti di TrackNet dopo il colpo, il primo punto piu' basso
   nell'immagine di quelli vicini (la pallina scende verso terra e risale),
   che a terra cada nel campo avversario.
2. Contatto: si risale dal rimbalzo lungo i punti di TrackNet finche' sono
   continui e la pallina non cambia bruscamente velocita' o direzione; il
   primo punto e' la pallina appena colpita, il contatto e' mezzo frame prima.
3. Velocita' e direzione dalla traiettoria giocatore -> rimbalzo; la
   direzione viene dal rimbalzo misurato.

Nel CSV la stima va nella colonna `velocita_rimbalzo_kmh` (quella di
`velocita_uscita_kmh` non viene mai toccata); sul video compare "circa ...
km/h (dal rimbalzo)" con margine circa +-15%. Dove anche il calcolo normale
funziona, i due metodi vanno abbastanza d'accordo: alcaraz, dritto al 275,
138 km/h dal calcolo normale e 131 dal rimbalzo; Djokovic, dritto al 65, 123
e 144 dal rimbalzo trovato con il colore (qui i passi 1-3 non trovano
l'inizio della traiettoria: TrackNet si interrompe al frame 99). Fino al 30/09,
con il programma di allora, erano 132 e 128.
Se TrackNet non vede il rimbalzo si provano altri due modi:

4. Colore nel campo lontano: nei fotogrammi dopo il colpo in cui TrackNet ha
   perso la pallina si cercano macchie gialle piccole (3-120 px quadrati a
   1080p) vicino all'ultima posizione nota, in un raggio di 12 px piu' 8 px per
   ogni fotogramma di buco, ignorando il giallo fermo. Sulla traccia
   completata si rifanno i passi 1-3 (margine circa +-15%). Con il contatto
   coperto, il contatto e' a meta' del tratto coperto.
5. Rimbalzo ricostruito: se il rimbalzo e' coperto (testa del giocatore,
   rete, avversario) ma la pallina si vede scendere prima e risalire dopo,
   con un buco di 4-20 fotogrammi, due curve adattate ai punti prima (almeno
   5) e dopo (almeno 3) si prolungano nel buco: il rimbalzo e' dove si
   incontrano. Se passano a piu' di 20 px (su 1080) i punti dopo non sono la
   stessa pallina e non si stima niente. Sul video compare "circa ... km/h
   (rimbalzo ricostruito)", margine circa +-20%.

Un rimbalzo non vale per due colpi. Prova del rimbalzo ricostruito:
nascondendo apposta il rimbalzo nei 5 colpi di alcaraz in cui si vede, in 4
la stima resta entro il 7%; nel quinto le curve passano a 102 px e il
controllo la scarta. Sui quattro video di prova i due modi aggiungono tre
velocita': alcaraz dritto al 418, circa 149 km/h (colore); alcaraz dritto al
709, circa 118 km/h (ricostruito); swing_vision rovescio al 553, circa 120
km/h (colore). Tutti gli altri colpi restano identici.
Limite: se la pallina non si vede ne' al rimbalzo ne' prima e dopo, non si
stima niente (alcaraz, rovescio al 1015: l'avversario la ribatte prima che
rimbalzi in vista).

### Il punto del rimbalzo sulla mappa (1 ottobre)

6. Per tutti gli altri colpi con una direzione (velocita' misurata, solo
   direzione, contatto coperto) si cerca solo dove la pallina rimbalza nel
   campo avversario, nei 1,6 s dopo il colpo (dopo la ricomparsa se il
   contatto era coperto), con gli stessi tre modi: TrackNet, colore,
   ricostruito. Non cambia ne' la velocita' ne' la direzione: serve per la
   mappa e come controllo. Se la direzione che darebbe il rimbalzo e'
   diversa da quella scritta, la nota lo dice ("il rimbalzo trovato ...
   darebbe ...").

Il rimbalzo trovato (passi 1-6) e' nelle colonne `rimbalzo_trovato_x_m`,
`rimbalzo_trovato_y_m`, `rimbalzo_trovato_frame` e `rimbalzo_trovato_come`
(tracknet, colore, ricostruito). `rimbalzo_x_m` e `rimbalzo_y_m` restano
quelle del servizio, usate per la fascia.

Sulla mappa del video: pallino giallo bordato di nero = rimbalzo visto
(TrackNet o colore); cerchio giallo vuoto = rimbalzo ricostruito; pallino
bianco = rimbalzo del servizio previsto dal calcolo, quando quello vero non
si trova.

Controllo sui colpi con la velocita' misurata: il rimbalzo si trova in 3 su
5 (alcaraz 275 e Djokovic 65 con TrackNet, swing_vision 412 con il colore) e
in tutti e 3 la direzione che darebbe e' la stessa del calcolo normale
(Djokovic 65: -5,1 gradi dal rimbalzo, -5,6 dal calcolo normale). Non si
trova nel servizio di Nicola (TrackNet perde la pallina prima del rimbalzo)
e nel rovescio di Djokovic al 217 (il video finisce prima). Su alcaraz il
punto c'e' in 7 colpi su 8; manca solo nel rovescio al 1015.
Tempo: il colore costa circa 15 s a colpo su un video 4K, quasi tutti per il
giallo fermo. I fotogrammi ora si leggono in fila invece che a salti: stessi
risultati, da circa 50 a 15 s a colpo in 4K.

## Colpi con il contatto nascosto: solo la direzione

`direzione_nascosta.py` si esegue dopo `velocita_uscita.py` e guarda solo i
colpi del punto 6. La velocita' resta "non disponibile": senza i primi frame
dopo il colpo dipende troppo dall'istante esatto del contatto (sul rovescio
di Nicola da 50 a oltre 200 km/h spostandolo di pochi frame). La direzione
invece si puo' ricavare dal volo che si vede dopo: vista dall'alto, la
pallina va praticamente dritta, perche' gravita' e aria non la fanno girare
di lato.

1. La pallina in arrivo si perde a un certo frame; si cercano i punti di
   TrackNet nei 0,75 s dopo e si tengono solo quelli su una stessa curva
   liscia (gli altri sono falsi rilevamenti).
2. Non sapendo quando e dove la racchetta ha colpito, si prova come contatto
   ogni frame del tratto coperto, a ciascuno dei due polsi, con lo stesso
   calcolo della traiettoria di `velocita_uscita.py` (il file
   `rf_ball_exit_speed.py` non e' modificato).
3. La direzione si scrive solo se tutti i calcoli che spiegano bene i punti
   danno la stessa risposta, con angoli entro 6 gradi; altrimenti niente.
4. Il colpo (istante stimato dalla posa) deve cadere nel tratto in cui la
   pallina e' coperta, con 0,25 s di tolleranza. Se la pallina si e' persa
   molto prima, i punti che si rivedono sono di un'altra parte dello scambio:
   sul video swing_vision_test1_trim il rovescio al frame 1379 aveva la
   pallina persa al 1247, e senza questo controllo usciva una direzione
   presa da frame di prima del colpo.
5. La pallina che ricompare deve allontanarsi dal giocatore per il suo moto:
   la distanza dai piedi del giocatore deve crescere e la pallina deve
   spostarsi nell'immagine piu' del giocatore. Sul video alcaraz, frame
   1302, il giocatore camminava (149 px) e la "pallina" quasi ferma (37 px):
   senza questo controllo usciva un falso "al T".

Nel CSV la nota dice da quali frame viene e l'intervallo degli angoli; sul
video compare "km/h non disponibile" con la direzione e la mappa.

Prove: sul rovescio di Nicola (pallina persa al frame 208, ricompare al 237)
esce "dal centro verso sinistra", angolo tra -4,7 e -0,4 gradi, arrivo a 3,7
m dalla riga laterale sinistra; la mappa di SwingVision mette il rimbalzo di
quel rovescio a circa 3,3 m. Sul video di Djokovic, cancellando la pallina
attorno al contatto (6 prove, 13-29 frame), non ha mai dato una direzione
sbagliata, ma non l'ha nemmeno mai data. Quindi: quando c'e' e' affidabile,
ma spesso manca.

## Precisione da aspettarsi

Dalle simulazioni (camera dietro al giocatore e rialzata, 60 fps, 20 frame
dopo l'impatto, colpi amatoriali da 65-90 km/h):

| | TrackNet preciso (2 px) | meno preciso (4 px) |
|---|---|---|
| velocita' | +-12-20 km/h | +-23-31 km/h |
| angolo della direzione | +-1 grado | +-2-3 gradi |
| rimbalzo del servizio, di lato | +-0,1-0,4 m | +-0,1-0,5 m |
| rimbalzo del servizio, in profondita' | +-2 m | +-3 m |

Sui video veri l'errore della pallina e' 1-4 px. La direzione e' quindi molto
piu' affidabile della velocita' (un incrociato fa 15-20 gradi, un lungo linea
0-5). La rotazione (topspin, slice) non e' nel modello: con il topspin la
velocita' esce sottostimata di circa 12 km/h. Il valore va sempre mostrato
con il suo margine.

## Provato su

| Video | Colpo | Contatto | Uscita | Direzione |
|---|---|---|---|---|
| nicola_matarese_trim | servizio | frame 15 | 116 km/h | al corpo, verso il T |
| nicola_matarese_trim | rovescio | frame 223 | non disponibile (pallina coperta) | dal centro verso sinistra (direzione_nascosta.py) |
| zverev_djokovic_trim_swin_like | dritto | frame 65 | 123 km/h | centrale |
| zverev_djokovic_trim_swin_like | rovescio | frame 217 | 114 km/h | centrale |
| swing_vision_test1_trim | dritto | frame 412 | 90 km/h | dal centro verso destra |
| swing_vision_test1_trim | servizio | frame 302 | non disponibile (pallina mossa) | esterno (solo direzione) |
| swing_vision_test1_trim | rovescio | frame 553 | circa 120 km/h (rimbalzo trovato con il colore) | centrale |
| alcaraz | servizio | frame 141 | circa 166 km/h (dal rimbalzo) | al T |
| alcaraz | dritto | frame 275 | 138 km/h | dal centro verso destra |
| alcaraz | dritto | frame 418 | circa 149 km/h (rimbalzo trovato con il colore) | dal centro verso sinistra (prima dei terzi: lungo linea) |
| alcaraz | dritto | frame 569 | circa 153 km/h (dal rimbalzo) | incrociato |
| alcaraz | dritto | frame 717 | circa 118 km/h (rimbalzo ricostruito) | lungo linea |
| alcaraz | rovescio | frame 871 | circa 127 km/h (dal rimbalzo) | centrale |
| alcaraz | rovescio | frame 1017 | non disponibile (pallina coperta) | incrociato (direzione_nascosta.py) |
| alcaraz | rovescio | frame 1168 | circa 152 km/h (dal rimbalzo) | lungo linea |

Il video di Nicola e' registrato con SwingVision, che per il servizio indica
83 km/h: pero' SwingVision mostra la velocita' MEDIA del volo, non quella di
uscita (la nostra media fino al rimbalzo e' ~90-98 km/h), e il rimbalzo che
calcoliamo cade quasi dove lo mette la sua mappa. Con il programma automatico
(20 frame) il rimbalzo esce a 3,96 m di larghezza contro 4,2 m di SwingVision:
lui e' al T vicino al confine, noi al corpo vicino al confine, da qui "al
corpo, verso il T". In profondita' la differenza e' di 2,3 m, come previsto.

Il video alcaraz (1080p, calibrazione del video con errore 9,5 px) e' difficile:
ripreso indoor con poca luce (la pallina colpita diventa una striscia mossa),
convertito da 50 a 60 fps, con oggetti gialli in campo. Gli 8 colpi veri
(contatti controllati a occhio, uno ogni 2,5 s circa) hanno ora tutti una
direzione, e tutte e 8 coincidono con quelle ricavate dai rimbalzi e dalle
immagini (il rovescio finale "lungo linea" l'aveva visto anche l'utente).
Velocita': una misurata (dritto al 275) e quattro stimate dal rimbalzo. Il
dritto al frame 246 non e' un colpo (resta "misura non affidabile") e il
"servizio" al 1302 e' un errore del classificatore (il giocatore cammina):
resta nel CSV senza direzione.

Le soglie sono state provate solo su questi quattro video: vanno verificate
su altri.

## Limiti e prossimi passi

- Colpi in cui la pallina passa dietro il corpo del giocatore subito dopo il
  contatto: niente velocita'; la direzione solo se il calcolo e' stabile
  (`direzione_nascosta.py`).
- La calibrazione standard vale solo con il telefono messo nella posizione
  standard; per gli altri video va fatta la calibrazione del video.
- Il rilevatore di colore puo' confondersi con oggetti gialli IN MOVIMENTO
  (magliette lime, racchette gialle come quella di Alcaraz): il giallo fermo
  ora viene ignorato, quello in movimento no; il controllo del punto 7
  nasconde i risultati sbagliati, ma non recupera la misura.
- Con poca luce la pallina colpita e' una striscia mossa: la velocita' subito
  dopo il colpo non si misura bene (resta la direzione, e la stima dal
  rimbalzo quando si vede). Meglio girare con molta luce o a 120/240 fps.
- La velocita' dal rimbalzo e' una stima (+-15%): contatto approssimato
  (piedi del giocatore, altezza fissa), tempo di volo +-1 frame, rotazione
  non nel modello.
- Il classificatore della posa a volte vede un servizio dove il giocatore
  cammina (alcaraz, frame 1302).
- Il servizio in slice o in kick curva di lato: la rotazione non e' nel
  modello, quindi il rimbalzo vero puo' spostarsi rispetto a quello previsto.
- Con il telefono all'altezza standard (circa 2,2 m) tutto il campo lontano
  si vede attraverso la rete, e la fascia bianca in cima alla rete copre una
  striscia di terreno subito dietro la riga di fondo lontana: i rimbalzi li'
  non si vedono, e attraverso le maglie TrackNet perde spesso la pallina.
  Esempio: alcaraz, rovescio al 1015/1017, rimbalzo e risposta
  dell'avversario dietro la fascia bianca (fotogrammi 1070-1071). Per vedere
  la riga di fondo lontana sopra la rete il telefono dovrebbe stare ad almeno
  circa 2,4 m.
- Da fare: avviso automatico quando le righe del campo non coincidono con la
  calibrazione standard, rilevamento del rimbalzo come vincolo, dimensione
  apparente della pallina come misura di distanza, audio, rotazione nel
  modello, fine-tuning di TrackNet.
