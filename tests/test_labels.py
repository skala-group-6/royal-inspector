import sys, pathlib, subprocess; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest, yaml, duckdb, pandas as pd
from app import service as s
import importlib.util
spec = importlib.util.spec_from_file_location("labels_mod", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "labels.py"); L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)

@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(s.DB)); cfg = L.load_weak_cfg(); df = L.weak_labels(c, cfg); L.write_labels(c, df)
    yield c, cfg; c.close()

def test_requires_label_source():
    r = subprocess.run([sys.executable, "-I", "scripts/labels.py"], capture_output=True, text=True, cwd=str(pathlib.Path(__file__).resolve().parents[1]))
    assert r.returncode == 2 and "--label-source" in r.stderr
    r = subprocess.run([sys.executable, "-I", "scripts/labels.py", "--label-source", "reviews"], capture_output=True, text=True, cwd=str(pathlib.Path(__file__).resolve().parents[1]))
    assert r.returncode == 2 and "--reviewers" in r.stderr

def test_config_covers_all_rules(tmp_path):
    cfg = L.load_weak_cfg(); rules = yaml.safe_load(open(L.RULES_CFG))["rules"]
    assert set(cfg["_rule_p"].rule_id) == set(rules)
    base = yaml.safe_load(open(L.WEAK_CFG))
    bad1 = dict(base); bad1["clusters"] = {**base["clusters"], "dup": ["R01_holiday_use"]}
    bad2 = dict(base); bad2["clusters"] = {k: v for k, v in base["clusters"].items() if k != "time"}
    bad3 = dict(base); bad3["p_tier"] = {"violation": 1.0, "advisory": 0.2}
    for i, b in enumerate((bad1, bad2, bad3)):
        p = tmp_path / f"bad{i}.yaml"; p.write_text(yaml.safe_dump(b, allow_unicode=True))
        with pytest.raises(ValueError): L.load_weak_cfg(p)

def test_rows_bounds_and_prior(con):
    c, cfg = con
    n_active, n_labels = c.execute("select (select count(*) from tx_active), (select count(*) from labels where label_source='weak')").fetchall()[0]
    assert n_active == n_labels
    lo, hi = c.execute("select min(prob), max(prob) from labels where label_source='weak'").fetchall()[0]
    assert lo == pytest.approx(cfg["prior"]) and hi < 1
    bad = c.execute("select count(*) from labels l where label_source='weak' and tx_id not in (select tx_id from flags) and (prob <> ? or n_votes <> 0)", [cfg["prior"]]).fetchall()[0][0]
    assert bad == 0

def test_cluster_counts_once_and_formula(con):
    c, cfg = con; pv, prior = cfg["p_tier"]["violation"], cfg["prior"]
    row = c.execute("""select l.prob, l.clusters_hit from labels l where label_source='weak' and tx_id in (
                        select tx_id from flags group by tx_id having list_sort(list(distinct rule_id)) = ['R08_banned_mcc','R11_account_mismatch'] ) limit 1""").fetchall()
    assert row, "need a tx flagged by exactly R08+R11"
    prob, clusters = row[0]; assert list(clusters) == ["entertain"] and prob == pytest.approx(1 - (1 - prior) * (1 - pv), abs=1e-6)
    # generic recomputation for 200 flagged tx
    fl = c.execute("select f.tx_id, f.rule_id from flags f where f.tx_id in (select tx_id from flags limit 200)").df().merge(cfg["_rule_p"], on="rule_id")
    pc = fl.groupby(["tx_id", "cluster"]).p.max().reset_index(); exp = 1 - (1 - prior) * pc.assign(q=1 - pc.p).groupby("tx_id").q.prod()
    got = c.execute("select tx_id, prob from labels where label_source='weak'").df().set_index("tx_id").prob
    assert all(abs(got[t] - v) < 1e-6 for t, v in exp.items())

def test_planted_vs_normal_and_no_dominance(con):
    c, cfg = con; out = L.validate_weak(c, cfg, None)
    assert out["planted_ok"], out
    assert out["loro_ok"], out["loro_top3"]

def test_deterministic(con):
    c, cfg = con; h1 = L.labels_hash(c, "weak"); L.write_labels(c, L.weak_labels(c, cfg)); assert h1 == L.labels_hash(c, "weak")

def test_reviews_and_import_in_memory(tmp_path):
    m = duckdb.connect(":memory:")
    m.execute("create table tx_active(tx_id bigint, emp_id int, tx_date date, total double)")
    m.execute("insert into tx_active values (1,100,'2025-03-01',10000),(2,100,'2025-03-02',20000),(3,100,'2025-03-02',20000),(4,200,'2025-03-05',5000)")
    m.execute("create table reviews(review_id varchar, tx_id bigint, rule_id varchar, decision varchar, reason_code varchar, memo varchar, reviewer varchar, created_at timestamp, superseded_by varchar)")
    m.execute("""insert into reviews values ('a',1,'R08','ok','',NULL,'auditor',now(),'b'), ('b',1,'R08','violation','',NULL,'auditor',now(),NULL),
                 ('c',2,'R01','hold','',NULL,'auditor',now(),NULL), ('d',4,'R01','violation','',NULL,'tester',now(),NULL)""")
    rv = L.review_labels(m, ["auditor"])
    assert rv.tx_id.tolist() == [1] and rv.prob.iloc[0] == 1.0  # superseded ignored, hold dropped, tester filtered
    f = tmp_path / "past.csv"
    pd.DataFrame(dict(tx_id=[1, None, None, None], emp_id=[None, 100, 100, 200], tx_date=[None, "2025-03-01", "2025-03-02", "2025-03-05"],
                      total=[None, 10000, 20000, 5000], decision=["위반", "적정", "위반", "보류"], decided_at=["2025-04-01"] * 4)).to_csv(f, index=False)
    df, st = L.import_labels(m, str(f))
    assert st["by_tx_id"] == 1 and st["by_key"] == 1 and st["ambiguous"] == 1   # tx 2/3 same emp/day/amount → ambiguous; hold dropped
    assert set(df.tx_id) == {1} and df.prob.iloc[0] == 1.0
