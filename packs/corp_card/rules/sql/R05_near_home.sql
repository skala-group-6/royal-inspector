select tx_id, json_object('merchant_sigungu', sigungu_of(merchant_addr), 'home_sigungu', sigungu_of(home_addr), 'work_sigungu', sigungu_of(work_site_addr), 'time', tx_time, 'mcc', mcc_name, 'total', total) evidence, [] related
from tx_active where sigungu_of(merchant_addr) is not null and sigungu_of(merchant_addr) = sigungu_of(home_addr)
  and coalesce(sigungu_of(work_site_addr),'') <> sigungu_of(home_addr) and mcc_name not in ('택시','철도','항공','주유소','무인주유소','주유소(LPG)','고속도로통행카드')
