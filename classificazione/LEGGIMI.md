# Classificazione dei colpi

Riconosce il colpo dalla posa del giocatore, un frame alla volta. Le classi
disponibili sono quattro: dritto, rovescio, servizio e posizione di attesa.
Quali usare si sceglie all'addestramento con --classi.

## Dati

Dataset pubblico "Tennis Player Actions Dataset" (Mendeley Data,
DOI 10.17632/nv3rpsxhhk, licenza CC BY 4.0), camera **dietro il giocatore** a
circa 6,4 m dalla linea di fondo, keypoint annotati in formato COCO (18 punti:
i 17 standard piu' il collo, che ignoriamo). Di quel dataset usiamo solo
i quattro file JSON delle annotazioni (500 esempi per classe, 2000 in tutto).
Servono solo le annotazioni, non le immagini.

## Come si usa

```
pip install scikit-learn joblib
python classificazione/addestra_colpi.py --annotazioni <cartella>/annotations
python classificazione/classifica_tracking.py --tracking outputs/<video>_tracking.csv
python classificazione/rileva_impatti.py --tracking outputs/<video>_tracking.csv
python classificazione/metriche_colpi.py --tracking outputs/<video>_tracking.csv
```

Per addestrare solo sui due colpi:

```
python classificazione/addestra_colpi.py --annotazioni <cartella>/annotations --classi dritto rovescio
```

## Cosa aspettarsi

In validazione (divisione a blocchi di frame consecutivi, non casuale):
**97,7%** con tutte e quattro le classi, **99,3%** addestrando solo dritto e
rovescio. Sono numeri del dataset pubblico: sulla nostra inquadratura, piu'
bassa e piu' vicina, vanno verificati sui video nostri.

Quale configurazione scegliere. Con due sole classi il modello distingue
meglio i due colpi, ma non ha modo di dire "non sta colpendo": etichetta come
dritto o rovescio anche i frame di attesa, e la lettura del video risulta
piu' rumorosa. Con quattro classi la separazione dritto/rovescio e'
leggermente meno netta, ma i frame di attesa e i servizi vengono riconosciuti
per quello che sono. Sul video di prova la seconda configurazione ha dato
anche impatti piu' sicuri (0,98 e 0,97 contro 0,95 e 0,89).

In ogni caso il modello guarda un frame alla volta e non sa QUANDO avviene
l'impatto: quello lo trova rileva_impatti.py dalla traiettoria della pallina,
e nel voto sul tipo di colpo la classe "attesa" viene ignorata.

Limite di fondo: il modello guarda un frame alla volta e non sa **quando**
avviene l'impatto. Per quello serve incrociare la traiettoria della pallina
(colonne `pallina_*` del tracking CSV) con questi tratti.
