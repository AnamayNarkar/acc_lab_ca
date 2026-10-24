#!/usr/bin/env bash
# The short accelerated controller run for the video. Writes only to results/live_demo (the saved results are untouched).
. "$(dirname "$0")/_ready.sh" || exit 1
LIVE_OUTDIR=results/live_demo INTERVAL_OVERRIDE=20 .venv/bin/python controller/run_experiments.py C
