import { ArrowLeft, ArrowRight, Check, Info, Lightbulb } from "lucide-react";
import { ErrorState } from "@/components/ErrorState";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { apiError } from "@/lib/api-error";
import { plural } from "@/lib/format";
import { type Grade, useGrades } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

interface GradeStepProps {
  selected: Grade | null;
  suggested: Grade | null;
  currentGrade: Grade | null;
  cooldownDays: number | null;
  onSelect: (grade: Grade) => void;
  onBack: () => void;
  onNext: () => void;
}

export function GradeStep({ selected, suggested, currentGrade, cooldownDays, onSelect, onBack, onNext }: GradeStepProps) {
  const grades = useGrades();
  const suggestedName = grades.data?.find((grade) => grade.slug === suggested)?.name;

  return (
    <>
      <CardHeader>
        <CardTitle>Выберите грейд для теста</CardTitle>
        <CardDescription>Ориентируйтесь на свой опыт. Решение за вами.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {suggestedName && (
          <p className="flex items-start gap-2.5 rounded-lg border border-primary bg-primary-tint px-4 py-3 text-sm">
            <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <span>
              По стажу, который вы указали в опросе, — скорее <b className="font-mono">{suggestedName}</b>. Можно выбрать
              любой грейд: тест покажет, подходит ли он.
            </span>
          </p>
        )}
        {grades.isPending && <SkeletonCards count={4} className="sm:grid-cols-4" />}
        {grades.isError && (
          <ErrorState description={apiError(grades.error).message} onRetry={() => void grades.refetch()} />
        )}
        {grades.isSuccess && (
          <div role="radiogroup" aria-label="Грейд" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {grades.data.map((grade) => {
              const isSelected = selected === grade.slug;
              const isSuggested = suggested === grade.slug;
              return (
                <button
                  key={grade.slug}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => onSelect(grade.slug)}
                  className={cn(
                    "flex flex-col gap-1.5 rounded-xl border p-4 text-left transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                    isSelected ? "border-primary bg-primary-tint" : "hover:bg-muted",
                    isSuggested && !isSelected && "border-dashed border-primary",
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-mono text-lg font-extrabold">{grade.name}</span>
                    {isSelected && <Check className="size-4 text-primary" aria-hidden />}
                  </span>
                  <span className="text-xs text-muted-foreground">{grade.experience_hint}</span>
                  <span className="flex flex-wrap gap-1 pt-1">
                    {isSuggested && <Badge variant="soft">по стажу</Badge>}
                    {currentGrade === grade.slug && <Badge variant="muted">текущий</Badge>}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        <div className="flex gap-3 rounded-lg bg-muted p-4 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <ul className="space-y-1.5">
            <li>Грейд вы выбираете сами — тест его подтверждает или нет.</li>
            <li>Если тест не пройден, уже полученный грейд не понижается.</li>
            <li>
              {cooldownDays
                ? `Сменить грейд после получения категории можно не чаще раза в ${cooldownDays} ${plural(cooldownDays, ["день", "дня", "дней"])}.`
                : "Сменить грейд после получения категории можно не чаще раза в несколько месяцев."}{" "}
              Пока категории нет, можно сразу попробовать грейд ниже.
            </li>
          </ul>
        </div>
      </CardContent>
      <CardFooter className="justify-between gap-2 border-t border-border-subtle pt-5">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft /> Назад
        </Button>
        <Button onClick={onNext} disabled={!selected}>
          Далее <ArrowRight />
        </Button>
      </CardFooter>
    </>
  );
}
