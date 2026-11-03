-- return ticket bought >= {min_days_early} days before trip end, and no later trip-tagged spend away from home/work region
select t.tx_id, json_object('trip', trip_start || '~' || trip_end, 'return_ticket_date', tx_date, 'days_before_end', trip_end - tx_date, 'memo', memo) evidence, [] related
from tx_active t where trip_type='국내출장' and mcc_name in ('철도','항공') and tx_date between trip_start and trip_end and trip_end - tx_date >= {min_days_early}
  and not exists (select 1 from tx_active u where u.emp_id=t.emp_id and u.trip_start=t.trip_start and u.tx_date > t.tx_date and u.tx_date <= t.trip_end
                  and u.mcc_name not in ('철도','항공') and sido_of(u.merchant_addr) is not null
                  and sido_of(u.merchant_addr) not in (coalesce(sido_of(u.home_addr),''), coalesce(sido_of(u.work_site_addr),'')))
