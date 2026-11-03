-- (a) same person, two places within window; (b) memo names a colleague who was paying elsewhere at the same time
with a as (
  select x.tx_id, list(y.tx_id) related, min(sigungu_of(y.merchant_addr)) other_sigungu
  from tx_active x join tx_active y on x.emp_id=y.emp_id and x.tx_id<>y.tx_id
   and abs(epoch(x.tx_ts)-epoch(y.tx_ts)) <= {window_min}*60 and not x.time_is_dummy and not y.time_is_dummy
   and sigungu_of(x.merchant_addr) is not null and sigungu_of(y.merchant_addr) is not null and sigungu_of(x.merchant_addr) <> sigungu_of(y.merchant_addr)
   and x.mcc_name not similar to '.*(PG|인터넷|오픈마켓|통신판매|택시|철도|항공|고속도로).*' and y.mcc_name not similar to '.*(PG|인터넷|오픈마켓|통신판매|택시|철도|항공|고속도로).*'
  group by x.tx_id),
b as (
  select x.tx_id, list(y.tx_id) related, min(sigungu_of(y.merchant_addr)) other_sigungu
  from tx_active x join employees e on e.emp_id<>x.emp_id and length(e.emp_name)>=3 and x.memo like '%' || e.emp_name || '%'
  join tx_active y on y.emp_id=e.emp_id and abs(epoch(x.tx_ts)-epoch(y.tx_ts)) <= {window_min}*60 and not y.time_is_dummy and not x.time_is_dummy
   and sigungu_of(x.merchant_addr) is not null and sigungu_of(y.merchant_addr) is not null and sigungu_of(x.merchant_addr) <> sigungu_of(y.merchant_addr)
  group by x.tx_id),
u as (select tx_id, related, other_sigungu, 'same_person' kind from a union all select tx_id, related, other_sigungu, 'named_attendee_elsewhere' from b
      union all select unnest(related), [tx_id], null, 'counterpart' from b)
select u.tx_id, json_object('kind', min(kind), 'this_sigungu', min(sigungu_of(t.merchant_addr)), 'other_sigungu', min(other_sigungu), 'window_min', {window_min}) evidence, list_distinct(flatten(list(related))) related
from u join tx_active t using(tx_id) group by u.tx_id
