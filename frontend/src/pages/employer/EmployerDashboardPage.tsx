import { ArrowRight, CheckCircle2, ListTodo, Mail, Plus, Target, TrendingDown, UserRoundSearch, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import {
  type InvitationForEmployer,
  type Need,
  useCompany,
  useDeclineStats,
  useEmployerInvitations,
  useNeeds,
} from "@/lib/employer-queries";
import { daysSince, formatDaysAgo, plural } from "@/lib/format";
import { cn } from "@/lib/utils";

const cardTitle = "font-mono text-base leading-tight font-bold";
const TODO_LIMIT = 3;

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

      <div className="grid gap-4">
        <TodoCard
          needs={needs}
          invitations={invitations}
          onRetry={() => {
            void needs.refetch();
            void invitations.refetch();
          }}
        />

        <section aria-label="Сводка" className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
          <StatCard label="Потребности" value={needs.data?.length ?? "—"} hint="активных запросов на подбор" icon={Target} />
          <StatCard label="Приглашения" value={stats.data?.total_sent ?? "—"} hint="отправлено всего" icon={Mail} />
          <StatCard label="Принято" value={stats.data?.accepted ?? "—"} hint="контакты кандидатов открыты" icon={CheckCircle2} />
          <StatCard
            label="Отказы"
            value={stats.data?.declined ?? "—"}
            hint={stats.data?.hint ?? undefined}
            icon={TrendingDown}
          />
        </section>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <h2 className={cn(cardTitle, "flex items-center gap-2")}>
                <Target className="size-4 text-primary" aria-hidden /> Потребности
              </h2>
              <CardDescription>Откройте подборку, чтобы увидеть кандидатов с объяснением</CardDescription>
              <CardAction>
                <AllLink to="/employer/needs" />
              </CardAction>
            </CardHeader>
            <CardContent>
              {needs.isPending ? (
                <RowsSkeleton />
              ) : needs.isError ? (
                <ErrorState
                  variant="block"
                  title="Не удалось загрузить потребности."
                  description={apiError(needs.error).message}
                  onRetry={() => void needs.refetch()}
                />
              ) : needs.data.length === 0 ? (
                <EmptyState
                  icon={Target}
                  title="Потребностей пока нет"
                  description="Опишите, кого ищете, — подборка кандидатов с объяснением появится сразу."
                />
              ) : (
                <ul className="divide-y divide-border-subtle">
                  {needs.data.slice(0, 6).map((need) => (
                    <NeedRow key={need.id} need={need} />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h2 className={cn(cardTitle, "flex items-center gap-2")}>
                <Mail className="size-4 text-primary" aria-hidden /> Последние приглашения
              </h2>
              <CardDescription>Статусы обновляются, когда кандидат отвечает</CardDescription>
              <CardAction>
                <AllLink to="/employer/invitations" />
              </CardAction>
            </CardHeader>
            <CardContent>
              {invitations.isPending ? (
                <RowsSkeleton />
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
                  title="Приглашений пока нет"
                  description="Пригласите кандидата из подборки по потребности — статус ответа появится здесь."
                />
              ) : (
                <ul className="divide-y divide-border-subtle">
                  {invitations.data.slice(0, 5).map((invitation) => (
                    <li key={invitation.id} className="flex items-center justify-between gap-3 py-3 first:pt-0">
                      <div className="min-w-0">
                        <div className="truncate font-mono text-sm font-bold">{invitation.candidate.display_name}</div>
                        <div className="truncate text-xs text-muted-foreground">
                          {(invitation.need_id !== null && needTitles.get(invitation.need_id)) || invitation.title} ·{" "}
                          {formatDaysAgo(daysSince(invitation.created_at))}
                        </div>
                      </div>
                      <StatusBadge status={invitation.status} className="shrink-0" />
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
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

function NeedRow({ need }: { need: Need }) {
  const { invitations_active: active, invitations_limit: limit, shortlisted } = need.stats;
  const fill = limit > 0 ? (active / limit) * 100 : 0;

  return (
    <li className="flex flex-col gap-3 py-3 first:pt-0 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="font-medium break-words">{need.title}</div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <CategoryBadge specialization={need.specialization} grade={need.grade} className="rounded-full" />
          <SalaryRange from={need.salary_from} to={need.salary_to} className="text-sm" />
        </div>
      </div>
      <div className="space-y-1.5 md:w-52 md:shrink-0">
        <div className="text-xs text-muted-foreground">
          <span className="whitespace-nowrap">
            приглашений{" "}
            <b className="font-mono font-bold text-foreground tabular-nums">
              {active} из {limit}
            </b>
          </span>{" "}
          ·{" "}
          <span className="whitespace-nowrap">
            в шорт-листе <b className="font-mono font-bold text-foreground tabular-nums">{shortlisted}</b>
          </span>
        </div>
        <Progress value={fill} aria-label={`Приглашений отправлено: ${active} из ${limit}`} className="h-1.5" />
      </div>
      <Button asChild variant="ghost" size="sm" className="self-start text-primary max-md:-ml-3 max-md:h-11 md:self-center">
        <Link to={`/employer/needs/${need.id}`}>
          Подборка<span className="sr-only">: {need.title}</span> <ArrowRight />
        </Link>
      </Button>
    </li>
  );
}

// ---------- что сделать сейчас ----------

interface Todo {
  key: string;
  icon: LucideIcon;
  text: ReactNode;
  action: string;
  to: string;
  urgent?: boolean;
}

/**
 * Действия из данных кабинета, сначала самое срочное: принятые приглашения (контакты открыты),
 * потребности с пустым шорт-листом, потом — с самым незаполненным лимитом приглашений.
 */
function buildTodos(needs: Need[], invitations: InvitationForEmployer[]): Todo[] {
  const todos: Todo[] = [];
  const accepted = invitations.filter((invitation) => invitation.status === "accepted").length;
  if (accepted > 0) {
    todos.push({
      key: "accepted",
      icon: CheckCircle2,
      text: `${accepted} ${plural(accepted, ["кандидат принял", "кандидата приняли", "кандидатов приняли"])} приглашения — контакты открыты`,
      action: "Открыть контакты",
      to: "/employer/invitations",
      urgent: true,
    });
  }
  const active = needs.filter((need) => need.status === "active");
  for (const need of active.filter((item) => item.stats.shortlisted === 0)) {
    todos.push({
      key: `shortlist-${need.id}`,
      icon: UserRoundSearch,
      text: (
        <>
          <span className="font-medium">{need.title}:</span> в шорт-листе пока никого
        </>
      ),
      action: "Открыть подборку",
      to: `/employer/needs/${need.id}`,
    });
  }
  const unfilled = active
    .filter((need) => need.stats.shortlisted > 0 && need.stats.invitations_active < need.stats.invitations_limit)
    .sort((a, b) => a.stats.invitations_active / a.stats.invitations_limit - b.stats.invitations_active / b.stats.invitations_limit);
  for (const need of unfilled) {
    todos.push({
      key: `invite-${need.id}`,
      icon: Users,
      text: (
        <>
          <span className="font-medium">{need.title}:</span> приглашений{" "}
          <b className="font-mono font-bold tabular-nums">
            {need.stats.invitations_active} из {need.stats.invitations_limit}
          </b>
        </>
      ),
      action: "Открыть подборку",
      to: `/employer/needs/${need.id}`,
    });
  }
  return todos.slice(0, TODO_LIMIT);
}

function TodoCard({
  needs,
  invitations,
  onRetry,
}: {
  needs: ReturnType<typeof useNeeds>;
  invitations: ReturnType<typeof useEmployerInvitations>;
  onRetry: () => void;
}) {
  const todos = needs.data && invitations.data ? buildTodos(needs.data, invitations.data) : [];

  return (
    <section aria-labelledby="todo-title" className="min-w-0 space-y-4 rounded-xl border-2 border-primary bg-card p-5 lg:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="todo-title" className="flex items-center gap-2 font-mono text-xl font-bold">
          <ListTodo className="size-5 text-primary" aria-hidden /> Что сделать сейчас
        </h2>
        {todos.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {todos.length} {plural(todos.length, ["действие", "действия", "действий"])} · сначала самое срочное
          </span>
        )}
      </div>

      {needs.isPending || invitations.isPending ? (
        <RowsSkeleton />
      ) : needs.isError || invitations.isError ? (
        <ErrorState
          variant="block"
          title="Не удалось собрать список дел."
          description={apiError(needs.error ?? invitations.error).message}
          onRetry={onRetry}
        />
      ) : needs.data.length === 0 ? (
        <ol>
          <TodoRow
            todo={{
              key: "first-need",
              icon: Plus,
              text: "Опишите, кого ищете, — подборка кандидатов с объяснением появится сразу",
              action: "Создать потребность",
              to: "/employer/needs/new",
              urgent: true,
            }}
          />
        </ol>
      ) : todos.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {needs.data.some((need) => need.status === "active")
            ? "Срочных дел нет: по действующим потребностям есть шорт-лист, а лимиты приглашений заполнены."
            : "Действующих потребностей нет — откройте черновик или закрытую потребность в разделе «Потребности»."}
        </p>
      ) : (
        <ol className="space-y-3">
          {todos.map((todo) => (
            <TodoRow key={todo.key} todo={todo} />
          ))}
        </ol>
      )}
    </section>
  );
}

function TodoRow({ todo }: { todo: Todo }) {
  const Icon = todo.icon;
  return (
    <li className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-full",
            todo.urgent ? "bg-primary text-primary-foreground" : "bg-primary-tint text-primary",
          )}
          aria-hidden
        >
          <Icon className="size-4" />
        </span>
        <span className="min-w-0 text-sm break-words sm:text-base">{todo.text}</span>
      </div>
      <Button asChild size="sm" variant={todo.urgent ? "default" : "outline"} className="self-stretch max-sm:h-11 sm:self-auto">
        <Link to={todo.to}>
          {todo.action} <ArrowRight />
        </Link>
      </Button>
    </li>
  );
}

function RowsSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Загрузка">
      {[0, 1, 2].map((index) => (
        <div key={index} className="flex items-center gap-3">
          <Skeleton className="size-9 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
          <Skeleton className="hidden h-8 w-32 sm:block" />
        </div>
      ))}
    </div>
  );
}
