import sys, pathlib, subprocess; ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import pytest, pandas as pd
from app import service as s
pytestmark = pytest.mark.usefixtures("pgdb")
PF, PT = "2025-03-01", "2025-03-31"
QI = "queue_items qi join queues qu on qu.tenant_id = qi.tenant_id and qu.queue_id = qi.queue_id"
PERIOD = "qi.tenant_id = tenant() and qu.period_from = %s and qu.period_to = %s"

def _clear():
    s.execute("delete from reviews where tenant_id = tenant() and reviewer_id = %s", [s.reviewer_id("qtester")])
    s.execute(f"delete from queue_items qi using queues qu where qu.tenant_id = qi.tenant_id and qu.queue_id = qi.queue_id and {PERIOD}", [PF, PT])
    s.execute("delete from queues where tenant_id = tenant() and period_from = %s and period_to = %s", [PF, PT])

@pytest.fixture(scope="module")
def built():
    _clear()
    r = s.build_queue(PF, PT, p_random=0.10, m_model=20, seed=42, force=True)  # the DB may already hold real reviews in this period
    yield r
    _clear()

def _ids(source): return set(s.q(f"select qi.tx_id from {QI} where {PERIOD} and qi.source = %s", [PF, PT, source]).tx_id)

def test_composition(built):
    q = s.q(f"select qi.source, count(*) n from {QI} where {PERIOD} group by 1", [PF, PT]).set_index("source").n
    n_flagged = s.one("select count(distinct f.tx_id) from current_flags f join tx_active t on t.tx_id = f.tx_id where t.tx_date between %s and %s", [PF, PT])
    assert q["rule"] >= built["n_rule"]  # kept reviewed rule rows are not re-counted in n_rule
    assert q["rule"] == n_flagged
    assert q.get("model", 0) == built["n_model"] <= 20
    assert q["random"] >= built["n_random"] and q["random"] <= min(built["n_pool_unflagged"], max(round(0.10 * q["rule"]), 10)) + 1
    params = s.q("select params from queues where tenant_id = tenant() and period_from = %s and period_to = %s order by built_at desc", [PF, PT]).params.iloc[0]
    assert params["pg_version"] and params["n_pool_unflagged"] == built["n_pool_unflagged"]

def test_random_and_model_are_clean(built):
    bad = s.one(f"""select count(*) from {QI} join tx_active t on t.tx_id = qi.tx_id where {PERIOD} and qi.source in ('random','model')
                    and (t.is_synthetic or qi.tx_id in (select tx_id from current_flags))""", [PF, PT])
    assert bad == 0
    dup = s.one(f"select count(*) from (select qi.tx_id from {QI} where {PERIOD} group by 1 having count(*)>1) d", [PF, PT])
    assert dup == 0
    prob = s.q(f"select distinct qi.selection_prob from {QI} where {PERIOD} and qi.source='random'", [PF, PT]).iloc[0, 0]
    assert prob == pytest.approx(built["n_random"] / built["n_pool_unflagged"])

def test_seed_determinism(built):
    ids42 = _ids("random")
    s.build_queue(PF, PT, seed=42, force=True); assert ids42 == _ids("random")
    s.build_queue(PF, PT, seed=7, force=True); assert ids42 != _ids("random")
    s.build_queue(PF, PT, seed=42, force=True)

def test_list_queue_and_unflagged_review(built):
    df = s.list_queue(PF, PT, sources=["random"], page_size=5)
    assert len(df) == 5 and set(df.queue_source) == {"random"} and (df.n_rules == 0).all() and (df.sev == 0).all()
    tx = int(df.tx_id.iloc[0]); n = s.review_transaction(tx, "ok", "business_confirmed", "", "qtester"); assert n == 1
    assert s.one("select rule_id is null from reviews where tenant_id = tenant() and tx_id = %s and reviewer_id = %s", [tx, s.reviewer_id("qtester")])
    assert tx in set(s.list_queue(PF, PT, review_status="reviewed", page_size=500).tx_id)
    summ = s.get_queue_summary(PF, PT).set_index("source"); assert summ.loc["random", "reviewed"] >= 1 and {"rule", "random"} <= set(summ.index)
    assert s.next_unreviewed(tx, queue_period=(PF, PT), sources=["random"]) not in (tx, None)
    assert s.today_count("qtester") >= 1

def test_rebuild_guard_keeps_reviewed(built):
    reviewed = s.q(f"select qi.tx_id, qi.source from {QI} where {PERIOD} and qi.tx_id in (select tx_id from reviews where tenant_id = tenant() and reviewer_id = %s)", [PF, PT, s.reviewer_id("qtester")])
    assert len(reviewed) == 1
    with pytest.raises(ValueError): s.build_queue(PF, PT)
    r = s.build_queue(PF, PT, force=True); assert r["kept_reviewed"] >= 1  # >= : the DB may hold earlier real reviews too
    after = s.q(f"select qi.source from {QI} where {PERIOD} and qi.tx_id = %s", [PF, PT, int(reviewed.tx_id.iloc[0])]).iloc[0, 0]
    assert after == reviewed.source.iloc[0]

def test_cli_requires_period():
    r = subprocess.run([sys.executable, "-I", "scripts/build_queue.py"], capture_output=True, text=True, cwd=str(ROOT)); assert r.returncode == 2
