select tx_id, jsonb_build_object('total', total, 'mcc', mcc_name, 'memo', memo) evidence, '{}'::bigint[] related
from tx_active where mcc_name in ('일반음식점','커피전문점','기타음식점') and total >= {min_amount} and total % {round_to} = 0
