# Commands for the recording

Run everything from the repository root (`acc_theory_cost_opt_aws`). Copy each box exactly. The matching words to say are in `demo/VIDEO_SCRIPT.md`.

## A. BEFORE you start recording (off camera, in this order)

```
make up
```
Wait until it prints `UP. ALB: ...` (1 to 2 minutes).

```
. infra/env.sh && .venv/bin/python infra/set_ip.py
```
Expected: `ip ok <your address>` or `ip updated <your address>`.

```
demo/preflight.sh
```
Expected: ends with `PREFLIGHT PASSED`. If not, fix that before recording.

Then open the browser: AWS console, account **Make It Happen (370854780982)**, region **Asia Pacific (Mumbai)**, CloudWatch, Dashboards, `CostScale`.

## B. DURING the recording (in this order)

**Segment 5: simulation results (offline)**
```
.venv/bin/python demo/show_results.py sim
```

**Segment 6b: preflight**
```
demo/preflight.sh
```

**Segment 6c: one request**
```
curl "http://$(.venv/bin/python -c "import json;print(json.load(open('results/cache/infra_state.json'))['alb_dns'])")/work?ms=400&cpu=80"
```

**Segment 6d: the controller at work** (about 2 minutes; press Ctrl+C when the table with `Aggregated` appears)
```
LIVE_OUTDIR=results/live_demo INTERVAL_OVERRIDE=20 .venv/bin/python controller/run_experiments.py C
```

**Segment 6f: recorded results of the full run (offline)**
```
.venv/bin/python demo/show_results.py live
```

**Segment 9: teardown** (a few minutes; stop recording when you see the line starting `DOWN:`)
```
make down
```

## C. If something fails during recording

Requests time out (your network address changed):
```
. infra/env.sh && .venv/bin/python infra/set_ip.py
```

Anything on AWS fails: skip it and run only the offline ones (the two `show_results.py` commands).

## D. After recording

Check nothing is left running:
```
demo/preflight.sh
```
The line `ASGs=0  load balancers=0  running instances=0` means CostScale has nothing running.

## Quick order cheat sheet

| When | Command |
|---|---|
| Before | `make up`, then `set_ip.py`, then `demo/preflight.sh` |
| 3:10 | `show_results.py sim` |
| 4:30 | `demo/preflight.sh`, then `curl ...`, then `run_experiments.py C` (Ctrl+C at the table) |
| about 6:00 | `show_results.py live` |
| 8:50 | `make down` |
