"""Feature construction for the hourly quantile forecaster. Decision time = start of hour h; only minutes < h*60 used."""
import numpy as np
QS = [0.5, 0.7, 0.8, 0.9, 0.95, 0.99]
TRIG = {"http": 0, "queue": 1, "event": 2, "orchestration": 3, "storage": 4, "others": 5}

def feats_at(conc, h, level, trig_code):
    """conc [n,T] (raw concurrency), h hour index (absolute), level [n] train mean. Returns [n, F] normalized features."""
    s = level[:, None]
    w1 = conc[:, h * 60 - 60:h * 60] / s
    w6 = conc[:, h * 60 - 360:h * 60] / s
    y = conc[:, (h - 24) * 60:(h - 23) * 60] / s
    hod = (h % 24) / 24.0 * 2 * np.pi
    n = conc.shape[0]
    cols = [w1.mean(1), w1.max(1), np.quantile(w1, .9, axis=1), w6.mean(1), w6.max(1), np.quantile(w6, .9, axis=1),
            y.mean(1), np.quantile(y, .9, axis=1), np.full(n, np.sin(hod)), np.full(n, np.cos(hod)),
            trig_code.astype(float), np.log(level + 1e-6)]
    return np.stack(cols, 1)
FEATURE_NAMES = ["m60", "max60", "q90_60", "m360", "max360", "q90_360", "yday_mean", "yday_q90", "hsin", "hcos", "trigger", "log_level"]
