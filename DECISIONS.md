# DECISIONS
Log of choices made without asking. Newest last.

- D0.1 Added `*.tar.xz`, `.env.*`, tfstate to .gitignore (dataset is 143 MB; not for git).
- D0.2 Infra via boto3 (user declined OpenTofu install). `make down` verifies via resourcegroupstaggingapi.
- D0.3 Budgets alerts ($30/$60/$80, ACTUAL > 100%) go to the user's email; created via boto3 in us-east-1 (global service), tagged project=costscale. Budgets beyond the 2 free ones cost ~$0.02/day each (~$0.60/mo total) — negligible, noted.
- D0.4 Creds mapped by `infra/env.sh` (sourced, never printed). Machine has 7 GB RAM / 12 GB free disk: pipeline streams CSVs in two passes, int32.
- D0.5 Python 3.14 venv; packages: numpy pandas pyarrow lightgbm scikit-learn matplotlib boto3 locust python-docx python-pptx.
- D1.1 Material difference found: ≥5 req/min filter alone gives 2,594 functions (2,518 w/ duration+memory); user's 2,127/2,066 are reproduced exactly when also requiring presence on all 14 days. Adopted that as the selection rule (also required for chronological split).
