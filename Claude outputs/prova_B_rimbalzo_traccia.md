# Prova B: il rimbalzo legato alla traccia della pallina del colpo

Prova solo nel cloud, sul codice del PC (commit 616406d). **Nessun file del PC è stato modificato.** Cambia solo `velocita_rimbalzo.py`; `velocita_uscita.py` e `direzione_nascosta.py` restano identici, quindi l'A/B riesegue solo il passo del rimbalzo a partire dal JSON scritto da `direzione_nascosta.py`, controllato uguale alla catena completa.

## 0. In breve

- **Risultato sui 7 video:** 5 identici (Nicola, Djokovic, swing_vision, alcaraz, test_tennis_1); 3 righe cambiano, tutte e tre nel verso giusto, controllate a occhio.
  - Giorgio 39,7 s: i punti scritti sono solo della pallina colpita (l'errore di identità della validazione è sparito).
  - video_alcaraz_palline_sparse 13,3 s: il rimbalzo sulla pallina ferma non c'è più. Al suo posto non c'è niente: la riga resta «solo direzione», senza km/h.
  - Giorgio 14,0 s: il rimbalzo passa dal frame 451 al 452, il punto più basso in cui la pallina si vede, e arriva una stima di 84 km/h.
- **Nessun risultato nuovo sbagliato.** Una versione intermedia ne creava uno (alcaraz 16,9 s, un «rimbalzo ricostruito» che era il colpo dell'avversario): è il motivo della terza regola qui sotto.
- **Costo:** il passo del rimbalzo dura il 40% in più (Giorgio 111 → 164 s, palline_sparse 89 → 126 s); sulla catena completa è circa il 6%.
- **Non risolve:** Giorgio 60,2 s (rimbalzo dentro un buco di TrackNet: serve il punto ricostruito, prova AP) e i colpi persi dalla posa.

## 1. Cosa fa B (versione finale)

Tre regole in `velocita_rimbalzo.py`, ognuna con la sua costante per spegnerla.

1. **La traccia della pallina del colpo** (`traccia_del_colpo`, `TRACCIA_DEL_COLPO`). I punti di TrackNet filtrati attorno al colpo si dividono in tracce coerenti (`tracce`, la stessa funzione di `direzione_nascosta.py`: salto massimo 0,08 altezze dell'immagine per fotogramma, buchi fino a 0,75 s). Si prende la traccia che contiene più punti del colpo (`_punti` scritti da `velocita_uscita.py` o `direzione_nascosta.py`: stesso fotogramma, posizione entro 0,1 altezze del giocatore). Tutti i passi (1-3, 4, 5, 6 e `PUNTO4`) cercano il rimbalzo **solo su quella traccia**, e i `_punti` scritti con la stima vengono da lì. Se il colpo non ha `_punti` o nessuna traccia li contiene: tutti i punti, come prima.
2. **Palline ferme nel colore** (`COLORE_FERME`). Nel passo 4 una macchia gialla trovata in un buco si prende come prima se sta sulla strada prevista dagli ultimi due punti (entro 12 px + 4 px per fotogramma di buco, a 1080p). Se è fuori strada si guarda il fotogramma di 0,4 s prima: se lì c'era già una macchia nello stesso punto, è una pallina ferma e si scarta (la pallina in volo in quell'istante era altrove). Serve perché la maschera del giallo fermo non vede le palline attraverso le maglie della rete (nella mediana il loro colore è fuori soglia).
3. **Rimbalzo ricostruito solo se la pallina continua** (`RIC_VELOCITA_MIN`). Nel passo 5 le due curve prima e dopo il buco valgono solo se dopo il buco la pallina va almeno 0,3 volte la velocità di prima (nell'immagine): dopo un rimbalzo la velocità resta simile, dopo un colpo dell'avversario no.

## 2. Come ci sono arrivato

| Versione | Cosa cambiava | Risultato | Perché scartata |
|---|---|---|---|
| B (prima) | traccia + nel colore il punto deve stare vicino alla posizione prevista | perdeva alcaraz 418 (rimbalzo giusto al 470: dopo il rimbalzo la pallina risale e la previsione va dall'altra parte; su alcaraz i fotogrammi ripetuti danno velocità zero) e non recuperava sparse 800; inventava alcaraz 1015 | una previsione da due punti non distingue "pallina ferma" da "pallina che ha appena rimbalzato" |
| solo traccia | traccia, colore vecchio | sparse 800 restava sulla pallina ferma (la aggiunge il colore, non TrackNet); alcaraz 1015: rimbalzo ricostruito falso al 1061, 184 km/h, fuori (è il colpo dell'avversario ai piedi; prima lo evitava per caso, un punto di un'altra pallina rompeva la "discesa") | manca la guardia del passo 5 |
| solo colore con previsione | colore con cancello sulla previsione | perdeva alcaraz 418, toglieva sparse 800 | come sopra |
| **B finale** | traccia + macchia ferma 0,4 s prima + guardia del passo 5 | vedi punto 3 | – |

## 3. A/B sui 7 video (passo del rimbalzo, base = codice del PC)

| Video | Righe | Esito |
|---|---|---|
| nicola, zverev_djokovic, test_tennis_1, alcaraz, swing_vision | 2, 2, 2, 10, 4 | **identici** (JSON compresi i rimbalzi 470 colore e 767 ricostruito di alcaraz) |
| Giorgio | 14 | 2 righe cambiano: 422 e 1191 |
| video_alcaraz_palline_sparse | 13 | 1 riga cambia: 800 |

**Giorgio 1191 (39,7 s).** Rimbalzo 1218 uguale. I `_punti` scritti passano da 26 (6 su palline ferme alla rete) a 18, tutti sulla pallina colpita (frame 1193-1218, x 1110-1125; controllati nella scheda). Velocità stimata 104 → 108 km/h e media 84 → 87: la partenza laterale del volo (`punto_di_partenza`, primi 1/6 s) ora si calcola dalla pallina giusta.

**Giorgio 422 (14,0 s).** Prima: rimbalzo al 451 visto da TrackNet, (10,5; 21,3) m, fuori di 0,94 m di lato, nessuna velocità. Il 451 passava il controllo «scende poi risale» grazie ai punti delle palline ferme ai frame 452-453 (dopo il 451 TrackNet perde la pallina per 10 fotogrammi). Sulla traccia della pallina quei punti non ci sono, il 451 non passa, e il colore trova la pallina al 452 un po' più in basso (y 573 → 588): è il punto più basso in cui si vede, ai frame 453-455 sta già risalendo (controllato fotogramma per fotogramma). Ora: rimbalzo al 452, (10,0; 18,1) m, fuori di 0,43 m, stima 84 km/h (volo 1,0 s). Di lato resta fuori, nel corridoio del doppio. In profondità 3,2 m di differenza per un fotogramma: a quella distanza, con la camera a 1,7 m, un fotogramma di discesa vale 15 px e 3 m. Nessuno dei due numeri è "il rimbalzo vero": il 452 è il più vicino che i dati permettono.

<!-- figura: fig_giorgio_422_B.jpg | Giorgio, frame 447-462: TrackNet (rosso) vede la pallina scendere fino al 451, il colore (arancione) la trova al 452, dal 453 risale. Prima il rimbalzo era al 451, ora al 452. -->

**video_alcaraz_palline_sparse 800 (13,3 s).** Prima: rimbalzo «colore» al 855 su una pallina ferma, 139 km/h, (6,7; 22,1) m dentro. Ora la macchia ferma viene riconosciuta (c'era già 0,4 s prima) e scartata; il passo 5 prova il rimbalzo ricostruito sul buco 847-857 ma le due curve si incontrano a 30 px (a 1080p), oltre i 20 ammessi, e non scrive niente. La riga resta «pallina mossa al colpo: solo direzione», centrale, senza km/h e senza rimbalzo. Si perde un numero che era sbagliato di circa 10 km/h e 0,6 m.

**alcaraz 1015 (16,9 s), il caso evitato.** Con la sola traccia il passo 5 trovava un buco pulito (1052-1069) con la pallina che scende prima e "risale" dopo: ma dopo è il colpo dell'avversario ai piedi, non un rimbalzo (velocità prima 9,9 px/frame, dopo 2,1: rapporto 0,21). Prima del rimbalzo vero (alcaraz 709: 5,0 → 4,5, rapporto 0,9). La guardia a 0,3 lo scarta; sui 7 video non toglie nessun rimbalzo ricostruito giusto (709 e sparse 1722 restano).

## 4. Costo

Passo del rimbalzo, un video alla volta: Giorgio 111 → 164 s, palline_sparse 89 → 126 s (+40%). Quasi tutto il tempo in più è nei salti a un fotogramma precedente per il controllo delle macchie ferme (`cap.set`, circa 0,4 s l'uno su HEVC): 146 salti in più su Giorgio. Sulla catena completa (Giorgio circa 750 s) è circa il 6%. Si può ridurre leggendo i fotogrammi in fila invece di saltare, se servirà.

## 5. Cosa resta fuori

- **Giorgio 1806 (60,2 s):** invariato. Il rimbalzo cade nel buco 1844-1847 e la riga lo mette al 1843, fuori lungo; serve il punto ricostruito nel buco (prova AP del 6 ottobre: 25,2 → 20,2 m).
- **sparse 800:** nessuna stima. Il rimbalzo ricostruito fallisce per 10 px; abbassare la soglia non è una cosa da fare per un caso solo.
- I colpi senza riga (swing_vision, test_tennis_1, Giorgio 24,7 s) e le righe false: non c'entrano con il rimbalzo.

## 6. Decisione

Opzioni, senza spingere:

- **Adottare B.** Toglie i due errori di identità visti, non ne introduce, costa il 6% in più. In cambio una stima (sbagliata) sparisce e un rimbalzo si sposta di un fotogramma. Se si adotta: LEGGIMI e COME_FUNZIONA (nuovo 8.19, scartati → 8.20), A/B conservato, commit separato da A+F+DT.
- **Aspettare il video del test cesto** e riprovare B lì prima di adottarla: è il caso d'uso per cui nasce e nessuno dei 7 video ha palline ferme vicino all'impatto.
- **Adottare solo le regole 1 e 3** (traccia e guardia), lasciando il colore com'è: sui 7 video darebbe gli stessi risultati di B tranne sparse 800, che resterebbe sulla pallina ferma. Costo quasi zero.

File della prova: `patch_traccia_rimbalzo.py` (applicata alla copia del PC), `code_B4/velocita_rimbalzo.py` nel cloud.
