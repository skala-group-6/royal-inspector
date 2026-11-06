select tx_id, jsonb_build_object('mcc', mcc_name, 'account', account_policy, 'trip_type', trip_type, 'reason', case when mcc_name in ('일반주점','주점','유흥주점','단란주점','노래방','골프장','골프연습장') then 'banned_mcc_not_entertainment_account' else 'overseas_trip_meal_not_trip_account' end, 'total', total) evidence, '{}'::bigint[] related
from tx_active where (mcc_name in ('일반주점','주점','유흥주점','단란주점','노래방','골프장','골프연습장') and account_policy <> '접대비')
   or (trip_type='해외출장' and tx_date between trip_start and trip_end and mcc_name in ('일반음식점','기타음식점','커피전문점') and account_policy not in ('해외출장비'))
