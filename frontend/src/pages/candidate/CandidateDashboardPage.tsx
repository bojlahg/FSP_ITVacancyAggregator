import { ArrowRight, CalendarClock, ListChecks, Mail, Target, UserRound } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { StatusBadge } from "@/components/StatusBadge";
import { Trace } from "@/components/Trace";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ErrorState } from "@/components/ErrorState";
import { SkeletonCards } from "@/components/SkeletonCards";
import { apiError } from "@/lib/api-error";
import { formatDate, formatDaysAgo, toPercent } from "@/lib/format";
import { type CandidateProfile, useCandidateMe, useGradeStatus } from "@/lib/testing-queries";
// MOCK: заменить на GET /candidates/me/invitations
import { mockCandidateInvitations } from "@/mocks/candidate";

export default function CandidateDashboardPage() {
  const newInvitations = mockCandidateInvitations.filter((invitation) => invitation.status === "sent").length;
  const me = useCandidateMe();
  const firstName = me.data?.first_name;

  return (
    <>
      <PageHeader
        eyebrow="Кабинет кандидата"
        title={firstName ? `Здравствуйте, ${firstName}` : "Здравствуйте"}
        description="Здесь собрано главное: ваша категория, новые приглашения от работодателей, задания и полнота профиля."
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {me.isPending && <SkeletonCards count={1} className="lg:col-span-3" />}
        {me.isError && (
          <ErrorState
            className="lg:col-span-3"
            title="Не удалось загрузить профиль"
            description={apiError(me.error).message}
            onRetry={() => void me.refetch()}
          />
        )}
        {me.isSuccess && (
          <>
            {me.data.onboarding_step === "done" && me.data.category ? (
              <CategoryCard category={me.data.category} />
            ) : (
              <OnboardingCta step={me.data.onboarding_step} />
            )}

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <UserRound className="size-4 text-primary" aria-hidden /> Полнота профиля
                </CardTitle>
                <CardDescription>Заполненный профиль выше в выдаче у работодателей.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="font-mono text-2xl font-extrabold tabular-nums">
                  {toPercent(me.data.profile_completeness)}%
                </div>
                <Progress value={toPercent(me.data.profile_completeness)} aria-label="Полнота профиля" />
                <Button asChild variant="link" className="h-auto p-0">
                  <Link to="/candidate/profile">Дополнить профиль</Link>
                </Button>
              </CardContent>
            </Card>
          </>
        )}

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="size-4 text-primary" aria-hidden /> Приглашения
            </CardTitle>
            <CardDescription>
              {newInvitations > 0 ? `Новых: ${newInvitations}. Вилка видна сразу, до начала общения.` : "Новых нет."}
            </CardDescription>
            <CardAction>
              <Button asChild variant="ghost" size="sm">
                <Link to="/candidate/invitations">
                  Все <ArrowRight />
                </Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            {mockCandidateInvitations.length === 0 ? (
              <EmptyState
                icon={Mail}
                title="Пока нет приглашений"
                description="Работодатели увидят вас в поиске после получения категории."
              />
            ) : (
              <ul className="divide-y divide-border-subtle">
                {mockCandidateInvitations.map((invitation) => (
                  <li key={invitation.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <div className="truncate font-medium">{invitation.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {invitation.company} · {formatDaysAgo(invitation.sentDaysAgo)}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <SalaryRange from={invitation.salaryFrom} to={invitation.salaryTo} className="text-sm" />
                      <StatusBadge status={invitation.status} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListChecks className="size-4 text-primary" aria-hidden /> Задания
            </CardTitle>
            <CardDescription>Регулярные задания поддерживают свежесть профиля.</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={CalendarClock}
              title="Заданий пока нет"
              description="Новое задание появится в начале недели."
              className="py-8"
            />
          </CardContent>
        </Card>
      </div>
    </>
  );
}

const ctaCopy: Record<string, { title: string; description: string; action: string }> = {
  test: {
    title: "Завершите начатый тест",
    description: "Тест уже идёт — продолжите с того вопроса, на котором остановились.",
    action: "Продолжить тест",
  },
};

const defaultCta = {
  title: "Пройдите тест, чтобы попасть в категорию",
  description:
    "Работодатели ищут кандидатов по категориям «специализация × грейд». Короткий опрос, выбор грейда и тест — около 30 минут.",
  action: "Начать онбординг",
};

function OnboardingCta({ step }: { step: string }) {
  const copy = ctaCopy[step] ?? defaultCta;
  return (
    <Card className="relative overflow-hidden border-primary bg-primary-tint lg:col-span-2">
      <Trace width={180} height={140} radius={32} className="absolute top-0 right-0 hidden opacity-70 sm:block" />
      <CardHeader>
        <CardDescription className="flex items-center gap-2 font-mono text-xs tracking-wider uppercase">
          <Target className="size-4 text-primary" aria-hidden /> Категории пока нет
        </CardDescription>
        <CardTitle className="max-w-md text-xl">{copy.title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="max-w-lg text-sm text-muted-foreground">{copy.description}</p>
        <Button asChild size="lg">
          <Link to="/candidate/onboarding">
            {copy.action} <ArrowRight />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function CategoryCard({ category }: { category: NonNullable<CandidateProfile["category"]> }) {
  const status = useGradeStatus();
  const current = status.data?.current;

  return (
    <Card className="relative overflow-hidden lg:col-span-2">
      <Trace width={180} height={140} radius={32} className="absolute top-0 right-0 hidden opacity-70 sm:block" />
      <CardHeader>
        <CardDescription className="font-mono text-xs tracking-wider uppercase">Ваша категория</CardDescription>
        <CategoryBadge specialization={category.specialization} grade={category.grade} variant="solid" size="lg" />
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
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
        <div className="flex items-end">
          <Button asChild variant="outline" size="sm">
            <Link to="/candidate/grade">
              Категория и грейд <ArrowRight />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
