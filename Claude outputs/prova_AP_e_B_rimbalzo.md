# Prova AP e B+AP: il punto del rimbalzo nel buco di TrackNet

Prova solo nel cloud, sul codice che ora è sul PC (`velocita_rimbalzo.py` con la palla corta dalla serie, P2, non ancora pushato). **Nessun file del PC è stato modificato.** Cambia solo `velocita_rimbalzo.py`: l'A/B riesegue il passo del rimbalzo sui 7 video a partire dal JSON scritto da `direzione_nascosta.py`, come nella prova B.

## 0. In breve

- **Base = codice del PC (P2):** sui 7 video dà gli stessi risultati del codice su GitHub (A+F+DT): la palla corta dalla serie non tocca nessuna riga di questi video.
- **AP da sola:** 5 righe cambiano, su 21 rimbalzi "tracknet". Sono esattamente i 5 rimbalzi che stanno accanto a un buco di TrackNet; gli altri 16 non hanno buchi e restano uguali. In tutti e 5 i casi, controllati fotogramma per fotogramma, la pallina tocca terra **dentro** il buco (nascosta dalla rete o dal nastro) e il punto che prima si prendeva era già in aria, dopo il rimbalzo. Il fotogramma ricostruito coincide con il punto più basso che si vede (±1 fotogramma).
- **B da sola:** identica alla prova B di ieri (Giorgio 422 e 1191, sparse 800). Il passo 6b (palla corta) non la disturba.
- **B+AP:** esattamente la somma delle due, 8 righe su 51; nessuna interazione, nessun risultato nuovo sbagliato. AP sulla traccia della pallina del colpo (come B) dà gli stessi 5 punti.
- **Velocità:** AP non cambia nessun km/h (per costruzione). B cambia Giorgio 1191 (104 → 108) e aggiunge Giorgio 422 (84), toglie sparse 800 (139, era su una pallina ferma).
- **Costo:** AP è gratis (qualche curva in più). B resta +40% sul passo del rimbalzo (circa +6% sulla catena completa), misurato ieri.

## 1. Cosa cambia con AP, riga per riga

| Video | Riga | Buco di TrackNet | Rimbalzo prima (in aria) | Rimbalzo con AP (nel buco) | Dentro/fuori |
|---|---|---|---|---|---|
| Giorgio | 1806 (60,2 s) | 1844-1847, dietro la rete | frame 1843, (3,0; 25,2) m | frame 1845, (3,2; 20,2) m | **fuori → dentro** |
| alcaraz | 867 (14,4 s) | 919-923, dietro il nastro | frame 924, (6,7; 23,1) m, profonda | frame 921, (6,5; 21,2) m, media | dentro |
| sparse | 181 (3,0 s) | 243-247, dietro la rete | frame 248, (5,6; 22,4) m, profonda | frame 246, (5,6; 20,1) m, media | dentro |
| sparse | 1097 (18,3 s) | 1138-1142, dietro la rete | frame 1143, (5,8; 21,5) m | frame 1141, (5,8; 19,0) m | dentro |
| sparse | 1384 (23,1 s) | 1431-1435, dietro il nastro | frame 1430, (6,6; 20,5) m | frame 1433, (6,5; 18,4) m | dentro |

La correzione va sempre nello stesso verso (più corto) e il perché è geometrico: la camera è dietro il giocatore, un punto in aria portato a terra cade più lungo del vero. Quanto più corto (2-5 m) lo dicono le due curve, non un dato misurato: non c'è una verità a terra per nessuno dei 5. Nella riga resta scritto che il punto è ricostruito (`rimbalzo_trovato_come = ricostruito`, e la nota dice tra quali frame TrackNet ha perso la pallina); nel video e nel riepilogo il cerchio è vuoto, come per i rimbalzi coperti del passo 5.

<!-- figura: giorgio_1806_buco.jpg | Giorgio, frame 1840-1851 (rosso = TrackNet, "-" = buco). La pallina passa dietro la rete, è più bassa al 1845-1846 e dal 1847 risale: il rimbalzo è nel buco. Il 1843, che prima faceva da rimbalzo, è ancora in discesa. -->

<!-- figura: alcaraz_867_buco.jpg | alcaraz, frame 916-927. Dietro il nastro al 919-923, punto più basso al 921-922, dal 924 risale (TrackNet la ritrova lì). -->

<!-- figura: sparse_181_buco.jpg | palline_sparse, frame 241-252. Dietro la rete al 243-247, più bassa al 245-246, al 248 è già sopra il nastro. -->

<!-- figura: sparse_1097_buco.jpg | palline_sparse, frame 1136-1147. Stesso schema: più bassa al 1140-1141, al 1143 risale. -->

<!-- figura: sparse_1384_buco.jpg | palline_sparse, frame 1426-1437. Scende fino al 1431, sparisce dietro il nastro al 1432-1435, al 1436 risale. Le due macchie gialle in basso sono palline ferme oltre la rete, non c'entrano. -->

## 2. A/B sui 7 video (passo del rimbalzo)

| Variante | nicola, djokovic, tt1, swing | alcaraz (10) | Giorgio (14) | sparse (13) |
|---|---|---|---|---|
| PC (P2) vs GitHub | identici | identico | identico | identico |
| AP | identici | 867 | 1806 | 181, 1097, 1384 |
| B | identici | identico | 422, 1191 | 800 |
| B+AP | identici | 867 | 422, 1191, 1806 | 181, 800, 1097, 1384 |

B+AP = B ∪ AP, riga per riga, con gli stessi numeri delle prove singole.

## 3. Cosa resta fuori

- Nessuna verità a terra per i 5 punti ricostruiti: si sa che il punto vecchio era in aria, non di quanto il nuovo sia giusto.
- AP interviene solo sui rimbalzi "tracknet" accanto a un buco più lungo di 0,067 s (2 frame a 30 fps, 4 a 60): un buco più corto non si corregge.
- I colpi senza riga e le righe false non c'entrano (posa/contatto).

## 4. Se si adotta

Entrambe su `velocita_rimbalzo.py` del PC (sopra P2), ognuna con la sua costante per spegnerla (`TRACCIA_DEL_COLPO`, `COLORE_FERME`, `RIC_VELOCITA_MIN`; `PUNTO_NEL_BUCO`). LEGGIMI e COME_FUNZIONA aggiornati per quello che si adotta, commit separato da P2.

File della prova: `patch_traccia_rimbalzo_P2.py`, `patch_punto_ricostruito.py`, `code_BAP/velocita_rimbalzo.py` nel cloud.
