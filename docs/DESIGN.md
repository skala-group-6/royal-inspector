# 디자인 규칙 — 선 대신 면·여백·글자 위계 (2026-11-04)

결정 과정: `web/src/pages/gallery.tsx`(`/gallery`)에서 네 안을 비교해 **제안 라이트 + 다크 A(카드가 기본 배경)** 채택.

## 1. 원칙
**영역은 면의 밝기와 여백으로 나눈다. 선은 쓰지 않는다.**
선이 허용되는 곳은 셋뿐: 입력창 테두리, 포커스 표시, 드롭다운 메뉴 안의 그룹 구분, 데이터 표의 열 구분. shadcn `components/ui/`의 기본 동작은 그대로 둔다.

## 2. 면의 층 (토큰: `web/src/index.css`)
규칙 하나: **카드는 기본 배경. 바탕은 카드에서 한 단계 멀게, 패널은 그 중간, 선택은 한 단계 더.** 라이트·다크가 같은 규칙을 따른다.

| 토큰 | 클래스 | 쓰는 곳 | 라이트 L | 다크 L |
|---|---|---|---|---|
| `--surface-base` (= `--sidebar`) | `bg-surface-base` | 레일, 헤더 띠, 앱 바탕 | 0.955 | 0.218 |
| `--surface-card` (= `--background`) | `bg-surface-card` | 작업 카드 | 1.000 | 0.148 |
| `--surface-panel` | `bg-surface-panel` | 카드 안 목록 패널, 근거 묶음 | 0.982 | 0.178 |
| `--surface-hover` | `hover:bg-surface-hover` | 목록 행 호버 | 0.962 | 0.215 |
| `--surface-selected` | `data-active:bg-surface-selected` | 선택된 행 | 0.940 | 0.255 |
| `--sidebar-accent` | (shadcn 내부) | 레일 아이콘 호버·활성 | 0.925 | 0.275 |

색은 이 토큰으로만 지정한다. 화면 코드에서 `bg-[oklch(...)]`, `bg-muted`로 층을 흉내 내지 않는다.

## 3. 글자 위계 (`@utility type-*`)
| 클래스 | 정의 | 쓰는 곳 |
|---|---|---|
| `type-title` | text-base, semibold | 패널·섹션 제목 |
| `type-label` | text-sm, medium | 행의 주 텍스트, 헤더 제목 |
| `type-value` | text-sm, medium, tabular-nums | 금액 등 숫자 |
| `type-meta` | text-xs, muted | 요약 줄, 날짜·가맹점, 보조 정보 |
`text-*` 대신 `type-*` 접두사를 쓰는 이유: `cn()`(tailwind-merge)이 `text-*`를 글자색으로 오인해 다른 색 클래스를 지울 수 있다.

## 4. 간격 (4px 격자)
- 묶음 안 요소 사이: 2~4px (`gap-0.5`, `gap-1`)
- 목록 행 사이: 2px + 행 안쪽 여백 `px-2.5 py-2`
- 제목과 내용 사이: 4~8px
- 묶음 사이: 16~24px
- 카드 바깥 여백: 8px (`m-2`), 카드 모서리 `rounded-lg`(10px), 행 모서리 `rounded-lg`

## 5. 공용 부품 (`web/src/components/layout/list.tsx`)
| 부품 | 역할 |
|---|---|
| `SectionTitle` | 패널 제목 + 오른쪽 액션 자리 |
| `ListMeta` | 제목 아래 요약 줄 |
| `ListGroup` | 행 묶음. 패널 가장자리에서 안쪽으로 들여 둥근 배경이 행으로 읽히게 |
| `ListItem` | 행 하나. 호버·선택은 배경으로만. `asChild`로 라우터 `Link` 렌더 |
새 목록은 이 부품으로 만든다. 행마다 `border-b`를 쓰지 않는다.

## 6. 셸
레일(`variant="sidebar"`, 접힘 상태 고정 48px, shadcn 기본 `--sidebar-width-icon` 3rem 유지. 패널 표시는 별도 상태 `panel-state.tsx`)과 헤더 띠(40px)는 `surface-base`. 그 위에 `surface-card` 카드 하나, 안에 `surface-panel` 목록 패널 + 메인. 치수는 `web/src/components/app-shell.tsx`의 `SIZES`. 아이콘 열 변수는 줄이지 않는다(메뉴 버튼 32px + 패딩 16px와 결합돼 있어 깨짐). 구조 상세: `docs/REVIEW_SCREEN.md` 셸 구조.

## 7. 검사
`tests/test_design_rules.py`가 `web/src`(단, `components/ui/`와 `pages/gallery.tsx` 제외)에서 다음을 찾으면 실패한다: 구분용 테두리 클래스(`border`, `border-t/r/b/l/x/y`), `divide-*`, `Separator`(드롭다운 메뉴의 `DropdownMenuSeparator`는 허용), 왼쪽 막대 선택 표시(`shadow-[inset`). 테두리를 없애는 `border-*-0`은 허용.

## 8. 차트 (recharts + shadcn chart, `dataviz` 스킬 규칙 적용)
- "한 값을 기준과 견준다"(이 건 vs 본인 평소 vs 동료 평소)는 **가로 막대 3개 + 끝 라벨**(shadcn Bar Horizontal + Label). 띠·눈금·로그축이 섞인 불릿·상자 그림은 쓰지 않는다(2026-11-06, 갤러리 비교 후). 분포 자체를 보여줄 때는 실제 거래를 점으로(Scatter 스트립), 이 건만 강조색.
- **차트는 판단 질문 하나에 하나.** 케이스 패널의 세 질문(평소 대비·그날·반복)에만. 점수·개수·비율 하나짜리 값은 숫자로.
- **숫자 병기.** 그림 옆에 항상 정확한 값(이 건, 중앙값, 배수, 상위 %). 그림은 속도, 숫자는 정확.
- **색은 역할로만.** 이 건·위반 확정 = `destructive`(상태색), 나머지 마크 = `muted-foreground`(비강조), 면 = `surface-*`. `--chart-1..5`는 쓰지 않는다. 색만으로 뜻을 전하지 않는다: 범례 글자, 라벨, 툴팁 병행.
- **마크 규격.** 막대 ≤24px·위 모서리 4px, 점 ≥8px(r≥4)에 면색 2px 링, 격자선은 `surface-selected` 1px, 축선 없음. 누적 막대의 구분은 면색 2px 스트로크(선이 아니라 간격).
- **라벨은 선택적으로.** 최댓값 하나만 직접 라벨, 나머지는 툴팁. 툴팁은 면 카드(`surface-card`, 그림자).
- **빈 상태 문구.** 표본 5건 미만이면 분포 띠 대신 "본인 과거 n건 — 비교 보류", 출입 기록 없으면 "사옥 출입 기록 없음".
- **검증 결과(2026-11-04).** `validate_palette.js`로 `destructive`+`muted-foreground`를 라이트·다크 표면에서 확인: 색각 이상·정상 시력 분리·대비 모두 통과. "채도 바닥" 실패는 비강조 회색을 의도한 것이고(범주 팔레트가 아니라 상태+중립), 다크의 밝기 대역 경고는 상태색 토큰을 그대로 쓴 결과 — 범례·라벨 병기로 보완. 번들: 차트 3개는 `React.lazy`로 분리.
