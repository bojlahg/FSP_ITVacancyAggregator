import type { ComponentType } from "react";
import { createBrowserRouter } from "react-router";
import { GuestOnly, RequireRole } from "@/app/guards";
import { RouteFallback } from "@/components/RouteFallback";
import PublicLayout from "@/layouts/PublicLayout";
import NotFoundPage from "@/pages/NotFoundPage";
import LandingPage from "@/pages/public/LandingPage";
import RouteErrorPage from "@/pages/RouteErrorPage";

// Кабинеты и формы грузятся лениво: лендинг не тянет код кабинетов, zod и react-hook-form.
function lazyPage(load: () => Promise<{ default: ComponentType }>) {
  return async () => ({ Component: (await load()).default });
}

/** Вход и регистрация — только для гостей (см. GuestOnly). */
function lazyGuestPage(load: () => Promise<{ default: ComponentType }>) {
  return async () => {
    const { default: Page } = await load();
    return {
      Component: () => (
        <GuestOnly>
          <Page />
        </GuestOnly>
      ),
    };
  };
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
          { path: "login", lazy: lazyGuestPage(() => import("@/pages/public/LoginPage")) },
          { path: "register", lazy: lazyGuestPage(() => import("@/pages/public/RegisterPage")) },
          { path: "verify-email", lazy: lazyPage(() => import("@/pages/public/VerifyEmailPage")) },
          { path: "expert/join", lazy: lazyPage(() => import("@/pages/public/ExpertJoinPage")) },
          { path: "how-it-works", lazy: lazyPage(() => import("@/pages/public/HowItWorksPage")) },
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
              { path: "debug", lazy: lazyPage(() => import("@/pages/debug/DebugPage")) },
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
              { path: "debug", lazy: lazyPage(() => import("@/pages/debug/DebugPage")) },
            ],
          },
        ],
      },
      {
        path: "expert",
        element: <RequireRole role="expert" />,
        children: [
          {
            lazy: lazyPage(() => import("@/layouts/ExpertLayout")),
            children: [
              { index: true, lazy: lazyPage(() => import("@/pages/expert/ExpertPage")) },
              { path: "debug", lazy: lazyPage(() => import("@/pages/debug/DebugPage")) },
            ],
          },
        ],
      },
      {
        path: "admin",
        element: <RequireRole role="admin" />,
        children: [
          {
            lazy: lazyPage(() => import("@/layouts/AdminLayout")),
            children: [
              { index: true, lazy: lazyPage(() => import("@/pages/admin/AdminReportsPage")) },
              { path: "debug", lazy: lazyPage(() => import("@/pages/debug/DebugPage")) },
            ],
          },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
