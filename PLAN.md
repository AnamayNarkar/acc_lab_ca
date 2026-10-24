# CostScale — Plan
ML quantile forecast sizes a cheap EC2 ASG base; overflow goes to Lambda via ALB weighted target groups.
Newsvendor: base = q*-quantile of forecast load, q* = 1 - f/L (base 0 if L <= f). Region ap-south-1.

| Phase | Work | Output | Gate |
|---|---|---|---|
| 0 | gitignore, creds, venv, layout, budgets, Makefile | repo skeleton | sts ok, budgets exist |
| 1 | two-pass data pipeline, filter, join duration+memory | results/dataset_summary.json | numbers match user's (or investigate) |
| 2 | prices (Price List API) + simulator, 8 strategies, sensitivity, energy | results/sim_*.json, figs | val-only tuning, test once |
| 3 | LightGBM quantile forecaster, baselines, spike injection | results/forecast_*.json | report ML vs rolling plainly |
| 4 | app, boto3 infra, calibrate, controller, Locust arms A-D, dashboard | results/calibration.json, live_*.csv | ASK before `make up` (cost est.); `make down` verified |
| 5 | report.docx, pptx, video script, runbook, preflight, QNA, README, RUBRIC_MAP | deliverables | render + visually check |

Rules: no invented numbers/citations; negative results reported; test touched once; commit per phase; ask before AWS spend/sudo/delete.
