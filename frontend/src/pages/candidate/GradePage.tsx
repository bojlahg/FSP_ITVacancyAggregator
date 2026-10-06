import { ArrowDown, ArrowRight, ArrowUp, Award, CalendarClock, ClipboardList, History, RotateCw, Target } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { GradeExplanationCard } from "@/components/candidate/GradeExplanationCard";
import { ExpressTestCard } from "@/components/candidate/ExpressTestCard";
import { StartAttemptButton } from "@/components/candidate/StartAttemptButton";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { GradeEvidenceCard } from "@/components/GradeConfidence";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { apiError } from "@/lib/api-error";
import { formatDate, plural, toPercent } from "@/lib/format";
import { ATTEMPT_PURPOSE_LABELS, ATTEMPT_RESULT_LABELS, ATTEMPT_STATUS_LABELS, gradeLabel } from "@/lib/labels";
import {
  type GradeStatus,
  purposeFor,
  useCandidateMe,
  useGrades,
  useGradeStatus,
} from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

const actionView: Record<string, { label: string; icon: LucideIcon }> = {
  calibrate: { label: "Тест на", icon: Target },
  upgrade: { label: "Повысить до", icon: ArrowUp },
  downgrade: { label: "Понизить до", icon: ArrowDown },
  retry: { label: "Повторить тест на", icon: RotateCw },
  // Срок категории истёк (§6.3): тот же грейд — подтверждение
  reconfirm: { label: "Подтвердить", icon: RotateCw },
  // Настройка платформы GRADE_RETEST_CAN_DOWNGRADE: перепроверка своего грейда, провал понижает
  retest: { label: "Перепроверить", icon: RotateCw },
};

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
      {status.isPending && <SkeletonCards count={2} className="lg:grid-cols-2" />}
      {status.isError && (
        <ErrorState description={apiError(status.error).message} onRetry={() => void status.refetch()} />
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
  const grades = useGrades();
  const { current } = status;
  const inProgress = status.attempts.find((attempt) => attempt.status === "in_progress");

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardDescription className="font-mono text-xs tracking-wider uppercase">Текущий статус</CardDescription>
          {current ? (
            <CategoryBadge
              specialization={current.category.specialization}
              grade={current.category.grade}
              variant="solid"
              size="lg"
            />
          ) : (
            <span className="font-mono text-lg font-bold">Категории пока нет</span>
          )}
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {current ? (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="font-mono text-2xl font-extrabold tabular-nums">
                  {current.percentile === null ? "—" : toPercent(current.percentile)}
                </div>
                <div className="text-xs text-muted-foreground">перцентиль в категории</div>
              </div>
              <div>
                <div className="font-mono text-base font-extrabold">{formatDate(current.valid_until)}</div>
                <div className="text-xs text-muted-foreground">результат действителен до</div>
              </div>
              {current.needs_reconfirmation && (
                <Badge variant="destructive" className="col-span-2">
                  Срок результата истёк — подтвердите грейд тестом
                </Badge>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground">
              Пройдите тест, чтобы получить категорию «специализация × грейд» и попасть в поиск работодателей.
            </p>
          )}

          {inProgress && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-primary-tint p-3">
              <span>Есть незаконченный тест на {gradeLabel(inProgress.grade_target)}</span>
              <Button asChild size="sm">
                <Link to={`/candidate/test/${inProgress.id}`}>
                  Продолжить <ArrowRight />
                </Link>
              </Button>
            </div>
          )}

          <Separator />
          <div className="space-y-3">
            <h2 className="font-mono text-sm font-bold">Сменить грейд</h2>
            {!specialization ? (
              <div className="space-y-2 text-muted-foreground">
                <p>Сначала пройдите опрос и подтвердите специализацию.</p>
                <Button asChild variant="outline" size="sm">
                  <Link to="/candidate/onboarding">К онбордингу</Link>
                </Button>
              </div>
            ) : status.actions.length === 0 ? (
              <p className="text-muted-foreground">Сейчас доступных действий нет.</p>
            ) : (
              <ul className="space-y-3">
                {status.actions.map((action) => {
                  const view = actionView[action.action] ?? { label: "Тест на", icon: Target };
                  const Icon = view.icon;
                  return (
                    <li key={`${action.action}-${action.grade}`} className="space-y-1.5">
                      {action.allowed ? (
                        <StartAttemptButton
                          variant={action.action === "downgrade" ? "outline" : "default"}
                          disabled={Boolean(inProgress)}
                          className="justify-items-start"
                          params={{
                            specialization,
                            grade_target: action.grade,
                            purpose: purposeFor(action.grade, status, grades.data),
                          }}
                        >
                          <Icon /> {view.label} {gradeLabel(action.grade)}
                        </StartAttemptButton>
                      ) : (
                        <div className="flex flex-wrap items-center gap-3">
                          <Button variant="outline" disabled>
                            <Icon /> {view.label} {gradeLabel(action.grade)}
                          </Button>
                          {action.available_at && (
                            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                              <CalendarClock className="size-4 text-primary" aria-hidden />
                              доступно с <b className="font-mono text-foreground">{formatDate(action.available_at)}</b>
                            </span>
                          )}
                        </div>
                      )}
                      {action.reason && <p className="text-xs text-muted-foreground">{action.reason}</p>}
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="text-xs text-muted-foreground">
              Повысить или понизить грейд можно не чаще раза в {status.cooldown_days}{" "}
              {plural(status.cooldown_days, ["день", "дня", "дней"])}. Повтор теста на тот же грейд после неудачи — тоже
              после паузы: дата видна рядом с кнопкой.
              {status.retest_can_downgrade && (
                <>
                  {" "}
                  Свой грейд можно перепроверить с той же паузой: при неудаче категория понижается до уровня, который
                  показал тест.
                </>
              )}
            </p>
          </div>
        </CardContent>
      </Card>

      {current?.evidence && <GradeEvidenceCard evidence={current.evidence} audience="candidate" />}

      {status.express && specialization && (
        <ExpressTestCard
          express={status.express}
          specialization={specialization}
          defaultGrade={current?.category.grade ?? "junior"}
          disabled={Boolean(inProgress)}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="size-4 text-primary" aria-hidden /> История категорий
          </CardTitle>
          <CardDescription>Выданные категории и сроки их действия</CardDescription>
        </CardHeader>
        <CardContent>
          {status.history.length === 0 ? (
            <EmptyState icon={Award} title="Категорий ещё не было" description="Они появятся после первого пройденного теста." className="py-8" />
          ) : (
            <ol className="relative space-y-5 border-l-[1.5px] border-primary pl-5">
              {status.history.map((record) => (
                <li key={`${record.category.label}-${record.assigned_at}`} className="relative">
                  <span
                    className={cn(
                      "absolute top-1.5 -left-[25px] size-2 rounded-full",
                      record.is_current ? "bg-primary" : "bg-border",
                    )}
                    aria-hidden
                  />
                  <div className="font-mono text-xs text-muted-foreground">{formatDate(record.assigned_at)}</div>
                  <div className="flex flex-wrap items-center gap-2 font-medium">
                    <CategoryBadge specialization={record.category.specialization} grade={record.category.grade} />
                    {record.is_current && <Badge variant="soft">текущая</Badge>}
                    {record.needs_reconfirmation && <Badge variant="destructive">требует подтверждения</Badge>}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {record.percentile !== null && `перцентиль ${toPercent(record.percentile)} · `}
                    действует до {formatDate(record.valid_until)}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <GradeExplanationCard />

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ClipboardList className="size-4 text-primary" aria-hidden /> Попытки
          </CardTitle>
          <CardDescription>Все тесты на грейд и их итоги</CardDescription>
        </CardHeader>
        <CardContent>
          {status.attempts.length === 0 ? (
            <EmptyState
              icon={ClipboardList}
              title="Тестов ещё не было"
              description="Начните с онбординга: опрос, специализация, грейд и тест."
              action={
                <Button asChild>
                  <Link to="/candidate/onboarding">К онбордингу</Link>
                </Button>
              }
              className="py-8"
            />
          ) : (
            <ul className="divide-y divide-border-subtle">
              {status.attempts.map((attempt) => (
                <li key={attempt.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <CategoryBadge specialization={attempt.specialization} grade={attempt.grade_target} />
                      <Badge variant="muted">{ATTEMPT_PURPOSE_LABELS[attempt.purpose] ?? attempt.purpose}</Badge>
                    </div>
                    <div className="font-mono text-xs text-muted-foreground">{formatDate(attempt.started_at)}</div>
                  </div>
                  <div className="flex items-center gap-3">
                    {attempt.result ? (
                      <Badge variant={attempt.result === "fail" ? "destructive" : "soft"}>
                        {ATTEMPT_RESULT_LABELS[attempt.result] ?? attempt.result}
                      </Badge>
                    ) : (
                      <Badge variant="muted">{ATTEMPT_STATUS_LABELS[attempt.status] ?? attempt.status}</Badge>
                    )}
                    {attempt.status === "in_progress" && (
                      <Button asChild size="sm">
                        <Link to={`/candidate/test/${attempt.id}`}>Продолжить</Link>
                      </Button>
                    )}
                    {attempt.status === "completed" && (
                      <Button asChild size="sm" variant="ghost">
                        <Link to={`/candidate/test/${attempt.id}/result`}>
                          Разбор <ArrowRight />
                        </Link>
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
