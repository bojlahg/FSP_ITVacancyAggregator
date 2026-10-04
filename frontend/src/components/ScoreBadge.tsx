import { cn } from "@/lib/utils";

interface ScoreBadgeProps {
  /** match-score 0–100 (docs/implementation.md §8.3). */
  score: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}

function tone(score: number): string {
  if (score >= 80) return "bg-primary text-primary-foreground";
  if (score >= 60) return "bg-primary-tint text-primary ring-1 ring-primary/30";
  return "bg-muted text-foreground";
}

const sizes = {
  sm: "h-7 min-w-9 px-1.5 text-sm",
  md: "h-10 min-w-12 px-2 text-lg",
  lg: "h-14 min-w-16 px-3 text-2xl",
} as const;

export function ScoreBadge({ score, size = "md", className }: ScoreBadgeProps) {
  const value = Math.round(score);
  return (
    <span
      title={`Совпадение с потребностью: ${value} из 100`}
      aria-label={`Совпадение ${value} из 100`}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-lg font-mono leading-none font-extrabold tabular-nums",
        tone(value),
        sizes[size],
        className,
      )}
    >
      {value}
    </span>
  );
}
