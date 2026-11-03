"""Single place that resolves pack files. Engine code imports these constants instead of hardcoding 'rules/...'.
PACK env selects the pack directory (relative to repo root); default is the corporate-card pack."""
import os
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
PACK_DIR = (ROOT / os.environ.get("PACK", "packs/corp_card")).resolve()
_m = yaml.safe_load(open(PACK_DIR / "pack.yaml"))

def _p(key):
    v = _m.get(key); return (PACK_DIR / v).resolve() if v else None

PACK_NAME = _m["name"]
RULES_CATALOG = _p("rules_catalog")
RULES_SQL_DIR = _p("rules_sql_dir")
MACROS = _p("macros")                 # may be None
FEATURES_CATALOG = _p("features_catalog")
WEAK_LABELS = _p("weak_labels")
CASES = _p("cases")
RAW_GLOB = list(_m.get("raw_glob") or [])
RAW_DIR = ROOT / "data" / "raw"
DB = Path(os.environ.get("ROYAL_DB", ROOT / "data" / "warehouse.duckdb"))

def macros_sql() -> str:
    return open(MACROS).read() if MACROS and MACROS.exists() else ""
