import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Award,
  CalendarClock,
  ChevronRight,
  ClipboardList,
  History,
  RotateCw,
  Target,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { AbandonExpressButton } from "@/components/candidate/AbandonExpressButton";
import { GradeExplanationCard } from "@/components/candidate/GradeExplanationCard";
import { ExpressTestCard } from "@/components/candidate/ExpressTestCard";
import { StartAttemptButton } from "@/components/candidate/StartAttemptButton";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { type GradeConfidence, GradeEvidenceCard } from "@/components/GradeConfidence";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import { formatDate, plural, toPercent } from "@/lib/format";
import {
  ATTEMPT_PURPOSE_LABELS,
  ATTEMPT_RESULT_LABELS,
  ATTEMPT_STATUS_LABELS,
  gradeLabel,
  specializationLabel,
} from "@/lib/labels";
import {
  type Grade,
  type GradeStatus,
  gradeOrder,
  purposeFor,
  useCandidateMe,
  useGrades,
  useGradeStatus,
} from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

type GradeAction = GradeStatus["actions"][number];
type CategoryRecord = GradeStatus["history"][number];
type AttemptSummary = GradeStatus["attempts"][number];

const actionView: Record<string, { label: string; icon: LucideIcon }> = {
  calibrate: { label: "Тест на грейд", icon: Target },
  upgrade: { label: "Повысить до грейда", icon: ArrowUp },
  downgrade: { label: "Понизить до грейда", icon: ArrowDown },
  retry: { label: "Повторить тест на грейд", icon: RotateCw },
  // Срок категории истёк (§6.3): тот же грейд — подтверждение
  reconfirm: { label: "Подтвердить грейд", icon: RotateCw },
  // Настройка платформы GRADE_RETEST_CAN_DOWNGRADE: перепроверка своего грейда, провал понижает
  retest: { label: "Перепроверить грейд", icon: RotateCw },
};

const FALLBACK_GRADES: Grade[] = ["intern", "junior", "middle", "senior"];
const LEVEL_BADGE: Record<string, "soft" | "outline" | "muted"> = { high: "soft", medium: "outline", low: "muted" };

const eyebrow = "font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase";

export default function GradePage() {
  const status = useGradeStatus();
  const me = useCandidateMe();

  return (
    <>
      <PageHeader
        eyebrow="Категория и грейд"
        title="Категория и грейд"
        description="Текущая категория, история тестов и ближайшие возможности сменить грейд. Неудачная попытка повышения не понижает текущий грейд."
      />
      {status.isPending && <GradeSkeleton />}
      {status.isError && (
        <ErrorState
          title="Не удалось загрузить категорию и грейд"
          description={apiError(status.error).message}
          onRetry={() => void status.refetch()}
        />
      )}
      {status.isSuccess && (
        <GradeView
          status={status.data}
          specialization={status.data.current?.category.specialization ?? me.data?.specialization ?? null}
        />
      )}
    </>
  );
}

function GradeView({ status, specialization }: { status: GradeStatus; specialization: string | null }) {
  const { current } = status;
  const inProgress = status.attempts.find((attempt) => attempt.status === "in_progress");
  const showExpress = Boolean(status.express && specialization);
  const showEvidence = Boolean(current?.evidence);

  return (
    <div className="grid gap-4">
      <StatusSection status={status} specialization={specialization} inProgress={inProgress} />

      {(showExpress || showEvidence) && (
        <div className={cn("grid gap-4", showExpress && showEvidence && "lg:grid-cols-2")}>
          {status.express && specialization && (
            <ExpressTestCard
              express={status.express}
              specialization={specialization}
              defaultGrade={current?.category.grade ?? "junior"}
              disabled={Boolean(inProgress)}
              unfinishedExpress={inProgress?.purpose === "express"}
            />
          )}
          {current?.evidence && <GradeEvidenceCard evidence={current.evidence} audience="candidate" showConfidence={false} />}
        </div>
      )}

      <HistoryCard status={status} />

      <GradeExplanationCard />
    </div>
  );
}

// ---------- текущий статус ----------

function StatusSection({
  status,
  specialization,
  inProgress,
}: {
  status: GradeStatus;
  specialization: string | null;
  inProgress: AttemptSummary | undefined;
}) {
  const { current } = status;
  const confidence = current?.evidence?.confidence ?? null;

  return (
    <section aria-label="Текущий статус" className="min-w-0 rounded-xl border bg-card">
      <div className="flex flex-col gap-5 p-5 lg:flex-row lg:items-center lg:gap-8">
        <div className="flex shrink-0 flex-col items-start gap-2 lg:w-64">
          <span className={eyebrow}>Текущий статус</span>
          {current ? (
            <CategoryBadge
              specialization={current.category.specialization}
              grade={current.category.grade}
              variant="solid"
              size="lg"
              className="rounded-full"
            />
          ) : (
            <span className="font-mono text-lg font-bold">Категории пока нет</span>
          )}
        </div>

        {current ? (
          <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3">
            <StatusStat
              value={current.percentile === null ? "—" : String(toPercent(current.percentile))}
              label="перцентиль в категории"
            />
            <StatusStat
              className="max-sm:order-last max-sm:col-span-2"
              value={formatDate(current.valid_until)}
              valueClassName="text-xl sm:text-2xl"
              label={current.needs_reconfirmation ? "срок истёк — подтвердите грейд тестом" : "результат действителен до"}
            />
            {confidence && (
              <StatusStat
                value={`${toPercent(confidence.at_least)}%`}
                badge={<Badge variant={LEVEL_BADGE[confidence.level] ?? "muted"}>{confidence.level_label}</Badge>}
                label={`уверенность, что уровень не ниже ${gradeLabel(confidence.grade)}`}
              />
            )}
          </dl>
        ) : (
          <p className="max-w-2xl text-sm text-muted-foreground lg:flex-1">
            Пройдите тест, чтобы получить категорию «специализация × грейд» и попасть в поиск работодателей.
          </p>
        )}
      </div>

      {(current?.needs_reconfirmation || inProgress) && (
        <div className="grid gap-3 px-5 pb-5">
          {current?.needs_reconfirmation && (
            <Badge variant="destructive">Срок результата истёк — подтвердите грейд тестом</Badge>
          )}
          {inProgress && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-primary-tint p-3 text-sm">
              <span>
                {inProgress.purpose === "express"
                  ? `Есть незаконченный экспресс-тест на ${gradeLabel(inProgress.grade_target)} — пока он идёт, другой тест не начать`
                  : `Есть незаконченный тест на ${gradeLabel(inProgress.grade_target)}`}
              </span>
              <div className="flex flex-wrap items-start gap-2">
                <Button asChild size="sm">
                  <Link to={`/candidate/test/${inProgress.id}`}>
                    Продолжить <ArrowRight />
                  </Link>
                </Button>
                {inProgress.purpose === "express" && <AbandonExpressButton attemptId={inProgress.id} />}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="grid border-t border-border-subtle lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="min-w-0 space-y-6 p-5">
          <GradeLadder specialization={specialization} current={current?.category.grade ?? null} />
          {confidence && <ConfidenceDistribution confidence={confidence} />}
        </div>
        <div className="min-w-0 space-y-3 border-t border-border-subtle p-5 lg:border-t-0 lg:border-l">
          <h2 className={eyebrow}>Сменить грейд</h2>
          <GradeActions status={status} specialization={specialization} blocked={Boolean(inProgress)} />
        </div>
      </div>
    </section>
  );
}

function StatusStat({
  value,
  label,
  badge,
  className,
  valueClassName,
}: {
  value: string;
  label: string;
  badge?: ReactNode;
  className?: string;
  valueClassName?: string;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col-reverse gap-1 sm:border-l sm:border-border-subtle sm:pl-4", className)}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="flex flex-wrap items-center gap-2">
        <span className={cn("font-mono text-3xl font-extrabold tabular-nums", valueClassName)}>{value}</span>
        {badge}
      </dd>
    </div>
  );
}

/** Лестница Стажёр → Junior → Middle → Senior: текущий грейд залит, следующий — пунктиром. */
function GradeLadder({ specialization, current }: { specialization: string | null; current: Grade | null }) {
  const grades = useGrades();
  const ladder = grades.data
    ? [...grades.data].sort((a, b) => a.order - b.order).map((item) => item.slug)
    : FALLBACK_GRADES;
  const currentIndex = current ? ladder.indexOf(current) : -1;

  return (
    <div className="space-y-3">
      <span id="grade-ladder" className={eyebrow}>
        Лестница грейдов{specialization ? ` · ${specializationLabel(specialization)}` : ""}
      </span>
      <ol aria-labelledby="grade-ladder" className="grid grid-cols-4 gap-1.5 sm:gap-2">
        {ladder.map((grade, index) => {
          const isCurrent = index === currentIndex;
          const isNext = currentIndex >= 0 && index === currentIndex + 1;
          return (
            <li key={grade} aria-current={isCurrent ? "step" : undefined} className="flex min-w-0 flex-col gap-1">
              <span
                className={cn(
                  "flex h-9 items-center justify-center truncate rounded-lg border px-1 font-mono text-xs font-medium sm:h-10 sm:text-sm",
                  isCurrent && "border-transparent bg-primary font-bold text-primary-foreground",
                  isNext && "border-dashed border-primary text-primary",
                  !isCurrent && !isNext && "text-muted-foreground",
                )}
              >
                {gradeLabel(grade)}
              </span>
              {isCurrent && <span className="text-center font-mono text-xs font-medium text-primary">текущий</span>}
              {isNext && <span className="text-center text-xs text-muted-foreground">следующий</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** Распределение уверенности (§10.4.1): вероятности полос грейдов. На грейд не влияет. */
function ConfidenceDistribution({ confidence }: { confidence: GradeConfidence }) {
  const gradeIndex = confidence.bands.findIndex((band) => band.grade === confidence.grade);
  const visible = confidence.bands
    .map((band, index) => ({ band, index }))
    .filter(({ band }) => toPercent(band.probability) >= 1);
  const summary = visible.map(({ band }) => `${band.label} ${toPercent(band.probability)}%`).join(", ");
  const tone = (index: number) =>
    index === gradeIndex ? "bg-primary" : index > gradeIndex ? "bg-primary-pale" : "bg-border";

  return (
    <div className="space-y-2.5">
      <span className={eyebrow}>Распределение уверенности</span>
      <div
        role="img"
        aria-label={`Вероятности грейдов: ${summary}`}
        className="flex h-2 w-full gap-0.5 overflow-hidden rounded-full bg-muted"
      >
        {visible.map(({ band, index }) => (
          <div key={band.label} className={cn("h-full", tone(index))} style={{ width: `${band.probability * 100}%` }} />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-muted-foreground tabular-nums" aria-hidden>
        {visible.map(({ band, index }) => (
          <li key={band.label} className={cn("flex items-center gap-1.5", index === gradeIndex && "text-foreground")}>
            <span className={cn("size-2 rounded-full", tone(index))} />
            {band.label} {toPercent(band.probability)}%
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">{confidence.note}</p>
    </div>
  );
}

/** Одна главная кнопка (повышение, первый тест, повтор), понижения — тихими кнопками под ней. */
function GradeActions({
  status,
  specialization,
  blocked,
}: {
  status: GradeStatus;
  specialization: string | null;
  blocked: boolean;
}) {
  const grades = useGrades();

  if (!specialization) {
    return (
      <div className="space-y-2 text-sm text-muted-foreground">
        <p>Сначала пройдите опрос и подтвердите специализацию.</p>
        <Button asChild variant="outline" size="sm">
          <Link to="/candidate/onboarding">К онбордингу</Link>
        </Button>
      </div>
    );
  }

  const main = status.actions.filter((action) => action.action !== "downgrade");
  // Понижения — от ближнего грейда к дальнему
  const quiet = status.actions
    .filter((action) => action.action === "downgrade")
    .sort((a, b) => gradeOrder(b.grade, grades.data) - gradeOrder(a.grade, grades.data));
  const primary = main.find((action) => action.allowed);

  return (
    <div className="space-y-3">
      {status.actions.length === 0 ? (
        <p className="text-sm text-muted-foreground">Сейчас доступных действий нет.</p>
      ) : (
        <>
          {main.length > 0 && (
            <ul className="space-y-3">
              {main.map((action) => (
                <ActionItem
                  key={`${action.action}-${action.grade}`}
                  action={action}
                  status={status}
                  specialization={specialization}
                  grades={grades.data}
                  blocked={blocked}
                  variant={action === primary ? "default" : "outline"}
                  size={action === primary ? "lg" : "default"}
                />
              ))}
            </ul>
          )}
          {quiet.length > 0 && (
            <ul className="space-y-1">
              {quiet.map((action) => (
                <ActionItem
                  key={`${action.action}-${action.grade}`}
                  action={action}
                  status={status}
                  specialization={specialization}
                  grades={grades.data}
                  blocked={blocked}
                  variant="ghost"
                  quiet
                />
              ))}
            </ul>
          )}
        </>
      )}
      <p className="text-xs text-muted-foreground">
        Повысить или понизить грейд можно не чаще раза в {status.cooldown_days}{" "}
        {plural(status.cooldown_days, ["день", "дня", "дней"])}. Повтор теста на тот же грейд после неудачи — тоже после
        паузы: дата видна рядом с кнопкой.
        {status.retest_can_downgrade && (
          <>
            {" "}
            Свой грейд можно перепроверить с той же паузой: при неудаче категория понижается до уровня, который показал
            тест.
          </>
        )}
      </p>
    </div>
  );
}

function ActionItem({
  action,
  status,
  specialization,
  grades,
  blocked,
  variant,
  size,
  quiet = false,
}: {
  action: GradeAction;
  status: GradeStatus;
  specialization: string;
  grades: ReturnType<typeof useGrades>["data"];
  blocked: boolean;
  variant: ComponentProps<typeof Button>["variant"];
  size?: ComponentProps<typeof Button>["size"];
  quiet?: boolean;
}) {
  const view = actionView[action.action] ?? { label: "Тест на грейд", icon: Target };
  const Icon = view.icon;
  const width = quiet ? "[&>button]:w-full [&>button]:justify-start" : "[&>button]:w-full";

  return (
    <li className="space-y-1.5">
      {action.allowed ? (
        <StartAttemptButton
          variant={variant}
          size={size}
          disabled={blocked}
          className={width}
          params={{ specialization, grade_target: action.grade, purpose: purposeFor(action.grade, status, grades) }}
        >
          <Icon /> {view.label} {gradeLabel(action.grade)}
        </StartAttemptButton>
      ) : (
        <div className="grid gap-1.5">
          <Button variant={quiet ? "ghost" : "outline"} disabled className={quiet ? "w-full justify-start" : "w-full"}>
            <Icon /> {view.label} {gradeLabel(action.grade)}
          </Button>
          {action.available_at && (
            <span className={cn("inline-flex items-center gap-1.5 text-sm text-muted-foreground", quiet && "px-3")}>
              <CalendarClock className="size-4 shrink-0 text-primary" aria-hidden />
              доступно с <b className="font-mono text-foreground">{formatDate(action.available_at)}</b>
            </span>
          )}
        </div>
      )}
      {action.reason && <p className={cn("text-xs text-muted-foreground", quiet && "px-3")}>{action.reason}</p>}
    </li>
  );
}

// ---------- история и попытки ----------

interface HistoryRow {
  key: string;
  date: string;
  attempt: AttemptSummary | null;
  record: CategoryRecord | null;
}

// Категорию выдаёт завершение попытки: запись истории и попытку сводим по времени (в пределах нескольких минут)
const MATCH_WINDOW_MS = 10 * 60 * 1000;

function historyRows(status: GradeStatus): HistoryRow[] {
  const records = [...status.history];
  const rows: HistoryRow[] = status.attempts.map((attempt) => {
    let record: CategoryRecord | null = null;
    if (attempt.status === "completed" && attempt.finished_at) {
      const finished = new Date(attempt.finished_at).getTime();
      const index = records.findIndex(
        (item) =>
          item.category.specialization === attempt.specialization &&
          Math.abs(new Date(item.assigned_at).getTime() - finished) <= MATCH_WINDOW_MS,
      );
      if (index >= 0) record = records.splice(index, 1)[0] ?? null;
    }
    return { key: `attempt-${attempt.id}`, date: attempt.finished_at ?? attempt.started_at, attempt, record };
  });
  for (const record of records) {
    rows.push({ key: `record-${record.category.label}-${record.assigned_at}`, date: record.assigned_at, attempt: null, record });
  }
  return rows.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
}

function HistoryCard({ status }: { status: GradeStatus }) {
  const rows = historyRows(status);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="size-4 text-primary" aria-hidden /> История и попытки
        </CardTitle>
        <CardDescription>Все тесты на грейд, их итоги и выданные категории</CardDescription>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <EmptyState
            icon={ClipboardList}
            title="Тестов ещё не было"
            description="Начните с онбординга: опрос, специализация, грейд и тест. Здесь появятся попытки и выданные категории."
            action={
              <Button asChild>
                <Link to="/candidate/onboarding">К онбордингу</Link>
              </Button>
            }
            className="py-8"
          />
        ) : (
          <>
            <table className="hidden w-full text-sm md:table">
              <thead>
                <tr className="border-b border-border-subtle text-left">
                  {["Дата", "Тест", "Категория", "Итог", "Разбор"].map((title) => (
                    <th key={title} scope="col" className={cn(eyebrow, "pr-4 pb-2 font-medium last:pr-0")}>
                      {title}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {rows.map((row) => (
                  <tr key={row.key} className="align-top">
                    <td className="py-3 pr-4 font-mono text-[13px] whitespace-nowrap">{formatDate(row.date)}</td>
                    <td className="py-3 pr-4">
                      <PurposeBadge attempt={row.attempt} />
                    </td>
                    <td className="py-3 pr-4">
                      <CategoryCell row={row} />
                    </td>
                    <td className="py-3 pr-4">
                      <OutcomeBadge row={row} />
                    </td>
                    <td className="py-3">
                      <RowAction attempt={row.attempt} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <ol className="divide-y divide-border-subtle md:hidden">
              {rows.map((row) => (
                <li key={row.key} className="space-y-2 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-xs text-muted-foreground">{formatDate(row.date)}</span>
                    <OutcomeBadge row={row} />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <PurposeBadge attempt={row.attempt} />
                    <CategoryCell row={row} />
                  </div>
                  <RowAction attempt={row.attempt} />
                </li>
              ))}
            </ol>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function PurposeBadge({ attempt }: { attempt: AttemptSummary | null }) {
  if (!attempt) return <span className="text-muted-foreground">—</span>;
  return (
    <Badge variant="muted" className="text-foreground">
      {ATTEMPT_PURPOSE_LABELS[attempt.purpose] ?? attempt.purpose}
    </Badge>
  );
}

function CategoryCell({ row }: { row: HistoryRow }) {
  const { record, attempt } = row;
  if (record) {
    return (
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <CategoryBadge
            specialization={record.category.specialization}
            grade={record.category.grade}
            variant={record.is_current ? "solid" : "soft"}
            className="rounded-full"
          />
          {record.is_current && <Badge variant="outline">текущая</Badge>}
          {record.needs_reconfirmation && <Badge variant="destructive">требует подтверждения</Badge>}
        </div>
        <div className="text-xs text-muted-foreground">
          {record.percentile !== null && `перцентиль ${toPercent(record.percentile)} · `}
          действует до {formatDate(record.valid_until)}
        </div>
      </div>
    );
  }
  if (!attempt) return null;
  return (
    <span className="font-mono text-[13px] font-medium whitespace-nowrap text-accent-foreground">
      {specializationLabel(attempt.specialization)} · {gradeLabel(attempt.grade_target)}
    </span>
  );
}

function OutcomeBadge({ row }: { row: HistoryRow }) {
  const { attempt } = row;
  if (!attempt) return <Badge variant="soft">категория выдана</Badge>;
  if (attempt.result) {
    return (
      <Badge variant={attempt.result === "fail" ? "destructive" : "soft"}>
        {attempt.result === "confident_pass" && <Award aria-hidden />}
        {ATTEMPT_RESULT_LABELS[attempt.result] ?? attempt.result}
      </Badge>
    );
  }
  return <Badge variant="muted">{ATTEMPT_STATUS_LABELS[attempt.status] ?? attempt.status}</Badge>;
}

function RowAction({ attempt }: { attempt: AttemptSummary | null }) {
  if (attempt?.status === "in_progress") {
    return (
      <Button asChild size="sm">
        <Link to={`/candidate/test/${attempt.id}`}>Продолжить</Link>
      </Button>
    );
  }
  if (attempt?.status === "completed") {
    return (
      <Link
        to={`/candidate/test/${attempt.id}/result`}
        className="inline-flex min-h-8 items-center gap-1 text-sm font-medium text-primary hover:underline max-md:min-h-11"
      >
        Разбор <ChevronRight className="size-4" aria-hidden />
      </Link>
    );
  }
  return <span className="font-mono text-[13px] text-muted-foreground max-md:hidden">—</span>;
}

// ---------- загрузка ----------

function GradeSkeleton() {
  return (
    <div className="grid gap-4" role="status" aria-busy="true" aria-label="Загрузка">
      <div className="space-y-5 rounded-xl border bg-card p-5">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:gap-8">
          <div className="space-y-2 lg:w-64">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-10 w-48 rounded-full" />
          </div>
          <div className="grid flex-1 grid-cols-2 gap-4 sm:grid-cols-3">
            {[0, 1, 2].map((index) => (
              <div key={index} className="space-y-2">
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-3 w-32" />
              </div>
            ))}
          </div>
        </div>
        <div className="grid gap-6 border-t border-border-subtle pt-5 lg:grid-cols-[3fr_2fr]">
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-2">
              {[0, 1, 2, 3].map((index) => (
                <Skeleton key={index} className="h-10 rounded-lg" />
              ))}
            </div>
            <Skeleton className="h-2 w-full rounded-full" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-12 w-full rounded-lg" />
            <Skeleton className="h-9 w-2/3" />
          </div>
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    </div>
  );
}

