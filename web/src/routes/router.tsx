import { createRootRoute, createRoute, createRouter, Outlet, redirect } from "@tanstack/react-router"
import { AppShell } from "@/components/app-shell"
import { ReviewLayout, ReviewEmpty, ReviewCase } from "@/pages/review"
import { RulesLayout, RulesEmpty, RuleDetail } from "@/pages/rules"
import { DataPage } from "@/pages/data"
import { SummaryPage } from "@/pages/summary"
import { GalleryPage } from "@/pages/gallery"

// URL is the only UI state: section = first segment, selection = param. See docs/REVIEW_SCREEN.md.
const rootRoute = createRootRoute({ component: () => (<AppShell><Outlet /></AppShell>) })
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", beforeLoad: () => { throw redirect({ to: "/review" }) } })

const reviewRoute = createRoute({ getParentRoute: () => rootRoute, path: "/review", component: ReviewLayout })
const reviewIndexRoute = createRoute({ getParentRoute: () => reviewRoute, path: "/", component: ReviewEmpty })
const reviewCaseRoute = createRoute({ getParentRoute: () => reviewRoute, path: "$txId", component: ReviewCase })

const dataRoute = createRoute({ getParentRoute: () => rootRoute, path: "/data", component: DataPage })

const rulesRoute = createRoute({ getParentRoute: () => rootRoute, path: "/rules", component: RulesLayout })
const rulesIndexRoute = createRoute({ getParentRoute: () => rulesRoute, path: "/", component: RulesEmpty })
const ruleDetailRoute = createRoute({ getParentRoute: () => rulesRoute, path: "$ruleId", component: RuleDetail })

const summaryRoute = createRoute({ getParentRoute: () => rootRoute, path: "/summary", component: SummaryPage })
// Dev-only design comparison page; not in the rail.
const galleryRoute = createRoute({ getParentRoute: () => rootRoute, path: "/gallery", component: GalleryPage })

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    indexRoute,
    reviewRoute.addChildren([reviewIndexRoute, reviewCaseRoute]),
    dataRoute,
    rulesRoute.addChildren([rulesIndexRoute, ruleDetailRoute]),
    summaryRoute,
    galleryRoute,
  ]),
})
declare module "@tanstack/react-router" { interface Register { router: typeof router } }
