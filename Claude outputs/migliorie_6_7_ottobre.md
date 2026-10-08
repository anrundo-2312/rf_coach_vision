# Migliorie del 6-7 ottobre

Ogni miglioria ha una sigla che la identifica (R, D2, A, F, DT, P2, B, AP, P1, P3): è il nome con cui compare nel codice, nei documenti e nelle prove.

## 1. Migliorie implementate da ieri a oggi

| Sigla | Cosa fa | Dove | Cosa risolve | Effetto su Boris |
|---|---|---|---|---|
| **R** riga al picco del polso | Nelle finestre della posa più lunghe di 3 s la riga "contatto non visibile" va all'istante in cui il polso è più veloce (lo swing), non alla fine del tratto | GitHub | La scritta cadeva a 5,9 s mentre Boris non colpiva | Dritto 8,8 s: riga al momento giusto, poi circa 66 km/h dal rimbalzo |
| **D2** una sola riga per colpo | La riga della ricerca estesa sostituisce la riga segnaposto della stessa finestra a qualunque distanza | GitHub | Due scritte sullo stesso colpo (palline_sparse 13,3 s) | Nessuno |
| **A** rimbalzo a 3,3 cm da terra | Il punto a terra tiene conto del raggio della pallina | GitHub | Rimbalzi 0,3-0,6 m troppo lunghi | Rimbalzi più corti; 60,2 s direzione centrale → incrociato (sul confine) |
| **F** filtro palline ferme anche per direzione e rimbalzo | I punti di TrackNet su palline ferme si tolgono anche in `direzione_nascosta.py` e `velocita_rimbalzo.py`, fino a 1,6 s dopo ogni colpo | GitHub | Direzione e rimbalzo presi da palline ferme | Dritto 11,5 s: direzione "dal centro verso sinistra"; 18,2 s rimbalzo trovato con il colore nello stesso punto |
| **DT** direzione dalla pallina in uscita | Se il metodo normale non dà la direzione, si prende dalla pallina che esce dal giocatore | GitHub | Primi dritti senza direzione | Dritto 14,0 s: riga a 14,03 s, "lungo linea", rimbalzo fuori di lato |
| **P2** palla corta dalla serie di rimbalzi | Se il primo rimbalzo non si vede, una serie di rimbalzi successivi di una pallina che muore davanti alla riga del servizio dà "palla corta"; colonna `rimbalzi_prima_servizio`; macchina a stati con la fine del colpo data dal colpo dopo | Sul PC, da pushare | Smorzate con il primo rimbalzo nascosto | Nessuno (su Boris non ci sono palle corte vere). Da verificare su un video con smorzate |
| **B** rimbalzo sulla pallina del colpo | Il rimbalzo si cerca solo sulla traccia di TrackNet che contiene i punti della pallina colpita; nel colore si scartano le macchie che c'erano già 0,4 s prima (ferme); rimbalzo ricostruito solo se la pallina continua | Sul PC, da pushare | Rimbalzi e punti presi da altre palline (errori di identità della validazione) | 39,7 s: punti scritti solo sulla pallina giusta (104 → 108 km/h); 14,0 s: rimbalzo al fotogramma dopo e stima 84 km/h |
| **AP** punto del rimbalzo nel buco | Se il rimbalzo visto da TrackNet sta accanto a un buco, il punto per la mappa e il dentro/fuori viene dall'incontro delle curve prima e dopo il buco; i km/h restano | Sul PC, da pushare | Rimbalzo nascosto dalla rete proprio quando tocca terra: il punto visto è in aria e cade più lungo | 60,2 s: fuori lungo → dentro (25,2 → 20,2 m); sugli altri video 4 rimbalzi 2-2,5 m più corti, controllati a occhio |

## 2. Prove nel cloud, in attesa di decisione

| Sigla | Cosa fa | Stato | Effetto su Boris |
|---|---|---|---|
| **P1** colpi falsi | Finestra della posa scartata se dura meno di 0,8 s o il polso non supera 2 altezze/s | Prototipo pronto, GPT non d'accordo per ora | Toglie le 3 righe false (16,5, 32,3, 35,0 s); toglie anche la riga a 45,7 s (colpo dubbio) |
| **P3** incertezza ± | Colonne `incertezza_m` e `al_limite`; fuori di meno dell'incertezza → dentro | Prototipo pronto, GPT non si è espresso | 18,2 s: fuori di 9 cm → dentro |
| **Fine-tuning TrackNet** | Pesi riaddestrati sul tennis (run1 pronto su Drive) | Manca il voto: Andrea deve etichettare i 465 fotogrammi del test | Potenziale sui tratti in cui TrackNet non vede la pallina (11,2 s, 24,7 s): da misurare |

## 3. Boris.mp4 colpo per colpo

12 colpi contati a occhio e con l'audio, 11 veri più uno dubbio.

| Colpo | Oggi nel CSV | Perché manca qualcosa | Cosa lo risolverebbe |
|---|---|---|---|
| Dritto 8,8 s (263) | circa 66 km/h dal rimbalzo, dal centro verso sinistra, dentro, corta | TrackNet non vede la pallina dal 255 al 271 (tutto il colpo); il colore segue la seconda pallina che Boris tiene nella mano sinistra. La stima parte dal frame in cui TrackNet la rivede (9,05 s), quindi è un po' alta (con il contatto vero sarebbe circa 58) | Istante del contatto dall'audio (picco netto a 8,78 s); seconda pallina in tasca, non in mano |
| Dritto 11,2 s (346) | solo direzione (F), nessun rimbalzo | TrackNet non vede mai la pallina vicino al giocatore: punta una pallina ferma alla rete per 15 fotogrammi; la pallina vera è nitida nell'immagine | Candidati multipli di TrackNet (C) solo se la pallina vera è nella heatmap come seconda macchia: NON VERIFICABILE DAL CODICE; fine-tuning TrackNet; audio per il contatto |
| Dritto 14,0 s (422) | direzione lungo linea (DT), rimbalzo fuori di lato di 0,43 m, circa 84 km/h dal rimbalzo (B) | Pallina lasciata cadere e colpita, vista da dietro: sale nell'immagine sia prima sia dopo il colpo, il cambio di direzione è piccolo (1,7 altezze/s contro la soglia 2,5); TrackNet non vede la pallina che cade vicino al corpo. Il rimbalzo è nell'ultimo fotogramma prima di un buco | B (fatto): rimbalzo al fotogramma dopo e stima 84 km/h; audio (14,12 s) |
| Rovescio 18,2 s (547) | 62 km/h misurati, dal centro verso destra, fuori di 9 cm | Il 62 è probabilmente basso: la media del volo (62) non è più bassa dell'uscita; palla alta, 1,45 s di volo, 30 fps. I 9 cm sono dentro l'errore (0,3 m per pixel al fondo) | P3 (nel dubbio dentro); 60 fps; contatto dall'audio |
| **Rovescio 24,7 s (circa 739)** | **nessuna riga** | Due cause, viste oggi sui dati. (1) La traccia parte dal primo punto di TrackNet confermato nella finestra, che è una pallina quasi ferma a bordo campo (1192; 517) non tolta dal filtro: quando TrackNet passa alla pallina vera (frame 698, salto di 350 px) la traccia la perde e muore dopo 8 fotogrammi. Zero punti vicino al polso, quindi nemmeno la riga "contatto non visibile". (2) Al contatto la pallina è nascosta dal corpo per 7 fotogrammi (734-740) e TrackNet in mezzo punta una pallina ferma (738) che il filtro toglie al 737 e al 739 ma non al 738. La ricerca estesa segue la pallina vera con il colore ma trova un contatto falso al 708 (il rimbalzo della pallina in arrivo): 334 km/h, scartato, e per come è scritto il codice non lascia la riga | **Seme sulla pallina in arrivo** (nuova proposta, generale): la traccia deve partire dalla pallina che si muove verso il giocatore, non dal primo punto confermato. Con la traccia giusta la pallina arriva al polso, la riga c'è, `direzione_nascosta.py` ha 20 punti in uscita (741-760) per la direzione e `velocita_rimbalzo.py` il rimbalzo al 769: direzione, rimbalzo e stima dei km/h. Da provare con A/B |
| Dritto 30,1 s (904) | circa 104 km/h dal rimbalzo, centrale, dentro | Il metodo normale non vede il contatto; la direzione viene dalla ricerca estesa e i km/h dalla stima dal rimbalzo | – |
| Dritto 37,0 s (1107) | circa 126 km/h dal rimbalzo, dal centro verso sinistra, dentro | Prima della F mancava del tutto | – |
| Dritto 39,7 s (1191) | circa 108 km/h dal rimbalzo (B), dal centro verso destra, dentro | Prima di B i punti scritti comprendevano 6 palline ferme alla rete (errore di identità della validazione) | B (fatto): 108 km/h, punti giusti |
| "Dritto" 45,7 s (1373) | misura scartata | Non è un colpo: Boris tiene la pallina sulle corde e la spinge piano | P1 toglie la riga |
| Rovescio 49,7 s (1493) | solo direzione, nessun rimbalzo | TrackNet alterna la pallina vera con un'altra pallina in volo vicino alla recinzione; la perde prima del rimbalzo | Nessuna proposta pronta: serve vedere il rimbalzo (telefono più alto) |
| Rovescio 55,6 s (1668) | 56 km/h misurati, dal centro verso destra, dentro | Probabilmente basso (dal rimbalzo verrebbe 72): a 30 fps e con la pallina dietro la schiena il contatto è approssimato | Contatto dall'audio; 60 fps |
| Dritto 60,2 s (1806) | circa 98 km/h dal rimbalzo, incrociato, dentro (AP: punto ricostruito nel buco) | Il rimbalzo cade nel buco 1844-1847 di TrackNet; prima di AP la riga lo metteva al 1843, in aria, un metro e mezzo più lungo (fuori) | AP (fatto): 25,2 → 20,2 m, dentro |
| Righe false 16,5, 32,3, 35,0 s | senza dati | La posa vede un colpo dove Boris è in attesa | P1 |

Riassunto (con B e AP): 11 colpi veri, 10 con la riga, 8 con una velocità (2 misurate ma probabilmente basse, 6 stimate), 2 solo direzione, 1 perso (24,7 s), 3 righe false più una dubbia.

## 4. Da fare, in ordine, per Boris

1. **Seme sulla pallina in arrivo** (nuovo, da provare). È la causa del rovescio perso a 24,7 s e un rischio generale in ogni video con palline a bordo campo. Regola possibile: tra le tracce coerenti di TrackNet nella finestra, partire da quella che si muove e arriva più vicina al polso, come fa già DT per la pallina in uscita. Prova A/B sui 7 video e controllo a occhio.
2. **Istante del contatto dall'audio** (proposto, mai fatto). Nel video 9 colpi su 12 hanno un picco netto entro 1-2 fotogrammi dal contatto; serve una correzione di circa 0,1-0,15 s per questo telefono. Darebbe il contatto dove la pallina è coperta (8,8; 14,0; 24,7; 39,7 s) e un controllo sui due misurati bassi (18,2 e 55,6 s). Da costruire e provare: è la modifica più grande della lista.
3. **P1 e P3** (pronte nel cloud): righe false e dentro/fuori al limite. In attesa dell'accordo con GPT.
4. **Fine-tuning TrackNet**: etichettare i 465 fotogrammi, voto, poi A/B. È l'unica strada per i tratti in cui TrackNet non vede la pallina (11,2 s).
5. **Ripresa**: 60 fps, telefono nella posizione standard (più alto), seconda pallina in tasca, palline raccolte oltre la rete, audio tenuto. Toglie alla radice metà dei problemi di questo video.
6. **Video del test cesto** per l'identità della pallina (15-20 colpi a 2-2,5 s, 3 palline ferme a 1-2 m dall'impatto, 3-5 nel campo lontano).

B e AP sono sul PC insieme a P2, da pushare (prova: `Claude outputs/prova_AP_e_B_rimbalzo.pdf`). Le altre non sono state toccate.
