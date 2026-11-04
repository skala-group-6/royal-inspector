# 검토 화면 사양 (프런트 요구사항) — 2026-10-31

Streamlit 임시 구현(`app/pages/1_플래그_검토.py`)은 버려져도 이 사양과 `app/service.py`는 남는다. 근거: `research_notes/audit_review_ui_references*.md` (Stripe Radar, Ramp, Brex, Expensify, Concur Verify, HighBond, MindBridge, SAS, 국내 감사 점검표).

## 원칙
1. 한 번에 한 질문. 1층 "규정에 어긋나나" → 2층 "정황이 뒷받침하나" → 3층 "반복인가". 대부분은 1층에서 끝나야 한다.
2. 이유는 코드가 아니라 문장. 결론 한 줄 + 숫자 한 줄 + 근거 규정 한 줄.
3. 심각도는 두 가지. 🔴 위반 가능(규정 근거 있음) / ⚪ 참고(통계·가설). 등급은 `packs/corp_card/rules/catalog.yaml`의 `tier`.
4. 판정은 거래 단위, 버튼 셋. 위반 / 아님 / 보류. "아님"일 때만 사유 필수. 자동 진행 없음, "다음 건" 버튼.
5. 모든 결정은 이력으로 남고 덮어쓰지 않는다(`reviews.superseded_by`).

## 화면 A. 목록
| 열 | 내용 |
|---|---|
| 등급 | 🔴/⚪ + 걸린 규칙 수 |
| 일시, 사용자(마스킹), 직급, 가맹점, 업종, 금액, 계정, 상태, 합성 표시 | |
기본 필터: 미검토. 정렬: 걸린 규칙 수 / 금액 / 날짜. 우측 상단: 목록 건수, 오늘 처리 건수.
선택 상태는 세션(또는 URL)에 보관한다. 목록 쿼리는 tx_id를 마지막 정렬 키로 넣어 순서가 결정적이어야 한다.

## 화면 B. 1층 (항상 보임)
- 헤더: #id · 일시(요일) · 사용자(부서 직급) · 가맹점 [업종] / 금액 · 계정 · 적요 · 증빙 유무
- 왜 걸렸나: 규칙마다
  - `{DOT} **{결론}**` 예: 🔴 **금지 업종 노래방**
  - `{숫자} · {R08 규칙명}` 예: 계정 의욕관리비 · 목 22:57 · 590,000원 · R08 금지 업종
  - `근거: {규정 인용}` 예: 의욕관리비 규정 Don'ts: "유흥주점, 골프장, 노래방 …" (`service.policy_citation`)
  - 링크 두 개: **왜?** (`catalog.explain`) · **동료** (같은 계정×업종 중앙값, 상위 몇 %)
- 함께 볼 거래: 분할 짝, 동시간 상대, 반복 패턴 (`flags.related_tx_ids`)
- 선례 칩(겹치는 사례가 1건 이상일 때만): `📁 비슷한 징계사례 n건 · 가장 가까운: "…"` → 팝오버 카드: 무슨 일이었나 / 무엇을 보고 적발했나 / 겹치는 점(규칙) · 다른 점(규칙). 나중에 판정 선례가 쌓이면 같은 칩에 "비슷한 거래 n건 중 위반 m건". 설계 `docs/PRECEDENTS.md`
- 판정 패널(우측): [위반] [아님] / 보류 · 다음 건 → / 저장 확인 문구 / 이 거래의 결정 이력

## 화면 C. 2층 "정황 보기" (접힘)
상태 배지(휴일·휴가·출장) · 그날 동선 타임라인(출입 + 카드, ★ = 이 거래)

## 화면 D. 3층 "배경 보기" (접힘)
이 사람 이력(걸림/위반/아님) · 계정 규정 허용/금지 원문 · 최근 거래 20건 · 원본 근거 JSON

## 서비스 함수 대응 (`app/service.py`)
list_flags · get_transaction · get_evidence(+evidence_headline, policy_citation, rule_explain) · get_context · get_day_timeline · get_policy · review_transaction · get_reviews · next_unreviewed · today_count · log_event

## 아직 못 한 것 / 정식 UI에서 할 것
- 좌우 두 칸(목록 왼쪽, 상세 오른쪽 패널) — Streamlit 한계로 상하 배치
- 키보드 단축키(다음/이전, 판정)
- 통과한 규칙도 접어서 표시(Concur 패턴)
- 검토자 피드백 "규칙이 틀렸다" 버튼 → 억제 규칙 후보로 수집(Ramp 패턴)
- 참석자 정보: 원천 데이터에 없음. 데이터 확보 시 1층 헤더에 추가

## 셸 구조 (2026-11-04, React `web/`)
shadcn 공식 패턴 둘의 조합: **"사이드바가 사이트 헤더 아래에 들어가는" 패턴 + `variant="inset"`**.
- **바탕**(`bg-sidebar`, 한 단계 어두움): 상단 헤더 띠(트리거 · 섹션 제목 · ⌘K 자리)와 아이콘 **레일**(섹션 4개 + 사용자).
- **카드**(`SidebarInset`, 둥근 모서리·그림자): 안에 **목록 패널**(20rem, 현재 섹션의 목록) + **메인**(선택 항목 내용)이 한 면으로.
- 레일은 shadcn 사이드바를 **접힘 상태로 고정**(`SidebarProvider open={false}`)해 항상 48px 아이콘 레일. 목록 패널은 **별도 상태**(`components/panel-state.tsx`, localStorage 저장, ⌘B·헤더 토글). 두 개념을 한 상태로 묶으면 패널을 여닫을 때마다 레일 버튼이 펼침↔접힘 스타일 사이를 전환해 출렁인다(2026-11-04 수정, CDP 실측으로 아이콘 위치 불변 확인). 모바일에서 토글은 레일 시트를 연다.
- 섹션: 검토 `/review` = 큐 목록, 데이터 `/data` = 적재·큐 이력, 규칙 `/rules` = 규칙 목록, 요약 `/summary` = 패널 없음.
- 상태는 전부 URL: 활성 섹션 = 첫 경로 조각(`components/sections.tsx` `useActiveSection`), 선택 = 파라미터(`/review/$txId`, `/rules/$ruleId`). 전역 스토어 없음.
- 목록 행 배지는 글자만("위반 n", "참고 n", "모델 추천", "무작위 표본", "위반 처리"). 이모지 없음. 거래 식별은 전표번호, tx_id는 URL에만.
- 파일: `app-shell.tsx`(배치), `app-sidebar.tsx`(레일), `section-panel.tsx`(카드 안 목록 열), `site-header.tsx`(헤더 띠), `lists/*`(섹션별 목록).
