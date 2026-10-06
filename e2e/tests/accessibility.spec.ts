import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

/**
 * Доступность по WCAG 2.1 AA (axe-core): серьёзные и критичные нарушения на публичных страницах и в обоих
 * кабинетах роняют тест. Только чтение — вход демо-кнопками, переходы внутри SPA (у /auth/* лимит частоты).
 */
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function audit(page: Page, path: string): Promise<void> {
  await page.waitForLoadState("networkidle");
  const { violations } = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const blocking = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const report = blocking.map(
    (v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join("\n  ")}`,
  );
  expect.soft(report, `${path}: нарушения доступности`).toEqual([]);
}

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
}

test("публичные страницы доступны", async ({ page }) => {
  for (const path of ["/", "/login", "/register", "/how-it-works"]) {
    await page.goto(path);
    await audit(page, path);
  }
});

test("кабинет кандидата доступен", async ({ page }) => {
  await demoLogin(page, "Кандидат");
  for (const section of ["", "/profile", "/grade", "/invitations", "/vacancies", "/applications", "/tasks", "/challenges", "/settings"]) {
    await go(page, `/candidate${section}`);
    await audit(page, `/candidate${section}`);
  }
});

test("кабинет работодателя доступен", async ({ page }) => {
  await demoLogin(page, "Работодатель");
  for (const section of ["", "/company", "/needs", "/needs/new", "/search", "/categories", "/invitations", "/vacancies", "/vacancy-test", "/tasks", "/challenges"]) {
    await go(page, `/employer${section}`);
    await audit(page, `/employer${section}`);
  }
  await go(page, "/employer/needs");
  await page.getByRole("link", { name: "Открыть подборку" }).first().click();
  await audit(page, page.url());
  await page.getByRole("link", { name: "Карточка и полное объяснение" }).first().click();
  await audit(page, page.url());
});
