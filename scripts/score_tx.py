"""Step 3.9: score every tx_features row with the trained models (models/LATEST or --version) → tx_scores, one row per model.
Rows: the chosen model (role rank) and the best learned model (role discover; the "other eye" on unflagged tx). rank_pct = percentile of
the score within the run. Also sets the serving model_bindings for both roles to these versions. Uses DATABASE_URL (current tenant)."""
from __future__ import annotations
import os, sys, json, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from db import conn as C
from features.executor import load_catalog
from models.base import load_model

AUX_TEXT = {"n_violation_rules": "걸린 위반등급 규칙 수", "n_rules": "걸린 규칙 수", "total": "금액"}
ROLES = {"rank": "chosen", "discover": "best_learned"}

def ensure_versions(con, manifest, mdir: Path):
    """model_versions rows must exist (FK from tx_scores). train.py writes them; this covers a models dir trained against another database."""
    for name, mv in manifest["model_versions"].items():
        C.execute(con, """insert into model_versions(tenant_id, model_version, model_id, plug, label_source, label_version, split_date, metrics, artifact_path)
                          values (tenant(), %s, %s, %s, %s, %s, %s, %s::jsonb, %s) on conflict do nothing""",
                  [mv, name, manifest["plugs"][name], manifest["label_source"], manifest["label_version"], manifest["split"]["split_date"],
                   json.dumps(manifest["candidates"][name]), str(mdir / f"{name}.pkl")])

def bind(con, role, model_version, set_by="score_tx"):
    cur = C.one(con, "select model_version from current_bindings where tenant_id = tenant() and role = %s", [role])
    if cur != model_version:
        C.execute(con, "insert into model_bindings(tenant_id, role, model_version, state, set_by, note) values (tenant(), %s, %s, 'serving', %s, 'set by scoring run')", [role, model_version, set_by])

def score(con, models_dir="models", version=None, quiet=False) -> int:
    mdir = Path(models_dir); version = version or (mdir / "LATEST").read_text().strip()
    manifest = json.loads((mdir / version / "manifest.json").read_text()); d = mdir / version
    cat = load_catalog(); desc = {n: f.get("describe", n) for n, f in cat["features"].items()}
    df = C.q(con, """select f.*, t.total, coalesce(a.n_rules,0) n_rules, coalesce(a.n_violation_rules,0) n_violation_rules
        from tx_features f join tx_active t on t.tx_id = f.tx_id
        left join (select tx_id, count(distinct rule_id) n_rules, count(distinct case when severity='violation' then rule_id end) n_violation_rules from current_flags group by 1) a on a.tx_id = f.tx_id
        where f.tenant_id = tenant() order by f.tx_id""")
    X = df[manifest["features"]].astype(float); aux = df[["n_rules", "n_violation_rules", "total"]].astype(float)
    def human(name, contrib, i):
        v = aux[name].iloc[i] if name in aux else X[name].iloc[i]
        txt = AUX_TEXT.get(name, desc.get(name, name)); vs = "" if pd.isna(v) else f" {v:,.2f}".rstrip("0").rstrip(".")
        return f"{txt}{vs} ({'↑' if contrib > 0 else '↓'})"
    ensure_versions(con, manifest, d)
    names = sorted({manifest[k] for k in ROLES.values()}); total = 0
    for name in names:
        model = load_model(d / f"{name}.pkl"); mv = manifest["model_versions"][name]
        s = np.clip(np.asarray(model.predict(X, aux), dtype=float), 0, 1); ex = model.explain(X, aux, 3)
        out = pd.DataFrame(dict(model_version=mv, tx_id=df.tx_id, score=np.round(s, 6), rank_pct=np.round(pd.Series(s).rank(method="average", pct=True).to_numpy() * 100, 4),
                                top_features=[json.dumps([[n, round(c, 6), human(n, c, i)] for n, c in ex[i]], ensure_ascii=False) for i in range(len(df))]))
        C.execute(con, "delete from tx_scores where tenant_id = tenant() and model_version = %s", [mv])
        C.write_df(con, "tx_scores", out); total += len(out)
        if not quiet: print(f"tx_scores[{mv}]: {len(out):,} rows · score>0.5: {(out.score>0.5).mean():.1%}")
    for role, key in ROLES.items(): bind(con, role, manifest["model_versions"][manifest[key]])
    if not quiet: print(f"bindings: rank → {manifest['chosen']} · discover → {manifest['best_learned']}")
    return total

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--models-dir", default="models"); ap.add_argument("--version", default=None); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(); con = C.connect(); score(con, a.models_dir, a.version, a.quiet); con.close()
