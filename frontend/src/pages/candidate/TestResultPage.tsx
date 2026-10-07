import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  CalendarClock,
  ChevronDown,
  Gauge,
  ListChecks,
  Mail,
  PartyPopper,
  ShieldAlert,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";
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

// Уровень темы считает сервер по порогам content/blueprints.yaml (topic_levels)
const TOPIC_LEVELS: Record<TopicScore["level"], { label: string; badge: "soft" | "muted" | "destructive" }> = {
  strong: { label: "сильная сторона", badge: "soft" },
  medium: { label: "на уровне", badge: "muted" },
  weak: { label: "стоит подтянуть", badge: "destructive" },
  insufficient: { label: "мало заданий для вывода", badge: "muted" },
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

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <OutcomeCard data={data} status={gradeStatus.data} />
        <NextStepsCard data={data} status={gradeStatus.data} statusPending={gradeStatus.isPending} />
        <TopicsCard topics={data.topic_scores} />
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BadgeCheck className="size-4 text-primary" aria-hidden /> Проверенные навыки
            </CardTitle>
            <CardDescription>
              Навыки, по которым тест дал достаточно заданий и большинство ответов верные. Работодатель видит их с
              отметкой «проверено тестом».
            </CardDescription>
          </CardHeader>
          <CardContent>
            <VerifiedSkills ids={data.verified_skills} />
          </CardContent>
        </Card>
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

function OutcomeCard({ data, status }: { data: AttemptResultOut; status: GradeStatus | undefined }) {
  const express = data.purpose === "express";
  const failed = data.result === "fail";
  const percentile = data.percentile === null ? null : toPercent(data.percentile);
  const target = gradeLabel(data.grade_target);
  // Когда можно повторить тест на этот же грейд — по правилам грейда с сервера (§6.3)
  const retry = status?.actions.find((action) => action.grade === data.grade_target);
  const likely = failed ? likelyGrade(data) : null;

  return (
    <Card className="relative overflow-hidden">
      <Trace width={140} height={88} radius={28} className="pointer-events-none absolute top-0 right-0 hidden sm:block" />
      <CardHeader className="gap-3">
        <CardDescription className="flex items-center gap-2 text-foreground">
          {failed ? (
            <ShieldAlert className="size-4 text-destructive" aria-hidden />
          ) : (
            <PartyPopper className="size-4 text-primary" aria-hidden />
          )}
          {express ? "Экспресс-тест" : "Тест"} на {specializationLabel(data.specialization)} · {target}
        </CardDescription>
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
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {!failed && percentile !== null && data.category && (
          <div className="space-y-1">
            <div className="flex flex-wrap items-baseline gap-x-2 font-mono font-extrabold text-primary">
              <span className="text-2xl">сильнее</span>
              <span className="text-5xl tabular-nums">{percentile}%</span>
            </div>
            <p className="text-base">кандидатов категории {data.category.label}</p>
          </div>
        )}
        {failed && (
          <p className="text-base">
            {likely ? (
              <>
                По этому тесту ваш уровень сейчас — <b className="font-mono">{likely}</b>.
              </>
            ) : (
              "По этому тесту результат пока ниже порога самого младшего грейда."
            )}
          </p>
        )}
        {failed && data.category && (
          <p>
            Текущая категория сохранена:{" "}
            <CategoryBadge specialization={data.category.specialization} grade={data.category.grade} />
          </p>
        )}
        {failed && !express && retry && (
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
        {failed && express && <p>Экспресс-тест короткий и неточный — полный тест покажет уровень надёжнее.</p>}
      </CardContent>
    </Card>
  );
}

function NextStepsCard({
  data,
  status,
  statusPending,
}: {
  data: AttemptResultOut;
  status: GradeStatus | undefined;
  statusPending: boolean;
}) {
  const express = data.purpose === "express";
  const testActions = data.next_actions.filter((item) => item.action !== "none" || item.message);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ArrowRight className="size-4 text-primary" aria-hidden /> Что дальше
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-5 text-sm">
          {testActions.map((next, index) => (
            <TestStep key={index} next={next} data={data} status={status} statusPending={statusPending} />
          ))}
          <Step icon={UserRound}>
            <p>
              <b>Заполните профиль:</b> укажите стек, которым владеете, — работодатели ищут по навыкам.
            </p>
            <Button asChild variant="outline" size="sm">
              <Link to="/candidate/profile">Профиль и резюме</Link>
            </Button>
          </Step>
          {!express && data.category && (
            <Step icon={Mail}>
              <p>
                <b>Ждите приглашений</b> — работодатели пишут первыми и сразу указывают вилку зарплаты.
              </p>
              <Button asChild variant="outline" size="sm">
                <Link to="/candidate/invitations">Приглашения</Link>
              </Button>
            </Step>
          )}
          <li>
            <Button asChild variant="ghost" size="sm">
              <Link to="/candidate">В кабинет</Link>
            </Button>
          </li>
        </ol>
      </CardContent>
    </Card>
  );
}

function Step({ icon: Icon, children }: { icon: typeof Mail; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
      <div className="min-w-0 flex-1 space-y-2">{children}</div>
    </li>
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
      <Step icon={BadgeCheck}>
        <p>{next.message}</p>
      </Step>
    );
  }
  const grade = next.grade;
  const statusAction = status?.actions.find((item) => item.grade === grade);
  // Действия на текущий грейд grade-status не отдаёт: тест на него недоступен (same_grade)
  if (status && !statusAction) return null;
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
      <Step icon={CalendarClock}>
        <p>{intro}</p>
        <p>
          Тест на {name} будет доступен{" "}
          {availableAt ? <b className="font-mono">{formatDate(availableAt)}</b> : "позже"}
          {statusAction?.reason ? `: ${statusAction.reason.charAt(0).toLowerCase()}${statusAction.reason.slice(1)}.` : "."}
        </p>
      </Step>
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
    <Step icon={Icon}>
      <p>{intro}</p>
      <StartAttemptButton
        variant={primary ? "default" : "outline"}
        disabled={statusPending}
        params={{
          specialization: data.specialization,
          grade_target: grade,
          purpose: purposeFor(grade, status, grades.data, data.category?.grade),
        }}
        className="justify-items-start"
      >
        {label} <Icon />
      </StartAttemptButton>
      {next.action === "try_higher" && status && (
        <p className="text-muted-foreground">
          Ждать {days(status.cooldown_days)} между сменами грейда не нужно — тест доступен прямо сейчас.
          {data.category && ` Если не получится, категория ${data.category.label} сохранится.`}
        </p>
      )}
    </Step>
  );
}

function TopicsCard({ topics }: { topics: TopicScore[] }) {
  const sorted = [...topics].sort(
    (a, b) => TOPIC_ORDER.indexOf(a.level) - TOPIC_ORDER.indexOf(b.level) || b.score - a.score,
  );
  const strong = topics.filter((topic) => topic.level === "strong").map((topic) => topic.name);
  const weak = topics.filter((topic) => topic.level === "weak").map((topic) => topic.name);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ListChecks className="size-4 text-primary" aria-hidden /> Разбор по темам
        </CardTitle>
        <CardDescription>Доля верных ответов в каждой теме теста</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {topics.length === 0 ? (
          <EmptyState title="Разбора по темам нет" description="Для этой попытки темы не посчитаны." className="py-8" />
        ) : (
          <>
            {(strong.length > 0 || weak.length > 0) && (
              <div className="space-y-1 rounded-lg bg-primary-tint p-3 text-sm">
                {strong.length > 0 && (
                  <p>
                    <b>Сильные стороны:</b> {strong.join(", ")}.
                  </p>
                )}
                {weak.length > 0 && (
                  <p>
                    <b>Стоит подтянуть:</b> {weak.join(", ")}.
                  </p>
                )}
              </div>
            )}
            <ul className="space-y-4">
              {sorted.map((topic) => {
                const level = TOPIC_LEVELS[topic.level];
                const percent = toPercent(topic.score);
                return (
                  <li key={topic.topic} className="space-y-1.5">
                    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{topic.name}</span>
                        <Badge variant={level.badge}>{level.label}</Badge>
                      </span>
                      <span className="font-mono tabular-nums">
                        <b>{percent}%</b> верно · {topic.items}{" "}
                        {plural(topic.items, ["задание", "задания", "заданий"])}
                      </span>
                    </div>
                    <Progress value={percent} aria-label={`${topic.name}: ${percent}% верных ответов`} />
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** θ̂, SE и уверенность (§10.4, §10.4.1): те же данные, что раньше были на первом экране, — для любопытных и жюри. */
function CalculationDetails({ data }: { data: AttemptResultOut }) {
  return (
    <Card className="lg:col-span-2">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-6 py-1 font-mono text-base font-bold [&::-webkit-details-marker]:hidden">
          <span className="flex items-center gap-2">
            <Gauge className="size-4 text-primary" aria-hidden /> Подробнее о расчёте
          </span>
          <ChevronDown className="size-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <div className="space-y-4 px-6 pt-4 text-sm">
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
          <Badge variant="soft">{names.get(id) ?? id}</Badge>
        </li>
      ))}
    </ul>
  );
}
