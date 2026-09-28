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
  su un fotogramma.
- `palla_locale.py` - rilevatore della pallina per colore, attorno al
  giocatore, dove TrackNet la perde.
- `velocita_uscita.py` - il programma principale: trova i colpi e calcola
  velocita' e direzione.
- `disegna_velocita.py` - riscrive il video con colpo, km/h, direzione e una
  piccola mappa del campo.
- `calibrazioni/` - una calibrazione per video: `<video>.json` e
  `<video>_campo.jpg`, l'immagine di controllo (resta sul PC). Il JSON viene
  copiato anche su Drive in `rf_coach_vision/calibrazioni/`, da dove lo prende
  Colab.

## Come si usa

### Su Colab (consigliato: l'analisi su CPU e' lenta)

Nel notebook `colab/rf_coach_colab.ipynb` le celle 6 (analisi) e 7 (colpi)
come sempre, poi la 7b (velocita' e direzione), la 8 (salvataggio su Drive) e
la 9 (anteprima). L'unico passo da fare sul PC e' la calibrazione del campo,
che e' interattiva ma leggera (apre un solo fotogramma): si puo' fare mentre
Colab fa l'analisi, anche con il video solo su Drive:

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

Poi, una volta per ogni posizione della camera, la calibrazione del campo:

```
python velocita/calibra_campo.py inputs/<video>.mp4
```

E infine velocita', direzione e video:

```
python velocita/velocita_uscita.py --video inputs/<video>.mp4
python velocita/disegna_velocita.py --video inputs/<video>.mp4
```

Risultati: `outputs/dati/<video>_velocita.csv` (un colpo per riga) e
`outputs/video/<video>_velocita.mp4`.

### Calibrazione del campo

Si apre un fotogramma: in alto c'e' scritto quale punto cliccare, lo schema
in basso a sinistra mostra dov'e' sul campo, la lente in alto ingrandisce
attorno al mouse. Tasti: clic = segna, S = non visibile, U = annulla,
frecce o IJKL = sposta di un pixel l'ultimo punto, `,` e `.` = fotogramma
precedente/successivo (se il giocatore copre le righe), F = fine, Esc = esci.

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
- La calibrazione va fatta per ogni posizione della camera.
- Il rilevatore di colore puo' confondersi con oggetti dello stesso colore
  (magliette lime, scritte).
- Da fare: direzione del servizio (al T / al corpo / esterno), rilevamento
  del rimbalzo come vincolo, dimensione apparente della pallina come misura
  di distanza, audio, rotazione nel modello, fine-tuning di TrackNet.
