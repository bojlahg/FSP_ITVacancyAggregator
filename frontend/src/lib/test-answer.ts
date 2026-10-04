import type { AnswerPayload, CurrentItem } from "@/lib/testing-queries";

export type ItemKind = NonNullable<CurrentItem["kind"]>;

/** Черновик ответа на текущее задание; в API уходит только поле, нужное для вида задания. */
export interface AnswerDraft {
  choice: string | null;
  choices: string[];
  number: string;
  order: string[];
  text: string;
}

export function emptyDraft(item: CurrentItem): AnswerDraft {
  return {
    choice: null,
    choices: [],
    number: "",
    // Для упорядочивания стартовый порядок — как прислал сервер (он уже перемешан).
    order: (item.options ?? []).map((option) => option.id),
    text: "",
  };
}

export function parseNumeric(raw: string): number | null {
  const trimmed = raw.trim().replace(/\s/g, "").replace(",", ".");
  if (trimmed === "") return null;
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : null;
}

/** Выбор одного варианта: «что выведет код» и «результат SQL» тоже выбор из вариантов. */
export function isSingleChoice(kind: ItemKind): boolean {
  return kind === "single_choice" || kind === "code_output" || kind === "sql_result";
}

export function isDraftEmpty(kind: ItemKind, draft: AnswerDraft): boolean {
  if (isSingleChoice(kind)) return draft.choice === null;
  switch (kind) {
    case "multi_choice":
      return draft.choices.length === 0;
    case "numeric":
      return parseNumeric(draft.number) === null;
    case "ordering":
      return draft.order.length === 0;
    case "open_approach":
      return draft.text.trim() === "";
    default:
      return true;
  }
}

/** Пустой черновик тоже отправляется (автоотправка по таймеру): сервер засчитает его как неверный. */
export function toPayload(kind: ItemKind, draft: AnswerDraft): AnswerPayload {
  if (isSingleChoice(kind)) return { choice_ids: draft.choice ? [draft.choice] : [] };
  switch (kind) {
    case "multi_choice":
      return { choice_ids: draft.choices };
    case "numeric":
      return { number: parseNumeric(draft.number) };
    case "ordering":
      return { order: draft.order };
    case "open_approach":
      return { text: draft.text };
    default:
      return {};
  }
}
