# Classificazione dei colpi

Riconosce dritto e rovescio dalla posa del giocatore, un frame alla volta.
Le classi servizio e posizione di attesa del dataset non vengono usate.

## Dati

Dataset pubblico "Tennis Player Actions Dataset" (Mendeley Data,
DOI 10.17632/nv3rpsxhhk, licenza CC BY 4.0), camera **dietro il giocatore** a
circa 6,4 m dalla linea di fondo, keypoint annotati in formato COCO (18 punti:
i 17 standard piu' il collo, che ignoriamo). Di quel dataset usiamo solo
`forehand.json` e `backhand.json` (circa 1000 esempi): servizio e posizione di
attesa sono esclusi. Servono solo le annotazioni, non le immagini.

## Come si usa

```
pip install scikit-learn joblib
python classificazione/addestra_colpi.py --annotazioni <cartella>/annotations
python classificazione/classifica_tracking.py --tracking outputs/<video>_tracking.csv
```

## Cosa aspettarsi

In validazione (divisione a blocchi di frame consecutivi, non casuale)
l'accuratezza su dritto contro rovescio e' intorno al 99%. E' un numero del
dataset pubblico: sulla nostra inquadratura, piu' bassa e piu' vicina, va
verificato sui video nostri.

Nota: escludendo la posizione di attesa, il modello ha solo due risposte
possibili e classifichera' come dritto o rovescio ANCHE i frame in cui il
giocatore sta semplicemente aspettando. Per sapere quando avviene davvero un
colpo serve la traiettoria della pallina.

Limite di fondo: il modello guarda un frame alla volta e non sa **quando**
avviene l'impatto. Per quello serve incrociare la traiettoria della pallina
(colonne `pallina_*` del tracking CSV) con questi tratti.
