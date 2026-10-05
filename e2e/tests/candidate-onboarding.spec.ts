import { expect, type Locator, type Page, test } from "@playwright/test";
import { openSection, registerUser, runId, uniqueEmail } from "./helpers";

// Шаги 1–3 демо-сценария (docs/implementation.md §18): регистрация → опрос → специализация и грейд → полный тест.
// Аккаунт одноразовый и в конце удаляется — в базе показа не остаётся лишних кандидатов.

/** Поля, которых в выдаче текущего задания быть не может: ключи ответов не уходят на фронт (§10.6). */
const LEAKY_FIELD = /key|correct|answer|solution|expected/i;
const MAX_ITEMS = 40;

type Filler = (group: Locator, page: Page) => Promise<void>;

async function addSkill(group: Locator, page: Page, name: string): Promise<void> {
  await group.getByRole("combobox").fill(name);
  // В подсказке за названием идёт семейство навыка
  await group
    .getByRole("listbox", { name: "Подсказки навыков" })
    .getByRole("option", { name: new RegExp(`^${name}`) })
    .first()
    .click();
  await expect(group.getByRole("button", { name: `Убрать ${name}` })).toBeVisible();
}

// Ответы опроса по тексту вопроса; необязательные вопросы пропускаем.
const SURVEY: [RegExp, Filler][] = [
  [/Чем вы занимаетесь/, (g) => g.getByRole("checkbox", { name: "Пишу серверную логику и API" }).check()],
  [/Какие задачи вам интереснее/, (g) => g.getByRole("checkbox", { name: /Масштабирование и производительность/ }).check()],
  [/Основной язык/, async (g) => void (await g.getByRole("combobox").selectOption({ label: "Python" }))],
  [
    /Технологии, с которыми/,
    async (g, page) => {
      for (const skill of ["Python", "FastAPI", "PostgreSQL"]) await addSkill(g, page, skill);
    },
  ],
  [/лет коммерческого опыта/, (g) => g.getByRole("spinbutton").fill("3")],
  [/формат работы/, (g) => g.getByRole("checkbox", { name: "Удалённо" }).check()],
  [/Готовы к переезду/, (g) => g.getByRole("radio", { name: "Нет" }).check()],
  [
    /Ожидания по зарплате/,
    async (g) => {
      await g.getByRole("spinbutton", { name: "Зарплата от, ₽" }).fill("200000");
      await g.getByRole("spinbutton", { name: "Зарплата до, ₽" }).fill("250000");
    },
  ],
];

async function fillSurvey(page: Page): Promise<void> {
  // На экране опроса других групп полей нет: всё, что role=group, — вопросы текущей части
  const form = page.getByRole("main");
  for (let screen = 0; screen < 4; screen += 1) {
    await expect(form.getByRole("group").first()).toBeVisible();
    for (const group of await form.getByRole("group").all()) {
      const legend = (await group.locator("legend").first().textContent()) ?? "";
      const filler = SURVEY.find(([pattern]) => pattern.test(legend))?.[1];
      if (filler) await filler(group, page);
    }
    const finish = form.getByRole("button", { name: "Узнать специализацию" });
    if (await finish.isVisible()) {
      await finish.click();
      return;
    }
    const before = await form.getByRole("group").first().locator("legend").textContent();
    await form.getByRole("button", { name: "Далее" }).click();
    await expect(form.getByRole("group").first().locator("legend")).not.toHaveText(before ?? "");
  }
  throw new Error("Опрос не закончился за 4 экрана");
}

function leakyFields(value: unknown, path = "$"): string[] {
  if (Array.isArray(value)) return value.flatMap((item, index) => leakyFields(item, `${path}[${index}]`));
  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([key, nested]) => [
      ...(LEAKY_FIELD.test(key) ? [`${path}.${key}`] : []),
      ...leakyFields(nested, `${path}.${key}`),
    ]);
  }
  return [];
}

/** Отвечаем «как получится»: ключей на фронте нет, проверяем механику, а не результат. */
async function answerCurrentItem(page: Page): Promise<void> {
  const choices = page.getByRole("radiogroup", { name: "Варианты ответа" });
  const multi = page.getByRole("group", { name: "Выберите все верные варианты" });
  const numeric = page.getByRole("textbox", { name: "Ваш ответ — число" });
  const open = page.getByRole("textbox", { name: "Опишите подход своими словами" });
  const ordering = page.getByText("Расставьте шаги в правильном порядке");
  await expect(choices.or(multi).or(numeric).or(open).or(ordering).first()).toBeVisible();

  if (await choices.isVisible()) await choices.getByRole("radio").first().check();
  else if (await multi.isVisible()) await multi.getByRole("checkbox").first().check();
  else if (await numeric.isVisible()) await numeric.fill("1");
  else if (await open.isVisible()) {
    await open.fill("Сначала уточню требования и ограничения, затем измерю текущее поведение, выберу простое решение и проверю его тестами.");
  }
  // ordering: порядок от сервера уже готов к отправке
}

test("кандидат регистрируется, проходит опрос и полный тест, получает результат", async ({ page }) => {
  const email = uniqueEmail("candidate", runId());
  const currentPayloads: unknown[] = [];
  page.on("response", async (response) => {
    if (response.request().method() === "GET" && /\/api\/v1\/tests\/attempts\/\d+\/current$/.test(new URL(response.url()).pathname)) {
      currentPayloads.push(await response.json().catch(() => null));
    }
  });

  await test.step("1. Регистрация кандидата", async () => {
    await registerUser(page, "candidate", email);
  });

  await test.step("2. Опрос → Backend, грейд Middle", async () => {
    await expect(page.getByRole("heading", { name: "Получите категорию" })).toBeVisible();
    await fillSurvey(page);

    await expect(page.getByText("Подтвердите специализацию")).toBeVisible();
    await expect(page.getByText("Рекомендуем по ответам")).toBeVisible();
    // Система предлагает Backend по ответам опроса — он выбран по умолчанию
    await expect(page.getByRole("button", { name: /Backend-разработка/ })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: /Подтвердить/ }).click();

    await expect(page.getByText("Выберите грейд для теста")).toBeVisible();
    await page.getByRole("radiogroup", { name: "Грейд" }).getByRole("radio", { name: /^Middle/ }).click();
    await page.getByRole("button", { name: /Далее/ }).click();

    await expect(
      page.getByRole("list", { name: "Шаги онбординга" }).getByRole("listitem").filter({ hasText: "Перед тестом" }),
    ).toHaveAttribute("aria-current", "step");
    await page.getByRole("button", { name: /Начать тест/ }).click();
    await expect(page).toHaveURL(/\/candidate\/test\/\d+$/);
  });

  await test.step("3. Полный тест → результат и разбор по темам", async () => {
    let answered = 0;
    for (; answered < MAX_ITEMS; answered += 1) {
      const submit = page.getByRole("button", { name: "Ответить" });
      await expect(submit.or(page.getByText("Разбор по темам"))).toBeVisible({ timeout: 60_000 });
      if (!(await submit.isVisible())) break;
      await answerCurrentItem(page);
      const ackPromise = page.waitForResponse(
        (r) => r.request().method() === "POST" && /\/api\/v1\/tests\/attempts\/\d+\/answer$/.test(new URL(r.url()).pathname),
      );
      const counter = page.getByText(/^Вопрос \d+/);
      const position = await counter.textContent();
      await submit.click();
      const ack = (await (await ackPromise).json()) as { finished?: boolean };
      if (ack.finished) {
        answered += 1;
        break;
      }
      // Ждём следующее задание — иначе можно ответить на старое повторно
      await expect(counter).not.toHaveText(position ?? "", { timeout: 30_000 });
    }
    expect(answered, "тест должен закончиться").toBeLessThan(MAX_ITEMS);

    await expect(page).toHaveURL(/\/candidate\/test\/\d+\/result$/);
    // Оба исхода валидны: категория присвоена или грейд не подтверждён
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Тест пройден уверенно|Тест пройден|Грейд не подтверждён/);
    await expect(page.getByText("Разбор по темам")).toBeVisible();
    const outcome = `заданий: ${answered}, итог «${(await page.getByRole("heading", { level: 1 }).textContent()) ?? ""}»`;
    test.info().annotations.push({ type: "result", description: outcome });
    console.log(`Тест кандидата: ${outcome}`);

    expect(currentPayloads.length).toBeGreaterThan(0);
    expect(currentPayloads.flatMap((payload) => leakyFields(payload))).toEqual([]);
  });

  await test.step("Уборка: одноразовый кандидат удаляет аккаунт", async () => {
    await openSection(page, "Настройки");
    await page.getByRole("button", { name: "Удалить аккаунт" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Удалить навсегда" }).click();
    await expect(page).not.toHaveURL(/\/candidate/);
  });
});
