with ref as (select account_policy, mcc_name, percentile_cont(0.5) within group (order by total) med, count(*) n from tx_active where total>0 group by 1,2 having count(*) >= {min_group})
select t.tx_id, jsonb_build_object('total', t.total, 'peer_median', r.med, 'ratio', round((t.total/r.med)::numeric,2), 'peer_group', t.account_policy || ' × ' || t.mcc_name, 'peer_n', r.n) evidence, '{}'::bigint[] related
from tx_active t join ref r using(account_policy, mcc_name) where t.total >= r.med * {ratio} and t.total >= {min_amount}
