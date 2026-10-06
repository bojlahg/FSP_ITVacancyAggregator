import { Loader2, Mail, MessageCircle, Phone, Undo2, Unlock, X } from "lucide-react";
import { Link } from "react-router";
import { CandidateCategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { SkeletonCards } from "@/components/SkeletonCards";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiError } from "@/lib/api-error";
import {
  type InvitationForEmployer,
  type InvitationStatus,
  parseId,
  useDeclineStats,
  useEmployerInvitations,
  useNeeds,
  useWithdrawInvitation,
} from "@/lib/employer-queries";
import { formatDateTime, toPercent } from "@/lib/format";
import { DECLINE_REASON_LABELS } from "@/lib/labels";
import { useUrlFilters } from "@/lib/url-filters";
import { cn } from "@/lib/utils";

const TABS = [
  { value: "all", label: "Все", statuses: null },
  { value: "active", label: "Ждут ответа", statuses: ["sent", "viewed"] },
  { value: "accepted", label: "Приняты", statuses: ["accepted"] },
  { value: "declined", label: "Отклонены", statuses: ["declined"] },
  { value: "closed", label: "Истекли и отозваны", statuses: ["expired", "withdrawn"] },
] as const satisfies readonly { value: string; label: string; statuses: readonly InvitationStatus[] | null }[];

type TabValue = (typeof TABS)[number]["value"];

const ACTIVE: readonly InvitationStatus[] = ["sent", "viewed"];

export default function EmployerInvitationsPage() {
  const { params, set } = useUrlFilters();
  const needId = parseId(params.get("need"));
  const tab: TabValue = TABS.find((item) => item.value === params.get("tab"))?.value ?? "all";

  const invitations = useEmployerInvitations(needId === null ? {} : { need_id: needId });
  const needs = useNeeds();
  const withdraw = useWithdrawInvitation();

  const needTitle = (id: number | null) =>
    id === null ? null : (needs.data?.find((need) => need.id === id)?.title ?? `Потребность №${id}`);
  const statusesOf = (value: TabValue) => TABS.find((item) => item.value === value)?.statuses ?? null;
  const countOf = (value: TabValue) => {
    const statuses = statusesOf(value);
    return (invitations.data ?? []).filter((item) => !statuses || (statuses as readonly string[]).includes(item.status))
      .length;
  };
  const statuses = statusesOf(tab);
  const visible = (invitations.data ?? []).filter(
    (item) => !statuses || (statuses as readonly string[]).includes(item.status),
  );

  return (
    <>
      <PageHeader
        eyebrow="Приглашения"
        title="Приглашения"
        description="Статусы всех отправленных приглашений и агрегат причин отказов — чтобы понимать, что поправить в предложении."
      />

      {needId !== null && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">Только по потребности:</span>
          <Link to={`/employer/needs/${needId}`} className="font-medium text-primary hover:underline">
            {needTitle(needId)}
          </Link>
          <Button variant="ghost" size="sm" onClick={() => set({ need: null })}>
            <X /> Все потребности
          </Button>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-4">
          <Tabs value={tab} onValueChange={(value) => set({ tab: value === "all" ? null : value })}>
            <TabsList className="max-w-full">
              {TABS.map((item) => (
                // Вкладки здесь — фильтр списка без отдельных панелей: ссылка на несуществующую панель нарушает ARIA
                <TabsTrigger key={item.value} value={item.value} aria-controls={undefined}>
                  {item.label}
                  {invitations.data && (
                    <span className="font-mono text-xs text-muted-foreground tabular-nums">{countOf(item.value)}</span>
                  )}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <FormAlert message={withdraw.isError ? `Не удалось отозвать: ${apiError(withdraw.error).message}` : null} />

          {invitations.isPending ? (
            <SkeletonCards count={3} />
          ) : invitations.isError ? (
            <ErrorState description={apiError(invitations.error).message} onRetry={() => void invitations.refetch()} />
          ) : invitations.data.length === 0 ? (
            <EmptyState
              icon={Mail}
              title="Вы ещё никого не пригласили"
              description="Откройте подборку по потребности и пригласите подходящих кандидатов."
              action={
                <Button asChild variant="outline">
                  <Link to="/employer/needs">К потребностям</Link>
                </Button>
              }
            />
          ) : visible.length === 0 ? (
            <EmptyState icon={Mail} title="В этом разделе пусто" description="Приглашений с таким статусом нет." />
          ) : (
            <div className="grid gap-3">
              {visible.map((invitation) => (
                <InvitationRow
                  key={invitation.id}
                  invitation={invitation}
                  needTitle={needTitle(invitation.need_id)}
                  withdrawing={withdraw.isPending && withdraw.variables === invitation.id}
                  onWithdraw={() => withdraw.mutate(invitation.id)}
                />
              ))}
            </div>
          )}
        </div>

        <DeclineStatsCard needId={needId} />
      </div>
    </>
  );
}

interface InvitationRowProps {
  invitation: InvitationForEmployer;
  needTitle: string | null;
  withdrawing: boolean;
  onWithdraw: () => void;
}

function InvitationRow({ invitation, needTitle, withdrawing, onWithdraw }: InvitationRowProps) {
  const { candidate, contacts } = invitation;
  const active = ACTIVE.includes(invitation.status);
  return (
    <Card className="gap-4">
      <CardContent className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto]">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/employer/candidates/${candidate.id}${invitation.need_id ? `?need=${invitation.need_id}` : ""}`}
              className="font-mono font-bold hover:text-primary hover:underline"
            >
              {contacts?.full_name ?? candidate.display_name}
            </Link>
            <CandidateCategoryBadge candidate={candidate} />
            <StatusBadge status={invitation.status} />
          </div>
          <div className="text-sm">
            <span className="font-medium">{invitation.title}</span>
            {needTitle && (
              <span className="text-muted-foreground">
                {" "}
                ·{" "}
                <Link
                  to={`/employer/needs/${invitation.need_id}`}
                  className="underline decoration-border underline-offset-2 hover:text-primary hover:decoration-primary"
                >
                  {needTitle}
                </Link>
              </span>
            )}
          </div>
          <SalaryRange from={invitation.salary_from} to={invitation.salary_to} className="text-primary" />
        </div>
        <div className="flex items-start md:justify-end">
          {active && (
            <Button variant="outline" size="sm" onClick={onWithdraw} disabled={withdrawing}>
              {withdrawing ? <Loader2 className="animate-spin" /> : <Undo2 />} Отозвать
            </Button>
          )}
        </div>

        <StatusTimeline invitation={invitation} />

        {invitation.status === "declined" && invitation.decline_reason && (
          <div className="rounded-lg bg-destructive-tint px-3 py-2 text-sm md:col-span-2">
            Причина отказа: <b>{DECLINE_REASON_LABELS[invitation.decline_reason] ?? invitation.decline_reason}</b>
            {invitation.decline_comment && <span className="text-muted-foreground"> — «{invitation.decline_comment}»</span>}
          </div>
        )}

        {contacts && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-primary/30 bg-primary-tint px-3 py-2 text-sm md:col-span-2">
            <span className="flex items-center gap-1.5 font-medium">
              <Unlock className="size-4 text-primary" aria-hidden /> Контакты открыты
            </span>
            {contacts.email && (
              <a href={`mailto:${contacts.email}`} className="flex items-center gap-1.5 font-mono hover:underline">
                <Mail className="size-3.5" aria-hidden /> {contacts.email}
              </a>
            )}
            {contacts.telegram && (
              <span className="flex items-center gap-1.5 font-mono">
                <MessageCircle className="size-3.5" aria-hidden /> {contacts.telegram}
              </span>
            )}
            {contacts.phone && (
              <a href={`tel:${contacts.phone}`} className="flex items-center gap-1.5 font-mono hover:underline">
                <Phone className="size-3.5" aria-hidden /> {contacts.phone}
              </a>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** sent → viewed → ответ (accepted | declined) | expired | withdrawn — §8.1 п.7. */
function StatusTimeline({ invitation }: { invitation: InvitationForEmployer }) {
  const { status } = invitation;
  const final =
    status === "accepted"
      ? { label: "Принято", at: invitation.responded_at }
      : status === "declined"
        ? { label: "Отклонено", at: invitation.responded_at }
        : status === "withdrawn"
          ? { label: "Отозвано", at: invitation.responded_at }
          : status === "expired"
            ? { label: "Истёк срок", at: invitation.expires_at }
            : { label: `Ответ до ${formatDateTime(invitation.expires_at)}`, at: null };
  const steps = [
    { label: "Отправлено", at: invitation.created_at, done: true },
    { label: "Просмотрено", at: invitation.viewed_at, done: invitation.viewed_at !== null },
    { label: final.label, at: final.at, done: !ACTIVE.includes(status) },
  ];
  return (
    <ol className="flex flex-wrap items-start gap-x-2 gap-y-2 md:col-span-2" aria-label="История статусов">
      {steps.map((step, index) => (
        <li key={index} className="flex items-start gap-2">
          {index > 0 && <span className={cn("mt-1.5 h-px w-6", step.done ? "bg-primary" : "bg-border")} aria-hidden />}
          <span className="flex items-start gap-1.5">
            <span
              className={cn(
                "mt-1 size-2.5 shrink-0 rounded-full border-2",
                step.done ? "border-primary bg-primary" : "border-border bg-background",
              )}
              aria-hidden
            />
            <span className="text-xs">
              <span className={cn("font-medium", !step.done && "text-muted-foreground")}>{step.label}</span>
              {step.at && step.done && <span className="block text-muted-foreground">{formatDateTime(step.at)}</span>}
            </span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function DeclineStatsCard({ needId }: { needId: number | null }) {
  const stats = useDeclineStats(needId);
  return (
    <Card className="h-fit">
      <CardHeader>
        <CardTitle>Причины отказов</CardTitle>
        <CardDescription>
          {stats.data ? (stats.data.hint ?? (stats.data.declined === 0 ? "Отказов пока нет" : null)) : "По всем вашим приглашениям"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {stats.isPending ? (
          <SkeletonCards count={1} />
        ) : stats.isError ? (
          <ErrorState className="py-6" description={apiError(stats.error).message} onRetry={() => void stats.refetch()} />
        ) : (
          <div className="space-y-5">
            <dl className="grid grid-cols-3 gap-2 text-center">
              <div>
                <dt className="text-xs text-muted-foreground">Отправлено</dt>
                <dd className="font-mono text-xl font-extrabold tabular-nums">{stats.data.total_sent}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Принято</dt>
                <dd className="font-mono text-xl font-extrabold text-primary tabular-nums">{stats.data.accepted}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Отказы</dt>
                <dd className="font-mono text-xl font-extrabold tabular-nums">{stats.data.declined}</dd>
              </div>
            </dl>
            {stats.data.acceptance_rate !== null && (
              <div className="space-y-1.5">
                <div className="flex justify-between text-sm">
                  <span>Доля принятых</span>
                  <span className="font-mono font-bold">{toPercent(stats.data.acceptance_rate)}%</span>
                </div>
                <Progress value={toPercent(stats.data.acceptance_rate)} aria-label="Доля принятых приглашений" />
              </div>
            )}
            {Object.keys(stats.data.by_reason).length > 0 && (
              <div className="space-y-3 border-t border-border-subtle pt-4">
                {Object.entries(stats.data.by_reason)
                  .sort(([, a], [, b]) => b - a)
                  .map(([reason, count]) => (
                    <div key={reason} className="space-y-1.5">
                      <div className="flex justify-between text-sm">
                        <span className={cn(reason === stats.data.top_reason && "font-bold")}>
                          {DECLINE_REASON_LABELS[reason] ?? reason}
                        </span>
                        <span className="font-mono font-bold">{count}</span>
                      </div>
                      <Progress
                        value={stats.data.declined > 0 ? (count / stats.data.declined) * 100 : 0}
                        indicatorClassName={reason === stats.data.top_reason ? "bg-destructive" : undefined}
                        aria-label={DECLINE_REASON_LABELS[reason] ?? reason}
                      />
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
