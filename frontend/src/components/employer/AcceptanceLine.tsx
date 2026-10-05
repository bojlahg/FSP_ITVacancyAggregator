import { Handshake } from "lucide-react";
import type { Acceptance } from "@/lib/employer-queries";
import { cn } from "@/lib/utils";

const levelClass: Record<Acceptance["level"], string> = {
  high: "text-primary",
  medium: "text-muted-foreground",
  low: "text-destructive",
};

/**
 * Вероятность, что кандидат примет приглашение (docs/implementation.md §8.3.1). Текст готов на backend —
 * собран из тех же факторов, что и число; фронт только показывает.
 */
export function AcceptanceLine({ acceptance, className }: { acceptance: Acceptance; className?: string }) {
  return (
    <p
      className={cn("flex items-start gap-2 text-sm", className)}
      title={
        acceptance.affects_score
          ? "Оценка по правилам, без обучения; учитывается в score"
          : "Оценка по правилам, без обучения; на score и порядок не влияет"
      }
    >
      <Handshake className={cn("mt-0.5 size-4 shrink-0", levelClass[acceptance.level])} aria-hidden />
      <span className="leading-snug">{acceptance.text}</span>
    </p>
  );
}
