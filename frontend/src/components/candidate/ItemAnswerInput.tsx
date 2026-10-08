import { ArrowDown, ArrowUp } from "lucide-react";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { type AnswerDraft, isSingleChoice, type ItemKind } from "@/lib/test-answer";
import type { CurrentItem } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

// Лимит текста открытого ответа на backend (AnswerPayload.text), если задание не прислало свой.
const OPEN_ANSWER_FALLBACK_MAX = 1500;

// Выбранный вариант — рамка 2px (border + inset-ring) и заливка tint; буква в моно-квадрате красится вместе с ним.
const optionClass =
  "group flex min-h-13 cursor-pointer items-start gap-3 rounded-lg border bg-card px-4 py-3 text-base transition-colors hover:bg-muted has-[:checked]:border-primary has-[:checked]:bg-primary-tint has-[:checked]:inset-ring-1 has-[:checked]:inset-ring-primary has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/40 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60 max-sm:py-4";
const letterClass =
  "flex size-7 shrink-0 items-center justify-center rounded-md bg-muted font-mono text-[13px] font-semibold text-muted-foreground group-has-[:checked]:bg-primary group-has-[:checked]:text-primary-foreground max-sm:size-6 max-sm:text-xs";

const optionLetter = (index: number) => String.fromCharCode(65 + index);

interface ItemAnswerInputProps {
  item: CurrentItem;
  kind: ItemKind;
  draft: AnswerDraft;
  onChange: (draft: AnswerDraft) => void;
  disabled: boolean;
}

/** Поле ответа по виду задания (docs/implementation.md §10.2). */
export function ItemAnswerInput({ item, kind, draft, onChange, disabled }: ItemAnswerInputProps) {
  const name = useId();
  const options = item.options ?? [];
  // Код ответа и SQL-результаты читаются моноширинным шрифтом.
  const monoOptions = kind === "code_output" || kind === "sql_result";

  if (isSingleChoice(kind)) {
    return (
      <div role="radiogroup" aria-label="Варианты ответа" className="grid gap-2">
        {options.map((option, index) => (
          <label key={option.id} className={optionClass}>
            <input
              type="radio"
              name={name}
              value={option.id}
              checked={draft.choice === option.id}
              onChange={() => onChange({ ...draft, choice: option.id })}
              disabled={disabled}
              className="mt-[5px] size-[18px] shrink-0 accent-primary outline-none max-sm:mt-0.5 max-sm:size-5"
            />
            <span className={letterClass} aria-hidden>
              {optionLetter(index)}
            </span>
            <span className={cn("min-w-0 py-0.5 font-medium whitespace-pre-wrap max-sm:py-0", monoOptions && "font-mono")}>
              {option.text}
            </span>
          </label>
        ))}
      </div>
    );
  }

  switch (kind) {
    case "multi_choice":
      return (
        <fieldset className="grid gap-2">
          <legend className="mb-2 text-sm text-muted-foreground">Выберите все верные варианты</legend>
          {options.map((option, index) => (
            <label key={option.id} className={optionClass}>
              <Checkbox
                className="mt-[5px] size-[18px] max-sm:mt-0.5 max-sm:size-5"
                checked={draft.choices.includes(option.id)}
                disabled={disabled}
                onChange={(event) =>
                  onChange({
                    ...draft,
                    choices: event.target.checked
                      ? [...draft.choices, option.id]
                      : draft.choices.filter((id) => id !== option.id),
                  })
                }
              />
              <span className={letterClass} aria-hidden>
                {optionLetter(index)}
              </span>
              <span className="min-w-0 py-0.5 font-medium whitespace-pre-wrap max-sm:py-0">{option.text}</span>
            </label>
          ))}
        </fieldset>
      );
    case "numeric":
      return (
        <div className="grid gap-2">
          <label htmlFor={name} className="text-sm text-muted-foreground">
            Ваш ответ — число
          </label>
          <Input
            id={name}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            className="max-w-56 font-mono text-base"
            value={draft.number}
            disabled={disabled}
            onChange={(event) => onChange({ ...draft, number: event.target.value })}
          />
        </div>
      );
    case "ordering":
      return <OrderingInput item={item} draft={draft} onChange={onChange} disabled={disabled} />;
    case "open_approach": {
      const max = item.max_length ?? OPEN_ANSWER_FALLBACK_MAX;
      return (
        <div className="grid gap-2">
          <label htmlFor={name} className="text-sm text-muted-foreground">
            Опишите подход своими словами
          </label>
          <Textarea
            id={name}
            rows={8}
            maxLength={max}
            value={draft.text}
            disabled={disabled}
            aria-describedby={`${name}-counter`}
            onChange={(event) => onChange({ ...draft, text: event.target.value })}
          />
          <div
            id={`${name}-counter`}
            className={cn(
              "text-right font-mono text-xs tabular-nums",
              draft.text.length >= max ? "text-destructive-strong" : "text-muted-foreground",
            )}
          >
            {draft.text.length} / {max}
          </div>
        </div>
      );
    }
    default:
      return <p className="text-sm text-muted-foreground">Этот вид задания пока не поддерживается.</p>;
  }
}

function OrderingInput({ item, draft, onChange, disabled }: Omit<ItemAnswerInputProps, "kind">) {
  const baseId = useId();
  const [announcement, setAnnouncement] = useState("");
  const textById = new Map((item.options ?? []).map((option) => [option.id, option.text]));

  const move = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= draft.order.length) return;
    const order = [...draft.order];
    [order[index], order[target]] = [order[target]!, order[index]!];
    onChange({ ...draft, order });
    setAnnouncement(`«${textById.get(order[target]!) ?? ""}» теперь на позиции ${target + 1}`);
    // Фокус едет вместе с элементом, чтобы его можно было двигать дальше с клавиатуры.
    const nextFocus = target === 0 || target === order.length - 1 ? -delta : delta;
    window.requestAnimationFrame(() => {
      document.getElementById(`${baseId}-${target}-${nextFocus > 0 ? "down" : "up"}`)?.focus();
    });
  };

  return (
    <div className="grid gap-2">
      <p className="text-sm text-muted-foreground">Расставьте шаги в правильном порядке кнопками ↑ и ↓</p>
      <ol className="grid gap-2">
        {draft.order.map((id, index) => (
          <li key={id} className="flex items-center gap-3 rounded-lg border bg-background px-3 py-2">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-tint font-mono text-xs font-bold text-primary">
              {index + 1}
            </span>
            <span className="flex-1 text-sm whitespace-pre-wrap">{textById.get(id) ?? id}</span>
            <span className="flex shrink-0 gap-1">
              <Button
                id={`${baseId}-${index}-up`}
                type="button"
                variant="ghost"
                size="icon-sm"
                disabled={disabled || index === 0}
                onClick={() => move(index, -1)}
                aria-label={`Поднять «${textById.get(id) ?? id}»`}
              >
                <ArrowUp />
              </Button>
              <Button
                id={`${baseId}-${index}-down`}
                type="button"
                variant="ghost"
                size="icon-sm"
                disabled={disabled || index === draft.order.length - 1}
                onClick={() => move(index, 1)}
                aria-label={`Опустить «${textById.get(id) ?? id}»`}
              >
                <ArrowDown />
              </Button>
            </span>
          </li>
        ))}
      </ol>
      <div className="sr-only" aria-live="polite">
        {announcement}
      </div>
    </div>
  );
}
