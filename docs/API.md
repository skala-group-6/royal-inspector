# 백엔드 / API 설계 (초안, 2026-10-31)

원칙
1. 화면이 바뀌어도 남는 것만 백엔드에 둔다. 지금은 파이썬 함수(`app/service.py`)로 만들고 Streamlit이 직접 호출, 나중에 같은 함수를 FastAPI로 노출한다.
2. 모든 응답은 규칙 엔진의 출력 계약(rule_id, evidence, related_tx_ids, severity, rule_version)을 그대로 전달한다. 화면에서 재가공하지 않는다.
3. 요청·응답 스키마는 Pydantic으로 고정한다. 아래 필드명이 그 스키마의 초안이다.
4. (2026-11-03) FastAPI 서버 프로세스 1개가 `warehouse.duckdb` 쓰기를 독점한다. Streamlit·배치 스크립트는 복사본(`ROYAL_DB`)을 쓰거나 서버 중지 후 실행. API는 팩이 바뀌어도 동일하다(엔진 테이블 flags/queue/reviews/tx_score만 노출).

공통 객체
- `FlagSummary`: tx_id, tx_ts, emp_id, emp_name(마스킹 가능), dept, account_policy, merchant, mcc_name, total, rules[{rule_id, severity}], review_status(unreviewed|violation|ok|hold)
- `Evidence`: rule_id, rule_name, rule_class(①규정|②임계치|③가설), severity, evidence(JSON), evidence_text(사람 말), related_tx[FlagSummary], rule_version
- `Review`: review_id, tx_id, rule_id|null, decision(violation|ok|hold), reason_code, memo, reviewer, created_at

## 1. 조회

| API | 함수 | 입력 | 출력 | 한 줄 설명 |
|---|---|---|---|---|
| 요약 통계 | `get_summary` | date_from, date_to, scope(all|leaders) | per_rule[{rule_id, flagged, reviewed, violation, hit_rate}], unreviewed_total | 대시보드 첫 화면 숫자 |
| 플래그 목록 | `list_flags` | rule_ids[], depts[], date_from, date_to, min_total, review_status, sort, page, page_size | items[FlagSummary], total | 검토할 거래를 찾는 표 |
| 거래 상세 | `get_transaction` | tx_id | 거래 전 필드 + HR 스냅샷 | 거래 한 건의 원본 |
| 근거 패키지 | `get_evidence` | tx_id | evidences[Evidence] | "왜 걸렸나"를 한 번에 |
| 맥락 | `get_context` | tx_id, n=20 | recent_tx[FlagSummary], peer{account, mcc, median, p90, n}, access_same_day[{ts, gate, event}], trip, leave | 판단에 필요한 주변 정보 |
| 사용자 프로필 | `get_employee` | emp_id | profile, tx_stats{by_mcc, by_hour, by_weekday}, flag_history, review_history | 상습인지 한 번인지 |
| 규칙 카탈로그 | `list_rules` | - | rules[{rule_id, name, class, params, version, data_ready}] | 화면이 규칙 이름을 하드코딩하지 않게 |

## 2. 검토 기록

| API | 함수 | 입력 | 출력 | 한 줄 설명 |
|---|---|---|---|---|
| 결정 저장 | `create_review` | tx_id, rule_id|null, decision, reason_code, memo, reviewer | Review | 라벨이 만들어지는 유일한 지점 |
| 결정 수정 | `update_review` | review_id, decision, reason_code, memo, reviewer | Review(새 행, 이전 행은 superseded) | 덮어쓰지 않고 이력으로 |
| 일괄 결정 | `bulk_review` | tx_ids[], rule_id|null, decision, reason_code, reviewer | count | 명백한 오탐 100건을 한 번에 |
| 사유 코드 | `list_reason_codes` | - | [{code, label, maps_to_rule_exception|null}] | 반복 사유 표준화. 억제 규칙 후보가 됨 |

테이블 `reviews`: review_id, tx_id, rule_id, decision, reason_code, memo, reviewer, created_at, superseded_by

## 3. 규칙 실행과 관리

| API | 함수 | 입력 | 출력 | 한 줄 설명 |
|---|---|---|---|---|
| 규칙 실행 | `run_rules` | rule_ids[]|null, overrides{rule.param: value} | run_id, per_rule_counts | 버튼 하나로 재점검 |
| 실행 이력 | `list_runs` | - | [{run_id, ran_at, rule_versions, data_snapshot_hash, counts}] | 같은 결과가 재현되는지 추적 |
| 임계치 변경 | `set_param` | rule_id, param, value, reason, actor | new_version | 조이기의 기록 |
| 민감도 미리보기 | `preview_param` | rule_id, param, values[] | [{value, real_flagged, synth_recall}] | 바꾸기 전에 영향 확인 (sweep.py) |
| 적중률 | `get_hit_rates` | date_from, date_to | per_rule[{flagged, reviewed, violation, ok, hold, hit_rate}] | 임계치 조정의 근거 숫자 |

## 4. 데이터 적재

| API | 함수 | 입력 | 출력 | 한 줄 설명 |
|---|---|---|---|---|
| 파일 업로드 | `ingest` | files[], period_label | load_id, rows, quality_report | 새 기간 데이터의 입구 (load.py) |
| 적재 상태 | `get_load` | load_id | status, progress, errors | 큰 파일은 시간이 걸림 |
| 컬럼 매핑 확인 | `get_column_mapping` | load_id | [{source_col, target_col, confidence}], unmapped[] | 포맷이 다른 엑셀 대응 |
| 데이터 품질 | `get_quality` | load_id | fill_rates, unmapped_accounts, cancel_handling, access_link_rate | 규칙이 못 미치는 영역 |

## 5. 기반 요소

| 요소 | 한 줄 설명 |
|---|---|
| 인증·역할 | reviewer / admin. 결정 기록의 reviewer 필드에 필요 |
| 감사 로그 | 조회·수정 전부 기록. 감사 시스템 자체가 감사 대상 |
| 개인정보 마스킹 | 이름·주소는 역할별 마스킹. LLM 전송 전 필수 |
| 스키마 | Pydantic 모델 1벌을 Streamlit과 FastAPI가 공유 |
| 테스트 | 합성 정답셋으로 `run_rules` 결과를 CI에서 검증 |

## 임시 화면(Streamlit)에 먼저 필요한 5개
`list_flags`, `get_evidence`, `get_context`, `create_review`, `get_hit_rates`. 나머지는 함수 서명만 만들어 둔다.

## 나중 전환
- Streamlit → React: 함수들을 FastAPI 라우터로 감싼다. 함수 본체는 그대로.
- DuckDB → PostgreSQL: 분석(flags 생성)은 DuckDB 유지, reviews·runs·감사 로그는 PostgreSQL로. SQL은 대부분 호환.
