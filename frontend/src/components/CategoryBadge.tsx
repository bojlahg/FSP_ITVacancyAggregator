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

interface CandidateCategoryBadgeProps extends Omit<CategoryBadgeProps, "specialization" | "grade"> {
  candidate: { category: { specialization: string; grade: string } | null; specialization: string };
}

/**
 * Категория кандидата в выдаче работодателя. Без действующей категории грейд не подтверждён тестом (§8.2):
 * приглушённая пометка вместо грейда — грейд не выдумываем.
 */
export function CandidateCategoryBadge({ candidate, size = "sm", className, ...props }: CandidateCategoryBadgeProps) {
  if (candidate.category) {
    return (
      <CategoryBadge
        specialization={candidate.category.specialization}
        grade={candidate.category.grade}
        size={size}
        className={className}
        {...props}
      />
    );
  }
  return (
    <span
      title="Тест ещё не подтвердил грейд: категории и результатов теста нет"
      className={cn(
        "inline-flex w-fit items-center rounded-md border border-dashed border-border bg-muted font-mono font-bold whitespace-nowrap text-muted-foreground",
        sizes[size],
        className,
      )}
    >
      {specializationLabel(candidate.specialization)}
      <span className="mx-1.5 opacity-60" aria-hidden>
        ·
      </span>
      Грейд не подтверждён
    </span>
  );
}
