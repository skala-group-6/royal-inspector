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
.venv/bin/python -I scripts/labels.py --label-source weak  # 3.7단계: 임시 정답 labels (규칙 투표 noisy-OR, labels/weak.yaml)
.venv/bin/streamlit run app/Home.py        # 4단계: 임시 검토 화면
.venv/bin/python -m pytest -q tests
```

## 문서
- `docs/PROJECT_NOTES.md` 문제·조사·설계 원칙·데이터 확인 결과
- `docs/ROADMAP.md` 진행 순서와 상태
- `docs/RULES.md` 규칙 19개, 실데이터 적중, 임계치 민감도
- `docs/API.md` 서비스 함수 / API 설계 (프런트 계약)
- `docs/REVIEW_SCREEN.md` 검토 화면 사양 · `docs/PRECEDENTS.md` 선례 기능 · `docs/MODEL.md` 우선순위 모델

## 구조
`scripts/` 적재·합성·규칙 실행·피처 · `rules/` 규칙 SQL과 카탈로그 · `features/` 피처 카탈로그와 실행기 · `labels/` 임시 정답 선언 · `synth/` 사례 명세 · `app/service.py` 서비스 함수 · `app/Home.py`, `app/pages/` Streamlit
