"""The one place that talks to PostgreSQL. Everything else imports from here.

  DATABASE_URL  postgresql://postgres:x@localhost:5432/ri   (default; tests/checks point it at a clone)
  TENANT_ID     1                                            (set per connection as ri.tenant_id; views filter on it)

Conventions: psycopg 3, %s parameters, session timezone Asia/Seoul, search_path ri. Reads come back as DataFrames with
numeric→float so service math never sees Decimal. Writes of DataFrames go through COPY (fast, typed by the table)."""
from __future__ import annotations
import os, io, csv, json, datetime as dt
from decimal import Decimal
from pathlib import Path
import numpy as np, pandas as pd, psycopg

DEFAULT_URL = "postgresql://postgres:x@localhost:5433/ri"

def url() -> str: return os.environ.get("DATABASE_URL", DEFAULT_URL)
def tenant_id() -> int: return int(os.environ.get("TENANT_ID", "1"))

def connect(dsn: str | None = None, autocommit: bool = True) -> psycopg.Connection:
    con = psycopg.connect(dsn or url(), autocommit=autocommit, options="-c search_path=ri,public -c timezone=Asia/Seoul")
    con.execute("select set_config('ri.tenant_id', %s, false)", [str(tenant_id())])
    return con

def with_dbname(dsn: str, dbname: str) -> str:
    """Same server, different database (for clones and maintenance connections)."""
    head, _, _ = dsn.rpartition("/")
    return f"{head}/{dbname}"

# ---------------------------------------------------------------- reads
def q(con, sql: str, params=None) -> pd.DataFrame:
    with con.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None: return pd.DataFrame()
        cols = [d.name for d in cur.description]; rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    for c in df.columns:
        if df[c].dtype == object and len(df) and any(isinstance(v, Decimal) for v in df[c].head(50)):
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df

def one(con, sql: str, params=None):
    with con.cursor() as cur:
        cur.execute(sql, params); r = cur.fetchone()
    return r[0] if r is not None and len(r) == 1 else r

def execute(con, sql: str, params=None) -> int:
    with con.cursor() as cur:
        cur.execute(sql, params); return cur.rowcount

def exec_script(con, path: str | Path):
    """Run a multi-statement SQL file (schema, pack functions)."""
    con.execute(Path(path).read_text())

# ---------------------------------------------------------------- writes
def pg_array(v) -> str | None:
    """Python list → Postgres array literal for COPY (text[], bigint[]). Quotes every element so Korean text and commas are safe."""
    if v is None or (isinstance(v, float) and np.isnan(v)): return None
    if isinstance(v, np.ndarray): v = v.tolist()
    def esc(x):
        if x is None: return "NULL"
        s = str(x).replace("\\", "\\\\").replace('"', '\\"'); return f'"{s}"'
    return "{" + ",".join(esc(x) for x in v) + "}"

def _cell(v):
    if v is None or v is pd.NA or v is pd.NaT: return None
    if isinstance(v, float) and np.isnan(v): return None
    if isinstance(v, (np.bool_, bool)): return "t" if v else "f"
    if isinstance(v, (np.integer,)): return str(int(v))
    if isinstance(v, (np.floating,)): return None if np.isnan(v) else repr(float(v))
    if isinstance(v, (list, tuple, np.ndarray)): return pg_array(v)
    if isinstance(v, dict): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (pd.Timestamp, dt.datetime, dt.date, dt.time)): return v.isoformat()
    return str(v)

def write_df(con, table: str, df: pd.DataFrame, cols: list[str] | None = None, tenant: bool = True) -> int:
    """COPY a DataFrame into `table`. Adds tenant_id unless the frame already has it (or tenant=False)."""
    df = df.copy()
    if tenant and "tenant_id" not in df.columns: df.insert(0, "tenant_id", tenant_id())
    cols = cols or list(df.columns)
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n")
    for row in df[cols].itertuples(index=False, name=None):
        w.writerow([_cell(v) if _cell(v) is not None else "" for v in row])
    buf.seek(0)
    with con.cursor() as cur, cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, NULL '')") as cp:
        cp.write(buf.read())
    return len(df)

def table_exists(con, name: str, schema: str = "ri") -> bool:
    return bool(one(con, "select count(*) from information_schema.tables where table_schema=%s and table_name=%s", [schema, name]))

def columns(con, name: str, schema: str = "ri") -> list[str]:
    return q(con, "select column_name from information_schema.columns where table_schema=%s and table_name=%s order by ordinal_position", [schema, name]).column_name.tolist()
