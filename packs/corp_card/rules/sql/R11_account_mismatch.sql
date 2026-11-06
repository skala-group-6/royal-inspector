-- one fact only: a meal during an overseas trip booked to a non-trip account. (The "banned mcc on a non-entertainment account"
-- branch was removed 2026-11-06: it restated R08's fact — 92% co-fire on real data; the account now appears in R08's evidence.)
select tx_id, jsonb_build_object('mcc', mcc_name, 'account', account_policy, 'trip_type', trip_type, 'reason', 'overseas_trip_meal_not_trip_account', 'total', total) evidence, '{}'::bigint[] related
from tx_active where trip_type='해외출장' and tx_date between trip_start and trip_end and mcc_name in ('일반음식점','기타음식점','커피전문점') and account_policy not in ('해외출장비')
