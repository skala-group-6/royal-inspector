# "Retool 같은 것을 만들어야 하나" — 사용성·유지보수 요구에 대한 정석 접근 (2026-11-03)

과제 요구: 사용자가 쓰기 편하고, 유지보수가 편해야 한다. 이 요구를 듣고 "Retool 같은 것"이 떠오르는 것은 자연스럽지만, 그 말에는 서로 다른 두 선택지가 섞여 있다.

## 1. 두 가지 뜻을 분리

| | (a) Retool을 **써서** 화면을 만든다 | (b) Retool **같은 제품을** 만든다 |
|---|---|---|
| 뜻 | 로우코드 빌더 위에 우리 DB를 붙여 화면 조립 | 사용자가 화면·쿼리를 스스로 조립하는 범용 빌더를 개발 |
| 결론 | **보조로만**. 우리 핵심 화면에는 부적합 | **하지 않는다**. 과제 범위 밖이고 유지보수 부담이 가장 큼 |

(b)는 바로 제외한다. 범용 빌더는 Retool이 수백 명으로 만드는 제품이고, 윤경팀은 화면을 조립하고 싶은 게 아니라 **판정을 빨리 끝내고 싶은** 사용자다. "유지보수 편함"은 설정 가능성이 아니라 **바꿀 것이 적고, 바꾸는 자리가 한 곳인 것**이다.

## 2. (a) 로우코드 빌더 사실 확인

| 도구 | 셀프호스트 | 로컬 DuckDB | 비고 |
|---|---|---|---|
| Retool | Enterprise 전용 | 없음(MotherDuck만) | Free 5명. 데이터가 벤더 클라우드로 감 |
| Appsmith | 오픈소스, Docker | 없음 | REST API 경유 필요 |
| Budibase / ToolJet | 오픈소스 | 없음 | 동일 |
| Windmill | 오픈소스 | Python 스크립트로 가능 | UI 빌더는 부속 기능 |

- 어느 도구도 단일 파일 DuckDB에 직접 붙지 않는다. 쓰려면 FastAPI로 감싸야 하며, 그 순간 "코드 없는 화면"이 아니다.
- DuckDB는 쓰기 프로세스 1개만 허용한다. 어떤 스택이든 **DB 앞에 서버 프로세스 하나**가 필수.
- Retool 자신의 글: CRUD·어드민 패널은 쉽지만 "상호작용이 특수할수록 저수준 접근이 필요"하다. 우리 검토 화면(큐, J/K 이동, 3층 근거, 판정 사유, 선례 칩)이 정확히 그 특수 상호작용이다.
- 앱 정의가 벤더 JSON이라 diff·테스트·리뷰가 약하고, 졸업 후 인수인계가 "벤더 계정 안의 설정"이 된다.

## 3. 정석 접근: 바꿀 자리를 데이터로, 화면은 코드로

업계 합의(Retool 포함)는 "핵심 업무 + 특수 UX + 수개월 이상 사용 + 개발자 있음"이면 **코드로 만든다**이고, 네 조건을 우리는 모두 충족한다. 단 "유지보수 편함"은 스택이 아니라 다음 원칙에서 나온다.

| 원칙 | 우리 현황 | 뜻 |
|---|---|---|
| 규칙·임계치는 데이터(YAML) | `rules/catalog.yaml`, `features/catalog.yaml`, `labels/weak.yaml` | 윤경팀이 바꾸는 것은 코드가 아니라 파일 한 줄 |
| DB가 단일 진실 원천 | `warehouse.duckdb`에 판정·큐·점수 전부 | 화면은 보기만 함. 화면을 갈아도 기록은 남음 |
| 얇은 서비스 레이어 | `app/service.py` | Streamlit도 React도 같은 함수를 호출 |
| 테스트가 규칙 변경을 지킴 | Octave checks(unit/rules/features/model) | 임계치 바꾸고 합성 재현율 떨어지면 바로 알림 |
| 인수인계 가능 | README·ARCHITECTURE·설계서 | Docker compose 1파일 + 실행 3줄이 목표 |

즉 **"Retool 같은 유연함"은 이미 YAML 카탈로그가 담당**하고 있다. 사용자가 조립하는 건 화면이 아니라 규칙이다.

## 4. 사용성은 "조립 가능"이 아니라 "덜 누르기"

윤경팀 사용자에게 편한 것은 설정 메뉴가 아니라 다음이다.
- 큐에서 J/K로 다음 건, 한 화면에 근거·정황·배경, 두 버튼 판정.
- "왜 걸렸나"가 규정 조항과 비교 값으로 적혀 있음.
- 규칙 바꾸고 싶으면 규칙 화면에서 임계치 숫자만 수정(백로그 E: 임계치 파일 분리 후 UI 노출).
- ⌘K로 자연어 질의(로드맵 5단계), 챗봇 페이지 없음.

## 5. 결정

| 역할 | 선택 | 이유 |
|---|---|---|
| 심사자 화면 | React(Vite + shadcn/ui + TanStack) + 얇은 FastAPI | 특수 UX, 코드 소유, 인수인계 가능. 이미 진행 중 |
| 데이터 | DuckDB, 서버 프로세스 1개 독점 | 단일 파일, 설치 없음 |
| 바꾸는 자리 | YAML 카탈로그 + 규칙 화면의 임계치 편집 | "Retool 같은 유연함"은 여기 |
| PM 검증·시연 | Streamlit(현행) 유지 | 규칙 튜닝·데모용. 심사자 일상 도구는 아님 |
| 로우코드 | 사용자 관리 같은 단순 CRUD가 생기면 Appsmith 셀프호스트를 FastAPI에 붙이는 것 검토 | 5명 이하면 shadcn 페이지 하나가 더 단순 |
| 하지 않을 것 | Retool(셀프호스트 불가·DuckDB 미지원·데이터 반출), 범용 빌더 자체 개발 | |

## 출처
- Retool pricing https://retool.com/pricing · integrations https://retool.com/integrations · MotherDuck https://docs.retool.com/data-sources/guides/connect/motherduck
- Retool "React or Retool" https://retool.com/blog/react-or-retool · "3 experts on build vs buy" https://retool.com/blog/3-experts-on-building-vs-buying-internal-tools
- Appsmith datasources https://docs.appsmith.com/connect-data/reference · pricing https://www.appsmith.com/pricing
- Budibase https://budibase.com/pricing/ · ToolJet https://tooljet.com/pricing · Windmill https://www.windmill.dev/pricing
- DuckDB concurrency https://duckdb.org/docs/2.0/connect/concurrency.html
- Streamlit architecture https://docs.streamlit.io/develop/concepts/architecture/architecture · auth https://docs.streamlit.io/develop/concepts/connections/authentication

## 6. 저장소: DuckDB 단독 vs Postgres vs 혼합 (2026-11-03 조사)

질문: 사내 여러 명이 쓰려면 Postgres로 가야 하나.

**업계 입장 요약**
- DuckDB 공식: OLAP 엔진. 읽기·쓰기는 프로세스 1개, 같은 행 동시 수정은 충돌 에러(재시도 필요), 인덱스 많은 OLTP 스키마에 불리, 웹앱 상태 저장 가이드 없음. 다중 프로세스 쓰기는 Quack(2.0 정식, 인증은 공유 비밀 하나)·DuckLake만. https://duckdb.org/docs/stable/connect/concurrency · https://duckdb.org/why_duckdb · https://duckdb.org/faq
- MotherDuck(DuckDB 상용사)조차 "운영 상태는 Postgres에, 분석은 DuckDB로 오프로드". https://motherduck.com/learn/duckdb-vs-postgres-embedded-analytics/ · https://motherduck.com/blog/self-hosting-duckdb-road-to-production/
- 프로덕션 사례는 전부 분석 서빙용. 앱 상태 저장소로 쓴 공개 사례 없음. https://motherduck.com/blog/15-companies-duckdb-in-prod/ · https://www.dench.com/blog/duckdb-in-production
- SQLite: 단일 노드 앱 상태의 정석(Fly.io Litestream, Tailscale). 하루 10만 요청 이하면 충분, writer 1개 + 큐. https://www.sqlite.org/whentouse.html · https://fly.io/blog/all-in-on-sqlite-litestream/ · https://tailscale.com/blog/database-for-2022
- Postgres: "진짜 한계에 닿을 때 전문 도구 추가". 단일 PC 운영비(서비스·롤·pg_dump·업그레이드)는 파일 DB 대비 명확히 높음. https://www.amazingcto.com/postgres-for-everything/

| 항목 | DuckDB 단독(서버 1개) | Postgres 단독 | 혼합: SQLite/PG(판정·큐·로그) + DuckDB(분석) |
|---|---|---|---|
| 설치·운영 | 최저 | 높음 | SQLite면 최저, PG면 PG와 같음 |
| 동시 사용자 5~20 | 가능 | 여유 | 가능 |
| 쓰기 동시성 | 1프로세스, 동일 행 충돌 에러 | 다중 writer | OLTP 쪽이 담당 |
| 분석 30만 행 | 최고 | 충분 | 최고 |
| 백업·마이그레이션 | CHECKPOINT+복사, 도구 빈약 | pg_dump, Alembic 성숙 | SQLite 파일 복사/Litestream, Alembic 지원 |
| 권한·감사 | 없음(앱 레이어) | 롤·RLS | SQLite 없음 / PG 있음 |
| 다중 서버 | 불가 | 기본 | OLTP를 PG로 바꾸면 해결 |
| 전환 비용 | 가장 큼(경계 없음) | DuckDB 추가는 ATTACH 한 줄 | 가장 낮음(경계 이미 분리) |

**결정**
1. **지금**: FastAPI 1프로세스. **판정·큐·사용자·감사 로그는 SQLite**(WAL, BEGIN IMMEDIATE, append-only). **거래·flags·피처·점수는 DuckDB**(월 배치가 재생성). DuckDB가 SQLite를 ATTACH해 조인. Postgres 설치 없음. 서비스 함수 뒤에 두 DB를 숨겨 화면·API는 모름.
2. **Postgres로 올리는 신호**: 두 번째 앱 서버·워커가 같은 DB에 써야 함 / DB 수준 롤·감사 요구가 규제상 필수 / 자동 failover·PITR 요구 / 공유 네트워크 스토리지만 가능. 그때 SQLite → Postgres만 바꾸고 DuckDB는 `postgres` 확장으로 ATTACH.
3. **DuckDB 단독으로 가지 않는 이유**: "에러 0" 요구와 동일 행 충돌 에러·파일 잠금 사고가 충돌하고, 권한·백업·마이그레이션 생태계가 OLTP용으로 미성숙하며, 나중 전환 비용이 가장 크다.

이전 답변(2026-11-03 오전) "서버 하나면 DuckDB 단독으로 충분"은 **동작 여부로는 맞지만 정석은 아니었다.** 정석은 혼합이며, 그중 가벼운 쪽(SQLite)으로 시작한다.
