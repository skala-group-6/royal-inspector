# 선례(유사 사례) 기능 설계 — 2026-10-31

## 목적
거래 한 건을 판정할 때 "비슷한 일로 징계된 사례가 있는가"와, 나중에는 "비슷한 거래를 감사자가 어떻게 판정했는가"를 옆에 보여준다.
판단을 대신하지 않고 **겹치는 단서와 다른 단서**를 드러내는 것이 목적이다.

## 원칙
1. 사례(징계사례 22건)와 판정 거래(reviews)를 **같은 테이블, 같은 함수, 같은 카드**로 다룬다. `kind` 값만 다르다.
2. 비교의 열쇠는 **걸린 규칙 집합**(구조적). 자연어(요약, 단서, 메모)는 사람에게 보여주는 용도로만 쓴다. 이유: "왜 비슷한가"를 규칙 이름으로 설명할 수 있어야 한다.
3. 겹치는 규칙이 0이면 아무것도 보여주지 않는다. "유사 사례 0건"은 "문제없음"으로 오독된다.
4. 기본 접힘. 펼치면 **겹치는 점 / 다른 점**을 반드시 함께 보여준다(확증 편향 방지).
5. 테스트 기간의 판정(개발팀 reviewer)은 선례로 쓰지 않는다. reviewer 이름으로 구분한다.

## 데이터 모델
```
precedents
  precedent_id  'case:12' | 'review:30512'
  kind          'case' | 'review'
  title         짧은 제목 (예: 휴가 중 사적 사용)
  summary       한두 문장 (사례: 주요시나리오 원문 요약 / 판정: 거래 요약)
  cues          ['휴가 기록과 결제 시각 모순', ...]   -- 무엇을 보고 적발했나 (판정: reason_code)
  rule_ids      ['R02','R08','R11']                 -- 규칙 서명 (비교 열쇠)
  account, mcc_group, amount_band                   -- 보조 키 (review에서 채움)
  outcome       NULL | 'violation' | 'ok'
  source        '주요시나리오#12' | reviewer
```
사례의 원천은 `synth/cases.yaml`(title, summary, cues, rules). 적재 스크립트가 테이블로 넣는다. 규칙이 바뀌면 yaml만 고친다.

## 유사도
```
score = |tx.rules ∩ p.rules| / |tx.rules ∪ p.rules|  (자카드)
      + 0.1·[account 일치] + 0.1·[mcc_group 일치]
반환: score, overlap_rules, only_in_precedent, only_in_tx
```
22건 규모에서는 임베딩이 필요 없다. 판정 거래가 수천 건이 되어 같은 서명이 많아지면 적요 임베딩을 **같은 서명 안의 순서 정하기**에만 보조로 추가한다(국내 리전 모델).

## 평가 (합성 정답셋이 공짜로 제공)
합성 거래는 출처 사례(`transactions.case_id`)를 안다. 테스트: 합성 위반 거래에 대해 자기 출처 사례가 1위인 비율 ≥ 80%. CI에 포함.

## API
`get_precedents(tx_id) → {cases:[…], reviews:[…], summary:{n, violation, ok}}` 하나. 화면은 이것만 부른다.

## 확장 흐름
1. 판정 저장(reviews) → 배치가 `precedents(kind='review')`로 복사(서명, 계정, 업종, 금액 구간, outcome, reason_code→cues).
2. 같은 함수가 kind='review'로 "비슷한 거래 n건 중 위반 m건"을 낸다.
3. 이 분포는 8단계 모델의 피처로도 들어간다.

## 화면
1층 "왜 걸렸나" 아래 칩: `📁 비슷한 징계사례 n건 · 가장 가까운: "…"` → 팝오버 카드(무슨 일 / 무엇을 보고 적발 / 겹치는 점 · 다른 점). 상세는 docs/REVIEW_SCREEN.md.
