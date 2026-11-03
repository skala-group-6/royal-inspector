# royal-inspector — 법인카드 사용 점검

## 실행
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# data/raw/ 에 원본 엑셀 2개를 넣은 뒤
.venv/bin/python -I scripts/load.py        # 1단계: DuckDB 적재
.venv/bin/python -I scripts/synth.py       # 2단계: 합성 정답셋 주입
.venv/bin/python -I scripts/run_rules.py   # 3단계: 규칙 실행 + 채점
.venv/bin/python -I scripts/load_precedents.py  # 4.5단계: 징계사례 선례 적재
.venv/bin/python -I scripts/build_features.py    # 3.5단계: 피처 표 tx_features (+entity_stats 뷰)
.venv/bin/python -I scripts/validate_features.py # 3.6단계: 피처 검증 7종 (누수·중복·단조·재실행)
.venv/bin/python -I scripts/labels.py --label-source weak  # 3.7단계: 임시 정답 labels (규칙 투표 noisy-OR, packs/corp_card/weak_labels.yaml)
.venv/bin/python -I scripts/train.py --label-source weak   # 3.8단계: 기준선·로지스틱·XGBoost 같은 시험 → models/<v>/manifest.json
.venv/bin/python -I scripts/score_tx.py                    # 3.9단계: tx_score (기준선 점수 + 학습 모델 점수·이유)
.venv/bin/python -I scripts/build_queue.py --from 2025-03-01 --to 2025-03-31  # 3.95단계: 검토 큐 (규칙 + 모델 상위 M + 무작위 p%)
.venv/bin/streamlit run app/Home.py        # 4단계: 임시 검토 화면
.venv/bin/python -m pytest -q tests
```

macOS arm64에서 xgboost import가 libomp 오류를 내면 `brew install libomp` (실패 시 자동으로 sklearn HistGradientBoosting 폴백).

## 문서
- `docs/PRODUCT_ESSENCE.md` 제품의 본질 한 문장, 네 박자, Hex·Retool 비교, Claude-native 원칙
- `docs/PROJECT_NOTES.md` 문제·조사·설계 원칙·데이터 확인 결과
- `docs/ROADMAP.md` 진행 순서와 상태
- `docs/RULES.md` 규칙 19개, 실데이터 적중, 임계치 민감도
- `docs/API.md` 서비스 함수 / API 설계 (프런트 계약)
- `docs/REVIEW_SCREEN.md` 검토 화면 사양 · `docs/PRECEDENTS.md` 선례 기능 · `docs/MODEL.md` 우선순위 모델
- `docs/TOOLING_DECISION.md` 스택 결정(React+FastAPI, 로우코드 불채택) · `docs/case_study/` 기존 솔루션 동작 원리 해부 · `deliverables/` 요구사항서·WBS·아키텍처·설계서

## 스택 (2026-11-03 확정)
| 층 | 선택 |
|---|---|
| 사람의 기록 (판정·큐·로그·사용자) | Postgres |
| 기계의 계산 (거래·flags·피처·점수) | DuckDB 파일, 배치가 재생성 |
| 규칙·피처·라벨 정의 | YAML + SQL (git) |
| 배치 | Python 스크립트 (CLI) |
| 모델 | 소켓(fit/predict/explain) + 플러그(기준선·로지스틱·XGBoost·DNN 자리) |
| API | FastAPI (Postgres 쓰기, DuckDB 읽기 전용) |
| 화면 | React (Vite + shadcn/ui + TanStack) · Streamlit은 시연·검증용 |
| 개발 환경 | Docker compose (Postgres) |
근거: `docs/TOOLING_DECISION.md`, `docs/STORAGE_ARCHITECTURE.md`

## 구조
범용 엔진 + 법인카드 팩. 팩 규격 `docs/PACK_SPEC.md`, 경로 해석 `paths.py`(`PACK` 환경변수, 기본 `packs/corp_card`).
`packs/corp_card/` 법인카드 팩(규칙 SQL·카탈로그·매크로, 피처 선언, 약한 라벨, 사례) · `scripts/` 엔진 CLI(적재·합성·규칙·피처·라벨·학습·점수·큐; `keys.py` 결정적 tx_id) · `tools/` 일회성 분석 · `features/executor.py` 피처 실행기 · `models/` 모델 소켓과 플러그(기준선·로지스틱·XGBoost·DNN 자리) · `app/service.py` 서비스 함수 · `app/Home.py`, `app/pages/` Streamlit(시연·검증용) · `web/` React 정식 화면(진행 중)
