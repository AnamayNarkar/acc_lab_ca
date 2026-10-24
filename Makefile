PY := .venv/bin/python
ENV := . infra/env.sh &&
.PHONY: data sim forecast up calibrate run down cost report ppt
data:      ; $(PY) data/pipeline.py
sim:       ; $(PY) sim/run_sim.py
forecast:  ; $(PY) forecast/train.py
up:        ; $(ENV) $(PY) infra/up.py
calibrate: ; $(ENV) $(PY) loadgen/calibrate.py
run:       ; $(ENV) $(PY) controller/run_experiments.py
down:      ; $(ENV) $(PY) infra/down.py
cost:      ; $(ENV) $(PY) infra/cost.py
report:    ; $(PY) report/build_report.py
ppt:       ; $(PY) ppt/build_ppt.py
