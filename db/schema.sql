-- royal-inspector · PostgreSQL 17 schema (single store, tenant-first)
-- Source of truth for the data model. Diagram: db/schema.dbml (generated) → dbdiagram.io. Notes: docs/ERD.md.
-- Kinds: [cfg] tenant/config (declared by people) · [src] source (external, immutable) · [der] derived (rebuilt by code,
-- versioned by run) · [rec] record (made by people, append-only).
-- Conventions: tenant_id first everywhere and in every PK/FK · timestamptz (session timezone Asia/Seoul) · KRW numeric ·
-- tx_id = content hash bigint (strings over JSON) · jsonb only for per-rule/per-model shapes.
-- Tenant scoping: db/conn.py sets `ri.tenant_id` per connection; the views below filter on it so unqualified reads cannot leak.
-- Pack SQL functions (sido_of, sigungu_of …) live in packs/<pack>/rules/functions.sql and are applied by scripts/bootstrap_db.py.

begin;

create schema if not exists ri;
set search_path to ri, public;

create or replace function tenant() returns int language sql stable as
  $$ select coalesce(nullif(current_setting('ri.tenant_id', true), '')::int, 1) $$;

-- ---------------------------------------------------------------- [cfg] tenant & configuration
create table tenants (
  tenant_id     int generated always as identity primary key,
  name          text not null unique,
  created_at    timestamptz not null default now()
);
comment on table tenants is '[cfg] 회사(테넌트). 모든 표의 뿌리.';

create table reviewers (
  tenant_id        int  not null references tenants,
  reviewer_id      int  generated always as identity,
  name             text not null,
  role             text not null default 'reviewer' check (role in ('reviewer','admin','dev')),
  counts_as_label  boolean not null default true,     -- dev/test accounts: false → never used as training labels
  created_at       timestamptz not null default now(),
  primary key (tenant_id, reviewer_id),
  unique (tenant_id, name)
);
comment on column reviewers.counts_as_label is '학습 라벨로 쓸지. 개발팀 테스트 계정은 false.';

create table data_sources (
  tenant_id       int  not null references tenants,
  source_id       int  generated always as identity,
  kind            text not null check (kind in ('card_tx','hr','access','policy')),
  name            text not null,
  column_mapping  jsonb not null default '{}'::jsonb,  -- source column → contract column (docs/PACK_SPEC.md §3)
  raw_glob        text,
  created_at      timestamptz not null default now(),
  primary key (tenant_id, source_id)
);
comment on table data_sources is '[cfg] 회사별 입력 파일과 열 매핑.';

create table rule_settings (
  tenant_id    int  not null references tenants,
  rule_id      text not null,                          -- matches packs/<pack>/rules/catalog.yaml
  version      int  not null,
  enabled      boolean not null default true,
  params       jsonb not null default '{}'::jsonb,     -- threshold overrides on top of the catalog defaults
  policy_ref   text,
  changed_by   text not null,
  changed_at   timestamptz not null default now(),
  note         text,
  primary key (tenant_id, rule_id, version)
);
comment on table rule_settings is '[cfg] 공통 규칙 카탈로그 위 회사별 덮어쓰기. 변경마다 새 version 행.';

create table account_map (
  tenant_id       int  not null references tenants,
  account_raw     text not null,
  account_policy  text,
  method          text,                                -- auto / manual / no_policy / unmapped
  primary key (tenant_id, account_raw)
);
comment on table account_map is '[cfg] 원장 계정명 → 규정 계정명 매핑 (적재가 생성, 수동 결정 포함).';

-- ---------------------------------------------------------------- [src] source data
create table loads (
  tenant_id    int  not null references tenants,
  load_id      int  generated always as identity,
  source_id    int,
  file_name    text,
  file_hash    text not null,
  n_rows       int,
  status       text not null default 'done' check (status in ('running','done','failed')),
  loaded_at    timestamptz not null default now(),
  primary key (tenant_id, load_id),
  foreign key (tenant_id, source_id) references data_sources (tenant_id, source_id)
);

-- Every column the loader produces is a real column: rules and features read them by name (HR snapshot at transaction time).
create table transactions (
  tenant_id          int    not null references tenants,
  tx_id              bigint not null,                  -- deterministic content hash (scripts/keys.py)
  load_id            int,
  sap_doc_no         text,
  settle_type        text,
  account_raw        text,
  account_policy     text,
  mid_account        text,
  dept               text,
  emp_id             int,
  emp_name           text,
  reviewer           text,
  approver           text,
  approver_id        int,
  approval_no        bigint,
  acquirer_no        text,
  tx_date            date   not null,                  -- set by the loader in the tenant's local time
  tx_time            text,                             -- 'HH:MM:SS' or null (rules compare as text)
  tx_ts              timestamptz not null,
  time_is_dummy      boolean not null default false,
  created_date       date,
  approved_date      date,
  merchant           text,
  merchant_addr      text,
  project_no         text,
  project_name       text,
  amount             numeric(14,2),
  vat                numeric(14,2),
  total              numeric(14,2),
  prepaid            numeric(14,2),
  net_total          numeric(14,2),
  cost_center        text,
  memo               text,
  mcc_code           int,
  mcc_name           text,
  has_attachment     boolean,
  is_mobile          boolean,
  rank               text,
  title              text,
  main_dept          text,
  weekday            text,
  is_holiday         boolean,
  is_remote          boolean,
  is_leave           boolean,
  work_start         text,
  work_end           text,
  work_hours         numeric(6,2),
  night_start        text,
  night_end          text,
  night_hours        numeric(6,2),
  trip_type          text,
  trip_start         date,
  trip_end           date,
  leave_type         text,
  leave_hours        numeric(6,2),
  home_addr          text,
  approver_addr      text,
  work_site          text,
  work_site_addr     text,
  exclude_reason     text,                             -- null = active
  is_partial_cancel  boolean not null default false,
  cancel_of_tx_id    bigint,
  is_synthetic       boolean not null default false,
  case_id            int,
  primary key (tenant_id, tx_id),
  foreign key (tenant_id, load_id) references loads (tenant_id, load_id)
);
create index on transactions (tenant_id, emp_id, tx_ts);
create index on transactions (tenant_id, tx_date);
create index on transactions (tenant_id, account_policy, mcc_name, tx_ts);
comment on table transactions is '[src] 표준 거래. tx_id는 내용 해시.';

create table employees (
  tenant_id         int  not null references tenants,
  emp_id            int  not null,
  emp_name          text,
  rank              text,
  title             text,
  main_dept         text,
  home_addr         text,
  work_site         text,
  work_site_addr    text,
  n_tx              int,
  n_home_variants   int,
  n_site_variants   int,
  is_synthetic      boolean not null default false,
  primary key (tenant_id, emp_id)
);

create table access_logs (
  tenant_id    int    not null references tenants,
  access_id    bigint generated always as identity,
  access_ts    timestamptz not null,
  weekday      text,
  gate         text,
  emp_name     text,
  emp_id       int,
  dept         text,
  title        text,
  event        text,
  site         text,
  direction    text,
  is_synthetic boolean not null default false,
  primary key (tenant_id, access_id)
);
create index on access_logs (tenant_id, emp_id, access_ts);

create table policy_accounts (
  tenant_id          int  not null references tenants,
  account            text not null,
  description        text,
  dos                text,
  donts              text,
  required_evidence  text,
  primary key (tenant_id, account)
);

create table geocode (
  tenant_id    int  not null references tenants,
  addr         text not null,
  lat          double precision,
  lon          double precision,
  geocoded_at  timestamptz,
  primary key (tenant_id, addr)
);
comment on table geocode is '[src] 주소 → 좌표 캐시 (API 비용 때문에 보존).';

create table ground_truth (
  tenant_id  int    not null references tenants,
  tx_id      bigint not null,
  case_id    int    not null,
  rule_id    text   not null,
  emp_id     int,
  primary key (tenant_id, tx_id, rule_id),
  foreign key (tenant_id, tx_id) references transactions (tenant_id, tx_id)
);
comment on table ground_truth is '[der] 합성 사례의 정답 (scripts/synth.py). 규칙 재현율 게이트의 분모.';

-- ---------------------------------------------------------------- [der] derived (rebuilt by code, versioned by run)
create table rule_runs (
  tenant_id         int  not null references tenants,
  run_id            int  generated always as identity,
  catalog_version   int  not null,
  settings_version  int,
  ran_at            timestamptz not null default now(),
  n_flags           int,
  primary key (tenant_id, run_id)
);

create table flags (
  tenant_id        int    not null references tenants,
  run_id           int    not null,
  tx_id            bigint not null,
  rule_id          text   not null,
  severity         text   not null check (severity in ('violation','advisory')),
  evidence         jsonb  not null,
  related_tx_ids   bigint[] not null default '{}',
  rule_version     int    not null,
  primary key (tenant_id, run_id, tx_id, rule_id),
  foreign key (tenant_id, run_id) references rule_runs (tenant_id, run_id),
  foreign key (tenant_id, tx_id)  references transactions (tenant_id, tx_id)
);
create index on flags (tenant_id, tx_id);
create index on flags (tenant_id, run_id, rule_id);
comment on table flags is '[der] 규칙 적중. 실행(run_id)마다 쌓임. 읽기는 current_flags 뷰(최신 run).';

-- tx_features (wide, pack-defined columns) is created by features/executor.py: DROP IF EXISTS + CREATE TABLE AS,
-- always with tenant_id, tx_id, features_version first. Not declared here on purpose.

create table labels (
  tenant_id        int    not null references tenants,
  tx_id            bigint not null,
  label_source     text   not null check (label_source in ('weak','reviews','import')),
  source_version   text   not null,
  prob             double precision not null check (prob between 0 and 1),
  n_votes          int    not null default 0,
  clusters_hit     text[] not null default '{}',
  created_at       timestamptz not null default now(),
  primary key (tenant_id, tx_id, label_source, source_version),
  foreign key (tenant_id, tx_id) references transactions (tenant_id, tx_id)
);

create table model_versions (
  tenant_id       int  not null references tenants,
  model_version   text not null,                       -- e.g. v20261105-1200_weak__xgb
  model_id        text not null,                       -- entry id (packs/<pack>/models.yaml later; today the plug name)
  plug            text not null,                       -- python path, e.g. models.xgb
  params          jsonb not null default '{}'::jsonb,
  label_source    text not null,
  label_version   text,
  split_date      date,
  trained_at      timestamptz not null default now(),
  metrics         jsonb not null default '{}'::jsonb,  -- p_at_100, pr_auc, overlap_at_100 … (the exam)
  status          text not null default 'ok' check (status in ('ok','failed','skipped')),
  error           text,
  artifact_path   text,
  artifact_hash   text,
  primary key (tenant_id, model_version)
);
comment on table model_versions is '[der] 학습 결과물 한 건 = 한 행. 실패·건너뜀도 기록(실패 격리).';

create table tx_scores (
  tenant_id       int    not null references tenants,
  model_version   text   not null,
  tx_id           bigint not null,
  score           double precision not null,
  rank_pct        double precision,                    -- percentile rank within the scoring run (model-independent meaning)
  top_features    jsonb  not null default '[]'::jsonb, -- [[feature, contribution, human_text], …]
  scored_at       timestamptz not null default now(),
  primary key (tenant_id, model_version, tx_id),
  foreign key (tenant_id, model_version) references model_versions (tenant_id, model_version),
  foreign key (tenant_id, tx_id)         references transactions (tenant_id, tx_id)
);
create index on tx_scores (tenant_id, model_version, score desc);
comment on table tx_scores is '[der] 모델마다 한 행. 옛 버전 점수도 남아 나란히 비교.';

-- ---------------------------------------------------------------- [rec] records (made by people, append-only)
create table queues (
  tenant_id     int  not null references tenants,
  queue_id      text not null,
  period_from   date not null,
  period_to     date not null,
  params        jsonb not null default '{}'::jsonb,   -- p_random, m_model, seed, n_pool_unflagged, rank model_version, pg_version
  built_at      timestamptz not null default now(),
  built_by      text,
  primary key (tenant_id, queue_id)
);

create table queue_items (
  tenant_id        int    not null references tenants,
  queue_id         text   not null,
  tx_id            bigint not null,
  source           text   not null check (source in ('rule','model','random')),
  selection_prob   double precision not null,
  rank_in_source   int,
  model_version    text,
  primary key (tenant_id, queue_id, tx_id),
  foreign key (tenant_id, queue_id) references queues (tenant_id, queue_id),
  foreign key (tenant_id, tx_id)    references transactions (tenant_id, tx_id)
);
create index on queue_items (tenant_id, tx_id);

create table reviews (
  tenant_id       int    not null references tenants,
  review_id       text   not null,
  tx_id           bigint not null,
  rule_id         text,                                -- null = transaction-level verdict on an unflagged (model/random) row
  decision        text   not null check (decision in ('violation','ok','hold')),
  reason_code     text,
  action_code     text,
  memo            text,
  reviewer_id     int    not null,
  created_at      timestamptz not null default now(),
  superseded_by   text,
  primary key (tenant_id, review_id),
  foreign key (tenant_id, tx_id)       references transactions (tenant_id, tx_id),
  foreign key (tenant_id, reviewer_id) references reviewers (tenant_id, reviewer_id)
);
create index on reviews (tenant_id, tx_id) where superseded_by is null;
comment on table reviews is '[rec] 판정. 덮어쓰지 않고 추가. 최신 = superseded_by is null.';

create table model_bindings (
  tenant_id      int  not null references tenants,
  binding_id     int  generated always as identity,
  role           text not null check (role in ('rank','discover')),
  model_version  text not null,
  state          text not null check (state in ('serving','shadow','retired')),
  set_by         text not null,
  set_at         timestamptz not null default now(),
  note           text,
  primary key (tenant_id, binding_id),
  foreign key (tenant_id, model_version) references model_versions (tenant_id, model_version)
);
create index on model_bindings (tenant_id, role, state, set_at desc);
comment on table model_bindings is '[rec] 역할별 배치. 상태 변경은 새 행 → 승격·되돌리기 이력.';

create table rule_candidates (
  tenant_id     int  not null references tenants,
  candidate_id  int  generated always as identity,
  title         text not null,
  sql           text not null,
  origin        text,
  backtest      jsonb,
  status        text not null default 'draft' check (status in ('draft','approved','rejected')),
  proposed_by   text,
  decided_by    text,
  decided_at    timestamptz,
  created_at    timestamptz not null default now(),
  primary key (tenant_id, candidate_id)
);

create table precedents (
  tenant_id      int,                                  -- null = shared library (disciplinary cases from the pack)
  precedent_id   text not null,
  kind           text not null check (kind in ('case','review')),
  title          text not null,
  summary        text,
  cues           text[] not null default '{}',
  rule_ids       text[] not null default '{}',
  account        text,
  mcc_group      text,
  amount_band    text,
  outcome        text,
  source         text,
  primary key (precedent_id)
);

create table audit_events (
  tenant_id   int    not null references tenants,
  event_id    bigint generated always as identity,
  actor       text,
  event       text   not null,
  payload     jsonb,
  ts          timestamptz not null default now(),
  primary key (tenant_id, event_id)
);
create index on audit_events (tenant_id, ts desc);

-- ---------------------------------------------------------------- views (tenant-scoped)
create view tx_active as
  select * from transactions where tenant_id = tenant() and exclude_reason is null;

create view current_flags as
  select f.* from flags f
  where f.tenant_id = tenant()
    and f.run_id = (select max(run_id) from rule_runs r where r.tenant_id = tenant());

create view latest_reviews as
  select * from reviews where tenant_id = tenant() and superseded_by is null;

create view current_bindings as
  select distinct on (tenant_id, role) tenant_id, role, model_version, state, set_at
  from model_bindings where state = 'serving' order by tenant_id, role, set_at desc;

commit;
