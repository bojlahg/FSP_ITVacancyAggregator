import { ArrowRight, Award, CalendarClock, Flag, ListChecks, Mail, Target } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { MarketCard, MarketSuggestions } from "@/components/candidate/MarketCard";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { StatusBadge } from "@/components/StatusBadge";
import { Trace } from "@/components/Trace";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import { daysSince, formatDate, formatDaysAgo, plural, toPercent } from "@/lib/format";
import { useMyInvitations } from "@/lib/invitation-queries";
import { useMyTasks } from "@/lib/task-queries";
import { type CandidateProfile, useCandidateMe, useGradeStatus } from "@/lib/testing-queries";

const cardTitle = "flex items-center gap-2 font-mono text-base leading-tight font-bold";

export default function CandidateDashboardPage() {
  const me = useCandidateMe();
  const firstName = me.data?.first_name;

  return (
    <>
      <PageHeader
        eyebrow="Кабинет кандидата"
        title={firstName ? `Здравствуйте, ${firstName}` : "Здравствуйте"}
        description="Здесь собрано главное: ваша категория, новые приглашения от работодателей, задания и полнота профиля."
      />

      {me.isPending && <DashboardSkeleton />}
      {me.isError && (
        <ErrorState
          title="Не удалось загрузить профиль"
          description={apiError(me.error).message}
          onRetry={() => void me.refetch()}
        />
      )}
      {me.isSuccess && <Dashboard profile={me.data} />}
    </>
  );
}

function Dashboard({ profile }: { profile: CandidateProfile }) {
  const category = profile.onboarding_step === "done" ? profile.category : null;

  return (
    <div className="grid gap-4">
      <NextStepCard profile={profile} hasCategory={Boolean(category)} />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {category ? <CategoryCard category={category} /> : <NoCategoryCard />}
        <InvitationsCard hasCategory={Boolean(category)} />
        <TasksCard hasCategory={Boolean(category)} className="md:col-span-2 lg:col-span-1" />
      </div>

      {category && <MarketCard />}
    </div>
  );
}

// ---------- следующий шаг ----------

interface Step {
  title: string;
  description: string;
  action: string;
  to: string;
}

const onboardingSteps: Record<string, Step> = {
  test: {
    title: "Завершите начатый тест",
    description: "Тест уже идёт — продолжите с того вопроса, на котором остановились.",
    action: "Продолжить тест",
    to: "/candidate/onboarding",
  },
};

const onboardingStep: Step = {
  title: "Пройдите тест, чтобы попасть в категорию",
  description:
    "Работодатели ищут кандидатов по категориям «специализация × грейд». Короткий опрос, выбор грейда и тест — около 30 минут.",
  action: "Начать онбординг",
  to: "/candidate/onboarding",
};

/** Первым — одно действие, которое сейчас важнее всего; рядом полнота профиля и «что ещё поможет». */
function NextStepCard({ profile, hasCategory }: { profile: CandidateProfile; hasCategory: boolean }) {
  const status = useGradeStatus();
  const invitations = useMyInvitations();
  const fresh = (invitations.data ?? []).filter((invitation) => invitation.status === "sent").length;
  const completeness = toPercent(profile.profile_completeness);

  let step: Step;
  if (!hasCategory) {
    step = onboardingSteps[profile.onboarding_step] ?? onboardingStep;
  } else if (status.data?.current?.needs_reconfirmation) {
    step = {
      title: "Подтвердите грейд",
      description: "Срок результата теста истёк — пройдите тест на свой грейд, чтобы категория снова была действительной.",
      action: "Категория и грейд",
      to: "/candidate/grade",
    };
  } else if (fresh > 0) {
    step = {
      title: `Ответьте на ${fresh} ${plural(fresh, ["новое приглашение", "новых приглашения", "новых приглашений"])}`,
      description:
        "Вилка видна сразу, до начала общения. Контакты работодатель получит, только если вы примете приглашение.",
      action: "К приглашениям",
      to: "/candidate/invitations",
    };
  } else if (completeness < 100) {
    step = {
      title: "Дополните профиль",
      description: "Заполненный профиль выше в выдаче у работодателей.",
      action: "Дополнить профиль",
      to: "/candidate/profile",
    };
  } else {
    step = {
      title: "Профиль заполнен",
      description:
        "Работодатели видят вас в поиске по вашей категории. Новые приглашения появятся здесь — а грейд можно попробовать повысить.",
      action: "Категория и грейд",
      to: "/candidate/grade",
    };
  }
  const profileStep = step.to === "/candidate/profile";

  return (
    <section
      aria-labelledby="next-step-title"
      className="relative flex min-w-0 flex-col overflow-hidden rounded-xl border-2 border-primary bg-card lg:flex-row"
    >
      <div className="flex min-w-0 flex-col gap-5 p-5 lg:flex-[3] lg:p-6">
        <div className="space-y-2">
          <span className="flex items-center gap-2 font-mono text-xs font-medium tracking-wider text-primary uppercase">
            <Flag className="size-4" aria-hidden /> Следующий шаг
          </span>
          <h2 id="next-step-title" className="font-mono text-xl font-bold">
            {step.title}
          </h2>
          <p className="max-w-xl text-sm text-muted-foreground sm:text-base">{step.description}</p>
        </div>

        <div className="max-w-md space-y-2">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm font-medium">Полнота профиля</span>
            <span className="font-mono text-base font-bold tabular-nums">{completeness}%</span>
          </div>
          <Progress value={completeness} aria-label="Полнота профиля" className="h-1.5" />
          {!profileStep && completeness < 100 && (
            <Link to="/candidate/profile" className="inline-flex text-sm font-medium text-primary hover:underline">
              Дополнить профиль
            </Link>
          )}
        </div>

        <Button asChild size="lg" className="self-stretch sm:self-start">
          <Link to={step.to}>
            {step.action} <ArrowRight />
          </Link>
        </Button>
      </div>

      {hasCategory && (
        <aside
          aria-label="Что ещё поможет"
          className="flex min-w-0 flex-col gap-3 border-t border-border-subtle p-5 lg:flex-[2] lg:border-t-0 lg:border-l lg:p-6"
        >
          <span className="font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">
            Что ещё поможет
          </span>
          <MarketSuggestions fallback={<HelpFallback />} />
        </aside>
      )}
    </section>
  );
}

function HelpFallback() {
  return (
    <p className="text-sm text-muted-foreground">
      Регулярные задания подтверждают навыки и держат профиль «свежим» в выдаче, а тест на грейд выше открывает
      потребности следующей категории.
    </p>
  );
}

// ---------- три карточки ----------

function DashCard({
  title,
  icon: Icon,
  action,
  className,
  children,
}: {
  title: string;
  icon: typeof Mail;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Card className={className}>
      <CardHeader>
        <h2 className={cardTitle}>
          <Icon className="size-4 text-primary" aria-hidden /> {title}
        </h2>
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">{children}</CardContent>
    </Card>
  );
}

function AllLink({ to }: { to: string }) {
  return (
    <Button asChild variant="ghost" size="sm" className="-my-1 max-sm:h-11">
      <Link to={to}>
        Все <ArrowRight />
      </Link>
    </Button>
  );
}

function CategoryCard({ category }: { category: NonNullable<CandidateProfile["category"]> }) {
  const status = useGradeStatus();
  const current = status.data?.current;

  return (
    <Card className="relative overflow-hidden">
      {/* Трасса заканчивается в шапке карточки: ниже справа стоит бейдж категории */}
      <Trace width={140} height={40} radius={20} className="absolute top-0 right-0 hidden opacity-70 sm:block" />
      <CardHeader>
        <h2 className={cardTitle}>
          <Award className="size-4 text-primary" aria-hidden /> Ваша категория
        </h2>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <CategoryBadge
          specialization={category.specialization}
          grade={category.grade}
          variant="solid"
          size="lg"
          className="rounded-full"
        />
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="font-mono text-3xl font-extrabold tabular-nums">
              {current?.percentile != null ? toPercent(current.percentile) : "—"}
            </div>
            <div className="text-xs text-muted-foreground">перцентиль в категории</div>
          </div>
          <div>
            <div className="font-mono text-base font-extrabold">{current ? formatDate(current.valid_until) : "—"}</div>
            <div className="text-xs text-muted-foreground">
              {current?.needs_reconfirmation ? "срок истёк — подтвердите тестом" : "результат действителен до"}
            </div>
          </div>
        </div>
        <Link
          to="/candidate/grade"
          className="mt-auto inline-flex min-h-8 items-center gap-1 self-start text-sm font-medium text-primary hover:underline max-sm:min-h-11"
        >
          Категория и грейд <ArrowRight className="size-4" aria-hidden />
        </Link>
      </CardContent>
    </Card>
  );
}

function NoCategoryCard() {
  return (
    <DashCard title="Ваша категория" icon={Award}>
      <EmptyState
        icon={Target}
        title="Категории пока нет"
        description="Она появится после теста — с ней вы попадёте в поиск работодателей."
        className="flex-1 py-8"
      />
    </DashCard>
  );
}

function InvitationsCard({ hasCategory }: { hasCategory: boolean }) {
  const invitations = useMyInvitations();

  return (
    <DashCard title="Приглашения" icon={Mail} action={<AllLink to="/candidate/invitations" />}>
      {invitations.isPending ? (
        <ListSkeleton />
      ) : invitations.isError ? (
        <ErrorState
          variant="block"
          title="Не удалось загрузить приглашения."
          description={apiError(invitations.error).message}
          onRetry={() => void invitations.refetch()}
        />
      ) : invitations.data.length === 0 ? (
        <EmptyState
          icon={Mail}
          title="Пока нет приглашений"
          description={
            hasCategory
              ? "Как только работодатель выберет вас в подборке, приглашение появится здесь."
              : "Работодатели увидят вас в поиске после получения категории."
          }
          className="flex-1 py-8"
        />
      ) : (
        <ul className="divide-y divide-border-subtle">
          {invitations.data.slice(0, 3).map((invitation) => (
            <li key={invitation.id} className="space-y-1.5 py-3 first:pt-0">
              <div className="flex items-start justify-between gap-2">
                <span className="min-w-0 font-medium break-words">{invitation.title}</span>
                <StatusBadge status={invitation.status} audience="recipient" className="shrink-0" />
              </div>
              <div className="text-xs text-muted-foreground">
                {invitation.company.company_name} · {formatDaysAgo(daysSince(invitation.created_at))}
              </div>
              <SalaryRange from={invitation.salary_from} to={invitation.salary_to} className="text-sm" />
            </li>
          ))}
        </ul>
      )}
    </DashCard>
  );
}

function TasksCard({ hasCategory, className }: { hasCategory: boolean; className?: string }) {
  return (
    <DashCard
      title="Задания"
      icon={ListChecks}
      className={className}
      action={hasCategory ? <AllLink to="/candidate/tasks" /> : undefined}
    >
      {hasCategory ? (
        <TasksBody />
      ) : (
        <EmptyState
          icon={CalendarClock}
          title="Задания откроются с категорией"
          description="Короткие задания от работодателей вашей категории приходят раз в неделю и подтверждают навыки."
          className="flex-1 py-8"
        />
      )}
    </DashCard>
  );
}

function TasksBody() {
  const tasks = useMyTasks();
  if (tasks.isPending) return <ListSkeleton />;
  if (tasks.isError) {
    return (
      <ErrorState
        variant="block"
        title="Не удалось загрузить задания."
        description={apiError(tasks.error).message}
        onRetry={() => void tasks.refetch()}
      />
    );
  }
  const active = tasks.data.find((task) => task.status === "offered");
  if (!active) {
    return (
      <EmptyState
        icon={CalendarClock}
        title="Активных заданий нет"
        description="Новое задание предлагается не чаще раза в неделю — загляните позже."
        className="flex-1 py-8"
      />
    );
  }
  return (
    <div className="flex flex-1 flex-col gap-3">
      <div className="space-y-1">
        <div className="font-medium break-words">{active.title}</div>
        <div className="text-xs text-muted-foreground">
          {active.company_name} · ответить до {formatDate(active.due_at)}
        </div>
      </div>
      <p className="text-sm text-muted-foreground">Решённое задание подтверждает навыки и обновляет свежесть профиля.</p>
      <Button asChild size="sm" className="mt-auto self-start max-sm:h-11">
        <Link to="/candidate/tasks">
          Решить задание <ArrowRight />
        </Link>
      </Button>
    </div>
  );
}

// ---------- загрузка ----------

function ListSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Загрузка">
      {[0, 1].map((index) => (
        <div key={index} className="space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="grid gap-4" role="status" aria-busy="true" aria-label="Загрузка">
      <div className="space-y-4 rounded-xl border-2 border-border-subtle p-6">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-6 w-64 max-w-full" />
        <Skeleton className="h-2 w-full max-w-md rounded-full" />
        <Skeleton className="h-12 w-48 rounded-lg" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((index) => (
          <div key={index} className="space-y-4 rounded-xl border bg-card p-5">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-10 w-44 rounded-full" />
            <Skeleton className="h-3 w-3/4" />
          </div>
        ))}
      </div>
    </div>
  );
}
