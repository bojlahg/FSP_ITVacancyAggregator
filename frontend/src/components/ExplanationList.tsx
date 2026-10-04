import { AlertTriangle, Check, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export type ExplanationKind = "positive" | "warning" | "neutral";

export interface ExplanationLine {
  kind: ExplanationKind;
  text: string;
}

interface ExplanationListProps {
  items: ExplanationLine[];
  /** Показать только первые N строк (в списках кандидатов — 2–3 причины). */
  limit?: number;
  className?: string;
}

const icons = {
  positive: { Icon: Check, className: "text-primary", label: "Плюс" },
  warning: { Icon: AlertTriangle, className: "text-destructive", label: "Внимание" },
  neutral: { Icon: Minus, className: "text-muted-foreground", label: "" },
} as const;

/**
 * Объяснение совпадения (docs/implementation.md §8.4). Строки приходят с backend готовыми —
 * фронт только отображает их, ничего не досчитывая.
 */
export function ExplanationList({ items, limit, className }: ExplanationListProps) {
  const visible = limit ? items.slice(0, limit) : items;
  return (
    <ul className={cn("space-y-1.5 text-sm", className)}>
      {visible.map((item, index) => {
        const { Icon, className: iconClass, label } = icons[item.kind];
        return (
          <li key={index} className="flex items-start gap-2">
            <Icon className={cn("mt-0.5 size-4 shrink-0", iconClass)} aria-label={label || undefined} aria-hidden={!label} />
            <span className={cn("leading-snug", item.kind === "neutral" && "text-muted-foreground")}>{item.text}</span>
          </li>
        );
      })}
    </ul>
  );
}
