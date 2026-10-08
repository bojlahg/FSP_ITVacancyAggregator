import { formatNumber, NET } from "@/lib/format";
import { cn } from "@/lib/utils";

interface SalaryFigureProps {
  from: number;
  to: number;
  className?: string;
}

/**
 * Вилка крупно: сумма одной строкой, «на руки» приглушённо и переносится отдельно, если не помещается.
 * Для строк и таблиц — SalaryRange.
 */
export function SalaryFigure({ from, to, className }: SalaryFigureProps) {
  return (
    <span className={cn("flex flex-wrap items-baseline gap-x-2 font-mono", className)}>
      <span className="font-semibold tracking-tight whitespace-nowrap tabular-nums">
        {formatNumber(from)} – {formatNumber(to)} ₽
      </span>{" "}
      <span className="text-base font-medium whitespace-nowrap text-muted-foreground">{NET}</span>
    </span>
  );
}
