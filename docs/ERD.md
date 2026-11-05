# ERD — Postgres 단독, 회사(테넌트) 층 포함 (2026-11-05)

시각화: `docs/design/erd.html` (Mermaid). 결정 배경: `docs/STORAGE_ARCHITECTURE.md` §0.

## 0. 설계 원칙 (시니어 관점에서 먼저 정한 것)

| 원칙 | 뜻 | ERD에 어떻게 나타나나 |
|---|---|---|
| **회사가 뿌리** | 모든 행은 어느 회사 것인지 안다 | 모든 표의 첫 열 `tenant_id`. 거래 PK는 `(tenant_id, tx_id)` |
| **네 종류를 섞지 않는다** | 원천 / 파생 / 기록 / 설정 | 색으로 구분. 선은 원천→파생→기록 방향으로만. 기록이 원천을 바꾸는 선 없음 |
| **파생은 버린다** | 원천 + 코드로 다시 만들 수 있는 것은 재생성 | `flags`·`tx_features`·`tx_scores`는 실행 ID(`run_id`·`model_version`)를 달고 쌓이며, 재실행은 새 행 |
| **기록은 안 지운다** | 사람이 만든 것은 덮어쓰지 않음 | `reviews`는 추가만(`superseded_by`), `model_bindings`는 상태 변경을 새 행으로 |
| **버전은 행이다** | "지금 설정이 뭔가"가 아니라 "그때 설정이 뭐였나"에 답함 | `rule_runs.catalog_version`, `model_versions`, `rule_settings.version` |
| **설정은 git, 상태는 DB** | 코드처럼 리뷰할 것은 YAML, 운영 중 바뀌는 것은 표 | 규칙 정의·피처 선언·모델 플러그 목록 = YAML. 회사별 임계치·배치·승인 = 표 |
| **루프가 닫혀야 한다** | 판정 → 라벨 → 학습 → 배치 → 점수 → 큐 → 판정 | 아래 §3 |

## 1. 표 목록 (약 18개)

### 회사·설정 (사람이 선언)
| 표 | 키 | 핵심 열 | 비고 |
|---|---|---|---|
| `tenants` | tenant_id | name, created_at | 회사 1행 |
| `reviewers` | reviewer_id | tenant_id, name, role, **counts_as_label** | 개발팀 테스트 계정은 false → 학습 제외 |
| `data_sources` | source_id | tenant_id, kind(card_tx/hr/access/policy), **column_mapping** jsonb, raw_glob | 회사별 열 매핑. 에이전트 제안 + 사람 확인 |
| `rule_settings` | (tenant_id, rule_id, version) | params jsonb, enabled, policy_ref, changed_by, changed_at | 공통 카탈로그 위 회사별 덮어쓰기. 변경마다 새 버전 |

### 원천 (밖에서 들어옴, 불변)
| 표 | 키 | 핵심 열 |
|---|---|---|
| `loads` | load_id | tenant_id, source_id, file_hash, n_rows, loaded_at, status |
| `transactions` | (tenant_id, tx_id) | load_id, emp_id, tx_ts, total, merchant, mcc_name, account_policy, dept, sap_doc_no, exclude_reason, is_synthetic … |
| `employees` | (tenant_id, emp_id) | name, dept, rank, home_sigungu, work_sigungu |
| `access_logs` | (tenant_id, access_id) | emp_id, access_ts, gate, direction |
| `policy_accounts` | (tenant_id, account) | description, dos, donts, required_evidence |

`tx_id`는 내용 해시(결정적). 재적재해도 같은 거래는 같은 번호 → 판정이 끊기지 않음.

### 파생 (코드가 만듦, 재생성 가능)
| 표 | 키 | 핵심 열 |
|---|---|---|
| `rule_runs` | run_id | tenant_id, catalog_version, settings_version, ran_at, n_flags |
| `flags` | (run_id, tx_id, rule_id) | tenant_id, severity, evidence jsonb, related_tx_ids bigint[], rule_version |
| `tx_features` | (tenant_id, tx_id, features_version) | 피처 열(35개) 또는 jsonb |
| `labels` | (tenant_id, tx_id, label_source, source_version) | prob, created_at |
| `model_versions` | model_version | tenant_id, model_id, plug, params jsonb, label_source, trained_at, metrics jsonb, artifact_path, artifact_hash |
| `tx_scores` | (model_version, tx_id) | tenant_id, score, **rank_pct**, top_features jsonb |

### 기록 (사람이 만듦, 불변)
| 표 | 키 | 핵심 열 |
|---|---|---|
| `queues` | queue_id | tenant_id, period_from, period_to, params jsonb, built_at |
| `queue_items` | (queue_id, tx_id) | source(rule/model/random), selection_prob, rank_in_source, model_version |
| `reviews` | review_id | tenant_id, tx_id, rule_id(null 허용), decision, reason_code, **action_code**, memo, reviewer_id, created_at, superseded_by |
| `model_bindings` | binding_id | tenant_id, **role**(rank/discover), model_version, **state**(serving/shadow/retired), set_by, set_at, note |
| `rule_candidates` | candidate_id | tenant_id, title, sql, backtest jsonb, status(draft/approved/rejected), decided_by, decided_at |
| `precedents` | precedent_id | tenant_id(null=공통 라이브러리), kind, title, cues, rule_ids, outcome |
| `audit_events` | event_id | tenant_id, actor, event, payload jsonb, ts |

## 2. 관계 (요지)
```
tenants ─┬─ reviewers, data_sources, rule_settings
         ├─ loads ─ transactions ─┬─ flags(run) ─ rule_runs
         │                        ├─ tx_features
         │                        ├─ labels
         │                        ├─ tx_scores ─ model_versions ─ model_bindings
         │                        ├─ queue_items ─ queues
         │                        └─ reviews ─ reviewers
         ├─ employees, access_logs, policy_accounts
         ├─ rule_candidates, precedents, audit_events
```

## 3. 루프가 닫히는 선
```
reviews ──(counts_as_label인 reviewer만)──▶ labels(label_source='reviews')
labels ──▶ model_versions(학습) ──▶ model_bindings(shadow → serving)
model_bindings(serving, role=rank/discover) ──▶ tx_scores 중 어떤 행을 읽을지
tx_scores ──▶ queue_items(source=model, rank) ──▶ reviews
flags + reviews ──▶ 규칙별 확정률 ──▶ rule_settings 새 버전(임계치 조정)
queue_items(source=random) + reviews(violation) ──▶ rule_candidates ──▶ 카탈로그 등록
```
끊긴 곳 없음. 사람이 서는 자리는 셋: `reviews`(판정), `model_bindings`(승격), `rule_candidates`(승인).

## 4. 스키마 규약
- 모든 표 첫 열 `tenant_id`, 복합 PK·FK에 포함. 나중에 Row-Level Security를 켜도 쿼리 변경 없음.
- 시각은 `timestamptz`. 금액은 `numeric(14,0)`(원 단위). 거래번호는 `bigint`(내용 해시, JSON에서는 문자열).
- jsonb는 "구조가 규칙마다 다른 것"(evidence, params, metrics)에만. 조회 기준이 되는 열은 꺼내서 일반 열로.
- 인덱스: `transactions(tenant_id, emp_id, tx_ts)`, `flags(tenant_id, tx_id)`, `reviews(tenant_id, tx_id) where superseded_by is null`, `tx_scores(model_version, score desc)`.
- 파생 표는 실행 ID로 쌓고, 오래된 실행은 보존 정책으로 정리(기본 최근 3회).
- 마이그레이션은 Alembic. 스키마 변경은 PR.

## 5. DuckDB에서 옮길 때 바뀌는 것
| 항목 | DuckDB | Postgres |
|---|---|---|
| 엑셀 직접 읽기 | `read_xlsx` | 적재 스크립트가 pandas로 읽어 `COPY` |
| 리스트 집계 | `list(x)` | `array_agg(x)` |
| 시간 윈도 | `RANGE BETWEEN INTERVAL … PRECEDING` | 같은 문법 지원(정렬 열이 timestamp일 때) |
| 분위수 | `quantile_cont` | `percentile_cont(p) WITHIN GROUP` |
| 매크로 | `CREATE MACRO sido_of` | SQL 함수 `CREATE FUNCTION … LANGUAGE sql IMMUTABLE` |
| 해시 | `hash()` | `hashtext()` 또는 `md5()` → 무작위 표본 구성이 바뀜(시드 기록으로 재현) |
| 테스트 | 파일 복사 | Docker Postgres + 템플릿 DB 복제(`CREATE DATABASE … TEMPLATE`) |
검증은 그대로: 합성 사례 재현율 114/114, 피처 검증 7종, 모델 결정성.

## 6. 지금 코드와의 차이 (요약)
| 있음 | 추가 | 바뀜 |
|---|---|---|
| transactions, employees, access_logs, policy_accounts, flags, tx_features, labels, tx_score, queue, reviews, precedents, ui_events | **tenants, reviewers, data_sources, rule_settings, loads, rule_runs, model_versions(파일 manifest → 표), model_bindings, rule_candidates** | 모든 표에 tenant_id · tx_score→tx_scores(모델별 행, rank_pct) · reviews에 action_code·reviewer_id · queue→queues+queue_items · ui_events→audit_events |
