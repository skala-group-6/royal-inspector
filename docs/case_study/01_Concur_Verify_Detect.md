# Case Study 01 — SAP Concur Verify / Concur Detect by Oversight / Audit Service

작성일 2026-11-02. 1차 출처(SAP Learning 코스 9개 레슨, SAP Help 검색 API 스니펫, 2022 Verify Release Notes PDF, UF·UNC Charlotte 공지)를 직접 읽고 정리. **검증 불가 항목은 ⚠️로 표기.**

## 1. 한 줄 정의

Concur Verify는 Concur Expense 워크플로우 **안에** 끼어 들어 제출된 경비보고서 100%를 "Receipt 체크 + Policy 체크" 라이브러리로 평가하고, 예외(exception)가 하나라도 있으면 보고서를 `Reports Pending Audit Review` 큐로 보내 사람 감사자가 예외 단위로 Pass/Fail을 내리게 하는 **예외 기반(exception-based) 인워크플로우 감사 엔진**이다. Concur Detect by Oversight는 같은 자리에 꽂히는 **파트너(Oversight) 엔진**으로, 보고서를 Concur 밖 Oversight Workbench로 보내 선지급(pre-payment)·후지급(post-payment) 두 번 리스크 점수를 매긴다. Audit Service(Intelligent Audit)는 SAP 소속 사람 감사자가 대신 감사해 주는 유료 서비스다.

## 2. 데이터 입력

**어디서 들어오나.** 입력은 전부 Concur Expense가 이미 보유한 객체다.
- 경비보고서(Report Header, 라인아이템, Expense Type, City, Attendees, Allocations, Travel Diary) — 제출(Submit) 이벤트가 트리거.
- 카드 피드 — `Personal Use of Company Card`, `Improper Merchant Categories` 체크는 "merchant category를 카드 거래 피드에서 직접 가져오며, 이 정보가 있는 경비에만 예외를 낼 수 있다"[공식문서].
- 영수증 이미지(라인아이템 첨부) / e-receipt / 멕시코 CFDi.
- 출장 일정(Travel bookings) — 교육자료는 "receipts, credit card transactions, and travel bookings"를 분석 대상으로 명시[교육자료].
- 과거 데이터: `Duplicate Receipt`·`Duplicate Transaction`은 "회사 전체의 다른 보고서"와 비교, `Unreasonable Amount`는 "cross-Concur average"(SAP 고객 전체 집계)와 비교[공식문서].

**전처리.** 영수증에서 날짜·금액·상인·세금ID 등을 추출(OCR + 모델). "Illegible Receipt"는 날짜와 금액을 못 읽으면 예외를 낸다. 모든 Spend Statistics 금액은 USD로 환산[교육자료].

**없으면 돌지 않는 전제조건(교육자료 'Describing Key Considerations' 원문).**
- "Verify will only evaluate receipts attached at the **line item level**." 보고서 레벨 첨부는 평가 안 함.
- "Verify will **not process poor-quality receipts or multiple receipt images**."
- 영수증 필수 여부는 Concur Expense 쪽 설정이 결정 — "if the expense type does not require receipts, no check will run for it."
- 위치 기반 체크(Unreasonable Amount, Duplicate Meal Claim, Duplicate Transaction)는 **City 필드 필수**, Unreasonable Amount는 Breakfast/Lunch/Dinner 같은 구체적 Meal Type 필수.
- 사용자별 `Expense Audit Required = Audit Never Required`면 그 사용자는 제외.
- 감사자는 최소 1개 Audit Profile에 배정돼야 큐가 보인다(2022-01 릴리즈노트).
- Audit Profile은 Expense Policy Group당 1개, 그룹 계층(Global이 최상위)으로 상속.

즉 **Concur 제출 파이프라인을 통과하지 않은 데이터(엑셀, 메일함 영수증)는 입력 경로 자체가 없다.**

## 3. 구성요소와 흐름

```
 직원                Concur Expense 워크플로우                         감사자(Verify Reports Auditor)
 ─────               ────────────────────────────                    ─────────────────────────────
 영수증 첨부(라인) ─► Submit ─► [Verify 평가: Audit Profile의 체크 실행]
                                   │
                     예외 0건 / 고신뢰 ───────────────► 다음 단계(Manager → Processor → 지급)
                                   │
                     예외 ≥1건 ──► "Submitted and Pending Verify Audit Review"
                                   │
                                   ▼
                        Reports Pending Audit Review 큐
                        (filter: 제출일·Audit Profile·Assignee / Unassigned 기본 / Self-assign)
                                   │
                                   ▼
                        Unified Compliance View (보고서 1건)
                        ├ AI 예외(Receipt/Policy) + 고객 Audit Rule 알림을 한 패널에
                        ├ 예외별: Auditor Response ▾ · Spend Statistics · Why was it raised? · Auditor Note
                        └ 영수증 뷰어 / 카드 거래 상세 / Attendees / Audit Trail
                                   │
                 ┌─────────────────┴──────────────────┐
     1건 이상 Fail (Out of Policy)                 전부 Pass (Incorrect Exception /
     + Comment to Employee 필수                      Approve with Exception / custom pass)
                 │                                   │
                 ▼                                   ▼
     직원에게 반송(Send Back)                 다음 워크플로우 단계
     [옵션 Split Report: 실패 라인만         [옵션 Skip Step: Verify 감사자가 승인했으면
      'Addendum' 신규 보고서로 분리,            Approval for Processing(Processor) 건너뜀]
      나머지는 계속 진행]                            │
                 │                                   ▼
     재제출 → Verify가 'resubmit'으로 인식,     Processor → 지급
     Auditor Exception 재검증
```

**구성요소.**
- **Library of Audit Checks**(SAP가 관리하는 닫힌 카탈로그): Receipt 계열(Duplicate Receipt, Illegible Receipt, Incorrect Date, Incorrect Amount, Incorrect Expense Type, AI-Generated Receipt(구 Online Generated/Fake Receipt), Incorrect Receipt Status‑UK, Invalid Merchant Tax ID‑JP…) + Policy 계열(Unreasonable Amount, Duplicate Meal Claim, Duplicate Transaction, Personal Use of Company Card, Improper Merchant Categories, Excessive Tip, Traveler Name, Companion Travel, Personal Items/Services/Entertainment, Configured Expense Type…). "This list is subject to change based on testing and performance."[공식문서]
- **Audit Profile**: 체크 묶음 + 조건(Amount Trigger, Expense Types Trigger, Date Threshold, Allowable Discrepancy, percentile) + 체크별 Auditor Response 세트 + 담당 감사자. "Add Essential Checks"로 5개 기본 체크 일괄 추가.
- **Reports Pending Audit Review** 큐와 **One-Time Audit**(2026 Preview): Verify 화면에서 Processor 권한으로 필드 수정·승인까지 완료.
- **Concur Detect by Oversight**(대체 경로): 보고서 상태 `Pending External Validation` → Oversight가 4단계(데이터 이해→정책 대조→행동 분석→리스크 평가) 처리 → Workbench에 exception → 감사자가 Workbench에서 승인/반송 → Concur 워크플로우로 복귀. 위험 없는 보고서는 자동 승인[마케팅 브로슈어 FR]. UF 운영 공지: 선지급 플래그는 72시간(고위험 기준 7일) 내 미검토 시 자동 승인 후 후지급 감사로 이월[2차].
- **Audit Service / Intelligent Audit**: SAP 글로벌 감사팀(2021 당시 HGS 파트너, 24/7)이 고객 정책으로 직접 감사·직원과 예외 해결. Verify와 동시 사용 불가[2차·SAP 커뮤니티 공식 포스트].

## 4. 판단 방식

**룰 vs ML 분담.** 공식 문서는 체크 단위로만 설명하고 모델 구조는 공개하지 않는다. 문서상 추론 가능한 분담:
- 결정론적 룰: 날짜 차이(현금 0–2일, 카드 30일 권고), 금액 불일치 허용치, 개인경비 플래그, MCC 리스트, Tax ID 포맷(T+13자리) 등.
- 통계: `Unreasonable Amount`는 "cross-Concur average" 대비 percentile. 2022년에는 "평균의 230%" 기본값, 현재 문서는 "value 5% → 해당 지역·식사유형 상위 5%면 예외"로 percentile 방식[공식문서]. `Excessive Tip`은 평균 대비 %.
- ML/비전: 영수증 필드 추출, Incorrect Expense Type(영수증 내용으로 지출 종류 추정), Duplicate Receipt(이미지 유사도 — "minor edits may impact accuracy"), AI-Generated Receipt(메타데이터 포렌식 + "확인된 AI 생성 영수증으로 학습된 모델, 지속 재학습"[마케팅]).

**리스크 레벨.** Verify에는 보고서 전체 점수가 없다. 예외가 있거나 없거나이며, 유일한 등급은 AI-Generated Receipt의 **Confidence High/Medium**이다 — "High는 워터마크·메타데이터 서명 같은 결정론적 마커 발견"[공식문서]. Detect는 반대로 라인·보고서 단위 **risk score(confidence × financial impact)**를 매기고 직원 화면에 "Report Audited by Concur Detect. Risk level: high/medium" 경고가 뜬다[2차 커뮤니티].

**"Why was it raised?"**: 2022-04 릴리즈로 예외 옆 info 아이콘 → 체크 설명 모달. 내용은 **해당 체크의 정적 설명문**이며 건별 피처 기여도가 아니다. 예외는 AI 영수증 체크 — 2026-09부터 "무엇이 탐지됐는지 평문 설명 + 신뢰도 + 권고 조치, 생성기 사이트명, 메타데이터 필드명·값"을 건별로 보여준다[공식문서].

**Spend Statistics 다이얼로그**(교육자료 원문): Expense type·Location, 평균 지출, 프로필에 설정된 percentile 임계치, 1인당 청구액, 이 건의 percentile, 그리고 50/80/95/99 percentile 분포. 모두 USD 환산. 즉 **SAP 전체 고객 집계 분포에서 위치를 보여주는 것**이고 자사 데이터만의 분포는 아니다.

**사람 개입 지점.** 모든 예외는 감사자 결정을 요구하며 워크플로우를 정지시킨다. 응답은 체크별로 사전 정의: `Fail – Out of Policy`(직원 코멘트 필수, 반송) / `Pass – Incorrect Exception`(오탐, 직원 조치 없음) / `Pass – Approve with Exception`(정책 교육용 사전 메시지 포함) / 관리자 정의 custom pass. 사전 코멘트는 제출자 언어로 현지화되지만 **편집하면 번역되지 않는다.** Verify가 못 잡은 건은 `Add Exception`으로 감사자가 직접 추가 가능. `Pass Pending`으로 일괄 통과. 2021 SAP 뉴스는 "AI 결과를 고객에게 플래그하기 전 Verify 감사자 팀이 검증한다"고 했으나 현재 셀프서비스 Verify 문서에는 이 단계가 없다 ⚠️(시점 차이 또는 Audit Service 한정).

## 5. 피드백

- **Audit Trail**에 상태 변경·감사자 응답이 기록되고, Addendum 재제출 시 "all the history for those expenses will remain"[공식문서]. Auditor Note는 내부용(직원 비노출).
- **감사자 Pass/Fail이 모델을 재학습시키는지에 대한 공식 문서는 없다 ⚠️.** 찾은 것은 (a) "Pass – Incorrect Exception"이 오탐 라벨로 기능한다는 UI 설명, (b) AI 영수증 모델이 "continuously retrained"된다는 마케팅 문구, (c) 2021 뉴스의 "customer feedback shaped the new checks"뿐이다. 즉 피드백은 **체크 카탈로그 개선(제품 로드맵)** 경로로 흡수되며, 고객 테넌트 단위 온라인 학습은 확인되지 않는다.
- **'helpful?' 류 프롬프트**: SAP Learning 9개 레슨·릴리즈노트 어디에도 없다 ⚠️. Detect(Oversight) 쪽은 리뷰어가 "users modify the system over time to produce better results, such as less noise"라고 하지만 룰 튜닝인지 모델 학습인지 불명[2차].
- 피드백이 가는 다른 곳: Reports Pending Audit Review의 **Excel export**, Analysis/Intelligence의 Audit 폴더 표준 리포트, 그리고 Audit Profile의 임계치(percentile, discrepancy) 조정 — 즉 사람이 숫자를 돌려 조정하는 수동 루프다.

## 6. 검증·수치

| 수치 | 출처 유형 | 비고 |
|---|---|---|
| 경비보고서 100% 평가 | [공식문서]/[교육자료] | 체크가 켜진 Expense Type·그룹에 한함 |
| 1년간 3,800만 건 체크, 월평균 보고서 1/3 플래그 | 벤더 주장(2021 블로그) | 셀프서비스 전환 전 수치 |
| 검토 영수증의 ~1%가 AI 생성 의심 플래그 | 벤더 주장(Chris Juneau, 2025-11) | Skift·SAP 블로그 동일 인용 |
| AI 생성 영수증 탐지율 "약 18배" | 벤더 주장 | 비교 기준은 "알려진 온라인 생성기만 보던 이전 체크" — **Oversight 수치가 아님** |
| "수천 건" AI 영수증 식별 | 벤더 주장 | 분모 미공개 |
| Unreasonable Amount 기본 230% → percentile(예 5%) | [공식문서] | 2022 RN vs 2026 Library |
| Verify 영수증 언어 16개 / Detect 약 50개, 비US영어 영수증 ≤1/3 | SAP 커뮤니티 공식 포스트[2차] | 열 귀속 불명확, 2026 "Expansion of Supported Languages"로 변동 |
| Oversight 가짜영수증 탐지 정확도 >90%, OCR 대비 오탐 80%↓, 80+ 언어 | 벤더(Oversight 보도자료 2025-09) | 방법론 미공개 |
| Detect 선지급 검토 72h/7d, 대부분은 후지급에서 플래그 | 제3자 운영 공지(UF, 2026-01) | 측정치 아닌 운영 SLA |
| 감사팀 시간의 80%가 사무적 오류에 소요 | 벤더(App Center) | 업계 일반 주장 |

**측정(measured)으로 분류할 수 있는 독립 수치는 없다.** 오탐률·재현율은 어느 문서에도 없다.

## 7. 구조적 한계

1. **입력 경로가 Concur 제출 이벤트 하나.** 엑셀 원장 + 영수증 폴더만 있는 회고적(retrospective) 감사는 설계상 불가능하다. 카드 피드·일정·첨부가 전부 Concur 객체여야 하고, 체크는 제출 시점에 1회 돈다.
2. **라인아이템 첨부 + 단일 깨끗한 이미지 전제.** 보고서 레벨 첨부·저화질·다중 이미지는 "처리하지 않음"으로 조용히 빠진다(예외가 아니라 미평가). Illegible Receipt 체크가 있지만 날짜·금액 가독성만 본다.
3. **한국 영수증·세법 미지원.** 체크 카탈로그의 지역 특화는 UK(VAT Receipt Status, Tax Amount), JP(Merchant Tax ID T+13, Tax rate), MX(CFDi)까지. 한국 현금영수증·세금계산서·카드전표 형식, 접대비 한도 같은 룰은 없고 고객이 추가할 수도 없다. 지원 언어 목록도 SAP가 정한다.
4. **닫힌 룰 카탈로그.** 고객은 SAP 라이브러리의 체크를 켜고 임계치만 조정한다. 새 체크는 SAP 릴리즈를 기다려야 한다. 자체 규칙은 Concur Expense의 Audit Rules(별도 엔진)로만 가능하며, 2026 One-Time Audit은 그 둘을 **한 화면에 합쳐 보여줄 뿐** 같은 엔진이 아니다.
5. **벤치마크가 SAP 전 고객 집계.** Spend Statistics는 자사 분포가 아니다. 지역·식사유형 축으로만 절단되고 USD 환산이라 원화 소액·물가 차이가 희석된다.
6. **데이터 거주지.** 영수증 이미지와 금액이 SAP 데이터센터(US/EU 등) 및 서브프로세서로 간다. Detect는 추가로 Oversight(제3자)로 전송되며 UI는 영어만[마케팅]. 국내 개인정보·금융 데이터 반출 요건이 있는 조직은 선택지가 없다.
7. **파트너 엔진 교체 리스크.** Detect는 AppZen → Oversight로 한 번 교체됐고, UNC Charlotte는 2026-07-31 Verify를 끄고 Detect로 갈아탄다. 두 제품은 큐·응답 체계·감사 흔적 위치(Concur 내부 vs Oversight Workbench)가 달라 **감사 이력과 운영 습관이 이식되지 않는다.** 커뮤니티에는 Detect 심사 중 보고서가 "stuck" 된다는 보고도 있다[2차].
8. **설명이 체크 단위.** "Why was it raised?"는 룰 설명문이고, 건별 근거는 AI 영수증 체크에만 있다. 모델 체크(Incorrect Expense Type, Duplicate Receipt)의 오탐 이유는 알 수 없다.
9. **피드백 루프 부재(확인 범위 내).** 오탐을 `Pass – Incorrect Exception`으로 눌러도 다음 달 같은 오탐이 줄어든다는 보장이 문서상 없다.

## 8. 우리에게 주는 것

**복사할 패턴**
- **Unified Compliance View**: 모델 예외와 룰 예외를 한 패널에, 라인별 예외 수 표시, "예외 없는 라인은 접기"(기본 숨김, 토글로 전체 보기). 감사자가 보고서 전체를 다시 읽지 않게 하는 핵심.
- **예외 단위 disposition**: 보고서 승인/반려가 아니라 **예외마다** Pass(오탐)/Pass(교육용 통과)/Fail(반송)을 고르게 하고, Fail엔 코멘트 필수. 오탐 라벨이 자연스럽게 쌓인다 — 우리는 이걸 실제 재학습/임계치 재조정에 써야 한다(Concur가 안 하는 부분).
- **Spend Statistics 링크**: 금액 이상치 예외에 평균·임계 percentile·이 건의 percentile·50/80/95/99 분포를 한 다이얼로그로. 단 우리는 **자사 분포 + 동일 부서/직급/도시** 절단을 기본으로 하고 외부 벤치마크는 보조로.
- **"Why was it raised?" + 건별 증거**: AI 영수증 체크처럼 "탐지 방식(메타데이터/시각) → 필드명·값 → 신뢰도 High/Medium → 권고 조치" 포맷을 모든 체크에 적용.
- **Auditor Note(내부) vs Comment to Employee(외부) 분리**, 사전 정의 코멘트의 현지화.
- **Split Report(Addendum)**: 실패 라인만 떼어 반송, 나머지는 지급 진행. 지급 지연 최소화.
- **Skip Step**: 감사자가 끝까지 봤으면 Processor 단계 생략 — 중복 검토 제거.
- **Self-assign/Unassigned 큐 + Audit Profile(그룹별 체크 세트)**.

**함정**
- "100% 감사"는 "켜진 체크가 100% 돈다"는 뜻이다. 체크 안 켠 영역은 0%. 커버리지 지표를 체크 단위로 따로 보여줘야 한다.
- 저화질·다중 이미지를 **조용히 미평가**하면 안 된다. 우리는 "평가 불가"를 명시적 예외로 올려야 한다.
- 외부 집계 벤치마크(USD)는 한국 식대·접대비에 그대로 쓰면 오탐/미탐 둘 다 난다.
- 리스크 점수 하나로 "high"만 던지면(Detect식) 직원·감사자 모두 "뭘 고치라는 건지" 모른다는 커뮤니티 불만이 반복된다. 점수보다 **예외 목록 + 조치**가 우선.
- 편집한 코멘트는 번역 안 됨 — 다국어라면 템플릿 변수 방식으로.
- 파트너 엔진 의존은 교체 시 감사 이력이 끊긴다. 판단 로그는 우리 저장소에 1차 보관.

## 9. 출처

**SAP Learning — "Working with Concur Verify for Audit"** (2026-10-01 빌드, Next.js data 라우트로 본문 확보) [교육자료]
- https://learning.sap.com/courses/working-with-concur-verify-for-audit/viewing-reports-pending-audit-review_a0b2361c-b970-4a6c-bc16-55886355c720
- https://learning.sap.com/courses/working-with-concur-verify-for-audit/working-with-submitted-expense-reports_e36d4586-417a-41b1-bd90-594935a7fd2a
- https://learning.sap.com/courses/working-with-concur-verify-for-audit/viewing-details-of-an-expense-report_d81452c4-5a34-4e66-ac63-58084538ed7f
- https://learning.sap.com/courses/working-with-concur-verify-for-audit/working-with-a-pass-or-fail-exception_dc30015b-f47a-417f-ad92-f06c469b3520 (Spend Statistics, Why was it raised?, Auditor Response 원문)
- https://learning.sap.com/courses/working-with-concur-verify-for-audit/completing-an-audit-of-an-expense-report_db234653-d0c6-4bc1-b5e0-2792204d1893 (One-Time Audit, Skip Processor, AI Receipt Check confidence)
- https://learning.sap.com/courses/working-with-concur-verify-for-audit/using-the-self-assign-or-unassigned-options_ccb92d30-72dc-4c56-826d-5c7bd48214e6
- https://learning.sap.com/courses/working-with-concur-verify-for-audit/introducing-verify_c2718493-d193-44af-8291-5ace9807a6b0
- **Describing Key Considerations**(요청한 레슨은 Verify Self-Service Activation 코스에 속함): https://learning.sap.com/courses/working-with-verify-self-service-activation-for-concur-professional-edition/describing-key-considerations_e9afd508-e67f-4682-b0e6-216aa7e1a044 — "line item level / poor-quality / multiple receipt images" 원문
- 같은 코스: configuring-audit-checks_b4b7a45b…, working-with-auditor-responses_bf357b54…, working-with-common-conditions_e4eb2a8f…, configuring-audit-profiles_dc92e3dc…

**SAP Help Portal — Concur Expense Tools Guides / Release Notes** (SPA라 본문은 help.sap.com 검색 API 스니펫으로 확인) [공식문서]
- Library of Audit Checks: https://help.sap.com/docs/CONCUR_EXPENSE/f5755419ccf14165ad6ff6816729ec08/9869980e71371014b1b8a2f66f04ca50.html
- Evaluation of an Expense Report (Split Report/Addendum, Skip Step): https://help.sap.com/docs/CONCUR_EXPENSE/f5755419ccf14165ad6ff6816729ec08/d9da325f07d0408a93435567585f0a3a.html
- Verify Roles: https://help.sap.com/docs/CONCUR_EXPENSE/f5755419ccf14165ad6ff6816729ec08/4da2bf070951481998a577ed132ea587.html
- Supported Receipt Languages: https://help.sap.com/docs/CONCUR_EXPENSE/f5755419ccf14165ad6ff6816729ec08/2bf8198ec75240928d44670093d2f571.html
- RN "Enhancements for Detecting AI-Generated Receipts" (2025-07-19): https://help.sap.com/docs/CONCUR_EXPENSE/e3c88ad9ff4342849305e7cd9aa9c9d4/3422198fdcda4001a2195d561f0550e9.html
- RN "AI Generated Receipts – Enhanced Auditors Experience" (2026-09-19): https://help.sap.com/docs/CONCUR_EXPENSE/61f9102049ab452ca24f99c575543675/2a5d477682e442b9a25d93c2720f73b0.html
- RN "One-Time Audit: Audit and Approve Expense Reports Within Verify" (2026 Preview): https://help.sap.com/docs/CONCUR_EXPENSE/61f9102049ab452ca24f99c575543675/bc9804d6e348427e90ebb7501dd6965a.html
- RN Intelligent Audit "Duplicate Receipt Check"/"Duplicate Transaction Check" (2026-05): https://help.sap.com/docs/CONCUR_EXPENSE/e3c88ad9ff4342849305e7cd9aa9c9d4/e6d8232aaa3a40239f7347431dce0e38.html
- Verify Release Notes 2022 (PDF, Unreasonable Amount 230%, 예외 설명 아이콘, 체크 리네임): https://help.sap.com/doc/14504cf8857b47c5a686dcf78bcdfee8/2022_12/en-US/Verify%20Release%20Notes%202022_client.pdf

**Concur Detect by Oversight**
- App Center 리스팅 [마케팅]: https://www.concur.ca/app-centre/listings/6009d8f92d2d5b0015e88b63
- 솔루션 브로슈어 FR(4단계 처리, Workbench, 자동승인) [마케팅]: https://www.concur.fr/sites/fr/files/acn/89895_89895_enus_fr-fr_interactive.pdf
- 제품 가이드 PDF ⚠️ **요청 URL(d.dam.sap.com/a/92950_Detect_ProductGuide_enUS.pdf)은 "asset not found"로 리다이렉트되어 열 수 없었음.** 커뮤니티 안내 페이지: https://community.concur.com/t5/Getting-Started/Concur-Detect-by-Oversight-Product-Guide-for-Admins/ba-p/36876
- SAP News(2021-07, 출시) [마케팅]: https://news.sap.com/africa/2021/07/concur-detect-by-oversight-new-solution-tackles-fraud-and-non-compliant-expenses-through-ai/
- Oversight 가짜영수증 보도자료(2025-09) [마케팅]: https://www.businesswire.com/news/home/20250923198574/en/
- UF "Audit Changes & Insights" 2026-01-22 (Pending External Validation, 72h/7d) [2차]: https://procurement.ufl.edu/wp-content/uploads/2026/02/2026-01-22-Audit-Changes-Insights.pdf
- Chapman Univ. Detect 도입 공지(2020) [2차]: https://blogs.chapman.edu/information-systems/2020/05/05/concur-detect-coming-may-11th/
- 커뮤니티 "Risk level high" 스레드 [2차]: https://community.concur.com/t5/Concur-Expense-Forum/Warning-Report-Audited-by-Concur-Detect-Risk-level-high/m-p/111004

**Audit Service / 비교**
- SAP Concur Community "Audit Service Options – What are the Differences?" (16/50 언어, 1/3 비US영어, 동시사용 불가) [2차·SAP 작성]: https://community.concur.com/t5/Admin-Group-Forums/SAP-Concur-Audit-Service-Options-What-are-the-Differences/m-p/31551
- SAP Concur 블로그 "audit options explained" [마케팅]: https://concur.com/blog/article/sap-concur-audit-options-explained
- Intelligent Audit 제품 페이지 [마케팅]: https://www.concur.com/products/intelligent-audit
- SAP News 2021-06 Verify 출시(HGS 감사팀, 38M 체크, 1/3 플래그) [마케팅]: https://news.sap.com/2021/06/sapphire-now-verify-sap-concur/

**AI 영수증 수치**
- SAP Concur 블로그 "Fake Receipts 2.0" (1%, 18x, 메타데이터 포렌식) [마케팅]: https://www.concur.com/blog/article/fake-receipts-20-why-human-audits-fail-against-ai-and-how-tech-is-fighting-back
- Skift 2025-11-26 [2차]: https://skift.com/2025/11/26/business-travel-faces-a-deluge-of-ai-generated-expense-fraud/
- SAP News Fusion 2026-03 (Expense Pre-Submit Audit Agent, EAC) [마케팅]: https://news.sap.com/2026/03/sap-concur-fusion-2026-ai-capabilities-integrated-travel-expense-enhancements-global-partnerships/
- Community Quarterly Digest (pre-submit receipt check GA Q3 2026 목표) [2차]: https://community.concur.com/t5/What-s-New-in-Product/Release-Highlights-and-Product-Tips-Your-Quarterly-Digest/ba-p/80243

**UNC Charlotte**
- OneIT 2026-07-30 "Concur Verify will be turned off Friday, July 31 … Concur Detect by Oversight will replace it in the coming months" [2차]: https://oneit.charlotte.edu/2026/07/30/concur-system-updates-august-2026/
- Inside UNC Charlotte 2026-08-03 (deactivated 확인) [2차]: https://inside.charlotte.edu/2026/08/03/summer-commencement-preview-concur-verify-deactivated-university-convocation-review-the-upcoming-academic-calendar-and-more/
- SLAC Verify 파일럿 2026-02-26 (상태 문구) [2차]: https://travel.slac.stanford.edu/news/2026-02-26-sap-concur-verify-pilot-implementation

**찾지 못한 것 ⚠️**: Verify 체크가 어떻게 만들어지는지 설명하는 SAP 엔지니어링/커뮤니티 블로그(검색 결과 없음), 감사자 결정의 재학습 사용 여부, 'helpful?' 피드백 UI, 독립 측정된 정확도.
