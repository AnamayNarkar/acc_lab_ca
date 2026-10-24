"""Build ppt/CostScale.pptx on the supplied Somaiya template ("Copy of somaiya template.pptx") from results/*.json and report/figures.
Speaker notes on every slide. Content is laid out in the template's safe area (left bar, top-right logo, bottom strip)."""
import json
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
ROOT = Path(__file__).resolve().parent.parent
R = lambda n: json.load(open(ROOT / "results" / n))
DS, SIM, FC, CAL, NV, WL = R("dataset_summary.json"), R("sim_results.json"), R("forecast_results.json"), R("calibration.json"), R("newsvendor_check.json"), R("live_workload.json")
SIM16 = R("sim_results_assumed_cap16.json")
LIVE = R("live_results.json") if (ROOT / "results/live_results.json").exists() else {}
T = SIM["ec2"]["test"]; FIG = ROOT / "report/figures"
K = lambda x: f"${x/1000:,.1f}k"
# template palette (from the template's master): Somaiya red, grey text; chart accents stay as in the figures
RED, GREY = RGBColor(0xB7, 0x20, 0x2E), RGBColor(0x58, 0x59, 0x5B)
BLUE, ORANGE, AQUA = RED, RGBColor(0xF2, 0x6B, 0x43), RED
INK, MUTED = RGBColor(0x21, 0x21, 0x21), GREY
prs = Presentation(ROOT / "Copy of somaiya template.pptx")
title_slide = prs.slides[0]; OBJ = prs.slides[1].slide_layout
ids = prs.slides._sldIdLst
for sid in list(ids)[1:]:                       # keep slide 1 (branded title slide), drop the sample slides
    prs.part.drop_rel(sid.rId); ids.remove(sid)

X = lambda v: v; Y = lambda v: v; W = lambda v: v; SZ = lambda v: Pt(v)     # coordinates are real template inches

def slide(title, notes, kicker=None):
    s = prs.slides.add_slide(OBJ)
    for ph in list(s.placeholders):
        if ph.placeholder_format.idx == 1: ph._element.getparent().remove(ph._element)   # body placeholder unused
        elif ph.placeholder_format.idx == 0:
            tf = ph.text_frame; tf.clear(); r = tf.paragraphs[0].add_run(); r.text = title; r.font.size = Pt(22); r.font.bold = True; r.font.color.rgb = RED
    if kicker:
        tb = s.shapes.add_textbox(Inches(0.36), Inches(0.9), Inches(7.9), Inches(0.32)); tf = tb.text_frame; tf.word_wrap = True
        r = tf.paragraphs[0].add_run(); r.text = kicker; r.font.size = Pt(12); r.font.color.rgb = GREY; r.font.italic = True
    s.notes_slide.notes_text_frame.text = notes
    return s

def bullets(s, items, x=0.6, y=1.7, w=6.2, h=5.2, size=18, gap=8):
    tb = s.shapes.add_textbox(Inches(X(x)), Inches(Y(y)), Inches(W(w)), Inches(W(h))); tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.space_after = Pt(6)
        sub = it.startswith("  "); txt = it.strip()
        r = p.add_run(); r.text = ("\u2013 " if sub else "\u2022 ") + txt; r.font.size = SZ(size - 2 if sub else size); r.font.color.rgb = MUTED if sub else INK
    return tb

def pic(s, name, x, y, w=None, h=None):
    return s.shapes.add_picture(str(FIG / name), Inches(X(x)), Inches(Y(y)), width=Inches(W(w)) if w else None, height=Inches(W(h)) if h else None)

def stat(s, x, y, big, small, color=RED, w=2.9):
    tb = s.shapes.add_textbox(Inches(X(x)), Inches(Y(y)), Inches(W(w)), Inches(1.2)); tf = tb.text_frame; tf.word_wrap = True
    r = tf.paragraphs[0].add_run(); r.text = big; r.font.size = SZ(28); r.font.bold = True; r.font.color.rgb = color
    p = tf.add_paragraph(); r = p.add_run(); r.text = small; r.font.size = SZ(11); r.font.color.rgb = MUTED

def table(s, rows, x, y, w, colw, size=12, h=0.4):
    sh = s.shapes.add_table(len(rows), len(rows[0]), Inches(X(x)), Inches(Y(y)), Inches(W(w)), Inches(W(h) * len(rows))); t = sh.table
    for j, cw in enumerate(colw): t.columns[j].width = Inches(W(cw))
    for i in range(len(rows)): t.rows[i].height = Inches(W(h))
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j); c.text = str(v); p = c.text_frame.paragraphs[0]; p.runs[0].font.size = SZ(size)
            p.runs[0].font.bold = (i == 0); p.runs[0].font.color.rgb = RGBColor(0xff, 0xff, 0xff) if i == 0 else INK
            c.fill.solid(); c.fill.fore_color.rgb = RED if i == 0 else RGBColor(0xff, 0xff, 0xff) if i % 2 else RGBColor(0xf4, 0xf4, 0xf4)
            c.margin_top = c.margin_bottom = Emu(20000); c.margin_left = c.margin_right = Emu(50000)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
    return t

# 1 title (uses the template's branded title slide)
s = title_slide
s.notes_slide.notes_text_frame.text = "Introduce the project in one sentence: a resource manager that keeps a cheap base of EC2 sized by a forecast and sends the rest to Lambda. Mention it is a university cloud-computing project, built and measured on AWS in Mumbai, using a real production trace from Azure."
for ph in s.placeholders:
    if ph.placeholder_format.idx == 0:
        ph.text_frame.clear(); r = ph.text_frame.paragraphs[0].add_run(); r.text = "CostScale"; r.font.size = Pt(40); r.font.bold = True; r.font.color.rgb = RED
def _tb(x, y, w, h, lines, size, color, bold=False):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.space_after = Pt(4); r = p.add_run(); r.text = ln; r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold
_tb(0.36, 1.05, 7.4, 0.9, ["ML-driven hybrid container and serverless resource management on AWS"], 20, GREY)
_tb(0.36, 2.2, 7.4, 1.2, ["Anamay Narkar (16010123040)", "Ananya Dhiman (16010123041)", "Anoushka Nelson (16010123049)"], 16, INK, True)
_tb(0.36, 3.5, 7.4, 1.0, ["B.Tech Computer Engineering, K.J. Somaiya School of Engineering, Mumbai", "[TO FILL: course name]  |  October 2026"], 12, GREY)
s = slide('The problem', 'Two ways to buy compute: reserved containers or VMs are cheap per unit but need lead time; Lambda is instant and pay per use but costs several times more per unit of work. Traffic varies, so sizing for peak wastes money and reacting late drops or delays requests. The task: predict workload and allocate resources. Rubric items: inputs and features, algorithm and horizon, allocation mechanism, evaluation on accuracy, utilisation, latency, cost and energy, and what happens when the prediction is wrong.', 'Predict workload, then allocate resources')
bullets(s, ['Containers / VMs: cheap per unit, but slow to provision', 'Lambda: instant, pay per use, several times costlier per unit', 'Load varies; most functions are idle, a few are very busy', 'Goal: lowest cost while serving every request in time'], x=0.45, y=1.5, w=5.4, h=3.6, size=17)
stat(s, 6.4, 1.6, f"{DS['heavy_functions']}", 'heavy Azure functions simulated\n(>= $50/month on training days)', BLUE, w=3.1)
stat(s, 6.4, 3.2, f"{DS['functions_on_all_14_days']:,}", 'functions present on all 14 days\n(of 72k in the trace)', ORANGE, w=3.1)
r7, r3 = (T['3_reactive_u0.7'], T['3_reactive_u0.3'])
s = slide('Why plain autoscaling is not enough', f"Reactive autoscaling sizes capacity from load it saw five minutes ago at a target utilisation u. In the simulation, every u we tried leaves load unserved because there is no fallback: u 0.7 costs {K(r7['cost'])} and drops {r7['unserved_pct']:.1f} percent; u 0.3 costs {K(r3['cost'])} and still drops {r3['unserved_pct']:.1f} percent. The hybrid in the bottom-left corner of the chart serves everything for {K(T['6_hybrid_rolling']['cost'])}. The seasonal line is an emulation of predictive-scaling style capacity from the same hour on previous days, not the AWS algorithm.", 'Every reactive setting drops load or overpays')
pic(s, 'unserved_vs_cost.png', 0.4, 1.45, w=5.8)
bullets(s, [f"Reactive u=0.7: {K(r7['cost'])}, {r7['unserved_pct']:.1f}% load dropped", f"Reactive u=0.3: {K(r3['cost'])}, still {r3['unserved_pct']:.1f}% dropped", f"Hybrid-rolling: {K(T['6_hybrid_rolling']['cost'])}, 0% dropped", 'Test days, 101 heavy functions, AWS Mumbai prices'], x=6.4, y=1.6, w=3.2, h=3.4, size=13)
s = slide('The idea: a base plus overflow', f"Keep a base of always-on EC2 capacity. Everything above the base goes to Lambda. The base is the quantile of forecast load whose level is q-star equals one minus f over L, where f is the container cost and L the Lambda cost of the same unit of load for a minute. If L is not above f the base is zero. We checked the rule against brute-force search per function and hour: the difference is {NV['relative_gap_pct']:.4f} percent. Forecasting sets the slow thing, instance count; a per-minute loop sets ALB weights.", 'Newsvendor: base = q*-quantile of forecast load')
bullets(s, ['Base: EC2 Auto Scaling Group (cheap, always on)', 'Overflow: AWS Lambda (instant, pay per use)', 'ALB weighted target groups split the traffic', 'Forecast sets instance count (hourly); observed rate sets weights (per minute)'], x=0.45, y=1.5, w=4.4, h=3.3, size=15)
tb = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(5.1), Inches(1.5), Inches(4.4), Inches(2.1))
tb.fill.solid()
tb.fill.fore_color.rgb = RGBColor(232, 240, 251)
tb.line.color.rgb = BLUE
tf = tb.text_frame
tf.word_wrap = True
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
for i, (txt, sz, b) in enumerate([('base  b* = F⁻¹(q*)', 21, True), ('q* = 1 − f / L', 21, True), ('f: container $ per unit-minute\nL: Lambda $ per unit-minute', 11, False)]):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = txt
    r.font.size = Pt(sz)
    r.font.bold = b
    r.font.color.rgb = INK
    r.font.name = 'Calibri'
stat(s, 5.1, 3.9, f"{abs(NV['relative_gap_pct']):.4f}%", 'gap between the rule and brute-force search (test hours)', AQUA, w=4.4)
s = slide('Data', f"Azure Functions 2019 trace, CC-BY, from Shahrad et al., USENIX ATC 2020. Fourteen days of per-minute invocations, with durations and memory. Most functions are rarely invoked, the median function on day one gets {DS['median_invocations_per_day_day1']:.0f} invocations, so we filter. We keep functions present on all 14 days with at least 5 requests per minute: {DS['functions_avg_ge_5rpm_all14days']:,}, of which {DS['functions_with_traffic_duration_memory']:,} also have duration and memory. A function is heavy if its cheaper single-platform option costs at least 50 dollars per month on training days. Load is concurrency: invocations per minute over 60 times average duration. Azure traffic is priced with AWS prices. Split is chronological per function: days 1-10 train, 11-12 validation, 13-14 test.", 'Azure Functions 2019 trace, filtered to busy functions')
table(s, [['Step', 'Count'], ['Distinct functions (14 days)', f"{DS['functions_total_distinct']:,}"], ['On day 1', f"{DS['day1_functions']:,}"], ['On all 14 days', f"{DS['functions_on_all_14_days']:,}"], ['>= 5 req/min, all 14 days', f"{DS['functions_avg_ge_5rpm_all14days']:,}"], ['+ duration + memory', f"{DS['functions_with_traffic_duration_memory']:,}"], ['Heavy (>= $50/mo)', f"{DS['heavy_functions']}"]], 0.45, 1.5, 4.9, [3.3, 1.6], size=14, h=0.43)
bullets(s, ['Load = invocations/min ÷ 60 × duration (concurrency)', 'Timer functions excluded (periodic, not diurnal)', 'Chronological split: train 1-10, validation 11-12, test 13-14', 'Azure traffic priced with AWS prices'], x=5.6, y=1.5, w=3.9, h=3.4, size=14)
fi = FC['feature_importance_q0.9']
s = slide('Features and model', f"One global LightGBM model per quantile, objective quantile, trained across all heavy functions with load normalised per function. Horizon: next hour, decided at the start of the hour. Features come only from before the decision time: last hour and last six hours mean, max and 90th percentile; same hour yesterday; hour of day; trigger; and the function's level. The safety margin was chosen on validation by minimising decision cost, and came out as {FC['margin_chosen']:.1f}, so none. Baselines: persistence, rolling six-hour quantile, seasonal naive and static training quantile. Accuracy: LightGBM is best at the upper quantiles and tracks coverage; persistence is better at the median. The decision-cost result is on the next slide.", 'LightGBM quantile regression, next-hour horizon')
bullets(s, ['Targets: q in {0.5, 0.7, 0.8, 0.9, 0.95, 0.99} of next-hour per-minute concurrency', 'Features: last 60 / 360 min (mean, max, q90), same hour yesterday, hour of day, trigger, app level', 'Margin multiplier chosen on validation by decision cost', 'Baselines: persistence, rolling 6 h, seasonal naive, static'], x=0.45, y=1.5, w=4.5, h=3.4, size=13)
pic(s, 'quantile_coverage.png', 5.1, 1.5, w=4.4)
s = slide('Architecture', 'A local controller does two jobs. Every decision interval it takes the forecast quantile at q-star and sets the ASG desired capacity. Every minute it reads the observed request rate and sets the ALB weights: the EC2 share is the minimum of one and healthy capacity over observed rate, in integer weights from 0 to 999. The ALB splits by percentage, not overflow-only, so the live system leaks relative to the simulator; we measure that. Everything is tagged project equals costscale, default VPC, no NAT gateway, no RDS, and one make down destroys it and verifies with the tagging API.', 'Forecast sets instances, observed load sets weights')
pic(s, 'architecture.png', 0.4, 1.5, w=6.3)
bullets(s, ['ALB weights 0-999, per minute', 'ASG desired capacity, per hour', 'Lambda 1769 MB (1 vCPU) as overflow', 'make up / make down, tagged, verified'], x=6.9, y=1.7, w=2.7, h=3, size=12)
s = slide('Simulation results', f"Test days 13 and 14 scaled to 30 days, EC2 base, container capacity measured on AWS. Hybrid rolling costs {K(T['6_hybrid_rolling']['cost'])}, {100 * (1 - T['6_hybrid_rolling']['cost'] / T['1_all_lambda']['cost']):.0f} percent below all-Lambda and {100 * (1 - T['6_hybrid_rolling']['cost'] / r7['cost']):.0f} percent below reactive at u 0.7, which also drops {r7['unserved_pct']:.1f} percent of load. Plainly: the ML forecaster is only {abs(FC['ml_vs_rolling_pct']):.2f} percent {('cheaper' if FC['ml_vs_rolling_pct'] < 0 else 'more expensive')} than the rolling six-hour quantile on test, and the whole headroom to the oracle is {FC['headroom_rolling_to_oracle_pct']:.1f} percent. Energy, by an estimate based on the Cloud Carbon Footprint method, is lowest for all-Lambda: the hybrid saves money, not energy. Under the earlier assumed capacity of 16 the saving was larger; measured capacity is {SIM['capacity_units']['ec2']:.1f}.", 'The hybrid wins on cost and unserved load; ML adds almost nothing over rolling')
pic(s, 'cost_comparison.png', 0.4, 1.5, w=6.2)
bullets(s, [f"Hybrid-rolling {K(T['6_hybrid_rolling']['cost'])} vs all-Lambda {K(T['1_all_lambda']['cost'])}", f"ML vs rolling: {FC['ml_vs_rolling_pct']:+.2f}% (noise level)", f"Headroom to oracle: {FC['headroom_rolling_to_oracle_pct']:.1f}%", f"Energy (estimate): hybrid {T['6_hybrid_rolling']['energy_wh'] / 1000:,.0f} kWh vs all-Lambda {T['1_all_lambda']['energy_wh'] / 1000:,.0f} kWh"], x=6.8, y=1.7, w=2.8, h=3, size=12)
if LIVE:
    A, B, C, D = (LIVE.get(k) for k in ('A_reactive', 'B_static', 'C_ml', 'D_ml_spike'))
    rows = [['Arm', 'Errors', 'Lambda', 'p95 ms', 'Cost']]
    for key, nm in (('A_reactive', 'A reactive'), ('B_static', 'B static'), ('C_ml', 'C ML'), ('D_ml_spike', 'D ML + spike')):
        v = LIVE.get(key)
        if v:
            rows.append([nm, f"{100 * v['error_rate']:.1f}%", f"{100 * v['lambda_share']:.0f}%", f"{v['latency_ms']['all']['p95']:.0f}", f"${v['total_cost_cw']:.3f}"])
    s = slide('Live results on AWS', 'Four arms on the same trace window, scaled to 28 requests per second and time-compressed, run from a laptop in Mumbai against the load balancer in ap-south-1. Arm A is ASG target tracking with everything on EC2; B and C use the controller with the static and ML forecasts; D is C with a 4x spike in the fourth hour. The table shows errors, share served by Lambda, p95 latency and cost computed from instance time and CloudWatch Lambda metrics. Be straightforward about what it shows. On this smooth ramp, reactive scaling (A) and the ML hybrid (C) cost the same, so we did not reproduce the simulated advantage over reactive scaling; the clear live win is against a static base, which cost more than twice as much because it idles. The spike arm D had no failed requests but about 20 percent of requests were slow, because the weights fed EC2 its full capacity and the weights take about 12 seconds to apply. Each arm ran once, so this supports the design and is not a statistical ranking. The replay agrees with arms A to C within about 2 percent in cost; for D it differs a lot because the closed-loop load generator slowed down under overload.', 'Four arms, same trace, run once each')
    pic(s, 'live_timelines.png', 0.4, 1.5, w=5.4)
    table(s, rows, 5.95, 1.5, 3.6, [1.05, 0.6, 0.7, 0.65, 0.6], size=10, h=0.34)
    bullets(s, [f"A ≈ C in cost on a smooth ramp; static base B costs {B['total_cost_cw'] / C['total_cost_cw']:.1f}x", f"Spike (D): 0 failed, but {100 * D['slo_violation_share']:.0f}% slower than 800 ms", f'Replay agrees within ~2% for A-C', f"Weight changes take ~{sum(CAL['weight_propagation_s']) / 3:.0f} s; launch {CAL['launch_to_healthy_s'][0]:.0f}-{CAL['launch_to_healthy_s'][1]:.0f} s"], x=5.95, y=3.4, w=3.6, h=1.8, size=11)
else:
    s = slide('Live results on AWS', 'Live results pending.', 'pending')
sp = FC['spike_test_ec2']
s = slide('What if the prediction is wrong?', f"Under-prediction is cheap by design: the excess goes to Lambda, nothing is dropped. Over-prediction wastes f per idle unit-minute until the next decision. A reactive controller is wrong in the damaging way. In simulation we multiplied one hour per function by 3, 4 or 5 after the forecast was made: the hybrids served everything; a x5 spike adds {K(sp['5']['hybrid_rolling']['cost'] - T['6_hybrid_rolling']['cost'])} to {K(sp['5']['hybrid_ML']['cost'] - T['7_hybrid_ML']['cost'])} per month. The ML forecaster over-reacts after a spike because its features include the spiked hour; a production system would clip forecasts after an anomaly. Live arm D repeated this on AWS: no request failed, but about 20 percent were slower than the 800 millisecond target, because the load balancer let EC2 run at its full capacity and weight changes take about 12 seconds to apply. The fix we would try first is a safety factor on capacity; we did not test it.", 'Under-prediction goes to Lambda: nothing fails, but latency can suffer')
pic(s, 'spike.png', 0.4, 1.6, w=6.0)
bullets(s, ['Too small base: overflow to Lambda, higher cost, higher latency on cold start', 'Too large base: idle containers, wasted money only', 'Reactive: under-provisions and drops load', f"Live arm D: 0 failed, but {100 * LIVE['D_ml_spike']['slo_violation_share']:.0f}% of requests slower than 800 ms" if LIVE else 'Live arm D: pending', f"x5 spike (sim): +{K(sp['5']['hybrid_rolling']['cost'] - T['6_hybrid_rolling']['cost'])} (rolling) / +{K(sp['5']['hybrid_ML']['cost'] - T['7_hybrid_ML']['cost'])} (ML) per month, 0% dropped"], x=6.6, y=1.6, w=3.0, h=3.4, size=12)
s = slide('Limitations and future work', 'Be upfront. Azure traffic is priced with AWS prices. Capacity is measured for one synthetic request on one instance type from a coarse grid. Live arms are short, time-compressed, single runs from one laptop. Energy is an estimate. AWS predictive scaling was not run live because it needs 24 hours of history. The hybrid advantage depends on measured capacity and Lambda price. Future work: storage tiering, network cost, a Fargate base, multi-region, anomaly-aware forecasting, and overflow-only routing.', 'Honest boundaries')
bullets(s, ['Azure traffic, AWS prices', 'One request type, one instance type, coarse capacity grid', 'Short, compressed, single-run live arms', 'Energy is an estimate; predictive scaling not run live', 'Advantage depends on capacity and Lambda price'], x=0.45, y=1.5, w=4.3, h=3.4, size=16)
bullets(s, ['Storage tiering and network cost (out of scope here)', 'Fargate base, measured and run live', 'Multi-region placement', 'Anomaly-aware forecasts', 'Overflow-only routing instead of weights'], x=5.0, y=1.5, w=4.5, h=3.4, size=16)
s = slide('Conclusion', f"Summarise. The newsvendor rule gives a principled base size and matches brute force. In simulation the hybrid serves all load at {K(T['6_hybrid_rolling']['cost'])} per month against {K(T['1_all_lambda']['cost'])} all-Lambda and {K(r7['cost'])} reactive with {r7['unserved_pct']:.1f} percent dropped. The ML forecaster adds almost nothing over a rolling quantile, and by an estimate the hybrid does not save energy. The live AWS runs are reconciled with a simulator replay. Thank the audience and invite questions.", 'A principled base, an honest result')
bullets(s, ['Newsvendor rule sets the base; matches brute force', f"Hybrid: {K(T['6_hybrid_rolling']['cost'])}/month, 0% dropped, vs {K(T['1_all_lambda']['cost'])} all-Lambda and reactive {K(r7['cost'])} with {r7['unserved_pct']:.1f}% dropped", 'ML forecaster ≈ rolling quantile (reported plainly)', 'Hybrid saves cost, not energy (estimate)', 'Live AWS runs: mechanism works; A ≈ C in cost on a smooth ramp; spike hurt latency'], x=0.45, y=1.5, w=9.0, h=3.5, size=18)
P = R('prices.json')['values']
s = slide('Backup: cost-model assumptions', "Prices from the AWS Price List API for ap-south-1, retrieved on the date shown. Azure traffic is priced with AWS prices. Lambda memory is the larger of 128 MB and the application's memory. Container capacity is the measured value for EC2; the Fargate capacity is assumed.", 'Backup')
table(s, [['Item', 'Value'], ['Lambda duration', f"${P['lambda_gbs']:.7f} per GB-s"], ['Lambda requests', f"${P['lambda_req']:.7f} per request"], ['EC2 t3.medium', f"${P['t3_medium_h']:.4f} per hour"], ['Fargate vCPU / GB', f"${P['fargate_vcpu_h']:.5f} / ${P['fargate_gb_h']:.6f} per hour"], ['EC2 capacity unit', f"{SIM['capacity_units']['ec2']:.1f} concurrent requests (measured; assumed 16)"], ['Fargate capacity unit', '4 concurrent requests (assumed)'], ['Prices retrieved', R('prices.json')['retrieved']]], 0.45, 1.5, 7.8, [2.8, 5.0], size=13, h=0.42)
sens = SIM['sensitivity_test']
s = slide('Backup: sensitivity', 'Hybrid-rolling cost relative to all-Lambda under each scenario. The advantage is large when containers carry more load per unit or Lambda is dearer, and small when capacity per unit is halved or Lambda is half price. The EC2 discount scenario is hypothetical, not an AWS-quoted figure.', 'Backup')
pic(s, 'sensitivity.png', 0.4, 1.5, w=5.6)
bullets(s, [f"Capacity x0.5: saves {100 * (1 - sens['cap_x0.5']['6_hybrid_rolling']['cost'] / sens['cap_x0.5']['1_all_lambda']['cost']):.0f}% vs all-Lambda", f"Lambda price x0.5: saves {100 * (1 - sens['lambda_price_x0.5']['6_hybrid_rolling']['cost'] / sens['lambda_price_x0.5']['1_all_lambda']['cost']):.0f}%", f"Assumed capacity 16: {K(SIM16['ec2']['test']['6_hybrid_rolling']['cost'])} vs {K(SIM16['ec2']['test']['1_all_lambda']['cost'])}"], x=6.2, y=1.7, w=3.3, h=3, size=12)
cp = prs.core_properties
cp.title = 'CostScale: ML-driven hybrid container and serverless resource management on AWS'
cp.author = 'Anamay Narkar, Ananya Dhiman, Anoushka Nelson'
cp.last_modified_by = cp.author
(ROOT / 'ppt').mkdir(exist_ok=True)
prs.save(ROOT / 'ppt/CostScale.pptx')
print('slides', len(prs.slides))
