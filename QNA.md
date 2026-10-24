# Likely examiner questions and honest answers

Numbers are generated from `results/*.json` by `demo/build_qna.py`; regenerate after any re-run.

## 1. Why not just use AWS predictive scaling?

Predictive scaling is a real option and the closest AWS-native comparison, but it was not practical here and it answers a different question. AWS documents that it needs at least 24 hours of metric history before it forecasts, produces an hourly capacity forecast for the next 48 hours updated every 6 hours, and scales the Auto Scaling group at the start of each hour. Each of our live arms lasts 38 minutes, so there is no way to give it history, and we say plainly that we did not run it. It also forecasts capacity for one tier from a utilisation target; it has no pay-per-use overflow tier and no price-ratio rule for how much to hold. In the simulator the seasonal strategy is an emulation in that style, labelled as an emulation and not the AWS algorithm: it drops 4.1% of load at u=0.7 and costs $104.4k because it has no fallback. A fair next step is to run the real thing on a workload with a day of history (future work).

## 2. Why Azure data on AWS?

Because the public production trace we used is the Azure Functions 2019 trace (CC-BY, Shahrad et al., USENIX ATC 2020); we did not evaluate other traces, so we cannot say whether an equivalent AWS one exists. The trace supplies the shape and size of demand, per-minute invocations with durations and memory. We price that demand with AWS prices (retrieved from the AWS Price List API for ap-south-1) and run the live system on AWS, since that is the platform we have access to. This is a modelling assumption and the report states it wherever cost numbers appear; it does not claim that an AWS customer observed this traffic.

## 3. Why an EC2 base and not Fargate?

EC2 was a design decision of the project, and it is the one we could measure: calibration found one t3.medium holds p95 latency at about the service time up to 16 requests per second. Fargate is priced in the simulator only, with an assumed capacity of 4 concurrent requests per 0.5 vCPU task, because we did not run it. With a Fargate base hybrid-rolling costs $30.6k against $32.2k with EC2 on the same load, so the conclusion holds but the saving over all-Lambda is smaller. A Fargate base would remove instance management but add start-up time per task and a higher unit price.

## 4. What happens when the prediction is wrong?

It depends on the direction. If the base is too small, the extra load goes to Lambda: nothing is dropped, cost rises only for the excess, and latency of the overflow is Lambda's. If it is too large, containers sit idle and we pay f per idle unit-minute until the next decision, but no request suffers. In simulation, multiplying one hour per function by 3 to 5 after the forecast was made cost $2.2k to $4.4k extra per month for hybrid-rolling and dropped nothing, while reactive scaling dropped about 9.5% of load regardless. One weakness we found: the ML forecaster reacts worse than the rolling quantile after a spike (x5: $37.8k against $36.6k) because its features include the spiked hour. Live arm D repeated the experiment on AWS.

## 5. Why a quantile, and where does q* come from?

It is the newsvendor problem. In each minute the base costs f per unit whether used or not, and anything above it costs L on Lambda. Minimising expected cost gives f - L times the probability that load exceeds the base equals zero, so the base is the q*-quantile of load with q* = 1 - f/L. If L is not above f, the base is zero. We checked the rule against brute-force search per function and test hour: the rule's cost differs by -0.0013%. We also swept the quantile level on validation and the theoretical level was the cheapest of the levels tried. Note that this checks the rule against hindsight within an hour, not the forecast.

## 6. Does the machine learning actually help?

Barely, and we report it that way. On test, hybrid-ML is 0.25% cheaper than a rolling six-hour quantile, which is within the noise of the assumptions; the whole gap from rolling to the hindsight oracle is only 5.4%, so that is the most any forecaster could win. LightGBM has better pinball loss and coverage at the upper quantiles, but persistence is better at the median and LightGBM under-covers there. Most of the benefit comes from the newsvendor rule and the hybrid design, not from the model. With the originally assumed capacity of 16 the ML gain was 4.1%, so the answer depends on capacity too.

## 7. Does the hybrid save energy?

Not by our estimate. Using the Cloud Carbon Footprint methodology (0.74 W idle to 3.5 W at full load per vCPU, Lambda at 50% utilisation) all-Lambda has the lowest estimate, 1,040 kWh per month, against 3,455 kWh for hybrid-rolling, because containers that are on draw idle power while Lambda only draws power while running. The hybrid is far better than reactive scaling at low utilisation targets (5,901 kWh at u=0.3). This is an estimate, not a measurement, and it is sensitive to the idle-power coefficient.

## 8. How trustworthy is your capacity number?

It is measured but coarse. We stepped the request rate in 4 requests-per-second increments on one t3.medium with one synthetic request type (400 ms service time, 80 ms of it CPU): p95 stayed near 480 ms with no errors up to 16 requests per second and failed at 20, so 16 is a lower bound between 16 and 20. That is 6.4 concurrent requests per instance, not the 16 we first assumed. The result matters: with capacity per unit halved, the hybrid saves only 8% against all-Lambda, and with it 1.5 times higher it saves 55%. Real functions with different CPU needs will differ. An earlier sweep also showed errors at 12 requests per second that were caused by our laptop's network address changing, not capacity; we found that and repeated the calibration.

## 9. Why did you time-compress the live runs, and what is lost?

Each real trace hour would take an hour, and four arms would cost many times more and take most of a day. We compress one trace hour to 375 seconds, which is four times the longest instance launch time we measured (94 s), so instances still have time to come up within a decision interval. What is lost: realistic timing of cold-start recycling, CPU credit behaviour of burstable instances over hours, and any effect that depends on very slow drift. The request rate is also scaled so the peak is 28 requests per second, and the request itself is a fixed 400 ms synthetic job rather than the trace's own durations. Each arm ran once, so we make no statistical claims.

## 10. Why only 'heavy' functions?

Most of the trace is unusable for this purpose: the median function receives 32 invocations a day. A function is heavy if the cheaper of all-Lambda and peak-sized containers costs at least $50 a month on the training days (training days only, to avoid selecting on the test period); 101 functions qualify with the measured capacity. For idle functions Lambda is simply the right answer, and our results say nothing about them. For roughly a quarter of even the heavy functions the hybrid is no cheaper than the best single platform.

## 11. How did you avoid data leakage?

Splits are chronological per function: days 1-10 train, 11-12 validation, 13-14 test. Features only use minutes before the decision time. The safety margin, the quantile-level sweep and all thresholds were chosen on validation; the test set was used for the final comparison. The heavy-function filter uses training days only. One honest detail: the simulator script prints validation and test together, and was re-run after the capacity was measured; no parameter was chosen by looking at test numbers, and the assumed-capacity results are kept for comparison.

## 12. Why does the live system not match the simulator exactly?

The simulator sends only the overflow to Lambda and assumes capacity is available instantly. The ALB splits by percentage, so with random arrivals some requests go to EC2 when it is full and some to Lambda when EC2 has room; instances take 29-31 s to become healthy (once 94 s); and a weight change takes about 12 s to apply. In the live runs the Lambda share differed from the simulator replay by -14.1 to +0.7 percentage points and cost by -39% to +2% (hybrid arms), so the leak is real and measured, not assumed away. Section 8.8 of the report has the reconciliation table.

## 13. What about Lambda cold starts?

We measured them: with only Lambda-served responses, the median latency of cold requests was 814 ms against 610 ms warm (+205 ms). This is small compared with the request's 400 ms service time and it only hits overflow requests; the base serves most traffic. Our first cold-start measurement was wrong because it did not wait for the load balancer's weight change to propagate, so we repeated it. The Lambda function uses 1769 MB because AWS documents that as the memory at which a function has one vCPU.

## 14. What does the live demo cost, and how do you stop it running?

The whole live phase (calibration, four arms and rehearsals; the stack was up for about 3.4 hours) is roughly half a dollar by our own estimate (about 5 instance-hours at $0.0448, about 3.4 hours of load balancer at $0.0239, and about $0.08 of Lambda in the spike arm; AWS's own figure arrives about a day later), expected to be covered by the account's free credits (the Billing page showed $120 of credits at the start); the idle stack costs about $0.024 an hour for the load balancer. Safeguards: every resource is tagged project=costscale, budget alerts exist at $30, $60 and $80, nothing runs without an explicit approval, and `make down` destroys the stack and then checks the tagging API and the ASG, load balancer and instance counts directly. The budget alerts only warn; they do not stop spending.

## 15. What are the main limitations, in one answer?

Azure traffic priced with AWS prices; one synthetic request type on one instance type with a coarse capacity grid; short, time-compressed, single-run live arms from one laptop; energy is an estimate; AWS predictive scaling not run; and the benefit depends on measured capacity and the Lambda price (hybrid-rolling saves 41% against all-Lambda here, 8% if capacity per unit were half). The ML forecaster's contribution is within noise. Storage and networking are out of scope because the trace has no usable data for them (future work). These are all in Section 10 of the report.
