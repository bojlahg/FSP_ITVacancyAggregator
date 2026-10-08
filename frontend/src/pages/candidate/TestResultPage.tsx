import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  CalendarClock,
  Check,
  ChevronDown,
  Gauge,
  ListChecks,
  PartyPopper,
  ShieldAlert,
} from "lucide-react";
import { type ReactNode, useId } from "react";
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
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import { formatDate, plural, toPercent } from "@/lib/format";
import { gradeLabel, specializationLabel } from "@/lib/labels";
import {
  type AttemptResultOut,
  type GradeStatus,
  purposeFor,
  useAttemptResult,
  useGrades,
  useGradeStatus,
  useSkillCatalog,
} from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

type TopicScore = AttemptResultOut["topic_scores"][number];
type NextAction = AttemptResultOut["next_actions"][number];

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

const TOPIC_ORDER: TopicScore["level"][] = ["strong", "medium", "weak", "insufficient"];

const days = (n: number) => `${n} ${plural(n, ["день", "дня", "дней"])}`;

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
  const gradeStatus = useGradeStatus();
  const express = data.purpose === "express";
  const copy = (express ? expressCopy : resultCopy)[data.result];

  return (
    <>
      <PageHeader eyebrow="Результат теста" title={copy.title} description={copy.description} />

      <div className="space-y-4 lg:space-y-6">
        <OutcomeHero data={data} status={gradeStatus.data} statusPending={gradeStatus.isPending} />
        <div className="grid items-start gap-4 lg:grid-cols-[2fr_1fr] lg:gap-6">
          <TopicsCard topics={data.topic_scores} />
          <NextStepsCard data={data} />
        </div>
        <CalculationDetails data={data} />
      </div>
    </>
  );
}

/**
 * Полоса грейда с наибольшей вероятностью — какой уровень показал тест (§10.4.1, только объяснение).
 * null — ниже порога самого младшего грейда.
 */
function likelyGrade(data: AttemptResultOut): string | null {
  const top = data.confidence.bands.reduce((best, band) => (band.probability > best.probability ? band : best));
  return top.grade ? gradeLabel(top.grade) : null;
}

const eyebrowClass = "font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase";

/** Герой результата: слева исход и проверенные навыки, справа «Следующий шаг» — тест на другой грейд. */
function OutcomeHero({
  data,
  status,
  statusPending,
}: {
  data: AttemptResultOut;
  status: GradeStatus | undefined;
  statusPending: boolean;
}) {
  // Действия на текущий грейд grade-status не отдаёт: тест на него недоступен (same_grade)
  const testActions = data.next_actions.filter((next) =>
    next.action === "none" || !next.grade
      ? Boolean(next.message)
      : !status || status.actions.some((item) => item.grade === next.grade),
  );

  return (
    <section
      aria-label="Итог теста"
      className={cn(
        "relative grid rounded-xl border bg-card text-card-foreground",
        testActions.length > 0 && "lg:grid-cols-[3fr_2fr]",
      )}
    >
      <Trace width={84} height={48} radius={24} className="absolute -top-px right-6 hidden sm:block" />
      <div className="flex min-w-0 flex-col gap-5 p-4 sm:p-6">
        <OutcomeSummary data={data} status={status} />
      </div>
      {testActions.length > 0 && (
        <div className="flex min-w-0 flex-col gap-3 border-t border-border-subtle p-4 sm:p-6 lg:row-span-2 lg:my-6 lg:border-t-0 lg:border-l lg:py-0 lg:pr-6 lg:pl-8">
          <h2 className={eyebrowClass}>Следующий шаг</h2>
          <div className="space-y-6">
            {testActions.map((next, index) => (
              <TestStep key={index} next={next} data={data} status={status} statusPending={statusPending} />
            ))}
          </div>
        </div>
      )}
      <div className="flex min-w-0 flex-col gap-2 border-t border-border-subtle p-4 pt-4 sm:mx-6 sm:mb-6 sm:px-0 sm:pb-0 lg:col-start-1">
        <h2 className={cn(eyebrowClass, "flex items-center gap-1.5")}>
          <BadgeCheck className="size-3.5 text-primary" aria-hidden /> Проверенные навыки
        </h2>
        <VerifiedSkills ids={data.verified_skills} />
        <p className="text-xs text-muted-foreground">
          Навыки, по которым тест дал достаточно заданий и большинство ответов верные. Работодатель видит их с отметкой
          «проверено тестом».
        </p>
      </div>
    </section>
  );
}

function OutcomeSummary({ data, status }: { data: AttemptResultOut; status: GradeStatus | undefined }) {
  const express = data.purpose === "express";
  const failed = data.result === "fail";
  const percentile = data.percentile === null ? null : toPercent(data.percentile);
  const target = gradeLabel(data.grade_target);
  // Когда можно повторить тест на этот же грейд — по правилам грейда с сервера (§6.3)
  const retry = status?.actions.find((action) => action.grade === data.grade_target);
  const likely = failed ? likelyGrade(data) : null;

  return (
    <>
      <div className="space-y-3">
        <p className="flex items-center gap-2 pr-24 text-sm text-muted-foreground max-sm:pr-0">
          {failed ? (
            <ShieldAlert className="size-4 shrink-0 text-destructive" aria-hidden />
          ) : (
            <PartyPopper className="size-4 shrink-0 text-primary" aria-hidden />
          )}
          {express ? "Экспресс-тест" : "Тест"} на {specializationLabel(data.specialization)} · {target}
        </p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          {express ? (
            <span className="inline-flex w-fit items-center rounded-md border border-border bg-muted px-4 py-2 font-mono text-lg font-bold">
              {failed ? "Ниже порога" : "Порог пройден"}: {target}
            </span>
          ) : failed ? (
            <span className="inline-flex w-fit items-center rounded-md border border-border bg-muted px-4 py-2 font-mono text-lg font-bold">
              {target} не подтверждён
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
        </div>
      </div>

      {!failed && percentile !== null && data.category && (
        <div className="space-y-1">
          <p className="font-mono text-3xl font-semibold tracking-tight text-primary tabular-nums">
            сильнее {percentile}%
          </p>
          <p className="text-sm text-muted-foreground">кандидатов категории {data.category.label}</p>
        </div>
      )}

      {failed && (
        <div className="space-y-3 text-sm">
          <p className="text-base">
            {likely ? (
              <>
                По этому тесту ваш уровень сейчас — <b className="font-mono">{likely}</b>.
              </>
            ) : (
              "По этому тесту результат пока ниже порога самого младшего грейда."
            )}
          </p>
          {data.category && (
            <p>
              Текущая категория сохранена:{" "}
              <CategoryBadge specialization={data.category.specialization} grade={data.category.grade} />
            </p>
          )}
          {!express && retry && (
            <p className="flex items-start gap-2">
              <CalendarClock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              <span>
                {retry.allowed ? (
                  <>Повторить тест на {target} можно уже сейчас.</>
                ) : retry.available_at ? (
                  <>
                    Повторить тест на {target} можно с{" "}
                    <b className="font-mono">{formatDate(retry.available_at)}</b>
                    {status && ` — пауза ${days(status.failed_retry_days)} защищает от заучивания заданий`}.
                  </>
                ) : (
                  <>Повторить тест на {target} пока нельзя.</>
                )}
              </span>
            </p>
          )}
          {express && <p>Экспресс-тест короткий и неточный — полный тест покажет уровень надёжнее.</p>}
        </div>
      )}
    </>
  );
}

/** «Что дальше» — нумерованные шаги вне теста: профиль и приглашения. */
function NextStepsCard({ data }: { data: AttemptResultOut }) {
  const express = data.purpose === "express";
  const steps: { key: string; text: ReactNode; to: string; action: string }[] = [
    {
      key: "profile",
      text: (
        <>
          <b className="font-semibold">Заполните профиль:</b> укажите стек, которым владеете, — работодатели ищут по
          навыкам.
        </>
      ),
      to: "/candidate/profile",
      action: "Профиль и резюме",
    },
  ];
  if (!express && data.category) {
    steps.push({
      key: "invitations",
      text: (
        <>
          <b className="font-semibold">Ждите приглашений</b> — работодатели пишут первыми и сразу указывают вилку
          зарплаты.
        </>
      ),
      to: "/candidate/invitations",
      action: "Приглашения",
    });
  }

  return (
    <Card className="gap-5 p-4 sm:p-6">
      <h2 className="flex items-center gap-2 font-mono text-base font-semibold tracking-tight">
        <ArrowRight className="size-4 text-primary" aria-hidden /> Что дальше
      </h2>
      <ol className="space-y-5 text-sm">
        {steps.map((step, index) => (
          <li key={step.key} className="flex gap-3">
            <span
              className="flex size-7 shrink-0 items-center justify-center rounded-full border border-primary font-mono text-[13px] font-medium text-primary"
              aria-hidden
            >
              {index + 1}
            </span>
            <div className="flex min-w-0 flex-1 flex-col items-start gap-2.5">
              <p>{step.text}</p>
              <Button asChild variant="outline" className="max-sm:h-11">
                <Link to={step.to}>{step.action}</Link>
              </Button>
            </div>
          </li>
        ))}
      </ol>
      <Link
        to="/candidate"
        className="inline-flex w-fit items-center gap-1.5 rounded-sm text-sm font-medium hover:text-primary focus-visible:ring-[3px] focus-visible:ring-ring/40 focus-visible:outline-none max-sm:h-11"
      >
        В кабинет <ArrowRight className="size-4" aria-hidden />
      </Link>
    </Card>
  );
}

function TestStep({
  next,
  data,
  status,
  statusPending,
}: {
  next: NextAction;
  data: AttemptResultOut;
  status: GradeStatus | undefined;
  statusPending: boolean;
}) {
  const grades = useGrades();
  if (next.action === "none" || !next.grade) {
    return (
      <p className="flex items-start gap-2 text-base font-medium">
        <BadgeCheck className="mt-1 size-4 shrink-0 text-primary" aria-hidden />
        {next.message}
      </p>
    );
  }
  const grade = next.grade;
  const statusAction = status?.actions.find((item) => item.grade === grade);
  // available_at приходит, только когда действие сейчас недоступно
  const locked = statusAction ? !statusAction.allowed : Boolean(next.available_at);
  const availableAt = statusAction && !statusAction.allowed ? statusAction.available_at : next.available_at;
  const name = gradeLabel(grade);
  const up = next.action !== "retake_lower";
  const Icon = up ? ArrowUpRight : ArrowDownRight;

  const intro =
    next.action === "full_test"
      ? "Категорию присваивает только полный тест — он точнее экспресс-оценки."
      : next.action === "try_higher"
        ? data.result === "confident_pass"
          ? `Результат заметно выше порога — попробуйте ${name}.`
          : `Можно попробовать следующий грейд — ${name}.`
        : data.category
          ? `Можно пройти тест на грейд ниже — ${name}.`
          : `Категория появится, когда тест подтвердит грейд. Попробуйте грейд ниже — ${name}.`;

  if (locked) {
    return (
      <div className="space-y-2">
        <p className="text-base font-medium">{intro}</p>
        <p className="flex items-start gap-2 text-sm">
          <CalendarClock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <span>
            Тест на {name} будет доступен{" "}
            {availableAt ? <b className="font-mono">{formatDate(availableAt)}</b> : "позже"}
            {statusAction?.reason
              ? `: ${statusAction.reason.charAt(0).toLowerCase()}${statusAction.reason.slice(1)}.`
              : "."}
          </span>
        </p>
      </div>
    );
  }

  const label =
    next.action === "full_test"
      ? `Пройти полный тест на ${name}`
      : next.action === "try_higher"
        ? `Пройти тест на ${name} сейчас`
        : `Пройти тест на ${name}`;
  // Грейд выше и полный тест — главное действие экрана; грейд ниже при действующей категории — второстепенное
  const primary = up || !data.category;

  return (
    <div className="space-y-3">
      <p className="text-base font-medium">{intro}</p>
      <StartAttemptButton
        variant={primary ? "default" : "outline"}
        size={primary ? "lg" : "default"}
        disabled={statusPending}
        params={{
          specialization: data.specialization,
          grade_target: grade,
          purpose: purposeFor(grade, status, grades.data, data.category?.grade),
        }}
        className="sm:justify-items-start"
      >
        {label} <Icon />
      </StartAttemptButton>
      {next.action === "try_higher" && status && (
        <p className="text-xs text-muted-foreground sm:text-sm">
          Ждать {days(status.cooldown_days)} между сменами грейда не нужно — тест доступен прямо сейчас.
          {data.category && ` Если не получится, категория ${data.category.label} сохранится.`}
        </p>
      )}
    </div>
  );
}

const TOPIC_GROUP_TITLE: Record<TopicScore["level"], string> = {
  strong: "Сильные стороны",
  medium: "На уровне",
  weak: "Стоит подтянуть",
  insufficient: "Мало заданий для вывода",
};

function TopicsCard({ topics }: { topics: TopicScore[] }) {
  const groups = TOPIC_ORDER.map((level) => ({
    level,
    items: topics.filter((topic) => topic.level === level).sort((a, b) => b.score - a.score),
  })).filter((group) => group.items.length > 0);
  const strong = topics.filter((topic) => topic.level === "strong").map((topic) => topic.name);
  const weak = topics.filter((topic) => topic.level === "weak").map((topic) => topic.name);

  return (
    <Card className="min-w-0 gap-5 p-4 sm:p-6">
      <div className="space-y-1">
        <h2 className="flex items-center gap-2 font-mono text-base font-semibold tracking-tight">
          <ListChecks className="size-4 text-primary" aria-hidden /> Разбор по темам
        </h2>
        <p className="text-sm text-muted-foreground">Доля верных ответов в каждой теме теста</p>
      </div>
      {topics.length === 0 ? (
        <EmptyState title="Разбора по темам нет" description="Для этой попытки темы не посчитаны." className="py-8" />
      ) : (
        <>
          {(strong.length > 0 || weak.length > 0) && (
            <div className="space-y-1 rounded-lg bg-primary-tint px-4 py-3 text-sm">
              {strong.length > 0 && (
                <p>
                  <b className="font-semibold">Сильные стороны:</b> {strong.join(", ")}.
                </p>
              )}
              {weak.length > 0 && (
                <p>
                  <b className="font-semibold">Стоит подтянуть:</b> {weak.join(", ")}.
                </p>
              )}
            </div>
          )}
          {groups.map((group, index) => (
            <TopicGroup key={group.level} level={group.level} topics={group.items} divided={index > 0} />
          ))}
        </>
      )}
    </Card>
  );
}

/** Темы одного уровня: уровень считает сервер по порогам content/blueprints.yaml (topic_levels). */
function TopicGroup({ level, topics, divided }: { level: TopicScore["level"]; topics: TopicScore[]; divided: boolean }) {
  const titleId = useId();
  const faint = level === "insufficient";
  return (
    <section aria-labelledby={titleId} className={cn("space-y-3", divided && "border-t border-border-subtle pt-4")}>
      <h3
        id={titleId}
        className={cn(
          "font-mono text-xs font-medium tracking-wider uppercase",
          level === "strong" ? "text-primary" : level === "weak" ? "text-destructive-strong" : "text-muted-foreground",
        )}
      >
        {TOPIC_GROUP_TITLE[level]}
      </h3>
      <ul className="space-y-3.5">
        {topics.map((topic) => {
          const percent = toPercent(topic.score);
          return (
            <li key={topic.topic} className="space-y-2">
              <div className="flex items-baseline justify-between gap-3 text-sm sm:gap-4">
                <span className={cn("min-w-0 font-medium", faint && "text-muted-foreground")}>{topic.name}</span>
                <span className="shrink-0 font-mono text-xs whitespace-nowrap text-muted-foreground tabular-nums sm:text-[13px]">
                  <b className={cn("font-semibold", !faint && "text-foreground")}>{percent}%</b> верно · {topic.items}{" "}
                  {plural(topic.items, ["задание", "задания", "заданий"])}
                </span>
              </div>
              <Progress
                value={percent}
                className="h-1.5"
                indicatorClassName={cn(faint && "bg-primary-pale")}
                aria-label={`${topic.name}: ${percent}% верных ответов`}
              />
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** θ̂, SE и уверенность (§10.4, §10.4.1): те же данные, что раньше были на первом экране, — для любопытных и жюри. */
function CalculationDetails({ data }: { data: AttemptResultOut }) {
  return (
    <Card className="py-0">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-4 py-5 font-mono text-base font-semibold tracking-tight focus-visible:ring-[3px] focus-visible:ring-ring/40 focus-visible:outline-none sm:px-6 [&::-webkit-details-marker]:hidden">
          <span className="flex items-center gap-2">
            <Gauge className="size-4 text-primary" aria-hidden /> Подробнее о расчёте
          </span>
          <ChevronDown className="size-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <div className="space-y-4 px-4 pb-5 text-sm sm:px-6 sm:pb-6">
          <p className="font-mono tabular-nums">
            θ̂ = {data.theta.toFixed(2)} ± {data.se.toFixed(2)}{" "}
            <span className="font-sans">— оценка способности на шкале специализации и её погрешность (SE)</span>
          </p>
          <GradeConfidenceBar confidence={data.confidence} />
          <p>
            Ответы переводятся в оценку θ на общей шкале специализации с учётом сложности каждого задания (модель IRT
            3PL). Задания у всех кандидатов разные, но откалиброваны на одной шкале, поэтому результаты сопоставимы.
          </p>
          <p>
            Грейд подтверждается, если θ̂ не ниже порога грейда. «Уверенно» — если даже с учётом погрешности результат
            выше порога. Перцентиль показывает место среди кандидатов той же категории.
          </p>
          <Link to="/how-it-works" className="inline-block text-primary hover:underline">
            Как работает тест
          </Link>
        </div>
      </details>
    </Card>
  );
}

function VerifiedSkills({ ids }: { ids: string[] }) {
  const skills = useSkillCatalog(ids.length > 0);
  const names = new Map((skills.data ?? []).map((skill) => [skill.id, skill.name]));
  if (ids.length === 0) {
    return <p className="text-sm">По этой попытке проверенных навыков нет.</p>;
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {ids.map((id) => (
        <li key={id}>
          <Badge variant="soft">
            <Check aria-hidden /> {names.get(id) ?? id}
          </Badge>
        </li>
      ))}
    </ul>
  );
}
