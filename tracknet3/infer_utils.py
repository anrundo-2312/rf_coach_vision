"""
infer_utils.py

Tre funzioni estratte da test.py del repo originale TrackNetV3
(https://github.com/qaz812345/TrackNetV3, licenza MIT), la parte di
codice che serve per l'inferenza (predict.py le usa per decodificare
l'heatmap in coordinate e per fare l'ensemble temporale).

Il file originale test.py importa anche pycocotools, che serve SOLO
per la valutazione stile COCO (calcolo di metriche su un dataset di
test) e non per predire su un video nuovo. pycocotools puo' essere
fastidioso da installare su Windows (richiede compilazione), quindi
qui teniamo solo le 3 funzioni davvero necessarie per l'inferenza,
senza quella dipendenza.

Nessuna logica e' stata modificata rispetto all'originale: e' un
copia-incolla di test.py, righe 25-79 e 223-258 della versione del
repo al 2026-09-20.
"""

import math
import numpy as np
import cv2
import torch


def get_ensemble_weight(seq_len, eval_mode):
    """ Get weight for temporal ensemble.

        Args:
            seq_len (int): Length of input sequence
            eval_mode (str): Mode of temporal ensemble
                Choices:
                    - 'average': Return uniform weight
                    - 'weight': Return positional weight

        Returns:
            weight (torch.Tensor): Weight for temporal ensemble
    """

    if eval_mode == 'average':
        weight = torch.ones(seq_len) / seq_len
    elif eval_mode == 'weight':
        weight = torch.ones(seq_len)
        for i in range(math.ceil(seq_len / 2)):
            weight[i] = (i + 1)
            weight[seq_len - i - 1] = (i + 1)
        weight = weight / weight.sum()
    else:
        raise ValueError('Invalid mode')

    return weight


def predict_location(heatmap):
    """ Get coordinates from the heatmap.

        Args:
            heatmap (numpy.ndarray): A single heatmap with shape (H, W)

        Returns:
            x, y, w, h (Tuple[int, int, int, int]): bounding box of the the bounding box with max area
    """
    if np.amax(heatmap) == 0:
        # No respond in heatmap
        return 0, 0, 0, 0
    else:
        # Find all respond area in the heapmap
        (cnts, _) = cv2.findContours(heatmap.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rects = [cv2.boundingRect(ctr) for ctr in cnts]

        # Find largest area amoung all contours
        max_area_idx = 0
        max_area = rects[0][2] * rects[0][3]
        for i in range(1, len(rects)):
            area = rects[i][2] * rects[i][3]
            if area > max_area:
                max_area_idx = i
                max_area = area
        x, y, w, h = rects[max_area_idx]

        return x, y, w, h


def generate_inpaint_mask(pred_dict, th_h=30):
    """ Generate inpaint mask form predicted trajectory.

        Args:
            pred_dict (Dict): Prediction result
                Format: {'Frame':[], 'X':[], 'Y':[], 'Visibility':[]}
            th_h (float): Height threshold (pixels) for y coordinate

        Returns:
            inpaint_mask (List): Inpaint mask
    """
    y = np.array(pred_dict['Y'])
    vis_pred = np.array(pred_dict['Visibility'])
    inpaint_mask = np.zeros_like(y)
    i = 0  # index that ball start to disappear
    j = 0  # index that ball start to appear
    threshold = th_h
    while j < len(vis_pred):
        while i < len(vis_pred) - 1 and vis_pred[i] == 1:
            i += 1
        j = i
        while j < len(vis_pred) - 1 and vis_pred[j] == 0:
            j += 1
        if j == i:
            break
        elif i == 0 and y[j] > threshold:
            # start from the first frame that ball disappear
            inpaint_mask[:j] = 1
        elif (i > 1 and y[i - 1] > threshold) and (j < len(vis_pred) and y[j] > threshold):
            inpaint_mask[i:j] = 1
        else:
            # ball is out of the field of camera view
            pass
        i = j

    return inpaint_mask.tolist()
