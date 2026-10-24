# DECISIONS
Log of choices made without asking. Newest last.

- D0.1 Added `*.tar.xz`, `.env.*`, tfstate to .gitignore (dataset is 143 MB; not for git).
- D0.2 Infra via boto3 (user declined OpenTofu install). `make down` verifies via resourcegroupstaggingapi.
- D0.3 Budgets alerts ($30/$60/$80, ACTUAL > 100%) go to the user's email; created via boto3 in us-east-1 (global service), tagged project=costscale. Budgets beyond the 2 free ones cost ~$0.02/day each (~$0.60/mo total) — negligible, noted.
- D0.4 Creds mapped by `infra/env.sh` (sourced, never printed). Machine has 7 GB RAM / 12 GB free disk: pipeline streams CSVs in two passes, int32.
- D0.5 Python 3.14 venv; packages: numpy pandas pyarrow lightgbm scikit-learn matplotlib boto3 locust python-docx python-pptx.
- D1.1 Material difference found: ≥5 req/min filter alone gives 2,594 functions (2,518 w/ duration+memory); user's 2,127/2,066 are reproduced exactly when also requiring presence on all 14 days. Adopted that as the selection rule (also required for chronological split).
- D2.1 Unit of analysis = function (HashOwner|HashApp|HashFunction), with its app's memory. Heavy = min(all-Lambda, peak×1.2 EC2) monthly cost on TRAIN days >= $50 → 94 heavy functions (user explored 96; train-only definition avoids leakage). Sim population = heavy minus timer = 94 (no heavy timers exist).
- D2.2 Container capacity is billed fractionally (pooled fleet across apps); an "integer instances per app" scenario is reported as sensitivity. Container capacity does not depend on function memory (assumption).
- D2.3 Prices (Price List API, retrieved 2026-10-24): t3.medium $0.0448/h (user's 0.0416 reference is us-east-1), Lambda $1.66667e-5/GB-s tier 1, $2e-7/req, Fargate x86 $0.04256/vCPU-h, $0.004655/GB-h. These explain part of the peak-sized gap vs user's reference ($349k vs $309k).
- D2.4 Energy estimate: Cloud Carbon Footprint methodology (opened; 0.74 W idle→3.5 W max per vCPU, Lambda vCPU=MB/1792 at 50% util). Estimate only.
- D2.5 Seasonal strategy (4): capacity = mean of previous-3-days same-hour max / u. Labeled emulation.
- D2.6 Test-period numbers were printed in the same script run as validation; the script was rerun once after a zero-duration clamp fix (no tuning). No hyperparameter was chosen on test.
- D2.7 Newsvendor brute-force check (results/newsvendor_check.json): rule within 0.009% of grid search per app-hour (user observed 0.5%).
