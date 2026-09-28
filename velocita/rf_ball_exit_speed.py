"""
RF Coach – Velocità di USCITA della palla dalla racchetta (velocità all'impatto).

Versione 2 – impostazione:
  - unica grandezza calcolata: velocità della palla nell'istante in cui lascia
    la racchetta (nessuna velocità media);
  - punto di impatto = cambio di direzione della palla già rilevato dal tracker,
    raffinato a livello sub-frame (intersezione traiettoria in arrivo / in uscita);
  - fit fisico 3D sui 10 frame successivi all'impatto (troncati al rimbalzo);
  - OPZIONE switchabile impact_mode="audio": l'istante di impatto viene preso dal
    suono palla-racchetta (onset acustico), corretto per il ritardo del suono
    (distanza camera-impatto / 343 m/s) e per l'offset audio-video del dispositivo.
    Se il suono non è riconoscibile, fallback automatico al metodo visivo.

Camera fissa dietro al giocatore, leggermente rialzata. Pensato per 30 fps.

Risultati del test sintetico (condizioni ideali, 30 fps, 10 frame, camera dietro
a 3.5 m, rumore del tracker 2 px; 60 prove):
  servizio 180 km/h: 95% entro ~±30-33 km/h  (visivo e audio simili)
  dritto   120 km/h: 95% entro ~±20 km/h
  L'errore cresce in proporzione al rumore del tracker (4 px -> circa il doppio).
  L'istante di impatto NON è la fonte principale di errore: lo è la profondità
  (la palla si allontana quasi lungo la linea di vista della camera).
  Camera d'angolo o laterale: ~±21 km/h servizio, ~±11-13 km/h dritto.

Coordinate campo (metri): x = larghezza (0..10.97), y = lunghezza (0 = fondo lato
camera, 23.77 = fondo opposto), z = altezza.

Modifiche per rf_coach_vision (25-28/09/2026): due parametri opzionali di
exit_speed, `forward` e `depth_tol`, segnati con [aggiunta rf_coach_vision].
Con i valori di default il comportamento e' quello originale.
"""
import subprocess
import numpy as np
import cv2
from scipy.optimize import least_squares, minimize_scalar
from scipy.signal import butter, sosfiltfilt

SPEED_OF_SOUND = 343.0        # m/s a ~20 °C

# ------------------------------------------------------------------ costanti
G = 9.81                      # m/s^2
RHO = 1.20                    # densità aria kg/m^3 (varia con quota e temperatura)
BALL_MASS = 0.0577            # kg (regolamento ITF 56.0–59.4 g)
BALL_DIAM = 0.067             # m  (regolamento ITF 6.54–6.86 cm)
CD = 0.55                     # coefficiente di resistenza (letteratura ~0.5–0.65)
AREA = np.pi * (BALL_DIAM / 2) ** 2
K_DRAG = RHO * CD * AREA / (2 * BALL_MASS)   # ~0.020 1/m

# Punti noti del campo (m). Tutti a terra tranne il centro rete (h 0.914 m),
# che rende la calibrazione non planare e aiuta a stimare la focale.
COURT_POINTS = {
    "fondo_vicino_sx_doppio": (0.0, 0.0, 0.0),
    "fondo_vicino_dx_doppio": (10.97, 0.0, 0.0),
    "fondo_lontano_sx_doppio": (0.0, 23.77, 0.0),
    "fondo_lontano_dx_doppio": (10.97, 23.77, 0.0),
    "fondo_vicino_sx_singolo": (1.37, 0.0, 0.0),
    "fondo_vicino_dx_singolo": (9.60, 0.0, 0.0),
    "servizio_vicino_sx": (1.37, 5.485, 0.0),
    "servizio_vicino_dx": (9.60, 5.485, 0.0),
    "T_vicino": (5.485, 5.485, 0.0),
    "servizio_lontano_sx": (1.37, 18.285, 0.0),
    "servizio_lontano_dx": (9.60, 18.285, 0.0),
    "T_lontano": (5.485, 18.285, 0.0),
    "rete_centro_alto": (5.485, 11.885, 0.914),
}


# ------------------------------------------------------------ calibrazione
def calibrate_camera(img_pts, world_pts, image_size):
    """Stima K (focale incognita, punto principale al centro, pixel quadrati)
    e posa della camera. img_pts: Nx2 pixel, world_pts: Nx3 metri."""
    w, h = image_size
    img_pts = np.asarray(img_pts, np.float64)
    world_pts = np.asarray(world_pts, np.float64)

    def solve(f):
        K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]], np.float64)
        ok, rvec, tvec = cv2.solvePnP(world_pts, img_pts, K, None,
                                      flags=cv2.SOLVEPNP_SQPNP)
        rvec, tvec = cv2.solvePnPRefineLM(world_pts, img_pts, K, None, rvec, tvec)
        proj, _ = cv2.projectPoints(world_pts, rvec, tvec, K, None)
        err = np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - img_pts) ** 2, 1)))
        return err, K, rvec, tvec

    fs = np.linspace(0.4 * w, 4.0 * w, 60)
    f0 = fs[int(np.argmin([solve(f)[0] for f in fs]))]
    res = minimize_scalar(lambda f: solve(f)[0],
                          bounds=(0.8 * f0, 1.2 * f0), method="bounded")
    err, K, rvec, tvec = solve(res.x)
    return {"K": K, "rvec": rvec, "tvec": tvec, "reproj_rms_px": err}


def project(points_3d, cam):
    p, _ = cv2.projectPoints(np.asarray(points_3d, np.float64).reshape(-1, 3),
                             cam["rvec"], cam["tvec"], cam["K"], None)
    return p.reshape(-1, 2)


def ground_from_pixel(px, cam):
    """Pixel -> punto sul piano z=0 (valido SOLO per oggetti a terra:
    piedi del giocatore, rimbalzo della palla)."""
    R, _ = cv2.Rodrigues(cam["rvec"])
    C = -R.T @ cam["tvec"].ravel()                      # centro camera
    ray = R.T @ np.linalg.inv(cam["K"]) @ np.array([px[0], px[1], 1.0])
    s = -C[2] / ray[2]
    return C + s * ray


# ------------------------------------------------------------------ fisica
def _acc(v, k):
    return np.array([0.0, 0.0, -G]) - k * np.linalg.norm(v) * v


def simulate(p0, v0, times, k=K_DRAG, dt=0.005):
    """Posizioni ai tempi richiesti (s dall'impatto, >= 0). RK4."""
    times = np.asarray(times, float)
    out = np.zeros((len(times), 3))
    p, v, t = np.array(p0, float), np.array(v0, float), 0.0
    order = np.argsort(times)
    for idx in order:
        target = times[idx]
        while t < target - 1e-12:
            h = min(dt, target - t)
            k1v, k1p = _acc(v, k), v
            k2v, k2p = _acc(v + h / 2 * k1v, k), v + h / 2 * k1v
            k3v, k3p = _acc(v + h / 2 * k2v, k), v + h / 2 * k2v
            k4v, k4p = _acc(v + h * k3v, k), v + h * k3v
            p = p + h / 6 * (k1p + 2 * k2p + 2 * k3p + k4p)
            v = v + h / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
            t += h
        out[idx] = p
    return out


def ground_crossing(p0, v0, k=K_DRAG, dt=0.004, t_max=2.0):
    """Tempo e punto in cui la traiettoria tocca il suolo (z=0)."""
    p, v, t = np.array(p0, float), np.array(v0, float), 0.0
    while t < t_max:
        pn = p + v * dt + 0.5 * _acc(v, k) * dt * dt
        if pn[2] <= 0:
            a = p[2] / (p[2] - pn[2])
            return t + a * dt, p + a * (pn - p)
        v = v + _acc(v, k) * dt; p = pn; t += dt
    return t, p



# ============================================================ IMPATTO VISIVO
def refine_impact_visual(track_px, frame_idx, change_idx, fps, n_side=4):
    """
    Raffina l'impatto rilevato dal cambio di direzione.
    change_idx: indice (nell'array) della PRIMA detection dopo il cambio di
                direzione (primo punto in uscita), come già fornito dal tracker.
    Fitta una parabola (pixel vs tempo) ai punti in arrivo e una a quelli in
    uscita e cerca l'istante tra i due frame in cui le curve si incontrano.
    Ritorna (t_impatto_s, pixel_impatto, qualità_px).
    """
    px = np.asarray(track_px, float)
    t = np.asarray(frame_idx, float) / fps
    i_in = np.arange(max(0, change_idx - n_side), change_idx)
    i_out = np.arange(change_idx, min(len(t), change_idx + n_side))
    if len(i_in) < 2 or len(i_out) < 2:
        raise ValueError("Servono almeno 2 punti prima e 2 dopo il cambio di direzione.")

    def fit(idx):
        deg = 2 if len(idx) >= 3 else 1
        return [np.polyfit(t[idx], px[idx, d], deg) for d in (0, 1)]

    cin, cout = fit(i_in), fit(i_out)
    ev = lambda c, tt: np.array([np.polyval(c[0], tt), np.polyval(c[1], tt)])
    t_lo, t_hi = t[change_idx - 1], t[change_idx]
    res = minimize_scalar(lambda tt: np.sum((ev(cin, tt) - ev(cout, tt)) ** 2),
                          bounds=(t_lo, t_hi), method="bounded")
    t_imp = float(res.x)
    p_imp = 0.5 * (ev(cin, t_imp) + ev(cout, t_imp))
    gap = float(np.sqrt(res.fun))
    return t_imp, p_imp, gap, (cin, cout)


# ============================================================= IMPATTO AUDIO
def load_audio_from_video(video_path, sr=48000):
    """Estrae l'audio mono (float32) dal video con ffmpeg."""
    cmd = ["ffmpeg", "-v", "error", "-i", video_path, "-ac", "1", "-ar", str(sr),
           "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64), sr


def detect_impact_audio(audio, sr, t_guess, search_s=0.10, hp_hz=1500.0,
                        min_snr_db=12.0):
    """
    Cerca l'onset del colpo palla-racchetta vicino a t_guess (s, tempo audio).
    - filtro passa-alto (il colpo è un transiente a banda larga, il rumore di
      fondo e i passi sono soprattutto a bassa frequenza)
    - inviluppo di energia a 0.5 ms
    - onset = primo superamento di una soglia adattiva prima del picco
    Ritorna (t_onset_s, snr_db) oppure (None, snr_db) se non affidabile.
    """
    audio = np.asarray(audio, float)
    a0 = max(0, int((t_guess - search_s - 0.2) * sr))
    a1 = min(len(audio), int((t_guess + search_s + 0.05) * sr))
    seg = audio[a0:a1]
    if len(seg) < int(0.1 * sr):
        return None, 0.0
    sos = butter(4, hp_hz, btype="highpass", fs=sr, output="sos")
    y = sosfiltfilt(sos, seg)
    win = max(1, int(0.0005 * sr))
    env = np.sqrt(np.convolve(y ** 2, np.ones(win) / win, mode="same"))
    tt = a0 / sr + np.arange(len(env)) / sr
    inwin = (tt >= t_guess - search_s) & (tt <= t_guess + search_s)
    if not inwin.any():
        return None, 0.0
    pre = env[tt < t_guess - search_s]
    noise = np.median(pre) if len(pre) > 10 else np.median(env)
    mad = np.median(np.abs(pre - noise)) if len(pre) > 10 else noise
    ipk = np.flatnonzero(inwin)[np.argmax(env[inwin])]
    snr_db = 20 * np.log10(env[ipk] / (noise + 1e-12))
    if snr_db < min_snr_db:
        return None, snr_db
    thr = noise + max(8 * mad, 0.15 * (env[ipk] - noise))
    j = ipk
    while j > 0 and env[j] > thr:
        j -= 1
    # interpolazione lineare del superamento soglia
    frac = (thr - env[j]) / (env[j + 1] - env[j] + 1e-12)
    return float(tt[j] + frac / sr), float(snr_db)


# ============================================================ VELOCITÀ USCITA
def exit_speed(track_px, frame_idx, fps, cam, change_idx,
               impact_mode="visual", audio=None, sr=None,
               av_offset_s=0.0, n_frames=10, player_ground_xy=None,
               bounce_frame=None, bounce_px=None, k=K_DRAG, return_debug=False,
               forward=False, depth_tol=None):
    """
    Velocità della palla all'uscita dalla racchetta (km/h).

    track_px, frame_idx: traccia della palla (pixel) e frame corrispondenti
    change_idx:   indice del primo punto dopo il cambio di direzione (dal tracker)
    impact_mode:  "visual" (default) oppure "audio"
    audio, sr:    campioni audio mono e frequenza (necessari per "audio")
    av_offset_s:  offset audio-video del dispositivo (tempo_audio - tempo_video
                  per lo stesso evento), da misurare una volta per modello di
                  telefono/camera; 0 se non noto
    n_frames:     frame usati dopo l'impatto (default 10)
    player_ground_xy: posizione a terra del giocatore (m) – vincolo debole
    bounce_frame / bounce_px: se il rimbalzo cade nei 10 frame, i punti dopo il
                  rimbalzo vengono esclusi; il pixel del rimbalzo aggiunge un
                  vincolo forte (punto a terra)
    forward:      [aggiunta rf_coach_vision] True = la palla va verso il campo
                  avversario (velocita' lungo y positiva). Evita soluzioni
                  "all'indietro" che spiegano gli stessi pixel quando la palla si
                  allontana quasi lungo la linea di vista della camera.
    depth_tol:    [aggiunta rf_coach_vision] se indicato (m), il punto di
                  contatto deve stare entro +-depth_tol dalla distanza
                  camera-giocatore (calcolata da player_ground_xy). Senza, con
                  la camera dietro al giocatore il fit puo' mettere il contatto
                  metri davanti o dietro il giocatore.
    """
    px = np.asarray(track_px, float)
    fi = np.asarray(frame_idx, int)

    # --- 1. istante e pixel di impatto
    t_vis, p_vis, gap, curves = refine_impact_visual(px, fi, change_idx, fps)
    t_imp, p_imp, mode_used, snr = t_vis, p_vis, "visual", None
    if impact_mode == "audio":
        if audio is None or sr is None:
            raise ValueError("impact_mode='audio' richiede audio e sr.")
        # il suono arriva in ritardo: prima stima con distanza ~ 10 m
        t_on, snr = detect_impact_audio(audio, sr, t_vis + av_offset_s + 10 / SPEED_OF_SOUND)
        if t_on is not None:
            mode_used = "audio"
    R, _ = cv2.Rodrigues(cam["rvec"])
    C = -R.T @ cam["tvec"].ravel()

    def impact_ray(pix):
        ray = R.T @ np.linalg.inv(cam["K"]) @ np.array([pix[0], pix[1], 1.0])
        return ray / np.linalg.norm(ray)

    def run_fit(t_imp, p_imp, free_dt):
        ray = impact_ray(p_imp)
        t_rel = fi / fps - t_imp
        sel = np.flatnonzero(t_rel > 0)[:n_frames]
        if bounce_frame is not None:
            sel = sel[fi[sel] < bounce_frame]
        if len(sel) < 4:
            raise ValueError("Troppo pochi punti dopo l'impatto (servono >= 4).")
        tr, obs = t_rel[sel], px[sel]
        # profondità iniziale: dal giocatore, se noto, altrimenti ~ 9 m
        if player_ground_xy is not None:
            s0 = float(np.linalg.norm(np.r_[player_ground_xy, 1.2] - C))
        else:
            s0 = 9.0
        bxy = ground_from_pixel(bounce_px, cam)[:2] if bounce_px is not None else None
        half = 0.5 / fps if free_dt else 0.002
        lb = np.array([1.0, -90, 0.5 if forward else -90, -45, -half])
        ub = np.array([60.0, 90, 90, 45, half])
        if depth_tol is not None:      # [aggiunta rf_coach_vision] contatto entro +-depth_tol m dalla distanza del giocatore
            lb[0], ub[0] = max(1.0, s0 - depth_tol), s0 + depth_tol

        def residuals(x):
            s, v0, dt = x[0], x[1:4], x[4]
            p0 = C + s * ray
            pts = simulate(p0, v0, np.maximum(tr - dt, 0.0), k)
            r = (project(pts, cam) - obs).ravel()
            if player_ground_xy is not None:
                r = np.r_[r, (p0[:2] - np.asarray(player_ground_xy)) / 0.8 * 2.0]
            r = np.r_[r, 2.0 * max(0.0, -p0[2]) / 0.05, 2.0 * max(0.0, p0[2] - 3.4) / 0.05]
            if bxy is not None:
                _, pb = ground_crossing(p0, v0, k)
                r = np.r_[r, (pb[:2] - bxy) / 0.25 * 2.0]
            return r

        # multi-start: direzione iniziale dall'ultimo punto proiettato a terra
        far = ground_from_pixel(obs[-1], cam)
        base = far - (C + s0 * ray); base[2] = 0
        base /= np.linalg.norm(base) + 1e-9
        best = None
        for spd in (20, 35, 50, 65):
            for elev in (-0.12, 0.0, 0.12, 0.25):
                v = base.copy(); v[2] = elev; v = v / np.linalg.norm(v) * spd
                x = np.clip(np.r_[s0, v, 0.0], lb + 1e-6, ub - 1e-6)
                c = np.sum(residuals(x) ** 2)
                if best is None or c < best[0]:
                    best = (c, x)
        sol = least_squares(residuals, best[1], bounds=(lb, ub), x_scale="jac")
        v0 = sol.x[1:4]; spd = np.linalg.norm(v0)
        dof = max(len(sol.fun) - len(sol.x), 1)
        try:
            cov = np.linalg.inv(sol.jac.T @ sol.jac) * np.sum(sol.fun ** 2) / dof
            g = np.zeros(5); g[1:4] = v0 / spd
            sig = float(np.sqrt(g @ cov @ g))
        except np.linalg.LinAlgError:
            sig = float("nan")
        return {"speed": spd, "sigma": sig, "p0": C + sol.x[0] * ray, "v0": v0,
                "dt": sol.x[4], "n": len(sel),
                "rms_px": float(np.sqrt(np.mean(sol.fun[:2 * len(sel)] ** 2)))}

    if mode_used == "audio":
        # correzione ritardo del suono con la distanza stimata (2 iterazioni)
        dist = 10.0
        for _ in range(2):
            t_imp = t_on - av_offset_s - dist / SPEED_OF_SOUND
            p_imp = 0.5 * (np.array([np.polyval(curves[0][0], t_imp), np.polyval(curves[0][1], t_imp)]) +
                           np.array([np.polyval(curves[1][0], t_imp), np.polyval(curves[1][1], t_imp)]))
            fit = run_fit(t_imp, p_imp, free_dt=False)
            dist = float(np.linalg.norm(fit["p0"] - C))
    else:
        fit = run_fit(t_imp, p_imp, free_dt=True)
        t_imp = t_imp + fit["dt"]

    out = {"exit_kmh": fit["speed"] * 3.6, "sigma_kmh": fit["sigma"] * 3.6,
           "impact_mode_used": mode_used, "impact_time_s": t_imp,
           "impact_xyz_m": fit["p0"], "n_points": fit["n"], "rms_px": fit["rms_px"],
           "audio_snr_db": snr, "visual_gap_px": gap}
    if return_debug:
        out["v0_ms"] = fit["v0"]
    return out


# ================================================================== TEST
def _synthetic_camera(image_size=(1920, 1080), f=1500.0,
                      pos=(5.485, -8.0, 3.5), look=(5.485, 14.0, 0.0)):
    w, h = image_size
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]], float)
    Cc, L = np.array(pos, float), np.array(look, float)
    zc = (L - Cc) / np.linalg.norm(L - Cc)
    xc = np.cross(zc, [0, 0, 1.0]); xc /= np.linalg.norm(xc)
    yc = np.cross(zc, xc)
    Rm = np.vstack([xc, yc, zc])
    rvec, _ = cv2.Rodrigues(Rm)
    return {"K": K, "rvec": rvec, "tvec": (-Rm @ Cc).reshape(3, 1)}


def _synthetic_audio(t_impact_video, dist_m, av_offset_s, sr=48000, dur=3.0,
                     rng=None, snr_db=25):
    """Audio sintetico: rumore di fondo + transiente del colpo (burst smorzato
    a banda larga) nell'istante t_video + ritardo del suono + offset A/V."""
    rng = rng or np.random.default_rng()
    n = int(dur * sr)
    audio = rng.normal(0, 1, n) * 0.01
    audio += 0.03 * np.sin(2 * np.pi * 120 * np.arange(n) / sr)   # ronzio basso
    t_on = t_impact_video + dist_m / SPEED_OF_SOUND + av_offset_s
    i0 = int(t_on * sr); L = int(0.03 * sr)
    burst = rng.normal(0, 1, L) * np.exp(-np.arange(L) / (0.004 * sr))
    amp = 0.01 * 10 ** (snr_db / 20)
    audio[i0:i0 + L] += amp * burst
    return audio, sr, t_on


def run_monte_carlo(shot="servizio", trials=30, fps=30, px_noise=2.0,
                    calib_noise=1.0, av_offset_s=0.045, av_offset_error_s=0.0,
                    seed=7, verbose=True, cam_pos=(5.485, -8.0, 3.5),
                    cam_look=(5.485, 14.0, 0.0), modes=("visual", "audio")):
    """Confronta modalità visiva e audio su traiettorie simulate."""
    rng = np.random.default_rng(seed)
    true_cam = _synthetic_camera(pos=cam_pos, look=cam_look)
    W = np.array(list(COURT_POINTS.values()))
    if shot == "servizio":
        p0 = np.array([6.2, -0.3, 2.75]); speed = 180 / 3.6
        aim = np.array([3.6, 17.0, 0.6]); v_in = np.array([0.0, 0.0, -3.0])
    else:
        p0 = np.array([7.5, -1.0, 0.95]); speed = 120 / 3.6
        aim = np.array([3.0, 22.0, 3.2]); v_in = np.array([-1.0, -22.0, -2.0])
    v0 = (aim - p0) / np.linalg.norm(aim - p0) * speed
    tb, pb = ground_crossing(p0, v0)
    Ctrue = -cv2.Rodrigues(true_cam["rvec"])[0].T @ true_cam["tvec"].ravel()
    dist = np.linalg.norm(p0 - Ctrue)

    res = {m: [] for m in modes}
    for _ in range(trials):
        img = project(W, true_cam) + rng.normal(0, calib_noise, (len(W), 2))
        cam = calibrate_camera(img, W, (1920, 1080))
        t_imp = 1.0 + rng.uniform(0, 1 / fps)          # impatto tra due frame
        frames = np.arange(int(0.8 * fps), int(1.0 * fps + 14))
        tt = frames / fps
        pos = np.where((tt < t_imp)[:, None],
                       p0 + np.outer(tt - t_imp, v_in),
                       simulate(p0, v0, np.maximum(tt - t_imp, 0)))
        keep = (tt < t_imp) | (tt - t_imp < tb)
        frames, pos = frames[keep], pos[keep]
        obs = project(pos, true_cam) + rng.normal(0, px_noise, (len(pos), 2))
        change_idx = int(np.flatnonzero(frames / fps > t_imp)[0])
        bf = int(np.ceil((t_imp + tb) * fps)) if tb < 11 / fps else None
        feet = p0[:2] + rng.normal(0, 0.3, 2)
        audio, sr, _ = _synthetic_audio(t_imp, dist, av_offset_s, rng=rng)
        for mode in modes:
            r = exit_speed(obs, frames, fps, cam, change_idx, impact_mode=mode,
                           audio=audio, sr=sr,
                           av_offset_s=av_offset_s + rng.normal(0, av_offset_error_s) if av_offset_error_s else av_offset_s,
                           player_ground_xy=feet, bounce_frame=bf)
            res[mode].append((r["exit_kmh"] - speed * 3.6, r["impact_time_s"] - t_imp,
                              r["impact_mode_used"]))
    if verbose:
        print(f"\n{shot.upper()} – camera {cam_pos} – uscita vera {speed*3.6:.0f} km/h, {fps} fps, "
              f"rumore tracker {px_noise} px, offset A/V {av_offset_s*1000:.0f} ms "
              f"(errore sull'offset {av_offset_error_s*1000:.0f} ms)")
        for mode, v in res.items():
            e = np.array([x[0] for x in v]); ti = np.array([x[1] for x in v]) * 1000
            used = sum(1 for x in v if x[2] == mode)
            print(f"  {mode:6s}: errore medio {e.mean():+5.1f} km/h | dev.std {e.std():4.1f} | "
                  f"95% entro ±{np.percentile(np.abs(e),95):4.1f} km/h | "
                  f"errore istante impatto {np.abs(ti).mean():4.1f} ms (media ass.) | "
                  f"modalità usata {used}/{len(v)}")
    return res


if __name__ == "__main__":
    print(f"K_DRAG = {K_DRAG:.4f} 1/m (Cd={CD})")
    run_monte_carlo("servizio", trials=20)
    run_monte_carlo("dritto", trials=20)
