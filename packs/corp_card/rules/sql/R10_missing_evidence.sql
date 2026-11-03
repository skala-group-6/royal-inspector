select tx_id, json_object('mcc', mcc_name, 'account', account_policy, 'total', total, 'has_attachment', has_attachment) evidence, [] related
from tx_active where not has_attachment and mcc_name in ('슈퍼마켓.마트','슈퍼마켓','대형할인점','백화점','인터넷상거래','오픈마켓','편의점','PG일반(인증)','PG일반(비인증)','통신판매','홈쇼핑')
