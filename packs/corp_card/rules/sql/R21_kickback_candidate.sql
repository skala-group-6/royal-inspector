select tx_id, jsonb_build_object('total', total, 'mcc', mcc_name, 'memo', memo, 'attendees_in_memo', (regexp_match(coalesce(memo,''), '(\d+)\s*명'))[1]::bigint) evidence, '{}'::bigint[] related
from tx_active where mcc_name in ('일반음식점','기타음식점') and total >= {min_amount}
  and ((regexp_match(coalesce(memo,''), '(\d+)\s*명'))[1]::bigint <= {max_attendees} or memo like '%동료%')
