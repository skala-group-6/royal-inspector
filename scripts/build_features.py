"""Step 3.5: build tx_features (+ entity_stats view) from the pack features catalog. Honors ROYAL_DB.
Usage: build_features.py [--strategy window|correlated] [--with-history] [--target NAME] [--source VIEW] [--quiet]"""
import os, sys, argparse, duckdb
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
from features.executor import build
ap = argparse.ArgumentParser(); ap.add_argument("--strategy", default="window", choices=["window", "correlated"])
ap.add_argument("--with-history", action="store_true"); ap.add_argument("--target", default="tx_features"); ap.add_argument("--source", default=None); ap.add_argument("--quiet", action="store_true")
a = ap.parse_args()
con = duckdb.connect(str(paths.DB))
info = build(con, a.strategy, a.with_history, a.source, a.target, a.quiet)
con.close()
