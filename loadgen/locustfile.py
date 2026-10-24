"""Locust: open-ish loop at the trace's (scaled, time-compressed) rate + embedded controller thread.
Env: ARM, INTERVAL_S (seconds per trace hour), OUTDIR. One test = one arm."""
import csv, gevent, json, os, sys, time, threading
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for p in ("controller", "loadgen", "infra"): sys.path.insert(0, str(ROOT / p))
from locust import HttpUser, task, events, LoadTestShape
import lgcommon as lg
from controller import Controller

ARM = os.environ["ARM"]; INTERVAL_S = float(os.environ["INTERVAL_S"]); OUTDIR = os.environ["OUTDIR"]
CAL = json.load(open(ROOT / "results/calibration.json"))
CTL = Controller(ARM, INTERVAL_S, OUTDIR, CAL)
REQS = []; LAM_COUNT = [0]; TARGET = [0.0]; NUSERS = [1]
TOTAL_S = INTERVAL_S * 6

class U(HttpUser):
    host = "http://" + json.load(open(ROOT / "results/cache/infra_state.json"))["alb_dns"]
    def wait_time(self):
        return max(0.0, NUSERS[0] / max(TARGET[0], 0.1) - getattr(self, "_dur", 0.0))
    @task
    def work(self):
        t = time.time(); b = "error"; code = 0
        with self.client.get(lg.PATH, catch_response=True, name="work") as r:
            code = r.status_code
            if code == 200:
                b = r.json().get("backend", "?"); r.success()
            else: r.failure(f"http {code}")
            lat = (time.time() - t) * 1000
        self._dur = lat / 1000.0
        REQS.append((t - CTL.t0, b, lat, code))
        if b == "lambda": LAM_COUNT[0] += 1

class Shape(LoadTestShape):
    def tick(self):
        t = self.get_run_time()
        if t >= TOTAL_S: return None
        m = min(359, int(t / CTL.wl.tick_s)); r = float(CTL.wl.rps[m]); TARGET[0] = r
        NUSERS[0] = max(1, int(r + 0.999))
        return (NUSERS[0], 50)

def control_loop(env):
    CTL.t0 = time.time(); CTL.setup_arm(); last_lam = 0; m = 0
    next_t = time.time()
    while not CTL.stop.is_set() and m < 360:
        if m % 60 == 0 and ARM != "A_reactive": CTL.decide(m // 60)
        obs = env.runner.stats.total.current_rps if env.runner else 0.0
        CTL.tick(m, obs, LAM_COUNT[0] - last_lam); last_lam = LAM_COUNT[0]
        m += 1; next_t += CTL.wl.tick_s
        gevent.sleep(max(0.0, next_t - time.time()))

@events.test_start.add_listener
def _start(environment, **kw):
    CTL.t0 = time.time(); gevent.spawn(control_loop, environment)

@events.test_stop.add_listener
def _stop(environment, **kw):
    CTL.stop.set(); gevent.sleep(1)
    with open(Path(OUTDIR) / "requests.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["t", "backend", "latency_ms", "status"]); w.writerows(REQS)
    if CTL.log: CTL.finish()
