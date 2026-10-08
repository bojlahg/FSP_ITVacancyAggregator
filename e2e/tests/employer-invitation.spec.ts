import { expect, type Page, test } from "@playwright/test";
import { E2E_CANDIDATE, login, openSection, registerUser, runId, salaryRangePattern, uniqueEmail } from "./helpers";

// Шаги 4–9 демо-сценария (docs/implementation.md §18). Работодатель новый на каждый прогон, приглашение уходит
// служебному кандидату сида (e2e-candidate@itscout.ru), а не героям показа — демо-данные не меняются.

const SALARY_FROM = 220_000;
const SALARY_TO = 260_000;
const NEED_TEXT = [
  "Python backend-разработчик в платёжную команду",
  "Ищем Middle backend-разработчика. Стек: Python, FastAPI, PostgreSQL, Docker, желательно Kafka.",
  "Работа удалённо. Вилка от 220 000 до 260 000 рублей.",
].join("\n");

async function findCandidateInSearch(page: Page, displayName: string): Promise<void> {
  for (let pageNo = 1; pageNo <= 15; pageNo += 1) {
    const results = page.getByRole("region", { name: /^Найдено/ });
    // Пока идёт запрос, на экране прежняя страница (placeholder) — ждём свежие результаты
    await expect(page.getByLabel("Обновляем результаты")).toHaveCount(0);
    await expect(results.getByRole("article").first()).toBeVisible();
    const link = results.getByRole("link", { name: displayName, exact: true });
    if (await link.isVisible()) {
      await link.click();
      return;
    }
    const next = page.getByRole("navigation", { name: "Страницы результатов" }).getByRole("button", { name: /Дальше/ });
    if (!(await next.isVisible()) || !(await next.isEnabled())) break;
    await next.click();
    await expect(page.getByText(new RegExp(`^${pageNo + 1} / \\d+$`))).toBeVisible();
  }
  throw new Error(`${displayName} не найден в поиске по базе`);
}

test("работодатель создаёт потребность, собирает шорт-лист и приглашает; кандидат принимает", async ({ page, browser }) => {
  const id = runId();
  const company = `E2E Компания ${id}`;
  const needTitle = `E2E · Python backend ${id}`;
  let needId = "";

  await test.step("Регистрация работодателя и профиль компании", async () => {
    await registerUser(page, "employer", uniqueEmail("employer", id));
    await page.getByLabel(/^Название/).fill(company);
    await page.getByLabel(/^Контактное лицо/).fill("Рекрутер E2E");
    await page.getByLabel("Telegram").fill("@itscout_e2e");
    await page.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Сохранено" })).toBeVisible();
  });

  await test.step("4. Потребность текстом: разбор словарём, вилка, сохранение", async () => {
    await openSection(page, "Потребности");
    await page.getByRole("link", { name: "Новая потребность" }).click();
    await page.getByRole("textbox", { name: "Текст вакансии или описание потребности" }).fill(NEED_TEXT);
    await page.getByRole("button", { name: "Разобрать" }).click();

    // На проде LLM выключен — разбор словарём; со включённым LLM подпись другая, тест её тоже принимает
    await expect(page.getByText(/Разобрано (по словарю навыков|словарём и языковой моделью)/)).toBeVisible();
    await expect(page.getByLabel(/^Специализация/)).toHaveValue("backend");
    await expect(page.getByLabel(/^Грейд/)).toHaveValue("middle");
    await expect(page.getByLabel(/^Вилка от/)).toHaveValue(String(SALARY_FROM));
    await expect(page.getByLabel(/^Вилка до/)).toHaveValue(String(SALARY_TO));
    await expect(page.getByRole("list", { name: "Выбранные навыки" }).first()).toBeVisible();

    await page.getByLabel(/^Название/).fill(needTitle);
    await page.getByRole("button", { name: "Сохранить и открыть подборку" }).click();
    await expect(page).toHaveURL(/\/employer\/needs\/\d+$/);
    needId = /\/needs\/(\d+)$/.exec(page.url())?.[1] ?? "";
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(needTitle);
    await expect(page.getByText("Покрытие вилки", { exact: true })).toBeVisible();
    await expect(page.getByText(/^\d+%\s*ожиданий кандидатов$/)).toBeVisible();
  });

  await test.step("5. Подборка: категории, кандидаты с объяснением, фильтр ФСП, шорт-лист переживает смену фильтра", async () => {
    const categories = page.getByRole("region", { name: "Рекомендованные категории" });
    await expect(categories.getByRole("button").filter({ hasText: "Точное совпадение" })).toBeVisible();

    const candidates = page.getByRole("region", { name: /^Кандидаты/ }).getByRole("article");
    await expect(candidates.first()).toBeVisible();
    await expect(candidates.first().getByRole("listitem").first()).toBeVisible();

    // Чекбоксы фильтров управляются адресом страницы: состояние меняется после перехода, поэтому click, а не check
    const fspFilter = page.getByRole("checkbox", { name: "Есть достижения ФСП" });
    await fspFilter.click();
    await expect(fspFilter).toBeChecked();
    await expect(page).toHaveURL(/[?&]fsp=1/);
    await expect(candidates.first()).toBeVisible();
    await expect(candidates.filter({ hasNot: page.getByTitle(/^Достижений ФСП/) })).toHaveCount(0);

    const pinned = page.getByRole("button", { name: /^Убрать .+ из шорт-листа$/ });
    await expect(pinned).toHaveCount(0);
    for (const index of [0, 1]) {
      const pin = candidates.nth(index).getByRole("button", { name: "В шорт-лист", exact: true });
      await pin.click();
      await expect(candidates.nth(index).getByRole("button", { name: "В шорт-листе" })).toHaveAttribute("aria-pressed", "true");
    }
    await expect(pinned).toHaveCount(2);
    const names = await pinned.evaluateAll((buttons) => buttons.map((button) => button.getAttribute("aria-label")));

    await fspFilter.click();
    await expect(fspFilter).not.toBeChecked();
    await page.getByLabel("Грейд", { exact: true }).selectOption("senior");
    await expect(page).not.toHaveURL(/[?&]fsp=1/);
    await expect(page).toHaveURL(/[?&]grade=senior/);
    await expect(pinned).toHaveCount(2);
    expect(await pinned.evaluateAll((buttons) => buttons.map((button) => button.getAttribute("aria-label")))).toEqual(names);
  });

  await test.step("6. Карточка e2e-кандидата из поиска по базе: тест по темам, контактов нет", async () => {
    await openSection(page, "Поиск по базе");
    await page.getByLabel("Специализация").selectOption("backend");
    await page.getByLabel("Грейд").selectOption("middle");
    await expect(page).toHaveURL(/spec=backend.*grade=middle|grade=middle.*spec=backend/);
    await findCandidateInSearch(page, E2E_CANDIDATE.displayName);

    await expect(page).toHaveURL(/\/employer\/candidates\/\d+/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(E2E_CANDIDATE.displayName);
    await expect(page.getByText("Карточка кандидата · обезличенная")).toBeVisible();
    await expect(page.getByText("Результаты теста по темам")).toBeVisible();
    await expect(page.getByText("Контакты скрыты")).toBeVisible();
    await expect(page.getByText(E2E_CANDIDATE.email)).toHaveCount(0);
    await expect(page.getByText(E2E_CANDIDATE.fullName)).toHaveCount(0);
  });

  await test.step("7. Приглашение с вилкой 220–260 тыс. ₽", async () => {
    await page.getByRole("button", { name: "Пригласить", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: `Приглашение · ${E2E_CANDIDATE.displayName}` });
    await dialog.getByLabel("Потребность").selectOption(needId);
    await dialog.getByLabel(/^Заголовок/).fill(needTitle);
    await dialog.getByLabel(/^Описание предложения/).fill("Платёжная команда, Python и PostgreSQL. Автотест ITScout.");
    await dialog.getByLabel(/^Вилка от/).fill(String(SALARY_FROM));
    await dialog.getByLabel(/^Вилка до/).fill(String(SALARY_TO));
    await expect(dialog.getByLabel(/^Контактное лицо/)).toHaveValue("Рекрутер E2E");
    await dialog.getByRole("button", { name: "Отправить приглашение" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("button", { name: "Приглашение отправлено" })).toBeDisabled();
  });

  await test.step("8. Кандидат видит приглашение, вилку и «почему вам» → принимает", async () => {
    const candidateContext = await browser.newContext();
    const candidatePage = await candidateContext.newPage();
    try {
      await login(candidatePage, E2E_CANDIDATE.email, E2E_CANDIDATE.password);
      await openSection(candidatePage, "Приглашения");
      const invitation = candidatePage.getByRole("button", { name: new RegExp(company) });
      await expect(invitation).toContainText(salaryRangePattern(SALARY_FROM, SALARY_TO));
      await invitation.click();
      await expect(invitation).toHaveAttribute("aria-expanded", "true");
      // Раскрыта только эта карточка: «почему вам» и кнопка «Принять» — её
      await expect(candidatePage.getByText("Почему вам")).toBeVisible();
      await expect(candidatePage.getByText(/^Категория совпадает: Backend · Middle/)).toBeVisible();
      await candidatePage.getByRole("button", { name: "Принять" }).click();
      // У служебного кандидата копятся принятые приглашения прошлых прогонов — проверяем статус именно этого
      await expect(invitation).toContainText("Принято");
      await expect(candidatePage.getByRole("button", { name: "Принять" })).toHaveCount(0);
    } finally {
      await candidateContext.close();
    }
  });

  await test.step("9. Работодатель видит «Принято» и контакты кандидата", async () => {
    await openSection(page, "Приглашения");
    await expect(page.getByText("Принято", { exact: true }).first()).toBeVisible();
    // У принятого приглашения контакты раскрываются кнопкой «Контакты» в строке таблицы
    await page.getByRole("button", { name: "Контакты", exact: true }).click();
    await expect(page.getByText("Контакты открыты")).toBeVisible();
    await expect(page.getByText(E2E_CANDIDATE.email)).toBeVisible();
    await page.getByRole("link", { name: E2E_CANDIDATE.fullName }).click();
    await expect(page.getByText("Карточка кандидата · контакты открыты")).toBeVisible();
    await expect(page.getByText("Контакты скрыты")).toHaveCount(0);
    await expect(page.getByText(E2E_CANDIDATE.email)).toBeVisible();
  });
});
