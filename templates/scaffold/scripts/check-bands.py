#!/usr/bin/env python3
"""Deterministic control-band detection for ops/bands.yaml.

For each metric: run its query, compare with the rolling baseline (mean ± σ of the last `window`
samples), record the sample, and report the band (0-3). Prints JSON; exit code is always 0 unless
the config is broken, so CI can branch on the reported `max_level`.
"""
import argparse
import json
import pathlib
import statistics
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = ROOT / "ops" / "bands.yaml"
HISTORY = ROOT / "ops" / ".history"
ACTIONS = {0: "none", 1: "log", 2: "diagnose", 3: "propose_pr_or_runbook"}


def load_config():
    try:
        import yaml
    except ImportError:
        sys.exit("pyyaml is required: pip install pyyaml")
    return yaml.safe_load(CONFIG.read_text())


def band(value, history, direction, min_samples):
    if len(history) < min_samples:
        return 0, None
    mean = statistics.fmean(history)
    sd = statistics.pstdev(history)
    if sd == 0:
        z = 0.0 if value == mean else float("inf") * (1 if value > mean else -1)
    else:
        z = (value - mean) / sd
    bad = {"up": z, "down": -z, "both": abs(z)}[direction]
    level = 3 if bad >= 3 else 2 if bad >= 2 else 1 if bad >= 1 else 0
    return level, round(z, 2) if z not in (float("inf"), float("-inf")) else z


def evaluate(metric, defaults, record, value=None, history=None):
    window = metric.get("window", defaults.get("window", 28))
    min_samples = metric.get("min_samples", defaults.get("min_samples", 7))
    hist_file = HISTORY / f"{metric['name']}.jsonl"
    if history is None:
        history = [json.loads(l)["value"] for l in hist_file.read_text().splitlines() if l.strip()] \
            if hist_file.exists() else []
    if value is None:
        out = subprocess.run(metric["query"], shell=True, capture_output=True, text=True, timeout=60)
        if out.returncode:
            return {"metric": metric["name"], "error": out.stderr.strip()[:300], "level": 0}
        value = float(out.stdout.strip().split()[-1])
    level, z = band(value, history[-window:], metric.get("direction", "both"), min_samples)
    if record:
        HISTORY.mkdir(parents=True, exist_ok=True)
        with hist_file.open("a") as f:
            f.write(json.dumps({"ts": int(time.time()), "value": value}) + "\n")
    return {"metric": metric["name"], "value": value, "z": z, "level": level, "action": ACTIONS[level],
            "owner": metric.get("owner"), "runbook": metric.get("runbook") if level == 3 else None}


def demo():
    base = [100, 102, 98, 101, 99, 100, 103, 97, 100, 101]  # mean 100.1, σ ≈ 1.76
    m = {"name": "demo", "direction": "up"}
    return [evaluate(m, {"min_samples": 7}, False, v, base) for v in (100.5, 102.2, 104.0, 106.0)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metric", help="evaluate only this metric")
    ap.add_argument("--no-record", action="store_true", help="don't append the sample to history")
    ap.add_argument("--demo", action="store_true", help="synthetic data showing bands 0-3")
    args = ap.parse_args()

    if args.demo:
        results = demo()
    else:
        cfg = load_config()
        metrics = [m for m in cfg["metrics"] if not args.metric or m["name"] == args.metric]
        if not metrics:
            sys.exit(f"unknown metric: {args.metric}")
        results = [evaluate(m, cfg.get("defaults", {}), not args.no_record) for m in metrics]

    print(json.dumps({"max_level": max((r["level"] for r in results), default=0), "results": results}, indent=2))


if __name__ == "__main__":
    main()
