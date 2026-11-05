-- Pack SQL functions (PostgreSQL). Formerly DuckDB macros (macros.sql). Applied by scripts/bootstrap_db.py after db/schema.sql.
-- sido_of: 시/도 2글자 (충청북도→충북 등), 해외는 '해외'.  sigungu_of: '시 구' 두 토큰 (예: '성남시 분당구').
set search_path to ri, public;

create or replace function sido_of(a text) returns text language sql immutable as $$
  select case when a is null or btrim(a) = '' then null
              when a like '충청북도%' then '충북' when a like '충청남도%' then '충남'
              when a like '전라북도%' then '전북' when a like '전라남도%' then '전남'
              when a like '경상북도%' then '경북' when a like '경상남도%' then '경남'
              when a like '미국%' or a like 'USA%' then '해외'
              else left(btrim(a), 2) end
$$;

create or replace function sigungu_of(a text) returns text language sql immutable as $$
  select nullif(string_agg(tok, ' ' order by ord), '')
  from (
    select ord,
           case when tok ~ '(특별시|광역시|특별자치시|특별자치도|도)$' then ''
                else coalesce((regexp_match(tok, '^([가-힣]+?(?:시|군|구))'))[1], '') end as tok
    from regexp_split_to_table(regexp_replace(coalesce(a, ''), '\s+', ' ', 'g'), ' ') with ordinality as t(tok, ord)
  ) s
  where tok <> ''
    and ord in (select ord from (
          select ord, row_number() over (order by ord) rn
          from (select ord, case when tok ~ '(특별시|광역시|특별자치시|특별자치도|도)$' then '' else coalesce((regexp_match(tok, '^([가-힣]+?(?:시|군|구))'))[1], '') end tok
                from regexp_split_to_table(regexp_replace(coalesce(a, ''), '\s+', ' ', 'g'), ' ') with ordinality as u(tok, ord)) v
          where tok <> '') w where rn <= 2)
$$;
