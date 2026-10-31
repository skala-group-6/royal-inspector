select tx_id, json_object('total', total, 'mcc', mcc_name, 'memo', memo, 'attendees_in_memo', try_cast(regexp_extract(coalesce(memo,''), '(\d+)\s*명', 1) as int)) evidence, [] related
from tx_active where mcc_name in ('일반음식점','기타음식점') and total >= {min_amount}
  and (try_cast(regexp_extract(coalesce(memo,''), '(\d+)\s*명', 1) as int) <= {max_attendees} or memo like '%동료%')
