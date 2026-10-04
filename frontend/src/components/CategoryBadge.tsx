import { gradeLabel, specializationLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

interface CategoryBadgeProps {
  specialization: string;
  grade: string;
  variant?: "solid" | "soft" | "outline";
  size?: "sm" | "md" | "lg";
  className?: string;
}

const variants = {
  solid: "bg-primary text-primary-foreground border-transparent",
  soft: "bg-primary-tint text-primary border-transparent",
  outline: "border-primary text-primary bg-background",
} as const;

const sizes = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-2.5 py-1 text-sm",
  lg: "px-4 py-2 text-lg",
} as const;

/** Категория «специализация × грейд», например «Backend · Middle». */
export function CategoryBadge({ specialization, grade, variant = "soft", size = "sm", className }: CategoryBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center rounded-md border font-mono font-bold whitespace-nowrap",
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {specializationLabel(specialization)}
      <span className="mx-1.5 opacity-60" aria-hidden>
        ·
      </span>
      {gradeLabel(grade)}
    </span>
  );
}
