"""
addestra.py - fine-tuning di TrackNet (TrackNetV3) partendo dai pesi che usa
gia' il programma (tracknet3/ckpts/TrackNet_best.pt, addestrati sul badminton).

Usa il codice di addestramento ORIGINALE di TrackNetV3 (qaz812345/TrackNetV3,
licenza MIT): dataset, funzione di perdita (WBCELoss) e valutazione
(eval_tracknet). Il repository originale va scaricato a parte (il notebook lo
fa da solo) e passato con --tracknetv3. Il modello e' lo stesso di
tracknet3/model.py (file identico), quindi i pesi prodotti si usano nel
programma cambiando solo il nome del file.

    python tracknet_finetune/addestra.py --dati /content/dati_tennis \
        --tracknetv3 /content/TrackNetV3 --pesi_iniziali tracknet3/ckpts/TrackNet_best.pt \
        --uscita /content/drive/MyDrive/rf_coach_vision/tracknet_finetune/run1 \
        --epoche 15 --lr 1e-4

Prima conviene una prova di pochi minuti, per scoprire subito un errore:

    python tracknet_finetune/addestra.py ... --prova

Cosa fa:
  1. carica i pesi iniziali (stessa lunghezza di sequenza e stesso sfondo:
     8 fotogrammi + immagine mediana, come nel programma);
  2. misura i pesi iniziali sulla validazione (il "prima");
  3. addestra (Adam, passo --lr piccolo: si corregge, non si riparte da zero),
     con la mescolanza di campioni (mixup) usata da TrackNetV3;
  4. dopo ogni epoca valuta sulla validazione e tiene il migliore (accuratezza,
     come TrackNetV3, tolleranza 4 px a 512x288 = 15 px a 1080p);
  5. salva in --uscita:
       TrackNet_tennis.pt      il migliore, SOLO modello + parametri (si usa nel programma)
       ultimo_completo.pt      l'ultimo, con l'ottimizzatore (per --riprendi)
       registro.json           perdita e metriche di ogni epoca

--congela inizio tiene fermi i primi blocchi (down_block_1..3, ~15% dei pesi:
riconoscono forme semplici) e addestra solo il resto: utile con pochi dati.
Con --riprendi riparte dall'ultima epoca salvata in --uscita (Colab che si
disconnette).
"""

import argparse
import json
import os
import sys
import time

import numpy as np


def argomenti():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dati", required=True, help="cartella prodotta da prepara_dataset_tennis.py")
    p.add_argument("--tracknetv3", required=True, help="cartella del repository originale TrackNetV3")
    p.add_argument("--pesi_iniziali", required=True, help="di solito tracknet3/ckpts/TrackNet_best.pt")
    p.add_argument("--uscita", required=True, help="cartella dei risultati (meglio su Drive)")
    p.add_argument("--epoche", type=int, default=15)
    p.add_argument("--lr", type=float, default=1e-4, help="passo di Adam (TrackNetV3 da zero usa 1e-3)")
    p.add_argument("--batch", type=int, default=10)
    p.add_argument("--mixup", type=float, default=0.5, help="alpha della mescolanza di campioni; -1 = spenta")
    p.add_argument("--congela", choices=["nessuno", "inizio"], default="nessuno")
    p.add_argument("--tolleranza", type=float, default=4, help="px a 512x288 per contare la pallina trovata")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--seme", type=int, default=13)
    p.add_argument("--riprendi", action="store_true", help="riparte da ultimo_completo.pt in --uscita")
    p.add_argument("--prova", action="store_true", help="prova veloce: 256 campioni, 1 epoca, niente salvataggio del migliore")
    return p.parse_args()


def main():
    a = argomenti()
    # Il codice originale si importa come "dataset", "test", "utils", "model":
    # la sua cartella deve venire prima di tutto il resto.
    sys.path.insert(0, os.path.abspath(a.tracknetv3))
    import torch
    from torch.utils.data import DataLoader
    from dataset import Shuttlecock_Trajectory_Dataset
    from test import eval_tracknet
    from utils.general import get_model
    from utils.metric import WBCELoss

    if not torch.cuda.is_available():
        raise SystemExit("Serve la GPU (su Colab: Runtime -> Cambia tipo di runtime -> GPU).")
    np.random.seed(a.seme)
    torch.manual_seed(a.seme)
    torch.cuda.manual_seed(a.seme)
    os.makedirs(a.uscita, exist_ok=True)
    p_ultimo = os.path.join(a.uscita, "ultimo_completo.pt")
    p_migliore = os.path.join(a.uscita, "TrackNet_tennis.pt")
    p_registro = os.path.join(a.uscita, "registro.json")

    print(f"GPU: {torch.cuda.get_device_name(0)}")

    def carica(percorso):
        # file nostri o di TrackNetV3: fidati. weights_only=False serve con torch >= 2.6
        try:
            return torch.load(percorso, map_location="cuda", weights_only=False)
        except TypeError:                      # torch vecchio, senza weights_only
            return torch.load(percorso, map_location="cuda")

    # ---------------------------------------------------------------- modello
    iniziale = carica(a.pesi_iniziali)
    seq_len = iniziale["param_dict"]["seq_len"]
    bg_mode = iniziale["param_dict"]["bg_mode"]
    model = get_model("TrackNet", seq_len, bg_mode).cuda()
    model.load_state_dict(iniziale["model"])
    print(f"Pesi iniziali: {a.pesi_iniziali} (sequenza {seq_len}, sfondo '{bg_mode}')")

    if a.congela == "inizio":
        fermi = 0
        for nome, par in model.named_parameters():
            if nome.startswith("down_block"):
                par.requires_grad = False
                fermi += par.numel()
        print(f"Congelati i blocchi iniziali: {fermi / 1e6:.2f} M pesi fermi")
    addestrabili = [par for par in model.parameters() if par.requires_grad]
    print(f"Pesi addestrati: {sum(p.numel() for p in addestrabili) / 1e6:.2f} M")
    ottimizzatore = torch.optim.Adam(addestrabili, lr=a.lr)

    # ---------------------------------------------------------------- dati
    debug = a.prova
    train = Shuttlecock_Trajectory_Dataset(root_dir=a.dati, split="train", seq_len=seq_len, sliding_step=1,
                                           data_mode="heatmap", bg_mode=bg_mode, debug=debug)
    val = Shuttlecock_Trajectory_Dataset(root_dir=a.dati, split="val", seq_len=seq_len, sliding_step=seq_len,
                                         data_mode="heatmap", bg_mode=bg_mode, debug=debug)
    workers = min(a.workers, os.cpu_count() or 2)
    dl_train = DataLoader(train, batch_size=a.batch, shuffle=True, num_workers=workers, drop_last=True,
                          pin_memory=True)
    dl_val = DataLoader(val, batch_size=a.batch, shuffle=False, num_workers=workers, drop_last=False,
                        pin_memory=True)
    print(f"Campioni: addestramento {len(train)}, validazione {len(val)}")
    parametri_valutazione = {"verbose": False, "tolerance": a.tolleranza}

    def valuta(etichetta):
        t0 = time.time()
        perdita, ris = eval_tracknet(model, dl_val, parametri_valutazione)
        r = {k: float(v) for k, v in ris.items()}
        print(f"  {etichetta}: perdita {perdita:.5f}  accuratezza {r['accuracy']:.3f}  precisione "
              f"{r['precision']:.3f}  richiamo {r['recall']:.3f}  F1 {r['f1']:.3f}  "
              f"(TP {r['TP']:.0f} TN {r['TN']:.0f} FP1 {r['FP1']:.0f} FP2 {r['FP2']:.0f} FN {r['FN']:.0f}) "
              f"[{time.time() - t0:.0f} s]")
        return float(perdita), r

    # ---------------------------------------------------------------- ripresa
    registro = {"argomenti": vars(a), "epoche": []}
    inizio, migliore = 0, -1.0
    if a.riprendi:
        if not os.path.exists(p_ultimo):
            raise SystemExit(f"--riprendi: non trovo {p_ultimo}")
        ck = carica(p_ultimo)
        model.load_state_dict(ck["model"])
        ottimizzatore.load_state_dict(ck["optimizer"])
        inizio, migliore = ck["epoch"] + 1, ck["max_val_acc"]
        if os.path.exists(p_registro):
            registro = json.load(open(p_registro))
        print(f"Riprendo dall'epoca {inizio + 1} (migliore finora: {migliore:.3f})")
    else:
        perdita0, ris0 = valuta("PRIMA (pesi del badminton)")
        registro["prima"] = {"perdita_val": perdita0, **ris0}

    epoche = 1 if a.prova else a.epoche

    def mescola(x, y, alpha):
        """Mescolanza di campioni (mixup) come train.py di TrackNetV3."""
        lamb = np.random.beta(alpha, alpha, size=x.size(0))
        lamb = torch.from_numpy(np.maximum(lamb, 1 - lamb)[:, None, None, None]).float().to(x.device)
        indice = torch.randperm(x.size(0), device=x.device)
        return x * lamb + x[indice] * (1 - lamb), y * lamb + y[indice] * (1 - lamb)

    # ---------------------------------------------------------------- addestramento
    for epoca in range(inizio, epoche):
        t0 = time.time()
        model.train()
        perdite = []
        for passo, (_, x, y, _, _) in enumerate(dl_train):
            ottimizzatore.zero_grad()
            x, y = x.float().cuda(non_blocking=True), y.float().cuda(non_blocking=True)
            if a.mixup > 0:
                x, y = mescola(x, y, a.mixup)
            perdita = WBCELoss(model(x), y)
            perdita.backward()
            ottimizzatore.step()
            perdite.append(perdita.item())
            if (passo + 1) % 200 == 0:
                print(f"    epoca {epoca + 1} passo {passo + 1}/{len(dl_train)} perdita {np.mean(perdite[-200:]):.5f}")
                sys.stdout.flush()
        perdita_train = float(np.mean(perdite)) if perdite else float("nan")
        print(f"Epoca {epoca + 1}/{epoche}: perdita addestramento {perdita_train:.5f} [{(time.time() - t0) / 60:.1f} min]")
        perdita_val, ris = valuta(f"validazione dopo l'epoca {epoca + 1}")
        registro["epoche"].append({"epoca": epoca + 1, "perdita_train": perdita_train,
                                   "perdita_val": perdita_val, **ris})

        param_dict = dict(iniziale["param_dict"])
        param_dict.update({"fine_tuning": True, "pesi_iniziali": os.path.basename(a.pesi_iniziali),
                           "dati": os.path.basename(os.path.normpath(a.dati)), "epoche": epoca + 1,
                           "lr": a.lr, "congela": a.congela})
        if ris["accuracy"] >= migliore and not a.prova:
            migliore = ris["accuracy"]
            # solo modello + parametri: e' quello che legge tracknet3/predict.py
            torch.save({"model": model.state_dict(), "param_dict": param_dict, "epoch": epoca,
                        "val": ris}, p_migliore)
            registro["migliore"] = {"epoca": epoca + 1, **ris}
            print(f"  -> nuovo migliore salvato in {p_migliore}")
        torch.save({"model": model.state_dict(), "optimizer": ottimizzatore.state_dict(), "epoch": epoca,
                    "max_val_acc": migliore, "param_dict": param_dict}, p_ultimo)
        with open(p_registro, "w") as f:
            json.dump(registro, f, indent=1)

    if a.prova:
        print("PROVA RIUSCITA: dati, modello, addestramento e valutazione funzionano. "
              "Ora lancia senza --prova.")
        return
    print("\nRiepilogo (validazione):")
    if "prima" in registro:
        print(f"  prima  : accuratezza {registro['prima']['accuracy']:.3f}  F1 {registro['prima']['f1']:.3f}")
    if "migliore" in registro:
        m = registro["migliore"]
        print(f"  dopo   : accuratezza {m['accuracy']:.3f}  F1 {m['f1']:.3f}  (epoca {m['epoca']})")
    print(f"Pesi: {p_migliore}")


if __name__ == "__main__":
    main()
