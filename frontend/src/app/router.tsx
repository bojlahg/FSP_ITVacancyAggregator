import type { ComponentType } from "react";
import { createBrowserRouter } from "react-router";
import { GuestOnly, RequireRole } from "@/app/guards";
import { TitledOutlet } from "@/app/DocumentTitle";
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
    element: <TitledOutlet />,
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement: <RouteFallback />,
    children: [
      {
        element: <PublicLayout />,
        children: [
          { index: true, element: <LandingPage /> },
          { path: "login", handle: { title: "Вход" }, lazy: lazyGuestPage(() => import("@/pages/public/LoginPage")) },
          { path: "register", handle: { title: "Регистрация" }, lazy: lazyGuestPage(() => import("@/pages/public/RegisterPage")) },
          { path: "verify-email", handle: { title: "Подтверждение почты" }, lazy: lazyPage(() => import("@/pages/public/VerifyEmailPage")) },
          { path: "expert/join", handle: { title: "Вход для экспертов" }, lazy: lazyPage(() => import("@/pages/public/ExpertJoinPage")) },
          { path: "how-it-works", handle: { title: "Как работает тест" }, lazy: lazyPage(() => import("@/pages/public/HowItWorksPage")) },
          { path: "legal/:slug", handle: { title: "Документы" }, lazy: lazyPage(() => import("@/pages/public/LegalPage")) },
        ],
      },
      {
        path: "candidate",
        element: <RequireRole role="candidate" />,
        children: [
          {
            lazy: lazyPage(() => import("@/layouts/CandidateLayout")),
            children: [
              { index: true, handle: { title: "Кабинет кандидата" }, lazy: lazyPage(() => import("@/pages/candidate/CandidateDashboardPage")) },
              { path: "onboarding", handle: { title: "Онбординг" }, lazy: lazyPage(() => import("@/pages/candidate/OnboardingPage")) },
              { path: "test/:attemptId", handle: { title: "Тест" }, lazy: lazyPage(() => import("@/pages/candidate/TestPage")) },
              { path: "test/:attemptId/result", handle: { title: "Результат теста" }, lazy: lazyPage(() => import("@/pages/candidate/TestResultPage")) },
              { path: "profile", handle: { title: "Профиль и резюме" }, lazy: lazyPage(() => import("@/pages/candidate/ProfilePage")) },
              { path: "grade", handle: { title: "Категория и грейд" }, lazy: lazyPage(() => import("@/pages/candidate/GradePage")) },
              { path: "invitations", handle: { title: "Приглашения" }, lazy: lazyPage(() => import("@/pages/candidate/CandidateInvitationsPage")) },
              { path: "vacancies", handle: { title: "Вакансии" }, lazy: lazyPage(() => import("@/pages/candidate/CandidateVacanciesPage")) },
              { path: "applications", handle: { title: "Отклики" }, lazy: lazyPage(() => import("@/pages/candidate/ApplicationsPage")) },
              { path: "tasks", handle: { title: "Задания" }, lazy: lazyPage(() => import("@/pages/candidate/CandidateTasksPage")) },
              { path: "challenges", handle: { title: "Челленджи" }, lazy: lazyPage(() => import("@/pages/candidate/CandidateChallengesPage")) },
              { path: "challenges/:attemptId", handle: { title: "Челлендж" }, lazy: lazyPage(() => import("@/pages/candidate/ChallengeRunPage")) },
              { path: "settings", handle: { title: "Настройки" }, lazy: lazyPage(() => import("@/pages/candidate/SettingsPage")) },
              { path: "debug", handle: { title: "Отладка" }, lazy: lazyPage(() => import("@/pages/debug/DebugPage")) },
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
              { index: true, handle: { title: "Кабинет работодателя" }, lazy: lazyPage(() => import("@/pages/employer/EmployerDashboardPage")) },
              { path: "company", handle: { title: "Профиль компании" }, lazy: lazyPage(() => import("@/pages/employer/CompanyPage")) },
              { path: "needs", handle: { title: "Потребности" }, lazy: lazyPage(() => import("@/pages/employer/NeedsPage")) },
              { path: "needs/new", handle: { title: "Новая потребность" }, lazy: lazyPage(() => import("@/pages/employer/NeedNewPage")) },
              { path: "needs/:needId", handle: { title: "Подборка по потребности" }, lazy: lazyPage(() => import("@/pages/employer/NeedDetailPage")) },
              { path: "needs/:needId/edit", handle: { title: "Редактирование потребности" }, lazy: lazyPage(() => import("@/pages/employer/NeedEditPage")) },
              { path: "search", handle: { title: "Поиск по базе" }, lazy: lazyPage(() => import("@/pages/employer/SearchPage")) },
              { path: "categories", handle: { title: "Каталог категорий" }, lazy: lazyPage(() => import("@/pages/employer/CategoriesPage")) },
              { path: "candidates/:candidateId", handle: { title: "Карточка кандидата" }, lazy: lazyPage(() => import("@/pages/employer/CandidateCardPage")) },
              { path: "invitations", handle: { title: "Приглашения" }, lazy: lazyPage(() => import("@/pages/employer/EmployerInvitationsPage")) },
              { path: "vacancies", handle: { title: "Вакансии и отклики" }, lazy: lazyPage(() => import("@/pages/employer/EmployerVacanciesPage")) },
              { path: "vacancy-test", handle: { title: "Проверка под вакансию" }, lazy: lazyPage(() => import("@/pages/employer/VacancyTestPage")) },
              { path: "tasks", handle: { title: "Задания" }, lazy: lazyPage(() => import("@/pages/employer/EmployerTasksPage")) },
              { path: "challenges", handle: { title: "Челленджи" }, lazy: lazyPage(() => import("@/pages/employer/EmployerChallengesPage")) },
              { path: "debug", handle: { title: "Отладка" }, lazy: lazyPage(() => import("@/pages/debug/DebugPage")) },
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
              { index: true, handle: { title: "Разметка и итоги" }, lazy: lazyPage(() => import("@/pages/expert/ExpertPage")) },
              { path: "debug", handle: { title: "Отладка" }, lazy: lazyPage(() => import("@/pages/debug/DebugPage")) },
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
              { index: true, handle: { title: "Жалобы" }, lazy: lazyPage(() => import("@/pages/admin/AdminReportsPage")) },
              { path: "appeals", handle: { title: "Обращения по грейду" }, lazy: lazyPage(() => import("@/pages/admin/AppealsPage")) },
              { path: "debug", handle: { title: "Отладка" }, lazy: lazyPage(() => import("@/pages/debug/DebugPage")) },
            ],
          },
        ],
      },
      { path: "*", handle: { title: "Страница не найдена" }, element: <NotFoundPage /> },
    ],
  },
]);
