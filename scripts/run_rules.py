"""Step 3: run every rule in the pack rules dir (paths.RULES_SQL_DIR) against tx_active, record one `rule_runs` row and its `flags`,
print counts (real vs synthetic), then score against ground_truth. Partial runs (--only) write a temp table and never touch `flags`.
Usage: run_rules.py [--set R03_split_payment.window_min=60 ...] [--only R03,R05]
Rule SQL is {param}-rendered text executed without bind parameters, so literal % in rules is safe."""
import sys, re, json, yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import paths
from db import conn as C
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

con = C.connect()
if only is None:
    run_id = C.one(con, "insert into rule_runs(tenant_id, catalog_version) values (tenant(), %s) returning run_id", [RULE_VERSION])
    TABLE = "current_flags"   # view: this tenant's latest run, i.e. the one just created
else:
    run_id = None; TABLE = "flags_subset"
    con.execute("create temp table flags_subset (tx_id bigint, rule_id text, severity text, evidence jsonb, related_tx_ids bigint[], rule_version int)")
rows = []
for f in sorted(paths.RULES_SQL_DIR.glob("R*.sql")):
    rid = f.stem
    if only and rid[:3] not in only and rid not in only: continue
    params = {**DEFAULTS.get(rid[:3], {}), **cat.get(rid, {}).get("params", {})}
    for k, v in overrides.items():
        r, p = k.split(".")
        if r == rid or r == rid[:3]: params[p] = type(params.get(p, v))(v) if p in params and not isinstance(params[p], list) else v
    sql = render(rid, f.read_text(), params)
    try:
        if run_id is not None:
            con.execute(f"insert into flags(tenant_id, run_id, tx_id, rule_id, severity, evidence, related_tx_ids, rule_version) "
                        f"select tenant(), {run_id}, tx_id, '{rid}', '{sev(rid)}', evidence, related, {RULE_VERSION} from ({sql}) s")
        else:
            con.execute(f"insert into flags_subset select tx_id, '{rid}', '{sev(rid)}', evidence, related, {RULE_VERSION} from ({sql}) s")
    except Exception as e:
        print(f"!! {rid}: {str(e)[:300]}"); continue
    real, syn = C.one(con, f"select sum(case when not t.is_synthetic then 1 else 0 end), sum(case when t.is_synthetic then 1 else 0 end) "
                           f"from {TABLE} f join transactions t on t.tenant_id=tenant() and t.tx_id=f.tx_id where f.rule_id='{rid}'")
    rows.append((rid, cat.get(rid, {}).get("name", ""), real or 0, syn or 0, json.dumps({k: v for k, v in params.items() if not isinstance(v, list)}, ensure_ascii=False)))
print(f"{'rule':26} {'name':22} {'real':>6} {'synth':>6}  params")
for r in rows: print(f"{r[0]:26} {r[1]:22} {r[2]:6} {r[3]:6}  {r[4]}")
n_real = C.one(con, "select count(*) from tx_active where not is_synthetic")
flagged_real = C.one(con, f"select count(distinct f.tx_id) from {TABLE} f join transactions t on t.tenant_id=tenant() and t.tx_id=f.tx_id where not t.is_synthetic")
print(f"\nreal transactions flagged by >=1 rule: {flagged_real}/{n_real} = {100.0*flagged_real/n_real:.1f}%")
if run_id is not None:
    con.execute("update rule_runs set n_flags=(select count(*) from flags where tenant_id=tenant() and run_id=%s) where tenant_id=tenant() and run_id=%s", [run_id, run_id])
    print(f"rule_runs.run_id={run_id}")
sys.path.insert(0, str(Path(__file__).parent)); import score; score.main(TABLE, con); con.close()
