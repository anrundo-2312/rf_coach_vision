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

## Dopo

1. Secondo fine-tuning con i nostri video (ex.mp4 tranne il pezzo del test,
   Giorgio, palline sparse, video nuovi), etichettati con lo stesso strumento:
   serve una lista di fotogrammi di addestramento (tratti continui attorno ai
   colpi) e un convertitore nel formato di TrackNetV3. Voto sempre sugli
   stessi 410 fotogrammi.
2. Se un giorno un voto migliora: integrazione (pesi da impostazione gia'
   pronta, poi A/B sui video di riferimento).
