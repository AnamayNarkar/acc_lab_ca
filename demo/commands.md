# Commands during recording (run from the repo root)

```
.venv/bin/python demo/show_results.py sim
```

```
demo/preflight.sh
```

```
curl "http://$(.venv/bin/python -c "import json;print(json.load(open('results/cache/infra_state.json'))['alb_dns'])")/work?ms=400&cpu=80"
```

```
LIVE_OUTDIR=results/live_demo INTERVAL_OVERRIDE=20 .venv/bin/python controller/run_experiments.py C
```

```
.venv/bin/python demo/show_results.py live
```

```
make down
```
