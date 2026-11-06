select tx_id, jsonb_build_object('mcc', mcc_name, 'account', account_policy, 'weekday', weekday, 'time', tx_time, 'total', total) evidence, '{}'::bigint[] related
from tx_active where mcc_name in ('일반주점','주점','유흥주점','단란주점','노래방','골프장','골프연습장','안마')
