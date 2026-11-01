import { createRootRoute, createRoute, createRouter, Outlet, redirect } from "@tanstack/react-router"
import { AppShell } from "@/components/app-shell"
import { ReviewPage } from "@/pages/review"
import { SummaryPage } from "@/pages/summary"
import { QueuePage } from "@/pages/queue"
import { RulesPage } from "@/pages/rules"

const rootRoute = createRootRoute({ component: () => (<AppShell><Outlet /></AppShell>) })
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", beforeLoad: () => { throw redirect({ to: "/review" }) } })
const reviewRoute = createRoute({ getParentRoute: () => rootRoute, path: "/review", component: ReviewPage })
const summaryRoute = createRoute({ getParentRoute: () => rootRoute, path: "/summary", component: SummaryPage })
const queueRoute = createRoute({ getParentRoute: () => rootRoute, path: "/queue", component: QueuePage })
const rulesRoute = createRoute({ getParentRoute: () => rootRoute, path: "/rules", component: RulesPage })

export const router = createRouter({ routeTree: rootRoute.addChildren([indexRoute, reviewRoute, summaryRoute, queueRoute, rulesRoute]) })
declare module "@tanstack/react-router" { interface Register { router: typeof router } }
