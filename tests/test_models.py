import sys, pathlib, re, json, importlib.util; ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd, pytest, duckdb
from app import service as s
from features.executor import load_catalog
from models.base import Scorer
from models.baseline import RuleAmountBaseline
from models.logistic import LogisticScorer
from models.xgb import XgbScorer
def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
T, S = _load("train"), _load("score_tx")

@pytest.fixture(scope="module")
def toy():
    rng = np.random.default_rng(0); n = 300
    X = pd.DataFrame(rng.normal(size=(n, 5)), columns=list("abcde")); X.loc[::7, "a"] = np.nan
    aux = pd.DataFrame(dict(n_rules=rng.integers(0, 4, n), n_violation_rules=rng.integers(0, 2, n), total=rng.uniform(1e3, 1e6, n)))
    y = pd.Series(((X.b.fillna(0) + 0.5 * X.c) > 0.3).astype(int)); return X, y, aux

@pytest.mark.parametrize("cls", [RuleAmountBaseline, LogisticScorer, XgbScorer])
def test_socket_conformance(toy, cls):
    X, y, aux = toy; m = cls().fit(X, y, aux); assert isinstance(m, Scorer)
    p = m.predict(X, aux); assert p.shape == (len(X),) and float(p.min()) >= 0 and float(p.max()) <= 1
    e = m.explain(X.iloc[:2], aux.iloc[:2], 3); assert len(e) == 2 and len(e[0]) == 3 and all(isinstance(n, str) and isinstance(c, float) for n, c in e[0])

@pytest.fixture(scope="module")
def con(): c = duckdb.connect(str(s.DB)); yield c; c.close()

def test_feature_matrix_is_clean(con):
    X, y, aux, tr, te, meta = T.load_xy(con, "weak")
    cat = load_catalog(); bad = re.compile(cat["forbidden_name"])
    assert not [c for c in X.columns if bad.search(c)] and not any(cat["features"][c].get("lookahead") for c in X.columns)
    assert "n_rules" not in X.columns and "total" not in X.columns and set(aux.columns) == {"n_rules", "n_violation_rules", "total"}
    assert not (tr & te).any() and (tr | te).all()
    d = pd.to_datetime(con.execute("select tx_date from tx_active where tx_id in (select tx_id from labels where label_source='weak')").df().tx_date)
    assert meta["train"]["to"] < meta["test"]["from"]

def test_train_manifest_and_determinism(con, tmp_path):
    m1 = T.train(con, "weak", out=tmp_path / "a", quiet=True); m2 = T.train(con, "weak", out=tmp_path / "b", quiet=True)
    assert "baseline" in m1["candidates"] and m1["chosen"] in m1["candidates"] and m1["best_learned"] in m1["candidates"] and m1["best_learned"] != "baseline"
    assert m1["candidates"] == m2["candidates"], "same input must give same metrics"
    assert (tmp_path / "a" / m1["version"] / "model_learned.pkl").exists() and m1["disclaimer"]

def test_score_tx_rows(con, tmp_path):
    T.train(con, "weak", out=tmp_path, quiet=True); n = S.score(con, models_dir=str(tmp_path), quiet=True)
    assert n == con.execute("select count(*) from tx_features").fetchall()[0][0]
    r = con.execute("select top_features, top_features_learned from tx_score limit 1").fetchall()[0]
    assert len(json.loads(r[0])) == 3 and len(json.loads(r[1])) == 3
    assert len(s.top_unflagged_by_score(5)) == 5 and s.get_score(11012)["disclaimer"]
    assert "score_learned" in s.list_flags(sort="learned", page_size=5).columns
