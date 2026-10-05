import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

function Progress({
  className,
  value,
  indicatorClassName,
  ...props
}: ComponentProps<"div"> & { value: number; indicatorClassName?: string }) {
  const clamped = Math.min(100, Math.max(0, value));
  // Без подписи скринридер прочитает только число — у индикатора всегда есть имя (WCAG 4.1.2)
  const name = props["aria-label"] ?? (props["aria-labelledby"] ? undefined : "Прогресс");
  return (
    <div
      data-slot="progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className={cn("relative h-2 w-full overflow-hidden rounded-full bg-muted", className)}
      {...props}
      aria-label={name}
    >
      <div
        className={cn("h-full rounded-full bg-primary transition-[width] duration-500", indicatorClassName)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export { Progress };
