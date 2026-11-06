# royal-inspector — 법인카드 사용 점검

## 실행
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
docker compose up -d --wait db             # PostgreSQL 17 (localhost:5433, DB `ri`). 접속: DATABASE_URL (기본 postgresql://postgres:x@localhost:5433/ri)
# data/raw/ 에 원본 엑셀 2개를 넣은 뒤 — 전부 한 번에: .venv/bin/python scripts/bootstrap_db.py (스키마 → 아래 10단계, 2~5분; 학습이 대부분)
.venv/bin/python scripts/bootstrap_db.py --schema-only   # 0단계: db/schema.sql + 팩 SQL 함수 + tenant 1
.venv/bin/python -I scripts/load.py        # 1단계: 엑셀 → transactions 등 (COPY)
.venv/bin/python -I scripts/synth.py       # 2단계: 합성 정답셋 주입
.venv/bin/python -I scripts/run_rules.py   # 3단계: 규칙 실행 + 채점
.venv/bin/python -I scripts/load_precedents.py  # 4.5단계: 징계사례 선례 적재
.venv/bin/python -I scripts/build_features.py    # 3.5단계: 피처 표 tx_features (+entity_stats 뷰)
.venv/bin/python -I scripts/validate_features.py # 3.6단계: 피처 검증 7종 (누수·중복·단조·재실행)
.venv/bin/python -I scripts/labels.py --label-source weak  # 3.7단계: 임시 정답 labels (규칙 투표 noisy-OR, packs/corp_card/weak_labels.yaml)
.venv/bin/python -I scripts/train.py --label-source weak   # 3.8단계: 기준선·로지스틱·XGBoost 같은 시험 → models/<v>/manifest.json
.venv/bin/python -I scripts/score_tx.py                    # 3.9단계: tx_scores (모델마다 1행, rank_pct) + serving 바인딩(rank/discover)
.venv/bin/python -I scripts/build_queue.py --from 2025-03-01 --to 2025-03-31  # 3.95단계: 검토 큐 (규칙 + 모델 상위 M + 무작위 p%)
pnpm --dir web install && pnpm --dir web dev  # 검토 화면(React). Octave Run 버튼도 이것을 띄움
.venv/bin/streamlit run app/Home.py        # (동결) 시연용 Streamlit 화면
.venv/bin/python -m pytest -q tests        # 테스트는 `ri`를 템플릿 복제한 임시 DB에서 돈다 (tests/conftest.py)
```

테스트·체크용 복제: `DATABASE_URL=$(.venv/bin/python scripts/db_clone.py --name x)` (1초, 끝나면 `--drop`). 1시간 넘은 복제는 자동 정리.

macOS arm64에서 xgboost import가 libomp 오류를 내면 `brew install libomp` (실패 시 자동으로 sklearn HistGradientBoosting 폴백).

## 문서
- `docs/PRODUCT_ESSENCE.md` 제품의 본질 한 문장, 네 박자, Hex·Retool 비교, Claude-native 원칙
- `docs/PROJECT_NOTES.md` 문제·조사·설계 원칙·데이터 확인 결과
- `docs/ROADMAP.md` 진행 순서와 상태
- `docs/RULES.md` 규칙 19개, 실데이터 적중, 임계치 민감도
- `docs/API.md` 서비스 함수 / API 설계 (프런트 계약)
- `docs/INGESTION.md` 데이터 적재: 파일이 정식 입구인 이유(카드사·DB 연동 판단), 매핑표·입구 검사·파일 보관함·업로드 화면
- `docs/REVIEW_SCREEN.md` 검토 화면 사양 · `docs/PRECEDENTS.md` 선례 기능 · `docs/MODEL.md` 우선순위 모델
- `docs/DESIGN.md` 디자인 규칙: 선 대신 면(surface-* 토큰)·여백·글자 위계(type-*), 공용 목록 부품, 검사
- `db/schema.sql` **Postgres 스키마(진실)** — dbdiagram.io에 붙여넣으면 ERD · `docs/ERD.md` 설계 원칙·표 설명 · `docs/design/erd.html` 개념도
- `docs/TOOLING_DECISION.md` 스택 결정(React+FastAPI, 로우코드 불채택) · `docs/case_study/` 기존 솔루션 동작 원리 해부 · `deliverables/` 요구사항서·WBS·아키텍처·설계서

## 스택 (2026-11-03 확정)
| 층 | 선택 |
|---|---|
| 저장소 | **PostgreSQL 17 단독**(회사별 설치, 2026-11-05 결정 · 2026-11-06 전 엔진 이전 완료). 스키마 `db/schema.sql`, 설명 `docs/ERD.md`, 접속층 `db/conn.py` |
| 규칙·피처·라벨 정의 | YAML + SQL (git) |
| 배치 | Python 스크립트 (CLI) |
| 모델 | 소켓(fit/predict/explain) + 플러그(기준선·로지스틱·XGBoost·DNN 자리) |
| API | FastAPI |
| 화면 | React (Vite + shadcn/ui + TanStack) · Streamlit은 시연·검증용 |
| 개발 환경 | Docker compose (Postgres) |
근거: `docs/TOOLING_DECISION.md`, `docs/STORAGE_ARCHITECTURE.md`

## 구조
범용 엔진 + 법인카드 팩. 팩 규격 `docs/PACK_SPEC.md`, 경로 해석 `paths.py`(`PACK` 환경변수, 기본 `packs/corp_card`).
`packs/corp_card/` 법인카드 팩(규칙 SQL·카탈로그·매크로, 피처 선언, 약한 라벨, 사례) · `scripts/` 엔진 CLI(적재·합성·규칙·피처·라벨·학습·점수·큐; `keys.py` 결정적 tx_id) · `tools/` 일회성 분석·개발 도구(`export_mock.py`: 서비스 함수로 React mock 추출, `remap_reviews.py`) · `features/executor.py` 피처 실행기 · `models/` 모델 소켓과 플러그(기준선·로지스틱·XGBoost·DNN 자리) · `app/service.py` 서비스 함수 · `app/Home.py`, `app/pages/` Streamlit(시연·검증용) · `web/` React 정식 화면(진행 중)
