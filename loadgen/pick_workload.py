"""Pick ONE heavy HTTP function for the live demo and a 6-hour ramp window on test day 14.
Criteria (documented in report): strong daily pattern (corr of hourly profile between day pairs), moderate minute-level burstiness
(CV of minute load around its hourly mean), and a window where hourly load changes by a large factor (so scaling decisions matter)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
import numpy as np
from core import load_all
conc, meta = load_all(); idx = np.load(ROOT / "data/processed/pop_idx.npy")
inv = np.load(ROOT / "data/processed/inv.npy", mmap_mode="r")
rows = []
for i in idx:
    if meta.trigger.values[i] != "http": continue
    x = conc[i].reshape(14, 24, 60); hm = x.mean(2)             # [day, hour]
    prof = np.mean([np.corrcoef(hm[d], hm[d + 1])[0, 1] for d in range(13)])
    cv = float(np.mean(x.std(2) / (hm + 1e-9)))
    rows.append((int(i), float(prof), cv, float(conc[i].mean())))
rows.sort(key=lambda r: -r[1])
print("candidates (idx, daily corr, minute CV, mean conc):"); [print(r) for r in rows]
ok = [r for r in rows if 0.1 <= r[2] <= 0.6] or rows
i = ok[0][0]
x = conc[i]; day14 = x[13 * 1440:]; hm = day14.reshape(24, 60).mean(1)
best = max(range(0, 19), key=lambda h: hm[h:h + 6].max() / (hm[h:h + 6].min() + 1e-9))
start_h = 13 * 24 + best
win_inv = np.asarray(inv[i, start_h * 60:(start_h + 6) * 60], dtype=float) / 60.0   # req/s per minute
scale = 28.0 / win_inv.max()
out = dict(idx=i, func=meta.func.values[i], trigger="http", avg_duration_ms=float(meta.avg_duration_ms.values[i]), app_memory_mb=float(meta.app_memory_mb.values[i]),
           daily_profile_corr=ok[0][1], minute_cv=ok[0][2], window_start_hour_abs=int(start_h), window_hours=6,
           trace_peak_rps=float(win_inv.max()), scale_factor=float(scale), live_peak_rps=28.0,
           hourly_mean_rps_window=[float(v) for v in (win_inv.reshape(6, 60).mean(1) * scale)],
           why="highest day-to-day hourly-profile correlation among heavy HTTP functions with moderate minute CV (0.1-0.6); window chosen with largest max/min hourly ratio on day 14")
json.dump(out, open(ROOT / "results/live_workload.json", "w"), indent=1); print(json.dumps(out, indent=1))
