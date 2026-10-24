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
- D3.1 Forecaster: 6 LightGBM quantile models (alpha=q) trained on per-minute values (10 sampled minutes/hour), train days 2-10, train-only fit; normalized by app train mean; quantiles interpolated to q* (anchor 0→0); safety margin chosen on validation by decision cost (=1.0). Population: 94 heavy non-timer functions (trigger as categorical feature).
- D3.2 Result: ML beats rolling-6h by ~4% decision cost on test (headroom to oracle ~11.6%). Persistence has better median pinball than LightGBM; LightGBM better on upper quantiles and coverage. Reported plainly.
- D4.0 BLOCKER: org SCP (o-bn2xfz421p) explicitly denies ec2/elbv2/lambda/ssm read calls in ap-south-1 for the admin user. Phase 4 paused; user asked.
- D4.1 SCP block resolved (2026-10-24): account upgraded to Paid plan, advanced features activated (spend limit removed; $120 credits shown on Billing before activation), then org SCP `AdvancedModeRegionRestrictionSecurityControlPolicy` (p-yb4sqghp) RegionFloor edited by the user to allow ap-south-1. Verified EC2/ELB/Lambda/SSM/ASG/CW/IAM calls succeed. Lambda concurrency limit 400. Default VPC vpc-021a3d718ac356506. No NAT/RDS.
- D4.2 Without a hard spend limit, safeguards are: Budgets alerts ($30/60/80), `make down` + tag verification after every experiment, and asking the user before `make up`.
- D4.3 Live workload: heavy HTTP function #643 (daily-profile corr 0.91, minute CV 0.21), 6-h ramp window on day 14 (hour 315), scale factor 6.83 so peak=28 req/s. Live request = fixed 400 ms service time (80 ms CPU burn + 320 ms wait), NOT the trace's 2.5 s mean duration (cost); trace load is mapped via rate only. Stated in report.
- D4.4 Live Lambda = 1769 MB (1 vCPU), python3.12. EC2 base = t3.medium preforking stdlib server, ASG min0/max8, ALB health 5 s. ALB SG allows only the user's IP. No NAT, no RDS, default VPC.
- D4.5 Controller weights use HEALTHY instance capacity (not desired) so traffic isn't sent to instances still booting; BaseCapacity metric logs desired. Arm A = ASG target tracking on CPU 50%, 100% to EC2.
- D4.6 Live arms use integer instance counts (ceil(base_rps/cap)); simulator replay uses the same decisions.
