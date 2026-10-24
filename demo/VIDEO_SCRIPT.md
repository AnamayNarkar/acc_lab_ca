# CostScale video script (about 9.5 minutes, one presenter)

How to use this file: each segment has the same blocks in the same order.
**SCREEN** = what to have open. **RUN** = the command, in a box (type or paste it). **YOU WILL SEE** = the expected output. **SAY** = the exact words, one sentence per line. **IF IT FAILS** = what to do instead.
Only the segments marked LIVE need AWS. All the others are slides or offline commands.

## What is happening in this video (30 seconds)
- Segments 1 to 5 and 7 to 9 are slides plus one offline command. They use files already on your laptop.
- Segment 6 is the only live part (about 2.5 minutes). It talks to AWS in Mumbai.
- The big experiment (about 2.8 hours) was done earlier. You do **not** repeat it. You show its saved results and say so out loud.

## Before you start recording (do this first, NOT on camera, about 5 minutes)
Do these in order. Each one depends on the one above it.

| Step | Command | Why it is needed | What depends on it |
|---|---|---|---|
| 1 | `make up` | Creates the load balancer, Lambda and an empty server group on AWS (1 to 2 minutes). Costs about $0.024 per hour while it exists. | Everything in segment 6 and `make down`. |
| 2 | `. infra/env.sh && .venv/bin/python infra/set_ip.py` | Allows your laptop's address through the load balancer (the demo scripts also redo this by themselves each time, because the address changes on mobile networks). | Nothing strictly; it is a safety step. |
| 3 | `demo/preflight.sh` | Checks credentials, region and access. It must print `PREFLIGHT PASSED`. | Nothing; it only tells you steps 1 and 2 worked. If it fails, fix that before recording. |
| 4 | Open the browser at AWS CloudWatch, Dashboards, `CostScale`, region ap-south-1, time range last 3 hours. | You will switch to it in segment 6. | Segment 6 only. |

**Slides:** open `ppt/CostScale.pptx` full screen. **Terminal:** one window, big font, in the repository root.

## When to start and stop recording
- **START recording after step 4 is done** (stack is up and preflight passed). Do not record the waiting.
- **Do not wait for slow commands to finish before talking.** Start the command, then read the SAY block while it runs.
- **Segment 6 controller run:** it takes about 2 minutes of traffic, then waits 90 more seconds. When the table with `Aggregated` appears, press **Ctrl+C**. That is enough; `make down` cleans up.
- **Segment 9 `make down`:** start it, then read the closing lines while it runs (it takes a few minutes). **STOP recording when you see the line starting `DOWN:`.** If you do not want to wait, stop recording right after you read the closing lines, then let `make down` finish off camera.
- If you mess up a segment, pause, and redo only that segment. Segments are independent, so you can cut and join them.

## Which commands depend on earlier ones (during recording)
| Command in the video | Needs |
|---|---|
| `show_results.py sim` and `show_results.py live` (segments 5 and 6) | Nothing. Offline. Works any time. |
| `demo/preflight.sh` (segment 6) | Steps 1 and 2 above. |
| `demo/curl.sh` (segment 6) | Step 1 only. |
| `demo/controller.sh` (segment 6) | Step 1 only. Do it after `demo/curl.sh`. |
| `make down` (segment 9) | Step 1 (something must exist to delete). Do it last. |

---

## SEGMENT 1: Introduction   (0:00 to 0:30)

**SCREEN:** Slide 1 (title).

**SAY (read this aloud):**

> Hello.
> We are Anamay Narkar, Ananya Dhiman and Anoushka Nelson, and this is CostScale.
> It is a resource manager on AWS that predicts the workload.
> It decides how much cheap capacity to keep running, and how much to leave to AWS Lambda.
> I will explain the idea, show the simulation results, run a short live demo on AWS in Mumbai, and then be honest about what worked and what did not.


---

## SEGMENT 2: The problem   (0:30 to 1:30)

**SCREEN:** Slide 2, then slide 3 (the cost against dropped-load chart).

**SAY (read this aloud):**

> Cloud compute comes in two forms.
> Servers are cheap per unit of work, but they take about 29 to 31 seconds to start, and you pay for them even when idle.
> Lambda starts instantly and bills only for use, but costs several times more per unit.
> Traffic goes up and down.
> If you size for the peak, you waste money.
> If you only react to load, you are late.
> In our simulation of 101 busy Azure functions, reactive scaling at its cheapest setting costs $37.5k a month and still drops 9.2 percent of the traffic.
> Making it safer is expensive: at a lower utilisation target it costs $87.5k and still drops 6.8 percent.


---

## SEGMENT 3: The idea   (1:30 to 2:20)

**SCREEN:** Slide 4.

**SAY (read this aloud):**

> Our idea is a base plus overflow.
> We keep a base of cheap always-on servers.
> Everything above the base goes to Lambda, and a load balancer splits the traffic.
> How big should the base be?
> This is the newsvendor problem from inventory theory.
> The best base is a quantile of the forecast load.
> The quantile level equals one minus the server cost divided by the Lambda cost for the same unit of work.
> We checked this rule against a brute-force search for every function and hour, and it agrees to within 0.0013 percent.
> The forecast decides the slow thing, how many servers.
> A fast loop every minute decides the traffic split.


---

## SEGMENT 4: Data and model   (2:20 to 3:10)

**SCREEN:** Slide 5, then slide 6.

**SAY (read this aloud):**

> The data is the public Azure Functions 2019 trace: fourteen days of per-minute invocations for 72,359 functions.
> Most functions are barely used.
> So we kept the 2,127 that average at least five requests per minute on all fourteen days.
> From those we took the 101 heavy ones that cost at least fifty dollars a month.
> We price this Azure traffic with AWS prices.
> That is a modelling choice, and the report says so.
> The model is LightGBM quantile regression, predicting the next hour's load.
> It uses the last hour and last six hours, the same hour yesterday, the hour of day, and the function's trigger type.
> Train, validation and test are chronological: days one to ten, eleven to twelve, and thirteen to fourteen.


---

## SEGMENT 5: Simulation results   (3:10 to 4:30)

**SCREEN:** Slide 8, then the terminal.

**NOTE:** Run the command first, then read the SAY block while the table is on screen.

**RUN (type or paste this):**
```
.venv/bin/python demo/show_results.py sim
```

**YOU WILL SEE:** A table of strategies. Key lines: all-Lambda 54,624; reactive u=0.7 37,485 with 9.21% unserved; hybrid_rolling 32,221 with 0.00% unserved; hybrid_ML 32,140. The last line says: ML vs rolling-6h decision cost (test): -0.25%.

**SAY (read this aloud):**

> These are test-period results, scaled to a month.
> The hybrid with a rolling quantile base costs $32.2k.
> That is about 41 percent below all-Lambda and 14 percent below reactive scaling, and it drops nothing.
> Now the honest part.
> Our machine-learning forecaster is only 0.25 percent cheaper than a simple rolling six-hour quantile.
> That is within noise.
> The whole room between that baseline and a perfect hindsight oracle is only 5.4 percent.
> So most of the benefit comes from the newsvendor rule, not from machine learning.
> Also, by an energy estimate based on the Cloud Carbon Footprint method, the hybrid saves money but not energy compared with all-Lambda.
> Running servers draw idle power.

**IF IT FAILS:** If the command fails, stay on slide 8 and read the same words; the numbers are on the slide.

---

## SEGMENT 6: LIVE on AWS and recorded results   (4:30 to 7:00)   <- this is the only part that needs AWS

**Needs:** steps 1 and 2 of the "Before you start" table are done.

### 6a. Introduce it (10 seconds)
**SCREEN:** the terminal.

**SAY (read this aloud):**

> Now a short live demonstration on AWS in Mumbai.
> The full experiment took about two hours forty minutes, so I am not repeating it.
> I will run the system for two minutes, then show the recorded results of the full run.

### 6b. Preflight check (20 seconds)
**RUN:**
```
demo/preflight.sh
```
**YOU WILL SEE:** lines marked `[ OK ]` for credentials, region ap-south-1, EC2, Lambda and ELBv2, and at the end `PREFLIGHT PASSED`.

**SAY (read this aloud):**

> This checks the credentials, the region, and that we can reach the services.

**IF IT FAILS:** say "I will show the recorded results instead", go to 6f, and skip 6c to 6e.

### 6c. One request (20 seconds)
**RUN:**
```
demo/curl.sh
```
**YOU WILL SEE:** `{"backend": "lambda", "took_ms": 400.1}`. The number is about 400. The very first call can take about a second because of a Lambda cold start.

**SAY (read this aloud):**

> There are no servers running yet.
> So the load balancer sent this request to Lambda, and the reply tells us which backend served it.

**IF IT FAILS:** run the same command again. The script loads the credentials and allows your current network address by itself each time.

### 6d. The controller at work (about 2 minutes, do NOT wait for it to finish before talking)
**RUN:**
```
demo/controller.sh
```
**YOU WILL SEE (in this order):** `decision interval (s per trace hour): 20.0 -> arm length 2.0 min`, then `RUN C_ml`, then lines like `[C_ml] hour 0: base 8.5 rps -> desired 1`, `hour 1`, `hour 2`, `hour 3`. Later a Locust table with about 1,250 requests and 0 failures.
**This script only writes into `results/live_demo`, so it cannot overwrite the saved results. It loads the credentials itself, so it works in any terminal.**

**SAY while it runs (read this aloud):**

> The controller forecasts the next hour and sets the number of servers.
> Every moment it reads the live request rate and sets the load balancer weights.
> This run is compressed much more than the real experiment, only for the demonstration.
> So you will see Lambda cover the load while the first server is starting.

**When the table containing `Aggregated` appears, press Ctrl+C.** You do not need the last 90 seconds.

### 6e. The dashboard (30 seconds)
**SCREEN:** switch to the browser, CloudWatch dashboard `CostScale`.

**SAY (read this aloud):**

> The controller publishes its numbers to CloudWatch.
> Here are the forecast, the actual request rate, the base capacity, the share of traffic going to the servers, and the running cost.

**IF THE DASHBOARD IS EMPTY:** set the time range to the last 3 hours and wait a minute. Or say "the numbers appear a minute after the run starts" and move on.

### 6f. The recorded results of the full run (60 seconds)
**SCREEN:** slide 9 and the terminal.

**RUN:**
```
.venv/bin/python demo/show_results.py live
```
**YOU WILL SEE:** one line per arm. A reactive: 23,511 requests, 0.1% errors, p95 566 ms, cost $0.038. B static: 23,688, 0.0%, 517 ms, $0.085. C ML: 23,685, 0.0%, 585 ms, $0.039. D ML plus spike: 30,988, 0.0%, 2618 ms, $0.124.

**SAY (read this aloud):**

> These are the recorded results of the four full runs.
> A is plain reactive scaling.
> B uses a fixed base.
> C uses the machine-learning forecast.
> D is C with a sudden four-times spike.
> On this smooth ramp, reactive scaling and our ML hybrid cost the same, about 0.038 and 0.039 dollars.
> So we did not reproduce the simulated advantage over reactive scaling.
> What the live runs do show is that forecasting beats a fixed base.
> The static base cost 2.2 times as much, because it keeps idle servers.
> Each run was done once, so this is evidence that the design works, not a statistical ranking.

**IF ANY AWS STEP ABOVE FAILED:** do only this step (6f). It works offline.

---

## SEGMENT 7: When the prediction is wrong   (7:00 to 8:00)

**SCREEN:** Slide 10.

**SAY (read this aloud):**

> If the base is too small, the extra load goes to Lambda.
> If it is too large, we pay for idle servers.
> In simulation, a spike of three to five times costs a little more and drops nothing.
> Reactive scaling still drops about 9.5 percent.
> In the live spike run, no request failed, and 48 percent of that hour's requests went to Lambda.
> But 20 percent of requests were slower than our 800 millisecond target.
> There are two reasons.
> Our controller gives each server its full measured capacity, which leaves no headroom.
> And a load balancer weight change takes about 12 seconds to apply.
> A safety factor on capacity would be the first fix.
> We did not test it.
> We also found that our forecaster over-reacts after a spike, because the spiked hour is in its history.


---

## SEGMENT 8: Limitations and future work   (8:00 to 8:50)

**SCREEN:** Slide 11.

**SAY (read this aloud):**

> Here are the limitations.
> We price Azure traffic with AWS prices.
> Server capacity was measured for one synthetic request type on one instance type.
> The live runs are short, compressed, done once, from one laptop.
> Energy is an estimate.
> AWS predictive scaling was not run live, because it needs twenty-four hours of history.
> Storage and networking are out of scope.
> For future work: storage tiering, network cost, a Fargate base, multi-region, forecasts that ignore anomalies, and a true overflow-only router, for example inside the application, instead of weighted routing.


---

## SEGMENT 9: Conclusion and teardown   (8:50 to 9:30)

**SCREEN:** Slide 12, then the terminal.

**NOTE:** Start `make down`, then read the SAY block below while it runs. After the `DOWN:` line appears, say the last two sentences below, then STOP recording.

**RUN (type or paste this):**
```
make down
```

**YOU WILL SEE:** A few minutes of lines: `ASG ...`, `listeners/ALB ...`, `launch template, lambda, role, logs, dashboard ...`, `security groups ...`, `verifying ...`. The last two lines are `direct check (should be 0): {'asg': 0, 'alb': 0, 'instances': 0}` and `DOWN: nothing tagged project=costscale remains (budgets kept).`

**SAY (read this aloud):**

> In conclusion, a newsvendor rule gives a principled base size, and it matches brute force.
> The hybrid serves all traffic in simulation at $32.2k a month, against $54.6k for all-Lambda.
> The machine-learning forecaster adds almost nothing over a rolling quantile.
> And the live runs show the mechanism works, and expose weaknesses we would fix next.
> Finally, we tear everything down.

**IF IT FAILS:** If it prints `LEFTOVERS:`, run `make down` once more. If you cannot wait, stop recording after the closing sentences and run it off camera.

**SAY after the `DOWN:` line appears (read this aloud):**

> Everything we created is deleted, and the tag check confirms nothing is left.
> Thank you.

---

## If something goes wrong while recording
| Problem | What to do |
|---|---|
| Any AWS command fails | Say "I will show the recorded results instead", show slide 9, run only `.venv/bin/python demo/show_results.py live`. |
| `explicit deny in a service control policy` | The organization policy must allow `ap-south-1`. See `demo/RUNBOOK.md`, section 5. |
| `demo/curl.sh` or `demo/controller.sh` fails | Run it again; if it says `No CostScale stack found`, run `make up` first. |
| Dashboard is empty | Set the time range to the last 3 hours and wait a minute. |
| You are running out of time | Skip 6b and 6e. Keep 6c, 6d and 6f. |
