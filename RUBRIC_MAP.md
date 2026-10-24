# Rubric map

Where each rubric item is covered. Section numbers refer to `report/CostScale_Report.docx`; slide numbers to `ppt/CostScale.pptx`; "video" to `demo/VIDEO_SCRIPT.md`.

| Rubric item | Report | Evidence / code | Slides | Video |
|---|---|---|---|---|
| **Problem:** ML-based cloud resource manager that predicts workload and allocates resources | 1 Introduction, 2 Problem statement (Table 1) | `PLAN.md`; whole repository | 2, 3, 4 | seg. 1-2 |
| **Identify input data and features** | 4 Data; 5.3 Features | `data/pipeline.py`, `results/dataset_summary.json`, `forecast/features.py` | 5, 6 | seg. 3 |
| **Choose ML algorithm and prediction horizon** | 5.3 Forecaster (LightGBM quantile regression, next hour) | `forecast/train.py`, `results/forecast_results.json` | 6 | seg. 3 |
| **Design resource allocation / auto-scaling mechanism** | 5.2 Newsvendor rule; 6 System design; 7 Implementation | `controller/controller.py`, `infra/up.py`, `app/` | 4, 7 | seg. 2, 5 |
| **Evaluate: prediction accuracy** | 8.2 (Tables 6-8, Figure 2-3); 8.4 | `results/forecast_results.json` (`accuracy`) | 6, 8 | seg. 4 |
| **Evaluate: utilisation** | 8.3 (Table 9, container utilisation); 8.8 (live CPU) | `results/sim_results.json`, `results/live_results.json` | 8 | seg. 4 |
| **Evaluate: latency** | 7.4 Calibration; 8.8 Live results (p50/p95/p99 by backend) | `results/calibration.json`, `results/live/*/requests.csv`, `results/live_results.json` | 9 | seg. 5-6 |
| **Evaluate: cost** | 8.3, 8.4, 8.7 (sensitivity), 8.8 (live, replay) | `results/sim_results.json`, `results/live_results.json`, `results/prices.json` | 3, 8, 9, 14 | seg. 4, 6 |
| **Evaluate: energy** | 8.6 (estimate, Cloud Carbon Footprint method [9]); 8.8 | `sim/core.py::energy_wh`, `results/live_results.json` | 8 | seg. 4 |
| **Discuss: what happens when the prediction is wrong** | 9 (simulated spike, live arm D, asymmetry, remaining risks) | `results/forecast_results.json` (`spike_test_ec2`), `results/live/D_ml_spike/` | 10 | seg. 7 |
| **Demonstration on any cloud** | 7, 8.8; Appendix A | live AWS stack in ap-south-1 (`make up` ... `make down`), `controller/`, `loadgen/` | 7, 9 | seg. 5-6 |
| **Screencast video** | - | `demo/VIDEO_SCRIPT.md`, `demo/RUNBOOK.md`, `demo/preflight.sh` (recorded by the student) | - | all |
| **Report** | whole document, template format | `report/build_report.py` | - | - |

## Additional deliverables
`ppt/CostScale.pptx` (12 slides + 2 backup, speaker notes), `QNA.md` (15 questions), `README.md`, `DECISIONS.md` (every non-trivial decision with reasons).

## Honest status notes
- The live demo ran on AWS only after an organization policy was edited to allow ap-south-1 (documented in `DECISIONS.md`, D4.1).
- AWS predictive scaling was **not** run live (needs 24 hours of history); the simulator has an emulation, labelled as such.
- Student names, IDs, course and repository fields in the report and slides are `[TO FILL]`.
