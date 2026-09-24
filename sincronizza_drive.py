"""
sincronizza_drive.py - copia su Google Drive i file di DATI appena prodotti.

Perche' solo i dati: i CSV pesano pochi KB e servono altrove (Colab, l'altro
computer, Excel), mentre i video pesano decine di MB, se ne produce uno a ogni
esecuzione e quasi sempre si guardano dove sono stati generati. Quelli si
copiano a mano quando serve.

Viene copiata anche la cache della pallina (tracknet3/pred_result): pesa 8 KB
e costa una ventina di minuti di calcolo rigenerarla.

Per disattivare tutto, metti CARTELLA_DRIVE = "" qui sotto.
"""

import os
import shutil

# Cartella di Drive sul PC. Su un computer senza Drive (o per disattivare la
# copia) basta lasciarla vuota: gli script continuano a funzionare.
CARTELLA_DRIVE = r"G:\Il mio Drive\rf_coach_vision"


def copia(percorso_file, sottocartella):
    """
    Copia un file nella corrispondente sottocartella di Drive.
    Non solleva mai errori: se Drive non c'e' o non e' scrivibile, l'analisi
    non deve fallire per questo.
    """

    if not CARTELLA_DRIVE or not percorso_file or not os.path.exists(percorso_file):
        return False

    destinazione = os.path.join(CARTELLA_DRIVE, sottocartella)

    try:
        if not os.path.isdir(CARTELLA_DRIVE):
            return False  # Drive non montato su questo computer
        os.makedirs(destinazione, exist_ok=True)
        shutil.copy2(percorso_file, destinazione)
        print(f"[drive] copiato in {os.path.join(destinazione, os.path.basename(percorso_file))}")
        return True
    except OSError as e:
        print(f"[drive] copia non riuscita ({e}): il file resta comunque in locale.")
        return False
