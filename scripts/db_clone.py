"""Clone a database from a template (≈1 s) — the Postgres equivalent of `cp warehouse.duckdb /tmp/x`.
  db_clone.py ri ri_test            create ri_test from template ri (terminates sessions on the template first)
  db_clone.py --drop ri_test        drop it
  db_clone.py --sweep               drop clones named ri_*_<epoch>_<pid> older than 1 hour
  db_clone.py --name unit           create ri_unit_<epoch>_<pid> and print only its DATABASE_URL (for checks)
Prints the DATABASE_URL of the clone so callers can `export DATABASE_URL=$(...)`."""
import sys, os, time, argparse, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import conn as C
import psycopg

def admin():
    return psycopg.connect(C.with_dbname(C.url(), "postgres"), autocommit=True)

def clone(src: str, dst: str) -> str:
    with admin() as a:
        a.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", [src])
        a.execute(f'drop database if exists "{dst}"')
        a.execute(f'create database "{dst}" template "{src}"')
    return C.with_dbname(C.url(), dst)

def drop(name: str):
    with admin() as a:
        a.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", [name])
        a.execute(f'drop database if exists "{name}"')

def sweep(max_age_s: int = 3600) -> list[str]:
    gone = []
    with admin() as a:
        for (n,) in a.execute("select datname from pg_database where datname like 'ri\\_%'").fetchall():
            m = re.match(r"ri_[a-z0-9]+_(\d+)_\d+$", n)
            if m and time.time() - int(m.group(1)) > max_age_s: drop(n); gone.append(n)
    return gone

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src", nargs="?"); ap.add_argument("dst", nargs="?")
    ap.add_argument("--drop", metavar="NAME"); ap.add_argument("--sweep", action="store_true"); ap.add_argument("--name", help="short label → ri_<name>_<epoch>_<pid>")
    a = ap.parse_args()
    if a.sweep: print("dropped:", sweep())
    elif a.drop: drop(a.drop); print("dropped", a.drop)
    elif a.name: sweep(); print(clone("ri", f"ri_{a.name}_{int(time.time())}_{os.getpid()}"))
    elif a.src and a.dst: print(clone(a.src, a.dst))
    else: ap.error("give SRC DST, --name LABEL, --drop NAME or --sweep")
