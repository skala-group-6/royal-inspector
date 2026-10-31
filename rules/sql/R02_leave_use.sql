select tx_id, json_object('leave_type', leave_type, 'leave_hours', leave_hours, 'time', tx_time, 'mcc', mcc_name, 'total', total) evidence, [] related
from tx_active where is_leave and trip_type is null
