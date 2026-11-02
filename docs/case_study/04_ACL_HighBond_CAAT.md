# 04. ACL Analytics / Diligent HighBond (ACL Robotics) + IDEA · Arbutus · Alessa — 룰 기반 감사분석(CAAT)

> 조사일 2026-11-02. 출처 등급: [공식문서] [마케팅] [2차] [정부보고서]. 확인 못 한 항목은 ⚠️ 표기.
> 주의: ACL 공식 도움말은 2025~26년에 `help.highbond.com` → `help.diligentoneplatform.com`으로 이전 중이라 URL이 301로 바뀌며 일부 페이지는 404다. 본문의 명령 문법은 Analytics 17 도움말에서 직접 확인한 것만 적었다. ACL의 "P-Card Fraud 패키지"(2013)의 테스트 10개 이름과 Oklahoma OMES 2013 연속감시 보고서 본문은 **열람 실패**다.

## 0. 한 장 요약

1987년부터 있는 감사자용 **스크립트 언어 + 배치 스케줄러 + 예외 추적표**. 감사자가 ACLScript로 "중복·쪼개기·주말·금액 임계" 같은 테스트를 직접 쓰고, Robots가 주기 실행해 Results 테이블에 예외 행을 쌓고, 사람이 상태(New→Open→Under Review→Closed/False Positive)를 바꾸며 닫는다. 벤더가 판정하지 않는다. 판정 로직은 전부 고객 내부감사의 스크립트 안에 있다.

- **모델이 없다.** 우선순위는 Low/Medium/High/Critical 4단계 수동값 또는 정렬. 2019년 "ML로 false positive 감소" 보도자료 이후 그 기능을 설명하는 공식 문서를 찾지 못했다.
- **피드백 경로가 없다.** False Positive로 닫아도 스크립트는 그대로다. 사람이 임계값을 고쳐 새 버전을 커밋해야 한다.
- **예외 과잉이 실측으로 기록돼 있다.** 샌디에이고 카운티(2009)는 ACL CCM의 P-card 분석 36개 중 3개가 6개월에 1만 건 이상, "동일 금액·여러 카드" 하나가 27,633건을 냈고, 14개 부서 중 5개는 모니터링을 아예 하지 않았다. 연준 OIG(2022)는 쪼개기 의심 36건 중 확정 0건.
- **운영 장치는 성숙하다.** 스크립트 버전·개발/운영 분리, 상태에 연결되는 질문지, 7일 미응답 재발송 트리거, 지표 임계 경보, 익명 공유 대시보드.
- 가져올 것: 표준 테스트 카탈로그(약 40개) · 상태 그룹(Open/Closed) + False Positive 별도 상태 · 상태↔질문지 연결 · 룰 버전 커밋/활성화 · 주기 실행 실패 알림. 피할 것: 스크립트에 지식이 갇히는 구조, 임계 하나로 예외 수를 못 조절하는 룰 전용 설계, 수동 4단계 우선순위.

## 1. 한 줄 정의

ACL(Audit Command Language)은 밴쿠버 ACL Services가 1987년 출시한 감사자용 데이터 분석 도구다. 2019년 Galvanize로 사명 변경, 2021년 Diligent에 인수돼 지금은 "Diligent One Platform" 안의 **Analytics(데스크톱 스크립트 도구) + Robots(서버 스케줄러, 구 Analytics Exchange/AX) + Results(예외 추적·질문지·트리거)** 세 앱으로 구성된다. 고객(기업·정부 내부감사)이 ACLScript로 테스트를 작성해 카드·경비·AP 거래 **전수**를 주기적으로 돌리고, 걸린 행을 Results에 올려 담당자에게 배정·질문·종결하는 **자체 제작형 연속감사(Continuous Auditing) 도구**다. 벤더는 언어·실행기·추적표를 팔고, 무엇을 잡을지는 고객이 쓴다. [공식문서]

비교 묶음: **IDEA**(CaseWare, 캐나다·독일 계열, IDEAScript + SmartAnalyzer 앱), **Arbutus Analyzer**(ACL 출신이 만든 ACL 호환 지향 도구, Hub 스케줄러 + Results Manager), **Alessa**(CaseWare → Tier1 Financial, 룰 기반 연속통제감시, P-card 모듈). 구조는 모두 "스크립트/룰 → 예외 테이블 → 사람 종결"로 ACL과 같다.

## 2. 데이터 입력

- **파일 적재가 1급 경로다.** Analytics는 `IMPORT EXCEL`, `IMPORT DELIMITED`, ODBC, SAP·Salesforce·DB 커넥터로 테이블을 만든다. 카드사 피드·ERP 연동이 **전제가 아니다** — 감사자가 은행 포털에서 내려받은 CSV/엑셀을 올리는 것이 표준 사용법이다. Robots에서도 "Excel·CSV 같은 non-Analytics 파일을 Input/Output 탭에 수동 업로드"할 수 있다. [공식문서 Robots 도움말]
- **전처리는 스크립트 안에서 수동.** 날짜 형식·필드 정의(table layout)·조인(`JOIN`, `RELATE`)을 감사자가 쓴다. 카드 거래 + 인사 마스터(퇴직자) + MCC 사전 + 카드 한도표를 수동 결합해야 "퇴직자 사용", "금지 MCC", "한도 초과" 테스트가 가능하다. [공식문서]
- **없으면 못 돌아가는 전제**: (a) 테이블 레이아웃을 정의할 수 있는 사람(ACLScript 숙련자), (b) 거래 한 건에 카드소유자·가맹점·MCC·금액·거래일이 열로 들어 있을 것, (c) 영수증·결재 문서는 입력 대상이 아님(Results 질문지로 직원에게 첨부를 요청하는 방식).
- **Results 적재 한도**: control test(테이블) 하나당 **10만 행**, 1회 export 10만 행, 행당 500필드, 필드당 256자. 월 수십만 건 카드 거래 **전체**를 Results에 올리는 구조가 아니다 — 예외만 올린다. [공식문서 EXPORT 명령]

## 3. 구성요소와 흐름

```
 카드사 CSV / ERP 추출 / 인사·MCC 마스터
        │  IMPORT (감사자 수동 또는 스크립트)
        ▼
 ┌────────────────────┐  ACLScript: DUPLICATES / SUMMARIZE / BENFORD /
 │ Analytics (데스크톱)│  EXTRACT IF … → 예외 테이블
 │ 스크립트 작성·테스트 │  analytic header(//ANALYTIC //PARAM //RESULT)로 포장
 └─────────┬──────────┘
           │ "commit" = 버전 n 생성 (개발 모드)
           ▼
 ┌────────────────────┐  개발/운영 두 모드. 운영은 "activate"한 버전 복사본만.
 │ Robots (서버)       │  Task Designer: 빈도·시작시각·파라미터값 지정
 │ 스케줄 실행          │  Import → Preparation → Analysis 스크립트 순서 실행
 └─────────┬──────────┘  실패/건너뜀/취소 시 지정 사용자 알림
           │ EXPORT … ACLGRC TO "<control_test_id>@us" [OVERWRITE]
           ▼
 ┌────────────────────┐  레코드 = 예외 1행. 열: Status·Priority·Assignee·
 │ Results (추적표)    │  Workflow Group + 스크립트가 보낸 필드
 │                    │  Trigger(실시간/주기) → 질문지 발송·상태 변경·배정·알림
 │                    │  Metric(집계) 임계 초과 → 알림
 └─────────┬──────────┘  Storyboard(대시보드, 익명 링크 공유)
           ▼
 사람: New → Open → Under Review → Closed / False Positive
```

- **Analytics Exchange(AX)는 2023-01-01 지원 종료**, Analytics 16 이후 버전은 AX 비호환. Robots가 후속. 즉 "AX Exception" 같은 구형 예외 관리 모듈 문서는 현행 구조가 아니다. [공식문서]
- **Robots 제약(Professional 에디션)**: 로봇당 모드별 Task 5개, 동시에 Task를 켤 수 있는 로봇 1개. Enterprise는 무제한. 동시 실행 5 Task, 초과는 큐. [공식문서]
- **개발/운영 분리의 구멍**: 두 모드는 Robots 내부 데이터만 분리하고 "Robots 바깥에 저장된 데이터는 분리하지 않는다" — 개발 스크립트가 운영 Results 테이블에 쓰지 않도록 사람이 조심해야 한다. [공식문서]

## 4. 판단 방식

### 4.1 표준 테스트 카탈로그 (P-card / T&E)

ACL은 "P-Card Fraud 패키지"(2013, "10 continuous monitoring analytics", "20개 이상 사기 리스크") 이름만 공개했고 테스트 목록은 못 찾았다 ⚠️. 대신 (a) Diligent 블로그 T&E 12종(2023), (b) Diligent AP 사기 10종(2019), (c) 샌디에이고 카운티 ACL CCM 36종 중 보고서에 언급된 것, (d) 알래스카대 ACL CCA 14종, (e) Alessa P-card 가이드 약 40종, (f) 정부 보고서가 실제 돌린 테스트를 합쳐 정리했다. 벤더 간 이름만 다르고 로직은 같다.

| 테스트 | 로직 | 전형 임계 / 비고 | 출처 |
|---|---|---|---|
| 중복 거래 | 같은 (카드, 가맹점, 금액, 거래일) 또는 (금액, 가맹점, 거래일·전기일) | 완전일치. Nigrini SSD: 8필드 일치 + 1필드 불일치(near-dup) | Alessa·IDEA SSD·Diligent |
| AP/T&E 교차 중복 | 카드 결제와 AP/경비 청구가 같은 벤더·금액 | 기간 창(예: 30일) 내 | Alessa·Wolters Kluwer |
| 쪼개기(단일 카드) | 같은 카드·가맹점·같은 날(또는 연속일) 합계 > 단건 한도 | 미 연방 micropurchase $3,500→$10,000(2018); 지자체 $2,499~$5,000 | 연준 OIG·Tulsa·Atlanta PS |
| 쪼개기(여러 카드) | 같은 가맹점·같은 날, 여러 카드 합계 > 한도 | | Alessa |
| 한도 바로 아래 | 금액이 한도의 95~100% 구간 | Diligent AP: "한도의 약 5% 이내", 예 $2,000 | Diligent 2019 |
| 단건/일간/월간 한도 초과 | 금액 > 카드 한도표 | 카드별 한도 조인 필요 | Alessa·Alaska |
| 주말·공휴일 | 거래일의 요일(`DOW()`) ∈ {토,일} 또는 공휴일표 | 공휴일표는 고객 제공 | Yolo·Alaska·Alessa |
| 영업시간 외 | 거래시각이 범위 밖(시각 데이터 있을 때만) | | Alessa |
| 금지 MCC / 제외 가맹점 유형 | MCC ∈ 차단 목록 | 연준 OIG는 "허용 MCC 목록"과 대조 | 연준 OIG·Alaska |
| 라운드 금액 | `MOD(금액, 100) = 0` 등 | $100 배수(현금성 의심) | Diligent·Alessa |
| 벤포드 | 선두 1~2자리 분포 vs 기대치, 상·하한 초과 자릿수 | ACL: 2개 이상 초과 시 조사 권고 | ACL BENFORD |
| 키워드 | 적요·코멘트에 "gift", "cash", "personal" 등 | 키워드 리스트는 고객 작성 | Diligent·Tulsa·Alessa |
| 퇴직자/휴직자 사용 | 거래일 > 퇴직일 (HR 조인) | | Alessa·Alaska·Tulsa |
| 본인 승인 / 승인 역전 | 승인자 = 카드소유자, 또는 하급자가 상급자 거래 승인 | | Tulsa 2023 |
| 승인 간격 | 카드소유자 서명 ~ 관리자 승인 간격이 매우 짧음(형식 승인) | | Alessa |
| 영수증 없음 / 코멘트 짧음 | 첨부 없음, 코멘트 길이 < n자 | | Alessa·Diligent |
| 동일인 범주 이상치 | 개인 범주별 지출 vs 회사 평균, 부서×MCC 그룹 비교 | | Diligent·Alessa |
| 단일 벤더 집중 / 급증 | 벤더 비중 > n%, 평균 지출 급증, 휴면 카드 갱신 사용 | | Alessa |
| 미사용 카드·중복 카드 | 6개월 무거래 활성 카드, 1인 다카드 | | Alessa |
| 연말 몰아쓰기 | 회계연도 마지막 달 고액 | | Alessa |

### 4.2 스크립트가 테스트를 표현하는 방식 (실제 ACLScript 문법)

```
COMMENT
//ANALYTIC Pcard_Split_Purchases
  동일 카드·가맹점·거래일 합계가 단건 한도를 넘는 조합을 찾는다
//PARAM v_limit N 단건 한도(원)
//RESULT TABLE Pcard_Splits
END
OPEN Pcard_Txns
SUMMARIZE ON Card_No Merchant Txn_Date SUBTOTAL Amount OTHER Cardholder_Name TO "Daily_Sums" PRESORT
OPEN Daily_Sums
EXTRACT RECORD IF Amount > %v_limit% AND COUNT > 1 TO "Pcard_Splits" OPEN
EXPORT FIELDS Card_No Merchant Txn_Date Amount COUNT Cardholder_Name ACLGRC TO "10926@us" OVERWRITE
```

- `//PARAM v_limit N`은 Robots Task Designer에서 값을 입력받아 `%v_limit%`로 치환된다. 이것이 ACL의 "임계값 분리" 방식이다. [공식문서 analytic header]
- 중복: `DUPLICATES ON Invoice_Number Vendor_Number OTHER Invoice_Date Invoice_Amount PRESORT TO "Duplicate_Invoices.FIL"` — 키 필드가 인접해야 잡히므로 `PRESORT` 필수. [공식문서 DUPLICATES]
- 벤포드: `BENFORD ON Amount LEADING 2 BOUNDS TO GRAPH` — LEADING 1~6, BOUNDS가 상·하한을 출력. [공식문서 BENFORD]
- 주말: `EXTRACT RECORD IF DOW(Txn_Date) = 1 OR DOW(Txn_Date) = 7 TO "Weekend"` (DOW 함수는 ACLScript 표준 함수).
- Results로 보낼 때 `ACLGRC TO "<control_test_id>@<datacenter>"`, `OVERWRITE`면 기존 데이터 덮어쓰기(Professional Manager 권한 필요), 없으면 추가. 필드는 **물리 이름**으로 매칭되고 새 이름은 새 열이 된다. [공식문서 EXPORT]

### 4.3 점수·우선순위·설명

- **점수 모델 없음.** 테스트는 참/거짓이고, 한 거래가 여러 테스트에 걸려도 **합산하는 기본 장치가 없다**(스크립트로 직접 계산해 열로 보내야 함). Results의 Priority는 Low/Medium/High/Critical 4값이며 사람 또는 트리거가 설정한다(튜토리얼: 직원이 "아니오"라고 답하면 Critical로 격상). [공식문서]
- **설명 = 테스트 이름 + 스크립트가 함께 보낸 열.** 정책 조문 인용은 감사자가 질문지나 코멘트에 손으로 쓴다.
- **ML 주장**: 2019-06 Galvanize 보도자료 "HighBond에 GRC 전용 ML 통합, 과거 데이터로 학습해 false positive를 줄이고 중요한 리스크 지표를 격상" — 기능명·학습 데이터·재학습 주기를 설명하는 공식 문서를 **찾지 못했다** ⚠️. 현행 Diligent 제품 페이지는 "AI 기반 노코드 ACL Analytics", "ACL 스크립트 완전 호환"을 말하며, 이는 스크립트 생성 보조(자연어→ACLScript)로 읽힌다. 학술적으로도 Svanberg et al.(2025)이 "현재 룰 기반 CA 설계에는 예외를 확률로 임계 조절할 방법이 없다"고 정리한다. [마케팅][2차]
- **사람이 개입하는 지점**: (1) 스크립트 작성·임계값 결정, (2) Task 스케줄과 파라미터 입력, (3) Results에서 레코드별 상태 변경·질문지 응답, (4) 지표 임계 초과 알림 수신.

### 4.4 Results의 예외 검토·종결 흐름 (공식 연속감시 가이드, P-card 예시)

1. Robots가 **월 1회** 스크립트 실행 → "Employee Pcard violations" 테이블에 예외 행 적재. 상태 **New**.
2. 트리거: `Status = New AND Further_investigation 공백` → 재무관리자에게 "Pcard exception review" 질문지 발송.
3. 관리자 답 "추가 조사 필요?" **No** → 트리거가 Status **Closed**. **Yes** → 직원 이메일로 "Pcard follow-up" 질문지(정책 확인·사유·사전승인·증빙 첨부) 발송, Status **Under Review**.
4. `Policy_attestation 공백 AND 마지막 갱신 ≥ 7일` → 주간 트리거가 재발송.
5. 직원 응답 시 관리자에게 Notify. 지표 "Count employees over monthly limit" > 0이면 컴플라이언스 관리자에게 통제 실패 알림.
6. Storyboard(표+지표+차트)를 익명 링크로 공유.

규칙: 상태 하나에 질문지 하나만 연결, 레코드가 그 상태로 재진입하면 이전 답이 채워진 질문지가 다시 요구됨, 일괄 처리 시 워크플로 규칙 밖 레코드는 처리 안 됨, 상태 이름을 바꿔도 Audit Trail 항목은 갱신 안 됨. [공식문서]

## 5. 피드백

- **사람의 판정 → 스크립트: 경로 없음.** False Positive로 닫힌 레코드는 Results에 남을 뿐이다. 다음 달 같은 패턴은 다시 예외가 된다. 임계값을 바꾸려면 Analytics에서 스크립트를 고쳐 **새 버전을 커밋·활성화**해야 한다(버전 n, n+1 순번). 이 버전 기록이 ACL에서 유일한 "룰 변경 이력"이다. [공식문서]
- **제외 목록도 스크립트 안.** 승인된 가맹점·반복 오탐 벤더는 감사자가 조회 테이블로 만들어 `IF NOT MATCH(...)`로 걸러야 한다.
- **지표 기반 트리거**는 통제 상태 알림이지 모델 조정이 아니다.
- IDEA/Arbutus/Alessa도 같다. IDEA "Exceptional Exceptions for Purchase Cards"(2021)는 "리스크 잠재성 기준으로 가장 관련 있는 예외를 식별"한다고만 쓰고 방식 미공개 ⚠️. Arbutus의 AI 기능(Smart Query·분류·Assistant)은 OpenAI 호출, 기본 비활성, 선택 테이블을 외부로 보냄 — 판정 학습이 아니라 질의 보조. Alessa는 "risk scoring, workflows"를 열거하나 학습 메커니즘 설명 없음. [2차][마케팅]

## 6. 검증·수치

벤더 정확도 수치는 **없다**(ACL은 도구라 주장할 수 없음). 대신 ACL을 쓴 정부·공공 감사 보고서가 적중률을 간접적으로 보여준다.

| 기관·연도 | 도구 | 모집단 | 플래그 → 확정 | 비고 | 출처 |
|---|---|---|---|---|---|
| San Diego County 2009 | ACL CCM P-Cards 모듈(2006 도입, 36 analytics) | 연 92,017건 / $34.4M, 623 카드소유자 | 36개 중 **3개가 6개월에 1만 건 초과**; "Same Amount Multiple Cards" **27,633건**(3개월 창, 전 부서 동일 가맹점·동일 금액). 부서는 자기 거래만 보여 짝을 못 봄 | 14개 모니터링 조직 중 **5개는 감사 시작 전까지 모니터링 0회**; 중앙 분석의 예외 해결 절차 매뉴얼 없음 | [정부보고서] |
| Federal Reserve OIG 2022 (CFPB) | 자체 알고리즘(정렬·그룹) | 7,037건 / $3.46M | 금지 MCC 150건(모두 A/OPC가 이미 탐지·조치), 쪼개기 의심 **36건 → 확정 0건**(한도 내), 제3자 결제 118건 모두 승인됨 | 쪼개기 룰이 "같은 카드·같은 벤더 합계 > 한도" 단순 그룹 | [정부보고서] |
| Yolo County 2019 | ACL 명시 | 미확인 | 쪼개기 의심 54건, 주말·공휴일 **1,811건** | 확정 수 미기재. 검색 스니펫 기반, PDF 403 ⚠️ | [정부보고서] |
| City of Tulsa 2023 | 자체 분석(11개 지표) | 미확인 | BPO 완료 전 거래 **91건** → 샘플 확인으로 위반 확정 | 주말·중복·쪼개기·키워드·$2,499 초과·본인 승인 포함 | [정부보고서] |
| Jacksonville OIG 2024 | 자체 | 미확인 | 주말 거래 **1,437건**, "일부는 정당할 수 있어 후속 검토 필요" | 스니펫 기반 ⚠️ | [정부보고서] |
| Univ. of Alaska | ACL CCA 월간 14 테스트(P-card 6) | 미공개 | 수치 미공개 | 로직·결과 모두 비공개 | [공식문서(기관)] |
| Alessa 고객사례(Univ. of Miami) | Alessa | 1,200 카드소유자 / $25M | 수치 없음. "연 9개월 20% 샘플 → 매월 100%" | 적중률 없음 | [마케팅] |

- **학술 실측**(Svanberg et al. 2025, 131,039건·오류 5% 라벨 데이터): 룰 기반 연속감사의 "예외 과잉"은 30년 된 문제이고 원인은 **클래스 불균형 + 룰 설계**. XGBoost + 임계 조절로 정밀도 0.65→0.73까지 올리면 재현율은 0.23→0.18로 떨어짐 — 즉 룰을 그대로 두고 "상위 n건만 보는" 운영이 가능해진다는 것이 요지. 카드 데이터가 아니라 공적연금 등록 데이터라 수치 전이는 불가. [2차·학술]
- **가격**(모두 2차 ⚠️): ACL 좌석 "연 약 $6,000" 사용자 1건 진술; VendorBenchmark 추정 기업 배포 연 $100K~400K; Arbutus ITQlick 추정 약 $400/사용자/년. 공식 가격표 없음.

## 7. 구조적 한계

1. **지식이 스크립트와 사람에 갇힌다.** 테스트 로직·임계값·제외 목록이 ACLScript 파일 안에 있고, 그걸 읽을 수 있는 사람은 조직 내 1~2명이다. 샌디에이고 보고서가 "담당자 이직 시 예외 해결 지식이 이전되지 않는다"고 적은 것이 그 증거. 룰의 근거 정책 조문은 어디에도 구조화되지 않는다.
2. **예외 수를 조절할 손잡이가 임계값 하나.** 룰은 참/거짓이라 "오늘 50건만 보겠다"가 불가능하다. 결과는 1만 건 예외(샌디에이고) 또는 쪼개기 36건 전부 오탐(연준). Svanberg가 말하는 "룰 기반 설계에는 확률 임계가 없다"는 한계 그대로.
3. **우선순위가 없다.** Priority 4값은 수동 또는 트리거 설정. 여러 테스트 동시 적중, 반복 위반자, 금액 가중 같은 축은 스크립트로 직접 계산해야 하고 기본 제공은 정렬뿐.
4. **판정이 돌아가지 않는다.** False Positive 상태는 통계용일 뿐 다음 실행에 영향이 없다. 재학습은커녕 "이 벤더는 승인됨"조차 사람이 조회 테이블을 고쳐 재커밋해야 한다.
5. **시점(point-in-time) 피처 없음.** "이 거래 시점의 카드 한도·직급·누적 사용액"을 보려면 감사자가 스냅샷 테이블을 직접 관리해야 한다. 기본 구조는 "지금 있는 마스터 테이블과 조인".
6. **Results 테이블 10만 행 한도.** 전수 거래를 올려 사후 탐색하는 용도가 아니라 예외만 올리는 설계. 무작위 샘플 검토(합격분 재검)는 기본 기능이 아니고 스크립트로 `SAMPLE` 해서 별도 테이블로 보내야 한다.
7. **운영 공백이 탐지보다 먼저 무너진다.** 샌디에이고: 도입 3년 후 14개 조직 중 5개가 한 번도 안 봄, 절차 매뉴얼 없음. 도구가 있어도 "누가 매월 열어보나"가 통제되지 않으면 예외는 쌓이기만 한다.
8. **라이선스·숙련 장벽.** ACLScript 전용 언어, Professional 에디션 로봇 1개 제한, 모듈별 별도 라이선스(Arbutus도 Hub·Results Manager 별매). 중소 조직은 데스크톱 1좌석 + 수동 실행으로 끝나는 경우가 흔하다. [2차]
9. **AX→Robots 전환으로 구형 자산 단절.** 2023년 AX 지원 종료, Analytics 16+는 AX 비호환. 10년 쌓은 분석 앱을 재커밋해야 했다. 도움말 URL도 2025~26년 재이전 중.

## 8. 우리에게 주는 것

우리 구조(YAML 룰 카탈로그 + 룰별 SQL, DuckDB, 무작위 샘플 포함 리뷰 큐, 약한 라벨 → 모델 정렬, 정책 조문 인용 증거문)와 대응시키면:

**가져올 것**
- (a) **테스트 카탈로그 그 자체.** 4.1의 20여 종은 30년간 수렴한 표준이다. 우리 `catalog.yaml`이 이 중 무엇을 빠뜨렸는지 1:1 대조표를 만들 것(특히 AP/경비 교차 중복, 여러 카드 쪼개기, 승인 간격, 연말 몰아쓰기, 단일 벤더 집중).
- (b) **임계값을 파라미터로 분리**(`//PARAM`)하고 룰 본문과 따로 둔다 — 03_Oversight 8.1-E와 같은 결론, ACL은 이를 언어 수준에서 강제한다.
- (c) **룰 버전 = 커밋 번호, 개발/운영 분리, 활성화는 복사.** 우리 룰 YAML을 git 커밋 해시로 버전 표기하고, 리뷰 결과에 "어느 룰 버전이 만든 플래그인지"를 저장한다. 사후에 "임계 바꾸기 전/후 적중률" 비교가 가능해진다.
- (d) **상태 설계**: Open 그룹(New/Open/Under Review) vs Closed 그룹(Closed/False Positive). **False Positive를 Closed와 구분**해야 룰별 오탐률이 집계된다. 상태 전환마다 질문지(= 우리의 판정 사유·조치 코드 입력폼)를 **상태에 연결**하는 방식.
- (e) **미응답 재발송(7일)·실패 알림·지표 임계 경보**라는 세 가지 운영 트리거. 샌디에이고의 "5개 부서가 안 봄"은 이 장치가 없을 때 생긴다. 우리 요약 화면에 "n일 이상 미처리 큐"를 넣는 것이 대응.
- (f) **파일 적재가 1급 경로**라는 전제. 카드사 CSV/엑셀을 바로 받는 설계는 ACL이 30년간 증명한 현실적 입력 경로다.

**피할 것**
- (a) 룰 로직·임계·제외 목록·근거 조문을 **코드 안에만** 두는 것. 우리는 YAML에 `policy_ref`, `rationale`, `threshold`, `exclusions`를 데이터로 둬 비개발자(윤경팀)가 읽고 고칠 수 있어야 한다.
- (b) 룰 참/거짓만으로 큐를 만드는 것. 예외 수 조절 손잡이가 없어 1만 건이 쌓인다. 약한 라벨 → 모델 정렬은 바로 이 Svanberg "임계 조절" 역할이며, 반드시 **룰 적중 수·반복자·금액** 피처를 함께 넣어 설명 가능하게.
- (c) 우선순위를 사람이 4값 중 고르게 하는 것. 리뷰어 시간이 우선순위 입력에 쓰이면 안 된다.
- (d) 판정이 룰로 돌아가지 않는 구조. 우리는 False Positive 집계가 룰별 오탐률 → 임계 재조정 제안(사람 승인 후 적용)으로 이어지는 **관측 가능한 경로**를 만든다.
- (e) 예외만 저장하는 구조. DuckDB에 전수를 두고 "통과분 무작위 샘플"을 큐에 섞는 우리 설계를 유지한다. ACL에선 이것이 별도 스크립트였다.
- (f) 시점 피처를 감사자 수작업에 맡기는 것. 카드 한도·직급·누적 사용액은 거래 시점 기준 스냅샷으로 피처 테이블에 고정.

### 8.1 백로그 반영 후보

| # | ACL의 장치 | 우리 현황 | 반영 | 우선 |
|---|---|---|---|---|
| A | 표준 테스트 ~20종 | catalog.yaml | 4.1 표와 1:1 대조, 누락 룰 추가(교차 중복·다카드 쪼개기·승인 간격·단일 벤더 집중) | **상** |
| B | False Positive ≠ Closed | 위반/아님/보류 | "아님" 사유를 **룰 오탐 / 정당 사유 확인** 두 갈래로 분리해 룰별 오탐률 산출 | **상** |
| C | 룰 버전 커밋·활성화 | 없음 | 플래그 행에 `rule_version`(git hash) 저장, 임계 변경 전후 비교 뷰 | 중 |
| D | 미응답 7일 재발송 트리거 | 보류 무기한(Oversight C와 겹침) | 보류 기한 + 요약에 기한 초과 건수 | 상(기존) |
| E | `//PARAM` 임계 분리 | thresholds.yaml 예정(Oversight E) | 동일. 추가로 `exclusions.yaml`(승인 가맹점·반복 오탐 벤더) 분리 | 중 |

## 9. 출처

- [공식문서] Robots — Creating a robot task — https://help.diligentoneplatform.com/helpdocs/d1p/en-us/Content/robots/building_automation/creating_scheduling_tasks.htm
- [공식문서] Robots — Development mode and production mode — https://help.diligentoneplatform.com/helpdocs/d1p/en-us/Content/robots/robots_dev_mode_prod_mode.htm
- [공식문서] Robots — Committing ACL scripts to Robots(버전 번호) — https://help.highbond.com/helpdocs/highbond/en-us/Content/global_topics/robots/committing_scripts_from_analytics_to_robots.htm
- [공식문서] Robots — Working with files in a robot(엑셀·CSV 수동 업로드) — https://help.highbond.com/helpdocs/highbond/en-us/Content/robots/working_with_data/working_with_files_hb_wf_robot.htm
- [공식문서] Analytics 16 — Analytic scripts(AX 지원 종료 2023-01-01) — https://help.highbond.com/helpdocs/analytics/16/en-us/Content/analytics/scripting/analytic_development/analytic_scripts.htm
- [공식문서] Analytics 14.1 — Analytic headers and tags — https://help.highbond.com/helpdocs/analytics/141/scripting-guide/en-us/Content/lang_ref/analytic_tags/analytic_header_syntax.htm
- [공식문서] AX 14 — Writing scripts for Analytics Exchange(`//PARAM v_top N`, `%v_top%` 예제) — https://help.highbond.com/helpdocs/analytics-exchange/14/user-guide/en-us/Content/global_topics/analysis_apps/writing_scripts_ax.htm
- [공식문서] Analytics 17 — EXPORT command(ACLGRC, 10만 행·500필드·256자) — https://help.diligentoneplatform.com/helpdocs/analytics-17/en-us/Content/analytics/scripting/commands/r_export.htm
- [공식문서] Analytics 17 — DUPLICATES command — https://help.diligentoneplatform.com/helpdocs/analytics-17/en-us/Content/analytics/scripting/commands/r_duplicates.htm
- [공식문서] Analytics 17 — BENFORD command — https://help.diligentoneplatform.com/helpdocs/analytics-17/en-us/Content/analytics/scripting/commands/r_benford.htm
- [공식문서] Results — Remediating records(기본 상태 5종, 우선순위 4종, Assignee·Workflow Group) — https://help.diligentoneplatform.com/helpdocs/d1p/en-us/Content/results/records/remediating.html
- [공식문서] Results — Configuring record statuses(Open/Closed 그룹) — https://help.diligentoneplatform.com/helpdocs/d1p/en-us/Content/administration/results/config/record_status.html
- [공식문서] Results — Configuring record priorities — https://help.highbond.com/helpdocs/highbond/en-us/Content/administration/results/config/record_priority.htm
- [공식문서] Results — Linking record statuses to questionnaires — https://help.diligentoneplatform.com/helpdocs/d1p/en-us/Content/results/records/status_questionnaires.htm
- [공식문서] Results — Triggering actions from metrics — https://help.highbond.com/helpdocs/highbond/en-us/Content/results/metrics/triggering_from_metrics.htm
- [공식문서] 연속감시 솔루션 가이드 — Remediating and reporting exceptions(P-card 월간 예시, 7일 재발송) — https://help.diligentoneplatform.com/helpdocs/d1p/en-us/Content/get_started/solution_guides/continuous_monitoring/remediating_and_reporting_exceptions.htm
- [공식문서] 튜토리얼 — Automating a remediation workflow(답 "No" → Critical 격상·배정) — https://help.diligentoneplatform.com/helpdocs/d1p/en-us/Content/get_started/tutorials/automating_remediation.htm
- [공식문서] Analytics 16 — Publishing data to Results — https://help.highbond.com/helpdocs/analytics/16/en-us/Content/analytics/sharing_extending/highbond/results.htm
- [마케팅] Diligent 블로그, "How to monitor T&E expenses with exception reports and analytics"(12종, 2023-04-23) — https://www.diligent.com/resources/blog/travel-and-entertainment-expense-analytics
- [마케팅] Diligent, "10 ways to identify accounts payable fraud"(2019-06-11, 한도 5% 이내·MOD) — https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud
- [마케팅] Galvanize 보도자료 2019-06-11, HighBond ML — https://www.diligent.com/news/galvanize-drives-grc-industry-transformation-machine-learning-governance-professionals-highbond
- [마케팅] Diligent ACL Analytics 제품 페이지("ACL 스크립트 완전 호환") — https://www.diligent.com/de/products/acl-analytics
- [2차] Accounting Today 2013-12-04, "ACL Offers Purchase Card Fraud Product"(10 analytics, 20+ risks) — https://www.accountingtoday.com/news/acl-offers-purchase-card-fraud-product
- [정부보고서] County of San Diego OAAS, Procurement Card Program Audit A09-001(2009-09; ACL CCM 36 analytics, 27,633 exceptions) — https://www.sandiegocounty.gov/content/dam/sdc/auditor/audit/fy0910/ProcurementCardProgramAudit.pdf
- [정부보고서] Federal Reserve OIG, CFPB Purchase Card Risk Assessment(2022-08; 7,037건, 쪼개기 36→0) — https://oig.federalreserve.gov/reports/bureau-purchase-card-risk-assessment-aug2022.pdf
- [정부보고서] Yolo County Internal Audit, Purchase Card(2019; ACL, 54 splits, 1,811 weekend — PDF 403, 스니펫 기반 ⚠️) — https://yolocounty.gov/home/showpublisheddocument/80487/638532708917400000
- [정부보고서] City of Tulsa, Purchasing Card Risk Review(2023-05; 11 indicators, 91건) — https://www.cityoftulsa.org/media/21904/purchasing-card-risk-review-5-2023.pdf
- [정부보고서] Jacksonville OIG 24-OA-0003(2024; 1,437 weekend — 503, 스니펫 기반 ⚠️) — https://www.jacksonville.gov/getattachment/Departments/Inspector-General/Reports/24-OA-0003-City-Purchase-Card-Summary-Analysis.pdf.aspx?lang=en-US
- [정부보고서] Oklahoma OMES, Statewide Purchase Card Continuous Monitoring Report(2013; **본문 열람 실패** ⚠️) — https://ok.gov/DCS/documents/Audit_June_24_2013-02_Oklahoma_Statewide_Purchase_Card_Continuous_Monitoring_Report_07-11-2011_to_11-05-2012.pdf
- [공식문서(기관)] University of Alaska, Continuous Controls Auditing Using ACL(14 tests) — https://www.alaska.edu/audit/tools_of_the_trade/continuous-controls-auditing/
- [2차·학술] Svanberg et al., "Addressing the Exception Prioritization Problem in Continuous Auditing Systems With Thresholding", ISAFM 32:e70022(2025) — https://doi.org/10.1002/isaf.70022
- [마케팅] Alessa, P-Card Program Analytics Guide(약 40 tests, Univ. of Miami 사례) — https://alessa.com/wp-content/uploads/2021/09/Alessa_P-card_analytics_guide_08.pdf
- [마케팅] CaseWare Tech Tips Fall 2021, "Exceptional Exceptions for Purchase Cards" — https://insights.caseware.com/tech-tips-fall-2021
- [2차] ideascripting.com, Same-Same-Different Test(IDEAScript, Nigrini ch.12, IDEA ≤8.5 Duplicate Key Exclusion 버그) — https://www.ideascripting.com/Same-Same-Different-Test
- [마케팅] Arbutus Software 홈(Analyzer·Hub·Results Manager) — https://www.arbutussoftware.com/
- [2차] internalauditguide.com, Arbutus Analyzer Review(2026-09; ACL Projects 커넥터, "95% 무수정 실행" 출처 추적 불가, OpenAI 기반 AI 옵트인) — https://internalauditguide.com/2026/09/arbutus-analyzer-review/
- [2차] Sepia Solutions, Arbutus Results Manager — https://www.sepiasolutions.net/software/arbutus-analytics/results-manager/
- [2차] ITCentralStation/PeerSpot ACL Analytics pricing(연 $6,000 진술) — https://www.itcentralstation.com/products/acl-analytics-pricing
- [2차] VendorBenchmark, Galvanize(Diligent) Pricing(추정치) — https://vendorbenchmark.com/vendors/galvanize-diligent-pricing
- 미발견: ACL P-Card Fraud 패키지(2013) 테스트 10개 이름, HighBond ML 기능의 공식 문서, Results 기본 Priority 초기값, Arbutus ACL 호환률 1차 출처, 한국 리셀러·국내 공공기관 ACL 사용 보고서.
