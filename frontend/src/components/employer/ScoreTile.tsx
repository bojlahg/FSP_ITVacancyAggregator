import { cn } from "@/lib/utils";

interface ScoreTileProps {
  /** match-score 0–100 (docs/implementation.md §8.3). */
  score: number;
  /** tint — в списке, solid — в карточке кандидата, card — на сером фоне (шорт-лист). */
  tone?: "tint" | "solid" | "card";
  size?: "sm" | "md" | "lg";
  className?: string;
}

const tones = {
  tint: "bg-primary-tint text-primary",
  solid: "bg-primary text-primary-foreground",
  card: "bg-card text-primary",
} as const;

const sizes = {
  sm: "size-8 rounded-lg text-sm",
  md: "size-12 rounded-[10px] text-2xl",
  lg: "size-14 rounded-[10px] text-[28px]",
} as const;

/** Квадрат со score: число крупно моноширинным, рядом всегда стоят причины из того же объяснения. */
export function ScoreTile({ score, tone = "tint", size = "lg", className }: ScoreTileProps) {
  const value = Math.round(score);
  return (
    <span
      role="img"
      title={`Совпадение с потребностью: ${value} из 100`}
      aria-label={`Совпадение ${value} из 100`}
      className={cn(
        "grid shrink-0 place-items-center font-mono leading-none font-bold tabular-nums",
        tones[tone],
        sizes[size],
        className,
      )}
    >
      {value}
    </span>
  );
}
