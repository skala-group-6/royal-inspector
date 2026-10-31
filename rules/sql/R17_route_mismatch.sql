select tx_id, json_object('merchant_sido', sido_of(merchant_addr), 'home_sido', sido_of(home_addr), 'work_sido', sido_of(work_site_addr), 'mcc', mcc_name, 'total', total) evidence, [] related
from tx_active where account_policy='자택방문교통비' and mcc_name in ('고속도로통행카드','주유소','무인주유소','주유소(LPG)') and sido_of(merchant_addr) is not null
  and sido_of(merchant_addr) not in (coalesce(sido_of(home_addr),''), coalesce(sido_of(work_site_addr),''))
