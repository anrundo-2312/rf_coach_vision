# rf_coach_vision

Prototipo di analisi video per il tennis (stile SwingVision) a scopo didattico:
rilevamento di posa, racchetta e pallina, per arrivare alla classificazione dei
colpi e a metriche utili ai maestri e ai loro allievi.

## Come si usa

```
python analyze.py inputs/<video>.mp4
```

Produce `outputs/video/<video>_combined_<modalita>.mp4` con posa, racchetta e
pallina disegnate, e `outputs/dati/<video>_tracking.csv` con una riga per
frame; stampa frame per frame confidenze e coordinate.

I risultati sono divisi per tipo: in `outputs/video` quelli da guardare, in
`outputs/dati` i CSV su cui si calcola (tracking, colpi, impatti, metriche).

## Componenti

- `analyze.py` - orchestratore: posa (YOLO11n-pose), racchetta (YOLO11 tennis,
  solo classe racket, su un ritaglio attorno al giocatore, con filtro "deve
  toccare la mano" e coerenza temporale), pallina (TrackNetV3).
- `ball_tracknet.py` - wrapper di TrackNetV3, con cache del risultato per video
  e modalita'.
- `tracknet3/` - TrackNetV3 vendorizzato (https://github.com/qaz812345/TrackNetV3,
  licenza MIT) con modifiche minime documentate in testa a `predict.py`.
- `colab/` - `prepara_colab.py` crea lo zip da caricare su Google Drive;
  `rf_coach_colab.ipynb` esegue l'analisi su GPU T4.

## File non presenti nel repository

Pesi dei modelli (`*.pt`), video di input, risultati e cache della pallina:
troppo grandi per GitHub, vanno tenuti su Google Drive. Vedi
`tracknet3/ckpts/LEGGIMI.txt` per i pesi di TrackNet.

## Opzioni principali (in cima ad `analyze.py`)

- `TRACKNET_MODE`: `"weight"` (piu' preciso) o `"nonoverlap"` (piu' veloce).
- `TRACKNET_FORCE_RECOMPUTE`: ricalcola la pallina invece di riusare la cache.
- `RACKET_HAND_MARGIN_RATIO`, `RACKET_MAX_JUMP_RATIO`, `RACKET_MAX_GAP_FRAMES`:
  filtri della racchetta.
