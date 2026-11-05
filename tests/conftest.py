"""Shared fixtures. DB-backed tests run against a throwaway clone of the `ri` template database (scripts/db_clone.py),
so they can write freely and never touch the database the app serves from. Skipped when Postgres is unreachable."""
import os, sys, time, subprocess
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))

def _pg_reachable() -> bool:
    try:
        import psycopg
        from db import conn as C
        with psycopg.connect(C.with_dbname(C.url(), "postgres"), connect_timeout=2) as a:
            return bool(a.execute("select 1 from pg_database where datname='ri'").fetchone())
    except Exception:
        return False

@pytest.fixture(scope="session")
def pgdb():
    """DATABASE_URL of a fresh clone of `ri`; dropped at session end. Set before importing app.service in a test."""
    if os.environ.get("RI_TEST_DB_READY") == "1":   # caller (Octave check) already pointed DATABASE_URL at a clone
        yield os.environ["DATABASE_URL"]; return
    if not _pg_reachable(): pytest.skip("Postgres with template database `ri` not reachable (docker compose up -d && scripts/bootstrap_db.py)")
    sys.path.insert(0, str(ROOT / "scripts")); import db_clone
    name = f"ri_pytest_{int(time.time())}_{os.getpid()}"
    url = db_clone.clone("ri", name); os.environ["DATABASE_URL"] = url
    try:
        yield url
    finally:
        db_clone.drop(name)
