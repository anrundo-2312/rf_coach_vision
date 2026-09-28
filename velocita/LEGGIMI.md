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
  giocatore, dove TrackNet la perde.
- `velocita_uscita.py` - il programma principale: trova i colpi e calcola
  velocita' e direzione.
- `disegna_velocita.py` - riscrive il video con colpo, km/h, direzione e una
  piccola mappa del campo.
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
   si muove.
3. **Contatto.** Cambio brusco della direzione della pallina (3 frame prima
   contro 3 dopo) con la pallina entro 0,6 altezze del giocatore da un polso,
   e pallina che DOPO si allontana veloce. L'ultima condizione scarta il
   rimbalzo della pallina dell'avversario davanti al giocatore, che
   nell'immagine sembra un colpo.
4. **Velocita'.** `exit_speed` sui ~1/3 di secondo dopo il contatto (20 frame
   a 60 fps), con la posizione a terra del giocatore (caviglie della posa,
   nel frame in cui i piedi sono piu' in basso: nel servizio al contatto sono
   in aria), il contatto entro 1 m dal giocatore (`depth_tol`) e la pallina
   diretta verso il campo avversario (`forward`).
5. **Direzione.** Angolo della pallina rispetto alle righe laterali; la
   direzione viene prolungata fino a 21 m (tra riga del servizio e fondo
   lontani) per vedere in che meta' arriva:
   - *lungo linea*: parte da un lato e arriva sulla meta' dello stesso lato;
   - *incrociato*: arriva sulla meta' opposta;
   - *centrale*: arriva entro 1 m dalla riga centrale;
   - *dal centro verso destra/sinistra*: parte dal centro (entro 1 m) e va
     verso un lato.
   Per il servizio la direzione non viene classificata.
6. Se la posa indica un colpo, la pallina arriva al giocatore ma il contatto
   non si vede (pallina coperta dal corpo), il colpo viene scritto lo stesso,
   senza velocita', con una nota.

Tutte le soglie sono in cima al file.

## Precisione da aspettarsi

Dalle simulazioni (camera dietro al giocatore e rialzata, 60 fps, 20 frame
dopo l'impatto, colpi amatoriali da 65-90 km/h):

| | TrackNet preciso (2 px) | meno preciso (4 px) |
|---|---|---|
| velocita' | +-12-20 km/h | +-23-31 km/h |
| angolo della direzione | +-1 grado | +-2-3 gradi |

Sui video veri l'errore della pallina e' 1-4 px. La direzione e' quindi molto
piu' affidabile della velocita' (un incrociato fa 15-20 gradi, un lungo linea
0-5). La rotazione (topspin, slice) non e' nel modello: con il topspin la
velocita' esce sottostimata di circa 12 km/h. Il valore va sempre mostrato
con il suo margine.

## Provato su

| Video | Colpo | Contatto | Uscita | Direzione |
|---|---|---|---|---|
| nicola_matarese_trim | servizio | frame 15 | 116 km/h | - |
| nicola_matarese_trim | rovescio | frame 223 | non disponibile (pallina coperta) | - |
| zverev_djokovic_trim_swin_like | dritto | frame 65 | 123 km/h | centrale |
| zverev_djokovic_trim_swin_like | rovescio | frame 217 | 114 km/h | centrale |

Il video di Nicola e' registrato con SwingVision, che per il servizio indica
83 km/h: pero' SwingVision mostra la velocita' MEDIA del volo, non quella di
uscita (la nostra media fino al rimbalzo e' ~90-98 km/h), e il rimbalzo che
calcoliamo cade quasi dove lo mette la sua mappa.

Solo 3 colpi misurati: le soglie vanno verificate su altri video.

## Limiti e prossimi passi

- Colpi in cui la pallina passa dietro il corpo del giocatore subito dopo il
  contatto: niente velocita' ne' direzione.
- La calibrazione standard vale solo con il telefono messo nella posizione
  standard; per gli altri video va fatta la calibrazione del video.
- Il rilevatore di colore puo' confondersi con oggetti dello stesso colore
  (magliette lime, scritte).
- Da fare: avviso automatico quando le righe del campo non coincidono con la
  calibrazione standard, direzione del servizio (al T / al corpo / esterno),
  rilevamento del rimbalzo come vincolo, dimensione apparente della pallina
  come misura di distanza, audio, rotazione nel modello, fine-tuning di
  TrackNet.
