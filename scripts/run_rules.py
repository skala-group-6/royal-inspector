"""Step 3: run every rule in the pack rules dir (paths.RULES_SQL_DIR) against tx_active, write `flags`, print counts (real vs synthetic), then score.
Usage: run_rules.py [--set R03_split_payment.window_min=60 ...] [--only R03,R05]"""
import sys, re, json, yaml, duckdb
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import paths
CAT = yaml.safe_load(open(paths.RULES_CATALOG)); cat = CAT["rules"]; RULE_VERSION = int(CAT.get("version", 1))
overrides = {}; only = None
for a in sys.argv[1:]:
    if a.startswith("--set"): continue
    if a.startswith("--only"): continue
    if "=" in a: k, v = a.split("="); overrides[k] = v
    elif "," in a or a.startswith("R"): only = set(a.split(","))
sev = lambda rid: cat[rid]["tier"]  # violation | advisory — single source of truth is the pack rules catalog
DEFAULTS = {}  # all thresholds live in the catalog

def render(rid, sql, params):
    def fmt(v):
        if isinstance(v, list): return ", ".join(f"'{x}'" for x in v) if any("가" <= c <= "힣" for x in v for c in x) and not rid.startswith("R13") or rid.startswith("R13") and "accounts" in str(v) else "|".join(v)
        return str(v)
    out = sql
    for k, v in params.items():
        if rid.startswith("R13") and k == "keywords": v = "|".join(v)
        elif rid.startswith("R13") and k == "accounts": v = ", ".join(f"'{x}'" for x in v)
        else: v = fmt(v)
        out = out.replace("{" + k + "}", v)
    left = re.findall(r"\{[a-z_]+\}", out)
    if left: raise SystemExit(f"{rid}: unresolved params {left}")
    return out

TABLE = "flags" if only is None else "flags_subset"  # partial runs never overwrite the full flags table
con = duckdb.connect(str(paths.DB))
if paths.MACROS: con.execute(paths.macros_sql()).fetchall()
con.execute(f"CREATE OR REPLACE TABLE {TABLE}(rule_id VARCHAR, tx_id BIGINT, evidence JSON, related_tx_ids BIGINT[], severity VARCHAR, rule_version INTEGER)").fetchall()
rows = []
for f in sorted(paths.RULES_SQL_DIR.glob("R*.sql")):
    rid = f.stem
    if only and rid[:3] not in only and rid not in only: continue
    params = {**DEFAULTS.get(rid[:3], {}), **cat.get(rid, {}).get("params", {})}
    for k, v in overrides.items():
        r, p = k.split("."); 
        if r == rid or r == rid[:3]: params[p] = type(params.get(p, v))(v) if p in params and not isinstance(params[p], list) else v
    sql = render(rid, f.read_text(), params)
    try:
        con.execute(f"INSERT INTO {TABLE} SELECT '{rid}', tx_id, evidence::JSON, related::BIGINT[], '{sev(rid)}', {RULE_VERSION} FROM ({sql})").fetchall()
    except Exception as e:
        print(f"!! {rid}: {str(e)[:300]}"); continue
    real, syn = con.execute(f"select sum(case when not t.is_synthetic then 1 else 0 end), sum(case when t.is_synthetic then 1 else 0 end) from {TABLE} f join transactions t using(tx_id) where rule_id='{rid}'").fetchall()[0]
    rows.append((rid, cat.get(rid, {}).get("name", ""), real or 0, syn or 0, json.dumps({k: v for k, v in params.items() if not isinstance(v, list)}, ensure_ascii=False)))
print(f"{'rule':26} {'name':22} {'real':>6} {'synth':>6}  params")
for r in rows: print(f"{r[0]:26} {r[1]:22} {r[2]:6} {r[3]:6}  {r[4]}")
n_real = con.execute("select count(*) from tx_active where not is_synthetic").fetchall()[0][0]
flagged_real = con.execute(f"select count(distinct tx_id) from {TABLE} f join transactions t using(tx_id) where not t.is_synthetic").fetchall()[0][0]
print(f"\nreal transactions flagged by >=1 rule: {flagged_real}/{n_real} = {100.0*flagged_real/n_real:.1f}%")
con.close()
sys.path.insert(0, str(Path(__file__).parent)); import score; score.main(TABLE)
