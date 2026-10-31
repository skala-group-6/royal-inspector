with f as (select * from tx_active where mcc_name in ('주유소','무인주유소','주유소(LPG)') and total>0),
d as (select a.tx_id, list(b.tx_id) related, count(*)+1 n from f a join f b on a.emp_id=b.emp_id and a.tx_date=b.tx_date and a.tx_id<>b.tx_id group by a.tx_id),
w as (select a.tx_id, list(b.tx_id) related, count(*)+1 n from f a join f b on a.emp_id=b.emp_id and a.tx_id<>b.tx_id and abs(b.tx_date - a.tx_date) <= {window_days} group by a.tx_id)
select coalesce(d.tx_id, w.tx_id) tx_id,
  json_object('same_day_count', d.n, 'count_in_' || {window_days} || 'd', w.n, 'per_day_limit', {per_day}, 'per_window_limit', {per_window}) evidence,
  list_distinct(coalesce(d.related, []) || coalesce(w.related, [])) related
from d full outer join w on d.tx_id=w.tx_id where coalesce(d.n,0) >= {per_day} or coalesce(w.n,0) >= {per_window}
