# CostScale runbook

Everything here is run from the repository root. Nothing in this file needs `sudo`.

## 0. Before you start
1. `demo/preflight.sh` - must print `PREFLIGHT PASSED`. It shows the account id and ARN only.
2. Credits and limits: AWS Billing -> Credits should show the remaining balance (about $120 at the start of the project).
3. Close heavy programs: the load generator runs on your laptop and its timing is part of the measurement.
4. Know the cost: one full live run (calibration + four arms) is about $1-3 on AWS; an idle stack costs about $0.024/hour (the load balancer) plus public addresses.

## 1. Quick check without any AWS spend (offline, 1 minute)
```
.venv/bin/python -c "import json;print(json.load(open('results/sim_results.json'))['ec2']['test']['6_hybrid_rolling']['cost'])"
make sim        # re-runs the simulator (~2-3 min); results/sim_results.json is rewritten
```

## 2. Live demo - short version (about 10 minutes of AWS time)
```
make up                      # creates ALB, 2 target groups, Lambda, ASG (0 instances), dashboard   (~1-2 min)
. infra/env.sh && .venv/bin/python infra/set_ip.py      # only if your network changed since `make up`
curl "http://$(.venv/bin/python -c "import json;print(json.load(open('results/cache/infra_state.json'))['alb_dns'])")/work?ms=400&cpu=80"
```
Expected: `{"backend": "lambda", ...}` (the ASG has no instances; weights are 0 EC2 / 999 Lambda).

Then show the controller shift traffic (one arm at an accelerated interval, about 3 minutes):
```
INTERVAL_OVERRIDE=20 .venv/bin/python controller/run_experiments.py C
```
Open the CloudWatch dashboard `CostScale` (region ap-south-1) in a browser while it runs.

## 3. Full experiment (about 2.8 hours; do not do this on camera)
```
make calibrate               # about 20 min; writes results/calibration.json
make sim && make forecast    # re-run both with the measured capacity
make run                     # arms A, B, C, D, about 40 minutes each
.venv/bin/python controller/analyze.py
.venv/bin/python report/make_live_figures.py
```

## 4. Teardown (always)
```
make down
```
It deletes the ASG (and its instances), listeners, ALB, target groups, launch template, Lambda, role, log group, dashboard and security groups, then checks the tagging API and prints
`DOWN: nothing tagged project=costscale remains (budgets kept).` If it prints `LEFTOVERS:`, run `make down` again; if something remains, delete it in the console, filtering by tag `project = costscale`.
Budgets alerts are intentionally kept. Confirm afterwards with `demo/preflight.sh`: ASGs, load balancers and running instances should all be 0.

## 5. Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| `explicit deny in a service control policy` | Organization policy `AdvancedModeRegionRestrictionSecurityControlPolicy`, statement `RegionFloor`, does not list ap-south-1 | Management account -> AWS Organizations -> Policies -> Service control policies -> add `"ap-south-1"` to the allowed Regions list |
| Requests time out (`ConnectTimeout`) | Laptop public IP changed (mobile network) | `. infra/env.sh && .venv/bin/python infra/set_ip.py`; the load generator also adds the current IP automatically every 10 s |
| `make up` says resource exists | A previous run left resources | `make down`, then `make up` |
| First request after a long idle returns slowly | Lambda cold start (about +200 ms measured) | Expected; shown in `results/calibration.json` |
| Reactive arm errors | Expected: arm A has no Lambda fallback | See Evaluation |
| Cost Explorer shows $0 | It lags by about a day | Use `.venv/bin/python infra/cost.py` for the local running estimate |
