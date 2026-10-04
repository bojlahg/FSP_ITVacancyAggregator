import { Loader2, Search, X } from "lucide-react";
import { useEffect, useId, useState, type KeyboardEvent } from "react";
import { Input } from "@/components/ui/input";
import { apiError } from "@/lib/api-error";
import { type SkillOut, useSkillSearch } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

const SEARCH_DEBOUNCE_MS = 250;
const MAX_SUGGESTIONS = 8;

interface SkillsMultiSelectProps {
  id: string;
  value: string[];
  onChange: (ids: string[]) => void;
  /** Подписи выбранных навыков: id → название (ответ API даёт только id). */
  names: Record<string, string>;
  onNamesChange: (skills: SkillOut[]) => void;
  invalid?: boolean;
  describedBy?: string;
}

function useDebounced(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/** Мультивыбор навыков из онтологии с подсказками по мере ввода (GET /catalog/skills?q=). */
export function SkillsMultiSelect({ id, value, onChange, names, onNamesChange, invalid, describedBy }: SkillsMultiSelectProps) {
  const listId = useId();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const query = useDebounced(text, SEARCH_DEBOUNCE_MS);
  const search = useSkillSearch(query);

  const suggestions = (search.data ?? []).filter((skill) => !value.includes(skill.id)).slice(0, MAX_SUGGESTIONS);
  const showList = open && text.trim().length > 0;
  const activeIndex = Math.min(active, Math.max(0, suggestions.length - 1));

  const add = (skill: SkillOut) => {
    onNamesChange([skill]);
    onChange([...value, skill.id]);
    setText("");
    setActive(0);
  };

  const remove = (skillId: string) => onChange(value.filter((item) => item !== skillId));

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((current) => Math.min(current + 1, suggestions.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      // Enter в поле поиска добавляет навык, а не отправляет форму опроса.
      event.preventDefault();
      const skill = suggestions[activeIndex];
      if (showList && skill) add(skill);
    } else if (event.key === "Escape") {
      setOpen(false);
    } else if (event.key === "Backspace" && text === "" && value.length > 0) {
      remove(value[value.length - 1]!);
    }
  };

  return (
    <div className="grid gap-2">
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Выбранные навыки">
          {value.map((skillId) => (
            <li
              key={skillId}
              className="inline-flex items-center gap-1 rounded-full bg-primary-tint py-0.5 pr-1 pl-2.5 font-mono text-xs font-medium text-primary"
            >
              {names[skillId] ?? skillId}
              <button
                type="button"
                onClick={() => remove(skillId)}
                aria-label={`Убрать ${names[skillId] ?? skillId}`}
                className="rounded-full p-0.5 outline-none hover:bg-primary hover:text-primary-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40"
              >
                <X className="size-3" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          id={id}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && suggestions[activeIndex] ? `${listId}-${activeIndex}` : undefined}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          autoComplete="off"
          placeholder="Начните вводить: Python, React, PostgreSQL…"
          className="pl-9"
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setOpen(true);
            setActive(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />

        {showList && (
          <ul
            id={listId}
            role="listbox"
            aria-label="Подсказки навыков"
            className="absolute inset-x-0 top-full z-20 mt-1 max-h-72 overflow-y-auto rounded-md border bg-popover p-1 text-sm shadow-md"
          >
            {search.isFetching && suggestions.length === 0 && (
              <li className="flex items-center gap-2 px-3 py-2 text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Ищем навыки…
              </li>
            )}
            {search.isError && (
              <li className="px-3 py-2 text-destructive-strong">{apiError(search.error).message}</li>
            )}
            {!search.isFetching && !search.isError && search.isSuccess && suggestions.length === 0 && (
              <li className="px-3 py-2 text-muted-foreground">Ничего не нашли — попробуйте другое написание</li>
            )}
            {suggestions.map((skill, index) => (
              <li
                key={skill.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === activeIndex}
                // mousedown, а не click: иначе blur поля закроет список раньше выбора.
                onMouseDown={(event) => {
                  event.preventDefault();
                  add(skill);
                }}
                onMouseEnter={() => setActive(index)}
                className={cn(
                  "flex cursor-pointer items-center justify-between gap-3 rounded-sm px-3 py-2",
                  index === activeIndex && "bg-accent text-accent-foreground",
                )}
              >
                <span>{skill.name}</span>
                <span className="font-mono text-xs text-muted-foreground">{skill.family}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
