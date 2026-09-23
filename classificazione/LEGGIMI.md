# Classificazione dei colpi

Riconosce dritto, rovescio, servizio e posizione di attesa dalla posa del
giocatore, un frame alla volta.

## Dati

Dataset pubblico "Tennis Player Actions Dataset" (Mendeley Data,
DOI 10.17632/nv3rpsxhhk, licenza CC BY 4.0): 2000 immagini, 500 per classe,
camera **dietro il giocatore** a circa 6,4 m dalla linea di fondo, con i
keypoint gia' annotati in formato COCO (18 punti: i 17 standard piu' il collo,
che noi ignoriamo). Serve solo la cartella `annotations`, non le immagini.

## Come si usa

```
pip install scikit-learn joblib
python classificazione/addestra_colpi.py --annotazioni <cartella>/annotations
python classificazione/classifica_tracking.py --tracking outputs/<video>_tracking.csv
```

## Cosa aspettarsi

In validazione (divisione a blocchi, non casuale) l'accuratezza sulle quattro
classi e' intorno al 97%, e dritto contro rovescio da solo sfiora il 99%.
Sono numeri del dataset pubblico: sulla nostra inquadratura, piu' bassa e piu'
vicina, vanno verificati sui video nostri.

Limite di fondo: il modello guarda un frame alla volta e non sa **quando**
avviene l'impatto. Per quello serve incrociare la traiettoria della pallina
(colonne `pallina_*` del tracking CSV) con questi tratti.
