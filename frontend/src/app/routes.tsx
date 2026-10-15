import { createBrowserRouter } from "react-router"
import {
  AppShell,
  CheckPage,
  DashboardPage,
  HomePage,
  NotFoundPage,
  ReportPage,
  ShopPage,
} from "@/pages"

export const router = createBrowserRouter([
  {
    path: "/",
    Component: AppShell,
    children: [
      { index: true, Component: HomePage },
      { path: "dashboard", Component: DashboardPage },
      { path: "shop/:id", Component: ShopPage },
      { path: "report/:id", Component: ReportPage },
      { path: "check", Component: CheckPage },
      { path: "*", Component: NotFoundPage },
    ],
  },
])
