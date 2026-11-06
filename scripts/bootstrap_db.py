"""Build the `ri` database from scratch: schema → pack SQL functions → tenant → full pipeline. Idempotent (drops and recreates).
  bootstrap_db.py                 everything (≈1–2 min)
  bootstrap_db.py --schema-only   schema + functions + tenant row, no data
The pipeline steps are the same CLI scripts a person runs (README), executed with DATABASE_URL pointing at `ri`."""
import sys, os, argparse, subprocess, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from db import conn as C
import paths, psycopg

PIPELINE = [  # (label, argv) — grows as scripts are migrated (plan 3-①)
    ("load",       ["scripts/load.py"]),
    ("synth",      ["scripts/synth.py"]),
    ("rules",      ["scripts/run_rules.py"]),
    ("precedents", ["scripts/load_precedents.py"]),
    ("features",   ["scripts/build_features.py", "--quiet"]),
    ("validate",   ["scripts/validate_features.py"]),
    ("labels",     ["scripts/labels.py", "--label-source", "weak"]),
    ("train",      ["scripts/train.py", "--label-source", "weak", "--quiet"]),
    ("score",      ["scripts/score_tx.py", "--quiet"]),
    ("queue",      ["scripts/build_queue.py", "--from", "2025-03-01", "--to", "2025-03-31", "--force"]),
]

def recreate(dbname: str):
    with psycopg.connect(C.with_dbname(C.url(), "postgres"), autocommit=True) as a:
        a.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", [dbname])
        a.execute(f'drop database if exists "{dbname}"'); a.execute(f'create database "{dbname}"')

def schema(dbname: str, tenant_name: str = "default"):
    with psycopg.connect(C.with_dbname(C.url(), dbname), autocommit=True) as con:
        C.exec_script(con, ROOT / "db" / "schema.sql")
        if paths.FUNCTIONS and paths.FUNCTIONS.exists(): con.execute("set search_path to ri, public"); C.exec_script(con, paths.FUNCTIONS)
        con.execute("set search_path to ri, public")
        con.execute("insert into tenants(name) values (%s) on conflict (name) do nothing", [tenant_name])
        tid = con.execute("select tenant_id from tenants where name=%s", [tenant_name]).fetchone()[0]
    return tid

def run_pipeline(dbname: str, steps=PIPELINE):
    env = dict(os.environ, DATABASE_URL=C.with_dbname(C.url(), dbname))
    for label, argv in steps:
        t = time.time(); print(f"── {label}: {' '.join(argv)}", flush=True)
        r = subprocess.run([sys.executable, "-I", *argv], cwd=ROOT, env=env)
        if r.returncode != 0: raise SystemExit(f"step {label} failed ({r.returncode})")
        print(f"   ok {time.time()-t:.1f}s", flush=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--db", default=C.url().rpartition("/")[2]); ap.add_argument("--schema-only", action="store_true"); ap.add_argument("--tenant", default="default")
    a = ap.parse_args()
    recreate(a.db); tid = schema(a.db, a.tenant); print(f"schema applied to {a.db} · tenant_id={tid}")
    if not a.schema_only: run_pipeline(a.db); print("bootstrap complete")
