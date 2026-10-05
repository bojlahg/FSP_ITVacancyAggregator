import { ArrowRight, CheckCircle2, Mail, Plus, Target, TrendingDown } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { SkeletonCards } from "@/components/SkeletonCards";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiError } from "@/lib/api-error";
import { useCompany, useDeclineStats, useEmployerInvitations, useNeeds } from "@/lib/employer-queries";
import { formatDaysAgo } from "@/lib/format";

export default function EmployerDashboardPage() {
  const company = useCompany();
  const needs = useNeeds();
  const invitations = useEmployerInvitations({});
  const stats = useDeclineStats(null);
  const needTitles = new Map((needs.data ?? []).map((need) => [need.id, need.title]));

  return (
    <>
      <PageHeader
        eyebrow={company.data?.company_name ? `Кабинет работодателя · ${company.data.company_name}` : "Кабинет работодателя"}
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
        <StatCard label="Потребности" value={needs.data?.length ?? "—"} hint="активных запросов на подбор" icon={Target} />
        <StatCard label="Приглашения" value={stats.data?.total_sent ?? "—"} hint="отправлено всего" icon={Mail} />
        <StatCard label="Принято" value={stats.data?.accepted ?? "—"} hint="контакты кандидатов открыты" icon={CheckCircle2} />
        <StatCard
          label="Отказы"
          value={stats.data?.declined ?? "—"}
          hint={stats.data?.hint ?? undefined}
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
            {needs.isPending ? (
              <SkeletonCards count={2} />
            ) : needs.isError ? (
              <ErrorState description={apiError(needs.error).message} onRetry={() => void needs.refetch()} />
            ) : needs.data.length === 0 ? (
              <EmptyState
                icon={Target}
                title="Потребностей пока нет"
                description="Опишите, кого ищете, — подборка появится сразу."
              />
            ) : (
              <ul className="divide-y divide-border-subtle">
                {needs.data.slice(0, 6).map((need) => (
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
                        <SalaryRange from={need.salary_from} to={need.salary_to} className="text-sm" />
                        <div className="text-xs text-muted-foreground">
                          приглашений {need.stats.invitations_active} из {need.stats.invitations_limit} · в шорт-листе{" "}
                          {need.stats.shortlisted}
                        </div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
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
            {invitations.isPending ? (
              <SkeletonCards count={2} />
            ) : invitations.isError ? (
              <ErrorState description={apiError(invitations.error).message} onRetry={() => void invitations.refetch()} />
            ) : invitations.data.length === 0 ? (
              <EmptyState
                icon={Mail}
                title="Приглашений пока нет"
                description="Пригласите кандидата из подборки по потребности."
              />
            ) : (
              <ul className="divide-y divide-border-subtle">
                {invitations.data.slice(0, 5).map((invitation) => (
                  <li key={invitation.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <div className="truncate font-mono text-sm font-bold">{invitation.candidate.display_name}</div>
                      <div className="truncate text-xs text-muted-foreground">
                        {(invitation.need_id !== null && needTitles.get(invitation.need_id)) || invitation.title} ·{" "}
                        {formatDaysAgo(daysSince(invitation.created_at))}
                      </div>
                    </div>
                    <StatusBadge status={invitation.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function daysSince(iso: string): number {
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000));
}
