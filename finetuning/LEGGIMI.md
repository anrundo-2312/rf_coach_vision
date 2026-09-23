# Fine-tuning del rilevatore di racchetta

Il modello attuale trova la racchetta in circa 1 frame su 3, confonde l'ombra
della racchetta sul campo con una racchetta vera e dà confidenze basse (0,25-0,40)
anche quando ha ragione. I filtri in `analyze.py` tolgono gli errori, ma non
possono trovare cio' che il modello non vede: per quello serve riaddestrarlo sui
nostri video.

## I passi

1. **Estrazione dei frame** (sul PC, veloce):
   `python finetuning/estrai_frame.py --per-video 45`
   Salva in `finetuning/dataset/images` frame distribuiti su tutta la durata di
   ogni video di `inputs/`, ridimensionati a 1920 px.

2. **Pre-annotazione** (su Colab, serve la GPU): cella apposita in
   `rf_coach_finetune.ipynb`, che lancia `finetuning/preannota.py`.
   Propone un riquadro per la racchetta usando il modello attuale piu' il filtro
   della mano. Serve solo a partire da qualcosa di gia' quasi giusto.

3. **Correzione a mano** (tu, su Roboflow o CVAT). Regole:
   - un riquadro per ogni racchetta visibile, anche quella dell'avversario;
   - le **ombre** restano senza riquadro;
   - il riquadro comprende manico e piatto corde, non il braccio;
   - se la racchetta e' mossa e sfocata, il riquadro la include comunque.

4. **Addestramento** (`rf_coach_finetune.ipynb`): parte da `tennis_yolo11.pt`,
   divide train/validazione **per video** e confronta vecchio e nuovo modello.

5. **Uso**: il modello nuovo viene salvato su Drive come
   `tennis_yolo11_finetuned.pt`; per usarlo nell'analisi basta cambiarne il nome
   in `analyze.py`.

## Quante immagini servono

Con 250-300 frame annotati si vede gia' un miglioramento; per un risultato solido
meglio 500-800, presi da video diversi. Contano piu' la varieta' (giocatori, luce,
ombre, fasi dello swing) che il numero.
