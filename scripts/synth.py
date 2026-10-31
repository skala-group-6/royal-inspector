"""Step 2: inject 22 disciplinary cases as synthetic users/transactions into data/warehouse.duckdb.
Idempotent: removes previous synthetic rows first. Seeded. Real rows are never modified."""
import random, datetime as dt, re
from pathlib import Path
import pandas as pd, numpy as np, duckdb

DB = "data/warehouse.duckdb"; SEED = 20251031
rng = random.Random(SEED)
con = duckdb.connect(DB)
D0, D1 = dt.date(2025, 2, 3), dt.date(2025, 3, 27)
HOLIDAYS = {dt.date(2025, 3, 1), dt.date(2025, 3, 3)}
WD = ["월", "화", "수", "목", "금", "토", "일"]

# ---------- schema prep ----------
for t, cols in {"transactions": ["is_synthetic BOOLEAN DEFAULT FALSE", "case_id INTEGER"],
                "employees": ["is_synthetic BOOLEAN DEFAULT FALSE"], "access_logs": ["is_synthetic BOOLEAN DEFAULT FALSE"]}.items():
    existing = {r[0] for r in con.execute(f"describe {t}").fetchall()}
    for c in cols:
        if c.split()[0] not in existing: con.execute(f"ALTER TABLE {t} ADD COLUMN {c}").fetchall()
con.execute("UPDATE transactions SET is_synthetic=FALSE WHERE is_synthetic IS NULL").fetchall()
con.execute("UPDATE employees SET is_synthetic=FALSE WHERE is_synthetic IS NULL").fetchall()
con.execute("UPDATE access_logs SET is_synthetic=FALSE WHERE is_synthetic IS NULL").fetchall()
for t in ("transactions", "employees", "access_logs"): con.execute(f"DELETE FROM {t} WHERE is_synthetic").fetchall()
con.execute("DROP TABLE IF EXISTS ground_truth").fetchall()
con.execute("CREATE OR REPLACE VIEW tx_active AS SELECT * FROM transactions WHERE exclude_reason IS NULL").fetchall()

# ---------- materials from real data ----------
real = con.execute("select * from transactions where not is_synthetic and exclude_reason is null").df()
TX_COLS = [r[0] for r in con.execute("describe transactions").fetchall()]
pool = real.dropna(subset=["merchant", "merchant_addr", "mcc_name"])[["merchant", "merchant_addr", "mcc_code", "mcc_name"]].drop_duplicates()
def merchants(mcc_names, pred=None):
    m = pool[pool.mcc_name.isin([mcc_names] if isinstance(mcc_names, str) else mcc_names)]
    if pred is not None: m = m[m.merchant_addr.map(pred)]
    return m
sido = lambda a: str(a).split()[0][:2] if a else None           # '경기', '서울'
sigungu = lambda a: " ".join(str(a).split()[1:3]) if a and len(str(a).split()) >= 3 else None
profiles = real.dropna(subset=["home_addr", "work_site_addr", "main_dept"]).groupby("emp_id").first().reset_index()
templates = {r: real[real["rank"] == r] for r in ["팀원", "팀장"]}
median_rail_home = real[(real.account_policy == "자택방문교통비") & (real.mcc_name == "철도")].total.median()
used_ids = set(con.execute("select emp_id from employees").df().emp_id.dropna().astype(int))
next_id = 880001
def new_id():
    global next_id
    while next_id in used_ids: next_id += 1
    used_ids.add(next_id); next_id += 1; return next_id - 1

# ---------- actors ----------
emps, tx_rows, acc_rows, gt_rows = [], [], [], []
def actor(code, rank="팀원", site="본사", home_sido=None, worksite_sido=None):
    cand = profiles[profiles["rank"] == rank] if (profiles["rank"] == rank).any() else profiles
    if home_sido: cand = cand[cand.home_addr.str.startswith(home_sido)]
    if worksite_sido: cand = cand[cand.work_site_addr.str.startswith(worksite_sido)]
    if site == "본사": cand2 = cand[cand.work_site == "본사"]; cand = cand2 if len(cand2) else cand
    p = cand.iloc[rng.randrange(len(cand))]
    e = dict(emp_id=new_id(), emp_name=f"가상{code}", rank=rank, title=p.title, main_dept=p.main_dept, home_addr=p.home_addr,
             work_site=p.work_site, work_site_addr=p.work_site_addr, n_tx=0, n_home_variants=1, n_site_variants=1, is_synthetic=True, code=code,
             dept=p.dept if "dept" in p else p.main_dept, approver_id=int(p.approver_id) if pd.notna(p.approver_id) else None)
    emps.append(e); return e

def rand_date(weekday_only=True, weekend=False):
    while True:
        d = D0 + dt.timedelta(days=rng.randrange((D1 - D0).days + 1))
        we = d.weekday() >= 5 or d in HOLIDAYS
        if weekend and we: return d
        if not weekend and (not weekday_only or not we): return d
def rand_time(lo="09:00", hi="18:00"):
    h0, m0 = map(int, lo.split(":")); h1, m1 = map(int, hi.split(":"))
    s = rng.randrange(h0 * 60 + m0, h1 * 60 + m1); return f"{s//60:02d}:{s%60:02d}:{rng.randrange(60):02d}"

def tx(a, merchant_row, date, time, total, account, case_id=None, rules=(), approver=None, trip=None, leave=None, attachment=True, memo="", addr_override=None):
    vat = round(total / 11) if total > 0 else 0
    r = {c: None for c in TX_COLS}
    r.update(tx_id=None, sap_doc_no=f"SY{len(tx_rows):09d}", settle_type="법인카드", account_raw=account, account_policy=account, mid_account="A-8",
             dept=a["dept"], emp_id=a["emp_id"], emp_name=a["emp_name"], approver_id=(approver or {}).get("emp_id", a["approver_id"]),
             approver=(approver or {}).get("emp_name"), approval_no=rng.randrange(10**6, 10**8), acquirer_no=None,
             tx_date=date, tx_time=time, created_date=date + dt.timedelta(days=3), approved_date=date + dt.timedelta(days=5),
             merchant=merchant_row["merchant"], merchant_addr=addr_override or merchant_row["merchant_addr"],
             project_no="CC-SYNTH", project_name="(조직)SYNTH", amount=total - vat, vat=vat, total=total, net_total=total, prepaid=0,
             cost_center=a["main_dept"], memo=memo, mcc_code=merchant_row["mcc_code"], mcc_name=merchant_row["mcc_name"],
             has_attachment=attachment, is_mobile=False, rank=a["rank"], title=a["title"], main_dept=a["main_dept"], weekday=WD[date.weekday()],
             is_holiday=date.weekday() >= 5 or date in HOLIDAYS, is_remote=False, is_leave=bool(leave),
             work_start="09:00", work_end="18:00", work_hours=8.0, night_hours=0.0,
             trip_type=trip and trip["type"], trip_start=trip and trip["start"], trip_end=trip and trip["end"],
             leave_type=leave and leave["type"], leave_hours=leave and leave["hours"],
             home_addr=a["home_addr"], work_site=a["work_site"], work_site_addr=a["work_site_addr"],
             tx_ts=dt.datetime.combine(date, dt.time.fromisoformat(time)), time_is_dummy=False, exclude_reason=None,
             is_partial_cancel=False, cancel_of_tx_id=None, is_synthetic=True, case_id=case_id)
    tx_rows.append(r)
    for rule in rules: gt_rows.append(dict(row_idx=len(tx_rows) - 1, case_id=case_id, rule_id=rule, emp_id=a["emp_id"]))
    return r

def normal_tx(a, n=None):
    n = n or rng.randrange(20, 41); t = templates.get(a["rank"], templates["팀원"])
    for _, s in t.sample(n, random_state=rng.randrange(10**6)).iterrows():
        d = rand_date(weekday_only=True)
        tx(a, s, d, s.tx_time if s.tx_time and s.tx_time != "00:00:00" else rand_time(), float(abs(s.total)), s.account_policy or s.account_raw,
           attachment=bool(s.has_attachment), memo=s.memo or "")

def access_day(a, d, t_in="08:50:00", t_out="18:40:00", site="본사"):
    for t, ev, g in ((t_in, "정상입문", f"{site}-1F 고층부 S/G IN 1"), (t_out, "정상출문", f"{site}-1F 고층부 S/G OUT 1")):
        acc_rows.append(dict(access_ts=dt.datetime.combine(d, dt.time.fromisoformat(t)), weekday=["MON", "TUE", "WEN", "THE", "FRI", "SAT", "SUN"][d.weekday()],
                             gate=g, emp_name=a["emp_name"], emp_id=a["emp_id"], dept=a["main_dept"], title=a["title"], event=ev, site=site,
                             direction="in" if ev == "정상입문" else "out", is_synthetic=True))
def routine_access(a):
    d = D0
    while d <= D1:
        if d.weekday() < 5 and d not in HOLIDAYS and rng.random() < 0.85: access_day(a, d)
        d += dt.timedelta(days=1)

def trip(type_, days, start=None):
    s = start or rand_date(); return dict(type=type_, start=s, end=s + dt.timedelta(days=days - 1))
def pick(df): return df.iloc[rng.randrange(len(df))]
def far_from(addr_list):
    sidos = {sido(x) for x in addr_list if x}
    return lambda a: sido(a) not in sidos and sido(a) in {"부산", "대구", "광주", "울산", "강원", "전북", "경남", "경북", "제주", "충북", "전남"}
def near(addr):  # merchant in same sigungu as given address
    sg = sigungu(addr); return lambda a: sg is not None and sg in str(a)
def home_addr_for(a): return f"{a['home_addr'].strip()} 1층"

# ---------- cases ----------
A = {}
# 1
A[1] = a = actor("S01"); tr = trip("국내출장", 5)
for _ in range(4):
    d = tr["start"] + dt.timedelta(days=rng.randrange(5)); m = pick(merchants("일반음식점"))
    tx(a, {**m, "merchant": "㈜우아한형제들_KCP"}, d, rand_time("19:00", "21:00"), rng.randrange(18000, 42000), "의욕관리비", 1, ["R05_near_home", "R07_outside_trip_area"], trip=tr, addr_override=home_addr_for(a), memo="구성원 식사")
for _ in range(6):
    m = pick(merchants(["슈퍼마켓.마트", "편의점", "일반음식점"]))
    tx(a, m, rand_date(), rand_time("10:00", "15:00"), rng.randrange(8000, 60000), "잡비", 1, ["R05_near_home"], addr_override=home_addr_for(a), memo="다과 구매")
# 2
A[2] = a = actor("S02")
for _ in range(3):
    d = rand_date(); m = pick(merchants("주유소")); t0 = rng.randrange(8 * 60, 17 * 60)
    for k in range(2):
        tx(a, m if k == 0 else pick(merchants("주유소")), d, f"{(t0+40*k)//60:02d}:{(t0+40*k)%60:02d}:00", rng.randrange(60000, 95000), "승용차량비", 2, ["R09_excess_fuel"], memo="주유")
# 3
A[3] = a = actor("S03"); rail = {"merchant": "철도승차권  발매", "merchant_addr": "서울 중구 한강대로 405 (봉래동2가)", "mcc_code": 7011, "mcc_name": "철도"}
for _ in range(2): tx(a, rail, rand_date(weekend=True), rand_time("07:00", "10:00"), rng.randrange(45000, 120000), "국내출장비", 3, ["R01_holiday_use"], memo="출장 교통")
# 4
A[4] = a = actor("S04"); tr = trip("국내출장", 20, dt.date(2025, 3, 3))
tx(a, rail, tr["end"] - dt.timedelta(days=8), "18:20:00", 53500, "국내출장비", 4, ["R15_trip_period_mismatch"], trip=tr, memo="복귀")
# 5
A[5] = a = actor("S05"); L = actor("S05L", "팀장")
for _ in range(2):
    m = pick(merchants("일반주점")); tx(a, m, rand_date(), rand_time("21:00", "23:00"), rng.randrange(300000, 450000), "의욕관리비", 5, ["R08_banned_mcc", "R18_approver_conflict"], approver=L, addr_override=home_addr_for(L), memo="팀원 회식")
# 6
A[6] = a = actor("S06")
for kw in ["충전케이블", "탁상용 선풍기", "화장품", "보조배터리", "이어폰"]:
    m = pick(merchants(["인터넷상거래", "오픈마켓"])); tx(a, m, rand_date(), rand_time("21:00", "23:30"), rng.randrange(15000, 90000), "잡비", 6, ["R13_personal_item", "R10_missing_evidence"], attachment=False, memo=f"사무실용 {kw} 구매")
# 8
A[8] = a = actor("S08"); C = actor("S08C"); tr = trip("국내출장", 3)
for _ in range(2):
    d = tr["start"] + dt.timedelta(days=rng.randrange(3)); t0 = rng.randrange(18 * 60 + 30, 20 * 60 + 30)
    tx(a, pick(merchants("일반음식점", near(a["work_site_addr"]))), d, f"{t0//60:02d}:{t0%60:02d}:00", 180000, "의욕관리비", 8, ["R06_same_time_diff_place"], memo=f"{C['emp_name']} 외 2명 석식")
    tx(C, pick(merchants("일반음식점", far_from([a["work_site_addr"]]))), d, f"{(t0+10)//60:02d}:{(t0+10)%60:02d}:00", 24000, "국내출장비", 8, ["R06_same_time_diff_place"], trip=tr, memo="출장 석식")
# 9
A[9] = a = actor("S09"); tr = trip("해외출장", 10)
for k in range(4):
    d = tr["start"] + dt.timedelta(days=rng.randrange(10)); m = pick(merchants("주유소")) if k < 3 else {"merchant": "도로공사자체_하이패스", "merchant_addr": "경기 성남시 분당구 판교로 (삼평동)", "mcc_code": 4784, "mcc_name": "고속도로통행카드"}
    tx(a, m, d, rand_time("10:00", "20:00"), rng.randrange(40000, 90000), "승용차량비", 9, ["R07_outside_trip_area", "R09_excess_fuel"], trip=tr, memo="차량 운행")
# 10
A[10] = a = actor("S10", "팀장")
for amt in (300000, 500000, 300000):
    tx(a, pick(merchants(["일반음식점", "커피전문점"])), rand_date(), rand_time("11:00", "14:00"), amt, "PJT운영비", 10, ["R04_prepayment"], memo="PJT 인력 식대 선결제")
# 11
A[11] = a = actor("S11")
for _ in range(3): tx(a, pick(merchants("인터넷상거래")), rand_date(), rand_time(), rng.randrange(150000, 400000), "사무용품비", 11, ["R10_missing_evidence", "R13_personal_item"], attachment=False, memo="팀 비품 구매")
# 12
A[12] = a = actor("S12"); lv = dict(type="연차휴가", hours=4.0)
for _ in range(2): tx(a, pick(merchants(["일반주점", "일반음식점"], near(a["work_site_addr"]))), rand_date(), rand_time("19:30", "22:00"), rng.randrange(60000, 140000), "의욕관리비", 12, ["R02_leave_use"], leave=lv, memo="팀원 석식")
# 13
A[13] = a = actor("S13")
for _ in range(4): tx(a, pick(merchants(["슈퍼마켓.마트", "백화점", "대형할인점"])), rand_date(), rand_time(), rng.randrange(40000, 200000), "잡비", 13, ["R10_missing_evidence"], attachment=False, memo="행사 물품")
# 14
A[14] = a = actor("S14", site="본사"); B = actor("S14B")
for _ in range(5):
    d = rand_date(); t = rand_time("12:00", "13:30"); h, mi = int(t[:2]), int(t[3:5])
    tx(a, pick(merchants("일반음식점", far_from([a["work_site_addr"], a["home_addr"]]))), d, t, rng.randrange(30000, 80000), "의욕관리비", 14, ["R12_card_lending"], memo="고객 미팅 식사")
    access_day(a, d, t_in=f"{(h*60+mi-60)//60:02d}:{(h*60+mi-60)%60:02d}:00", t_out=f"{min(23,(h*60+mi+120)//60):02d}:{(h*60+mi+120)%60:02d}:00")
# 15
A[15] = a = actor("S15"); tr = trip("해외출장", 30, dt.date(2025, 2, 10))
for _ in range(6):
    d = tr["start"] + dt.timedelta(days=rng.randrange(30)); m = pick(merchants("일반음식점"))
    tx(a, {**m, "merchant": f"{m['merchant'][:6]} USD", "merchant_addr": "미국 캘리포니아 San Jose"}, d, rand_time("11:30", "20:30"), rng.randrange(30000, 90000), "의욕관리비", 15, ["R14_trip_meal_double", "R11_account_mismatch"], trip=tr, memo="현지 식사")
# 17
A[17] = a = actor("S17", "팀장"); m = pick(merchants("일반주점")); d = rand_date()
for k, amt in enumerate((480000, 450000)): tx(a, m, d, f"21:{40+12*k}:00", amt, "접대비", 17, ["R03_split_payment", "R08_banned_mcc"], memo="고객 접대")
# 18
A[18] = a = actor("S18", "팀장"); M = actor("S18M")
for mcc in ("골프장", "일반주점"): tx(M, pick(merchants(mcc)), rand_date(), rand_time("17:00", "22:00"), rng.randrange(250000, 600000), "의욕관리비", 18, ["R08_banned_mcc", "R11_account_mismatch"], approver=a, memo="팀 워크숍")
# 19
A[19] = a = actor("S19", home_sido="서울", worksite_sido="대전") if ((profiles.home_addr.str.startswith("서울")) & (profiles.work_site_addr.str.startswith("대전"))).any() else actor("S19", home_sido="서울")
a["work_site_addr"] = "대전광역시 유성구"; a["work_site"] = "대전"
for city, addr in (("부산", "부산 강서구 대저2동 (부산TG)"), ("울산", "울산 울주군 언양읍 (언양TG)"), ("부산", "부산 기장군 (기장TG)"), ("울산", "울산 북구 (울산TG)")):
    tx(a, {"merchant": f"{city}TG", "merchant_addr": addr, "mcc_code": 4784, "mcc_name": "고속도로통행카드"}, rand_date(weekend=rng.random() < 0.5, weekday_only=False), rand_time("06:00", "22:00"), rng.randrange(9000, 25000), "자택방문교통비", 19, ["R17_route_mismatch"], memo="자택 방문 톨비")
# 20
A[20] = a = actor("S20", home_sido="서울"); a["work_site_addr"] = "대전광역시 유성구"; a["work_site"] = "대전"
for _ in range(4): tx(a, rail, rand_date(weekday_only=False), rand_time("17:00", "20:00"), int(round(median_rail_home * 2.2 / 100) * 100), "자택방문교통비", 20, ["R16_amount_outlier"], memo="서울-대전 왕복")
# 21
A[21] = a = actor("S21")
for _ in range(2): tx(a, pick(merchants("일반음식점", near(a["work_site_addr"]))), rand_date(), rand_time("18:30", "21:00"), 480000, "의욕관리비", 21, ["R21_kickback_candidate"], memo="동료 2명과 만찬")
# 22
A[22] = a = actor("S22"); tr = trip("국내출장", 25, dt.date(2025, 2, 17)); far = merchants("일반음식점", far_from([a["home_addr"], a["work_site_addr"]]))
for _ in range(8): tx(a, pick(far), tr["start"] + dt.timedelta(days=rng.randrange(25)), rand_time("11:30", "20:00"), rng.randrange(45000, 70000), "국내출장비", 22, ["R16_amount_outlier", "R14_trip_meal_double"], trip=tr, memo="출장 식대(실비)")

# ---------- normal background + routine access for every synthetic user ----------
for e in emps: normal_tx(e); routine_access(e)

# ---------- write ----------
base = con.execute("select coalesce(max(tx_id),0) from transactions").fetchall()[0][0]
txdf = pd.DataFrame(tx_rows)[TX_COLS]; txdf["tx_id"] = np.arange(base + 1, base + 1 + len(txdf))
gt = pd.DataFrame(gt_rows); gt["tx_id"] = gt.row_idx.map(lambda i: int(txdf.tx_id.iloc[i])); gt = gt.drop(columns="row_idx")
empdf = pd.DataFrame(emps).drop(columns=["code", "dept", "approver_id"]); empdf["n_tx"] = empdf.emp_id.map(txdf.emp_id.value_counts())
accdf = pd.DataFrame(acc_rows)
for name, df in (("transactions", txdf), ("employees", empdf), ("access_logs", accdf)):
    con.register("df", df); con.execute(f"INSERT INTO {name} BY NAME SELECT * FROM df").fetchall(); con.unregister("df")
con.register("gt", gt); con.execute("CREATE TABLE ground_truth AS SELECT tx_id, case_id, rule_id, emp_id FROM gt").fetchall(); con.unregister("gt")
print(f"synthetic users {len(empdf)} | tx {len(txdf)} (violations {gt.tx_id.nunique()}, normal {len(txdf)-gt.tx_id.nunique()}) | access {len(accdf)} | ground_truth rows {len(gt)}")
print(con.execute("select case_id, count(distinct tx_id) tx, string_agg(distinct rule_id, ',') rules from ground_truth group by 1 order by 1").df().to_string(index=False))
con.close()
