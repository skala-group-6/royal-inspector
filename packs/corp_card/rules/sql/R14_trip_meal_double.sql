select tx_id, json_object('trip_type', trip_type, 'trip', trip_start || '~' || trip_end, 'mcc', mcc_name, 'account', account_policy, 'total', total) evidence, [] related
from tx_active where trip_type is not null and tx_date between trip_start and trip_end and mcc_name in ('일반음식점','기타음식점','커피전문점') and total>0
