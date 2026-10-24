# CostScale

ML-driven hybrid resource manager on AWS: a cheap always-on **EC2 Auto Scaling base** sized from an hourly **quantile forecast**, with all load above the base sent to **AWS Lambda** through an ALB with weighted target groups. Base size comes from the newsvendor rule: base = the q*-quantile of forecast load, q* = 1 - f/L.

University cloud-computing project. Region `ap-south-1`. Data: Azure Functions 2019 trace (CC-BY, Shahrad et al., USENIX ATC 2020) **priced with AWS prices**.

## Where things are
| Path | What |
|---|---|
| `report/CostScale_Report.docx` (+ `.pdf`) | Final report in the supplied template format |
| `ppt/CostScale.pptx` | Slides with speaker notes |
| `demo/VIDEO_SCRIPT.md`, `demo/RUNBOOK.md`, `demo/preflight.sh` | Screencast script, runbook, preflight check |
| `QNA.md` | 15 likely examiner questions with honest answers |
| `RUBRIC_MAP.md` | Where each rubric item is covered |
| `PLAN.md`, `DECISIONS.md` | Plan and every non-trivial decision, with reasons |
| `results/*.json` | All numbers used anywhere (dataset summary, prices, simulator, forecaster, calibration, live) |

## Reproduce
See `demo/RUNBOOK.md` and Appendix A of the report. In short: `make data`, `make sim`, `make forecast`, then (spends AWS credits) `make up`, `make calibrate`, `make run`, `make down`, then `make report`, `make ppt`.
Credentials live in `.env` (git-ignored) under the names `AWS_ADMIN_IAM_USER_ACCES_KEY` and `AWS_ADMIN_IAM_USER_SECRET_ACCESS_KEY`; `infra/env.sh` maps them to the standard variables without printing them.

## Headline results (see the report for the full tables and caveats)
Numbers are generated into `results/` and quoted in the report; this README points to them instead of copying them, so that they cannot drift.
Honest summary of what was found: the hybrid beats all-Lambda and reactive scaling on cost and unserved load in simulation; the newsvendor rule matches brute force; the ML forecaster adds almost nothing over a rolling six-hour quantile; by an estimate, hybrid saves money but not energy against all-Lambda; the result depends strongly on the measured capacity per container.

## Known limitations
Azure traffic with AWS prices; capacity measured on one synthetic request type on one instance type; short, time-compressed, single-run live arms from one laptop; energy is an estimate; AWS predictive scaling was not run live (it needs 24 h of history); storage and networking are out of scope.
