# CostScale - video script (about 9.5 minutes, one presenter)

**Format.** One person records and reads; the three team members are named at the start. The long experiments were run earlier (about 2.8 hours); in the video they are shown as **recorded results** and you say so out loud. Only about 2.5 minutes are live.
**Slides:** `ppt/CostScale.pptx` (slide numbers below). **Terminal:** one window, large font, in the repository root. **Browser:** AWS console in `ap-south-1`, CloudWatch -> Dashboards -> `CostScale`.
**Shared account:** other people may be using this AWS account. CostScale only creates and deletes `costscale-...` resources; never touch anything with another prefix.

## Before you press record (not on camera, about 5 minutes)
1. `make up` (about 1-2 minutes; creates the load balancer, Lambda, an Auto Scaling Group with 0 instances, and the dashboard). It costs about $0.024/hour while it exists.
2. `. infra/env.sh && .venv/bin/python infra/set_ip.py` (your laptop's public address changes on mobile networks; this refreshes the allow-list).
3. `demo/preflight.sh` must print `PREFLIGHT PASSED`.
4. Open the CloudWatch dashboard `CostScale` in the browser (set the time range to the last 3 hours; metrics from the earlier recorded runs stay visible for 15 days).
5. Rehearse once. Keep the terminal at about 20 lines of visible output.
6. After recording: run `make down` (see the last segment) and keep it from being left running.

---

## 0:00 - 0:30 Introduction  (slide 1)
**Screen:** title slide.
**Say:** "Hello. We are Anamay Narkar, Ananya Dhiman and Anoushka Nelson, and this is CostScale: a resource manager on AWS that predicts the workload and decides how much cheap capacity to keep running and how much to leave to AWS Lambda. I will explain the idea, show the simulation results, run a short live demo on AWS in Mumbai, and then be upfront about what worked and what did not."
**Fallback:** none needed.

## 0:30 - 1:30 The problem  (slides 2 and 3)
**Screen:** slide 2, then slide 3 (the cost against dropped-load chart).
**Say:** "Cloud compute comes in two forms. Servers are cheap per unit of work, but take about 29 to 31 seconds to start in our measurements, and you pay for them even when idle. Lambda starts instantly and bills only for use, but costs several times more per unit. Traffic goes up and down, so if you size for the peak you waste money, and if you only react to load you are late. In our simulation of 101 busy Azure functions, plain reactive scaling at its cheapest setting costs $37.5k a month and still drops 9.2 percent of the traffic. Making it safer makes it much more expensive: at a lower utilisation target it costs $87.5k and still drops 6.8 percent."
**Fallback:** if the slide fails to load, read the same sentences from the script.

## 1:30 - 2:20 The idea  (slide 4)
**Screen:** slide 4.
**Say:** "Our idea is a base plus overflow. We keep a base of cheap always-on servers, and everything above the base goes to Lambda. A load balancer splits the traffic. How big should the base be? This is the newsvendor problem from inventory theory: the best base is a quantile of the forecast load, with the quantile level q-star equal to one minus the server cost divided by the Lambda cost for the same unit of work. We checked this rule against a brute-force search for every function and hour, and it agrees to within 0.0013 percent. The forecast sets the slow decision, how many servers, and a fast loop every minute sets the traffic split."
**Fallback:** none.

## 2:20 - 3:10 Data and model  (slides 5 and 6)
**Screen:** slide 5, then slide 6.
**Say:** "The data is the public Azure Functions 2019 trace, fourteen days of per-minute invocations for 72,359 functions. Most functions are barely used, so we kept the 2,127 that average at least five requests per minute on all fourteen days, and then the 101 heavy ones that cost at least fifty dollars a month. We price this Azure traffic with AWS prices; that is a modelling choice and we say so in the report. The model is LightGBM quantile regression predicting the next hour's load, using the last hour and last six hours, the same hour yesterday, the hour of day and the function's trigger type. Train, validation and test are chronological: days one to ten, eleven to twelve, and thirteen to fourteen."
**Fallback:** none.

## 3:10 - 4:30 Simulation results  (slide 8 and the terminal)
**Screen:** slide 8, then the terminal.
**Command:** `.venv/bin/python demo/show_results.py sim`
**Expected output:** a table of strategies. Key lines: all-Lambda $54,624; reactive u=0.7 $37,485 with 9.21% unserved; hybrid-rolling $32,221 with 0.00% unserved; hybrid-ML $32,140; hybrid-oracle $30,478; last line "ML vs rolling-6h decision cost (test): -0.25%".
**Say:** "These are test-period results, scaled to a month. The hybrid with a rolling quantile base costs $32.2k, about 41 percent below all-Lambda and 14 percent below reactive scaling, and it drops nothing. Now the honest part. Our machine-learning forecaster is only 0.25 percent cheaper than a simple rolling six-hour quantile, which is within noise, and the whole room between the rolling baseline and a perfect hindsight oracle is only 5.4 percent. Most of the benefit comes from the newsvendor rule, not from machine learning. Also, by an energy estimate based on the Cloud Carbon Footprint method, the hybrid saves money but not energy compared with all-Lambda, because running servers draw idle power."
**Fallback:** if the command fails, show the table on slide 8 and report Table 9.

## 4:30 - 7:00 Live demo on AWS  (terminal and browser; about 2.5 minutes live)
**Say first:** "Now a short live demonstration on AWS in Mumbai. The full experiment took about two hours and forty minutes, so I am not repeating that; I will show the system running for two minutes, and then show the recorded results from the full run."
**Step 1 (20 s) - preflight.** Command: `demo/preflight.sh`. Expected: lines marked OK for credentials, region ap-south-1, EC2, Lambda and ELB, then `PREFLIGHT PASSED`. Say: "This checks the credentials, region and that no servers are running."
**Step 2 (20 s) - one request.** Command (copy exactly):
`curl "http://$(.venv/bin/python -c "import json;print(json.load(open('results/cache/infra_state.json'))['alb_dns'])")/work?ms=400&cpu=80"`
Expected: `{"backend": "lambda", "took_ms": 400.1}` (about 400 ms; the first call after a long idle can take about 1 s because of a Lambda cold start). Say: "There are no servers running yet, so the load balancer sends this request to Lambda, and the answer says which backend served it."
**Step 3 (about 2 minutes) - the controller at work.** Command:
`LIVE_OUTDIR=results/live_demo INTERVAL_OVERRIDE=20 .venv/bin/python controller/run_experiments.py C`
Expected: first `decision interval (s per trace hour): 20.0 -> arm length 2.0 min`, then `RUN C_ml`, then lines like `[C_ml] hour 0: base 8.5 rps -> desired 1`, `hour 1: base 6.1 rps -> desired 1`, `hour 2: base 13.2 rps -> desired 1`, `hour 3: base 14.7 rps -> desired 1`, then a Locust summary with about 1,250 requests and 0 failures. (It writes to `results/live_demo`, so it cannot overwrite the recorded results.)
Say while it runs: "The controller forecasts the next hour, sets the number of servers, and every moment reads the live request rate and sets the load balancer weights. This run is compressed far more than in the real experiment, only for the demonstration, so you will see it add a server and Lambda covering the load while that server starts. Switching to the dashboard: forecast, actual rate, base capacity, the traffic share to the servers and the running cost are published to CloudWatch."
**Screen during step 3:** switch to the browser and show the `CostScale` dashboard (Forecast, Actual, BaseCapacity, Weight, RunningCost, and the instance count).
**When the Locust table appears:** press Ctrl+C to skip the 90-second settling wait. (If you do, the Auto Scaling Group is left at its last size; `make down` removes it.)
**Fallback:** if the curl times out, run `. infra/env.sh && .venv/bin/python infra/set_ip.py` and retry (your address changed). If AWS access fails, say "I am showing the recorded run instead", open slide 9 and skip steps 1 to 3.
**Then (slide 9, about 60 s) - recorded results.** Terminal: `.venv/bin/python demo/show_results.py live`
Expected output: one line per arm: A reactive 23,511 requests, 0.1% errors, p95 566 ms, cost $0.038; B static 23,688, 0.0%, 517 ms, $0.085; C ML 23,685, 0.0%, 585 ms, $0.039; D ML plus spike 30,988, 0.0%, 2618 ms, $0.124.
**Say:** "These are the recorded results of the four full runs: A is plain reactive scaling, B uses a fixed base, C uses the machine-learning forecast, and D is C with a sudden four-times spike. On this smooth ramp, reactive scaling and our ML hybrid cost the same, about 0.038 and 0.039 dollars, so we did not reproduce the simulated advantage over reactive scaling. What the live runs do show is that forecasting beats a fixed base: the static base cost 2.2 times as much because it keeps idle servers. Each run was done once, so this is evidence that the design works, not a statistical ranking."

## 7:00 - 8:00 When the prediction is wrong  (slide 10)
**Screen:** slide 10 (and the timeline figure on slide 9 if you want).
**Say:** "If the base is too small, the extra load goes to Lambda; if it is too large, we pay for idle servers. In simulation, a spike of three to five times hurts cost a little and drops nothing, while reactive scaling still drops about 9.5 percent. In the live spike run, no request failed and 48 percent of that hour's requests went to Lambda, but 20 percent of requests were slower than our 800 millisecond target. There are two reasons. Our controller gives each server its full measured capacity, which leaves no headroom, and a load balancer weight change takes about 12 seconds to apply. A safety factor on capacity would be the first fix; we did not test it. We also found that our forecaster over-reacts after a spike, because the spiked hour is in its history."
**Fallback:** none.

## 8:00 - 8:50 Limitations and future work  (slide 11)
**Say:** "Limitations. We price Azure traffic with AWS prices. Server capacity was measured for one synthetic request type on one instance type. The live runs are short, compressed, done once, from one laptop. Energy is an estimate. AWS's own predictive scaling was not run live because it needs twenty-four hours of history. Storage and networking are out of scope. Future work: storage tiering, network cost, a Fargate base, multi-region, forecasts that ignore anomalies, and a true overflow-only router, for example inside the application, instead of weighted routing."

## 8:50 - 9:30 Conclusion and teardown  (slide 12 and the terminal)
**Screen:** slide 12.
**Say:** "In conclusion: a newsvendor rule gives a principled base size and matches brute force; the hybrid serves all traffic in simulation at $32.2k a month against $54.6k for all-Lambda; the machine-learning forecaster adds almost nothing over a rolling quantile; and the live runs show the mechanism works and expose weaknesses we would fix next. Finally, we tear everything down."
**Command:** `make down`
Expected (takes 2 to 4 minutes; cut or speed up this part when editing): lines `ASG ...`, `listeners/ALB ...`, `launch template, lambda, role, logs, dashboard ...`, `security groups ...`, `verifying ...`, then `direct check (should be 0): {'asg': 0, 'alb': 0, 'instances': 0}` and `DOWN: nothing tagged project=costscale remains (budgets kept).`
**Say after it finishes:** "Everything we created is deleted, and the tag check confirms nothing is left. Thank you."
**Fallback:** if `make down` prints `LEFTOVERS:`, run it once more. If you must stop recording first, run it after recording, and read the expected final line from the report instead.

---
### If something goes wrong during recording
| Problem | What to do |
|---|---|
| Any AWS command fails | Say "I will show the recorded results instead", show slide 9 and `.venv/bin/python demo/show_results.py live`. |
| `explicit deny in a service control policy` | The organization policy must list `ap-south-1`; see `demo/RUNBOOK.md` section 5. |
| Request times out | `. infra/env.sh && .venv/bin/python infra/set_ip.py`, then retry. |
| Dashboard empty | Set the range to the last 3 hours; metrics appear about a minute after the controller starts. |
| Out of time | Skip the dashboard and step 1; keep the curl, the controller run and the recorded results. |
