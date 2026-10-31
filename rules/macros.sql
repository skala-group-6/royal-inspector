create or replace macro sido_of(a) as case when a is null or trim(a)='' then null
  when a like '충청북도%' then '충북' when a like '충청남도%' then '충남' when a like '전라북도%' then '전북' when a like '전라남도%' then '전남'
  when a like '경상북도%' then '경북' when a like '경상남도%' then '경남' when a like '미국%' or a like 'USA%' then '해외' else left(trim(a),2) end;
create or replace macro sigungu_of(a) as nullif(array_to_string(list_slice(
  list_filter(list_transform(string_split(regexp_replace(coalesce(a,''), '\s+', ' ', 'g'), ' '),
    lambda x: case when regexp_matches(x, '(특별시|광역시|특별자치시|특별자치도|도)$') then '' else regexp_extract(x, '^([가-힣]+?(?:시|군|구))', 1) end),
  lambda x: x <> ''), 1, 2), ' '), '');
