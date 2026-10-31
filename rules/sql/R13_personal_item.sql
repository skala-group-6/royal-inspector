with s as (
  select tx_id, account_policy, mcc_name, memo, has_attachment, tx_time, is_holiday,
    regexp_matches(coalesce(memo,''), '{keywords}') kw,
    mcc_name in ('인터넷상거래','오픈마켓','통신판매','홈쇼핑','슈퍼마켓.마트','슈퍼마켓','대형할인점','백화점','편의점','화장품','일반의류','PG일반(인증)','PG일반(비인증)') shop,
    (tx_time >= '21:00:00' or tx_time < '06:00:00' or is_holiday) offhours
  from tx_active where account_policy in ({accounts}) and total>0)
select tx_id, json_object('account', account_policy, 'mcc', mcc_name, 'memo_keyword', kw, 'shopping_mcc', shop, 'off_hours', offhours, 'has_attachment', has_attachment,
       'score', (kw::int + shop::int + offhours::int + (not has_attachment)::int)) evidence, [] related
from s where kw or (shop and not has_attachment) or (shop and offhours)
