import type { ComponentType } from "react";
import { createBrowserRouter } from "react-router";
import { GuestOnly, RequireRole } from "@/app/guards";
import { RouteFallback } from "@/components/RouteFallback";
import PublicLayout from "@/layouts/PublicLayout";
import NotFoundPage from "@/pages/NotFoundPage";
import LandingPage from "@/pages/public/LandingPage";
import LoginPage from "@/pages/public/LoginPage";
import RegisterPage from "@/pages/public/RegisterPage";
import VerifyEmailPage from "@/pages/public/VerifyEmailPage";
import RouteErrorPage from "@/pages/RouteErrorPage";

// Кабинеты грузятся лениво: лендинг и вход не тянут код кабинетов.
function lazyPage(load: () => Promise<{ default: ComponentType }>) {
  return async () => ({ Component: (await load()).default });
}

export const router = createBrowserRouter([
  {
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement: <RouteFallback />,
    children: [
      {
        element: <PublicLayout />,
        children: [
          { index: true, element: <LandingPage /> },
          {
            path: "login",
            element: (
              <GuestOnly>
                <LoginPage />
              </GuestOnly>
            ),
          },
          {
            path: "register",
            element: (
              <GuestOnly>
                <RegisterPage />
              </GuestOnly>
            ),
          },
          { path: "verify-email", element: <VerifyEmailPage /> },
        ],
      },
      {
        path: "candidate",
        element: <RequireRole role="candidate" />,
        children: [
          {
            lazy: lazyPage(() => import("@/layouts/CandidateLayout")),
            children: [
              { index: true, lazy: lazyPage(() => import("@/pages/candidate/CandidateDashboardPage")) },
              { path: "onboarding", lazy: lazyPage(() => import("@/pages/candidate/OnboardingPage")) },
              { path: "test/:attemptId", lazy: lazyPage(() => import("@/pages/candidate/TestPage")) },
              { path: "test/:attemptId/result", lazy: lazyPage(() => import("@/pages/candidate/TestResultPage")) },
              { path: "profile", lazy: lazyPage(() => import("@/pages/candidate/ProfilePage")) },
              { path: "grade", lazy: lazyPage(() => import("@/pages/candidate/GradePage")) },
              { path: "invitations", lazy: lazyPage(() => import("@/pages/candidate/CandidateInvitationsPage")) },
              { path: "vacancies", lazy: lazyPage(() => import("@/pages/candidate/CandidateVacanciesPage")) },
              { path: "applications", lazy: lazyPage(() => import("@/pages/candidate/ApplicationsPage")) },
              { path: "tasks", lazy: lazyPage(() => import("@/pages/candidate/CandidateTasksPage")) },
              { path: "settings", lazy: lazyPage(() => import("@/pages/candidate/SettingsPage")) },
            ],
          },
        ],
      },
      {
        path: "employer",
        element: <RequireRole role="employer" />,
        children: [
          {
            lazy: lazyPage(() => import("@/layouts/EmployerLayout")),
            children: [
              { index: true, lazy: lazyPage(() => import("@/pages/employer/EmployerDashboardPage")) },
              { path: "company", lazy: lazyPage(() => import("@/pages/employer/CompanyPage")) },
              { path: "needs", lazy: lazyPage(() => import("@/pages/employer/NeedsPage")) },
              { path: "needs/new", lazy: lazyPage(() => import("@/pages/employer/NeedNewPage")) },
              { path: "needs/:needId", lazy: lazyPage(() => import("@/pages/employer/NeedDetailPage")) },
              { path: "needs/:needId/edit", lazy: lazyPage(() => import("@/pages/employer/NeedEditPage")) },
              { path: "search", lazy: lazyPage(() => import("@/pages/employer/SearchPage")) },
              { path: "categories", lazy: lazyPage(() => import("@/pages/employer/CategoriesPage")) },
              { path: "candidates/:candidateId", lazy: lazyPage(() => import("@/pages/employer/CandidateCardPage")) },
              { path: "invitations", lazy: lazyPage(() => import("@/pages/employer/EmployerInvitationsPage")) },
              { path: "vacancies", lazy: lazyPage(() => import("@/pages/employer/EmployerVacanciesPage")) },
              { path: "vacancy-test", lazy: lazyPage(() => import("@/pages/employer/VacancyTestPage")) },
              { path: "tasks", lazy: lazyPage(() => import("@/pages/employer/EmployerTasksPage")) },
            ],
          },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
