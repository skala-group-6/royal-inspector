# 02. AppZen Expense Audit — 동작 원리 해부

> 조사일 2026-11-02. 1차 자료 우선(특허·API 문서), 벤더 자료는 [마케팅]으로 표시. 확인 못 한 것은 **(미검증)**.

## 0. 한 장 요약

Concur·Coupa 같은 경비 시스템 위에 얹는 외부 감사 SaaS. 제출된 경비 보고서를 지급 전에 100% 자동 검사해 LOW/MED/HIGH 등급을 매기고, LOW는 자동 승인, 나머지는 감사자 큐로 보낸다.

- **룰이 1차 판정자, ML은 보조.** 영수증 읽기·가맹점 해석·이상치 탐지에 ML을 쓰고, 최종 등급은 룰 결과의 최댓값으로 보인다.
- **설명은 "임계값 20 초과" 같은 템플릿 문장.** 왜 20인지, 어느 규정인지 없다. "신뢰도 낮음"도 MEDIUM에 섞여 들어간다.
- **감사자 판정은 3필드(original/computed/current)로 보존**된다. 좋은 패턴이지만, 그게 모델로 돌아간다는 증거는 특허·문서 어디에도 없다.
- 한계: 경비 보고서(사유·참석자·영수증) 없으면 입력 불가 → 카드 거래 파일만 있는 조직은 못 쓴다 · 사후 일괄 감사 모드 없음 · 가맹점 보강이 Google/Yelp 중심(한국 범위 밖) · 정확도·오탐률 제3자 수치 없음.
- 가져올 것: 판정 3필드 보존 · "해당 없음"까지 남기는 전수 로그 · 중복 탐지 3단 범위(보고서 내/동일인/전사) · 큐를 위반유형·부서로 자르기.

## 1. 한 줄 정의
Concur·Coupa·Workday 등 **경비 시스템에 제출된 Expense Report**를 제출 직후·지급 전에 100% 자동 감사해, 보고서 단위로 LOW/MEDIUM/HIGH 위험을 매기고 LOW는 자동 승인, 나머지는 감사자 큐로 보내는 SaaS. 감사 대상은 "카드 거래"가 아니라 "직원이 작성한 경비 보고서 + 영수증 이미지"다.

## 2. 데이터 입력
- **공급원**: SAP Concur(2-way API), Coupa, Workday(Design Approved), Oracle Fusion, Amadeus Cytric 등 pre-built 커넥터. Concur 페이지 문구: "All data used in AppZen Expense Audit starts with SAP Concur" [마케팅]. 즉 **상위 경비 시스템이 없으면 돌아가지 않는다.**
- **Ingestion API가 요구하는 것** [공식문서]: `PUT /expense-ingestion/reports/{external_report_id}`. 보고서 헤더(금액·통화·국가·제출일·`status`)와 `elines[]` 라인마다 `eltype`(경비유형), `eldate`, `elpaidamount`, `elinetype`(CASH/CREDIT), `elpurpose`(사유, **필수**), `elpersonalflag`, `missingReceipt`(**필수**), `elattendees[]`(참석자 — 필수 루트), `cardTransactionDetails`(MCC/SIC, 가맹점명·도시·국가, 거래ID — 선택), `elimageid[]`(사전 업로드한 영수증 PDF/JPEG/PNG/TIFF). 영수증은 별도 2단계(URL 생성 → 업로드) 후 보고서에 연결.
- **플랫 거래 파일**: CSV/SFTP 경로는 **Master Data(AP용)와 Employee Sync 전용**이라고 명시 [공식문서]. 경비 라인 CSV 업로드·과거 거래 일괄 회고 감사 모드는 문서상 없음. 구현 시 "historical data 수령" 단계는 있으나 형식 미공개 **(미검증)**.

## 3. 구성요소와 흐름

```
[Concur/Coupa/Workday]            ┌──────────── Mastermind 플랫폼 ────────────┐
  보고서 + 라인 + 참석자          │                                           │
  + 카드거래 + 영수증 이미지 ───▶ │ ① 이미지 분리 (한 장에 영수증 N개 → N객체)  │  US11126838
                                  │ ② OCR/필드 추출 (가맹점·금액·일자·통화·품목) │
                                  │ ③ 라인↔영수증 할당 (우선순위 규칙 완화 반복)  │  US11126838
                                  │ ④ 경비유형 온톨로지 분류 + 웹 보강          │  US11321784
                                  │    (Google Places/Yelp/위키 → 가맹점 성격,   │
                                  │     참석자·공직자(PEP)·OFAC 조회)           │
                                  │ ⑤ 룰 모델 ×N  (header-level / line-level)  │
                                  │    + ML 이상치(kNN 거리·범위) + 직원 위험(SVM)│
                                  │ ⑥ 라인·헤더 위험 → 보고서 위험 LOW/MED/HIGH │
                                  └──────┬──────────────────────┬─────────────┘
                                         │ LOW                  │ MED/HIGH
                                   자동 승인 ───▶ 지급        감사자 큐(위반유형·직원그룹·정책·국가별)
                                   (또는 정해진 위반은                  │ 승인 / 반려 / 직원 반송
                                    자동 직원 반송)                    ▼
                                         Webhook: audit_status + auditor_comments ──▶ 경비 시스템
                                         (상태 확정은 고객 측 PUT /external_status 콜백 필요)
```

핵심: **룰 모델(rule_name)이 1차 판정자**이고, ML은 (a) 영수증 읽기·매칭, (b) 가맹점·참석자 해석, (c) 이상치·직원 위험 보조 신호로 들어간다. 2025년부터 AppZen은 이 층을 "ZenLM"(200+개 금융 특화 모델, 2026-10 ZenLM Plus)이라 부르지만 내부 구조 공개는 없음 [마케팅].

## 4. 판단 방식
**(a) 룰은 두 층이다** [공식문서, API 샘플]. 헤더 레벨: `Report Unauthorized Expenses`, `Daily meal limit check`. 라인 레벨(`external_exp_line_id`별): `Expense Age`, `Weekend Expense`, `Amount Verification`, `Amount Verification By Expense Type`, `Non-Conforming Receipt`, `Receipt Verification`, `Merchant Price Check`, `Unauthorized Expenses`, `Duplicate Across Reports`, `Duplicate Within A Report`, `Itemization Verification`, `Merchant Category Check`, 그 외 `Merchant Blacklist Check`(고객이 목록 제공, AppZen 기본 목록 없음), `Manager as an Attendee`. 모든 룰은 모든 라인에 실행되며 "해당 없음"도 LOW로 기록된다.

**(b) 설명은 룰별 템플릿 문장**이다. 샘플 그대로:
- `"Amount for this line is above threshold of 20"`
- `"User entered expense type is verified. Amount (USD 1200.00) and date (01-AUG-20) could not be verified."`
- `" Alcohol was/were detected on receipt."`
- `"Duplicate expense line was detected but the expense types of these lines were not added in audit configuration."`
- `"The transaction date exceeds the expense age threshold but has low confidence."`
- `"Merchant was not detected as anything suspicious, could not find merchant info"`
정책 조문 인용·근거 데이터 링크는 없고, 룰 이름 + 변수 치환 문장. 마지막 두 문장처럼 **신뢰도 낮음·정보 없음도 등급에 섞여 들어간다**(MEDIUM이 "모호함"의 뜻으로 쓰임).

**(c) 등급 합성**. 보고서 `current_risk_level`은 라인·헤더 룰 결과의 **최댓값**으로 보인다(샘플: 라인에 HIGH 3개 → 보고서 HIGH). 가중합·점수화 문서는 없음 **(미검증, 샘플에서 추론)**. 룰별 임계값·위험등급은 고객이 Audit Models Config에서 설정(Appstore 앱은 룰별 Low/Med/High 지정 가능) [공식문서].

**(d) 세 개의 위험 필드 = 감사자 오버라이드 기록**. 모든 룰·보고서에 `original_risk_level`/`computed_risk_level`/`current_risk_level`이 있다. 필드 정의 문서는 없으나, bulk API가 세 필드 각각으로 정렬을 지원하는 점에서 computed=모델 산출, original=최초 공개값, current=감사자 조정 후 현재값으로 읽힌다 **(해석, 미검증)**. 즉 **오버라이드가 등급을 덮어쓰지 않고 나란히 보존**된다.

**(e) 특허가 말하는 매칭·중복** [특허]. US11321784/US11954739(우선일 2013, 등록 2022/2024): 경비 온톨로지로 유형 결정 → 웹 데이터로 가맹점 성격 확인(스타벅스=커피, "bar"가 식당인지 성인업소인지) → **kNN**: 과거 유사 지출 군집과의 k번째 이웃 거리가 임계 초과면 HIGH → **SVM 선형커널**로 직원 Z-score 특징(현금/카드 비율, 영수증 누락액, 주말·오래된 영수증 빈도)에서 직원 위험 HIGH/MED/LOW → 영수증 OCR 금액·일자 대조 → 중복은 "보고서 내 / 한 직원의 여러 보고서 / 직원 집단 전체"에서 사용자 입력+OCR 값으로 검색. 이미지 해시·임베딩 유사도는 **언급 없음**. 엔티티 명 소거는 문자열·토큰·음성 유사도. US11126838(2021): 한 페이지에 여러 영수증 → 객체 분할 → 라인과 다대일 매칭이 생기면 우선순위 제약을 하나씩 풀며 재할당해 1:1 강제. 세 특허 모두 **감사자 피드백 루프 단계가 없다**.

**(f) 사람 개입 지점**: ① 룰·임계값 설정(go-live 전 필수), ② MED/HIGH 큐 검토 → 승인/반려/반송, ③ 등급 수동 조정(current 필드), ④ 모델 튜닝 요청(ExpertCare/CSM 경유). 반려 사유 템플릿 기능은 문서에 없고, 사용자들은 "표준 반송 문구 스프레드시트"를 따로 운영 [2차, Concur 커뮤니티].

## 5. 피드백
- **기록되는 것** [공식문서]: 웹훅 페이로드 `audit_status`(AUTOMATIC/MANUAL × APPROVED/REJECT 4종), `auditor_comments`(자유문), `actioned_by`. 이는 **경비 시스템으로 돌아가는 상태 동기화**이지, 모델 입력이라는 명시는 없다.
- **학습 주장** [마케팅]: Mastermind "Feedback Models learn based on team interactions", ZenLearn "2-3 샘플로 예측 조정", 가짜영수증 모델 "learns from every transaction". Spectrum Brands 사례는 감사자가 "과거 승인/반려 이력으로 모델을 조정"했다고 하나 수동 설정 조정인지 재학습인지 불명 **(미검증)**.
- **증거**: 유일한 피드백 특허(US11954440)는 **AP 인보이스**용 — 과거 사용자 수정이 있으면 모델 출력을 덮어쓰는 룰 기반 오버라이드다. 경비 쪽 특허에는 없다. 리뷰어는 "같은 카테고리에서 반복되는 false positive", "모델 조정 절차가 느리고 번거롭다", "3년 열려 있는 케이스"를 보고 [2차]. → 피드백은 **설정 변경 경로**가 주이고, 자동 재학습은 주장 수준.

## 6. 검증·수치
| 수치 | 출처 | 성격 |
|---|---|---|
| Flight Centre Canada: 40명×5h/월 → 1명 2h/월, "line-by-line 검토 노동 95% 감소", 비용 50% 절감 | AppZen 사례 | [마케팅] 분모는 라인 검토 시간, 전체 감사 아님 |
| Spectrum Brands 72% 자동승인(1년차), 처리 2~3주→3h, 연 560(본문 600+) 시간 절감 | AppZen 사례 | [마케팅] 내부 불일치 |
| 생명과학 고객 50% 자동승인 "minimal false positives"(2개월) | AppZen 사례 | [마케팅] 수치 없음 |
| Concur 사용자: 미자동승인 10% ≈ 월 1,000건, "mostly FPOS" | Concur 커뮤니티(아카이브) | [2차] 원문 소실, **(미검증)** |
| ZenLM Plus: 7개 frontier 모델 대비 6개 감사 통제 중 5개 우위 | 2026-10-01 보도 | [마케팅] 자사 벤치마크, 과제·모델 비공개 |
| **AI 생성 가짜 영수증 비율**(적발된 가짜 중) | | |
| 2024-09 ≈0% → 2025-09 **14%** | FT 보도(2025-10-27) | [2차] 분모 해석 논쟁 있음 |
| 2025-03 0% → 2025 Q2 26% → Q4 11% → 2026-04 39%(템플릿 위조 추월) → **2026-05 중순 70.8%** | Accounting Today 2026-06-23 | [2차] 1,471건·745명·174사·$148,143, 평균 ≈$100(중앙값 $32) vs 템플릿 위조 $182 |
| 공개 false-positive 비율 | — | **없음**. 제3자 실측 없음 |

## 7. 구조적 한계
1. **상위 경비 시스템 전제.** 입력 스키마가 "보고서→라인→사유·참석자·영수증"이다. 사유(`elpurpose`)·영수증 유무 플래그가 필수 → 카드사 거래 파일만 있는 조직은 입력 자체가 안 된다. CSV 경로는 마스터데이터용.
2. **회고 모드 없음.** 제출 시점 pre-payment 게이트로 설계. 수년 치 거래를 한 번에 재감사하는 흐름·문서가 없다.
3. **설명 = 룰명 + 템플릿 문장.** "임계값 20 초과"는 왜 20인지, 어느 정책 조항인지 말하지 않는다. 신뢰도 낮음도 MEDIUM 등급 안에 녹아 감사자가 구분 못 한다.
4. **등급 합성이 불투명.** 최댓값 추정 외 공개 없음. 룰 하나 HIGH면 보고서 HIGH → 리뷰어가 말하는 "같은 카테고리 반복 FP"의 구조적 원인.
5. **피드백이 모델로 돌아간다는 증거 없음.** 승인/반려는 상태 동기화. 교정은 설정 변경 + 벤더 티켓.
6. **영어·서구 데이터 중심 보강.** 특허의 외부 소스는 Google Places/Yelp/TripAdvisor/Wikipedia/OFAC. 한국 가맹점명·국세청 적격증빙 체계는 범위 밖. 42개 언어 OCR 주장은 [마케팅].
7. **폐쇄 모델.** ZenLM 구조·학습데이터·벤치마크 비공개. 2013년 우선권 특허의 SVM/kNN이 현재 프로덕션과 같은지 확인 불가.
8. **AI 영수증 탐지의 취약 축.** 공식 설명의 첫 신호가 "메타데이터가 있으면 잡는다". 스크린샷·재저장·인쇄 후 촬영이면 사라진다(heise, 금융 가이드 지적). 가맹점 DB 대조·수학 검증이 보조하지만, 평균 $100·중앙값 $32는 다수 고객의 자동승인 임계 아래다.
9. **운영 결합 리스크.** 상태 확정이 고객 측 콜백에 의존 → 콜백 누락 시 "무한 pending, 에러 없음"이 공식 문서에 적혀 있다. 2025-11 Concur 워크플로 정체 장애 14시간.

## 8. 우리에게 주는 것
**가져올 패턴**
- `original / computed / current` 3필드로 **오버라이드를 덮어쓰지 않고 보존** — 우리 룰·모델 평가의 ground truth가 된다.
- 헤더/라인 2층 룰 + 모든 룰이 "해당 없음"까지 결과를 남기는 **전수 로그** — 왜 안 잡았는지도 설명 가능.
- 중복 탐지 범위 3단(보고서 내 / 동일인 교차 / 집단 교차)과 **라인↔영수증 1:1 할당 알고리즘**(우선순위 완화 반복)은 그대로 쓸 만하다.
- 큐를 위반유형·직원그룹·정책·국가로 자르는 것, 특정 위반은 사람 없이 **직원에게 자동 반송**.
- 웹훅 4종 이벤트(자동/수동 × 승인/반려) + 코멘트 — 피드백 최소 스키마.

**피할 함정**
- 템플릿 문장을 "설명"으로 팔지 말 것. 우리는 **정책 조항·비교 대상 거래·임계값 근거**를 같이 붙인다.
- "신뢰도 낮음"을 MEDIUM 등급에 섞지 말고 별도 축(확신도)으로 분리.
- 경비 보고서 없는 플랫 카드 거래로도 돌아가야 한다 — AppZen이 비운 자리다.
- AI 영수증 탐지는 메타데이터에 기대지 않고 가맹점 DB·금액 분포·행동 패턴으로.

## 9. 출처
**[특허]**
- US11321784B2 / US11954739B2 "Methods and systems for automatically detecting fraud and compliance issues in expense reports and invoices" (Verma, Kale; 우선일 2013-03-06; 등록 2022-05-03 / 2024-04-09) — https://patents.google.com/patent/US11321784B2/en , https://patents.google.com/patent/US11954739B2/en
- US11126838B2 "matching line item textual entries with individual image objects from a file with multiple image objects" (2021-09-21) — https://patents.google.com/patent/US11126838B2/en
- US11954440B2 (AP 인보이스 피드백 오버라이드, 2024-04-09); US12469058, US12632885 (AP PO 매칭·GL 코딩) — https://patents.justia.com/assignee/appzen-inc

**[공식문서]** (support.appzen.com; 직접 접근 시 Cloudflare 차단, 리더 프록시로 확인)
- Introduction(통합 흐름, Low/Medium/High) — /hc/en-us/articles/12682580110739
- Upload Report Details(Ingestion 스키마) — /hc/en-us/articles/12654969224083
- Fetch Audit Results for a Single Expense Report(rule_name/risk_message/3 risk 필드 샘플, 2023-07-13) — /hc/en-us/articles/12657595272851
- Fetch Audit Results in Bulk(3 risk 필드 정렬) — /hc/en-us/articles/12657693112211
- Auditor's Action API Overview(웹훅 4 이벤트, auditor_comments, external_status 콜백, 2026-09-16) — /hc/en-us/articles/13078579887507
- Merchant Blacklist Check(고객 제공 목록, 2026-10-23) — /hc/en-us/articles/56225176272147
- CSV Integration / CSV Templates(마스터데이터·직원 전용) — /hc/en-us/articles/42480450036499 , /hc/en-us/articles/42480470322707

**[마케팅]**
- Expense Audit 데이터시트 25DS01(큐 관리: violation/employee group/policy/country; 이미지 PDF, 텍스트 추출 불가) — https://appzen.com/hubfs/expense-audit-datasheet-25DS01.pdf
- How we are different(Mastermind/ZenLM, Feedback Models) — https://www.appzen.com/how-we-are-different
- SAP Concur 통합 페이지 — https://appzen.com/integrations/sap-concur
- Flight Centre Canada 사례 — https://www.appzen.com/resources/case-studies/flight-centre-canada-soars-with-ai-powered-expense-audit
- Spectrum Brands 사례 — https://appzen.com/spectrum-streamlining-audit-process
- Catching AI-generated fake receipts with AI(탐지 방법) — https://www.appzen.com/blog/catching-ai-generated-fake-receipts-with-ai
- 7 ways to automate your unique T&E policy — https://appzen.com/blog/7-ways-to-automate-your-unique-corporate-te-policy-with-mastermind

**[2차]**
- Accounting Today 2026-06-23 "Use of AI receipts in expense fraud soars" — https://www.accountingtoday.com/news/use-of-ai-receipts-in-expense-fraud-soars
- Computerworld 2025-10-27(FT 14% 인용) — https://www.computerworld.com/article/4079701/new-ai-scam-fake-expense-receipts.html
- heise 2025(메타데이터 제거 취약) — https://heise.de/-10904220
- Runtimewire 2026-10 ZenLM Plus 벤치마크 — https://runtimewire.com/article/appzen-zenlm-plus-finance-models
- Aithority 2021-06-18 특허 보도 — https://aithority.com/machine-learning/appzen-continues-to-innovate-finance-with-new-ai-patent/
- SAP Concur Community: 코멘트 필드 미전송(2019-04-12) https://community.concur.com/t5/Additional-Products-Forum/How-do-Detect-customers-handle-the-comments-field/m-p/5371 ; 운영 방식(2020-04-20) https://community.concur.com/t5/Concur-Expense/How-to-use-AppZen-with-Concur/m-p/9267 ; "mostly FPOS" 스레드(아카이브, 원문 미확인) m-p/218
- SoftwareFinder 리뷰(2024-09~11, 반복 FP·느린 조정) — https://softwarefinder.com/accounting-software/appzen/reviews ; G2 — https://www.g2.com/products/appzen-appzen/reviews
