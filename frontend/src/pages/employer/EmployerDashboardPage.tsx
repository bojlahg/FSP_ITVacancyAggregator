import { ArrowRight, CheckCircle2, Mail, Plus, Target, TrendingDown } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDaysAgo } from "@/lib/format";
// MOCK: заменить на GET /needs, /employers/me/invitations, /employers/me/decline-stats
import { mockDeclineStats, mockEmployerInvitations, mockNeeds } from "@/mocks/talent";

export default function EmployerDashboardPage() {
  const accepted = mockEmployerInvitations.filter((invitation) => invitation.status === "accepted").length;
  const declinedTotal = mockDeclineStats.reduce((sum, item) => sum + item.count, 0);
  const topReason = mockDeclineStats[0];

  return (
    <>
      <PageHeader
        eyebrow="Кабинет работодателя · Демо Банк"
        title="Обзор подбора"
        description="Потребности, отправленные приглашения и причины отказов — в одном месте."
        actions={
          <Button asChild>
            <Link to="/employer/needs/new">
              <Plus /> Новая потребность
            </Link>
          </Button>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Потребности" value={mockNeeds.length} hint="активных запросов на подбор" icon={Target} />
        <StatCard label="Приглашения" value={mockEmployerInvitations.length} hint="отправлено за 30 дней" icon={Mail} />
        <StatCard label="Принято" value={accepted} hint="контакты кандидатов открыты" icon={CheckCircle2} />
        <StatCard
          label="Отказы"
          value={declinedTotal}
          hint={topReason ? `${topReason.count} из ${declinedTotal} — ${topReason.reason.toLowerCase()}` : undefined}
          icon={TrendingDown}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Потребности</CardTitle>
            <CardDescription>Откройте подборку, чтобы увидеть кандидатов с объяснением</CardDescription>
            <CardAction>
              <Button asChild variant="ghost" size="sm">
                <Link to="/employer/needs">
                  Все <ArrowRight />
                </Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-border-subtle">
              {mockNeeds.map((need) => (
                <li key={need.id}>
                  <Link
                    to={`/employer/needs/${need.id}`}
                    className="flex flex-wrap items-center justify-between gap-3 py-3 hover:text-primary"
                  >
                    <div className="min-w-0 space-y-1">
                      <div className="font-medium">{need.title}</div>
                      <CategoryBadge specialization={need.specialization} grade={need.grade} />
                    </div>
                    <div className="text-right">
                      <SalaryRange from={need.salaryFrom} to={need.salaryTo} className="text-sm" />
                      <div className="text-xs text-muted-foreground">{need.candidatesCount} кандидатов</div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Последние приглашения</CardTitle>
            <CardDescription>Статусы обновляются, когда кандидат отвечает</CardDescription>
            <CardAction>
              <Button asChild variant="ghost" size="sm">
                <Link to="/employer/invitations">
                  Все <ArrowRight />
                </Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-border-subtle">
              {mockEmployerInvitations.slice(0, 4).map((invitation) => (
                <li key={invitation.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <div className="truncate font-mono text-sm font-bold">{invitation.candidateName}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {invitation.needTitle} · {formatDaysAgo(invitation.sentDaysAgo)}
                    </div>
                  </div>
                  <StatusBadge status={invitation.status} />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
