-- approver lives in the same sigungu as the (evening / holiday) bar or restaurant that a subordinate paid for
select tx_id, json_object('approver_sigungu', sigungu_of(approver_addr), 'merchant_sigungu', sigungu_of(merchant_addr), 'work_sigungu', sigungu_of(work_site_addr), 'mcc', mcc_name, 'time', tx_time, 'total', total) evidence, [] related
from tx_active where sigungu_of(approver_addr) is not null and sigungu_of(approver_addr) = sigungu_of(merchant_addr)
  and mcc_name in ('일반주점','주점','유흥주점','단란주점','노래방','일반음식점','기타음식점') and (tx_time >= '19:00:00' or is_holiday) and total >= {min_amount}
