with g as (
  select a.tx_id, array_agg(b.tx_id order by b.tx_ts) related, count(*) n, sum(b.total) + a.total grp_total
  from tx_active a join tx_active b on a.emp_id=b.emp_id and a.merchant=b.merchant and a.tx_id<>b.tx_id
   and abs(extract(epoch from b.tx_ts)-extract(epoch from a.tx_ts)) <= {window_min}*60 and not a.time_is_dummy and not b.time_is_dummy and a.total>0 and b.total>0
  group by a.tx_id, a.total)
select g.tx_id, jsonb_build_object('count_in_window', n+1, 'window_min', {window_min}, 'group_total', grp_total, 'merchant', t.merchant, 'near_limit', {near_limit}) evidence, related
from g join tx_active t using(tx_id) where n+1 >= {min_count} and grp_total >= {min_sum}
