import { EyeOff, ListOrdered, Scale, Shuffle, Timer, Undo2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useExplainerOverview } from "@/lib/explainer-queries";
import { extraItemsNote, plural } from "@/lib/format";
import { type AttemptPurpose, type Grade, useGradeStatus } from "@/lib/testing-queries";

/** docs/implementation.md §6.2: длительность полного теста. */
export const TEST_DURATION_LABEL = "~25 минут";

export interface TestRule {
  icon: LucideIcon;
  title: string;
  text: string;
}

/**
 * Сколько заданий в полном тесте на грейд: то же число, что total_estimate попытки и шапка теста
 * (explainer overview, §10.3), плюс приписка про уточняющие задания.
 */
export function useTestLengthText(grade: Grade): string {
  const overview = useExplainerOverview();
  const items = overview.data?.grades.find((item) => item.grade === grade)?.test_items;
  const extra = overview.data ? extraItemsNote(overview.data.extra_items_max) : "";
  return items !== undefined
    ? `${items} ${plural(items, ["задание", "задания", "заданий"])}, примерно 25 минут${extra ? `; ${extra}` : ""}.`
    : "Примерно 25 минут. Если результат близок к порогу грейда, добавятся уточняющие задания.";
}

/** Общие правила полного теста — экран «Перед тестом» в онбординге и подтверждение старта. */
export function testRules(lengthText: string): TestRule[] {
  return [
    { icon: ListOrdered, title: "Один вопрос на экране", text: lengthText },
    {
      icon: Undo2,
      title: "Назад вернуться нельзя",
      text: "Ответ отправляется сразу. Если не знаете — выберите наиболее вероятный вариант.",
    },
    {
      icon: Timer,
      title: "Таймер на каждый вопрос",
      text: "Время считает сервер. Когда оно выходит, текущий ответ отправляется автоматически.",
    },
    {
      icon: EyeOff,
      title: "Уход со вкладки фиксируется",
      text: "Мы отмечаем переключения вкладок, но баллы за это не снимаем.",
    },
    {
      icon: Shuffle,
      title: "Задания у всех разные",
      text: "Их сложность выверена: результаты сравниваются на общей шкале, поэтому они сопоставимы.",
    },
  ];
}

/** Как попытка учитывается в правилах грейда (§6.3): сроки — из grade-status, не из кода. */
export function useAttemptRuleText(purpose: AttemptPurpose): TestRule {
  const status = useGradeStatus();
  const cooldown = status.data?.cooldown_days;
  const retry = status.data?.failed_retry_days;
  const days = (n: number) => `${n} ${plural(n, ["день", "дня", "дней"])}`;
  let text: string;
  if ((purpose === "upgrade" || purpose === "downgrade") && cooldown !== undefined) {
    // §6.3: после смены грейда — пауза cooldown_days; уверенный проход сразу открывает грейд выше
    text = `Следующая смена грейда — не раньше чем через ${days(cooldown)} (после уверенного прохождения грейд выше доступен сразу). Если тест не получится, текущая категория сохранится.`;
  } else if (retry !== undefined) {
    text = `Если грейд не подтвердится, повторить тест на него можно будет через ${days(retry)}.`;
  } else {
    text = "Повтор теста и смена грейда возможны не сразу — сроки покажем на экране результата.";
  }
  return { icon: Scale, title: "Попытка засчитывается", text };
}
