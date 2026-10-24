"""Brute-force check: per (app, hour) in TEST, search base b over a fine grid minimizing f*60*b + L*sum(max(0,c-b));
compare total cost with the q* quantile rule (= base_oracle)."""
import json
from run_sim import *
conc, meta, heavy, _ = setup(); idx = np.load(ROOT/"data/processed/pop_idx.npy")
E = make_env(conc, meta, idx, "ec2"); f, L = E["f"], E["L"]
hrs = list(hours_of(TEST)); bf = 0.0; th = 0.0
B = base_oracle(E, TEST)
for j, h in enumerate(hrs):
    w = E["c"][:, h*60:(h+1)*60]
    cand = np.linspace(0, 1, 401)[None, :] * w.max(1, keepdims=True)          # [n, 401]
    cost = f * 60 * cand + L[:, None] * np.maximum(0, w[:, None, :] - cand[:, :, None]).sum(2)
    bf += cost.min(1).sum()
    b = B[:, j]; th += (f * 60 * b + L * np.maximum(0, w - b[:, None]).sum(1)).sum()
res = {"brute_force_cost_test_period": bf, "qstar_rule_cost_test_period": th, "relative_gap_pct": 100 * (th - bf) / bf,
       "note": "grid of 401 candidates per app-hour; rule gap is discretisation (60 samples/hour) not theory error"}
json.dump(res, open(ROOT/"results/newsvendor_check.json", "w"), indent=1); print(res)
