import type { ComponentType } from "react"
import { S01Data } from "./S01Data"
import { S02Shell } from "./S02Shell"
export interface GallerySection { id: string; title: string; description: string; status: "done" | "wip" | "todo"; component: ComponentType }
export const sections: GallerySection[] = [
  { id: "01", title: "가짜 데이터", description: "실제 DB 거래 6건: 규칙 4건(노래방 #11012, 분할결제 짝, 참고 1건), 모델 추천 1건, 무작위 표본 1건. 서비스 함수 출력과 같은 모양.", status: "done", component: S01Data },
  { id: "02", title: "레이아웃 틀", description: "상단 바 + 좌 목록 / 우 케이스 패널 분할. 패널 경계를 끌어 크기를 바꿀 수 있다. 내용은 다음 조각에서 채운다.", status: "done", component: S02Shell },
]
