# 07. Ramp (주) · Brex (보조) — 카드 발급사 측 통제 시스템

> 조사일 2026-11-02. 출처 등급: [공식문서] [기술블로그] [마케팅] [2차]. 확인 못 한 항목은 ⚠️ 표기.
> 두 회사는 **카드 발급사(issuer)이자 지출관리 SaaS**다. 우리와 달리 승인(authorization) 시점에 거래를 직접 거절할 수 있다. 이 문서의 핵심 질문은 "그렇게 좋은 사전 통제가 있는데 왜 사후 감사가 여전히 필요한가"이다.
> Brex는 2026-04-07 Capital One에 인수 완료(SEC 8-K/10-Q). 이후 문서·기능이 통합될 수 있어 Brex 항목은 2026년 상반기 기준.

## 0. 한 장 요약

Ramp·Brex는 **카드를 직접 발급**하기 때문에 결제 승인 순간에 MCC·가맹점·금액·한도·요일로 거래를 **거절**할 수 있고, 거절 못 한 거래는 영수증 자동수집 + LLM 정책 에이전트로 **예외만 사람에게** 올린다. 사람(심사자)은 전체의 10~15%만 본다.

- **승인 시점에 쓸 수 있는 데이터는 네 가지뿐**: 가맹점 디스크립터, MCC, 금액, 위치(+카드 제시 방식). 품목·참석자·목적은 **결제 뒤 영수증·메모**로만 들어온다. 그래서 "허용 식당에서 가족 식사" 같은 사적 사용은 구조상 승인 단계에서 막을 수 없다.
- **룰은 데이터로 존재**: 카드·펀드 단위 설정값(허용/차단 카테고리, 가맹점 allow/block, 최대 건당 금액, 주기 한도, 자동 잠금일)이 전부 UI 필드이고, 정책 플래그(주말·과도한 팁·영수증 불일치·AI 생성 영수증 의심)도 켜고 끄는 항목이다.
- **LLM은 세 곳에**: 영수증 읽기·메모 초안(Ramp "Intelligence", Brex Assistant), 정책 문서 기반 승인 추천(Ramp Policy Agent: Approve / Needs review / Reject + 정책 조문 인용), 가맹점 오분류 수정(RAG 에이전트). Ramp 기술 블로그가 설계·평가를 공개했고, Brex는 마케팅 외 기술 공개가 거의 없다.
- **피드백은 "사람 판정 = 정답"으로 쓰지 않는다**: Ramp는 "finance 팀은 관대해서 승인 기록을 정답으로 쓰면 모델이 느슨해진다"고 명시하고, 주간 라벨링 세션으로 golden set을 따로 만든다. 심사자 override는 감사 로그와 정책 편집 제안으로 돌아간다.
- 우리에게: 발급사가 아니므로 차단은 못 하지만, **룰=데이터·결제 직후 메모 요청·2/3 일치 영수증 매칭·예외만 검토·"왜 플래그됐나"를 정책 조문으로 설명**하는 패턴은 그대로 가져올 수 있다. 피할 것: 벤더 자가 수치(99%, 15x) 인용, 사용자 승인 기록을 라벨로 쓰는 것, 미국 MCC 품질을 한국 업종코드에 가정하는 것.

## 1. 한 줄 정의

Ramp(2019, 뉴욕)와 Brex(2017, 샌프란시스코)는 **법인카드를 자체 발급**하고(Ramp: Visa, Sutton Bank/Celtic Bank 발급; Brex: Mastercard, Emigrant/Fifth Third 발급 + Visa Sutton Bank) 그 위에 지출관리 SaaS를 얹은 회사다. 결제 승인 요청이 네트워크를 거쳐 자사 시스템으로 들어오므로 **거래 발생 전 차단(pre-authorization)**, 결제 직후 **영수증·메모 수집**, 월말 전 **정책 위반 플래그·승인 흐름**의 세 단계를 한 제품 안에서 처리한다. 감사자가 아니라 **재무팀 관리자(controller)와 카드 사용자** 양쪽이 사용자다. [공식문서]

## 2. 데이터 입력

- **승인 메시지(실시간)**: 네트워크(Visa/Mastercard ISO 8583)로 들어오는 것은 가맹점 디스크립터(단말기가 보내는 원문, 예 `PTI*BRYANTPARKWV`), MCC(가맹점이 단말기에 설정, Ramp는 "변경 불가"라 명시), 금액·통화, 가맹점 도시/주/우편번호, 카드 제시 방식(대면/디지털 월렛 등). Ramp 기술 블로그의 사기 모델 입력도 정확히 이 필드들이다: "merchant, category, country, amount, time, how the card was presented, approved or not". [공식문서][기술블로그]
- **승인 시점에 없는 것**: 품목(line item), 참석자, 업무 목적, 영수증. 이들은 결제 뒤 사용자가 올리거나 자동수집으로 들어온다. Visa Level 2/3 품목 데이터는 청산(clearing) 단계 B2B 가맹점에만 존재. [2차]
- **영수증 수집 경로(Ramp)**: SMS 회신(사진 + 텍스트는 메모로), Gmail/Outlook 사내 메일박스 스캔(관리자 전사 설정 또는 직원 개인 연결, merchant·amount·date로 매칭), 포워딩 주소, Chrome 확장, iOS 사진첩 온디바이스 매칭, 벤더 직접 수집(Adobe·항공사·Walmart 등 "standard auto-capture": 이름·이메일·확인번호·카드 끝 4자리를 벤더에 보내 조회), Amazon 계정 로그인 대행(미국 한정, 30일 내 거래). Uber·Lyft 자동수집은 Ramp 문서에 없음. [공식문서]
- **영수증 수집 경로(Brex)**: 자동 생성 영수증(Amazon·주요 항공사, 구매 즉시 또는 1~3일 후), SMS/WhatsApp 회신, Slack 스레드 회신, receipts@brex.com 포워딩(2개월 이내만 자동 매칭), Gmail/Outlook 애드온(키워드 "receipt/invoice" 시간별 수집), Lyft Business·Uber Business 직접 연동, 대량 업로드 500장. [공식문서]
- **정책 문서**: Ramp Policy Agent는 회사 경비 정책 PDF를 받아 "구조화된 agent-facing 정책"으로 변환(이미지·하이퍼링크 해석 불가, 권장 10쪽/1만 단어). Brex Policy Rule Builder는 if-then 룰로 직접 입력. [공식문서]
- **보조 컨텍스트**: Ramp — HRIS 커스텀 필드(부서·직급), GSA 출장 기준율, 펀드·카드 속성(물리/가상, 스펜드 프로그램), 최근 지출 이력. Brex — Google Calendar(지출 시각 전후 일정만 읽음), 위치. [공식문서][2차]
- **없으면 못 돌아가는 전제**: 자기가 발급한 카드여야 한다. 타사 카드 피드는 Ramp/Brex 통제 대상이 아니다. 이것이 우리와의 결정적 차이다.

## 3. 구성요소와 흐름

```
 [결제 단말]──네트워크(Visa/MC)──▶ 승인 요청 {디스크립터, MCC, 금액, 위치, 제시방식}
                                      │  ≤ 수백 ms 예산
                                      ▼
 ┌──────────────────────────────────────────────────────────┐
 │ ① 승인 결정 (pre-authorization)                            │
 │  카드/펀드 룰: 잠금·종료 → 건당 최대금액 → 주기 한도 →      │
 │  회사 잔여한도 → 허용/차단 카테고리(MCC 매핑) →              │
 │  허용/차단 가맹점(디스크립터 매칭) → 가상카드 전용 여부     │
 │  + 사기 모델(XGBoost + 거래 시퀀스 Transformer, Ramp)       │
 │  → 승인 / 거절(SMS로 사유 통보, 예외 요청 가능)             │
 └──────────────┬───────────────────────────────────────────┘
                ▼ 승인된 거래
 ┌──────────────────────────────────────────────────────────┐
 │ ② 결제 직후 (post-auth, pre-review)                        │
 │  SMS/푸시 "영수증 필요" → 회신 사진·텍스트=메모            │
 │  영수증 자동수집(메일·벤더·사진첩) → OCR → 3필드 매칭      │
 │  가맹점 정규화(디스크립터→이름·카테고리·로고)              │
 │  LLM 메모 초안·GL 코드 제안(임베딩 유사거래 검색)          │
 └──────────────┬───────────────────────────────────────────┘
                ▼
 ┌──────────────────────────────────────────────────────────┐
 │ ③ 정책 평가                                                │
 │  (a) 결정론 플래그: 금액 초과·주말·과도한 팁·영수증 불일치 │
 │      ·영수증 재사용·차단 품목(MCC)·알코올·AI생성 영수증    │
 │  (b) Policy Agent(LLM): 정책 조문 × 거래+영수증+메모+HRIS   │
 │      → Approve / Needs review / Reject + 조문 인용 + 근거  │
 │  (c) Brex: 룰 빌더 플래그 + "anomalous spend" ML + 품목    │
 │      의미 기반 고위험 플래그(예: 'vodka')                   │
 └──────────────┬───────────────────────────────────────────┘
                ▼
 ┌──────────────────────────────────────────────────────────┐
 │ ④ 검토 큐                                                  │
 │  저위험 자동승인(autonomy slider) · 예외만 관리자/매니저    │
 │  Reject → Request changes / Request repay(개인 상환)       │
 │  override·👍👎 → 감사 로그, 정책 편집 제안("coming soon")   │
 └──────────────────────────────────────────────────────────┘
```

- **①의 설정은 전부 데이터**: Ramp 펀드 편집 화면의 필드 — Amount, Frequency(Daily/Weekly/Monthly/Quarterly/Yearly/Does not repeat), Max expense amount, Lock on a certain date, Category restrictions(Allowed/Blocked/None), Merchant restrictions(Allowed/Blocked/None), Spend on(물리+가상/가상만). 회사 단위 글로벌 차단 목록은 카드 단위에서 allowlist로 풀 수 없다. [공식문서]
- **Brex의 두 층**: 스펜드 리밋(카드 한도) 레벨 통제가 정책 레벨 통제를 **우선**한다. 2026-07 정책 레벨 MCC 통제가 Policy Rule Builder에 추가되어 "한 번 설정, 정책 아래 모든 카드 적용"이 가능해졌다. Brex는 "사전 승인 룰(차단)과 사후 승인 룰(플래그)"을 명시적으로 구분하고, 오차단 방지를 위해 **MCC는 차단보다 플래그로** 쓰라고 권고한다. [공식문서]

## 4. 판단 방식

### 4.1 승인 시점 (룰 + 사기 모델)
- 룰은 결정론적이며 순서대로 평가된다(위 그림). Ramp 거절 사유 목록 11종 중 정책 관련은 금액한도·회사한도·가맹점 제한·카테고리 제한·가상카드 전용·사기 의심 6종. 거절 시 카드 사용자에게 SMS로 사유를 보내고 **예외 요청** 버튼을 준다. [공식문서]
- **가맹점·카테고리 매칭의 실제 품질**: Ramp 문서가 스스로 적은 한계 — 같은 벤더가 여러 디스크립터로 들어오므로 allowlist에 한 항목만 넣으면 다른 디스크립터는 거절됨; Ramp가 가맹점을 잘못 라벨링해 제한 거절이 날 수 있음("Report incorrect merchant info"로 신고). Brex 문서 — 카테고리는 "카드 네트워크 데이터 + 자체 ML 모델"로 정하며 "항상 정확하지는 않음", 수정은 Brex 지원팀만 가능, 룰 세트를 여러 개 겹치면 오플래그·오차단 발생. [공식문서]
- **사기 모델(Ramp, 2026-10 기술 블로그)**: 기존 XGBoost에 거래 시퀀스 Transformer(3 attention layer)를 붙여 카드 사용자의 최근 거래 이력을 임베딩. 사전학습은 사기 라벨 없이 "다음 거래 예측·마스킹 복원·필드 교체 탐지" 3개 목표로 2년치 거래를 L40S 4장에서 1.5시간. 가맹점은 빈도별 3단계 임베딩(개별 / 카테고리 내 해시 슬롯 ~200만 / 카테고리 토큰). 결과: 같은 플래그 예산에서 사기 금액 32% 더 포착(그중 29pt는 **금액 가중 손실함수**만으로), 중앙값 지연 145ms→54ms. "사기 라벨은 희소하고 몇 주 늦게 온다"고 명시. [기술블로그]
- 이 모델은 **도난·탈취 사기**용이다. 임직원의 사적 사용(authorized misuse)은 사기 라벨에 안 잡힌다.

### 4.2 결제 후 정책 평가
- **결정론 플래그(Ramp Policy Flags)**: 기본 — 가맹점 제한, 카테고리 제한, 금액 조건. Plus — Excessive Tipping(세전 금액 대비 %), Weekend Spend(금요일 밤~일요일 밤, 사용자 로컬 시각), Itemized Receipt Required(식당·일반상품·슈퍼·주류/바·숙박), Receipt Doesn't Match Transaction(금액·가맹점·날짜), Receipt Previously Used(환급 건 한정), Blocked Items(종교·정치·담배 MCC), Alcohol(영수증 품목+가맹점명 분류), Receipt likely AI-generated(이미지 메타데이터). 플래그 결과는 Out-of-policy(자동승인 차단 + 승인 사유 필수 + 매니저 추가) 또는 Warning(라벨만). **중복 거래·개인 사용·영수증 누락 플래그는 목록에 없다.** [공식문서]
- **Policy Agent(LLM)**: 입력은 §2의 정책 문서 + 거래 + 직원 입력 + HRIS·GSA + 카드 속성 + 최근 이력. 출력은 Approval recommended / Requires review / Rejection recommended. 설명은 (i) 토글에 참조 조문, 활동 피드에 근거·인용 텍스트·**정책 버전**. 애매하면 보수적으로 Requires review. 숫자 확신도는 "재현 불가·신뢰 불가"라며 **의도적으로 쓰지 않는다**. [공식문서][기술블로그]
- 기술 블로그가 밝힌 설계 원칙: Approve/Reject/Needs review 세 범주 고정, 설명 bullet마다 정책 조문 링크, "모르겠다"를 유효한 출력으로 취급해 기존 에스컬레이션 경로로 보냄, 결정론 룰(금액·벤더 블록·카테고리)을 LLM 위에 **별도 층**으로 유지, autonomy slider(예: $50 초과 전부 사람 / 의심 건만 사람)를 기존 워크플로 빌더 위에 구현. 평가는 "crawl-walk-run" 단계의 golden dataset + CI 회귀. 실패 원인 대부분은 모델이 아니라 **컨텍스트 누락**(직급·HRIS·영수증 추출·ERP 계정과목·과거 패턴)이었다. [기술블로그][2차 ZenML 요약]
- **Brex**: 룰 빌더 조건은 금액·경비유형·벤더·직원 역할·HRIS 필드·카드 유형·회계 필드·MCC, 액션은 영수증/메모/참석자/회계필드 요구·승인자 지정·플래그·차단. 시간 조건은 없음. 섹션 내 "마지막 매칭 룰 우선"(문서 예시는 first-match로 읽혀 ⚠️ 상충). 플래그 출처는 "정의된 리스크 룰 + anomalous spend ML(예: 영수증보다 큰 환급 청구) + 정책". 2024-02 "Powerful AI for expense reviews"가 품목 의미 기반 고위험 플래그('vodka'), 위반 사유를 대화로 설명하는 코멘트, 자연어 검색을 발표. 2025-11 Fall Release는 Review Agent(저위험 자동승인·예외 에스컬레이션·미준수자 팔로업)와 Audit Agent(위반을 위험 등급으로 정렬)로 재포장. 기준·등급 정의는 **비공개**. [공식문서][마케팅]

### 4.3 LLM이 쓰이는 자리
| 용도 | Ramp | Brex |
|---|---|---|
| 영수증 읽기 | LLM 기반 추출(merchant·date·amount·line items). iOS는 온디바이스: OCR→결정론 날짜/금액 검출→Apple Intelligence로 가맹점명 확인, 세 조건 모두 통과 시 매칭. v2 단일 LLM 호출은 "숫자 환각 빈번", 하이브리드 v3가 정밀도 66%→87% | OCR + 검증(3필드 중 2개 일치=verified, 실패 시 "Receipt failed verification" → 정책에 따라 리뷰). "best-effort" 명시 |
| 메모 초안 | 가맹점·거래·과거 코딩·정책·영수증 품목 기반 고신뢰 시 프리필, 애매하면 확인 요청. 홈 화면 메모 제안 선택 시 다른 빈 필드도 채움 | Brex Assistant가 영수증·캘린더·거래로 메모 작성(auto-pilot 기본 ON), "Added by Brex Assistant" 라벨과 피드백 폼. 두 번째 LLM이 "compliance judge"로 AI/사람 작성 메모 모두 검사(2차 자료) |
| 정책 Q&A | SMS/Slack/이메일로 직원 질문 응답 | Slack에서 응답(◆ 기호로 AI 표시) |
| 가맹점 분류 | 사용자 신고 → RAG 에이전트(임베딩 후보 K개, 행동 3종 고정, 유효성 검사 후 재시도) <10초, 거절 시 두 번째 LLM이 평문으로 사유 재작성. 약 1/4 거절, LLM judge 기준 99% 개선 | ML 모델(비공개) |
| GL 코드 | triplet loss 거래 임베딩으로 유사 기코딩 거래 검색 | "99.7% GL coded" (마케팅) |
| 모델 | "best LLMs available", 자체 게이트웨이 Ramp Router(Thompson sampling 라우팅) | 2023 OpenAI → 2025 Bedrock/Claude, 자체 LLM Gateway(2023-03) (2차) |

## 5. 피드백

- **심사자 → 모델**: Ramp 공식 문서는 override·👍👎·예외 결정이 "감사 로그에 기록되고 시스템 개선에 쓰이며 정책 편집기 인사이트에 반영", 정책 제안 자동 노출은 "coming soon". 재학습 주기·방식은 **미기술**. 기술 블로그는 더 솔직하다: **"finance 팀은 종종 관대하다 — 사용자 승인을 정답으로 쓰면 LLM이 너무 느슨해진다."** 그래서 사용자 행동을 ground truth로 쓰지 않고, 제품·엔지니어·디자인이 모이는 **주간 라벨링 세션**으로 golden set을 만들며(자체 Streamlit 라벨링 도구), 사용자가 신고한 오류는 **검증 후** 테스트 케이스로 넣는다. [공식문서][기술블로그][2차]
- **심사자 → 정책**: 출력에 동의하지 않으면 **정책 문서를 고치라**는 설계. 모델이 아니라 정책 텍스트가 조정 지점. 정책 버전이 각 판정에 기록된다. [기술블로그][공식문서]
- **사용자 → 가맹점 사전**: "Report incorrect merchant info"가 RAG 에이전트를 트리거하고 결과가 같은 가맹점의 다른 거래에도 적용될 수 있다. 가맹점 품질 개선은 이 경로로 돈다. [공식문서][기술블로그]
- **사기 모델**: 라벨(차지백 등)이 몇 주 늦게 도착. SMS "Yes" 확인이 라벨로 쓰이는지는 **미기술** ⚠️. [기술블로그]
- **Brex**: "피드백으로 더 정확해진다", "하지 말라고 한 행동은 반복하지 않는다"는 마케팅 문구만 있고 메커니즘 공개 없음. Brex Assistant 메모 피드백 폼 존재. [마케팅][공식문서]
- **Ramp Risk Ops(결제 리스크, 카드 아님)**: 운영자가 티켓마다 구조화 피드백 → 1,000+ 건 벤치마크(에이전트 도구 호출 경로·운영자 일치·실제 리스크 결과 태깅) → 새 설정은 **shadow mode**로 실거래에 먼저 돌림, 자율 결정은 "감사 가능한 모델 + 승인된 정책" 안에서만. 카드 감사와 다른 도메인이지만 피드백 운영 설계의 참고 사례. [기술블로그]

## 6. 검증·수치

| 수치 | 출처 | 비고 |
|---|---|---|
| Policy Agent: 수동 리뷰 85% 감소, 99%+ 정확도, 15x 더 많은 위반 포착, 10~15%만 에스컬레이션 | [마케팅] Ramp 발표 2025-07 | 방법론·분모 미공개 |
| 승인의 65% 이상을 에이전트가 완전 처리 | [기술블로그] Ramp | 자가 보고 |
| 사기 모델: 사기 금액 +32%(동일 플래그 예산), AP +12~14%, 첫 사기 거래 +40%, 중앙값 54ms | [기술블로그] Ramp 2026-10 | 내부 오프라인/온라인 비교, 외부 검증 없음 |
| iOS 영수증 매칭 정밀도 87%, 재현율 "2배 이상"(절대값 미공개) | [기술블로그] Ramp 2026-04 | 벤치마크 자체 구성 |
| 가맹점 수정 에이전트: 99% 개선(LLM judge), 재신고 <10%, 거절 ~25% | [기술블로그] Ramp 2025-06 | 평가자가 LLM |
| Brex: 월 300시간/기업 절감, $18M+ 차단, 영수증 140만·메모 100만 생성, 270만 자동승인 | [마케팅] Brex 2023-09 보도자료 | 누적 수치 |
| Brex: 99.7% GL coded, 99% automated, 98% compliance, 준수율 70%→90% 중반 | [마케팅][2차] | 분모 불명 |

**제3자 실측은 없다.** Ramp 기술 블로그 수치는 방법이 적혀 있어 재현 가능성은 있으나 외부 검증은 아니다. 정부 감사 보고서(05)·영국 ATRS(06)처럼 독립 측정된 적중률은 두 회사 모두 없다.

## 7. 구조적 한계 — "카드를 잠그면 되지 않나"에 대한 답

승인 시점에 **막을 수 있는 것**: 특정 MCC(주류·도박·정치), 특정 가맹점 디스크립터, 건당/주기 금액 초과, 날짜 이후 사용, 가상카드 전용, 회사 한도 초과, 도난 패턴. 이것들은 네 필드(가맹점·MCC·금액·위치)와 카드 상태만으로 결정 가능하다.

승인 시점에 **구조상 막을 수 없는 것** — 입력 필드에 그 정보가 없기 때문이다:
1. **허용 가맹점에서의 사적 사용**: 허용 카테고리 식당에서 가족 저녁. 디스크립터·MCC·금액·위치가 모두 정상. 참석자·목적은 결제 뒤 메모로만 들어오고, 메모는 사용자가 쓴다(Ramp·Brex 모두 LLM이 **초안을 대신 써 주기까지** 한다 — 사적 사용자에게는 편의가 된다).
2. **업무처럼 보이는 가맹점의 개인 사용**: 주말 마트, 집 근처 주유소, 개인 Amazon 주문. Weekend Spend 플래그는 요일만 보고, 위치 플래그는 Ramp 목록에 없다.
3. **카드 대여**: 동료·가족이 쓴 거래는 소유자 패턴에서 벗어나면 사기 모델이 잡을 수 있지만, 동일 도시·유사 가맹점이면 정상 시퀀스다. 모델은 "누가 들고 있는지"를 알 수 없다.
4. **한도 아래 쪼개기**: Max expense amount는 건당이다. Ramp Policy Agent는 "최근 이력을 컨텍스트로 쓸 수 있다"고 하나 공식 문서는 "거래별 평가, 다건 비교로 행동 분석은 안 함"이라고도 적어 ⚠️ 상충. 중복·쪼개기 전용 플래그는 Ramp Policy Flags 목록에 없다.
5. **예산 안의 접대, 잘못된 참석자**: 금액·카테고리 모두 정책 내. 참석자 필드가 있어도 입력값의 진위는 영수증·메모 어디에도 없다.
6. **가맹점 식별 자체의 오류**: 같은 벤더의 복수 디스크립터, MCC 오설정(호텔 안 식당), 자체 분류 ML의 오분류를 두 회사 문서가 모두 인정한다. 차단 룰이 정확할수록 **정상 거래 오거절**이 늘어 Brex는 "MCC는 플래그로 쓰라"고 권한다. 즉 사전 차단은 **보수적으로밖에 못 쓴다**.
7. **라벨 지연과 희소성**: 사기 라벨은 몇 주 늦고, 임직원 사적 사용은 사기 라벨에 없다. 사용자 승인 기록은 "관대해서" 정답이 아니다. 결국 **사람이 따로 라벨링**해야 하고, Ramp도 그렇게 한다.

그래서 Ramp 자신도 ①차단 → ②수집 → ③정책 평가 → ④검토 큐의 **사후 흐름을 통째로 유지**한다. 사전 통제는 사후 감사를 대체하지 않고, 사후 감사가 볼 **분모를 줄인다**.

**우리와의 차이**:
- **발급사가 아니다**: 우리는 카드사 승인내역 엑셀을 받는다. ①은 아예 없고, ②의 영수증·메모 자동수집도 카드사 앱 밖이라 없다. 우리가 받는 데이터는 Ramp가 승인 시점에 보는 네 필드 + 승인일시 + 할부·취소 정도다 — 즉 **Ramp가 "이것만으론 사적 사용을 못 막는다"고 한 바로 그 데이터**로 사후 감사를 해야 한다. 거꾸로, 그 네 필드만으로 할 수 있는 것(주말·심야·휴일·지역·금액 분포·반복·쪼개기)에 집중해야 한다는 뜻이다.
- **MCC 품질**: 미국은 가맹점이 단말기에 MCC를 설정하고 네트워크가 4자리 코드를 그대로 전달하며, 그래도 두 회사가 오분류를 인정한다. 한국 카드사 승인내역의 업종코드/업종명은 카드사별 체계가 다르고 ⚠️ 가맹점 사업자번호가 함께 오는 경우 명칭 정규화에 유리할 수 있다(미확인). MCC 기반 "Blocked Items" 같은 룰을 그대로 옮기면 안 되고 **카드사별 업종 매핑표**가 선행돼야 한다.
- **한국 부재**: Ramp는 2026 Marqeta로 호주·일본·싱가포르·브라질·멕시코 로컬 발급 확장 중, 한국 없음. Brex도 없음. [2차]

## 8. 우리에게 주는 것

**가져올 것**
- (a) **룰 = 데이터**: 카드 단위 허용/차단 카테고리·금액·요일·시간이 전부 설정 필드다. 우리 `rules/*.yaml`도 "룰 1개 = 조건 + 임계치 + 설명문"으로 두고 코드가 아닌 데이터로 조정. Brex의 "차단(사전) vs 플래그(사후)" 구분처럼 우리 룰에도 **경고/위반 2단계**를 두되, 모두 플래그다.
- (b) **결제 직후 메모 요청 UX**: Ramp SMS "영수증 필요 → 회신 텍스트 = 메모", Brex SMS/WhatsApp/Slack 회신. 우리는 카드사 밖이라 실시간은 불가하나, 월별 승인내역을 올린 직후 **의심 거래만** 사용자에게 "용도·참석자" 질문을 발송하는 배치형 변형은 가능. 정보가 없으면 못 판정한다는 사실을 제품이 인정하는 방식.
- (c) **영수증 매칭 규칙**: 가맹점·금액·날짜 3필드, Brex는 2/3 일치=verified, Ramp iOS는 3/3 필수. 숫자 환각 때문에 **금액·날짜는 결정론 검출, 가맹점명만 LLM** — 우리가 영수증 OCR을 넣을 때 그대로 적용.
- (d) **예외만 검토 + autonomy slider**: "금액 X 초과 전부 사람" ↔ "의심 건만 사람"을 윤경팀이 고르게. 우리 임계치 분리(`thresholds.yaml`)와 결합.
- (e) **"왜 플래그됐나" 문장**: 숫자 확신도 대신 **참조 정책 조문 + 근거 bullet + 정책 버전**. Ramp가 확신도 점수를 "재현 불가"라며 버린 결정은 우리 점수 표기 방식(03 §8.1 A항)에 반영할 것 — 점수는 정렬용, 설명은 조문·피처값으로.
- (f) **"모르겠다"를 출력으로**: Requires review를 오류가 아닌 정상 분기로 두고, 그 비율을 "컨텍스트 부족" 선행지표로 모니터링.
- (g) **라벨링 운영**: 사용자 승인 기록을 정답으로 쓰지 말고, 주간 라벨링 세션 + 신고 오류의 검증 후 테스트화. 가맹점 오분류 신고 → 같은 가맹점 다른 거래 일괄 반영.
- (h) **금액 가중 손실**: 사기 모델 개선분의 대부분(29/32pt)이 손실함수 가중만으로 나왔다. 우리 모델도 금액 가중을 실험 1순위로 — 단 03의 교훈대로 횟수·패턴 축은 별도 유지.

**피할 것**
- (a) 99% / 15x / 85% 같은 **벤더 자가 수치**를 우리 목표치나 비교 기준으로 인용.
- (b) 사용자 승인/반려 클릭을 그대로 학습 라벨로 사용(Ramp가 명시적으로 경고).
- (c) 미국 MCC 룰(Blocked Items 등)을 한국 업종코드에 매핑표 없이 이식.
- (d) LLM이 메모를 **대신 써 주는** 기능 — 사적 사용의 흔적을 지우는 쪽으로 작용할 수 있다. 우리는 질문만 하고 답은 사용자가 쓰게.
- (e) 사전 차단이 있다는 이유로 사후 감사 범위를 줄이는 논리. Ramp조차 ④검토 큐를 유지한다.

## 9. 출처

- [공식문서] Ramp, Setting up controls on Ramp cards and funds — https://support.ramp.com/hc/en-us/articles/360051065813-Setting-up-controls-on-Ramp-cards-and-funds
- [공식문서] Ramp, Blocking or restricting merchants on Ramp — https://support.ramp.com/hc/en-us/articles/4402982321683-Blocking-or-restricting-merchants-on-Ramp
- [공식문서] Ramp, Transaction declines(거절 사유 11종) — https://support.ramp.com/hc/en-us/articles/360056379274-Transaction-declines
- [공식문서] Ramp, Correcting transaction merchant and date information(MCC는 단말기 설정, Ramp 변경 불가) — https://support.ramp.com/correcting-transaction-merchant-and-date-information-on-ramp
- [공식문서] Ramp, Ramp's fraud protection procedures — https://support.ramp.com/hc/en-us/articles/9550192601875-Ramp-s-fraud-protection-procedures
- [공식문서] Ramp, Automatically flag transactions with policy flags — https://support.ramp.com/automatically-flag-transactions-with-policy-flags
- [공식문서] Ramp, Policy Agent Overview — https://support.ramp.com/hc/en-us/articles/44072387128979-Policy-Agent-Overview
- [공식문서] Ramp, Flagging transactions: accidental purchase, fraud, out of policy — https://support.ramp.com/flagging-transactions-accidental-purchase-fraud-and-out-of-policy/
- [공식문서] Ramp, Submitting receipts, memos, and accounting(SMS 회신=메모) — https://support.ramp.com/hc/en-us/articles/360042588454-Submitting-receipts-and-memos-for-your-Ramp-card
- [공식문서] Ramp, Gmail integration: Set up for admins — https://support.ramp.com/hc/en-us/articles/4469891766803
- [공식문서] Ramp, Receipt auto-capture(벤더 목록, Amazon 로그인 대행) — https://support.ramp.com/hc/en-us/articles/40334371635219-Ramp-Receipt-Auto-Capture
- [공식문서] Ramp, Automate receipts and expense requirements — https://support.ramp.com/automate-receipts-and-expense-requirements
- [공식문서] Ramp Community, New on Ramp: AI Agents (2025-07-15) — https://community.ramp.com/t/new-on-ramp-ai-agents/956
- [기술블로그] Ramp Builders, Putting a Transformer Inside Every Card Authorization (2026-10-07) — https://builders.ramp.com/post/sequence-aware-card-fraud
- [기술블로그] Ramp Builders, How To Build Agents Users Can Trust (2025-07-10) — https://builders.ramp.com/post/how-to-build-agents-users-can-trust
- [기술블로그] Ramp Builders, How Ramp Fixes Merchant Matches with AI (2025-06-16) — https://builders.ramp.com/post/fixing-merchant-classifications-with-ai
- [기술블로그] Ramp Builders, From RAG to Richness: Industry Classification (2025-01-15) — https://builders.ramp.com/post/industry_classification
- [기술블로그] Ramp Builders, Improving Retrieval with Transaction Embeddings (2024-08-13) — https://builders.ramp.com/post/transaction-embeddings
- [기술블로그] Ramp Builders, Automating Receipt Collection: Apple Intelligence (2026-04-13) — https://builders.ramp.com/post/apple-intelligence-receipt-matching
- [기술블로그] Ramp Builders, Agentic Risk Operations (2026-06-30) — https://builders.ramp.com/post/agentic-risk-operations
- [기술블로그] Ramp Builders, Online Learning for Cost-Efficient LLM Routing (2026-07-20) — https://builders.ramp.com/post/thompson-sampling-model-routing
- [마케팅] Ramp, Introducing Ramp Agents (2025-07-09; 15x·99%·10–15%) — https://ramp.com/blog/ramp-agents-announcement
- [마케팅] Ramp, Announcing merchant restrictions (2021-07-12) — https://ramp.com/blog/announcing-merchant-restrictions
- [마케팅] Ramp Intelligence — https://ramp.com/ai
- [2차] ZenML LLMOps DB, Ramp: Agentic Workflow Automation for Financial Operations(강연 요약: 주간 라벨링, 사용자 결정은 정답 아님, autonomy slider 유래) — https://www.zenml.io/llmops-database/building-production-scale-ai-agents-for-financial-automation
- [공식문서] Brex, Brex merchant categories(MCC+ML, 스펜드 리밋 우선, "플래그로 쓰라") — https://brex.com/support/brex-merchant-categories
- [공식문서] Brex, Declines and failed expenses — https://www.brex.com/support/declines-and-failed-expenses
- [공식문서] Brex, Policy Rule Builder(조건·액션·우선순위) — https://www.brex.com/support/policy-rule-builder
- [공식문서] Brex, Flagged expenses(리스크 룰 + ML + 정책) — https://www.brex.com/support/flagged-expenses
- [공식문서] Brex, Receipts for expenses(채널, 2/3 일치, 검증 실패) — https://www.brex.com/support/receipts-for-expenses
- [공식문서] Brex, Brex Assistant — https://www.brex.com/support/brex-assistant
- [공식문서] Brex, Set MCC controls at the policy level (2026-07-14) — https://www.brex.com/product-announcements/set-mcc-controls-at-the-policy-level
- [공식문서] Brex, Build more powerful and dynamic policy rules (2026-05-19) — https://www.brex.com/product-announcements/new-policy-rule-builder
- [마케팅] Brex, Powerful AI for expense reviews (2024-02-29; 'vodka') — https://www.brex.com/product-announcements/powerful-ai-for-expense-reviews
- [마케팅] Brex, Guided reviews (2024-02-29) — https://www.brex.com/product-announcements/guided-reviews
- [마케팅] Brex, Agents on Brex / Intelligence (2025 Fall Release) — https://brex.com/intelligence
- [마케팅] Brex, Brex AI — https://brex.com/platform/brex-ai
- [마케팅] Brex 보도자료, Brex gives every employee an expense assistant (2023-09-19) — https://brex.com/journal/press/brex-gives-every-employee-an-expense-assistant-with-ai
- [2차] ZenML LLMOps DB, Brex: AI-Powered Financial Assistant(LLM Gateway 2023-03, Bedrock/Claude, compliance judge LLM; 원자료 YouTube) — https://www.zenml.io/llmops-database/ai-powered-financial-assistant-for-automated-expense-management
- [2차] SEC, Capital One 8-K (2026-01-22 Brex 인수 합의) / 10-Q (2026-04-07 완료) — https://www.sec.gov/Archives/edgar/data/927628/000119312526019543/d97758d8k.htm , https://www.sec.gov/Archives/edgar/data/0000927628/000092762826000089/cof-20260630.htm
- [2차] Visa 개발자 커뮤니티, ISO 8583 가맹점 필드 매핑(MCC=DE18, 가맹점명/위치=DE43) — https://community.developer.visa.com/t5/Implementation-API-Sample-Code/Mapping-of-ISO8583-merchant-related-fields-in-MerchantSearch-API/td-p/15563
- 미발견: Brex 엔지니어링 블로그의 사기·ML·데이터 플랫폼 글(채용 공고·인터뷰 가이드만 존재), Ramp SMS 확인이 사기 라벨로 쓰이는지, Ramp Policy Agent의 다건 비교 범위(문서 상충), Brex 리스크 룰 전체 목록, 두 회사의 한국 가용성.
