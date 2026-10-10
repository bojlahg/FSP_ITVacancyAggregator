import { expect, type Page, test } from "@playwright/test";

/** Пароль одноразовых аккаунтов e2e: домен example.com почту не принимает, аккаунты живут только в этой БД. */
export const E2E_PASSWORD = "e2e-password-2026";

/**
 * Пароль служебного кандидата: как в генераторе (backend/app/core/config.py) — E2E_CANDIDATE_PASSWORD,
 * а если он пуст — DEMO_SEED_PASSWORD. Пароля в коде нет: без переменной тест падает с понятной ошибкой.
 */
function candidatePassword(): string {
  const password = process.env.E2E_CANDIDATE_PASSWORD || process.env.DEMO_SEED_PASSWORD;
  if (!password) {
    throw new Error(
      "Задайте E2E_CANDIDATE_PASSWORD (или DEMO_SEED_PASSWORD) — тот же, что в .env стенда (docs/deploy.md §5.5)",
    );
  }
  return password;
}

/** Служебный кандидат из генератора демо-данных (backend/seed/generate.py). */
export const E2E_CANDIDATE = {
  email: process.env.E2E_CANDIDATE_EMAIL ?? "e2e-candidate@itscout.ru",
  // Читается при входе, а не при импорте: тесты без кандидата e2e запускаются и без пароля
  get password(): string {
    return candidatePassword();
  },
  displayName: "Тест А.",
  // Полное имя после раскрытия контактов: «Фамилия Имя»
  fullName: /Автотестов Тест|Тест Автотестов/,
};

export function runId(): string {
  return `${Date.now()}${Math.floor(Math.random() * 1000)}`;
}

export function uniqueEmail(role: "candidate" | "employer", id: string): string {
  return `e2e-${role}-${id}@example.com`;
}

/** Ссылка бокового меню кабинета — переходы внутри SPA, без лишних перезагрузок (refresh-токен под rate limit). */
export async function openSection(page: Page, label: string): Promise<void> {
  await page.getByRole("navigation", { name: "Разделы кабинета" }).getByRole("link", { name: label, exact: true }).click();
}

export async function registerUser(page: Page, role: "candidate" | "employer", email: string): Promise<void> {
  await page.goto(`/register?role=${role}`);
  await expect(page.getByRole("radio", { name: role === "candidate" ? "Я кандидат" : "Я работодатель" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill(E2E_PASSWORD);
  await page.getByRole("checkbox", { name: /обработку персональных данных/ }).check();
  if (role === "candidate") await page.getByRole("checkbox", { name: /публикацию профиля/ }).check();
  const registered = page.waitForResponse(
    (response) => response.request().method() === "POST" && response.url().endsWith("/api/v1/auth/register"),
  );
  await page.getByRole("button", { name: "Зарегистрироваться" }).click();
  const { user } = await (await registered).json();
  // При EMAIL_VERIFICATION_REQUIRED кабинет открывается только по ссылке из письма, а example.com почту не принимает
  test.skip(
    user.email_verification_required,
    "На стенде включено обязательное подтверждение почты (EMAIL_VERIFICATION_REQUIRED): сценарий с регистрацией пропущен",
  );
  await expect(page).toHaveURL(role === "candidate" ? /\/candidate\/onboarding$/ : /\/employer\/company$/);
}

export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill(password);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Разделы кабинета" })).toBeVisible();
}

/** «220 000 – 260 000 ₽» — Intl разделяет разряды неразрывными пробелами. */
export function salaryRangePattern(from: number, to: number): RegExp {
  const group = (value: number) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, "\\s");
  return new RegExp(`${group(from)}\\s–\\s${group(to)}\\s₽`);
}
