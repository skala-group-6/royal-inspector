-- card owner badged IN at a work site within {lookback_min} min before a purchase in a non-adjacent sido (exits are rarely logged, so no OUT check)
with cand as (
  select t.tx_id, t.emp_id, max(a.access_ts) last_in
  from tx_active t join access_logs a on a.emp_id=t.emp_id and a.direction='in' and a.access_ts between t.tx_ts - interval ({lookback_min}) minute and t.tx_ts
  where not t.time_is_dummy and sido_of(t.merchant_addr) is not null and sido_of(t.work_site_addr) is not null and sido_of(t.merchant_addr) <> sido_of(t.work_site_addr)
    and not (sido_of(t.merchant_addr) || '-' || sido_of(t.work_site_addr)) in ('서울-경기','경기-서울','서울-인천','인천-서울','경기-인천','인천-경기','대전-세종','세종-대전','대전-충남','충남-대전','대구-경북','경북-대구','부산-경남','경남-부산','울산-경남','경남-울산','광주-전남','전남-광주')
    and t.mcc_name not similar to '.*(PG|인터넷|오픈마켓|통신판매|택시|철도|항공|고속도로).*' and t.total > 0
  group by t.tx_id, t.emp_id),
rep as (select emp_id, count(*) n, list(tx_id) ids from cand group by emp_id having count(*) >= {min_repeat})
select c.tx_id, json_object('badged_in_at', c.last_in, 'minutes_before_purchase', round((epoch(t.tx_ts)-epoch(c.last_in))/60), 'merchant_sido', sido_of(t.merchant_addr), 'work_sido', sido_of(t.work_site_addr), 'repeat_count', r.n) evidence, list_filter(r.ids, lambda x: x <> c.tx_id) related
from cand c join rep r using(emp_id) join tx_active t on t.tx_id=c.tx_id
