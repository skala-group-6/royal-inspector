"""Threshold sensitivity for class-2 rules: how many REAL transactions each setting flags, and synthetic recall for that rule."""
import subprocess, re, sys
SWEEPS = {"R03": [("window_min", v) for v in (30, 60, 120, 240)], "R06": [("window_min", v) for v in (10, 15, 30, 60)],
          "R09": [("per_window", v) for v in (3, 4, 5)], "R12": [("lookback_min", v) for v in (20, 30, 45, 60)],
          "R16": [("ratio", v) for v in (1.8, 2.5, 3.0, 4.0)], "R04": [("min_amount", v) for v in (200000, 300000, 500000)]}
print(f"{'rule':6} {'param':14} {'value':>8} {'real_flagged':>12} {'synth_recall':>12}")
for rid, settings in SWEEPS.items():
    for p, v in settings:
        out = subprocess.run([sys.executable, "-I", "scripts/run_rules.py", rid, f"{rid}.{p}={v}"], capture_output=True, text=True).stdout
        real = re.search(rf"^{rid}\S*\s+.*?\s+(\d+)\s+(\d+)\s+\{{", out, re.M)
        rec = re.search(rf"^\s*{rid}\S*\s+(\d+)\s+(\d+)\s+([\d.]+)", out, re.M)
        print(f"{rid:6} {p:14} {v:>8} {real.group(1) if real else '?':>12} {rec.group(3)+'%' if rec else '?':>12}")
