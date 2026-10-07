import { ArrowDownRight, ArrowUpRight, BadgeCheck, CalendarClock, CircleHelp, PartyPopper, ShieldAlert } from "lucide-react";
import { Link, Navigate, useParams } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { StartAttemptButton } from "@/components/candidate/StartAttemptButton";
import { EmptyState } from "@/components/EmptyState";
import { GradeConfidenceBar } from "@/components/GradeConfidence";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Trace } from "@/components/Trace";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import { formatDate, toPercent } from "@/lib/format";
import { gradeLabel, specializationLabel } from "@/lib/labels";
import {
  type AttemptResultOut,
  purposeFor,
  useAttemptResult,
  useGrades,
  useGradeStatus,
  useSkillCatalog,
} from "@/lib/testing-queries";

const resultCopy: Record<AttemptResultOut["result"], { title: string; description: string }> = {
  confident_pass: {
    title: "Тест пройден уверенно",
    description: "Результат заметно выше порога грейда. Категория присвоена — её видят работодатели в поиске.",
  },
  pass: {
    title: "Тест пройден",
    description: "Грейд подтверждён. Категория присвоена — её видят работодатели в поиске.",
  },
  fail: {
    title: "Грейд не подтверждён",
    description: "Результат ниже порога выбранного грейда. Уже полученная категория при этом не понижается.",
  },
};

// Экспресс-тест (§10.3.1) категорию не присваивает — тексты о результате другие
const expressCopy: Record<AttemptResultOut["result"], { title: string; description: string }> = {
  confident_pass: {
    title: "Экспресс-тест: порог пройден уверенно",
    description: "Короткая оценка выше порога грейда с запасом. Категорию присваивает только полный тест.",
  },
  pass: {
    title: "Экспресс-тест: порог пройден",
    description: "Короткая оценка не ниже порога грейда. Категорию присваивает только полный тест.",
  },
  fail: {
    title: "Экспресс-тест: ниже порога",
    description: "Короткая оценка ниже порога грейда. Категория и попытки смены грейда не затронуты.",
  },
};

export default function TestResultPage() {
  const params = useParams();
  const attemptId = Number(params.attemptId);
  const result = useAttemptResult(attemptId);

  if (!Number.isFinite(attemptId)) return <Navigate to="/candidate/grade" replace />;

  if (result.isPending) {
    return (
      <>
        <PageHeader eyebrow="Результат теста" title="Считаем результат…" />
        <SkeletonCards count={2} className="lg:grid-cols-2" />
      </>
    );
  }
  if (result.isError) {
    const { status, code, message } = apiError(result.error);
    // Попытка ещё не закончена — возвращаем к вопросам.
    if (code === "attempt_not_finished") return <Navigate to={`/candidate/test/${attemptId}`} replace />;
    return (
      <>
        <PageHeader eyebrow="Результат теста" title="Результат недоступен" />
        <ErrorState
          title={status === 404 ? "Попытка не найдена" : "Не удалось загрузить результат"}
          description={message}
          onRetry={status === 404 ? undefined : () => void result.refetch()}
        />
      </>
    );
  }

  return <ResultView data={result.data} />;
}

function ResultView({ data }: { data: AttemptResultOut }) {
  const express = data.purpose === "express";
  const copy = (express ? expressCopy : resultCopy)[data.result];
  const failed = data.result === "fail";
  const percentile = data.percentile === null ? null : toPercent(data.percentile);

  return (
    <>
      <PageHeader eyebrow="Результат теста" title={copy.title} description={copy.description} />

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card className="relative overflow-hidden">
          <Trace width={200} height={160} radius={36} className="absolute top-0 right-0 hidden sm:block" />
          <CardHeader className="gap-3">
            <CardDescription className="flex items-center gap-2">
              {failed ? (
                <ShieldAlert className="size-4 text-destructive" aria-hidden />
              ) : (
                <PartyPopper className="size-4 text-primary" aria-hidden />
              )}
              {express ? "Экспресс-тест" : "Тест"} на {specializationLabel(data.specialization)} ·{" "}
              {gradeLabel(data.grade_target)}
            </CardDescription>
            {express ? (
              <span className="inline-flex w-fit items-center rounded-md border border-border bg-muted px-4 py-2 font-mono text-lg font-bold">
                {failed ? "Ниже порога" : "Порог пройден"}: {gradeLabel(data.grade_target)}
              </span>
            ) : failed ? (
              <span className="inline-flex w-fit items-center rounded-md border border-border bg-muted px-4 py-2 font-mono text-lg font-bold">
                Грейд не подтверждён
              </span>
            ) : (
              data.category && (
                <CategoryBadge
                  specialization={data.category.specialization}
                  grade={data.category.grade}
                  variant="solid"
                  size="lg"
                />
              )
            )}
            <Badge variant={failed ? "destructive" : "soft"}>
              {failed ? "не пройден" : data.result === "confident_pass" ? "пройден уверенно" : "пройден"}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-5">
            {failed && data.category && (
              <p className="text-sm">
                Текущая категория сохранена:{" "}
                <CategoryBadge specialization={data.category.specialization} grade={data.category.grade} />
              </p>
            )}
            {!failed && percentile !== null && (
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-5xl font-extrabold text-primary tabular-nums">{percentile}</span>
                <span className="text-sm text-muted-foreground">
                  перцентиль в категории — результат выше, чем у {percentile}% кандидатов
                </span>
              </div>
            )}
            <div className="font-mono text-xs text-muted-foreground tabular-nums">
              θ = {data.theta.toFixed(2)} ± {data.se.toFixed(2)}
            </div>
            <GradeConfidenceBar confidence={data.confidence} />
            <NextActions data={data} />
            <Button asChild variant="ghost">
              <Link to="/candidate">В кабинет</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Разбор по темам</CardTitle>
            <CardDescription>Доля верных ответов в каждой теме</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.topic_scores.length === 0 ? (
              <EmptyState title="Разбора по темам нет" description="Для этой попытки темы не посчитаны." className="py-8" />
            ) : (
              data.topic_scores.map((topic) => (
                <div key={topic.topic} className="space-y-1.5">
                  <div className="flex justify-between gap-3 text-sm">
                    <span>{topic.name}</span>
                    <span className="font-mono font-bold tabular-nums">
                      {toPercent(topic.score)}%
                      <span className="ml-1.5 font-normal text-muted-foreground">· {topic.items} зад.</span>
                    </span>
                  </div>
                  <Progress value={toPercent(topic.score)} aria-label={`${topic.name}: ${toPercent(topic.score)}%`} />
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BadgeCheck className="size-4 text-primary" aria-hidden /> Проверенные навыки
            </CardTitle>
            <CardDescription>Навык отмечается проверенным, если по нему было 2+ задания и 70%+ верных</CardDescription>
          </CardHeader>
          <CardContent>
            <VerifiedSkills ids={data.verified_skills} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CircleHelp className="size-4 text-primary" aria-hidden /> Как считается результат
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>
              Ответы переводятся в оценку θ на общей шкале специализации с учётом сложности каждого задания. Задания у
              всех кандидатов разные, но откалиброваны на одной шкале, поэтому результаты сопоставимы.
            </p>
            <p>
              Грейд подтверждается, если θ не ниже порога грейда. «Уверенно» — если даже с учётом погрешности (±)
              результат выше порога. Перцентиль показывает место среди кандидатов той же категории.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function VerifiedSkills({ ids }: { ids: string[] }) {
  const skills = useSkillCatalog(ids.length > 0);
  const names = new Map((skills.data ?? []).map((skill) => [skill.id, skill.name]));
  if (ids.length === 0) {
    return <p className="text-sm text-muted-foreground">По этой попытке проверенных навыков нет.</p>;
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {ids.map((id) => (
        <li key={id}>
          <Badge variant="soft">{names.get(id) ?? id}</Badge>
        </li>
      ))}
    </ul>
  );
}

function NextActions({ data }: { data: AttemptResultOut }) {
  const gradeStatus = useGradeStatus();
  const grades = useGrades();
  const actions = data.next_actions.filter((item) => item.action !== "none" || item.message);
  if (actions.length === 0) return null;

  return (
    <div className="space-y-3 rounded-lg bg-primary-tint p-4 text-sm">
      {actions.map((next, index) => {
        if (next.action === "none" || !next.grade) {
          return <p key={index}>{next.message}</p>;
        }
        const grade = next.grade;
        const statusAction = gradeStatus.data?.actions.find((item) => item.grade === grade);
        const availableAt = statusAction && !statusAction.allowed ? statusAction.available_at : next.available_at;
        // available_at приходит, только когда действие сейчас недоступно.
        const locked = statusAction ? !statusAction.allowed : Boolean(next.available_at);
        const Icon = next.action === "retake_lower" ? ArrowDownRight : ArrowUpRight;
        const label =
          next.action === "full_test"
            ? "Полный тест"
            : next.action === "try_higher"
              ? "Тест на грейд выше"
              : "Тест на грейд ниже";
        return (
          <div key={index} className="space-y-2">
            <p>{next.message}</p>
            {locked ? (
              <p className="flex items-center gap-2 text-muted-foreground">
                <CalendarClock className="size-4 text-primary" aria-hidden />
                <span>
                  Тест на грейд {gradeLabel(grade)} будет доступен{" "}
                  {availableAt ? <b className="font-mono text-foreground">{formatDate(availableAt)}</b> : "позже"}
                </span>
              </p>
            ) : (
              <StartAttemptButton
                variant={next.action === "retake_lower" ? "outline" : "default"}
                disabled={gradeStatus.isPending}
                params={{
                  specialization: data.specialization,
                  grade_target: grade,
                  purpose: purposeFor(grade, gradeStatus.data, grades.data, data.category?.grade),
                }}
                className="justify-items-start"
              >
                {label}: {gradeLabel(grade)}{" "}
                <Icon />
              </StartAttemptButton>
            )}
          </div>
        );
      })}
    </div>
  );
}
