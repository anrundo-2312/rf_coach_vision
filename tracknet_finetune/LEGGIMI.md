# tracknet_finetune: fine-tuning di TrackNet sul tennis

TrackNet (la rete che trova la pallina, `tracknet3/`) oggi usa i pesi
`TrackNet_best.pt`, addestrati sul **badminton**. Sbaglia di più proprio dove
servirebbe: la pallina **mossa** (una striscia) vicino al colpo e la pallina che
arriva lungo la linea di vista; a volte prende righe del campo e palline ferme.

Qui la si **riaddestra un po'** (fine-tuning) partendo da quei pesi, con le
palline da tennis del dataset pubblico del primo TrackNet (2019), e le si dà
un **voto** prima/dopo su un set di test etichettato a mano con i nostri video.

**Il programma non cambia** finché non decidiamo di integrare: questa cartella
contiene solo file nuovi. (Da non confondere con `finetuning_racchetta/`, che riguarda il
rilevatore della racchetta.)

## I file

| File | Dove gira | Cosa fa |
|---|---|---|
| `scegli_frame_test.py` | PC | sceglie i fotogrammi del set di test (attorno ai colpi + qualcuno a caso) e li estrae come immagini |
| `etichetta_pallina.py` | PC | finestra per segnare a mano la pallina in quei fotogrammi |
| `finetune_tracknet_colab.ipynb` | Colab (GPU) | tutto il resto, cella per cella: dataset, prova, addestramento, voto |
| `prepara_dataset_tennis.py` | Colab | converte il dataset pubblico nel formato di TrackNetV3 (ne prende una parte) |
| `addestra.py` | Colab | il fine-tuning, con il codice originale di TrackNetV3 |
| `valuta_tracknet.py` | Colab | il voto sul set di test: confronta pesi diversi sugli stessi fotogrammi |
| `sguardo_veloce.py` | Colab | sguardo veloce senza etichette: pesi del badminton contro pesi nuovi sui nostri video (non è il voto) |
| `scegli_tratti_addestramento.py` | PC | sceglie i tratti continui attorno ai colpi dei NOSTRI video (addestramento) e li estrae come immagini, con i suggerimenti |
| `prepara_dataset_nostro.py` | PC | converte le nostre etichette di addestramento nel formato di TrackNetV3 e mette il tar su Drive |
| `addestramento/lista_frame.csv`, `addestramento/etichette_addestramento.csv` | | i tratti di addestramento e le loro etichette (le immagini in `addestramento/fotogrammi/` no) |
| `test/lista_frame.csv`, `test/etichette_test.csv` | | il set di test (vanno su GitHub; le immagini in `test/fotogrammi/` no) |

## Passi

### 1. Scegliere i fotogrammi del set di test (PC, una volta sola)

    python tracknet_finetune/scegli_frame_test.py

Video del test (mai usati per addestrare): `nicola_matarese_trim`,
`zverev_djokovic_trim_swin_like`, `alcaraz` e il pezzo di `ex.mp4` fra 60 e
150 secondi (al massimo 10 colpi). Per scelta restano fuori
`swing_vision_test1_trim`, `federer_trim` e `test_tennis_1`. Per ogni colpo
trovato dal programma (`outputs/dati/<video>_velocita.csv`) prende i
fotogrammi entro ±0,12 s; in più 10 fotogrammi a caso per video (20 per ex)
lontani dai colpi, per contare anche i punti falsi. Con i dati di oggi sono
410 fotogrammi (Alcaraz 160, ex 170, Nicola 40, Djokovic 40). I video e i dati li cerca prima su Drive, poi in `inputs/` e
`outputs/dati/` del progetto.

Scrive `test/lista_frame.csv` e le immagini in `test/fotogrammi/`. Non
riscrive una lista che c'è già (le etichette si riferiscono a quella).

I numeri dei fotogrammi partono da 1, come in `outputs/dati/` (nel CSV di
TrackNet partono da 0).

### 2. Etichettare (PC, circa un'ora; si può fare in più volte)

    python tracknet_finetune/etichetta_pallina.py

Si segna il **centro** della pallina con un clic (la lente ingrandisce). Le regole:

- pallina nitida: il centro della pallina;
- pallina **mossa** (striscia): il centro della striscia, e **M**;
- pallina coperta, fuori dall'immagine o assente: **N** (non visibile);
- le palline **ferme** a terra non contano: solo la pallina in gioco (se c'è
  solo una pallina ferma: N);
- (addestramento, dal 12/10) conta solo la pallina **in aria**: palleggi prima
  del servizio, lancio, colpi, volo, rimbalzi. Pallina in mano o appoggiata
  alla racchetta prima del servizio, o che rotola a terra a fine punto: **N**.
  Come SwingVision, che analizza solo i punti giocati; e nelle lezioni il campo
  è pieno di palline ferme o in mano che la rete non deve trovare;
- dubbio: **S** (incerta: non conta nel voto).

Invio o Spazio confermano; frecce (o IJKL) spostano il punto di 1 pixel; A/D
mostrano il fotogramma prima/dopo; U torna indietro; Esc salva ed esce (la
volta dopo riparte da lì). Tutti i tasti sono in cima al file.

I **suggerimenti** (giallo = TrackNet, azzurro = punti usati dal programma)
sono **spenti** e si accendono con **H**. Restano spenti di proposito: se si
parte dal punto di TrackNet si tende a confermarlo, e il voto di TrackNet
verrebbe gonfiato. Meglio accenderli solo quando non si trova la pallina.

Ogni conferma salva `test/etichette_test.csv` e lo copia su Drive
(`rf_coach_vision/tracknet_finetune/`), da dove lo legge Colab.

### 3. Mandare su GitHub (da PowerShell)

    cd C:\Users\anrun\rfCoach_vision
    git add tracknet_finetune
    git commit -m "Fine-tuning TrackNet: set di test e script"
    git push

Le immagini non vanno su GitHub (`.gitignore`: `*.jpg`, `*.png`, `*.pt`).

### 4. Colab: `finetune_tracknet_colab.ipynb`

Su Colab: File → Apri notebook → GitHub → `anrundo-2312/rf_coach_vision` →
`tracknet_finetune/finetune_tracknet_colab.ipynb` (oppure File → Carica
notebook, dal PC). Runtime con GPU (A100 o T4), poi **Runtime → Esegui tutto**:
servono solo due autorizzazioni di Google (Drive nella cella 2 e, la prima
volta, la copia del dataset nella cella 5).

| Cella | Cosa fa |
|---|---|
| 1-4 | GPU, Drive, codice (il nostro + TrackNetV3 originale), pesi di partenza dal Drive (`ckpts/TrackNet_best.pt`) |
| 4b | **sguardo veloce** (facoltativo, senza etichette): badminton contro pesi nuovi sui nostri video, attorno ai colpi del programma; si salta da solo se i pesi nuovi non ci sono |
| 5 | dataset pubblico: copia `Dataset.zip` nel tuo Drive con l'API di Google, lo scarica e lo scompatta |
| 6 | lo prepara (circa 10.000 fotogrammi di addestramento, partite 9 e 10 per la validazione) e ne salva una copia sul Drive |
| 7 | **prova** di 2-3 minuti: se non riesce il notebook si ferma qui |
| 8 | addestramento (15 epoche): risultati su Drive in `tracknet_finetune/run1/`; se è già finito salta, se era interrotto riprende |
| 9 | grafico della validazione epoca per epoca |
| 10 | **voto** sul set di test: pesi del badminton contro pesi nuovi (prima di etichettare si ferma con un messaggio) |

Se Colab si disconnette: riapri ed "Esegui tutto". Il dataset pronto torna dal
Drive in pochi minuti e la cella 8 riprende dall'ultima epoca salvata.

**Sguardo veloce (cella 4b).** Si può lanciare subito dopo le celle 1-4, prima di
etichettare. Per ogni video del test e per i fotogrammi attorno ai colpi del
programma dice quante volte TrackNet vede la pallina (badminton contro pesi
nuovi), quanti salti sospetti (più di 120 px a 1080p fra fotogrammi
consecutivi) e punti isolati ci sono, e disegna ritagli con i punti
sovrapposti (badminton = cerchio giallo, pesi nuovi = quadrato azzurro). **Non è
il voto**: senza etichette un punto falso conta come "visto". Serve a capire
presto se i pesi nuovi sono chiaramente peggio. Risultati su Drive in
`tracknet_finetune/valutazione/sguardo/`; le previsioni restano in
`valutazione/previsioni/` e la cella 10 le riusa.

Il dataset è il file `Dataset.zip` nella
[cartella condivisa](https://drive.google.com/drive/folders/11r0RUaQHX7I3ANkaYG4jOxXK1OYo01Ut)
(gli altri due file lì non servono). Google ne blocca spesso il download
diretto ("Too many users have viewed or downloaded this file"): per questo la
cella 5 ne fa prima una copia nel tuo Drive (`Il mio Drive/Dataset_tennis_TrackNet.zip`,
fatta dai server di Google, a cui il limite non si applica) e scarica quella.
Se anche la copia non riuscisse: clic destro su `Dataset.zip` → Crea una copia,
e rilancia la cella 5.

## Come leggere il voto (`voto.md`)

Per ogni fotogramma etichettato:

| Esito | Significato |
|---|---|
| TP | pallina visibile, TrackNet la trova entro 15 px (a 1080p) |
| FP1 | pallina visibile, TrackNet indica un'altra cosa (lontano) |
| FN | pallina visibile, TrackNet non indica niente |
| FP2 | pallina non visibile, TrackNet indica qualcosa (riga, pallina ferma, ...) |
| TN | pallina non visibile, TrackNet non indica niente |

- **richiamo** = TP / (TP + FN): quante palline vere trova;
- **precisione** = TP / (TP + FP1 + FP2): quanto ci si può fidare di un punto;
- **F1** = media dei due; **accuratezza** = (TP + TN) / tutti (come TrackNetV3);
- **errore mediano dei TP**: quanto è precisa la posizione quando la trova;
- **richiamo a 8 px**: come il richiamo ma con tolleranza stretta.

Gruppi: tutti; *vicino al colpo* (entro 0,1 s); *pallina mossa*; *a caso*
(lontano dai colpi); ogni video. Per noi contano soprattutto richiamo e F1
**vicino al colpo** e con la **pallina mossa**, senza che crescano i FP2 nel
gruppo *a caso*.

La tolleranza di 15 px a 1080p corrisponde ai 4 px a 512x288 usati da
TrackNetV3. La previsione è fatta come nel programma (`tracknet3/predict.py`,
modalità `weight`) ma **senza InpaintNet**: si misura TrackNet da solo.

## Scelte (e perché)

- **Si parte dai pesi del badminton**, non da zero: la rete sa già trovare un
  oggetto piccolo e veloce, va solo corretta. Passo di Adam 1e-4 (TrackNetV3
  da zero usa 1e-3), 15 epoche, si tiene l'epoca migliore sulla validazione.
- **Stesso modello del programma** (`tracknet3/model.py` è identico
  all'originale; la cella 3 lo controlla): i pesi nuovi si usano cambiando
  solo il file.
- **Dataset pubblico**: visibilità 1 e 2 = visibile (2 è proprio la pallina
  mossa), 0 e 3 = non visibile (3 = coperta, come la nostra regola N). I
  fotogrammi si salvano già a 512x288; lo sfondo (mediana) è per clip, perché
  nelle riprese TV l'inquadratura cambia da una clip all'altra.
- **Divisioni**: addestramento e validazione per **partita** (9 e 10 solo in
  validazione), mai per fotogramma (fotogrammi vicini sono quasi uguali). Il
  **test** sono i nostri video, mai usati per addestrare: è l'unico voto che
  dice se migliora sulla nostra inquadratura.
- **Alcaraz è nel test**, così come i video del confronto A/B: non vanno mai
  nell'addestramento.

## Fonti e licenze

- TrackNetV3, codice di addestramento e modello: <https://github.com/qaz812345/TrackNetV3>,
  licenza MIT, versione `6eda442ada1740573f200f836d93edc9a541ee86`.
- Dataset del tennis (TrackNet 2019: 10 partite, 19.835 fotogrammi 1280x720 a
  30 fps), dal README di <https://github.com/yastrebksv/TrackNet>. Articolo:
  Huang et al., *TrackNet: A Deep Learning Network for Tracking High-speed and
  Tiny Objects in Sports Applications*, 2019. Il README non indica una
  licenza per i dati: uso didattico e di ricerca, citando l'articolo.

## Risultato del voto (8 ottobre 2026)

Set di test: 410 fotogrammi etichettati (365 con pallina visibile, 192 mosse).
Richiamo vicino al colpo: badminton 0,52, run1 0,42, run2 0,38; il criterio
chiedeva +8-10 punti, quindi **i pesi nuovi non si integrano**. Contando i
fotogrammi: vicino al colpo il badminton trova la pallina nel 43% dei casi e
indica un'altra cosa nel 16%; run1 40% e 4%; run2 36% e 5%. Il fine-tuning sul
dataset TV rende la rete prudente (meno punti falsi, piu' palline perse), e
sulle partite in TV migliora: non si trasferisce ai nostri video. Dettagli in
`valutazione/voto.md` e `confronto_*.csv` su Drive.

## Provare pesi nuovi nel programma (senza integrarli)

In `analyze.py` c'e' `TRACKNET_PESI` ("" = pesi del programma): con il percorso
di un altro file `.pt` la pallina viene calcolata con quei pesi e la cache
prende la loro etichetta nel nome (`<video>_ball_weight_run1.csv`). Su Colab,
nel notebook principale, basta `PESI` nella cella 4b: il notebook analizza una
copia del video con il suffisso dei pesi (`nicola_matarese_trim_run1.mp4`, con
la sua calibrazione), cosi' i risultati di oggi restano e si confrontano i due
`_velocita.mp4` e `_velocita.csv`.

## Addestrare con i NOSTRI video (dal 9 ottobre)

Il dataset lo facciamo noi: la rete impara solo da fotogrammi con la pallina
segnata, e per le nostre riprese non li ha fatti nessuno. Servono TRATTI
CONTINUI (TrackNet guarda 8 fotogrammi di fila), non fotogrammi sparsi come
nel test. Per il pilota: circa 30 colpi da 1 secondo (1.800 fotogrammi), da
almeno 3 video o posizioni del telefono diverse.

1. Analizzare il video con il programma (notebook principale, `PESI` vuoto):
   servono `outputs/dati/<video>_velocita.csv` (i colpi) e `_tracking.csv`
   (i suggerimenti). I video del test (nicola, djokovic, alcaraz, ex 60-150 s)
   non si usano mai: lo script li rifiuta.
2. Sul PC, i tratti e le immagini (0,5 s prima e 0,5 s dopo ogni colpo, al
   massimo 10 colpi per video distribuiti lungo il video, piu' 1 tratto a caso):

       python tracknet_finetune/scegli_tratti_addestramento.py --video nome.mp4

   Si rilancia con altri video: le righe gia' fatte restano. I tratti con la
   camera che si muove (piu' di 12 px tra inizio e fine, video girati a mano)
   non vengono proposti: si passa ad altri colpi o ad altri tratti a caso
   (`--max_spostamento`, `--tieni_mossi` per tenerli). Per avere meno
   fotogrammi con la stessa riduzione per tutti i video, `--percentuale 65`
   accorcia ogni tratto al 65% della durata attorno allo stesso contatto: i
   colpi restano tutti (minimo circa 50% per i video a 30 fps). Oltre ai colpi
   del giocatore vicino (`_velocita.csv`) prende anche quelli dell'avversario
   da `_impatti.csv` (pallina lontana e piccola, il caso piu' difficile):
   tratti `a<frame>`, motivo `colpo_lontano`; `--solo_vicini` per farne a meno.
3. Etichettare, con i suggerimenti accesi e il punto gia' sul suggerimento
   (Invio se e' giusto, clic se no, N se non c'e'; anche i fotogrammi senza
   pallina vanno segnati, insegnano cosa NON e' la pallina):

       python tracknet_finetune/etichetta_pallina.py --cartella tracknet_finetune/addestramento --suggerimenti

   Un fotogramma incerto (S) spezza il tratto in due pezzi: usarlo poco.

   **Un video alla volta, anche da computer diversi.** Con `--per_video` e
   `--uscita` su Drive ogni video ha la sua cartella (lista, immagini, etichette
   `etichette_<video>.csv`): si etichetta un video per volta da qualunque
   computer con Drive, il codice del progetto (git pull) e Python con
   `opencv-python` e `pandas`, e due computer non scrivono mai lo stesso file
   (meglio non aprire la STESSA cartella da due computer insieme). Circa
   200 MB di immagini per video su Drive; sull'altro computer conviene
   rendere la cartella "disponibile offline" prima di iniziare.

       python tracknet_finetune/scegli_tratti_addestramento.py --per_video --uscita "G:\Il mio Drive\rf_coach_vision\tracknet_finetune\addestramento" --video a.mp4 b.mp4
       python tracknet_finetune/etichetta_pallina.py --suggerimenti --cartella "G:\Il mio Drive\rf_coach_vision\tracknet_finetune\addestramento\a"
       python tracknet_finetune/prepara_dataset_nostro.py --cartella "G:\Il mio Drive\rf_coach_vision\tracknet_finetune\addestramento"
4. Convertire (PC, CPU; ogni tratto = una clip, un tratto ogni 4 in
   validazione; il tar va da solo su Drive in `tracknet_finetune/dati_nostri.tar`):

       python tracknet_finetune/prepara_dataset_nostro.py

5. Colab: `finetune_tracknet_run3.ipynb` (su Drive in `tracknet_finetune/`),
   "Esegui tutto" dopo che Drive ha finito di caricare il tar. Fa solo run3:
   scompatta il tar, prova, addestramento (`RUN = "run3"`, `LR = 1e-5`,
   `EPOCHE = 10`, `DATI_RUN = DATI_NOSTRI`), voto sugli stessi 410 fotogrammi
   e lettura del voto con il criterio di sempre, anche senza il video djokovic
   del test (stesso campo di due video di addestramento). Le stesse cose si
   fanno nel notebook generale: cella 6b, poi cella 8 con quelle impostazioni,
   poi cella 10.

## Dopo

1. Se il pilota muove il voto nella direzione giusta: 100-150 colpi
   (6.000-9.000 fotogrammi) e addestramento vero.
2. Se un voto supera il criterio: integrazione (pesi da impostazione gia'
   pronta, poi A/B sui video di riferimento).
