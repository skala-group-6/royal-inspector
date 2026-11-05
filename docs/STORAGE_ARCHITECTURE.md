# 저장소 구조 — Postgres 단독 (2026-11-05 확정) · 이전안: Postgres(기록) + DuckDB(계산)

## 0. 2026-11-05 결정: Postgres 단독
전제가 바뀌었다. 이 제품은 **회사마다 자기 안에 설치**하고 중앙에서는 규칙·코드 업데이트만 받는 구조다(`docs/ERD.md` §0). 그러면 설치·백업·권한·감사를 **한 가지 방식**으로 운영하는 것이 DuckDB의 분석 속도·엑셀 직접 읽기보다 크다. 월 1회 배치 30만 건은 Postgres로 수십 초면 충분하다.
- 모든 표는 Postgres. 스키마와 루프는 `docs/ERD.md`.
- DuckDB는 **개발자 로컬 탐색 도구**로만 남긴다(테스트 복사본 패턴 유지 여부는 계획 3에서 결정).
- 전환 비용: 규칙 SQL 21개·피처 실행기·적재의 방언 변경(`docs/ERD.md` §5). 검증은 기존 테스트(재현율 114/114, 피처 검증 7종)가 그대로 한다.
- 시점: 계획 3(FastAPI)과 함께. API가 열리기 전에 스키마를 확정해야 화면을 두 번 고치지 않는다.

아래 §1~7은 이전안(혼합)의 분석 기록이다. 표 배치 판단은 유효하나 "DuckDB에 둔다"는 결정은 위로 대체된다.


전제: 사내 배포, 서버 1대에서 시작, 5~20명 사용, 월 1회 엑셀 적재, 데이터가 특정 PC에 종속되면 안 됨. 조사 근거는 `docs/TOOLING_DECISION.md` §6(DuckDB·MotherDuck·Retool·Hex·Rill·Superset 문서).

## 1. 원칙 한 줄
**다시 만들 수 없는 것은 Postgres, 엑셀과 스크립트로 다시 만들 수 있는 것은 DuckDB.** 서버 1개(FastAPI)가 둘을 다루고, 화면·API는 어느 DB인지 모른다.

## 2. 테이블 배치 (현재 실제 테이블 기준)

| 테이블 | 행 수 | 저장소 | 이유 |
|---|---|---|---|
| reviews (판정) | 4 → 수천/년 | **Postgres** | 사람이 만든 기록. 라벨·선례·감사 증적의 원천. 손실 불가 |
| queue (검토 큐) | 7,563 | **Postgres** | 사람 작업이 붙는 단위. 재빌드 보호(force) 로직이 판정과 묶임 |
| ui_events (화면 로그) | 8 | **Postgres** | 감사 시스템 자체의 감사 증적 |
| 신규: reviewers(사용자·역할), rule_changes(임계치 변경 이력), candidate_patterns(규칙 후보·승인), model_registry(manifest 요약) | — | **Postgres** | 전부 사람의 결정 |
| transactions, employees, access_logs(82만), policy_accounts, account_map | 30,849 / 3,176 / 821,491 / 39 / 49 | **DuckDB** | 엑셀 → 적재 스크립트. 재생성 가능 |
| ground_truth, precedents(cases) | 114 / 22 | **DuckDB** | YAML → 스크립트. 재생성 가능 |
| flags | 10,279 | **DuckDB** | 규칙 실행 결과 |
| tx_features, labels, tx_score | 30,284 ×3 | **DuckDB** | 피처·라벨·점수 계산 결과 |
| geocode (지오코딩 캐시) | 8,189 | **DuckDB + Parquet 백업** | 재생성 가능하지만 API 비용·키 필요. 파일로 따로 보관 |
| labels(label_source=reviews/import) | — | DuckDB에 **스냅샷** | 원천은 Postgres reviews·윤경팀 파일. 학습 직전에 Postgres에서 뽑아 DuckDB에 적재(버전 기록) |

DuckDB 파일은 "파생 데이터"지만 **이름·주소·사번이 그대로 들어 있어 민감도는 원본과 같다.** 서버 디스크 암호화·접근 제한은 Postgres와 동일하게.

## 3. 파이프라인 단계별로 다시 보기

| 단계 | 읽음 | 씀 | 저장소 | 프로덕션 메모 |
|---|---|---|---|---|
| ① 적재 | 엑셀 | transactions 등 | DuckDB | **새 파일에 쓰고 원자적 교체**(§5). 서버가 열고 있는 파일에 쓰지 않음 |
| ② 합성 | YAML | 합성 거래, ground_truth | DuckDB | 운영 DB에는 넣지 않음(시연·테스트 전용 플래그). is_synthetic 필터 유지 |
| ③ 규칙 | tx_active | flags | DuckDB | 임계치 변경 이력은 Postgres rule_changes에 기록, 값은 YAML |
| ④ 피처·라벨 | tx_active, flags, **reviews(PG)** | tx_features, labels | DuckDB | reviews는 PG에서 읽어 스냅샷. 라벨 출처·버전 기록 |
| ⑤ 모델 | tx_features, labels | tx_score, manifest | DuckDB + 파일 | manifest 요약을 PG model_registry에 1행 |
| ⑥ 큐 빌드 | tx_active, flags, tx_score, **reviews(PG)** | **queue(PG)** | 양쪽 | 후보는 DuckDB에서 뽑고 결과 행은 PG에 삽입 |
| ⑦ 화면 목록 | queue(PG) + tx_active/flags/tx_score(DuckDB) + reviews(PG) | — | 양쪽 조인 | §4 |
| ⑧ 판정 | — | reviews, ui_events | PG | supersede + insert를 **한 트랜잭션**으로(현재 두 문장) |
| ⑨ 재학습·선례 승격 | reviews(PG) | labels, precedents | DuckDB | ④와 같은 스냅샷 경로 |

## 4. 두 DB를 어떻게 조인하나 (가장 큰 설계 비용)

`list_queue`가 queue·reviews(PG)와 tx_active·flags·tx_score(DuckDB)를 한 SQL로 조인한다. 선택지:

| 방식 | 코드 변화 | 장점 | 위험 |
|---|---|---|---|
| A. DuckDB `postgres` 확장으로 PG를 ATTACH, 기존 SQL 유지 | 최소 | 한 SQL, 지금 테스트 그대로 | 확장 설치 가능 여부(서버 OS), PG 네트워크 왕복. 7천 행 큐에서는 문제 없음 |
| B. 앱에서 두 번 조회 후 pandas 병합 | 중간 | 의존성 없음 | SQL이 파이썬으로 흩어짐, 페이징·정렬 재구현 |
| C. 큐·판정 상태를 DuckDB에 주기 복제 | 중간 | 읽기 단순 | 지연·불일치. 판정 직후 화면 갱신 어려움 |

**A를 기본, B를 폴백.** 서비스 함수 내부만 바뀌고 함수 서명과 테스트는 유지된다. 쓰기(판정·큐 삽입)는 ATTACH가 아니라 **PG 드라이버로 직접**(트랜잭션 보장).

## 5. 프로덕션에서 괜찬은가 — 항목별

| 항목 | 판단 | 조건 |
|---|---|---|
| 동시 사용자 5~20 | 문제 없음 | FastAPI 1프로세스, PG 커넥션 풀 5~10 |
| 판정 쓰기 | 문제 없음 | PG. 초당 수십 건도 여유 |
| 월 배치 중 서비스 중단 | **없음**, 단 규율 필요 | 배치는 `warehouse_next.duckdb`에 쓰고 완료 후 rename. 서버는 **read_only**로 열고 교체 신호에 재오픈. 서버가 쓰기 핸들을 가지는 순간 잠금 충돌이 재발 |
| tx_id 안정성 | **현재 결함** | `load.py`가 tx_id를 행 순번(arange)으로 부여. 엑셀이 바뀌면(월 추가·정렬) 같은 번호가 다른 거래를 가리켜 PG의 판정이 엉뚱한 거래에 붙음. **원본 식별자(전표번호+승인번호 등) 또는 원본 열 해시로 결정적 키** 필수. 분리 전 선결 과제 |
| 백업 | 충분 | PG 일일 dump + 원본 엑셀 보관 + geocode Parquet = 전체 복구. DuckDB 파일은 백업 대상 아님(재생성) |
| 스키마 변경 | 성숙 | PG: Alembic. DuckDB: 재생성이므로 마이그레이션 불필요 |
| 권한·감사 | 가능 | PG 앱 롤 1개 + 감사 로그 테이블. DuckDB 파일은 OS 권한으로만 보호 |
| 서버 2대 | 가능 | PG 공유, DuckDB 파일은 각 서버에 배치 산출물 배포(동일 입력 → 동일 파일) |
| 30만 건/년 | 여유 | DuckDB 수 초. PG 큐·판정은 소량 |
| 개발·테스트 | 비용 증가 | Docker compose로 PG 기동. 테스트는 임시 PG 스키마 또는 testcontainers. 현재 "DB 복사 후 테스트" 패턴은 DuckDB 쪽만 유지 |
| 민감정보 | 주의 | PG(memo·reviewer)와 DuckDB(이름·주소) 둘 다 사내망·암호화. LLM 전송은 규칙 출력 필드만 |

## 6. 전환 순서 (계획 3번 안에서)
1. tx_id를 결정적 키로 교체, 기존 reviews 매핑 스크립트.
2. PG 스키마(reviews, queue, ui_events, reviewers) + Alembic 초기 리비전. Docker compose.
3. `app/service.py`: 쓰기 함수(review_transaction, log_event, build_queue 삽입)를 PG 드라이버로. 읽기는 ATTACH(A) 또는 병합(B).
4. labels.py `--label-source reviews`, load_precedents.load_reviews를 PG 읽기로.
5. 서버 DuckDB read_only + 배치 "쓰고 교체" 스크립트.
6. 테스트: PG 임시 스키마 픽스처, DuckDB 복사본 유지. 33개 통과.

## 7. 하지 않는 것
- DuckDB에 판정 저장(단일 writer·충돌 에러·백업 도구 부재).
- 전부 Postgres(규칙·피처 SQL 재작성, 분석 속도 손실, 엑셀 직접 읽기 상실).
- Postgres 없이 SQLite(로컬 종속 금지 요구에 위배).
