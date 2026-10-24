"""Phase 3: global LightGBM quantile forecaster, baselines, margin chosen on validation by decision cost, spike test."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim")); sys.path.insert(0, str(ROOT / "forecast"))
import numpy as np, lightgbm as lgb
from features import *
from run_sim import *

rng = np.random.default_rng(0)
conc, meta, heavy, _ = setup()
idx = np.load(ROOT / "data/processed/pop_idx.npy")
C = conc[idx]; M = meta.iloc[idx]
level = C[:, TRAIN].mean(1) + 1e-6
trig = M.trigger.map(TRIG).values
E = make_env(conc, meta, idx, "ec2")

def hour_range(per): return range(per.start // 60, per.stop // 60)

def build(Cmat, hours, sample=None):
    X, Y, H = [], [], []
    for h in hours:
        F = feats_at(Cmat, h, level, trig)
        if sample:
            mins = rng.choice(60, sample, replace=False)
            for m in mins:
                X.append(F); Y.append(Cmat[:, h * 60 + m] / level); H.append(np.full(len(F), h))
        else: X.append(F); H.append(np.full(len(F), h))
    return np.concatenate(X), (np.concatenate(Y) if Y else None)

Xtr, Ytr = build(C, range(24, 240), sample=10)
models = {}
for q in QS:
    m = lgb.LGBMRegressor(objective="quantile", alpha=q, n_estimators=300, learning_rate=0.05, num_leaves=15,
                          min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
    m.fit(Xtr, Ytr); models[q] = m

def predict_q(Cmat, per):
    """-> [n, hours, 6] raw-unit quantile forecasts of per-minute concurrency for each hour of period"""
    out = []
    for h in hour_range(per):
        F = feats_at(Cmat, h, level, trig)
        P_ = np.stack([models[q].predict(F) for q in QS], 1) * level[:, None]
        out.append(np.maximum.accumulate(np.maximum(P_, 0), axis=1))
    return np.stack(out, 1)

def interp_base(Pq, qs):
    xq = np.array([0.0] + QS); B = np.zeros(Pq.shape[:2])
    for i in range(Pq.shape[0]):
        for j in range(Pq.shape[1]):
            B[i, j] = np.interp(qs[i], xq, np.concatenate([[0.0], Pq[i, j]]))
    return B

# ---- baselines at all six quantiles
def baseline_q(kind, per):
    out = []
    tr = C[:, TRAIN]
    for h in hour_range(per):
        row = []
        for q in QS:
            if kind == "persistence": w = C[:, h * 60 - 60:h * 60]
            elif kind == "rolling6h": w = C[:, h * 60 - 360:h * 60]
            elif kind == "seasonal_naive": w = C[:, (h - 24) * 60:(h - 23) * 60]
            else: w = tr
            row.append(np.quantile(w, q, axis=1))
        out.append(np.stack(row, 1))
    return np.stack(out, 1)

def accuracy(Pq, per):
    res = {}
    for k, q in enumerate(QS):
        errs, pin, cov = [], [], []
        for j, h in enumerate(hour_range(per)):
            a = C[:, h * 60:(h + 1) * 60] / level[:, None]; f = Pq[:, j, k][:, None] / level[:, None]
            real_q = np.quantile(a, q, axis=1)
            errs.append(np.abs(f[:, 0] - real_q)); cov.append((a <= f).mean())
            d = a - f; pin.append(np.maximum(q * d, (q - 1) * d).mean())
        res[str(q)] = dict(mae_norm=float(np.mean(errs)), pinball_norm=float(np.mean(pin)), coverage=float(np.mean(cov)))
    return res

out = {"features": FEATURE_NAMES, "train_rows": int(len(Xtr)), "n_apps": int(len(idx)), "horizon": "next hour, decided at hour start"}
P_val, P_test = predict_q(C, VAL), predict_q(C, TEST)
acc = {"lightgbm": {"val": accuracy(P_val, VAL), "test": accuracy(P_test, TEST)}}
for b in ("persistence", "rolling6h", "seasonal_naive", "static_train"):
    acc[b] = {"val": accuracy(baseline_q(b, VAL), VAL), "test": accuracy(baseline_q(b, TEST), TEST)}
out["accuracy"] = acc

# ---- safety margin chosen on VALIDATION by decision cost
Bv_raw = interp_base(P_val, E["q"])
margins = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5]
val_cost = {str(m): hybrid_eval(E, VAL, Bv_raw * m)["cost"] * 15 for m in margins}
best_m = float(min(val_cost, key=val_cost.get)); out["margin_val_cost_monthly"] = val_cost; out["margin_chosen"] = best_m
roll_val = hybrid_eval(E, VAL, base_rolling(E, VAL))["cost"] * 15
out["rolling6h_val_cost_monthly"] = roll_val
Bv, Bt = Bv_raw * best_m, interp_base(P_test, E["q"]) * best_m
(ROOT / "results/cache").mkdir(exist_ok=True)
np.save(ROOT / "results/cache/ml_base_val.npy", Bv); np.save(ROOT / "results/cache/ml_base_test.npy", Bt)

# ---- TEST (once): decision cost of all hybrids
def mon(r): return {k: float(r[k]) * (15 if k in ("cost", "cost_container", "cost_lambda", "energy_wh") else 1) for k in
                    ("cost", "cost_container", "cost_lambda", "util", "lambda_share", "unserved_pct", "energy_wh")}
dec = {"hybrid_ML": mon(hybrid_eval(E, TEST, Bt)), "hybrid_rolling": mon(hybrid_eval(E, TEST, base_rolling(E, TEST))),
       "hybrid_static": mon(hybrid_eval(E, TEST, base_static(E, TEST))), "hybrid_oracle": mon(hybrid_eval(E, TEST, base_oracle(E, TEST))),
       "hybrid_seasonal_naive_q": mon(hybrid_eval(E, TEST, interp_base(baseline_q("seasonal_naive", TEST), E["q"])))}
out["decision_cost_test_ec2"] = dec
ml, ro, orc = dec["hybrid_ML"]["cost"], dec["hybrid_rolling"]["cost"], dec["hybrid_oracle"]["cost"]
out["ml_vs_rolling_pct"] = 100 * (ml - ro) / ro
out["headroom_rolling_to_oracle_pct"] = 100 * (ro - orc) / ro
out["ml_beats_rolling"] = bool(ml < ro)

# ---- unseen spike: x4 load for one hour per app at a random test hour (clean history before), forecasts unchanged for that hour
def inject(Cmat, mult, seed=1):
    r = np.random.default_rng(seed); X = Cmat.copy(); hs = r.integers(TEST.start // 60 + 2, TEST.stop // 60 - 2, size=len(X))
    for i, h in enumerate(hs): X[i, h * 60:(h + 1) * 60] *= mult
    return X
spk = {}
for mult in (3, 4, 5):
    Cs = inject(C, mult)
    Es = dict(E); Es["c"] = Cs
    # ML/rolling decide from history at hour start; spike appears within the hour => base for that hour unchanged by spike
    PqS = predict_q(Cs, TEST)  # features at hour start only use minutes before hour start
    spk[str(mult)] = {
        "hybrid_ML": mon(hybrid_eval(Es, TEST, interp_base(PqS, E["q"]) * best_m)),
        "hybrid_rolling": mon(hybrid_eval(Es, TEST, base_rolling(Es, TEST))),
        "reactive_u0.7": mon(capped_eval(Es, TEST, cap_reactive(Es, TEST, 0.7))),
        "reactive_u0.3": mon(capped_eval(Es, TEST, cap_reactive(Es, TEST, 0.3)))}
out["spike_test_ec2"] = spk
fi = dict(zip(FEATURE_NAMES, models[0.9].feature_importances_.tolist())); out["feature_importance_q0.9"] = fi
json.dump(out, open(ROOT / "results/forecast_results.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in ("margin_chosen", "margin_val_cost_monthly", "rolling6h_val_cost_monthly", "decision_cost_test_ec2", "ml_vs_rolling_pct", "headroom_rolling_to_oracle_pct")}, indent=1)[:3500])
for m in ("lightgbm", "rolling6h", "persistence", "seasonal_naive", "static_train"):
    print(m, {q: (round(v["pinball_norm"], 4), round(v["coverage"], 3)) for q, v in acc[m]["test"].items()})
import pickle
if not (ROOT / "results/cache/forecaster.pkl").exists(): pickle.dump({"models": models, "apps": M.func.tolist(), "level": level, "trigger": trig, "idx": idx}, open(ROOT / "results/cache/forecaster.pkl", "wb"))
