import type { ComponentProps } from "react";
import { Input } from "@/components/ui/input";

type CommitInputProps = Omit<ComponentProps<typeof Input>, "value" | "defaultValue" | "onChange" | "onBlur"> & {
  value: string;
  onCommit: (value: string) => void;
};

/**
 * Поле фильтра, которое применяет значение по Enter или при уходе фокуса — чтобы не дёргать API
 * на каждую букву. Внешнее значение (например, сброс фильтров) перемонтирует поле.
 */
export function CommitInput({ value, onCommit, onKeyDown, ...props }: CommitInputProps) {
  const commit = (raw: string) => {
    const next = raw.trim();
    if (next !== value) onCommit(next);
  };
  return (
    <Input
      key={value}
      defaultValue={value}
      onBlur={(event) => commit(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          commit(event.currentTarget.value);
        }
        onKeyDown?.(event);
      }}
      {...props}
    />
  );
}
