select tx_id, json_object('date', tx_date, 'weekday', weekday, 'account', account_policy, 'mcc', mcc_name, 'total', total) evidence, [] related
from tx_active where is_holiday and trip_type is null and total > 0
