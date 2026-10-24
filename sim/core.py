"""Simulator core: cost model, load, strategies. Pure numpy replay of the real trace (Azure traffic, AWS prices)."""
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MIN, TRAIN, VAL, TEST = 1440, slice(0, 10 * 1440), slice(10 * 1440, 12 * 1440), slice(12 * 1440, 14 * 1440)
MONTH_MIN = 30 * 1440

# ---- AWS ap-south-1 prices from results/prices_raw.json (Price List API); see results/prices.json
P = dict(lambda_gbs=1.66667e-5, lambda_req=2e-7, t3_medium_h=0.0448, fargate_vcpu_h=0.04256, fargate_gb_h=0.004655)
CAP = dict(ec2=16.0, fargate=4.0)  # concurrent requests per t3.medium / per 0.5vCPU-1GB task (ASSUMED until calibrated)
cal = ROOT / "results" / "calibration.json"
if cal.exists():
    c = json.load(open(cal))
    CAP = {**CAP, **c.get("capacity_units", {})}

def f_unit_min(kind="ec2", p=P, cap=None, scale=1.0):
    """container $ per capacity-unit-minute"""
    cap = cap or CAP[kind]
    hourly = p["t3_medium_h"] if kind == "ec2" else 0.5 * p["fargate_vcpu_h"] + 1.0 * p["fargate_gb_h"]
    return scale * hourly / cap / 60.0

def lambda_unit_min(mem_mb, dur_ms, p=P, lscale=1.0):
    """Lambda $ to serve one unit of concurrency for a minute = 60*(GB*price_gbs + price_req/dur_s)"""
    gb = np.maximum(128.0, mem_mb) / 1024.0
    return lscale * 60.0 * (gb * p["lambda_gbs"] + p["lambda_req"] / (np.maximum(dur_ms, 1.0) / 1000.0))

def load_all():
    inv = np.load(ROOT / "data/processed/inv.npy", mmap_mode="r")
    meta = pd.read_parquet(ROOT / "data/processed/meta.parquet")
    dur = np.maximum(meta.avg_duration_ms.values, 1.0)
    conc = (np.asarray(inv, dtype=np.float32) / 60.0) * (dur[:, None].astype(np.float32) / 1000.0)
    return conc, meta

def qstar(f, L):
    return np.where(L > f, 1.0 - f / L, 0.0)

def hourly_view(x):  # [n, T] -> [n, hours, 60]
    return x.reshape(x.shape[0], -1, 60)

def quantile_per_row(x, q):
    """x [n,k]; q [n] -> per-row quantile (linear interp). q==0 -> 0 base handled by caller."""
    xs = np.sort(x, axis=1)
    pos = q * (x.shape[1] - 1)
    lo = np.floor(pos).astype(int); hi = np.minimum(lo + 1, x.shape[1] - 1); w = pos - lo
    r = np.arange(x.shape[0])
    return xs[r, lo] * (1 - w) + xs[r, hi] * w

def energy_wh(base_unit_min_total, util, lam_gbs_total, kind="ec2"):
    """Energy ESTIMATE (CCF methodology, cloudcarbonfootprint.org): W = 0.74 + util*(3.5-0.74) per vCPU-h.
    containers: capacity-unit-minutes -> vCPU-hours (t3.medium: 2 vCPU/16 units; Fargate task 0.5 vCPU/4 units).
    Lambda: vCPUs = mem_MB/1792 at 50% util -> GB-s*1024/1792 vCPU-s."""
    vcpu_per_unit = (2.0 / CAP["ec2"]) if kind == "ec2" else (0.5 / CAP["fargate"])
    vcpu_h = base_unit_min_total / 60.0 * vcpu_per_unit
    w = 0.74 + util * (3.5 - 0.74)
    cont = vcpu_h * w
    lam = (lam_gbs_total * 1024.0 / 1792.0) / 3600.0 * (0.74 + 0.5 * (3.5 - 0.74))
    return cont + lam
