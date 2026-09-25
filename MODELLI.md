# Modelli usati da rf_coach_vision

La pipeline usa quattro modelli. Tre sono preaddestrati e li usiamo cosi'
come sono; il quarto, il classificatore dei colpi, l'abbiamo addestrato noi.

## I quattro modelli

| File | Cosa riconosce | Da dove viene | Dove sta |
|---|---|---|---|
| `yolo11n-pose.pt` | posa del giocatore (17 punti del corpo) | preaddestrato da Ultralytics, usato cosi' com'e' | cartella principale; su Drive in `models/` |
| `tennis_yolo11.pt` | racchetta | preaddestrato, scaricato gia' pronto | cartella principale; su Drive in `models/` |
| `TrackNet_best.pt` + `InpaintNet_best.pt` | pallina (InpaintNet ricostruisce i tratti di traiettoria mancanti) | preaddestrati: pesi pubblici di TrackNetV3, fatti sul badminton | `tracknet3/ckpts/`; su Drive in `ckpts/` |
| `modello_colpi.joblib` | dritto / rovescio / servizio / attesa | **addestrato da noi** con `classificazione/addestra_colpi.py` | `classificazione/` |

I pesi `.pt` sono esclusi da GitHub perche' troppo grandi e stanno su Drive.
`modello_colpi.joblib` invece pesa circa 1,2 MB e si rigenera in pochi secondi.

## Il classificatore dei colpi

Non ha un nome proprio: e' un `HistGradientBoostingClassifier` di
scikit-learn, cioe' un insieme di alberi decisionali, non una rete neurale.

Non guarda l'immagine: usa i 17 punti del corpo trovati da yolo11n-pose,
normalizzati sul riquadro del giocatore e trasformati in 51 numeri (x, y e
visibilita' di ogni punto, vedi `classificazione/caratteristiche.py`). Per
questo si addestra in pochi secondi anche senza GPU.

## Perche' serve il dataset

Il classificatore non era preaddestrato. Non avevamo un classificatore dei
colpi pronto da scaricare, ma c'era un dataset pubblico con le pose di
tennisti gia' etichettate come dritto, rovescio, servizio e attesa. Da quello
abbiamo creato il nostro modello.

- Dataset: "Tennis Player Actions Dataset for Human Pose Estimation"
  (Mendeley Data, DOI 10.17632/nv3rpsxhhk, licenza CC BY 4.0).
- Su Drive: `datasets/tennis_actions/Tennis Player Actions Dataset for Human Pose Estimation/`.

Il dataset serve solo a creare il modello. Una volta che
`modello_colpi.joblib` esiste, per analizzare nuovi video non serve piu'.
Serve di nuovo solo per riaddestrare, per esempio aggiungendo colpi
etichettati dai nostri video.

Sul peso: dei circa 527 MB del dataset quasi tutto sono immagini, che
l'addestramento non usa mai. Servono solo le annotazioni, cioe' 4 file JSON
da circa 300 KB l'uno (`forehand.json`, `backhand.json`, `serve.json`,
`ready_position.json`) nella cartella `annotations`. Per averle in locale
basta copiare quella cartella.

## Come riaddestrare

```
pip install scikit-learn joblib
python classificazione/addestra_colpi.py --annotazioni "G:\Il mio Drive\rf_coach_vision\datasets\tennis_actions\Tennis Player Actions Dataset for Human Pose Estimation\annotations"
```

Senza `--classi` addestra tutte e quattro le classi; con
`--classi dritto rovescio` solo i due colpi. Il modello nuovo sovrascrive
`classificazione/modello_colpi.joblib`.
