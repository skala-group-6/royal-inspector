# 팩 규격 (Pack Spec) — 범용 검토 엔진에 데이터 도메인을 꽂는 양식 (2026-11-03)

엔진(규칙 실행기·피처 실행기·라벨·모델·큐·판정·화면)은 데이터 도메인을 모른다. 도메인은 **팩 폴더 하나**로 들어온다. 첫 팩은 `packs/corp_card/`(법인카드). 두 번째 팩(예: 출장비)은 이 양식을 따른다. 계획 10의 팩 생성 에이전트도 이 양식대로 초안을 쓴다.

## 1. 폴더 구성
```
packs/<name>/
  pack.yaml            매니페스트 (아래 2)
  rules/catalog.yaml   규칙 카탈로그 v2: id, name, tier(violation|advisory), cluster(같은 상황 묶음), fact_key(주장하는 사실의 이름 — 같은 묶음에서 같으면 한 줄로 합침), params, fact(규칙 줄 한 문장, 사실만), brief{value, verdict}(관측값 · 판단어), explain, policy_ref. fact·brief는 서버가 evidence로 렌더(service.rule_fact)
  rules/sql/R*.sql     규칙 1개 = SQL 1장. 출력 계약 고정 (아래 4)
  rules/functions.sql  (선택) PostgreSQL SQL 함수(sido_of 등). 규칙·피처가 공유. bootstrap_db.py가 schema 다음에 적용
  features.yaml        피처 선언: {entity}__{window}__{what}, 시점 기준(point-in-time) 집계. docs/FEATURES.md
  weak_labels.yaml     약한 라벨: p_tier·prior·p_rule (noisy-OR). 묶음(cluster)은 rules/catalog.yaml의 cluster 필드. docs/MODEL.md
  cases.yaml           선례·합성 사례 명세(징계사례 등). docs/PRECEDENTS.md
```
적재 스크립트(엑셀 → 계약 테이블)와 합성 생성기는 지금 `scripts/load.py`, `scripts/synth.py`에 있다(파이썬은 `scripts/`에 둔다 — `python -I` sys.path 관례). 두 번째 팩은 `scripts/load_<name>.py`를 추가하고 pack.yaml의 `raw_glob`으로 원본을 가리킨다.

## 2. pack.yaml
| 키 | 뜻 | 필수 |
|---|---|---|
| name, version | 팩 이름·버전 | 예 |
| rules_catalog, rules_sql_dir | 규칙 카탈로그·SQL 폴더 (pack.yaml 기준 상대경로) | 예 |
| functions | 팩 SQL 함수 파일. null 허용 | 아니오 |
| features_catalog | 피처 선언 | 예 |
| weak_labels | 약한 라벨 설정 | 예 (라벨 없을 때 학습 시작점) |
| cases | 선례·합성 사례 | 아니오 |
| raw_glob | `data/raw/` 아래 원본 파일 패턴 목록 | 적재 스크립트가 쓰면 예 |
| presentation | 표현 코드(근거 문장 템플릿·규정 인용·타임라인) 모듈. 계획 3에서 사용 | 아니오(예약) |
`paths.py`가 `PACK` 환경변수(기본 `packs/corp_card`)로 이 파일을 읽어 상수로 노출한다. 엔진 코드는 경로를 하드코딩하지 않는다.

## 3. 입력 계약 — 적재가 만들어야 하는 테이블
`transactions` + 뷰 `tx_active`(= 제외 사유 없는 행).

| 열 | 필수 | 뜻 |
|---|---|---|
| tx_id BIGINT | **필수** | **결정적 키.** 행 순번 금지. 거래 내용 필드의 해시(`scripts/keys.det_ids`). 엑셀을 다시 내보내도 같은 거래는 같은 번호 |
| emp_id | **필수** | 주체(사람). "평소 대비" 피처의 축 |
| tx_ts TIMESTAMP | **필수** | 시각. 시간순 분할·누적 피처·큐 기간 |
| total | 권장 | 금액. 없으면 금액 피처·규칙 비활성 |
| mcc_name / 분류 | 권장 | 업종·카테고리 |
| dept, rank | 권장 | 동료 비교 축 |
| merchant, approver_id | 선택 | 가맹점·승인자 피처 |
| exclude_reason | 권장 | 취소쌍 등 분석 제외 사유. `tx_active`가 걸러냄 |
| is_synthetic BOOLEAN | 필수(합성 쓰면) | 합성 행 표시. 모델·큐·통계가 제외 |
보강 테이블(선택): `employees`, `access_logs`, `policy_accounts`, `geocode` 등. 있으면 해당 규칙·피처·표현이 켜진다.

## 4. 규칙 출력 계약 (엔진이 읽는 유일한 형태)
`flags(rule_id, tx_id, evidence JSON, related_tx_ids BIGINT[], severity, rule_version)`. 규칙 SQL은 `tx_id, evidence, related`를 내고 실행기가 나머지를 채운다. 화면·모델·선례는 이 테이블만 본다.

## 5. 엔진이 만드는 테이블 (팩 무관)
PostgreSQL 한 곳(`db/schema.sql`). 파생: `rule_runs`·`flags`(현재 실행은 `current_flags` 뷰), `tx_features`(실행기가 생성)·`entity_baselines`, `labels`, `model_versions`·`tx_scores`·`model_bindings`, `precedents`(사례 라이브러리는 tenant 공용). 기록: `queues`·`queue_items`, `reviews`, `audit_events`. 설명 docs/ERD.md.

## 6. 두 번째 팩을 만드는 절차
1. `packs/<name>/` 복사 → pack.yaml의 name·raw_glob 수정.
2. `scripts/load_<name>.py`: 원본 → §3 계약 테이블. tx_id는 `keys.det_ids(df, [식별 필드들])`.
3. 규칙 SQL·카탈로그 작성(도메인 규정에서). 피처 선언은 범용 항목 유지 + 도메인 항목 추가. 약한 라벨 클러스터 재정의.
4. (권장) 합성 사례 `cases.yaml` + 생성기 → 재현율 체크.
5. `PACK=packs/<name>`로 같은 CLI 실행: run_rules → build_features → validate_features → labels → train → score_tx → build_queue.
6. `tests/test_pack.py`가 매니페스트 경로 존재·키 결정성을 검사한다.

## 7. 지키는 선
- 엔진 코드(`scripts/*.py` 중 load/synth 제외, `features/executor.py`, `models/`, `app/service.py` 범용 부분, `web/`)에 팩 이름이나 도메인 열을 넣지 않는다. 예외는 계획 3에서 `presentation`으로 뺀다.
- 팩은 엔진 테이블(flags 등)의 스키마를 바꾸지 않는다.
- 판정은 사람. 팩도 에이전트도 `reviews`에 직접 쓰지 않는다.
- 검토 화면의 **다섯 층(결론 → 맥락 → 해석 → 근거 → 제2의견)의 순서와 틀은 엔진**이 정한다. 팩이 정하는 것은 두 가지: 규칙마다 2층에 들어갈 **맥락 종류**(그날 동선 / 금액 비교 / 없음)와 4층의 **확인할 문서 목록**(품의서·영수증 등). 규칙 카탈로그의 `context`·`documents` 항목으로 선언한다(계획: 지금은 `web/src/lib/copy.ts`와 패널 코드의 규칙 접두 표). 사람 말 결론 문장의 템플릿도 팩 소유.
