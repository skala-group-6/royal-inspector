"""Step 3.7: labels for the prioritization model. One script, three sources — the label source is mandatory.
  --label-source weak     rule votes → noisy-OR probability per tx (pack weak_labels.yaml; clusters from rules/catalog.yaml). No human labels needed.
  --label-source reviews  --reviewers A,B : latest non-superseded auditor decisions (violation=1, ok=0, hold dropped)
  --label-source import   --file F        : past audit outcomes (xlsx/csv). Columns: tx_id OR (emp_id, tx_ts|tx_date, total); decision; decided_at; reason
Output table labels (current tenant), replaced per source. Flags are read from current_flags (latest rule run).
Synthetic rows are included (validation needs them); training must exclude them via tx_active.is_synthetic. Uses DATABASE_URL."""
from __future__ import annotations
import os, sys, argparse, hashlib, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import yaml, pandas as pd
import paths
from db import conn as C

WEAK_CFG = paths.WEAK_LABELS; RULES_CFG = paths.RULES_CATALOG
FLAGS = "current_flags"

# ---------- config ----------
def load_weak_cfg(path=WEAK_CFG, rules_path=RULES_CFG) -> dict:
    cfg = yaml.safe_load(open(path)); rules = yaml.safe_load(open(rules_path))
    rule_ids = set(rules["rules"])
    seen = {r: v.get("cluster") for r, v in rules["rules"].items()}          # cluster lives in the rule catalog (one place)
    missing = [r for r, c in seen.items() if not c]
    if missing: raise ValueError(f"rules without a cluster in the catalog: {sorted(missing)}")
    for k, v in list(cfg["p_tier"].items()) + list(cfg.get("p_rule", {}).items()) + [("prior", cfg["prior"])]:
        if not (0 < float(v) < 1): raise ValueError(f"{k}: probability must be in (0,1), got {v}")
    for r in cfg.get("p_rule", {}):
        if r not in rule_ids: raise ValueError(f"p_rule: unknown rule {r}")
    cfg["_rule_p"] = pd.DataFrame([dict(rule_id=r, cluster=c, p=float(cfg.get("p_rule", {}).get(r, cfg["p_tier"][rules["rules"][r]["tier"]]))) for r, c in seen.items()])
    cfg["_rules_version"] = int(rules.get("version", 1))
    return cfg

# ---------- sources ----------
def _rule_p_table(con, cfg):
    con.execute("DROP TABLE IF EXISTS rule_p"); con.execute("CREATE TEMP TABLE rule_p(rule_id text, cluster text, p float8)")
    C.write_df(con, "rule_p", cfg["_rule_p"], tenant=False)

def weak_labels(con, cfg, flags_table=FLAGS) -> pd.DataFrame:
    _rule_p_table(con, cfg)
    ver = f"rules_v{cfg['_rules_version']}+weak_v{cfg['version']}"
    df = C.q(con, f"""
      WITH votes AS (SELECT f.tx_id, r.cluster, max(r.p) p, count(*) n FROM {flags_table} f JOIN rule_p r USING(rule_id) GROUP BY 1,2),
      agg AS (SELECT tx_id, 1 - (1 - %s) * exp(sum(ln(1 - p))) prob, sum(n)::int n_votes, array_agg(cluster ORDER BY cluster) clusters_hit FROM votes GROUP BY 1)
      SELECT t.tx_id, round(coalesce(a.prob, %s)::numeric, 6)::float8 prob, 'weak' label_source, %s source_version,
             coalesce(a.n_votes, 0) n_votes, coalesce(a.clusters_hit, '{{}}'::text[]) clusters_hit
      FROM tx_active t LEFT JOIN agg a USING(tx_id) ORDER BY t.tx_id""", [cfg["prior"], cfg["prior"], ver])
    return df

def review_labels(con, reviewers: list[str]) -> pd.DataFrame:
    """Latest non-superseded decisions by the named reviewers (reviewers.name). violation=1, ok=0, hold dropped."""
    return C.q(con, """
      SELECT r.tx_id, max(CASE WHEN r.decision='violation' THEN 1 ELSE 0 END)::float8 prob, 'reviews' label_source,
             %s source_version, count(*)::int n_votes, '{}'::text[] clusters_hit
      FROM latest_reviews r JOIN reviewers v ON v.tenant_id = r.tenant_id AND v.reviewer_id = r.reviewer_id
      WHERE r.decision IN ('violation','ok') AND v.name = ANY(%s)
      GROUP BY r.tx_id ORDER BY r.tx_id""", ["reviewers=" + ",".join(sorted(reviewers)), list(reviewers)])

DECISION = {"violation": 1.0, "위반": 1.0, "부적정": 1.0, "ok": 0.0, "적정": 0.0, "아님": 0.0, "hold": None, "보류": None}
def import_labels(con, path: str) -> tuple[pd.DataFrame, dict]:
    p = Path(path); raw = pd.read_excel(p, dtype=str) if p.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(p, dtype=str)   # dtype=str: tx_id is a 64-bit hash, a float column would lose digits
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    if "tx_id" in raw: raw["tx_id"] = raw["tx_id"].str.strip().replace({"": None}).astype("Int64")
    raw["_y"] = raw["decision"].astype(str).str.strip().str.lower().map(DECISION.get)
    raw = raw[raw["_y"].notna()]
    if "decided_at" in raw: raw = raw.sort_values("decided_at")
    stats = dict(rows=len(raw), by_tx_id=0, by_key=0, ambiguous=0, unmatched=0)
    out = []
    tx = C.q(con, "select tx_id, emp_id, tx_date, total from tx_active")
    if "tx_id" in raw:
        m = raw.dropna(subset=["tx_id"]).drop_duplicates("tx_id", keep="last")
        ok = m[m.tx_id.astype(int).isin(tx.tx_id)]; stats["by_tx_id"] = len(ok)
        out.append(pd.DataFrame(dict(tx_id=ok.tx_id.astype(int), prob=ok._y.astype(float))))
        raw = raw[~raw.index.isin(m.index)] if "emp_id" in raw else raw.iloc[0:0]
    if len(raw) and {"emp_id", "total"} <= set(raw.columns) and ("tx_date" in raw or "tx_ts" in raw):
        r2 = raw.dropna(subset=["emp_id", "total"]).drop(columns=[c for c in ("tx_id",) if c in raw.columns]).reset_index(drop=True).reset_index().rename(columns={"index": "_src"})
        r2 = r2.assign(emp_id=pd.to_numeric(r2.emp_id).astype(int), total=pd.to_numeric(r2.total).astype(float), _d=pd.to_datetime(r2["tx_ts"] if "tx_ts" in r2 else r2["tx_date"]).dt.date)
        key = tx.assign(_d=pd.to_datetime(tx.tx_date).dt.date, emp_id=tx.emp_id.astype(int), total=tx.total.astype(float))[["tx_id", "emp_id", "_d", "total"]]
        j = r2.merge(key, on=["emp_id", "_d", "total"], how="left")
        cnt = j.groupby("_src").tx_id.transform("count")
        stats["unmatched"] = int(j.tx_id.isna().sum()); stats["ambiguous"] = int(j[(cnt > 1) & j.tx_id.notna()]._src.nunique())
        good = j[(cnt == 1) & j.tx_id.notna()]; stats["by_key"] = len(good)
        out.append(pd.DataFrame(dict(tx_id=good.tx_id.astype(int), prob=good._y.astype(float))))
    df = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["tx_id", "prob"])
    df = df.drop_duplicates("tx_id", keep="first").sort_values("tx_id")  # explicit tx_id match (appended first) beats key-inferred match
    ver = "import:" + hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    df["label_source"] = "import"; df["source_version"] = ver; df["n_votes"] = 1; df["clusters_hit"] = [[] for _ in range(len(df))]
    return df.reset_index(drop=True), stats

# ---------- write / hash ----------
def write_labels(con, df: pd.DataFrame):
    """Replace this tenant's rows of the frame's label_source."""
    src = df.label_source.iloc[0] if len(df) else None
    if src: C.execute(con, "DELETE FROM labels WHERE tenant_id = tenant() AND label_source = %s", [src])
    if len(df): C.write_df(con, "labels", df[["tx_id", "prob", "label_source", "source_version", "n_votes", "clusters_hit"]])

def labels_hash(con, source) -> str:
    return C.one(con, "select md5(string_agg(md5((tx_id, prob, n_votes, clusters_hit)::text), '' order by tx_id)) from labels where tenant_id = tenant() and label_source = %s", [source])

# ---------- validation (weak) ----------
def validate_weak(con, cfg, df: pd.DataFrame, flags_table=FLAGS) -> dict:
    v = cfg["validation"]; out = {}
    L = "labels l join tx_active t on t.tenant_id = l.tenant_id and t.tx_id = l.tx_id where l.tenant_id = tenant() and l.label_source='weak'"
    GT = "select tx_id from ground_truth where tenant_id = tenant()"
    real = C.q(con, f"select l.prob from {L} and not t.is_synthetic").prob
    out["real_quantiles"] = real.quantile([.05, .25, .5, .75, .95, .99]).round(3).to_dict(); out["real_mean"] = round(float(real.mean()), 4)
    out["real_share_gt_05"] = round(float((real > 0.5).mean()), 4); out["real_share_prior"] = round(float((real == cfg["prior"]).mean()), 4)
    planted = C.q(con, f"select l.prob from {L} and l.tx_id in ({GT})").prob
    normal = C.q(con, f"select l.prob from {L} and t.is_synthetic and l.tx_id not in ({GT})").prob
    out["planted_mean"], out["synthetic_normal_mean"] = round(float(planted.mean()), 4), round(float(normal.mean()), 4)
    out["planted_ok"] = out["planted_mean"] >= v["planted_min_mean"] and out["planted_mean"] / max(out["synthetic_normal_mean"], 1e-9) >= v["planted_over_normal_min"]
    # leave-one-rule-out on real rows
    fl = C.q(con, f"select f.tx_id, f.rule_id from {flags_table} f join tx_active t on t.tx_id = f.tx_id where not t.is_synthetic").merge(cfg["_rule_p"], on="rule_id")
    n_real = int(C.one(con, "select count(*) from tx_active where not is_synthetic")); prior = cfg["prior"]
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
    con = C.connect()
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
