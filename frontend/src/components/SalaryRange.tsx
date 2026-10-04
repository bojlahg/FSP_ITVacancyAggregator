import { formatSalaryRange } from "@/lib/format";
import { cn } from "@/lib/utils";

interface SalaryRangeProps {
  from?: number | null;
  to?: number | null;
  className?: string;
}

/** Вилка зарплаты: «220 000 – 260 000 ₽». */
export function SalaryRange({ from, to, className }: SalaryRangeProps) {
  return (
    <span className={cn("font-mono font-bold whitespace-nowrap tabular-nums", className)}>
      {formatSalaryRange(from, to)}
    </span>
  );
}
