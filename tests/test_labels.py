import sys, pathlib, subprocess; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest, yaml, pandas as pd
from db import conn as C
import importlib.util
spec = importlib.util.spec_from_file_location("labels_mod", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "labels.py"); L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)
ROOT = pathlib.Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def con(pgdb):
    c = C.connect(); cfg = L.load_weak_cfg(); df = L.weak_labels(c, cfg); L.write_labels(c, df)
    yield c, cfg; c.close()

def test_requires_label_source():
    r = subprocess.run([sys.executable, "-I", "scripts/labels.py"], capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 2 and "--label-source" in r.stderr
    r = subprocess.run([sys.executable, "-I", "scripts/labels.py", "--label-source", "reviews"], capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 2 and "--reviewers" in r.stderr

def test_config_covers_all_rules(tmp_path):
    cfg = L.load_weak_cfg(); rules = yaml.safe_load(open(L.RULES_CFG))["rules"]
    assert set(cfg["_rule_p"].rule_id) == set(rules)
    base = yaml.safe_load(open(L.WEAK_CFG)); cat = yaml.safe_load(open(L.RULES_CFG))
    bad_cat = dict(cat); bad_cat["rules"] = {k: ({kk: vv for kk, vv in v.items() if kk != "cluster"} if k == "R01_holiday_use" else v) for k, v in cat["rules"].items()}
    pc = tmp_path / "cat.yaml"; pc.write_text(yaml.safe_dump(bad_cat, allow_unicode=True))
    with pytest.raises(ValueError): L.load_weak_cfg(L.WEAK_CFG, pc)                      # a rule without a cluster
    bad3 = dict(base); bad3["p_tier"] = {"violation": 1.0, "advisory": 0.2}
    p = tmp_path / "bad3.yaml"; p.write_text(yaml.safe_dump(bad3, allow_unicode=True))
    with pytest.raises(ValueError): L.load_weak_cfg(p)                                   # probability out of (0,1)

def test_rows_bounds_and_prior(con):
    c, cfg = con
    n_active, n_labels = C.one(c, "select (select count(*) from tx_active), (select count(*) from labels where tenant_id=tenant() and label_source='weak')")
    assert n_active == n_labels
    lo, hi = C.one(c, "select min(prob), max(prob) from labels where tenant_id=tenant() and label_source='weak'")
    assert lo == pytest.approx(cfg["prior"]) and hi < 1
    bad = C.one(c, "select count(*) from labels l where tenant_id=tenant() and label_source='weak' and tx_id not in (select tx_id from current_flags) and (prob <> %s or n_votes <> 0)", [cfg["prior"]])
    assert bad == 0

def test_cluster_counts_once_and_formula(con):
    c, cfg = con; pv, prior = cfg["p_tier"]["violation"], cfg["prior"]
    row = C.q(c, """select l.prob, l.clusters_hit from labels l where l.tenant_id=tenant() and label_source='weak' and tx_id in (
                    select tx_id from current_flags group by tx_id having array_agg(distinct rule_id order by rule_id) = array['R08_banned_mcc','R18_approver_conflict']) order by tx_id limit 1""")
    assert len(row), "need a tx flagged by exactly R08+R18 (same cluster: entertain)"
    prob, clusters = row.prob.iloc[0], row.clusters_hit.iloc[0]; assert list(clusters) == ["entertain"] and prob == pytest.approx(1 - (1 - prior) * (1 - pv), abs=1e-6)
    # generic recomputation for 200 flagged tx
    fl = C.q(c, "select f.tx_id, f.rule_id from current_flags f where f.tx_id in (select tx_id from current_flags order by tx_id limit 200)").merge(cfg["_rule_p"], on="rule_id")
    pc = fl.groupby(["tx_id", "cluster"]).p.max().reset_index(); exp = 1 - (1 - prior) * pc.assign(q=1 - pc.p).groupby("tx_id").q.prod()
    got = C.q(c, "select tx_id, prob from labels where tenant_id=tenant() and label_source='weak'").set_index("tx_id").prob
    assert all(abs(got[t] - v) < 1e-6 for t, v in exp.items())

def test_planted_vs_normal_and_no_dominance(con):
    c, cfg = con; out = L.validate_weak(c, cfg, None)
    assert out["planted_ok"], out
    assert out["loro_ok"], out["loro_top3"]

def test_deterministic(con):
    c, cfg = con; h1 = L.labels_hash(c, "weak"); L.write_labels(c, L.weak_labels(c, cfg)); assert h1 == L.labels_hash(c, "weak")

def test_reviews_and_import(con, tmp_path):
    """Review labels: superseded ignored, hold dropped, untrusted reviewer filtered. Import: explicit tx_id beats key match; same emp/day/amount pairs are ambiguous."""
    c, _ = con
    pair = C.q(c, "select emp_id, tx_date, total from tx_active where total > 0 and not is_synthetic group by 1,2,3 having count(*) = 2 order by 1,2,3 limit 1").iloc[0]
    uniq = C.q(c, "select tx_id, emp_id, tx_date, total from tx_active where total > 0 and not is_synthetic and (emp_id, tx_date, total) in (select emp_id, tx_date, total from tx_active group by 1,2,3 having count(*) = 1) order by tx_id limit 2")
    t1, t4 = int(uniq.tx_id.iloc[0]), int(uniq.tx_id.iloc[1])
    ids = {n: C.one(c, "insert into reviewers(tenant_id, name, role, counts_as_label) values (tenant(), %s, 'dev', false) on conflict (tenant_id, name) do update set role = excluded.role returning reviewer_id", [n]) for n in ("auditor_t", "tester_t")}
    with c.transaction():
        C.execute(c, "insert into reviews(tenant_id, review_id, tx_id, rule_id, decision, reviewer_id, superseded_by) values "
                     "(tenant(), 'tl_a', %s, 'R08', 'ok', %s, 'tl_b'), (tenant(), 'tl_b', %s, 'R08', 'violation', %s, null), "
                     "(tenant(), 'tl_c', %s, 'R01', 'hold', %s, null), (tenant(), 'tl_d', %s, 'R01', 'violation', %s, null)",
                  [t1, ids["auditor_t"], t1, ids["auditor_t"], t4, ids["auditor_t"], t4, ids["tester_t"]])
        rv = L.review_labels(c, ["auditor_t"])
        assert rv.tx_id.tolist() == [t1] and rv.prob.iloc[0] == 1.0
        f = tmp_path / "past.csv"
        pd.DataFrame(dict(tx_id=[str(t1), "", "", ""], emp_id=[None, uniq.emp_id.iloc[1], pair.emp_id, pair.emp_id],
                          tx_date=[None, str(uniq.tx_date.iloc[1]), str(pair.tx_date), str(pair.tx_date)], total=[None, float(uniq.total.iloc[1]), float(pair.total), float(pair.total)],
                          decision=["위반", "적정", "위반", "보류"], decided_at=["2025-04-01"] * 4)).to_csv(f, index=False)
        df, st = L.import_labels(c, str(f))
        assert st["by_tx_id"] == 1 and st["by_key"] == 1 and st["ambiguous"] == 1, st   # unique row matched by key; the duplicate pair is ambiguous; hold dropped
        assert set(df.tx_id) == {t1, t4} and df.set_index("tx_id").prob[t1] == 1.0 and df.set_index("tx_id").prob[t4] == 0.0
        C.execute(c, "delete from reviews where tenant_id = tenant() and review_id like 'tl\\_%%'")
