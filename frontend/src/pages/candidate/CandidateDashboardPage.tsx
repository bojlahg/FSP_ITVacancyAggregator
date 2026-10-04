import { ArrowRight, CalendarClock, ListChecks, Mail, UserRound } from "lucide-react";
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
import { formatDaysAgo } from "@/lib/format";
// MOCK: заменить на GET /candidates/me, /candidates/me/grade-status, /candidates/me/invitations
import { mockCandidateInvitations, mockMe } from "@/mocks/candidate";

export default function CandidateDashboardPage() {
  const newInvitations = mockCandidateInvitations.filter((invitation) => invitation.status === "sent").length;

  return (
    <>
      <PageHeader
        eyebrow="Кабинет кандидата"
        title={`Здравствуйте, ${mockMe.displayName.split(" ")[0]}`}
        description="Здесь собрано главное: ваша категория, новые приглашения от работодателей, задания и полнота профиля."
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="relative overflow-hidden lg:col-span-2">
          <Trace width={180} height={140} radius={32} className="absolute top-0 right-0 hidden opacity-70 sm:block" />
          <CardHeader>
            <CardDescription className="font-mono text-xs tracking-wider uppercase">Ваша категория</CardDescription>
            <CategoryBadge specialization={mockMe.specialization} grade={mockMe.grade} variant="solid" size="lg" />
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            <div>
              <div className="font-mono text-3xl font-extrabold tabular-nums">{mockMe.percentile}</div>
              <div className="text-xs text-muted-foreground">перцентиль в категории</div>
            </div>
            <div>
              <div className="font-mono text-3xl font-extrabold tabular-nums">{mockMe.validMonthsLeft} мес</div>
              <div className="text-xs text-muted-foreground">до подтверждения результата</div>
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

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserRound className="size-4 text-primary" aria-hidden /> Полнота профиля
            </CardTitle>
            <CardDescription>Заполненный профиль выше в выдаче у работодателей.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-2xl font-extrabold">{mockMe.profileCompleteness}%</span>
              <span className="text-xs text-muted-foreground">не хватает: опыт, отрасли</span>
            </div>
            <Progress value={mockMe.profileCompleteness} />
            <Button asChild variant="link" className="h-auto p-0">
              <Link to="/candidate/profile">Дополнить профиль</Link>
            </Button>
          </CardContent>
        </Card>

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
