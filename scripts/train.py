"""Step 3.8: train candidate scorers on the same time-split exam and keep the winner only if it beats the baseline.
  train.py --label-source {weak|reviews|import} [--reviewers A,B] [--split-date 2025-03-01] [--k 100,500] [--out models]
Writes models/<version>/{<candidate>.pkl, manifest.json}, models/LATEST, and one model_versions row per candidate (model_version = <version>__<candidate>).
Uses DATABASE_URL (current tenant). Synthetic rows are never used."""
from __future__ import annotations
import os, sys, re, json, argparse, hashlib, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import paths
import numpy as np, pandas as pd, yaml
from db import conn as C
from sklearn.metrics import average_precision_score
from features.executor import load_catalog, KEY_COLS
from models.base import DEMO_DISCLAIMER, save_model
from models.baseline import RuleAmountBaseline
from models.logistic import LogisticScorer
from models.xgb import XgbScorer

RANDOM_STATE = 0
def candidates(): return [RuleAmountBaseline(), LogisticScorer(RANDOM_STATE), XgbScorer(RANDOM_STATE)]

def feature_columns(cat) -> tuple[list[str], list[str]]:
    feats = [n for n, f in cat["features"].items() if f.get("kind", "agg") != "history"]
    look = [n for n in feats if cat["features"][n].get("lookahead")]
    return [n for n in feats if n not in look], look

def load_xy(con, label_source, reviewers=None, split_date="2025-03-01"):
    cat = load_catalog(); use, look = feature_columns(cat); bad = re.compile(cat["forbidden_name"])
    assert not [c for c in use if bad.search(c)], "rule-derived column in features"
    df = C.q(con, """
      select f.*, l.prob, l.source_version, t.total, t.tx_date as d, t.is_synthetic as syn,
             coalesce(a.n_rules, 0) n_rules, coalesce(a.n_violation_rules, 0) n_violation_rules
      from tx_features f join tx_active t on t.tx_id = f.tx_id
      join labels l on l.tenant_id = f.tenant_id and l.tx_id = f.tx_id and l.label_source = %s
      left join (select tx_id, count(distinct rule_id) n_rules, count(distinct case when severity='violation' then rule_id end) n_violation_rules from current_flags group by 1) a on a.tx_id = f.tx_id
      where f.tenant_id = tenant() order by f.tx_id""", [label_source])
    df = df[~df.syn.astype(bool)].reset_index(drop=True)
    X = df[use].astype(float); y = (df.prob >= 0.5).astype(int); aux = df[["n_rules", "n_violation_rules", "total"]].astype(float)
    split = pd.Timestamp(split_date).date(); d = pd.to_datetime(df.d).dt.date
    tr, te = (d < split).to_numpy(), (d >= split).to_numpy()
    meta = dict(label_source=label_source, label_version=str(df.source_version.iloc[0]) if len(df) else None, reviewers=reviewers, split_date=str(split),
                train=dict(**{"from": str(d[tr].min()), "to": str(d[tr].max())}, n=int(tr.sum()), n_pos=int(y[tr].sum())),
                test=dict(**{"from": str(d[te].min()), "to": str(d[te].max())}, n=int(te.sum()), n_pos=int(y[te].sum())),
                features=use, dropped=dict(key_cols=KEY_COLS, lookahead=look, aux_only=["n_rules", "n_violation_rules", "total"]), tx_id=df.tx_id.to_numpy())
    if y[tr].nunique() < 2 or y[te].nunique() < 2: raise SystemExit("train/test must both contain positives and negatives")
    return X, y, aux, tr, te, meta

def precision_at_k(y, s, ids, k):
    order = np.lexsort((ids, -s)); return float(np.mean(np.asarray(y)[order[:k]])) if len(y) >= k else float("nan")

def evaluate(name, s, y, ids, base_s, aux, ks):
    out = {f"p_at_{k}": round(precision_at_k(y, s, ids, k), 4) for k in ks}
    out["pr_auc"] = round(float(average_precision_score(y, s)), 4)
    flagged = aux["n_rules"].to_numpy() > 0
    out["p_at_100_flagged"] = round(precision_at_k(y[flagged], s[flagged], ids[flagged], 100), 4)
    out["spearman_vs_baseline"] = round(float(pd.Series(s).corr(pd.Series(base_s), method="spearman")), 4)
    top = lambda v: set(ids[np.lexsort((ids, -v))[:100]])
    out["overlap_at_100"] = round(len(top(s) & top(base_s)) / 100, 2); out["learned_nothing"] = bool(out["overlap_at_100"] >= 0.95)
    return out

def snapshot(con):
    h = lambda t, cols: C.one(con, f"select md5(string_agg(md5(({cols})::text), '' order by tx_id)) from {t} where tenant_id = tenant()")
    return dict(tx_features_hash=h("tx_features", "tx_id, user__all__n_tx, user__all__amount_ratio_median, acct_mcc__all__amount_pctile"), labels_hash=h("labels", "tx_id, prob, label_source"))

def register_versions(con, manifest: dict, d: Path):
    """One model_versions row per candidate (idempotent on re-run of the same version). The exam result is the row's metrics."""
    for name, mv in manifest["model_versions"].items():
        art = d / f"{name}.pkl"
        C.execute(con, """insert into model_versions(tenant_id, model_version, model_id, plug, params, label_source, label_version, split_date, metrics, status, artifact_path, artifact_hash)
                          values (tenant(), %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, 'ok', %s, %s)
                          on conflict (tenant_id, model_version) do update set metrics = excluded.metrics, artifact_path = excluded.artifact_path, artifact_hash = excluded.artifact_hash""",
                  [mv, name, manifest["plugs"][name], json.dumps(dict(random_state=manifest["random_state"], version=manifest["version"])), manifest["label_source"], manifest["label_version"],
                   manifest["split"]["split_date"], json.dumps(manifest["candidates"][name]), str(art), hashlib.sha1(art.read_bytes()).hexdigest()])

def train(con, label_source, reviewers=None, split_date="2025-03-01", ks=(100, 500), out="models", quiet=False) -> dict:
    X, y, aux, tr, te, meta = load_xy(con, label_source, reviewers, split_date)
    ids_te = meta["tx_id"][te]; results, scores, fitted = {}, {}, {}
    for m in candidates():
        m.fit(X[tr], y[tr], aux[tr]); s = np.asarray(m.predict(X[te], aux[te]), dtype=float); fitted[m.name] = m; scores[m.name] = s
    base = scores["baseline"]
    for name, s in scores.items():
        results[name] = evaluate(name, s, y[te].to_numpy(), ids_te, base, aux[te].reset_index(drop=True), ks); results[name]["backend"] = name
    learned = [n for n in results if n != "baseline"]
    best = max(learned, key=lambda n: (results[n]["p_at_100"], results[n]["pr_auc"]))
    beats = results[best]["p_at_100"] > results["baseline"]["p_at_100"]
    chosen = best if beats else "baseline"
    version = f"v{dt.datetime.now():%Y%m%d-%H%M%S}_{label_source}"
    cat = load_catalog(); rules = yaml.safe_load(open(paths.RULES_CATALOG)); weak = yaml.safe_load(open(paths.WEAK_LABELS))
    manifest = dict(version=version, created_at=dt.datetime.now().isoformat(timespec="seconds"), label_source=label_source, label_version=meta["label_version"], reviewers=reviewers,
                    split=dict(split_date=meta["split_date"], train=meta["train"], test=meta["test"]), features=meta["features"], dropped=meta["dropped"],
                    candidates=results, chosen=chosen, beats_baseline=bool(beats),
                    snapshot=dict(**snapshot(con), features_catalog_version=cat["version"], rules_version=rules.get("version"), weak_version=weak.get("version") if label_source == "weak" else None),
                    random_state=RANDOM_STATE, disclaimer=DEMO_DISCLAIMER)
    manifest["best_learned"] = best  # kept even when it does not beat the baseline: it is the only "other eye" on unflagged tx
    d = Path(out) / version; d.mkdir(parents=True, exist_ok=True)
    manifest["model_versions"] = {name: f"{version}__{name}" for name in fitted}
    manifest["plugs"] = {name: type(m).__module__ for name, m in fitted.items()}
    for name, m in fitted.items(): save_model(m, d / f"{name}.pkl")
    (d / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)); (Path(out) / "LATEST").write_text(version)
    register_versions(con, manifest, d)
    if not quiet:
        cols = ["p_at_100", "p_at_500", "pr_auc", "p_at_100_flagged", "overlap_at_100", "learned_nothing"]
        print(f"label_source={label_source} · train {meta['train']['n']:,} (pos {meta['train']['n_pos']:,}) {meta['train']['from']}~{meta['train']['to']} · test {meta['test']['n']:,} (pos {meta['test']['n_pos']:,}) {meta['test']['from']}~{meta['test']['to']}")
        print(pd.DataFrame(results).T[cols].to_string())
        print(f"chosen: {chosen}  (beats_baseline={beats}, best_learned={best}) → {d}")
    return manifest

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label-source", required=True, choices=["weak", "reviews", "import"]); ap.add_argument("--reviewers", default=None)
    ap.add_argument("--split-date", default="2025-03-01"); ap.add_argument("--k", default="100,500"); ap.add_argument("--out", default="models"); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if a.label_source == "reviews" and not a.reviewers: ap.error("--reviewers is required with --label-source reviews")
    con = C.connect()
    train(con, a.label_source, [r.strip() for r in a.reviewers.split(",")] if a.reviewers else None, a.split_date, tuple(int(k) for k in a.k.split(",")), a.out, a.quiet)
    con.close()
