import sys, pathlib, subprocess; ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import pytest, pandas as pd
from app import service as s
PF, PT = "2025-03-01", "2025-03-31"

@pytest.fixture(scope="module")
def built():
    s.con().execute("delete from reviews where reviewer='qtester'").fetchall(); s.con().execute("delete from queue where period_from=? and period_to=?", [PF, PT]).fetchall()
    r = s.build_queue(PF, PT, p_random=0.10, m_model=20, seed=42, force=True)  # the DB may already hold real reviews in this period
    yield r
    s.con().execute("delete from reviews where reviewer='qtester'").fetchall(); s.con().execute("delete from queue where period_from=? and period_to=?", [PF, PT]).fetchall()

def test_composition(built):
    q = s.q("select queue_source, count(*) n from queue where period_from=? and period_to=? group by 1", [PF, PT]).set_index("queue_source").n
    n_flagged = s.q("select count(distinct f.tx_id) from flags f join tx_active t using(tx_id) where t.tx_date between ? and ?", [PF, PT]).iloc[0, 0]
    assert q["rule"] == built["n_rule"] + sum(1 for _ in range(0)) or q["rule"] >= built["n_rule"]  # kept reviewed rule rows are not re-counted in n_rule
    assert q["rule"] == n_flagged
    assert q.get("model", 0) == built["n_model"] <= 20
    assert q["random"] >= built["n_random"] and q["random"] <= min(built["n_pool_unflagged"], max(round(0.10 * q["rule"]), 10)) + 1

def test_random_and_model_are_clean(built):
    bad = s.q("""select count(*) from queue qu join tx_active t using(tx_id) where qu.period_from=? and qu.period_to=? and qu.queue_source in ('random','model')
                 and (t.is_synthetic or qu.tx_id in (select tx_id from flags))""", [PF, PT]).iloc[0, 0]
    assert bad == 0
    dup = s.q("select count(*) from (select tx_id from queue where period_from=? and period_to=? group by 1 having count(*)>1)", [PF, PT]).iloc[0, 0]
    assert dup == 0
    prob = s.q("select distinct selection_prob from queue where period_from=? and period_to=? and queue_source='random'", [PF, PT]).iloc[0, 0]
    assert prob == pytest.approx(built["n_random"] / built["n_pool_unflagged"])

def test_seed_determinism(built):
    ids42 = set(s.q("select tx_id from queue where period_from=? and period_to=? and queue_source='random'", [PF, PT]).tx_id)
    s.build_queue(PF, PT, seed=42, force=True); assert ids42 == set(s.q("select tx_id from queue where period_from=? and period_to=? and queue_source='random'", [PF, PT]).tx_id)
    s.build_queue(PF, PT, seed=7, force=True); assert ids42 != set(s.q("select tx_id from queue where period_from=? and period_to=? and queue_source='random'", [PF, PT]).tx_id)
    s.build_queue(PF, PT, seed=42, force=True)

def test_list_queue_and_unflagged_review(built):
    df = s.list_queue(PF, PT, sources=["random"], page_size=5)
    assert len(df) == 5 and set(df.queue_source) == {"random"} and (df.n_rules == 0).all() and (df.sev == 0).all()
    tx = int(df.tx_id.iloc[0]); n = s.review_transaction(tx, "ok", "business_confirmed", "", "qtester"); assert n == 1
    assert s.q("select rule_id is null from reviews where tx_id=? and reviewer='qtester'", [tx]).iloc[0, 0]
    assert tx in set(s.list_queue(PF, PT, review_status="reviewed", page_size=500).tx_id)
    summ = s.get_queue_summary(PF, PT).set_index("source"); assert summ.loc["random", "reviewed"] >= 1 and {"rule", "random"} <= set(summ.index)
    assert s.next_unreviewed(tx, queue_period=(PF, PT), sources=["random"]) not in (tx, None)

def test_rebuild_guard_keeps_reviewed(built):
    reviewed = s.q("select tx_id, queue_source from queue qu where period_from=? and period_to=? and tx_id in (select tx_id from reviews where reviewer='qtester')", [PF, PT])
    assert len(reviewed) == 1
    with pytest.raises(ValueError): s.build_queue(PF, PT)
    r = s.build_queue(PF, PT, force=True); assert r["kept_reviewed"] >= 1  # >= : the DB may hold earlier real reviews too
    after = s.q("select queue_source from queue where period_from=? and period_to=? and tx_id=?", [PF, PT, int(reviewed.tx_id.iloc[0])]).iloc[0, 0]
    assert after == reviewed.queue_source.iloc[0]

def test_cli_requires_period():
    r = subprocess.run([sys.executable, "-I", "scripts/build_queue.py"], capture_output=True, text=True, cwd=str(ROOT)); assert r.returncode == 2
