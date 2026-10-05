import { expect, type Page, test } from "@playwright/test";

/**
 * Адаптивная вёрстка: на ширине телефона ни один экран кабинетов не прокручивается по горизонтали.
 * Только чтение — вход демо-кнопками, без изменения данных. Переходы внутри SPA через history API:
 * перезагрузка страницы обновляет сессию через /auth/refresh, а у /auth/* ограничение частоты.
 */
test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

async function demoLogin(page: Page, persona: "Кандидат" | "Работодатель"): Promise<void> {
  await page.goto("/login");
  await page.getByRole("button", { name: persona, exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

async function go(page: Page, path: string): Promise<void> {
  await page.evaluate((target) => {
    window.history.pushState({}, "", target);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
  await expect(page).toHaveURL(new RegExp(`${path.replace(/[?]/g, "\\?")}$`));
  await page.waitForLoadState("networkidle");
}

async function expectNoHorizontalScroll(page: Page, path: string): Promise<void> {
  const widths = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  expect(widths[0], `${path}: ширина содержимого ${widths[0]} при экране ${widths[1]}`).toBeLessThanOrEqual(widths[1] + 1);
}

test("публичные страницы помещаются в ширину телефона", async ({ page }) => {
  for (const path of ["/", "/login", "/register"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expectNoHorizontalScroll(page, path);
  }
});

test("кабинет кандидата помещается в ширину телефона", async ({ page }) => {
  await demoLogin(page, "Кандидат");
  for (const section of ["", "/profile", "/grade", "/invitations", "/vacancies", "/applications", "/tasks", "/settings"]) {
    const path = `/candidate${section}`;
    await go(page, path);
    await expectNoHorizontalScroll(page, path);
  }
});

test("кабинет работодателя помещается в ширину телефона", async ({ page }) => {
  await demoLogin(page, "Работодатель");
  for (const section of ["", "/company", "/needs", "/needs/new", "/search", "/categories", "/invitations", "/vacancies", "/vacancy-test", "/tasks"]) {
    const path = `/employer${section}`;
    await go(page, path);
    await expectNoHorizontalScroll(page, path);
  }
  // Подборка и карточка кандидата — самые насыщенные экраны
  await go(page, "/employer/needs");
  await page.getByRole("link", { name: "Открыть подборку" }).first().click();
  await page.waitForLoadState("networkidle");
  await expectNoHorizontalScroll(page, page.url());
  await page.getByRole("link", { name: "Карточка и полное объяснение" }).first().click();
  await page.waitForLoadState("networkidle");
  await expectNoHorizontalScroll(page, page.url());
});
