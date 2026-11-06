select tx_id, jsonb_build_object('leave_type', leave_type, 'leave_hours', leave_hours, 'time', tx_time, 'mcc', mcc_name, 'total', total) evidence, '{}'::bigint[] related
from tx_active where is_leave and trip_type is null
