# Validazione A/B dell'identità della pallina (pipeline attuale)

Codice: commit 616406d, lo stesso del PC (md5 controllati su tutti i file di `velocita/`). Nessuna modifica al codice, nessun commit. Catena completa (`velocita_uscita.py` → `direzione_nascosta.py` → `velocita_rimbalzo.py`) eseguita nel cloud sui 7 video di riferimento, a partire da `_tracking.csv` e `_colpi.csv` di Colab. Le verifiche di identità sono fatte a occhio sui fotogrammi veri, con schede di ritagli costruite dai dati di uscita (`_velocita_punti.json`, `_palline_ferme.csv`, `_tracking.csv`); le immagini `_velocita.mp4` non sono state generate: le schede mostrano gli stessi punti con più precisione.

## 0. In breve

- **Identità dei punti usati per il risultato:** 38 righe con punti, controllate una per una: **37 giuste, 1 sbagliata** (Giorgio 39,7 s: 6 punti su 26 sono palline ferme alla rete).
- **Identità del rimbalzo:** 30 rimbalzi trovati: **28 giusti, 1 su una pallina ferma** (video_alcaraz_palline_sparse 13,3 s: la velocità stimata passa da circa 149 a 139 km/h e il punto si sposta di 0,6 m), **1 al fotogramma sbagliato** (Giorgio 60,2 s: il rimbalzo è in un buco di TrackNet, la riga lo mette 3-4 fotogrammi prima e lo dichiara fuori).
- **Test cesto:** non abbiamo un video adatto. Il più vicino è video_alcaraz_palline_sparse (13 colpi ogni 2,2-2,9 s, maestro che alimenta, 2 palline ferme vicino alla rete): tutte le 13 righe ci sono, nessun punto preso dalla pallina del colpo prima o dopo, 1 rimbalzo sbagliato su 12.
- **Le perdite più grandi non sono di identità:** 6 colpi veri senza riga (swing_vision 3, test_tennis_1 2, Giorgio 1) e 1 riga fuori tempo (swing_vision 1377) dipendono dalla posa e dal contatto, non dalla pallina scelta.
- **Il punto 5 è dimostrato:** il legame tra rimbalzo e traccia del colpo oggi non è garantito dal codice, e sui video si vede.

## 1. A/B sui 7 video

Dati per video. "Finestre" = colpi individuati dalla posa (`finestre_colpi`); le altre colonne sono righe di `_velocita.csv`.

| Video | fps | Finestre | Righe | V. misurata | V. rimbalzo | Solo direz. | Senza risult. | Rimbalzi | Scartate |
|---|---|---|---|---|---|---|---|---|---|
| nicola | 60 | 3 | 2 | 1 | 0 | 1 | 0 | 0 | 0 |
| djokovic | 60 | 2 | 2 | 2 | 0 | 0 | 0 | 1 | 0 |
| swing_vision | 60 | 7 | 4 | 1 | 1 | 1 | 1 | 2 | 0 |
| alcaraz | 60 | 10 | 10 | 1 | 6 | 1 | 2 | 7 | 1 |
| test_tennis_1 | 30 | 5 | 2 | 0 | 0 | 0 | 2 | 0 | 2 |
| Giorgio | 30 | 18 | 14 | 2 | 5 | 3 | 4 | 8 | 1 |
| palline_sparse | 60 | 14 | 13 | 10 | 3 | 0 | 0 | 12 | 0 |

**Note per video**

- **Nicola.** Servizio 116 km/h (frame 15); rovescio 223 solo direzione (contatto coperto). Nessuna pallina ferma in campo, filtro mai attivo.
- **Djokovic.** 123 e 114 km/h; un rimbalzo (117) visto da TrackNet ai piedi dell'avversario. Nessuna pallina ferma.
- **swing_vision.** Servizio 302 solo direzione, dritto 412 90 km/h (rimbalzo 468 con il colore), rovescio 553 circa 118 km/h dal rimbalzo. Riga 1377 "contatto non visibile" senza dati. Finestre 666-694, 837-871 e 1020-1035 senza riga.
- **alcaraz.** 8 colpi veri, tutti con direzione; 1 velocità misurata (275) e 6 dal rimbalzo. Righe 246 e 1302 senza dati (non sono colpi).
- **test_tennis_1.** Video 640x360 a 30 fps, giocatore lontano a metà campo, fuori dalle condizioni del programma. Due righe, tutte e due "misura scartata" (errore 30,7 e 21,5 px a 1080p).
- **Giorgio.** 14 righe: 7 con una velocità (2 misurate, 5 dal rimbalzo), 3 solo direzione, 4 senza risultato (3 righe false a 16,5, 32,3 e 35,0 s; una "misura scartata" a 45,7 s). 198 punti di TrackNet su 1362 (14,5%) tolti come palline ferme.
- **video_alcaraz_palline_sparse.** 13 righe, 10 velocità misurate e 3 dal rimbalzo, 12 rimbalzi. Nessun punto tolto come pallina ferma: le palline ferme in questo video sono 2, vicino alla rete sul lato lontano, e TrackNet non le indica mai (le ha prese solo il colore, vedi punto 5).

## 2. Test di identità della pallina

**Metodo.** Per ogni riga con `_punti` ho costruito una scheda di ritagli (fino a 16 fotogrammi: primo, ultimo, quelli segnalati dai controlli automatici, gli altri campionati), con il punto usato cerchiato, più 5 ritagli attorno al rimbalzo trovato (fb−4, fb−2, fb, fb+2, fb+4) con il punto di TrackNet quando c'è. Ho guardato tutte le schede. Regola: **un solo punto su una pallina diversa = FAIL**, anche con km/h plausibili.

Prima delle schede, tre controlli automatici (solo per indirizzare lo sguardo): punti entro 0,04 altezze da una pallina ferma nota (posizioni di `_palline_ferme.csv` più i punti di TrackNet fermi per ±0,5 s), salti > 0,3 altezze tra punti consecutivi, 3 punti fermi di fila. Hanno segnalato 15 righe; alla verifica **13 erano falsi allarmi** (apice della parabola, in cui la pallina quasi non si muove nell'immagine; o una pallina che si ferma DOPO, nello stesso punto dell'immagine dove era passata in volo). Il controllo "stessa traccia coerente tra ultimo punto e rimbalzo" (`direzione_nascosta.tracce`) ha dato "no" in 10 casi, e in 9 era la stessa pallina nascosta dalla rete o dalla testa per più di quanto `tracce` tollera. **Nessun controllo automatico attuale sostituisce l'occhio.**

**Risultato: 38 righe con punti, 37 PASS, 1 FAIL.**

| Video | Righe con punti | PASS | FAIL | Note |
|---|---|---|---|---|
| nicola | 2 | 2 | 0 | |
| djokovic | 2 | 2 | 0 | |
| swing_vision | 3 | 3 | 0 | |
| alcaraz | 8 | 8 | 0 | 275: punti all'apice segnalati "fermi", a occhio è la pallina |
| test_tennis_1 | 0 | – | – | nessuna riga con punti |
| Giorgio | 10 | 9 | **1** | **1191 (39,7 s)**: `_punti` 1192, 1196, 1204, 1206, 1212, 1214 su 2-3 palline ferme alla rete; 1193-1211 e 1213-1218 sulla pallina vera |
| palline_sparse | 13 | 13 | 0 | 656: la pallina passa a ~40 px dalle palline in mano al maestro, non prese |

**Il caso Giorgio 1191.** La riga è "solo direzione" dalla ricerca estesa più il rimbalzo del passo 6 (`PUNTO4`): la velocità (104 km/h) viene dal contatto 1191 e dal rimbalzo 1218, tutti e due giusti. Ma i `_punti` scritti per il colpo sono "tutti i punti di TrackNet filtrati tra contatto e rimbalzo" (`stima_da_contatto_esteso`): TrackNet in quei frame salta tra la pallina vera (x≈1110) e il gruppo di palline ferme alla rete (x≈675-693), che il filtro non toglie perché con più palline vicine il punto non cade a metà tra le macchie. Sul video i cerchi rossi comparirebbero sulle palline ferme. **FAIL di identità con numeri giusti**: proprio il caso che il requisito vuole scoprire.

<!-- figura: fig_giorgio_1191.jpg | Giorgio, riga 1191: i punti usati (rosso). 1192, 1196, 1204, 1206, 1212 sono palline ferme sulla fascia della rete; 1198-1216 è la pallina vera che scende verso il rimbalzo 1218 (arancione). -->

## 3. Test "cesto di palline"

**Non abbiamo un video con queste caratteristiche** (15-20 colpi a 2-2,5 s, palline ferme vicino all'impatto e vicino al rimbalzo). Ho usato i due più vicini e dico cosa coprono e cosa no.

**video_alcaraz_palline_sparse** (13 colpi in 31 s, intervalli 2,2-2,9 s, maestro sul lato lontano che alimenta con le palline in mano, 2 palline ferme vicino alla rete sul lato lontano, nessuna vicino all'impatto):

| Controllo per ogni colpo N | Risultato |
|---|---|
| 1. Esiste la riga giusta | 13/13 (la riga del colpo 2 è al frame 181, 23 frame prima del contatto 204: stesso colpo) |
| 2. `_punti` del colpo N sulla pallina colpita | 13/13 |
| 3. Nessun punto della pallina del colpo N−1 | 13/13 (i punti stanno entro 1/3 s dal contatto o fino al rimbalzo; la pallina precedente è già ferma o raccolta) |
| 4. Nessun punto della pallina preparata per N+1 | 13/13 (le palline del maestro restano in mano; al colpo 656 la pallina passa a ~40 px da esse senza prenderle) |
| 5. `rimbalzo_trovato_frame` è il rimbalzo della pallina N | 11/12 trovati; **800: pallina ferma** (punto 5); 656 nessun rimbalzo (la pallina va lunga, oltre i 26 m di `CAMPO_Y`) |

**Giorgio** (11 colpi veri più uno dubbio, intervalli 2,4-6,7 s, autoalimentazione con la seconda pallina in mano, decine di palline ferme nella fascia della rete):

| Controllo | Risultato |
|---|---|
| 1. Riga | 10/11 colpi veri (manca il rovescio 24,7 s); il colpo dubbio di 46,4 s ha una riga "misura scartata"; **3 righe false** (16,5, 32,3, 35,0 s), senza dati |
| 2. `_punti` sulla pallina colpita | 9/10 (**1191 FAIL**) |
| 3-4. Pallina del colpo prima/dopo | nessun caso: la seconda pallina in mano non entra mai nei `_punti`; al dritto di 8,8 s il colore la seguiva nella ricerca normale, ma quella riga viene poi dalla stima dal rimbalzo, i cui punti sono della pallina vera |
| 5. Rimbalzo | 8 trovati: 7 giusti; **1806 al fotogramma sbagliato** (punto 5) |

**Verdetto del test cesto sui video che abbiamo: FAIL** per la regola stretta (1 identità e 2 rimbalzi su 23 colpi), con questa precisazione: nessun caso di scambio con la pallina del colpo precedente o successivo. Le due condizioni più rischiose del requisito, **palline ferme a 1-2 m dal punto d'impatto** e **ritmo 2-2,5 s con palline a terra nel campo lontano**, non sono coperte da nessuno dei 7 video.

## 4. Test multi-ball A-F sui video che abbiamo

| Test | Video che lo copre | Identità punti | Rimbalzi | Esito | Cosa manca |
|---|---|---|---|---|---|
| **A** 1 in gioco + 0 ferme | nicola, zverev_djokovic, swing_vision, alcaraz | 15/15 PASS | 10/10 giusti | **PASS** (identità). Però swing_vision perde 3 colpi veri su 6 e mette la riga 1377 a 2 s dal colpo vero (1250): problema di posa/contatto | – |
| **B** 1 in gioco + 3 ferme | palline_sparse (2 ferme vicino alla rete lontana) | 13/13 PASS | 11/12, **1 su pallina ferma** | **FAIL** | pallina ferma vicino all'impatto |
| **C** 1 in gioco + 5-10 ferme | Giorgio (15 posti con ≥5 fotogrammi, gruppi di 2-3 alla rete) | 9/10, **1 FAIL** | 7/8, **1 frame sbagliato** | **FAIL** | 60 fps; palline vicine all'impatto |
| **D** passaggio vicino a una ferma | Giorgio 263 (passa a 0,05 h dalla ferma (780,540) ai frame 298-305), palline_sparse 47 (rimbalzo accanto a una ferma alla rete), Giorgio 1191 (attraversa il gruppo alla rete) | 263 PASS, 47 PASS, **1191 FAIL** | 305 e 85 giusti | **FAIL** (1 su 3) | passaggio a pochi pixel con la pallina vera ben visibile |
| **E** coperta/mossa al contatto + ferma vicino al giocatore | Giorgio 346, 422 (contatto non visibile), 547 (seconda pallina in mano); nicola 223; alcaraz 1015 | 5/5 PASS | 451 e 591 giusti | **PASS** parziale | pallina ferma A TERRA ai piedi del giocatore: nessun video |
| **F** colpi consecutivi a 2-2,5 s | palline_sparse (2,2-2,9 s), alcaraz (2,2-2,6 s), swing (1,8-2,3 s) | 24/24 PASS | 20/21, **1 su pallina ferma** (800) | **FAIL** (1 rimbalzo) | palline a terra nel campo lontano a questo ritmo |

## 5. Test del rimbalzo (`velocita_rimbalzo.py`)

**Dal codice.** Il rimbalzo si cerca con `trova_rimbalzo` sui punti di TrackNet filtrati tra il colpo e 1,6 s dopo (passi 1-3 e 6), oppure sulla traccia riempita con il colore (`estendi_col_colore`, passo 4), oppure ricostruito tra due curve (passo 5). In nessuno dei tre casi c'è una verifica che il rimbalzo appartenga alla stessa pallina dei `_punti` del colpo: l'unico legame è `usati` (un rimbalzo non vale per due colpi) e, nei passi 1-3, la risalita `inizio_traiettoria` fino a 25 frame dal colpo. Nel passo 6 e in `PUNTO4` il rimbalzo è semplicemente il primo punto più basso nel campo avversario.

**Sui video, tre casi concreti.**

**(a) video_alcaraz_palline_sparse, rovescio 13,3 s (riga 800): rimbalzo su una pallina ferma.** La pallina colpita scende verso il fondo, passa le gambe del compagno (838-847), TrackNet la perde (848-856), lei rimbalza dietro la fascia della rete attorno al frame 852-853 e risale (857-861, x≈2046). Il passo 4 riempie il buco con il colore: 848 e 850 sono giusti, poi al buco di 4 fotogrammi il raggio di ricerca arriva a 88 px (4K) e prende la **pallina ferma a terra a (2109; 746)**, visibile attraverso la rete in tutti i fotogrammi. Da lì `trova_rimbalzo` legge "scende poi risale" e scrive il rimbalzo al 855. Perché la maschera del giallo fermo non la esclude: nella mediana di 15 fotogrammi il colore di quella pallina, vista attraverso le maglie, è HSV (54; 35; 173), fuori dalle soglie (tinta ≤ 48, saturazione ≥ 70); nel singolo fotogramma la macchia passa (47 pixel gialli). Verificato rieseguendo le stesse funzioni sui fotogrammi. **Effetto:** velocità stimata 139 km/h e rimbalzo (6,7; 22,1) m; con il rimbalzo vero stimato a occhio (frame 853, pixel ≈ (2040; 738)) la stessa formula dà **circa 149 km/h** e (6,4; 22,6) m: 10 km/h e 0,6 m di differenza, dentro al margine dichiarato (±15%) ma per il motivo sbagliato.

<!-- figura: fig_sparse_800.jpg | palline_sparse, frame 855: punti del colpo 800 (rosso), punti aggiunti dal colore (magenta), TrackNet dopo il rimbalzo (verde). I punti 854-855 e il rimbalzo sono sulla pallina ferma a destra, non sulla pallina colpita, che risale a sinistra. -->

<!-- figura: fig_sparse_800_strip.jpg | Gli stessi fotogrammi uno per uno: la pallina colpita (rosso = TrackNet) scende fino al 851, sparisce dietro la fascia, ricompare al 855 e risale. Il cerchio arancione è il rimbalzo scritto nel CSV: una pallina ferma, visibile attraverso la rete in tutti i fotogrammi. -->

**(b) Giorgio, dritto 39,7 s (riga 1191): rimbalzo giusto, punti sbagliati.** Il rimbalzo 1218 è della pallina colpita (controllato fotogramma per fotogramma: scende dal 1208 al 1218 e risale). Ma i `_punti` scritti con la stima (`stima_da_contatto_esteso`) sono tutti i punti filtrati tra 1192 e 1218, 6 dei quali sono le palline ferme alla rete. Il legame contatto-rimbalzo è giusto per caso: `trova_rimbalzo` ha preso il primo minimo valido, che qui era quello vero.

**(c) Giorgio, dritto 60,2 s (riga 1806): rimbalzo al fotogramma sbagliato.** TrackNet vede la pallina fino al 1843, la perde dal 1844 al 1847 (rimbalza dietro la fascia della rete, si vede attraverso le maglie) e la rivede dal 1848 in risalita. `trova_rimbalzo` ammette buchi fino a 10 fotogrammi nella finestra di 5 punti, quindi 1843 risulta "più basso dei 3 prima e dei 2 dopo": rimbalzo al 1843, a (3,0; 25,2) m, **fuori lungo**. Il rimbalzo vero è 3-4 fotogrammi dopo, più in basso nell'immagine, quindi più corto: la prova AP del 6 ottobre lo metteva a 20,2 m, dentro. Stessa pallina, punto sbagliato.

<!-- figura: fig_giorgio_1806.jpg | Giorgio, frame 1839-1853: TrackNet (rosso) vede la pallina fino al 1843, poi la perde mentre scende dietro la fascia della rete (1844-1847, pallina visibile attraverso le maglie) e la rivede in risalita dal 1848. Il rimbalzo scritto è al 1843. -->

**Conclusione del punto 5:** oggi il rimbalzo di un colpo **non è garantito** essere della stessa pallina che ha dato i punti del colpo. Sui 7 video è successo 1 volta su 30 (3,3%); una seconda volta il rimbalzo era giusto ma la traccia scritta no; una terza il rimbalzo era della pallina giusta ma al fotogramma sbagliato.

## 6. Tabelle riassuntive

### Per video

"Colpi veri" = contati a occhio sui fotogrammi (Giorgio e alcaraz dalle liste già verificate nei documenti; swing_vision e test_tennis_1 contati ora). "Riconosciuti" = riga entro 0,5 s dal contatto vero. "Errori identità" = righe con almeno un punto o un rimbalzo su una pallina diversa. "Rimbalzi sbagliati" = su pallina diversa o al fotogramma sbagliato, sui trovati. "Velocità valide" = misurate o stimate, su colpi veri, senza controllo del valore. "Direzioni valide" = direzione scritta su colpi veri, coerente con il rimbalzo visto.

| VIDEO | COLPI VERI | COLPI RICONO-SCIUTI | ERRORI IDENTITÀ | RIMBALZI SBAGLIATI | VELOCITÀ VALIDE | DIREZ. VALIDE | Righe false |
|---|---|---|---|---|---|---|---|
| nicola | 2 | 2 | 0 | 0 su 0 | 1 | 2 | 0 |
| djokovic | 2 | 2 | 0 | 0 su 1 | 2 | 2 | 0 |
| swing_vision | 6 (+1 dubbio ~1030) | 3 | 0 | 0 su 2 | 2 | 3 | 1 (1377, a 2 s dal dritto 1250) |
| alcaraz | 8 | 8 | 0 | 0 su 7 | 7 | 8 | 2 (246, 1302, senza dati) |
| test_tennis_1 | 4 | 2 (senza risultato) | – | – | 0 | 0 | 0 |
| Giorgio | 11 (+1 dubbio 46,4 s) | 10 | **1** (1191) | **1** su 8 (1806) | 7 | 10 | 3 (16,5, 32,3, 35,0 s, senza dati) |
| palline_sparse | 13 | 13 | **1** (800, rimbalzo) | **1** su 12 (800) | 13 (3 troppo alte, già noto) | 13 | 0 |
| **Totale** | **46** | **40** | **2** | **2 su 30** | 32 | 38 | 6 |

### Per test

| TEST | PASS/FAIL | PROBLEMA OSSERVATO | GRAVITÀ |
|---|---|---|---|
| 1. A/B 7 video | eseguito | 6 colpi veri senza riga (posa/contatto), 6 righe false di cui 5 senza dati | media: non è identità, ma pesa più degli errori di identità |
| 2. Identità `_punti` | **FAIL** (37/38) | Giorgio 1191: 6 punti su palline ferme alla rete, scritti come traccia del colpo | bassa sui numeri (km/h giusti), **alta sul requisito** (il video mostra la pallina sbagliata) |
| 3. Cesto | **FAIL** (proxy) | nessun video adatto; sui proxy: 1 identità, 2 rimbalzi su 23 colpi; 0 scambi con la pallina prima/dopo | da ripetere con un video vero |
| 4A. 0 ferme | PASS | – | – |
| 4B. 3 ferme | **FAIL** | rimbalzo su pallina ferma (800) | media: 10 km/h, 0,6 m |
| 4C. 5-10 ferme | **FAIL** | 1191 punti; 1806 frame | media |
| 4D. passaggio vicino | **FAIL** (2/3) | il gruppo alla rete entra nei `_punti` (1191) | media |
| 4E. coperta/mossa | PASS parziale | nessun errore; manca il caso "pallina ferma ai piedi" | – |
| 4F. colpi a 2-2,5 s | **FAIL** (1 rimbalzo) | 800 | media |
| 5. Rimbalzo stessa pallina | **FAIL** | non garantito dal codice; 1 su 30 su pallina ferma, 1 frame sbagliato, 1 traccia sbagliata | **alta**: è il percorso che dà km/h e dentro/fuori ai colpi senza misura |

## 7. Cosa serve davvero, in base ai risultati

Premessa: sui 7 video gli errori di identità sono **rari** (2 colpi su 46) e **piccoli nei numeri** (10 km/h, 0,6 m, un dentro/fuori). I tre casi hanno però la stessa radice: **il rimbalzo e la traccia scritta non sono legati alla pallina del colpo**, e le palline ferme che il filtro non toglie (gruppi alla rete, palline viste attraverso la rete, pallina grande) entrano dal passo 4 e dal passo 6. Le perdite più grandi (6 colpi senza riga, 6 righe false) non c'entrano con la pallina.

| Opzione | Vantaggi | Svantaggi | Complessità | Rischio di regressione | Video che migliorano / peggiorano |
|---|---|---|---|---|---|
| **A) Lasciare così** | Nessun lavoro; 44 colpi su 46 giusti; misure di controllo intatte | I tre errori trovati si ripresenteranno in ogni lezione con palline a terra vicino alla rete o al fondo lontano (è il caso d'uso del progetto); il video può mostrare cerchi rossi su palline ferme | – | nessuno | nessuno / nessuno |
| **B) Legare rimbalzo e traccia** (passi 4 e 6 e `_punti` solo sulla traccia coerente che contiene i punti del colpo; nel colore, candidati solo se continui con la traccia) | Corregge direttamente 800 (il salto di 84 px a una pallina ferma non è continuo con la traccia) e 1191 (i `_punti` scritti sarebbero solo la traccia della pallina vera); `tracce` esiste già in `direzione_nascosta.py`; TC2 del 6 ottobre su 7 video: nessun danno | Non risolve 1806 (buco: serve il punto ricostruito, prova AP) né i colpi persi; una pallina ferma può ancora entrare se è davvero sulla traiettoria (passaggio a pochi pixel) | bassa: funzione esistente, 2-3 punti di `velocita_rimbalzo.py` | basso, verificabile con l'A/B: le righe con velocità misurata non cambiano per costruzione; da controllare che nessun rimbalzo giusto sparisca quando il buco supera 0,5 s (alcaraz 709, sparse 502 hanno buchi lunghi) | migliora: palline_sparse 800, Giorgio 1191 (solo i punti). Rischio: alcaraz 709 e 1152, sparse 502 e 1681, Giorgio 547 e 1806 (rimbalzi dopo un buco lungo), da misurare |
| **C) Candidati multipli di TrackNet** | Affronta la radice (un punto per fotogramma scelto per area); permetterebbe di non perdere la pallina vera quando TrackNet indica una ferma (Giorgio 11,2 s: punto sulla ferma per 15 fotogrammi) | Richiede di rifare TrackNet su tutti i video (20 min per un 4K su CPU) e di modificare `predict.py`, `ball_tracknet.py`, `analyze.py` (nuove colonne) e `segui`; **se la pallina vera non è nella heatmap non aiuta**: su Giorgio 11,2 s TrackNet "non vede mai la pallina vicino al giocatore" (NON VERIFICABILE DAL CODICE quanto spesso sia nella heatmap come seconda macchia) | alta | medio-alto: cambia i punti di ingresso di tutta la catena; le misure di controllo (116/123/114/90) andrebbero riverificate | potenziale su Giorgio (11,2, 14,0, 24,7 s) e sui gruppi alla rete; nessun beneficio misurabile sugli altri 6 video; costo di calcolo per tutti |
| **D) Tracking persistente tra colpi** | Un'identità sola per tutto il video, stato tra un colpo e l'altro, scelta esplicita della pallina colpita | **Nessun caso nei 7 video** lo giustifica: zero scambi con la pallina del colpo prima o dopo; progetto nuovo (associazione, buchi di secondi, palline che escono dal campo) con molte scelte da tarare; TrackNet dà comunque un punto per fotogramma senza C | alta | alto: tocca contatto, direzione e rimbalzo insieme | nessuno dei 7 video mostra il problema che risolve; andrebbe prima provocato con un video cesto vero |
| **E) B + C + D** | Copre tutto | Somma dei costi e dei rischi, senza dati che giustifichino C e D oggi | molto alta | alto | – |

**Lettura dei risultati.** I dati raccolti indicano **B** come l'intervento che risolve quello che si è visto (2 dei 3 casi) al costo più basso e con un A/B già definito; **C** è l'unico che tocca la causa prima ma va misurato su un video con palline ferme vicino al giocatore, perché sui 7 video il suo effetto sarebbe quasi nullo; **D** non ha oggi un caso che lo richieda. Prima di decidere servirebbe il video del test cesto (15-20 colpi, 2-2,5 s, 3 palline ferme a 1-2 m dall'impatto, 3-5 nel campo lontano, 60 fps): è l'unico modo per sapere se D serve.

Nessuna modifica è stata fatta al codice.
