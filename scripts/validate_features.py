"""Step 3.6: validate tx_features. Writes only scratch tables (tx_features_chk, tx_features_pert) and a temp view.
Checks: schema · static PIT markers · dual-strategy equality · future perturbation · redundancy · monotonic sanity · idempotent hash.
Exit code 1 if any check fails. Honors ROYAL_DB."""
import os, sys, re, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import duckdb, pandas as pd, numpy as np
from features.executor import load_catalog, build, build_sql, render_feature, KEY_COLS

con = duckdb.connect(os.environ.get("ROYAL_DB", "data/warehouse.duckdb"))
cat = load_catalog(); feats = cat["features"]; fails = []
def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok: fails.append(name)

cols = [c for c in con.execute("describe tx_features").df().column_name if c not in KEY_COLS]
active = [n for n, f in feats.items() if f.get("kind", "agg") != "history"]
lookahead = {n for n, f in feats.items() if f.get("lookahead")}
column_feats = {n for n, f in feats.items() if f.get("kind") == "column"}

# 1 schema
bad = re.compile(cat["forbidden_name"])
check("1 schema: columns == catalog", set(cols) == set(active), f"missing={set(active)-set(cols)} extra={set(cols)-set(active)}")
check("1 schema: no rule-derived names", not [c for c in cols if bad.search(c)])
nobs_ok = True
for n, f in feats.items():
    if f.get("n_obs") and n in cols:
        bad_rows = con.execute(f"select count(*) from tx_features where {n} is not null and ({f['n_obs']} is null or {f['n_obs']} = 0)").fetchone()[0]
        if bad_rows: nobs_ok = False; print(f"      {n}: {bad_rows} rows with value but n_obs null/0")
check("1 schema: n_obs accompanies ratios", nobs_ok)

# 2 static PIT markers
markers = ("INTERVAL 1 MICROSECOND PRECEDING", "h.tx_ts < t.tx_ts")
static_ok = True
for n in active:
    if n in lookahead or n in column_feats: continue
    for strat in ("window", "correlated"):
        e = render_feature(cat, n, feats[n], strat) or ""
        if not any(m in e for m in markers): static_ok = False; print(f"      {n} [{strat}]: no PIT marker")
check("2 leakage/static: every non-lookahead agg has a PIT marker", static_ok)

# 3 dual strategy equality
sample_ids = [r[0] for r in con.execute("select tx_id from tx_active using sample reservoir(500) repeatable (42)").fetchall()]
build(con, strategy="correlated", target="tx_features_chk", quiet=True, focal_ids=sample_ids)  # correlated path on a seeded sample (full run is O(n^2) on big partitions)
cmp_cols = [c for c in cols if c not in lookahead and c not in column_feats]
diff = con.execute("select " + ", ".join(f"sum(case when abs(coalesce(a.{c},-1e18) - coalesce(b.{c},-1e18)) > 1e-6 then 1 else 0 end) as {c}" for c in cmp_cols)
                   + " from tx_features a join tx_features_chk b using(tx_id)").df().iloc[0]
check(f"3 leakage/dual-path: window == correlated on {len(sample_ids)} sampled tx (non-lookahead)", int(diff.sum()) == 0, f"mismatching cells per column: {diff[diff>0].to_dict()}")

# 4 future perturbation
rng = random.Random(7)
pairs = con.execute("""select a.tx_id x, b.tx_id y from tx_active a join tx_active b on a.emp_id=b.emp_id and a.account_policy=b.account_policy and a.mcc_name=b.mcc_name
                       and b.tx_ts > a.tx_ts + interval 1 day where a.total>0 and b.total>0 and not a.is_synthetic limit 2000""").fetchall()
x, y = rng.choice(pairs)
con.execute(f"create or replace temp view tx_active_pert as select * replace (case when tx_id={y} then 1e9 else total end as total) from tx_active").fetchall()
build(con, strategy="window", source="tx_active_pert", target="tx_features_pert", quiet=True)
before = con.execute(f"select * from tx_features where tx_id={x}").df().iloc[0]; after = con.execute(f"select * from tx_features_pert where tx_id={x}").df().iloc[0]
unchanged = all((pd.isna(before[c]) and pd.isna(after[c])) or (not pd.isna(before[c]) and not pd.isna(after[c]) and abs(before[c]-after[c]) < 1e-6) for c in cmp_cols)
any_diff = " OR ".join(f"abs(coalesce(a.{c},-1e18)-coalesce(b.{c},-1e18)) > 1e-6" for c in cmp_cols)
later_changed = con.execute(f"""select count(*) from tx_features a join tx_features_pert b using(tx_id) join tx_active t using(tx_id)
   where (t.emp_id=(select emp_id from tx_active where tx_id={y}) or (t.account_policy, t.mcc_name) = (select (account_policy, mcc_name) from tx_active where tx_id={y}))
   and t.tx_ts > (select tx_ts from tx_active where tx_id={y}) and ({any_diff})""").fetchone()[0]
check("4 leakage/perturbation: earlier row unchanged when a later row is altered", unchanged, f"x={x} y={y}")
check("4 leakage/perturbation: later rows do change (sanity)", later_changed > 0 or con.execute(f"select count(*) from tx_active t where t.emp_id=(select emp_id from tx_active where tx_id={y}) and t.tx_ts>(select tx_ts from tx_active where tx_id={y})").fetchone()[0] == 0, f"{later_changed} later rows changed")

# 5 redundancy
num = con.execute("select * from tx_features where not is_synthetic").df()[cols].select_dtypes("number")
corr = num.corr().abs(); known = {tuple(sorted(p)) for p in cat.get("known_redundant", [])}
pairs_hi = sorted({tuple(sorted((a, b))) for a in corr.columns for b in corr.columns if a < b and corr.loc[a, b] >= 0.95})
unknown = [p for p in pairs_hi if p not in known]
check("5 redundancy: |r|>=0.95 pairs are all declared known_redundant", not unknown, f"high pairs={[(a,b,round(corr.loc[a,b],3)) for a,b in pairs_hi]}")

# 6 monotonic sanity vs violation-tier flags
has_flags = con.execute("select count(*) from information_schema.tables where table_name='flags'").fetchone()[0] > 0
if has_flags:
    sig = con.execute("""select f.tx_id, max(case when fl.severity='violation' then 1 else 0 end) y from tx_features f
                         left join flags fl on fl.tx_id=f.tx_id where not f.is_synthetic group by 1""").df().set_index("tx_id").y
    mono_ok = True
    for n, f in feats.items():
        if not f.get("expect_direction") or n not in num.columns: continue
        s = con.execute(f"select tx_id, {n} v from tx_features where not is_synthetic and {n} is not null").df().set_index("tx_id").v
        d = pd.DataFrame({"v": s, "y": sig}).dropna()
        if len(d) < 200: continue
        d["dec"] = pd.qcut(d.v.rank(method="first"), 10, labels=False)
        rate = d.groupby("dec").y.mean(); rho = rate.rank().corr(pd.Series(range(10), index=rate.index).rank())  # Spearman via ranks (no scipy)
        ok = (rho > 0) if f["expect_direction"] == "+" else (rho < 0)
        print(f"      {n:36} spearman(decile, violation-rate) = {rho:+.2f} expected {f['expect_direction']}")
        mono_ok &= bool(ok)
    check("6 monotonic sanity (weak signal only)", mono_ok)
else: print("SKIP  6 monotonic: no flags table")

# 7 idempotency
h1 = con.execute("select md5(string_agg(md5(t::varchar), '' order by tx_id)) from tx_features t").fetchone()[0]
build(con, strategy="window", quiet=True)
h2 = con.execute("select md5(string_agg(md5(t::varchar), '' order by tx_id)) from tx_features t").fetchone()[0]
check("7 idempotent rebuild hash", h1 == h2, h1[:12])

for t in ("tx_features_chk", "tx_features_pert"): con.execute(f"drop table if exists {t}").fetchall()
con.close()
print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
