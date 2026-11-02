# 03. Oversight Systems — Insights On Demand / Spend Insights / Concur Detect by Oversight

> 조사일 2026-11-02. 출처 등급: [특허] [조달문서] [공식문서] [마케팅] [2차]. 확인 못 한 항목은 **(미확인)** 표기.
> 주의: 과제 지시에 있던 "US 11514533"은 Google Patents 확인 결과 **Mastercard의 MCC 오분류 특허**이며 Oversight와 무관하다. Oversight 명의 특허는 US 7,937,319 (Knowledge Base, 2011 등록)와 US 8,170,902 (Case Management, 2012 등록) 두 건이 확인됐고, 둘 다 2004~2006년 출원이다. 현재 "AI 모델" 구조는 특허가 아니라 마케팅 페이지로만 확인된다.

## 1. 한 줄 정의

Oversight는 2003년 설립된 애틀랜타 SaaS로, 기업·정부의 **T&E·P-card·AP 거래 100%를 사후(및 일부 사전) 분석**해 "Insight"(분석 모듈)별 Exception을 만들고, 이를 confidence × 잠재 금액영향으로 우선순위화해 감사자의 Workbench 큐에 넘기는 **감사자용 예외 관리 플랫폼**이다. 미 국방부 GPC 전체(Army AFARS Appendix EE 기준)와 SAP Concur 내장 상품(Concur Detect by Oversight)이라는 두 개의 대형 유통 경로를 가진다. [조달문서][공식문서]

## 2. 데이터 입력

- **소스**: 공식 Processing Layer 페이지는 "ERP, T&E, P-Card, Procure-to-Pay, AP automation, payments, procurement, vendor, accounting systems"를 **"APIs, flat files, direct feeds"** 로 받는다고만 적는다. 파트너 페이지에는 SAP Concur·SAP·Oracle·Oracle iExpense·Chrome River·Certify·Rydoo(경비), Amex·Citi·JP Morgan·Bank of America·US Bank·Visa·Mastercard(카드) 로고가 있으나 **연동 방식은 로고별로 기술돼 있지 않다.** [공식문서]
- **정부 경로**: Army에서는 발급 은행(US Bank → SmartPay 3)이 IOD를 "servicing bank의 데이터 마이닝 도구"로 제공하므로, 카드 거래 피드는 은행 측에서 들어온다. 사용 가이드도 은행이 배포한다. [조달문서]
- **Concur 경로**: Concur Expense Standard/Professional의 workflow 안에 통합되어 경비 보고서를 결제 전·후로 받는다. 구현 일정은 9~12주(FR 브로슈어). [공식문서]
- **필수 전제**: 영수증 이미지·거래·정책 코드가 소스 시스템에 이미 구조화돼 있어야 한다. 소스 시스템에 없는 데이터(예: 결재 라인, 직원 조직 정보)는 "enrich"한다고만 쓰여 있다.
- **대량 과거 파일 적재 가능 여부**: **(미확인)** — 어떤 공식 문서도 historical bulk load를 언급하지 않는다. 2014·2015 Spend Analysis Report가 수천만 건을 분석했으니 가능은 하다고 추정되지만 고객이 CSV를 올리는 셀프 서비스 경로는 문서화돼 있지 않다. AWS Marketplace 리뷰에 "데이터 다운로드·업로드에 수 시간" 언급이 있어 파일 기반 배치 경로가 실존함은 짐작된다. [2차]

## 3. 구성요소와 흐름

특허 두 건과 현행 문서를 합치면 구성은 15년 동안 거의 같다.

```
 소스(ERP/T&E/카드 피드/영수증)
        │  API / flat file / direct feed
        ▼
 ┌──────────────┐   정책을 XML "Frame"(=현행 Insight)으로 보유
 │ Knowledge    │   Frame 안에 Indicator(논리식 + confidence) 다수
 │ Base         │
 └──────┬───────┘
        ▼
 ┌──────────────┐   Frame을 순차 실행, Indicator 참 → Exception 생성
 │ CORE 룰·추론 │   Exception = {frame, 설명, confidence, 잠재/기대 impact}
 │ 엔진 (+ML)   │   Priority = confidence × nominal impact
 └──────┬───────┘   Entity(직원·벤더)의 Wariness += priority  ← 반복자 추적
        ▼
 ┌──────────────┐   Exception 묶음 → Case, 상태: Detected/Under Review/
 │ Workbench    │   Dismissed/Fixed, 담당자 배정, 증거 locker, 활동 로그
 │ (Case Mgmt)  │   저위험은 자동 종결(auto-close/auto-approve)
 └──────┬───────┘
        ▼
 Disposition → (Concur) 직원 outreach / (Army) Finding·Corrective Action
        ▼
 회수(reimbursement, vendor credit) · 리포트
```

- **Insight**: Oversight가 "룰이 아니라 insight를 만든다"고 말하는 단위. 특허의 Frame에 해당하며 "Base frame(공통) + Custom frame(고객 수정)" 구조. [특허 US7937319][공식문서 FR 브로슈어]
- **Exception → Case**: 특허에서 사용자가 복수 Exception에 case number를 부여. Army IOD는 **룰 하나가 깨질 때마다 케이스 1건**이 시스템 생성된다. [특허 US8170902][조달문서]
- **IOD 케이스 수명주기 (AFARS Appendix EE 11-4)** [조달문서]:
  1. IOD가 Tier 1(DoD 전체 필수)·Tier 2(필수지만 지역 조정 가능) 룰로 거래 검사, 위반 시 케이스 생성 → **Billing Official(BO)** 에 매일 배정.
  2. BO가 카드소유자 서류 검토 후 IOD의 BO DM Case Questionnaire 입력. **청구주기 종료 후 15일** 내 완료, 미완 시 A/OPC가 managing account 정지 가능.
  3. IOD가 **Level 4 A/OPC** 에 자동 이관. A/OPC가 코멘트·Finding 선택·종결. **30일** 내, 미완 시 OA/OPC(Level 3)가 계정 정지 의무.
  4. Finding/Determination(Table 11-1, 이미지로만 제공되어 항목 **미확인**)과 Corrective Action(Table 11-2, 11항목: 수사기관 이관, 지휘계통 이관, 프로그램 제외, 환급, 공식/비공식 상담, 카드 정지·해지, 재교육, 행정불일치 해소, 외부사기 신고, 벤더 크레딧·분쟁) 기록. 5개 표준 징계 카테고리로 분류.
  5. Tier 2 **auto-closed 케이스의 1%를 IOD가 무작위 재개("1% Random Reopen")** 해 사람에게 배정. A/OPC는 추가 거래를 임의 플래그 가능.

## 4. 판단 방식

- **특허가 기술하는 점수 산출** [특허 US7937319 / US8170902]: Indicator마다 confidence(예: voucher 중복 0.3)와 Estimated Impact(거래액 또는 고정값)가 있다. 한 Frame 안에서 여러 Indicator가 참이면 confidence를 "단순 누적이 아닌 통계적으로 적절한 방식"으로 합성한다(예시에서는 0.80까지 누적, 음수 Indicator는 감점). **Priority = confidence × nominal impact**(예: $1,000 × 0.44 → 440). 이 priority가 Entity의 **Wariness**에 더해져 벤더·직원 단위 누적 의심도가 된다 — 현행 "Repeat Offenders"(2018 출시)의 원형이다. 설명은 Indicator의 human-readable summary를 Exception에 붙여 생성한다.
- **"confidence × impact" 우선순위**: FR 브로슈어도 "exceptions basées sur la confiance et l'impact potentiel"로 동일하게 쓴다. 이 두 축이 20년간 유지된 핵심이다. [공식문서]
- **peer group(카테고리×지역×계절)**: **특허에는 없다.** 2016 Sourcing Innovation 리뷰는 "statistical, clustering, data mining, break point, rule-based" 혼합과 "직원 간 비교"를 언급하고, 현행 Intelligence Layer 페이지는 "behavioral analysis across employees, vendors", "Behavioral trends across teams"라고 쓴다. 구체 분할 축은 **(미확인)**. [2차][마케팅]
- **현행 모델 레이어**(마케팅 기술): expert system(정책 로직) + "20년 감사자 판정 라벨로 학습한 global risk/fraud model" + document intelligence(영수증, "fake receipt 90%+") + behavioral analysis. "Scores every finding by how likely it is to be real" — 즉 likelihood 점수가 confidence 역할. [마케팅]
- **라우팅**: 점수·역할·임계값·반복 행동으로 Workbench에 배정. Concur Detect는 고위험만 감사자에게, 저위험은 자동 승인. Actions(2025~)는 "approved low-risk items within threshold"를 자동 종결하고 직원에게 영수증·설명 요청을 자동 발송하되 "not open-ended automation"이라 명시. [공식문서][마케팅]
- **Army의 판단**: 룰(Tier 1/2)이 전부이고 점수 기반 우선순위는 AFARS에 없다. 판단은 BO → A/OPC 두 사람의 수동 조사다. [조달문서]

## 5. 피드백

- **Disposition**: 특허 상태값 Detected / Under Review / Dismissed / Fixed. Concur Detect는 감사자가 Workbench에서 직원과 직접 소통하고 전 과정이 audit trail로 남는다. Army는 Finding + Corrective Action 코드(11종) 선택. [특허][공식문서][조달문서]
- **무작위 재감사**: Army 1% Random Reopen이 유일하게 문서화된 품질 통제. 이는 Oversight 기능이 아니라 **조달 요구사항**이다. 재개 결과가 룰을 바꾸는지는 "IST가 Tier 2 데이터 추세를 검토해 방법론 변경을 고려"로만 적혀 있다. [조달문서]
- **재학습 여부**: 특허에는 disposition이 분석으로 되돌아가는 경로가 **없다**(관리자가 Frame을 수동 편집). 현행 마케팅은 "learns from what your team decides… retraining on a controlled cadence with human oversight"라고 하지만 주기·범위는 **(미확인)**. 2018 보도자료도 "guided machine learning… from human interaction"으로 표현만 한다. 고객이 할 수 있는 조정은 **exclusion 추가/삭제, keyword 리스트, Tier 2 tailoring** 수준으로 문서화돼 있다. [마케팅][공식문서]

## 6. 검증·수치

| 수치 | 출처 종류 | 비고 |
|---|---|---|
| 5% 직원이 사기 82% (2014, 1천만 건) | [마케팅] 자사 보고서 | 2015 보고서에선 "10% 여행자가 거의 전부", 2019 보도엔 "0.4%가 25%" — 수치가 보고서마다 바뀜 |
| 거래의 약 2% 비준수, 경비보고서의 1.3%만 고위험 (2015, 3,200만 경비+1,600만 P-card) | [마케팅] 자사 보고서 | 분모가 "거래" vs "보고서"로 다름 |
| 95%+ true risk detection, 96%+ 케이스 자동 처리 정확, 70% 감사 공수 절감, 3.5% 지출 절감 | [마케팅] 홈페이지 | 방법론 미공개 |
| Southwest $60K 중복결제 회수(1년차) | [마케팅] 고객사례 | 단일 사례 |
| G2 4.3/42건, AWS Marketplace 4.4/50건 | [2차] | 리뷰 플랫폼 |
| Gartner Cool Vendor 2016 | [2차] | Gartner는 비추천 고지 |
| **정부 실측** | — | AFARS는 절차만 규정. IOD의 적중률·재개 케이스 번복률을 공개한 DoD IG/GAO 문서를 **찾지 못함 (미확인)** |

제3자 검증 수치는 **없다**. 모든 정확도는 벤더 자가 보고다.

## 7. 구조적 한계

1. **연동에 묶인 입력**: 소스 시스템(Concur, 은행 피드, ERP)이 데이터를 구조화해 줘야 분석이 시작된다. 소스 밖 데이터(이메일, 내부 결재, 한국형 법인카드 승인내역 포맷)는 enrichment 대상이 아니다. 리뷰에 "Concur → Oversight 데이터 완전성 문제", "다운로드·업로드 수 시간" 호소가 있다. [2차]
2. **닫힌 Insight 카탈로그**: 고객은 exclusion·keyword·임계값만 조정한다. "insights and exceptions that could be customizable more", "expense-type subcategory별 threshold 설정 불가" 리뷰. 특허 구조상 Frame 작성은 벤더 데이터 과학자의 일이다. [2차][특허]
3. **공개 인정된 false positive**: 리뷰 다수가 "ultimately allowable인데 플래그", "시스템 버그로 중복 exception"을 적고, 벤더는 G2에서 "models are built to surface potential risk"로 응답. "insights를 fine-tune하는 데 시간이 걸렸다"는 초기 설정 부담도 반복된다. [2차]
4. **자동 종결 위험**: 같은 경비 라인의 여러 exception 중 하나만 감사자에게 보내고 나머지를 자동 종결한다는 리뷰. Army가 1% 무작위 재개를 **외부에서** 강제해야 했다는 점이, 자동 종결의 누락 위험을 제품 자체가 통제하지 못함을 시사한다. [2차][조달문서]
5. **점수 = confidence × 금액**: 금액이 작은 반복 위반(소액 쪼개기, 개인 사용)은 priority가 낮게 나와 Wariness 누적에 의존한다. 금액 축이 없는 위반(사적 용도 추정)은 impact를 임의값으로 정해야 한다. [특허]
6. **한국 부재·데이터 상주**: 파트너에 국내 카드사·ERP 없음. Concur Detect 가용 지역 목록(APAC 22개국)에 한국 포함 여부 **(미확인)**. 프로덕션은 애틀랜타 코로케이션, DR은 미국 내 다른 지역, EU 로그인(eu.detect.oversight.com) 존재. 한국 상주 옵션 없음. SOC 2 Type 2·SSAE-18, PCI는 자가 인증. [공식문서]
7. **사후 중심**: 특허·Army 흐름 모두 결제·청구 후 분석. Concur Detect만 "pre-payment" 옵션. 승인 시점 차단은 범위 밖. [조달문서][공식문서]

## 8. 우리에게 주는 것

- **가져올 것**: (a) Indicator별 confidence + Estimated Impact → Priority, Entity 단위 Wariness 누적 — 단순하고 설명 가능하며 20년 버틴 구조. (b) 룰 1개 = 케이스 1개, 2단계 검토자, 15/30일 SLA와 미이행 시 계정 정지라는 **운영 규율**이 탐지보다 효과를 좌우한다는 Army 설계. (c) 자동 종결분의 **무작위 재개 샘플**을 제품 기본값으로 내장. (d) Corrective Action을 코드화해 사후 통계를 가능하게 한 11항목 리스트.
- **피할 것**: (a) 금액 가중만으로 우선순위를 매기면 소액 반복 위반이 묻힌다 — 횟수·패턴 축을 별도로. (b) Insight 카탈로그를 닫아두고 exclusion만 열면 "너무 경직" 리뷰가 반복된다. (c) disposition이 모델로 되돌아가는 경로를 마케팅 문구가 아닌 **관측 가능한 메커니즘**으로 만들 것. (d) 연동 전제 입력만 받으면 국내 중소 고객의 승인내역 엑셀을 못 받는다 — 대량 과거 파일 적재를 1급 경로로.

## 9. 출처

- [특허] US 7,937,319 B2 "Methods and systems for compliance monitoring knowledge base" (출원 2006-01-31, 등록 2011-05-03, Oversight Systems) — https://patents.google.com/patent/US7937319B2/en
- [특허] US 8,170,902 B2 "Methods and systems for compliance monitoring case management" (등록 2012-05-01, 만료 2026-06) — https://patents.google.com/patent/US8170902B2/en
- [특허·참고] US 11,514,533 B2 — Mastercard "MCC-misclassified merchant" 특허. **Oversight 무관**, 오인 방지용 기록 — https://patents.google.com/patent/US11514533
- [조달문서] AFARS Appendix EE 11-3 "Insights on Demand" — https://www.acquisition.gov/afars/11-3.-insights-demand
- [조달문서] AFARS Appendix EE 11-4 "Data Mining Case Review and Closure" (Tier 1/2, 1% Random Reopen, Table 11-2/11-3) — https://www.acquisition.gov/afars/11-4.-data-mining-case-review-and-closure
- [조달문서] AFARS 3-5 "MasterCard Insights on Demand (IOD)" — https://www.acquisition.gov/afars/3-5.-mastercard-insights-demand-iod
- [조달문서] AFARS 2-6 Billing Official duties — https://www.acquisition.gov/afars/2-6.-primary-and-alternate-level-5-billing-official-duties-and-responsibilities
- [공식문서] SAP Concur, "Concur Detect par Oversight: Commençons!" FR 온보딩 키트 PDF(2022) — https://www.concur.fr/sites/fr/files/acn/sap_concur_detect_infographic_final_fr-fr_interactive.pdf
- [공식문서] SAP Concur App Center listing, Concur Detect by Oversight — https://www.concur.com/app-center/listings/6009d8f92d2d5b0015e88b63
- [공식문서] Concur Community, Product Guide for Admins(PDF 본문은 로그인 필요, **미열람**) — https://community.concur.com/t5/Getting-Started/Concur-Detect-by-Oversight-Product-Guide-for-Admins/ba-p/36876
- [공식문서] Oversight Processing Layer — https://www.oversight.com/ai-processing-layer
- [공식문서] Oversight Partners & Integrations — https://www.oversight.com/platform/partners-integrations
- [공식문서] Oversight Hosting Guide(Exhibit 1) / Data Management & Security Policy(Exhibit 2) — https://www.oversight.com/service-guide-exhibit-1 , https://www.oversight.com/service-guide-exhibit-2
- [공식문서/마케팅] Oversight Actions — https://www.oversight.com/oversight-actions
- [마케팅] Oversight Intelligence Layer — https://www.oversight.com/ai-intelligence-layer
- [마케팅] Oversight T&E Monitoring (95%+, 96%+, 70%) — https://www.oversight.com/ai-travel-expense-monitoring
- [마케팅] Oversight P-Card Monitoring — https://www.oversight.com/platform/purchase-card-monitoring
- [마케팅] 보도자료 2014-09-23 Spend Analysis Report Vol.1 (5%/82%) — https://www.oversight.com/news/travel-and-expense-fraud-linked-to-5-percent-of-travelers-according-new-oversight-report
- [마케팅] 보도자료 2015-12-09 Vol.2 (10%, 2%, 1.3%) — https://oversight.com/news/oversight-annual-report-high-risk-spending-linked-to-10-percent-of-business-travelers
- [마케팅] 보도자료 2018-01-09 Repeat Offenders — https://www.oversight.com/news/repeat-offenders-visibility-helps-stop-fraud-compliance-risks
- [마케팅] 보도자료 2011-05-27 / 2012-06-05 특허 공지 — https://www.oversight.com/news/us-patent-awarded-to-oversight-systems , https://oversight.com/news/oversight-systems-granted-patent-for-compliance-monitoring-case-management
- [2차] Sourcing Innovation, "Oversight for more than just your Travel & Expense budget management" (2016-12-06) — https://sourcinginnovation.com/wordpress/2016/12/06/oversight-for-more-than-just-your-travel-expense-budget-management/
- [2차] AWS Marketplace 리뷰(50건, 4.4) — https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-zs2767htuncuy
- [2차] G2 리뷰(42건, 4.3; 자동 종결·false positive 인용은 검색 스니펫 기반, 페이지 직접 열람 403 — **인용문 원문 미확인**) — https://www.g2.com/products/oversight-oversight/reviews
- [2차] GAO-02-732 (Army 구매카드, 데이터 마이닝 샘플링) — https://www.gao.gov/assets/a234979.html
- 미발견: Table 11-1 Findings 텍스트, IOD 적중률 정부 실측, historical bulk load 문서, 한국 가용성.
