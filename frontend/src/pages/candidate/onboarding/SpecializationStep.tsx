import { ArrowLeft, ArrowRight, Check, Loader2 } from "lucide-react";
import { useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import { toPercent } from "@/lib/format";
import {
  type SpecializationOut,
  type SurveyResult,
  useConfirmSpecialization,
  useSpecializations,
} from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

interface SpecializationStepProps {
  surveyResult: SurveyResult | null;
  /** Уже подтверждённая специализация из профиля. */
  current: string | null;
  /** Выбранная, но ещё не подтверждённая карточка — из черновика онбординга. */
  initialPicked?: string | null;
  onPick?: (specialization: string) => void;
  onBack: () => void;
  onConfirmed: (specialization: string) => void;
  /** 409 survey_required: опрос не засчитан — вернуть кандидата к опросу. */
  onSurveyRequired: () => void;
}

export function SpecializationStep({
  surveyResult,
  current,
  initialPicked = null,
  onPick,
  onBack,
  onConfirmed,
  onSurveyRequired,
}: SpecializationStepProps) {
  const catalog = useSpecializations();
  const confirm = useConfirmSpecialization();
  const firstTestable =
    surveyResult?.recommended.find((item) => catalog.data?.some((s) => s.slug === item.specialization && s.has_test))
      ?.specialization ?? null;
  const [picked, setPicked] = useState<string | null>(initialPicked);
  const selected = picked ?? current ?? firstTestable;

  if (catalog.isPending) {
    return (
      <CardContent>
        <SkeletonCards count={2} className="sm:grid-cols-2" />
      </CardContent>
    );
  }
  if (catalog.isError) {
    return (
      <CardContent>
        <ErrorState description={apiError(catalog.error).message} onRetry={() => void catalog.refetch()} />
      </CardContent>
    );
  }

  const bySlug = new Map(catalog.data.map((item) => [item.slug, item]));
  const recommended = (surveyResult?.recommended ?? []).filter((item) => bySlug.has(item.specialization));
  const recommendedSlugs = new Set(recommended.map((item) => item.specialization));
  const others = catalog.data.filter((item) => !recommendedSlugs.has(item.slug));

  const onConfirm = () => {
    if (!selected) return;
    confirm.mutate(selected, {
      onSuccess: () => onConfirmed(selected),
      onError: (err) => {
        if (apiError(err).code === "survey_required") onSurveyRequired();
      },
    });
  };

  const renderOption = (spec: SpecializationOut, score?: number) => {
    const isSelected = selected === spec.slug;
    return (
      <button
        key={spec.slug}
        type="button"
        onClick={() => {
          setPicked(spec.slug);
          onPick?.(spec.slug);
        }}
        disabled={!spec.has_test}
        aria-pressed={isSelected}
        className={cn(
          "flex flex-col gap-2 rounded-xl border p-4 text-left transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
          isSelected ? "border-primary bg-primary-tint" : "hover:bg-muted",
          !spec.has_test && "cursor-not-allowed opacity-60 hover:bg-transparent",
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="font-mono font-bold">{spec.name}</span>
          {isSelected && <Check className="size-4 shrink-0 text-primary" aria-hidden />}
          {!spec.has_test && <Badge variant="muted">тест скоро</Badge>}
        </div>
        {score !== undefined && (
          <div className="flex items-center gap-2">
            <Progress value={toPercent(score)} className="h-1.5" aria-label={`Совпадение с ответами: ${toPercent(score)}%`} />
            <span className="font-mono text-xs tabular-nums">{toPercent(score)}%</span>
          </div>
        )}
        {spec.description && <span className="text-xs text-muted-foreground">{spec.description}</span>}
      </button>
    );
  };

  const error = confirm.isError && apiError(confirm.error).code !== "survey_required" ? apiError(confirm.error).message : null;

  return (
    <>
      <CardHeader>
        <CardTitle>Подтвердите специализацию</CardTitle>
        <CardDescription>
          {recommended.length > 0
            ? "Рассчитано по ответам опроса. Подтвердите вариант или выберите другой."
            : "Выберите направление, по которому будете проходить тест."}{" "}
          Тест сейчас есть не для всех направлений.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {recommended.length > 0 && (
          <section className="space-y-3">
            <h2 className="font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Рекомендуем по ответам
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {recommended.map((item) => renderOption(bySlug.get(item.specialization)!, item.score))}
            </div>
          </section>
        )}
        <section className="space-y-3">
          {recommended.length > 0 && (
            <h2 className="font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Другие направления
            </h2>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{others.map((spec) => renderOption(spec))}</div>
        </section>
        <FormAlert message={error} />
      </CardContent>
      <CardFooter className="justify-between gap-2 border-t border-border-subtle pt-5">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft /> К опросу
        </Button>
        <Button onClick={onConfirm} disabled={!selected || confirm.isPending}>
          {confirm.isPending && <Loader2 className="animate-spin" aria-hidden />}
          Подтвердить <ArrowRight />
        </Button>
      </CardFooter>
    </>
  );
}
