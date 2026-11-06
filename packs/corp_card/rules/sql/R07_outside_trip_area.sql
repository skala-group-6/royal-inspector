select tx_id, jsonb_build_object('trip_type', trip_type, 'trip', trip_start || '~' || trip_end, 'merchant_sido', sido_of(merchant_addr), 'home_sido', sido_of(home_addr), 'work_sido', sido_of(work_site_addr), 'mcc', mcc_name, 'total', total) evidence, '{}'::bigint[] related
from tx_active where trip_type is not null and tx_date between trip_start and trip_end and merchant_addr is not null and total > 0
  and mcc_name !~ '(PG|인터넷|오픈마켓|통신판매)'
  and ((trip_type='해외출장' and sido_of(merchant_addr) <> '해외' and mcc_name not in ('철도','항공','택시'))
    or (trip_type='국내출장' and mcc_name not in ('철도','항공','고속도로통행카드','택시') and sido_of(merchant_addr) = sido_of(home_addr) and sigungu_of(merchant_addr) = sigungu_of(home_addr)))
