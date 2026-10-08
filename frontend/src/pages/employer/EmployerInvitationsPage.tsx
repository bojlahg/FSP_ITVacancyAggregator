import { Check, Info, Loader2, Mail, MessageCircle, Phone, Undo2, Unlock, X } from "lucide-react";
import { Fragment, useState } from "react";
import { Link } from "react-router";
import { CandidateCategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
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
import { daysSince, formatDate, formatDateTime, formatDaysAgo, formatNumber, NET, toPercent } from "@/lib/format";
import { DECLINE_REASON_LABELS } from "@/lib/labels";
import { useUrlFilters } from "@/lib/url-filters";
import { cn } from "@/lib/utils";

const TABS = [
  { value: "all", label: "Все", statuses: null, marker: null },
  { value: "active", label: "Ждут ответа", statuses: ["sent", "viewed"], marker: "bg-primary-pale" },
  { value: "accepted", label: "Приняты", statuses: ["accepted"], marker: "check" },
  { value: "declined", label: "Отклонены", statuses: ["declined"], marker: "bg-destructive" },
  { value: "closed", label: "Истекли и отозваны", statuses: ["expired", "withdrawn"], marker: "bg-border" },
] as const satisfies readonly {
  value: string;
  label: string;
  statuses: readonly InvitationStatus[] | null;
  marker: string | null;
}[];

type TabValue = (typeof TABS)[number]["value"];

const ACTIVE: readonly InvitationStatus[] = ["sent", "viewed"];
const CLOSED: readonly InvitationStatus[] = ["expired", "withdrawn"];

const th = "px-3 py-3 font-mono text-xs font-medium tracking-[0.1em] text-muted-foreground uppercase";
const td = "px-3 py-3.5 align-middle";

export default function EmployerInvitationsPage() {
  const { params, set } = useUrlFilters();
  const needId = parseId(params.get("need"));
  const tab: TabValue = TABS.find((item) => item.value === params.get("tab"))?.value ?? "all";
  const [openContacts, setOpenContacts] = useState<Set<number>>(new Set());

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

  const toggleContacts = (id: number) =>
    setOpenContacts((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <>
      <PageHeader
        eyebrow="Приглашения"
        title="Приглашения"
        description="Статусы обновляются, когда кандидат отвечает. Контакты открываются только после принятия; причины отказов — внизу, чтобы понимать, что поправить в предложении."
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

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Фильтр по статусу">
          {TABS.map((item) => {
            const selected = item.value === tab;
            return (
              <button
                key={item.value}
                type="button"
                aria-pressed={selected}
                onClick={() => set({ tab: item.value === "all" ? null : item.value })}
                className={cn(
                  "inline-flex h-9 items-center gap-1.5 rounded-full border px-3.5 font-mono text-[13px] font-medium outline-none transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/40",
                  selected
                    ? "border-primary bg-primary-tint text-accent-foreground"
                    : "border-border text-foreground hover:border-primary",
                )}
              >
                {item.marker === "check" ? (
                  <Check className="size-3.5 text-primary" aria-hidden />
                ) : (
                  item.marker && <span className={cn("size-1.5 rounded-full", item.marker)} aria-hidden />
                )}
                {item.label}
                {invitations.data && <span className="tabular-nums">· {countOf(item.value)}</span>}
              </button>
            );
          })}
        </div>

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
          <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
            {/* Таблица прокручивается в своём блоке — страница на телефоне не уезжает вбок. relative держит внутри
                блока и абсолютно спозиционированные sr-only подписи, иначе они расширяют страницу */}
            <div
              role="region"
              aria-label="Таблица приглашений"
              tabIndex={0}
              className="relative overflow-x-auto rounded-lg border bg-card outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
            >
              <table className="w-full min-w-[920px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b">
                    <th scope="col" className={cn(th, "pl-5")}>
                      Кандидат
                    </th>
                    <th scope="col" className={th}>
                      Потребность
                    </th>
                    <th scope="col" className={th}>
                      Вилка
                    </th>
                    <th scope="col" className={th}>
                      Отправлено
                    </th>
                    <th scope="col" className={th}>
                      Статус
                    </th>
                    <th scope="col" className={cn(th, "pr-5 text-right")}>
                      <span className="sr-only">Действие</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((invitation) => (
                    <InvitationRow
                      key={invitation.id}
                      invitation={invitation}
                      needTitle={needTitle(invitation.need_id)}
                      contactsOpen={openContacts.has(invitation.id)}
                      onToggleContacts={() => toggleContacts(invitation.id)}
                      withdrawing={withdraw.isPending && withdraw.variables === invitation.id}
                      onWithdraw={() => withdraw.mutate(invitation.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Info className="size-3.5 shrink-0" aria-hidden />
              Вилка указана в каждом приглашении — кандидат видит её до ответа.
            </p>
          </div>
        )}

        <DeclineStatsCard needId={needId} />
      </div>
    </>
  );
}

interface InvitationRowProps {
  invitation: InvitationForEmployer;
  needTitle: string | null;
  contactsOpen: boolean;
  onToggleContacts: () => void;
  withdrawing: boolean;
  onWithdraw: () => void;
}

function InvitationRow({
  invitation,
  needTitle,
  contactsOpen,
  onToggleContacts,
  withdrawing,
  onWithdraw,
}: InvitationRowProps) {
  const { candidate, contacts } = invitation;
  const active = ACTIVE.includes(invitation.status);
  const closed = CLOSED.includes(invitation.status);
  const accepted = invitation.status === "accepted";
  const cardPath = `/employer/candidates/${candidate.id}${invitation.need_id ? `?need=${invitation.need_id}` : ""}`;
  const contactsId = `invitation-contacts-${invitation.id}`;
  const showContacts = contacts !== null && contacts !== undefined && contactsOpen;
  const lastCell = cn(!showContacts && "border-b border-border-subtle");

  return (
    <Fragment>
      <tr className={cn(accepted && "bg-primary-tint", closed && "text-muted-foreground", "[&:last-child>td]:border-b-0")}>
        <td className={cn(td, lastCell, "pl-5")}>
          <div className="flex flex-col items-start gap-1">
            <Link to={cardPath} className="font-mono font-semibold hover:text-primary hover:underline">
              {contacts?.full_name ?? candidate.display_name}
            </Link>
            <CandidateCategoryBadge candidate={candidate} className={cn(accepted && "bg-card")} />
          </div>
        </td>
        <td className={cn(td, lastCell, "min-w-[180px]")}>
          {needTitle && sameTitle(needTitle, invitation.title) ? (
            // Заголовок приглашения по умолчанию берётся из потребности — не повторяем его дважды
            <Link
              to={`/employer/needs/${invitation.need_id}`}
              className="underline decoration-border underline-offset-2 hover:text-primary hover:decoration-primary"
            >
              {invitation.title}
            </Link>
          ) : (
            <span>{invitation.title}</span>
          )}
          {needTitle && !sameTitle(needTitle, invitation.title) && (
            <Link
              to={`/employer/needs/${invitation.need_id}`}
              className="mt-0.5 block text-xs text-muted-foreground underline decoration-border underline-offset-2 hover:text-primary hover:decoration-primary"
            >
              {needTitle}
            </Link>
          )}
        </td>
        <td className={cn(td, lastCell)}>
          <span className="block font-mono font-semibold whitespace-nowrap tabular-nums">
            {formatNumber(invitation.salary_from)} – {formatNumber(invitation.salary_to)} ₽
          </span>
          <span className="block text-xs text-muted-foreground">{NET}</span>
        </td>
        <td className={cn(td, lastCell, "whitespace-nowrap")}>
          <span className="block text-muted-foreground" title={formatDateTime(invitation.created_at)}>
            {formatDaysAgo(daysSince(invitation.created_at))}
          </span>
          <span className="block text-xs text-muted-foreground">
            {invitation.viewed_at ? (
              <span title={formatDateTime(invitation.viewed_at)}>
                просмотрено {formatDaysAgo(daysSince(invitation.viewed_at))}
              </span>
            ) : (
              "не просмотрено"
            )}
          </span>
        </td>
        <td className={cn(td, lastCell)}>
          <div className="flex flex-col items-start gap-1">
            <StatusBadge status={invitation.status} className={cn(accepted && "bg-card")} />
            <StatusNote invitation={invitation} />
          </div>
        </td>
        <td className={cn(td, lastCell, "pr-5 text-right whitespace-nowrap")}>
          <div className="flex items-center justify-end gap-1">
            {accepted && contacts ? (
              <Button aria-expanded={contactsOpen} aria-controls={contactsId} onClick={onToggleContacts}>
                <Unlock /> Контакты
              </Button>
            ) : active ? (
              // Карточка кандидата — по ссылке с имени; у ждущих ответа единственное действие — отозвать
              <Button variant="outline" size="sm" onClick={onWithdraw} disabled={withdrawing}>
                {withdrawing ? <Loader2 className="animate-spin" /> : <Undo2 />} Отозвать
              </Button>
            ) : (
              <Button asChild variant="ghost" size="sm">
                <Link to={cardPath}>
                  Карточка<span className="sr-only">: {contacts?.full_name ?? candidate.display_name}</span>
                </Link>
              </Button>
            )}
          </div>
        </td>
      </tr>
      {showContacts && (
        <tr id={contactsId} className="bg-primary-tint">
          <td colSpan={6} className="border-b border-border-subtle px-5 pt-0 pb-4">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-lg border border-primary/30 bg-card px-3 py-2">
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
          </td>
        </tr>
      )}
    </Fragment>
  );
}

/** Подпись под статусом: срок ответа, время ответа или причина отказа (§8.1 п.7). */
function StatusNote({ invitation }: { invitation: InvitationForEmployer }) {
  const { status } = invitation;
  const note = "text-xs text-muted-foreground";
  if (ACTIVE.includes(status)) return <span className={note}>ответ до {formatDate(invitation.expires_at)}</span>;
  if (status === "expired") return <span className={note}>{formatDate(invitation.expires_at)}</span>;
  if (status === "declined") {
    return (
      <span className={cn(note, "max-w-[200px]")}>
        {invitation.decline_reason ? (DECLINE_REASON_LABELS[invitation.decline_reason] ?? invitation.decline_reason) : null}
        {invitation.decline_comment && <span className="block">«{invitation.decline_comment}»</span>}
      </span>
    );
  }
  return invitation.responded_at ? <span className={note}>{formatDateTime(invitation.responded_at)}</span> : null;
}

function sameTitle(a: string, b: string): boolean {
  const normalize = (value: string) => value.trim().replace(/[.\s]+$/, "").toLowerCase();
  return normalize(a) === normalize(b);
}

function DeclineStatsCard({ needId }: { needId: number | null }) {
  const stats = useDeclineStats(needId);
  return (
    <Card>
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
          <div className="grid gap-6 md:grid-cols-2 md:gap-10">
            <div className="space-y-5">
              <dl className="grid grid-cols-3 gap-2 text-center md:text-left">
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
            </div>
            {Object.keys(stats.data.by_reason).length > 0 && (
              <div className="space-y-3 border-t border-border-subtle pt-4 md:border-t-0 md:border-l md:pt-0 md:pl-10">
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
