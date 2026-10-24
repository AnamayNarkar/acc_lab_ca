"""Build report/CostScale_Report.docx from results/*.json (every number comes from those files)."""
import json, subprocess, sys, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "report"))
from docxlib import Doc
from docx.shared import Emu
import live_text

R = lambda n: json.load(open(ROOT / "results" / n))
DS, SIM, FC, CAL, NV, WL = R("dataset_summary.json"), R("sim_results.json"), R("forecast_results.json"), R("calibration.json"), R("newsvendor_check.json"), R("live_workload.json")
SIM16, FC16 = R("sim_results_assumed_cap16.json"), R("forecast_results_assumed_cap16.json")
PR = R("prices.json")["values"]
LIVE = R("live_results.json") if (ROOT / "results/live_results.json").exists() else {}
T, V = SIM["ec2"]["test"], SIM["ec2"]["val"]; FIG = ROOT / "report/figures"
k = lambda x: f"${x / 1000:,.1f}k"; usd = lambda x: f"${x:,.0f}"; pct = lambda x, d=1: f"{x:.{d}f}%"
CAPU = SIM["capacity_units"]["ec2"]; SUS = CAL["sustainable_rps_per_instance"]
N_POP = SIM["population"]
INTERVAL = 4 * max(CAL['launch_to_healthy_s'] + [CAL.get('launch_to_healthy_s_first_ever_launch_earlier_run', 0)])

def build(pagemap=None):
    d = Doc(ROOT / "report_template/Skyline_Weather_Devops_Mini_Project_Report.docx")
    cp = d.d.core_properties; cp.title = "CostScale: ML-Driven Hybrid Container and Serverless Resource Management on AWS - Detailed Project Report"; cp.author = "Anamay Narkar, Ananya Dhiman, Anoushka Nelson"; cp.last_modified_by = cp.author; cp.subject = "Cloud computing project report"; cp.keywords = ""; cp.comments = ""
    # ------------------------------------------------ cover
    d.para("", after=40)
    d.para("COSTSCALE", "c", size=22, bold=True, after=14, spacing=1.15)
    d.para("ML-Driven Hybrid Container and Serverless Resource Management on AWS", "c", size=15, after=14, spacing=1.15)
    d.para("Detailed Project Report", "c", size=14, after=40, spacing=1.15)
    d.para("Submitted by", "c", after=8, spacing=1.15)
    for nm in ("Anamay Narkar - 16010123040", "Ananya Dhiman - 16010123041", "Anoushka Nelson - 16010123049"): d.para(nm, "c", size=15, bold=True, after=4, spacing=1.15)
    d.para("", after=30)
    d.para("B.Tech Computer Engineering, Final Year", "c", after=4, spacing=1.15); d.para("K.J. Somaiya School of Engineering, Mumbai", "c", after=4, spacing=1.15)
    d.para("[TO FILL: course name] (cloud computing project)", "c", after=4, spacing=1.15); d.para("October 2026", "c", after=30, spacing=1.15)
    d.para("Repository: github.com/AnamayNarkar/acc_lab_ca", "c", size=11, spacing=1.15)
    # ------------------------------------------------ abstract
    d.h1("Abstract", center=True)
    for t in live_text.abstract(DS, SIM, FC, CAL, LIVE, T, N_POP, CAPU): d.para(t)
    d.para("**Keywords:** cloud resource management, workload prediction, quantile forecasting, newsvendor, AWS Lambda, EC2 Auto Scaling, Application Load Balancer, LightGBM, serverless", align="l")
    # ------------------------------------------------ TOC / lists (filled after layout pass)
    d.h1("Table of contents", center=True)
    toc_at = len(d.d.paragraphs)
    d.h1("List of figures", center=True); lof_at = len(d.d.paragraphs)
    d.h1("List of tables", center=True); lot_at = len(d.d.paragraphs)
    heads_marker = len(d.heads)

    # ------------------------------------------------ 1 Introduction
    d.h1("1. Introduction")
    d.h2("1.1 Background")
    d.para("Cloud providers sell the same computation in two very different ways. Containers and virtual machines are cheap per unit of work but must be provisioned ahead of demand: a new EC2 instance takes tens of seconds to minutes to become useful. Function-as-a-Service platforms such as AWS Lambda react instantly and bill only for the milliseconds used, but each unit of work costs several times more. Production traffic is rarely flat, so an operator who sizes capacity for the peak pays for idle machines, and an operator who relies on pure reactive scaling suffers while capacity catches up with the load.")
    d.para("Workload studies of a large public FaaS platform show why this matters. Shahrad et al. characterise the full Azure Functions workload and report that invocation rates vary across roughly eight orders of magnitude and that most functions are invoked rarely [1]. A small number of busy functions therefore dominate cost, and these are exactly the functions where the choice between a reserved base and pay-per-use matters.")
    d.h2("1.2 Idea in one paragraph")
    d.para("CostScale keeps a **base** of cheap always-on capacity (an EC2 Auto Scaling Group) sized from an hourly **quantile forecast** of load, and sends everything above the base to AWS Lambda. An Application Load Balancer with two weighted target groups splits traffic between the two. Forecasting decides the slow thing (how many instances to run, which needs lead time); a fast per-minute loop only moves routing weights. The size of the base is not a guess: it follows from the newsvendor problem, so the optimal base is a specific quantile of the forecast load whose level depends only on the price ratio between the two platforms.")
    d.h2("1.3 Contributions")
    d.bullet("A cost model and a closed-form rule for the base size (Section 5.2), checked against brute-force search (Section 8.9).")
    d.bullet(f"A trace-driven simulator that replays the Azure Functions 2019 trace [8] with AWS ap-south-1 prices over {N_POP} heavy functions, comparing eight strategies on cost, unserved load, utilisation and an energy estimate.")
    d.bullet("A global LightGBM quantile forecaster [7] with honest baselines, including a plain statement of how much it does and does not help (Section 8.2).")
    d.bullet("A live AWS implementation with a calibration campaign and four experiment arms, reconciled against a simulator replay of the same arms (Section 8.8).")
    d.h2("1.4 Scope")
    d.para("The project covers compute only. Storage and networking costs are out of scope because the public trace contains no usable data for them; they appear as future work. Azure traffic is replayed against **AWS prices**: the Azure trace supplies the shape and size of demand, AWS supplies the price list and the platform on which the live system runs. This is a modelling choice and is stated wherever cost numbers appear.")

    # ------------------------------------------------ 2 Problem statement
    d.h1("2. Problem statement")
    d.para("Given a stream of requests whose rate varies over time, choose at every moment how much capacity to hold in cheap-but-slow-to-provision form (the base) and how much load to send to expensive-but-instant form (overflow), so that total cost is minimised while every request is served within a latency target. Two kinds of error are possible, and they are not symmetric: a base that is too large wastes money continuously, while a base that is too small sends extra load to the costlier platform but does not drop it.")
    d.h2("2.1 What the system must decide")
    d.table(["Question", "CostScale answer", "Where"], [
        ["Input data and features", "Per-minute invocations, average duration and memory of Azure Functions; last-hour and last-6-hour statistics, same hour yesterday, hour of day, trigger, app level", "Sections 4, 5.3"],
        ["ML algorithm", "Global LightGBM quantile regression, one model per quantile", "Section 5.3"],
        ["Prediction horizon", "Next hour, decided at the start of each hour", "Section 5.3"],
        ["Allocation mechanism", "ASG desired capacity from forecast (hourly); ALB weights from observed rate (per minute)", "Section 6"],
        ["Evaluation", "Accuracy, utilisation, latency, cost, energy estimate", "Section 8"],
        ["Wrong prediction", "Spike injection in simulation and a live arm; asymmetric error discussion", "Section 9"]], [4.0, 9.0, 3.0], "Decisions the resource manager makes", align_right_from=9)

    # ------------------------------------------------ 3 Related work
    d.h1("3. Related work")
    d.para("Only sources that were opened and read while preparing this report are cited.")
    d.para("**Serverless workloads.** Shahrad et al. [1] analyse the production Azure Functions workload, find extreme variation in invocation rates, and propose a policy that reduces cold starts while using fewer resources than common industry approaches. Their trace is the data source for this work [8]. Their focus is the keep-alive and pre-warming of functions inside a serverless platform, whereas CostScale asks the inverse question: when is it cheaper to leave serverless for provisioned capacity, and how much?")
    d.para("**Predictive autoscaling with serverless overflow.** MArk [2] is a machine-learning inference serving system built on AWS. According to the paper's abstract it uses predictive autoscaling to hide provisioning latency at low cost, and uses more flexible but pricier serverless instances to absorb occasional spikes that are hard to predict.")
    d.para("**Hybrid VM and serverless designs.** Several works combine provisioned VMs with serverless functions, and some are closer to CostScale than MArk. LIBRA [10] (IEEE IC2E 2021) provisions both VM and serverless capacity to minimise cost under SLAs; its abstract reports more than 85% fewer SLA violations and up to 53% lower cost on real traces, in simulation and on AWS, and does not give the routing algorithm. Spandana [11] (arXiv preprint, 2026) places a lightweight controller next to each application VM that decides **per request** whether to serve it locally or forward it to a FaaS layer such as AWS Lambda, keeping requests that can meet the SLO on the VM; its abstract reports 76-86% CPU utilisation and 5-44% lower cost than three baselines. Flare [12] (arXiv preprint, 2026) runs steady traffic on VMs and shifts the excess load of overloaded microservices to serverless. We read only the abstracts of [10]-[12], not the full papers. CostScale therefore does not claim that a VM base with serverless overflow is new. What it adds, as far as the abstracts show, is an explicit price-ratio rule for the size of the base (the newsvendor quantile of Section 5.2) and a measured comparison with reactive scaling on a public production trace plus a live AWS check. Unlike Spandana, it routes by weighted target groups rather than per request, which is the weaker mechanism (Section 8.8).")
    d.para("**Provider predictive scaling.** Amazon EC2 Auto Scaling offers predictive scaling [3]. The documentation states that the monitored metric needs at least 24 hours of data, that the service analyses up to 14 days of history, generates an hourly forecast of capacity for the next 48 hours updated every 6 hours, and by default scales at the start of each hour. It forecasts capacity from a utilisation target and does not consider a pay-per-use overflow tier. We did not run it live because it needs 24 hours of history before it forecasts (Section 7.5); the simulator contains an emulation in the same spirit, which is explicitly **not** the AWS algorithm.")
    d.para("**Newsvendor theory.** The newsvendor model chooses an order quantity before demand is known. In critical-fractile form the optimum is a quantile of the demand distribution whose level balances the cost of too little against the cost of too much [6]. We apply it per minute of load: the base is bought in advance, the overflow is bought on demand at a higher price.")
    d.para("**Forecasting and energy.** LightGBM [7] is a gradient-boosted decision tree implementation; its quantile objective gives one conditional quantile per model. For the energy estimate we follow the Cloud Carbon Footprint methodology [9], which converts vCPU-hours and utilisation into watt-hours and treats Lambda through allocated memory.")

    # ------------------------------------------------ 4 Data
    d.h1("4. Data")
    d.h2("4.1 Dataset")
    d.para(f"We use the Azure Functions 2019 trace [8], released under CC-BY, which accompanies [1]. It contains 14 days of per-minute invocation counts per function with trigger type, per-function execution-time statistics (excluding cold starts) and per-application allocated memory for 12 of the 14 days. The trace covers {DS['functions_total_distinct']:,} distinct functions in total; day 1 alone has {DS['day1_functions']:,}, and {DS['functions_on_all_14_days']:,} appear on all 14 days. The median function receives only {DS['median_invocations_per_day_day1']:.0f} invocations per day on day 1, so most of the data is unusable for forecasting and must be filtered.")
    d.h2("4.2 Filtering and joins")
    d.para(f"Loading all 14 days of all functions at once exhausts memory on the development machine, so the pipeline works in two passes: the first streams every file and computes per-function totals; the second loads only the selected functions as 32-bit integers. A function is selected when it is present on all 14 days (required for a chronological split) and averages at least 5 requests per minute over the 14 days. This gives {DS['functions_avg_ge_5rpm_all14days']:,} functions; {DS['functions_with_traffic_duration_memory']:,} also have duration and memory data. Duration is the Count-weighted mean over days and memory is the SampleCount-weighted mean per application.")
    d.para(f"One difference from the preliminary exploration is documented here for transparency. Applying the 5 requests per minute rule alone gives {DS['functions_avg_ge_5rpm_any_presence']:,} functions; the {DS['functions_avg_ge_5rpm_all14days']:,} and {DS['functions_with_traffic_duration_memory']:,} figures are reproduced exactly only when presence on all 14 days is also required, so that is the rule used.")
    d.table(["Quantity", "Value"], [
        ["Distinct functions in 14 days", f"{DS['functions_total_distinct']:,}"], ["Functions on day 1", f"{DS['day1_functions']:,}"],
        ["Functions present on all 14 days", f"{DS['functions_on_all_14_days']:,}"], ["Median invocations/day (day 1)", f"{DS['median_invocations_per_day_day1']:.0f}"],
        ["Average >= 5 req/min, present all 14 days", f"{DS['functions_avg_ge_5rpm_all14days']:,}"], ["... with traffic + duration + memory", f"{DS['functions_with_traffic_duration_memory']:,}"],
        ["Heavy functions (Section 4.4, measured capacity)", f"{DS['heavy_functions']}"],
        ["Heavy by trigger", ", ".join(f"{a} {b}" for a, b in DS["heavy_by_trigger"].items() if b)]], [9.5, 6.5], "Dataset funnel", align_right_from=1)
    d.h2("4.3 Load model and split")
    d.para("Offered load is expressed as concurrency: c(t) = invocations per minute / 60 x average duration in seconds. Timer-triggered functions are periodic rather than diurnal and are excluded from forecasting. The split is chronological per function: days 1-10 train, days 11-12 validation, days 13-14 test. All thresholds and hyperparameters are chosen on validation only, and the test period is evaluated once at the end.")
    d.h2("4.4 Heavy functions")
    d.para(f"A function is heavy when the cheaper of its two single-platform options costs at least $50 per month on the **training** days: min(all-Lambda, containers sized to the training peak x 1.2). Using only training days avoids selection leakage. With the measured container capacity this yields {DS['heavy_functions']} functions, all non-timer, and these form the simulated population ({N_POP} functions). The preliminary exploration, run with the assumed capacity, found 96; the count depends on the capacity per container, and the earlier assumed-capacity run of this pipeline gave {SIM16['population']}.")

    # ------------------------------------------------ 5 Methodology
    d.h1("5. Methodology")
    d.h2("5.1 Cost model")
    d.para(f"Prices were retrieved from the AWS Price List API for ap-south-1 on {R('prices.json')['retrieved']}: Lambda ${PR['lambda_gbs']:.7f} per GB-second (tier 1) and ${PR['lambda_req']:.7f} per request; EC2 t3.medium ${PR['t3_medium_h']:.4f} per hour; Fargate ${PR['fargate_vcpu_h']:.5f} per vCPU-hour and ${PR['fargate_gb_h']:.6f} per GB-hour. **Azure traffic is priced with AWS prices.** Lambda memory is max(128 MB, application memory). The Lambda cost of one concurrent second is GB x price per GB-second + price per request / average duration in seconds.")
    d.para(f"Container capacity: the measured capacity of one t3.medium is {SUS:.0f} requests per second at the latency target (Section 7.4), which at the live service time of 0.4 s is {CAPU:.1f} concurrent requests. The initial assumption was 16, so the simulator was re-run with the measured value; the Fargate figure (4 concurrent requests per 0.5 vCPU / 1 GB task) is still the assumed one because Fargate was not run live. Container cost per capacity-unit-minute is f; Lambda cost to serve one unit of load for one minute is L.")
    d.h2("5.2 Newsvendor rule for the base")
    d.para("In every minute the load c is random. A base of b capacity units costs f per unit-minute whether used or not; load above b is served by Lambda at L per unit-minute. The expected cost f b + L E[(c - b)+] is convex in b. Setting its derivative to zero gives f - L P(c > b) = 0, so the optimal base is **b* = F^-1(q*) with q* = 1 - f / L**, the q*-quantile of the load distribution. If L <= f the base is zero, because containers are never cheaper than overflow. The cost ratio therefore fixes the quantile and the forecaster only needs to supply that quantile of the next hour. This is the critical-fractile result of the newsvendor model [6].")
    d.para(f"With the measured capacity the median q* across the simulated functions is {SIM['qstar_stats']['median']:.2f} and no function has q* = 0. A direct sweep of the quantile level on validation (Table 12) shows that the theoretical level is the cheapest of the levels tried.")
    d.h2("5.3 Forecaster")
    d.bullet("**Target.** At the start of each hour, for each function, the q-quantile of per-minute concurrency over the next hour, for q in {0.5, 0.7, 0.8, 0.9, 0.95, 0.99}. The base uses q* by linear interpolation between these anchors (with 0 anchored at 0).")
    d.bullet("**Model.** One global LightGBM model per quantile [7], objective quantile, trained across all simulated functions with load normalised by each function's training-period mean. Trigger type is a categorical feature. The model trains on ten sampled minutes per hour and sees training days 2-10.")
    d.bullet("**Features** (all from minutes before the decision time): mean, maximum and 90th percentile of the last 60 and last 360 minutes; mean and 90th percentile of the same hour yesterday; sine and cosine of hour of day; trigger type; log of the function's mean level.")
    d.bullet(f"**Safety margin.** A multiplier on the base, chosen on validation by minimising decision cost rather than error. The chosen value is {FC['margin_chosen']:.1f}, i.e. no extra margin.")
    d.bullet("**Baselines.** Persistence (quantile of the last hour), rolling 6 hours (quantile of the previous 360 minutes), seasonal naive (same hour yesterday), and a static quantile of the training period.")
    d.h2("5.4 Strategies compared")
    d.table(["#", "Strategy", "Definition"], [
        ["1", "All-Lambda", "Everything on Lambda"], ["2", "Peak-sized", "Containers sized to training peak x 1.2; no fallback"],
        ["3", "Reactive", "Capacity = load seen 5 min ago / target utilisation u; u in {0.7, 0.5, 0.3, 0.2, 0.1}; no fallback"],
        ["4", "Seasonal (emulation)", "Capacity from the same hour on the previous 3 days / u. An emulation in the style of predictive scaling, not the AWS algorithm"],
        ["5", "Hybrid-static", "Base = q* quantile of training load, constant"], ["6", "Hybrid-rolling", "Base = q* quantile of previous 6 h, reset hourly"],
        ["7", "Hybrid-ML", "Base = LightGBM forecast at q*"], ["8", "Hybrid-oracle", "Base = q* quantile of the actual hour (lower bound)"]],
        [1.0, 4.0, 11.0], "Strategies in the simulator", align_right_from=9)
    d.para("In a hybrid, **overflow** is load above base capacity and is billed on Lambda. **Unserved load** is load above container capacity with no Lambda fallback; it is non-zero only for strategies 2, 3 and 4. Each strategy is priced with an EC2 base and, as an alternative, with a Fargate base.")

    # ------------------------------------------------ 6 System design
    d.h1("6. System design")
    d.h2("6.1 Architecture")
    d.para("Clients send HTTP requests to an internet-facing Application Load Balancer. Its listener forwards to two target groups with weights between 0 and 999: requests are distributed in proportion to the weights [5]. tg-ec2 contains an Auto Scaling Group of t3.medium instances (the base); tg-lambda contains one Lambda function (the overflow). A local controller reads forecasts and observed load and drives both the ASG and the weights; custom metrics go to CloudWatch (Figure 1).")
    d.figure(FIG / "architecture.png", 14.5, "CostScale architecture")
    d.h2("6.2 Two time scales")
    d.para("Instances need lead time, so instance count is set from a forecast, once per decision interval. Routing weights are cheap to change, so they are recomputed every minute from the observed request rate: the EC2 share is w = min(1, base capacity / observed rate), with integer weights 0-999 and the Lambda weight equal to 999 minus the EC2 weight. The base capacity used in this formula is the capacity of instances that are healthy in the target group, so traffic is never sent to an instance that is still booting.")
    d.h2("6.3 Controller algorithm")
    d.code(["every decision interval (start of trace hour h):",
            "    Q <- forecast quantiles of next hour (LightGBM) ; q* <- 1 - f/L",
            "    base_rps <- interp(q*, Q) ; n <- ceil(base_rps / cap_per_instance)",
            "    ASG.set_desired_capacity(n)",
            "every tick (one trace minute):",
            "    obs <- observed request rate ; cap <- healthy_instances * cap_per_instance",
            "    w_ec2 <- round(999 * min(1, cap / obs)) ; w_lambda <- 999 - w_ec2",
            "    ALB.modify_listener(weights) ; publish Forecast, Actual, BaseCapacity, Weight, RunningCost"])
    d.para("The ALB splits by percentage and cannot send only the overflow to Lambda, so with random arrivals some requests go to EC2 when EC2 is already full and some go to Lambda when EC2 has room. The live system therefore leaks relative to the simulator; the size of this sim-to-real gap is measured in Section 8.8.")

    # ------------------------------------------------ 7 Implementation
    d.h1("7. Implementation")
    d.h2("7.1 Repository and tooling")
    d.para("Python 3 with a virtual environment; boto3 for AWS (OpenTofu was not installed and installing it was declined, so infrastructure is created and destroyed by `infra/up.py` and `infra/down.py`). Every AWS resource is tagged `project=costscale`; the default VPC is used; there is no NAT gateway and no RDS. AWS Budgets alerts are set at $30, $60 and $80. By our own estimate the whole live phase cost roughly half a dollar (about 5 instance-hours, about 3.4 hours of load balancer and under $0.1 of Lambda); AWS's billing figure lags by about a day and was not available when this report was written.")
    d.table(["Directory", "Content"], [["data/", "two-pass pipeline (`pipeline.py`), processed arrays (not committed)"], ["sim/", "cost model, strategies, sensitivity, newsvendor check"],
        ["forecast/", "features and LightGBM training, baselines, spike test"], ["infra/", "boto3 create/destroy, tag verification, spend report"],
        ["app/", "HTTP service and Lambda handler sharing one work module"], ["loadgen/", "calibration, workload selection, Locust file"],
        ["controller/", "forecast-driven controller, experiment runner, analysis"], ["results/, report/, ppt/, demo/", "outputs and deliverables"]], [4.5, 11.5], "Repository layout", align_right_from=9)
    d.h2("7.2 Application")
    d.para(f"The service exposes `/work?ms=N&cpu=C`: it burns C milliseconds of calibrated single-core CPU and waits for the rest of N milliseconds, and returns the name of the backend that served it. The EC2 version is a pre-forking standard-library HTTP server with one worker per vCPU, started by user-data; the Lambda version is the same module behind an ALB handler, configured with 1769 MB. At that size a function has the equivalent of one vCPU [4]. The live request uses N = {CAL['service_ms']} ms with C = {CAL['cpu_ms']} ms. This is a fixed service time chosen for cost, not the trace's own average duration; the trace is replayed in rate only.")
    d.h2("7.3 Workload for the live demo")
    d.para(f"One heavy HTTP function with a clear daily pattern and moderate burstiness was chosen by score: the highest day-to-day correlation of its hourly profile among the heavy HTTP functions (r = {WL['daily_profile_corr']:.2f}) with a minute-level coefficient of variation between 0.1 and 0.6 (here {WL['minute_cv']:.2f}). A six-hour window on day 14 with the largest rise in load was selected; the rate was scaled by a factor of {WL['scale_factor']:.2f} so that the peak is {WL['live_peak_rps']:.0f} requests per second. The window is time-compressed so that one trace hour lasts {INTERVAL:.0f} seconds, which is four times the longest measured instance launch time ({INTERVAL/4:.1f} s); an arm therefore lasts {6*INTERVAL/60:.1f} minutes.")
    d.h2("7.4 Calibration")
    ls = CAL["lambda_cold_warm_v2"]
    d.table(["Quantity", "Measured value"], [
        ["Sustainable rate per t3.medium (p95 <= 800 ms, no errors)", f"{SUS:.0f} req/s ({CAPU:.1f} concurrent requests)"],
        ["Capacity sweep (rps: p95 ms, error rate)", "; ".join(f"{s['rps']}: {s['p95']:.0f}, {100*s['error_rate']:.0f}%" for s in CAL["capacity_steps"])],
        ["ASG launch to healthy", f"{CAL['launch_to_healthy_s'][0]:.1f} s and {CAL['launch_to_healthy_s'][1]:.1f} s from an empty group; {CAL.get('launch_to_healthy_s_first_ever_launch_earlier_run', float('nan')):.1f} s on the very first launch of an earlier run"],
        ["Lambda cold vs warm latency (median)", f"{ls['cold_median']:.0f} ms vs {ls['warm_median']:.0f} ms (+{ls['cold_overhead_ms_median']:.0f} ms); n = {ls['cold_n']} cold, {ls['warm_n']} warm, Lambda-served only"],
        ["ALB weight-update propagation", ", ".join(f"{x:.1f}" for x in CAL["weight_propagation_s"]) + " s (three trials)"]],
        [8.0, 8.0], "Calibration results", align_right_from=9)
    d.para("Two measurement problems were found and fixed during calibration, and are noted because they affect how far the numbers can be trusted. First, an initial capacity sweep showed errors at 12 requests per second that were really connection time-outs: the laptop's network address changed during the run and the load balancer's security group no longer matched it. A watchdog now keeps the security group pointed at the current address. Second, the first Lambda cold-start measurement did not wait for the load balancer's weight change to propagate (about 12 s), so cold and warm samples were mixed with EC2 responses; it was repeated with a 25 s wait and a filter that keeps only Lambda-served responses. The capacity figure comes from a coarse 4 requests-per-second grid: it is a lower bound between 16 and 20 requests per second.")
    d.h2("7.5 What was not run live")
    d.para("AWS predictive scaling [3] was not run, because it needs 24 hours of metric history before it forecasts and each experiment arm lasts under 40 minutes. The seasonal strategy in the simulator is an emulation of that style of policy, not the AWS algorithm. Fargate was priced in the simulator only.")

    # ------------------------------------------------ 8 Evaluation
    d.h1("8. Evaluation")
    d.h2("8.1 Set-up")
    d.para(f"Simulation results are for the {N_POP} heavy functions, test days 13-14 scaled to 30 days, with the EC2 base and the measured capacity, unless stated. Costs are in US dollars at AWS ap-south-1 prices with Azure traffic. Test data were touched once for the final comparison; the quantile level, margin and all strategy parameters were chosen or fixed on validation. The sweeps over u for strategies 3 and 4 are reported in full rather than selecting one value.")
    d.h2("8.2 Prediction accuracy")
    acc = FC["accuracy"]; qs = ["0.5", "0.7", "0.8", "0.9", "0.95", "0.99"]
    d.para("Accuracy is reported on test days, normalised by each function's training mean. Pinball loss is computed against the 60 per-minute values of each forecast hour; coverage is the share of minutes at or below the forecast.")
    d.table(["q", "LightGBM", "Persistence", "Rolling 6 h", "Seasonal naive", "Static train"],
            [[q] + [f"{acc[m]['test'][q]['pinball_norm']:.3f}" for m in ("lightgbm", "persistence", "rolling6h", "seasonal_naive", "static_train")] for q in qs],
            [1.6, 2.8, 2.8, 2.8, 3.0, 2.8], "Pinball loss on test (normalised; lower is better)", align_right_from=1)
    d.table(["q", "LightGBM", "Persistence", "Rolling 6 h", "Seasonal naive", "Static train"],
            [[q] + [f"{acc[m]['test'][q]['coverage']:.3f}" for m in ("lightgbm", "persistence", "rolling6h", "seasonal_naive", "static_train")] for q in qs],
            [1.6, 2.8, 2.8, 2.8, 3.0, 2.8], "Coverage on test (ideal equals q)", align_right_from=1)
    d.table(["q", "MAE LightGBM", "MAE rolling 6 h"], [[q, f"{acc['lightgbm']['test'][q]['mae_norm']:.3f}", f"{acc['rolling6h']['test'][q]['mae_norm']:.3f}"] for q in qs],
            [2.0, 4.0, 4.0], "Mean absolute error of the forecast against the realised hourly quantile (test, normalised)", align_right_from=1)
    lg, rl, ps = acc["lightgbm"]["test"], acc["rolling6h"]["test"], acc["persistence"]["test"]
    better = [q for q in qs if lg[q]["pinball_norm"] < min(rl[q]["pinball_norm"], ps[q]["pinball_norm"])]
    d.para(f"LightGBM has the lowest pinball loss at q = {', '.join(better)} and its coverage tracks the nominal level at the upper quantiles (for example {lg['0.9']['coverage']:.3f} at q = 0.9 against {rl['0.9']['coverage']:.3f} for rolling 6 h and {ps['0.9']['coverage']:.3f} for persistence). At the median, persistence has the lower pinball loss ({ps['0.5']['pinball_norm']:.3f} against {lg['0.5']['pinball_norm']:.3f}), and LightGBM under-covers there ({lg['0.5']['coverage']:.3f}). The 0.99 mean absolute error of LightGBM ({acc['lightgbm']['test']['0.99']['mae_norm']:.2f}) is slightly worse than rolling 6 h ({acc['rolling6h']['test']['0.99']['mae_norm']:.2f}), so the gain is not uniform. Figure 2 shows how the coverage curves compare.")
    d.figure(FIG / "quantile_coverage.png", 10.5, "Observed coverage against nominal quantile on test days")
    d.figure(FIG / "forecast_vs_actual.png", 14.5, "Hourly base capacity for the live-demo function: forecasts against the realised hourly quantile")
    d.h2("8.3 Decision cost, utilisation and unserved load")
    rows = []
    names = {"1_all_lambda": "1 All-Lambda", "2_peak_x1.2": "2 Peak-sized x1.2", "3_reactive_u0.7": "3 Reactive u=0.7", "3_reactive_u0.5": "3 Reactive u=0.5", "3_reactive_u0.3": "3 Reactive u=0.3",
             "3_reactive_u0.2": "3 Reactive u=0.2", "3_reactive_u0.1": "3 Reactive u=0.1", "4_seasonal_u0.7": "4 Seasonal u=0.7", "4_seasonal_u0.5": "4 Seasonal u=0.5", "4_seasonal_u0.3": "4 Seasonal u=0.3",
             "5_hybrid_static": "5 Hybrid-static", "6_hybrid_rolling": "6 Hybrid-rolling", "7_hybrid_ML": "7 Hybrid-ML", "8_hybrid_oracle": "8 Hybrid-oracle"}
    for key, nm in names.items():
        v = T[key]; u = "n/a" if v["util"] != v["util"] else f"{v['util']:.2f}"
        rows.append([nm, usd(v["cost"]), pct(v["unserved_pct"], 2), u, f"{v['lambda_share']:.2f}", f"{v['energy_wh'] / 1000:,.0f}"])
    d.table(["Strategy", "Cost / month", "Unserved", "Container util.", "Lambda share", "Energy kWh/mo"], rows, [4.6, 2.7, 2.2, 2.6, 2.3, 2.6], "Test results, EC2 base (measured capacity)")
    d.figure(FIG / "cost_comparison.png", 14.5, "Monthly cost by strategy; hatching marks strategies that drop load")
    rl_, ml_, orc_, st_, al_, re7 = T["6_hybrid_rolling"]["cost"], T["7_hybrid_ML"]["cost"], T["8_hybrid_oracle"]["cost"], T["5_hybrid_static"]["cost"], T["1_all_lambda"]["cost"], T["3_reactive_u0.7"]
    d.para(f"The hybrids are the only strategies with no unserved load and the lowest cost. Hybrid-rolling costs {k(rl_)} per month, {100*(1-rl_/al_):.0f}% below all-Lambda ({k(al_)}) and {100*(1-rl_/re7['cost']):.0f}% below the cheapest reactive setting (u = 0.7, {k(re7['cost'])}), which also drops {re7['unserved_pct']:.1f}% of the load. Lowering u reduces unserved load only slowly and raises cost steeply: u = 0.3 costs {k(T['3_reactive_u0.3']['cost'])} and still drops {T['3_reactive_u0.3']['unserved_pct']:.1f}%, which is consistent with a controller that sizes capacity from load five minutes old and has no fallback for load that arrives in the meantime. The seasonal emulation drops less load than reactive but costs more at every u, because capacity set from the past maximum of the same hour is high all hour. Peak-sizing costs {k(T['2_peak_x1.2']['cost'])} and still drops {T['2_peak_x1.2']['unserved_pct']:.2f}% on test days because the test peak exceeded the training peak.")
    d.figure(FIG / "unserved_vs_cost.png", 12.5, "Cost against unserved load for the reactive and seasonal sweeps, and the hybrids")
    d.h2("8.4 Does the ML forecaster help?")
    dc, dv = FC["decision_cost_test_ec2"], V
    d.table(["Hybrid variant", "Validation cost / month", "Test cost / month", "Test Lambda share"], [
        ["Static quantile (5)", usd(V["5_hybrid_static"]["cost"]), usd(dc["hybrid_static"]["cost"]), f"{dc['hybrid_static']['lambda_share']:.2f}"],
        ["Rolling 6 h (6)", usd(FC["rolling6h_val_cost_monthly"]), usd(dc["hybrid_rolling"]["cost"]), f"{dc['hybrid_rolling']['lambda_share']:.2f}"],
        ["LightGBM (7)", usd(V["7_hybrid_ML"]["cost"]), usd(dc["hybrid_ML"]["cost"]), f"{dc['hybrid_ML']['lambda_share']:.2f}"],
        ["Oracle (8)", usd(V["8_hybrid_oracle"]["cost"]), usd(dc["hybrid_oracle"]["cost"]), f"{dc['hybrid_oracle']['lambda_share']:.2f}"]],
        [4.6, 4.0, 3.6, 3.6], "Decision cost of the hybrid base policies")
    vr = (V["7_hybrid_ML"]["cost"] - FC["rolling6h_val_cost_monthly"]) / FC["rolling6h_val_cost_monthly"] * 100
    d.para(f"**The ML forecaster does not meaningfully beat the rolling 6-hour baseline.** On validation LightGBM is {abs(vr):.1f}% {'cheaper' if vr < 0 else 'more expensive'} than rolling 6 h; on test it is {abs(FC['ml_vs_rolling_pct']):.2f}% {'cheaper' if FC['ml_vs_rolling_pct'] < 0 else 'more expensive'}, a difference well inside what the sweeps over assumptions move. The whole gap from rolling 6 h to the hindsight oracle is only {FC['headroom_rolling_to_oracle_pct']:.1f}% of cost, which is the most any forecaster could gain on this population. Better accuracy at the upper quantiles shows up as a small gain that shrinks from {abs(vr):.1f}% on validation to {abs(FC['ml_vs_rolling_pct']):.2f}% on test, and on test the ML base sends a larger share of load to Lambda ({dc['hybrid_ML']['lambda_share']:.2f} against {dc['hybrid_rolling']['lambda_share']:.2f}). Under the originally assumed capacity of 16 the same comparison gave {FC16['ml_vs_rolling_pct']:.1f}% with {FC16['headroom_rolling_to_oracle_pct']:.1f}% headroom, which is consistent with the preliminary exploration that suggested about 10% headroom. The practical conclusion is that the newsvendor rule, not the sophistication of the forecaster, delivers most of the benefit; a rolling quantile captures nearly all of it.")
    d.h2("8.5 Latency")
    d.para("The simulator has no latency model. Latency is measured live (Section 8.8). The calibration gives the building blocks: an EC2 instance holds p95 near the service time up to its capacity and degrades sharply beyond it, and Lambda adds a cold-start overhead (Table 5).")
    d.h2("8.6 Energy (estimate)")
    e = {kk: v["energy_wh"] / 1000 for kk, v in T.items()}
    d.para(f"Energy is estimated with the Cloud Carbon Footprint methodology [9]: watts per vCPU = 0.74 + utilisation x (3.5 - 0.74), multiplied by vCPU-hours; Lambda uses vCPUs = memory in MB / 1792 at 50% utilisation. This is an **estimate**, not a measurement. On this basis all-Lambda uses the least energy ({e['1_all_lambda']:,.0f} kWh per month), the hybrids use about {e['6_hybrid_rolling']:,.0f} kWh, and the reactive strategies use {e['3_reactive_u0.7']:,.0f} kWh or more. The reason is that the methodology charges an idle vCPU {0.74:.2f} W, so any strategy that keeps containers running pays for idle time that Lambda does not. The hybrid therefore saves money but, by this estimate, **not** energy relative to all-Lambda; it does use far less energy than reactive scaling at low u. The result is sensitive to the idle-power coefficient and to treating Lambda at 50% utilisation.")
    d.h2("8.7 Per-function distribution and sensitivity")
    pa = SIM["per_app_ratio_rolling_vs_best_single"]
    d.para(f"Across functions, the ratio of hybrid-rolling cost to the best single platform has median {pa['p50']:.2f} (5th percentile {pa['p5']:.2f}, 95th percentile {pa['p95']:.2f}); hybrid-rolling is cheaper than all-Lambda for {100*SIM['per_app_frac_hybrid_cheaper_than_all_lambda']:.0f}% of functions. For roughly a quarter of the functions (75th percentile ratio {pa['p75']:.2f}) the hybrid is no cheaper than the best single platform, so the saving comes from the other three quarters; we did not analyse which load characteristics separate the two groups.")
    sens = SIM["sensitivity_test"]
    srows = [["Baseline", usd(al_), usd(T["3_reactive_u0.3"]["cost"]), usd(rl_), usd(orc_)]]
    labels = {"cap_x0.5": "Capacity per unit x0.5", "cap_x1.5": "Capacity per unit x1.5", "lambda_price_x0.5": "Lambda price x0.5", "lambda_price_x2": "Lambda price x2",
              "ec2_savings_-30pct_hypothetical": "EC2 price -30% (hypothetical)", "fargate_base": "Fargate base"}
    for kk, lab in labels.items():
        s = sens[kk]; srows.append([lab, usd(s["1_all_lambda"]["cost"]), usd(s["3_reactive_u0.3"]["cost"]), usd(s["6_hybrid_rolling"]["cost"]), usd(s["8_hybrid_oracle"]["cost"])])
    s = sens["integer_instances_per_app"]; srows.append(["Whole instances per function", "-", "-", usd(s["6_hybrid_rolling"]["cost"]), usd(s["8_hybrid_oracle"]["cost"])])
    d.table(["Scenario (test, monthly)", "All-Lambda", "Reactive u=0.3", "Hybrid-rolling", "Hybrid-oracle"], srows, [5.6, 2.6, 2.8, 2.8, 2.6], "Sensitivity of cost to assumptions")
    d.figure(FIG / "sensitivity.png", 12.5, "Hybrid-rolling cost relative to all-Lambda under each scenario")
    sw = SIM["qstar_sweep_rolling_val_cost"]
    d.table(["Quantile level offset from q*", "Validation cost / month"], [[kk, usd(vv)] for kk, vv in sw.items()], [6.0, 6.0], "Quantile-level sweep for hybrid-rolling on validation (offset 0 = theoretical q*)")
    d.para(f"The hybrid advantage is not unconditional. If a container unit carries half as much load as measured, hybrid-rolling saves only {100*(1-sens['cap_x0.5']['6_hybrid_rolling']['cost']/sens['cap_x0.5']['1_all_lambda']['cost']):.0f}% against all-Lambda; if Lambda were half the price it would save {100*(1-sens['lambda_price_x0.5']['6_hybrid_rolling']['cost']/sens['lambda_price_x0.5']['1_all_lambda']['cost']):.0f}%. With a Fargate base the savings are smaller ({k(R('sim_results.json')['fargate']['test']['6_hybrid_rolling']['cost'])} against {k(rl_)}) because Fargate capacity is priced higher per unit under the assumed 4-request task. The 30% EC2 discount is a hypothetical scenario, not an AWS-quoted figure. Under the assumed capacity of 16, hybrid-rolling cost {k(SIM16['ec2']['test']['6_hybrid_rolling']['cost'])} against {k(SIM16['ec2']['test']['1_all_lambda']['cost'])} for all-Lambda (a larger saving), which shows how strongly the result depends on the measured capacity.")
    d.h2("8.8 Live results and sim-to-real gap")
    live_text.live_section(d, LIVE, CAL, WL, R)
    d.h2("8.9 Validation of the newsvendor rule")
    d.para(f"For every function and every test hour, a brute-force search over 401 candidate bases between zero and the hour's maximum was compared with the q*-quantile rule. Over all function-hours the rule's cost differs from the brute-force optimum by {NV['relative_gap_pct']:.4f}% (a negative sign means the rule is marginally cheaper, because the grid is discrete). The preliminary exploration observed agreement within 0.5%; this check agrees to well under that. The check validates the rule against hindsight within an hour, not the forecast itself.")

    # ------------------------------------------------ 9 prediction wrong
    d.h1("9. What happens when the prediction is wrong")
    d.para("The two directions of error behave differently, and the design makes the expensive direction mild.")
    d.bullet("**Under-prediction (base too small).** Load above the base goes to Lambda, so in the simulation nothing is dropped and cost rises only by the Lambda price difference for the excess. The live spike arm (Section 8.8) showed the caveat: no request failed, but latency suffered while EC2 was fed up to its full capacity and the weights caught up. The architecture absorbs the load; it does not by itself protect latency.")
    d.bullet("**Over-prediction (base too large).** Containers run idle. Cost rises by f per idle unit-minute until the next decision; no request is harmed. The asymmetry f versus L is what pushes q* above 0.5.")
    d.bullet("**Slow reaction.** A purely reactive scaler is wrong in the damaging way: it under-provisions during a rise and has no fallback, so load is dropped or delayed.")
    sp = FC["spike_test_ec2"]
    d.para("**Simulated unseen spike.** In the test period one hour per function was multiplied by 3, 4 or 5 after the forecast for that hour had been made, with forecasts for later hours computed from the spiked history.")
    d.table(["Spike", "Hybrid-ML cost", "Hybrid-rolling cost", "Reactive u=0.7 cost", "Reactive u=0.7 unserved", "Hybrid unserved"],
            [["none", usd(T["7_hybrid_ML"]["cost"]), usd(T["6_hybrid_rolling"]["cost"]), usd(T["3_reactive_u0.7"]["cost"]), pct(T["3_reactive_u0.7"]["unserved_pct"], 1), "0.0%"]] +
            [[f"x{m}", usd(sp[m]["hybrid_ML"]["cost"]), usd(sp[m]["hybrid_rolling"]["cost"]), usd(sp[m]["reactive_u0.7"]["cost"]), pct(sp[m]["reactive_u0.7"]["unserved_pct"], 1), pct(max(sp[m]["hybrid_ML"]["unserved_pct"], sp[m]["hybrid_rolling"]["unserved_pct"]), 1)] for m in ("3", "4", "5")],
            [1.6, 2.7, 2.9, 3.0, 3.2, 2.6], "Simulated spike results (monthly cost, test)")
    d.figure(FIG / "spike.png", 14.5, "Effect of an unseen spike on cost and unserved load")
    d.para(f"The hybrids serve all load in every case; the cost of a x5 spike is {k(sp['5']['hybrid_rolling']['cost'] - T['6_hybrid_rolling']['cost'])} (rolling) to {k(sp['5']['hybrid_ML']['cost'] - T['7_hybrid_ML']['cost'])} (ML) per month above the no-spike case. The ML forecaster reacts worse than the rolling quantile after a spike (x5: {k(sp['5']['hybrid_ML']['cost'])} against {k(sp['5']['hybrid_rolling']['cost'])}), because its features also include the spiked hour and it over-raises the next base. A production system would clip forecasts that follow a detected anomaly. The reactive controller is unaffected in kind but still drops about {sp['4']['reactive_u0.7']['unserved_pct']:.1f}% of load in every case. Live arm D repeats this test on AWS (Section 8.8): there too nothing failed, but about " + f"{100*LIVE['D_ml_spike']['slo_violation_share']:.0f}% of requests exceeded the latency target, a cost the simulator does not model." if LIVE else "Live arm D repeats this test on AWS (Section 8.8).")
    d.para("**Remaining risks.** The newsvendor argument assumes the forecast quantile is calibrated. Coverage at the median is not (Table 7), so a forecaster used at low q* (cheap containers relative to Lambda) would be miscalibrated where it matters most. A sustained level shift larger than the lookback window would be absorbed by Lambda for several hours at higher cost before the base catches up, and a fully new function with no history has no forecast at all and must start on Lambda.")

    # ------------------------------------------------ 10 limitations
    d.h1("10. Limitations")
    for t in [
        "**Azure traffic, AWS prices.** The trace was recorded on Azure Functions; running the same traffic on AWS with AWS prices is a modelling assumption, not an observation of an AWS customer.",
        f"**Capacity assumptions.** Container capacity per unit is measured for one synthetic request type (400 ms service time, 20% CPU) on one instance type, from a coarse grid ({SUS:.0f} req/s sustainable, 20 req/s failing). Real functions differ. Fargate capacity was never measured. Burstable t3 instances can run out of CPU credits under sustained load; credit balances were not measured in the short experiments.",
        "**Fractional capacity in the simulator.** Containers are billed as a shared pool; the whole-instance sensitivity row shows a small effect, but real fleets also have minimum sizes and availability-zone constraints.",
        "**Heavy-function filter.** Only 101 functions qualify; conclusions are about busy functions, not the median function, which is idle most of the day.",
        "**Forecaster scale.** The model trains on a small population (218k sampled rows); it is not tuned beyond a fixed configuration, and the benefit over rolling quantiles is within noise on test.",
        "**ALB leakage.** The load balancer splits by percentage, not overflow-only, and weight changes take about 12 s to propagate; the live system cannot match the simulator exactly (Section 8.8).",
        "**Short live runs.** Each arm is a time-compressed six-hour window run once, from one laptop and one function; no confidence intervals can be given. Cold-start behaviour of Lambda depends on how long environments stayed warm between arms. The window is a smooth ramp, so it does not stress reactive scaling the way the simulated population does.",
        "**Closed-loop load generator.** Locust users wait for each response, so when latency rises the offered load falls (arm D delivered about 63% of the planned rate in the spiked hour). Latency under overload is therefore understated.",
        "**No capacity headroom.** The controller gives EC2 its full measured capacity; the spike arm shows this leaves no margin. A safety factor was not tested.",
        "**Energy** is an estimate from a published methodology, not a measurement, and is sensitive to the idle-power coefficient.",
        "**Not covered.** Storage, networking, multi-region operation, security, and AWS predictive scaling (not run live) are outside this work."]:
        d.bullet(t)

    # ------------------------------------------------ 11 conclusion
    d.h1("11. Conclusion")
    for t in live_text.conclusion(T, FC, SIM, LIVE, CAL, k): d.para(t)

    # ------------------------------------------------ 12 future work
    d.h1("12. Future work")
    for t in ["**Storage tiering.** Extend the base-plus-overflow idea to storage classes once access-pattern data is available.",
              "**Network cost.** Include data-transfer and load-balancer charges, which this compute-only model omits.",
              "**Fargate base.** Measure Fargate capacity and run it live; the simulator prices it only under an assumed capacity.",
              "**Multi-region.** Place the base in the cheapest region and route overflow by latency and price.",
              "**Anomaly-aware forecasting.** Clip or down-weight history that follows a detected spike so the ML forecaster does not over-react (Section 9).",
              "**Overflow-only routing.** Replace weighted routing with per-request spillover, where each instance forwards a request to Lambda only when it is full, as Spandana [11] describes, to remove the ALB leakage measured in Section 8.8. We did not implement or test this.",
              "**Provider predictive scaling.** Run AWS predictive scaling [3] on a workload with 24 hours of history and compare directly."]:
        d.bullet(t)

    # ------------------------------------------------ references
    d.h1("References")
    refs = [
        "M. Shahrad, R. Fonseca, I. Goiri, G. Chaudhry, P. Batum, J. Cooke, E. Laureano, C. Tresness, M. Russinovich and R. Bianchini, \"Serverless in the Wild: Characterizing and Optimizing the Serverless Workload at a Large Cloud Provider,\" in Proc. 2020 USENIX Annual Technical Conference (USENIX ATC '20), pp. 205-218. https://www.usenix.org/conference/atc20/presentation/shahrad",
        "C. Zhang, M. Yu, W. Wang and F. Yan, \"MArk: Exploiting Cloud Services for Cost-Effective, SLO-Aware Machine Learning Inference Serving,\" in Proc. 2019 USENIX Annual Technical Conference (USENIX ATC '19), pp. 1049-1062. https://www.usenix.org/conference/atc19/presentation/zhang-chengliang",
        "Amazon Web Services, \"How predictive scaling works,\" Amazon EC2 Auto Scaling User Guide. https://docs.aws.amazon.com/autoscaling/ec2/userguide/predictive-scaling-policy-overview.html (accessed 24 October 2026).",
        "Amazon Web Services, \"Configure Lambda function memory,\" AWS Lambda Developer Guide. https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html (accessed 24 October 2026).",
        "Amazon Web Services, \"Action types for listener rules\" (forward actions and weighted target groups), Elastic Load Balancing User Guide. https://docs.aws.amazon.com/elasticloadbalancing/latest/application/rule-action-types.html (accessed 24 October 2026).",
        "\"Newsvendor model,\" Wikipedia. https://en.wikipedia.org/wiki/Newsvendor_model (accessed 24 October 2026). The article cites F. Y. Edgeworth (1888) and K. J. Arrow, T. Harris and J. Marschak (1951) for the original results; those originals were not opened.",
        "G. Ke, Q. Meng, T. Finley, T. Wang, W. Chen, W. Ma, Q. Ye and T.-Y. Liu, \"LightGBM: A Highly Efficient Gradient Boosting Decision Tree,\" Advances in Neural Information Processing Systems 30 (NIPS 2017). https://papers.nips.cc/paper_files/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html",
        "Microsoft Azure, \"Azure Functions Trace 2019,\" Azure Public Dataset (CC-BY). https://github.com/Azure/AzurePublicDataset/blob/master/AzureFunctionsDataset2019.md (accessed 24 October 2026).",
        "Cloud Carbon Footprint, \"Methodology.\" https://www.cloudcarbonfootprint.org/docs/methodology/ (accessed 24 October 2026).",
        "A. Raza, Z. Zhang, N. Akhtar, V. Isahagian and I. Matta, \"LIBRA: An Economical Hybrid Approach for Cloud Applications with Strict SLAs,\" 9th IEEE International Conference on Cloud Engineering (IC2E), 2021; arXiv:2104.05491. https://arxiv.org/abs/2104.05491 (abstract read; accessed 24 October 2026).",
        "D. Dehigama, S. Jesalpura, Z. Xu, M. Nemeth, S. Zhu, M. Kogias and B. Grot, \"Spandana: Reconciling Strict SLOs with Low Cost under Fine-Grained Load Fluctuations,\" arXiv:2606.30533, June 2026 (preprint). https://arxiv.org/abs/2606.30533 (abstract read; accessed 24 October 2026).",
        "D. Dehigama, S. Jesalpura, D. Schall, A. Katsarakis, M. Kogias, R. Kumar and B. Grot, \"Flare: Leveraging Serverless Elasticity to Absorb Microservice Load Spikes,\" arXiv:2605.23707, May 2026 (preprint). https://arxiv.org/abs/2605.23707 (abstract read; accessed 24 October 2026)."]
    for i, r in enumerate(refs, 1):
        p = d.para(f"[{i}] {r}", align="l", after=6, spacing=1.15); p.paragraph_format.left_indent = Emu(342900); p.paragraph_format.first_line_indent = Emu(-342900)

    # ------------------------------------------------ appendix
    d.h1("Appendix A: Reproduction steps")
    d.para("All commands are run from the repository root. Credentials are read from `.env` and mapped to standard AWS variable names by `infra/env.sh`; they are never printed or committed.")
    d.code(["python3 -m venv .venv && .venv/bin/pip install numpy pandas pyarrow lightgbm scikit-learn matplotlib boto3 locust python-docx python-pptx",
            "tar -xJf azurefunctions_dataset2019_*.tar.xz -C data/raw        # about 2.2 GB",
            "make data        # two-pass pipeline -> results/dataset_summary.json",
            "make sim         # simulator -> results/sim_results.json",
            "make forecast    # LightGBM + baselines + spike test -> results/forecast_results.json",
            ". infra/env.sh && .venv/bin/python infra/budgets.py <email>    # budget alerts",
            "make up          # create the stack (ASG at 0 instances; ALB bills about $0.024/h)",
            "make calibrate   # -> results/calibration.json ; then re-run make sim and make forecast",
            "make run         # arms A-D, about 2.8 h, -> results/live/",
            "make down        # destroy everything and verify with the tagging API",
            ".venv/bin/python controller/analyze.py ; make report ; make ppt"])
    d.h2("A.1 Parameters")
    d.table(["Parameter", "Value"], [["Region", "ap-south-1"], ["Split", "days 1-10 train, 11-12 validation, 13-14 test"], ["Quantiles", "0.5, 0.7, 0.8, 0.9, 0.95, 0.99"],
        ["LightGBM", "300 trees, learning rate 0.05, 15 leaves, min 50 samples per leaf, subsample 0.8, seed 0"], ["Lambda", "python3.12, 1769 MB, 30 s timeout"],
        ["Instance", "t3.medium, AL2023, ASG 0-8, ALB health check every 5 s"], ["Live request", f"{CAL['service_ms']} ms total, {CAL['cpu_ms']} ms CPU"]], [4.0, 12.0], "Key parameters", align_right_from=9)

    # ------------------------------------------------ TOC, LoF, LoT
    body = d.d.element.body
    def insert_after(idx_par, items):
        pass
    return d, toc_at, lof_at, lot_at


def fill_front(d, toc_at, lof_at, lot_at, pagemap):
    """Insert TOC / figure list / table list paragraphs after their headings (python-docx: create then move)."""
    from docx.shared import Pt
    from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER
    paras = d.d.paragraphs
    def mk(text, bold=False, size=None, tab=None, indent=0):
        p = d.d.add_paragraph(style="Normal"); p.paragraph_format.space_after = Pt(2); p.paragraph_format.line_spacing = 1.15; p.paragraph_format.left_indent = Pt(indent)
        if tab is not None: p.paragraph_format.tab_stops.add_tab_stop(Pt(451), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        r = p.add_run(text); r.bold = bold or None
        if size: r.font.size = Pt(size)
        return p
    def anchor(title):
        return [p for p in d.d.paragraphs if p.style.name == "Heading 1" and p.text == title][0]
    toc = [(lv, t) for lv, t in d.heads if t not in ("Abstract", "Table of contents", "List of figures", "List of tables")]
    for title, items in (("List of tables", [mk(f"Table {i+1}: {c}") for i, c in enumerate(d.tabs)][::-1]),
                         ("List of figures", [mk(f"Figure {i+1}: {c}") for i, c in enumerate(d.figs)][::-1]),
                         ("Table of contents", [mk(f"{t}\t{pagemap.get(t, '')}", bold=(lv == 1), size=None if lv == 1 else 11, tab=True, indent=0 if lv == 1 else 14) for lv, t in toc][::-1])):
        a = anchor(title)
        for p in items: a._p.addnext(p._p)

def main():
    pagemap = {}
    out = ROOT / "report/CostScale_Report.docx"
    for it in range(2):
        d, a, b, c = build()
        fill_front(d, a, b, c, pagemap); d.save(out)
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(ROOT / "report"), str(out)], check=True, capture_output=True)
        txt = subprocess.run(["pdftotext", "-layout", str(ROOT / "report/CostScale_Report.pdf"), "-"], capture_output=True, text=True).stdout.split("\f")
        pagemap = {}
        for lv, t in d.heads:
            if t in ("Abstract", "Table of contents", "List of figures", "List of tables"): continue
            for pg, pt in enumerate(txt, 1):
                if pg > 4 and re.search(r"^\s*" + re.escape(t) + r"\s*$", pt, re.M): pagemap[t] = str(pg); break
    print("pages:", len(txt) - 1, "headings mapped:", len(pagemap), "figs", len(d.figs), "tables", len(d.tabs))

if __name__ == "__main__":
    main()
