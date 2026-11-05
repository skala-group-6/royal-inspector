-- royal-inspector · Postgres schema (single store, tenant-first)
-- Source of truth for the data model. Diagram: paste this file into dbdiagram.io / drawDB, or connect DBeaver after plan 3.
-- Design notes: docs/ERD.md. Kinds: [cfg] tenant/config (declared by people) · [src] source (external, immutable)
-- · [der] derived (rebuilt by code, versioned by run) · [rec] record (made by people, append-only).
-- Conventions: tenant_id is the first column everywhere and part of every PK/FK · timestamptz · amounts numeric(14,0) KRW
-- · tx_id is a content hash (bigint; strings over JSON) · jsonb only for per-rule/per-model shapes.

begin;

create schema if not exists ri;
set search_path to ri, public;

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
  primary key (tenant_id, reviewer_id)
);
comment on column reviewers.counts_as_label is '학습 라벨로 쓸지. 개발팀 테스트 계정은 false.';

create table data_sources (
  tenant_id       int  not null references tenants,
  source_id       int  generated always as identity,
  kind            text not null check (kind in ('card_tx','hr','access','policy')),
  name            text not null,
  column_mapping  jsonb not null default '{}'::jsonb,  -- source column → contract column (docs/PACK_SPEC.md §3); agent proposes, human confirms
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

-- ---------------------------------------------------------------- [src] source data
create table loads (
  tenant_id    int  not null references tenants,
  load_id      int  generated always as identity,
  source_id    int  not null,
  file_name    text,
  file_hash    text not null,
  n_rows       int,
  status       text not null default 'done' check (status in ('running','done','failed')),
  loaded_at    timestamptz not null default now(),
  primary key (tenant_id, load_id),
  foreign key (tenant_id, source_id) references data_sources (tenant_id, source_id)
);

create table transactions (
  tenant_id        int    not null references tenants,
  tx_id            bigint not null,                    -- deterministic content hash (scripts/keys.py); same tx → same id across reloads
  load_id          int    not null,
  emp_id           int,
  tx_ts            timestamptz not null,
  tx_date          date   not null,                      -- set by the loader in the tenant's local time (a timestamptz→date generated column is not immutable in PG)
  total            numeric(14,0),
  net_total        numeric(14,0),
  merchant         text,
  merchant_addr    text,
  mcc_code         int,
  mcc_name         text,
  account_raw      text,
  account_policy   text,
  dept             text,
  rank             text,
  approver_id      int,
  sap_doc_no       text,
  approval_no      bigint,
  memo             text,
  has_attachment   boolean,
  is_holiday       boolean,
  is_leave         boolean,
  leave_type       text,
  leave_hours      numeric(5,2),
  trip_type        text,
  trip_start       date,
  trip_end         date,
  time_is_dummy    boolean not null default false,
  exclude_reason   text,                               -- null = active (the old tx_active view)
  cancel_of_tx_id  bigint,
  is_synthetic     boolean not null default false,
  case_id          int,                                -- synthetic ground-truth case
  extra            jsonb,                              -- pack-specific columns not promoted to real columns
  primary key (tenant_id, tx_id),
  foreign key (tenant_id, load_id) references loads (tenant_id, load_id)
);
create index on transactions (tenant_id, emp_id, tx_ts);
create index on transactions (tenant_id, tx_date);
create index on transactions (tenant_id, account_policy, mcc_name);
comment on table transactions is '[src] 표준 거래. tx_id는 내용 해시.';
create view tx_active as select * from transactions where exclude_reason is null;

create table employees (
  tenant_id       int  not null references tenants,
  emp_id          int  not null,
  name            text,
  dept            text,
  rank            text,
  title           text,
  home_sigungu    text,
  work_site       text,
  work_sigungu    text,
  is_synthetic    boolean not null default false,
  primary key (tenant_id, emp_id)
);

create table access_logs (
  tenant_id    int    not null references tenants,
  access_id    bigint generated always as identity,
  emp_id       int    not null,
  access_ts    timestamptz not null,
  gate         text,
  site         text,
  event        text,
  direction    text check (direction in ('in','out')),
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

-- ---------------------------------------------------------------- [der] derived (rebuilt by code, versioned by run)
create table rule_runs (
  tenant_id         int  not null references tenants,
  run_id            int  generated always as identity,
  catalog_version   int  not null,
  settings_version  int,                               -- max rule_settings.version applied
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
comment on table flags is '[der] 규칙 적중. 실행(run_id)마다 쌓임. 화면은 최신 run만 읽음.';

create table tx_features (
  tenant_id         int    not null references tenants,
  tx_id             bigint not null,
  features_version  int    not null,                   -- packs/<pack>/features.yaml version
  features          jsonb  not null,                   -- {feature_name: value}; wide table is an optimisation for later
  computed_at       timestamptz not null default now(),
  primary key (tenant_id, tx_id, features_version),
  foreign key (tenant_id, tx_id) references transactions (tenant_id, tx_id)
);

create table labels (
  tenant_id        int    not null references tenants,
  tx_id            bigint not null,
  label_source     text   not null check (label_source in ('weak','reviews','import')),
  source_version   text   not null,
  prob             numeric(5,4) not null check (prob between 0 and 1),
  created_at       timestamptz not null default now(),
  primary key (tenant_id, tx_id, label_source, source_version),
  foreign key (tenant_id, tx_id) references transactions (tenant_id, tx_id)
);

create table model_versions (
  tenant_id       int  not null references tenants,
  model_version   text not null,                       -- e.g. v20261105-1200_xgb_d3_weak
  model_id        text not null,                       -- entry in packs/<pack>/models.yaml
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
  score           numeric(7,6) not null,
  rank_pct        numeric(5,2),                        -- percentile rank within the scoring run; model-independent meaning for the UI
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
  params        jsonb not null default '{}'::jsonb,   -- p_random, m_model, seed, n_pool_unflagged, rank model_version
  built_at      timestamptz not null default now(),
  built_by      text,
  primary key (tenant_id, queue_id)
);

create table queue_items (
  tenant_id        int    not null references tenants,
  queue_id         text   not null,
  tx_id            bigint not null,
  source           text   not null check (source in ('rule','model','random')),
  selection_prob   numeric(8,6) not null,
  rank_in_source   int,
  model_version    text,                               -- which model produced a 'model' row
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
  action_code     text,                                -- for violations: refund / counsel / retrain / refer / other (backlog D)
  memo            text,
  reviewer_id     int    not null,
  created_at      timestamptz not null default now(),
  superseded_by   text,                                -- append-only: a newer review points back here
  primary key (tenant_id, review_id),
  foreign key (tenant_id, tx_id)       references transactions (tenant_id, tx_id),
  foreign key (tenant_id, reviewer_id) references reviewers (tenant_id, reviewer_id)
);
create index on reviews (tenant_id, tx_id) where superseded_by is null;
comment on table reviews is '[rec] 판정. 덮어쓰지 않고 추가. 최신 = superseded_by is null.';

create table model_bindings (
  tenant_id      int  not null references tenants,
  binding_id     int  generated always as identity,
  role           text not null check (role in ('rank','discover')),   -- 순서 정하기 / 규칙 밖 후보 찾기
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
  origin        text,                                  -- random_sample / model_top / repeated_reason / adversarial
  backtest      jsonb,                                 -- n_hits, precision on reviewed rows, period
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

-- ---------------------------------------------------------------- helpers
-- Current serving model per role (what the queue and the UI read).
create view current_bindings as
  select distinct on (tenant_id, role) tenant_id, role, model_version, state, set_at
  from model_bindings where state = 'serving' order by tenant_id, role, set_at desc;

-- Latest review per (tx, rule).
create view latest_reviews as
  select * from reviews where superseded_by is null;

commit;
