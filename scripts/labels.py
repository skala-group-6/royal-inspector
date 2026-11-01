"""Step 3.7: labels for the prioritization model. One script, three sources — the label source is mandatory.
  --label-source weak     rule votes → noisy-OR probability per tx (labels/weak.yaml). No human labels needed.
  --label-source reviews  --reviewers A,B : latest non-superseded auditor decisions (violation=1, ok=0, hold dropped)
  --label-source import   --file F        : past audit outcomes (xlsx/csv). Columns: tx_id OR (emp_id, tx_ts|tx_date, total); decision; decided_at; reason
Output table labels(tx_id, prob, label_source, source_version, n_votes, clusters_hit, created_at), replaced per source.
Synthetic rows are included (validation needs them); training must exclude them via tx_active.is_synthetic. Honors ROYAL_DB."""
from __future__ import annotations
import os, sys, argparse, hashlib, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import yaml, duckdb, pandas as pd

WEAK_CFG = ROOT / "labels" / "weak.yaml"; RULES_CFG = ROOT / "rules" / "catalog.yaml"
DDL = "CREATE TABLE IF NOT EXISTS labels(tx_id BIGINT, prob DOUBLE, label_source VARCHAR, source_version VARCHAR, n_votes INTEGER, clusters_hit VARCHAR[], created_at TIMESTAMP)"

# ---------- config ----------
def load_weak_cfg(path=WEAK_CFG, rules_path=RULES_CFG) -> dict:
    cfg = yaml.safe_load(open(path)); rules = yaml.safe_load(open(rules_path))
    rule_ids = set(rules["rules"]); seen = {}
    for c, members in cfg["clusters"].items():
        for r in members:
            if r not in rule_ids: raise ValueError(f"cluster {c}: unknown rule {r}")
            if r in seen: raise ValueError(f"rule {r} in two clusters: {seen[r]}, {c}")
            seen[r] = c
    missing = rule_ids - set(seen)
    if missing: raise ValueError(f"rules without a cluster: {sorted(missing)}")
    for k, v in list(cfg["p_tier"].items()) + list(cfg.get("p_rule", {}).items()) + [("prior", cfg["prior"])]:
        if not (0 < float(v) < 1): raise ValueError(f"{k}: probability must be in (0,1), got {v}")
    for r in cfg.get("p_rule", {}):
        if r not in rule_ids: raise ValueError(f"p_rule: unknown rule {r}")
    cfg["_rule_p"] = pd.DataFrame([dict(rule_id=r, cluster=c, p=float(cfg.get("p_rule", {}).get(r, cfg["p_tier"][rules["rules"][r]["tier"]]))) for r, c in seen.items()])
    cfg["_rules_version"] = int(rules.get("version", 1))
    return cfg

# ---------- sources ----------
def weak_labels(con, cfg, flags_table="flags") -> pd.DataFrame:
    con.register("rule_p", cfg["_rule_p"])
    ver = f"rules_v{cfg['_rules_version']}+weak_v{cfg['version']}"
    df = con.execute(f"""
      WITH votes AS (SELECT f.tx_id, r.cluster, max(r.p) p, count(*) n FROM {flags_table} f JOIN rule_p r USING(rule_id) GROUP BY 1,2),
      agg AS (SELECT tx_id, 1 - (1 - ?) * product(1 - p) prob, sum(n)::int n_votes, list(cluster ORDER BY cluster) clusters_hit FROM votes GROUP BY 1)
      SELECT t.tx_id, round(coalesce(a.prob, ?), 6) prob, 'weak' label_source, ? source_version,
             coalesce(a.n_votes, 0) n_votes, coalesce(a.clusters_hit, []) clusters_hit
      FROM tx_active t LEFT JOIN agg a USING(tx_id) ORDER BY t.tx_id""", [cfg["prior"], cfg["prior"], ver]).df()
    con.unregister("rule_p"); return df

def review_labels(con, reviewers: list[str]) -> pd.DataFrame:
    ph = ",".join("?" * len(reviewers))
    return con.execute(f"""
      SELECT r.tx_id, max(CASE WHEN r.decision='violation' THEN 1 ELSE 0 END)::DOUBLE prob, 'reviews' label_source,
             ? source_version, count(*)::int n_votes, []::VARCHAR[] clusters_hit
      FROM reviews r WHERE r.superseded_by IS NULL AND r.decision IN ('violation','ok') AND r.reviewer IN ({ph})
      GROUP BY r.tx_id ORDER BY r.tx_id""", ["reviewers=" + ",".join(sorted(reviewers))] + list(reviewers)).df()

DECISION = {"violation": 1.0, "위반": 1.0, "부적정": 1.0, "ok": 0.0, "적정": 0.0, "아님": 0.0, "hold": None, "보류": None}
def import_labels(con, path: str) -> tuple[pd.DataFrame, dict]:
    p = Path(path); raw = pd.read_excel(p) if p.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(p)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    raw["_y"] = raw["decision"].astype(str).str.strip().str.lower().map(lambda v: DECISION.get(v, DECISION.get(v.upper() if False else v)))
    raw = raw[raw["_y"].notna()]
    if "decided_at" in raw: raw = raw.sort_values("decided_at")
    stats = dict(rows=len(raw), by_tx_id=0, by_key=0, ambiguous=0, unmatched=0)
    out = []
    tx = con.execute("select tx_id, emp_id, tx_date, total from tx_active").df()
    if "tx_id" in raw:
        m = raw.dropna(subset=["tx_id"]).drop_duplicates("tx_id", keep="last")
        ok = m[m.tx_id.astype(int).isin(tx.tx_id)]; stats["by_tx_id"] = len(ok)
        out.append(pd.DataFrame(dict(tx_id=ok.tx_id.astype(int), prob=ok._y.astype(float))))
        raw = raw[~raw.index.isin(m.index)] if "emp_id" in raw else raw.iloc[0:0]
    if len(raw) and {"emp_id", "total"} <= set(raw.columns) and ("tx_date" in raw or "tx_ts" in raw):
        raw = raw.assign(_d=pd.to_datetime(raw["tx_ts"] if "tx_ts" in raw else raw["tx_date"]).dt.date)
        key = tx.assign(_d=pd.to_datetime(tx.tx_date).dt.date)
        j = raw.merge(key, left_on=["emp_id", "_d", "total"], right_on=["emp_id", "_d", "total"], how="left")
        cnt = j.groupby(j.index).tx_id.transform("count")
        stats["unmatched"] = int(j.tx_id.isna().sum()); stats["ambiguous"] = int(((cnt > 1) & j.tx_id.notna()).sum())
        good = j[(cnt == 1) & j.tx_id.notna()]; stats["by_key"] = len(good)
        out.append(pd.DataFrame(dict(tx_id=good.tx_id.astype(int), prob=good._y.astype(float))))
    df = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["tx_id", "prob"])
    df = df.drop_duplicates("tx_id", keep="last").sort_values("tx_id")
    ver = "import:" + hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    df["label_source"] = "import"; df["source_version"] = ver; df["n_votes"] = 1; df["clusters_hit"] = [[] for _ in range(len(df))]
    return df.reset_index(drop=True), stats

# ---------- write / hash ----------
def write_labels(con, df: pd.DataFrame):
    con.execute(DDL).fetchall()
    src = df.label_source.iloc[0] if len(df) else None
    if src: con.execute("DELETE FROM labels WHERE label_source = ?", [src]).fetchall()
    df = df.assign(created_at=dt.datetime.now())
    con.register("df", df); con.execute("INSERT INTO labels SELECT tx_id, prob, label_source, source_version, n_votes, clusters_hit, created_at FROM df").fetchall(); con.unregister("df")

def labels_hash(con, source) -> str:
    return con.execute("select md5(string_agg(md5((tx_id, prob, n_votes, clusters_hit)::varchar), '' order by tx_id)) from labels where label_source=?", [source]).fetchall()[0][0]

# ---------- validation (weak) ----------
def validate_weak(con, cfg, df: pd.DataFrame, flags_table="flags") -> dict:
    v = cfg["validation"]; out = {}
    real = con.execute("select l.prob from labels l join tx_active t using(tx_id) where l.label_source='weak' and not t.is_synthetic").df().prob
    out["real_quantiles"] = real.quantile([.05, .25, .5, .75, .95, .99]).round(3).to_dict(); out["real_mean"] = round(float(real.mean()), 4)
    out["real_share_gt_05"] = round(float((real > 0.5).mean()), 4); out["real_share_prior"] = round(float((real == cfg["prior"]).mean()), 4)
    planted = con.execute("select l.prob from labels l where l.label_source='weak' and tx_id in (select tx_id from ground_truth)").df().prob
    normal = con.execute("select l.prob from labels l join tx_active t using(tx_id) where l.label_source='weak' and t.is_synthetic and tx_id not in (select tx_id from ground_truth)").df().prob
    out["planted_mean"], out["synthetic_normal_mean"] = round(float(planted.mean()), 4), round(float(normal.mean()), 4)
    out["planted_ok"] = out["planted_mean"] >= v["planted_min_mean"] and out["planted_mean"] / max(out["synthetic_normal_mean"], 1e-9) >= v["planted_over_normal_min"]
    # leave-one-rule-out on real rows
    fl = con.execute(f"select f.tx_id, f.rule_id from {flags_table} f join tx_active t using(tx_id) where not t.is_synthetic").df().merge(cfg["_rule_p"], on="rule_id")
    n_real = int(con.execute("select count(*) from tx_active where not is_synthetic").fetchall()[0][0]); prior = cfg["prior"]
    def mean_prob(sub):
        pc = sub.groupby(["tx_id", "cluster"]).p.max().reset_index()
        tx_prob = 1 - (1 - prior) * pc.assign(q=1 - pc.p).groupby("tx_id").q.prod()
        return (tx_prob.sum() + prior * (n_real - len(tx_prob))) / n_real
    base = mean_prob(fl); loro = {r: base - mean_prob(fl[fl.rule_id != r]) for r in fl.rule_id.unique()}
    share = {r: d / max(base - prior, 1e-9) for r, d in loro.items()}
    top = sorted(share.items(), key=lambda kv: -kv[1])[:3]
    out["loro_top3"] = [(r, round(s, 3)) for r, s in top]; out["loro_ok"] = all(s <= v["max_single_rule_share"] for _, s in top)
    return out

def print_report(out, cfg):
    print(f"[weak] real rows: mean {out['real_mean']} · >0.5 {out['real_share_gt_05']:.1%} · ==prior {out['real_share_prior']:.1%} · quantiles {out['real_quantiles']}")
    print(f"[weak] planted mean {out['planted_mean']} vs synthetic-normal mean {out['synthetic_normal_mean']} → {'PASS' if out['planted_ok'] else 'FAIL'}")
    print(f"[weak] leave-one-rule-out share of (mean−prior): {out['loro_top3']} → {'PASS' if out['loro_ok'] else 'FAIL (> ' + str(cfg['validation']['max_single_rule_share']) + ')'}")

# ---------- CLI ----------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label-source", required=True, choices=["weak", "reviews", "import"])
    ap.add_argument("--reviewers", default=None, help="comma-separated reviewer names (reviews)")
    ap.add_argument("--file", default=None, help="xlsx/csv of past audit outcomes (import)")
    ap.add_argument("--config", default=str(WEAK_CFG)); ap.add_argument("--quiet", action="store_true"); ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args()
    if a.label_source == "reviews" and not a.reviewers: ap.error("--reviewers is required with --label-source reviews")
    if a.label_source == "import" and not a.file: ap.error("--file is required with --label-source import")
    con = duckdb.connect(os.environ.get("ROYAL_DB", "data/warehouse.duckdb"))
    if a.label_source == "weak":
        cfg = load_weak_cfg(a.config); df = weak_labels(con, cfg); write_labels(con, df)
        if not a.quiet: print(f"labels[weak]: {len(df):,} rows · version {df.source_version.iloc[0]} · hash {labels_hash(con, 'weak')[:12]}")
        if not a.no_validate:
            out = validate_weak(con, cfg, df)
            if not a.quiet: print_report(out, cfg)
            if not (out["planted_ok"] and out["loro_ok"]): sys.exit(1)
    elif a.label_source == "reviews":
        df = review_labels(con, [r.strip() for r in a.reviewers.split(",") if r.strip()]); write_labels(con, df)
        if not a.quiet: print(f"labels[reviews]: {len(df):,} tx · positives {int((df.prob==1).sum())} · {df.source_version.iloc[0] if len(df) else ''}")
    else:
        df, st = import_labels(con, a.file); write_labels(con, df)
        if not a.quiet: print(f"labels[import]: {len(df):,} tx matched · {st}")
    con.close()
