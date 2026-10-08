import { zodResolver } from "@hookform/resolvers/zod";
import {
  Building2,
  Check,
  ChevronDown,
  Clock,
  Flag,
  Globe,
  Loader2,
  Lock,
  Mail,
  MessageCircle,
  Phone,
  ShieldAlert,
  Unlock,
  User,
  X,
} from "lucide-react";
import { type ReactNode, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ExplanationList } from "@/components/ExplanationList";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { SalaryMarketBadge, SalaryMarketNote } from "@/components/SalaryMarketNote";
import { SalaryFigure } from "@/components/SalaryFigure";
import { SkeletonCards } from "@/components/SkeletonCards";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { apiError } from "@/lib/api-error";
import { useIndustries } from "@/lib/employer-queries";
import { daysSince, formatDate, formatDaysAgo, formatHours, toPercent } from "@/lib/format";
import {
  type InvitationForCandidate,
  useAcceptInvitation,
  useDeclineInvitation,
  useMyInvitations,
  useReportInvitation,
  useViewInvitation,
} from "@/lib/invitation-queries";
import { DECLINE_REASON_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

const DECLINE_REASONS = ["salary", "stack", "work_format", "company", "not_looking", "other"] as const;
const REPORT_REASONS = ["scam", "discrimination", "fake_company", "spam", "other"] as const;
const REPORT_REASON_LABELS: Record<(typeof REPORT_REASONS)[number], string> = {
  scam: "Мошенничество: просят деньги или данные",
  discrimination: "Дискриминация",
  fake_company: "Компания не та, за кого себя выдаёт",
  spam: "Спам или не по профилю",
  other: "Другое",
};
const OPEN_STATUSES: readonly InvitationForCandidate["status"][] = ["sent", "viewed"];

/** Группы списка: новые — сверху, архив (отклонённые, истёкшие, отозванные) свёрнут. */
const GROUPS = [
  { key: "open", title: "Новые", statuses: OPEN_STATUSES },
  { key: "accepted", title: "Принятые", statuses: ["accepted"] },
  { key: "archive", title: "Архив", statuses: ["declined", "expired", "withdrawn"] },
] as const satisfies readonly { key: string; title: string; statuses: readonly InvitationForCandidate["status"][] }[];

const eyebrow = "font-mono text-xs font-medium tracking-[0.1em] text-muted-foreground uppercase";

export default function CandidateInvitationsPage() {
  const invitations = useMyInvitations();
  const view = useViewInvitation();
  const accept = useAcceptInvitation();
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [declining, setDeclining] = useState<InvitationForCandidate | null>(null);
  const [reporting, setReporting] = useState<InvitationForCandidate | null>(null);
  // POST /view — один раз за сессию на приглашение, даже если карточку раскрыли несколько раз.
  const viewSent = useRef(new Set<number>());

  const toggle = (invitation: InvitationForCandidate) => {
    const opening = !expanded.has(invitation.id);
    setExpanded((current) => {
      const next = new Set(current);
      if (opening) next.add(invitation.id);
      else next.delete(invitation.id);
      return next;
    });
    if (opening && invitation.status === "sent" && !viewSent.current.has(invitation.id)) {
      viewSent.current.add(invitation.id);
      view.mutate(invitation.id);
    }
  };

  const sorted = [...(invitations.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const groups = GROUPS.map((group) => ({
    ...group,
    items: sorted.filter((item) => (group.statuses as readonly string[]).includes(item.status)),
  }));

  const renderCard = (invitation: InvitationForCandidate) => (
    <InvitationCard
      key={invitation.id}
      invitation={invitation}
      open={expanded.has(invitation.id)}
      onToggle={() => toggle(invitation)}
      accepting={accept.isPending && accept.variables === invitation.id}
      onAccept={() => accept.mutate(invitation.id)}
      onDecline={() => setDeclining(invitation)}
      onReport={() => setReporting(invitation)}
    />
  );

  return (
    <>
      <PageHeader
        eyebrow="Приглашения"
        title="Приглашения"
        description="Работодатели пишут первыми и сразу указывают вилку. Примете приглашение — работодатель увидит ваши контакты, а вы — контакт рекрутера."
      />

      {invitations.isPending ? (
        <SkeletonCards count={3} />
      ) : invitations.isError ? (
        <ErrorState description={apiError(invitations.error).message} onRetry={() => void invitations.refetch()} />
      ) : sorted.length === 0 ? (
        <EmptyState
          icon={Mail}
          title="Приглашений пока нет"
          description="Как только работодатель выберет вас в подборке, приглашение появится здесь."
        />
      ) : (
        <div className="grid gap-8">
          <FormAlert message={accept.isError ? `Не удалось принять: ${apiError(accept.error).message}` : null} />
          {groups.map((group) => {
            if (group.items.length === 0) return null;
            const headingId = `invitations-${group.key}`;
            if (group.key === "archive") {
              return (
                <section key={group.key} aria-labelledby={headingId} className="grid gap-3">
                  <h2 className="m-0">
                    <button
                      type="button"
                      id={headingId}
                      aria-expanded={archiveOpen}
                      aria-controls={`${headingId}-list`}
                      onClick={() => setArchiveOpen((value) => !value)}
                      className={cn(
                        eyebrow,
                        "inline-flex min-h-9 items-center gap-2 rounded-md pr-2 outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40",
                      )}
                    >
                      <ChevronDown className={cn("size-4 transition-transform", !archiveOpen && "-rotate-90")} aria-hidden />
                      {group.title} · {group.items.length}
                    </button>
                  </h2>
                  {archiveOpen && (
                    <div id={`${headingId}-list`} className="grid gap-3">
                      {group.items.map(renderCard)}
                    </div>
                  )}
                </section>
              );
            }
            return (
              <section key={group.key} aria-labelledby={headingId} className="grid gap-3">
                <h2 id={headingId} className={eyebrow}>
                  {group.title} · {group.items.length}
                </h2>
                {group.items.map(renderCard)}
              </section>
            );
          })}
        </div>
      )}

      <Dialog open={declining !== null} onOpenChange={(open) => !open && setDeclining(null)}>
        <DialogContent>
          {declining && <DeclineForm key={declining.id} invitation={declining} onDone={() => setDeclining(null)} />}
        </DialogContent>
      </Dialog>
      <Dialog open={reporting !== null} onOpenChange={(open) => !open && setReporting(null)}>
        <DialogContent>
          {reporting && <ReportForm key={reporting.id} invitation={reporting} onDone={() => setReporting(null)} />}
        </DialogContent>
      </Dialog>
    </>
  );
}

interface InvitationCardProps {
  invitation: InvitationForCandidate;
  open: boolean;
  onToggle: () => void;
  accepting: boolean;
  onAccept: () => void;
  onDecline: () => void;
  onReport: () => void;
}

/** Две колонки одной сетки: слева компания, роль и «почему вам», справа панель решения с вилкой. */
const columns = "grid gap-x-8 gap-y-4 md:grid-cols-[minmax(0,1fr)_minmax(260px,300px)]";
const panel = "flex min-w-0 flex-col gap-4 md:border-l md:border-border-subtle md:pl-8";

function InvitationCard({ invitation, open, onToggle, accepting, onAccept, onDecline, onReport }: InvitationCardProps) {
  const { company } = invitation;
  const industries = useIndustries();
  const industry = company.industry
    ? (industries.data?.find((item) => item.slug === company.industry)?.name ?? company.industry)
    : null;
  const canRespond = OPEN_STATUSES.includes(invitation.status);
  const accepted = invitation.status === "accepted";
  const detailsId = `invitation-${invitation.id}`;

  let decision: ReactNode = null;
  if (canRespond) {
    decision = (
      <>
        <p className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2.5 text-sm">
          <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <span>Примете приглашение — работодатель увидит ваши контакты, а вы — контакт рекрутера.</span>
        </p>
        {/* На телефоне решение закреплено внизу экрана, пока карточка открыта */}
        <div className="sticky bottom-0 z-10 -mx-4 mt-auto flex flex-row-reverse gap-2 rounded-b-xl border-t border-border-subtle bg-card px-4 pt-3 pb-4 sm:-mx-6 sm:px-6 md:static md:mx-0 md:flex-col md:border-0 md:bg-transparent md:p-0">
          <Button
            size="lg"
            className="min-w-0 flex-[2_1_0%] max-md:px-3 md:flex-none"
            onClick={onAccept}
            disabled={accepting}
          >
            {accepting ? <Loader2 className="animate-spin" /> : <Check className="max-md:hidden" />}
            <span>
              Принять<span className="md:hidden"> приглашение</span>
            </span>
          </Button>
          <Button
            size="lg"
            variant="outline"
            className="min-w-0 flex-[1_1_0%] max-md:px-3 md:flex-none"
            onClick={onDecline}
            disabled={accepting}
          >
            <X className="max-md:hidden" /> Отклонить
          </Button>
        </div>
      </>
    );
  } else if (invitation.contact_method) {
    decision = <ContactBlock invitation={invitation} />;
  }

  return (
    <article
      aria-labelledby={`${detailsId}-title`}
      className={cn(
        "min-w-0 rounded-xl border bg-card text-card-foreground",
        invitation.status === "sent" ? "border-2 border-primary" : canRespond && "border-primary",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={detailsId}
        className={cn(
          columns,
          "w-full rounded-xl p-4 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 sm:p-6",
        )}
      >
        <span className="flex min-w-0 flex-col gap-3">
          <span className="flex items-center gap-3">
            <span
              className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary-tint text-primary sm:size-10"
              aria-hidden
            >
              <Building2 className="size-4 sm:size-5" />
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="text-sm font-medium">{company.company_name}</span>
              {industry && <span className="text-xs text-muted-foreground">{industry}</span>}
            </span>
            <StatusBadge status={invitation.status} audience="recipient" className="ml-auto" />
          </span>
          <span id={`${detailsId}-title`} className="font-mono text-lg font-semibold tracking-tight text-balance sm:text-xl">
            {invitation.title}
          </span>
          <span className="inline-flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
            <Clock className="size-3 shrink-0" aria-hidden />
            пришло {formatDaysAgo(daysSince(invitation.created_at))}
            {canRespond && <> · ответьте до {formatDate(invitation.expires_at)}</>}
          </span>
        </span>
        <span className={cn(panel, "gap-1.5 max-md:rounded-lg max-md:bg-primary-tint max-md:p-3")}>
          <span className={eyebrow}>Вилка</span>
          <SalaryFigure
            from={invitation.salary_from}
            to={invitation.salary_to}
            className="text-[22px] leading-7 md:text-2xl md:leading-8"
          />
          {invitation.salary_market && <SalaryMarketBadge market={invitation.salary_market} />}
          <span className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary">
            {open ? "Свернуть" : "Подробнее"}
            <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} aria-hidden />
          </span>
        </span>
      </button>

      {accepted && (
        <div className="px-4 pb-4 sm:px-6 sm:pb-6">
          <div className="flex items-start gap-2 rounded-lg border border-primary/30 bg-primary-tint px-3 py-2 text-sm" role="status">
            <Unlock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <span>
              Вы приняли приглашение. <b>Работодатель увидит ваши контакты</b> и свяжется с вами — или напишите рекрутеру
              сами.
            </span>
          </div>
        </div>
      )}

      {open && (
        <div id={detailsId} className={cn(columns, "border-t border-border-subtle px-4 pt-5 sm:px-6", canRespond ? "pb-0 md:pb-6" : "pb-4 sm:pb-6")}>
          <div className="flex min-w-0 flex-col gap-5">
            <ScamWarnings invitation={invitation} />
            <div className="space-y-2.5">
              <div className={eyebrow}>Почему вам</div>
              {invitation.why_you.lines.length === 0 ? (
                <p className="text-sm text-muted-foreground">Работодатель пригласил вас без привязки к потребности.</p>
              ) : (
                <ExplanationList items={invitation.why_you.lines} className="space-y-2" />
              )}
              <p className="text-xs text-muted-foreground">То же объяснение совпадения, которое видел работодатель.</p>
            </div>
            <div className="space-y-2.5 border-t border-border-subtle pt-4">
              <div className={eyebrow}>Сообщение работодателя</div>
              <p className="text-sm leading-relaxed whitespace-pre-line">{invitation.message}</p>
            </div>
            {invitation.salary_market && <SalaryMarketNote market={invitation.salary_market} />}
            <CompanyBlock invitation={invitation} />
            <div>
              {invitation.report ? (
                <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground" role="status">
                  <Flag className="size-3.5" aria-hidden /> Жалоба отправлена {formatDate(invitation.report.created_at)}
                  {invitation.report.status === "resolved" ? " · рассмотрена" : " · на рассмотрении"}
                </span>
              ) : (
                <Button variant="ghost" size="sm" className="-ml-3 text-muted-foreground" onClick={onReport}>
                  <Flag /> Пожаловаться
                </Button>
              )}
            </div>
          </div>
          {decision && <div className={panel}>{decision}</div>}
        </div>
      )}
    </article>
  );
}

/** Контакт рекрутера приходит с сервера только после принятия — симметрично раскрытию ваших контактов (§8.5). */
function ContactBlock({ invitation }: { invitation: InvitationForCandidate }) {
  const contact = invitation.contact_method;
  if (!contact) {
    return (
      <p className="rounded-lg border px-3 py-2.5 text-xs text-muted-foreground">
        Контакт рекрутера откроется, когда вы примете приглашение.
      </p>
    );
  }
  const channels = [
    { icon: MessageCircle, label: "Telegram", value: contact.telegram, href: null },
    { icon: Mail, label: "Email", value: contact.email, href: contact.email ? `mailto:${contact.email}` : null },
    { icon: Phone, label: "Телефон", value: contact.phone, href: contact.phone ? `tel:${contact.phone}` : null },
  ].filter((channel) => channel.value);

  return (
    <div className="space-y-2 rounded-lg border px-3 py-2.5 text-sm">
      <div className="flex items-center gap-1.5 font-medium">
        <User className="size-4 text-primary" aria-hidden /> Контакт: {contact.name}
      </div>
      <ul className="grid gap-1">
        {channels.map(({ icon: Icon, label, value, href }) => (
          <li key={label} className="flex items-center gap-2">
            <Icon className="size-3.5 text-muted-foreground" aria-hidden />
            {href ? (
              <a href={href} className="font-mono hover:text-primary hover:underline">
                {value}
              </a>
            ) : (
              <span className="font-mono">{value}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CompanyBlock({ invitation }: { invitation: InvitationForCandidate }) {
  const { company } = invitation;
  const { reputation } = company;
  const facts = [
    reputation.acceptance_rate !== null && `${toPercent(reputation.acceptance_rate)}% приглашений принимают`,
    reputation.withdrawn_rate !== null && `${toPercent(reputation.withdrawn_rate)}% отзывает сама`,
    reputation.median_response_hours !== null && `отвечает на отклики за ${formatHours(reputation.median_response_hours)}`,
  ].filter((fact): fact is string => typeof fact === "string");
  return (
    <div className="space-y-2.5 border-t border-border-subtle pt-4 text-sm">
      <div className={eyebrow}>О компании</div>
      {company.description && <p className="text-muted-foreground">{company.description}</p>}
      {company.website && (
        <a
          href={company.website}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center gap-1.5 text-primary underline underline-offset-2"
        >
          <Globe className="size-3.5" aria-hidden /> {company.website}
        </a>
      )}
      <p className="text-xs text-muted-foreground">
        Приглашений отправлено: {reputation.invitations_sent}
        {facts.length > 0 && ` · ${facts.join(" · ")}`}
      </p>
    </div>
  );
}

const declineSchema = z.object({
  reason: z.enum(DECLINE_REASONS, { error: "Выберите причину" }),
  comment: z.string().trim().max(1000, "Не больше 1000 символов"),
});

type DeclineValues = z.infer<typeof declineSchema>;

function DeclineForm({ invitation, onDone }: { invitation: InvitationForCandidate; onDone: () => void }) {
  const decline = useDeclineInvitation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<DeclineValues>({ resolver: zodResolver(declineSchema), defaultValues: { comment: "" } });

  const onSubmit = (values: DeclineValues) =>
    decline.mutate(
      { invitationId: invitation.id, body: { reason: values.reason, comment: values.comment || null } },
      { onSuccess: onDone },
    );

  return (
    <>
      <DialogHeader>
        <DialogTitle>Отклонить приглашение</DialogTitle>
        <DialogDescription>
          Компания «{invitation.company.company_name}», приглашение «{invitation.title}». Работодатель увидит выбранную
          причину и комментарий в своём списке приглашений — это поможет ему делать более точные предложения.
        </DialogDescription>
      </DialogHeader>
      <form id="decline-form" className="grid gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormAlert message={decline.isError ? apiError(decline.error).message : null} />
        <fieldset className="grid gap-2" aria-describedby={errors.reason ? "decline-reason-error" : undefined}>
          <legend className="mb-1 text-sm font-medium">Причина *</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {DECLINE_REASONS.map((reason) => (
              <label
                key={reason}
                className="flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2 text-sm has-[:checked]:border-primary has-[:checked]:bg-primary-tint"
              >
                <input type="radio" value={reason} className="accent-primary" {...register("reason")} />
                {DECLINE_REASON_LABELS[reason]}
              </label>
            ))}
          </div>
          {errors.reason && (
            <p id="decline-reason-error" className="text-xs font-medium text-destructive-strong" role="alert">
              {errors.reason.message}
            </p>
          )}
        </fieldset>
        <FormField
          id="decline-comment"
          label="Комментарий"
          error={errors.comment?.message}
          hint="Необязательно, работодатель его увидит"
        >
          <Textarea id="decline-comment" rows={3} aria-invalid={!!errors.comment} {...register("comment")} />
        </FormField>
      </form>
      <DialogFooter>
        <DialogClose asChild>
          <Button variant="ghost">Отмена</Button>
        </DialogClose>
        <Button type="submit" form="decline-form" disabled={decline.isPending}>
          {decline.isPending && <Loader2 className="animate-spin" />} Отклонить
        </Button>
      </DialogFooter>
    </>
  );
}

/** Признаки мошенничества в тексте (§8.5): предупреждение, решение остаётся за кандидатом. */
function ScamWarnings({ invitation }: { invitation: InvitationForCandidate }) {
  const warnings = invitation.warnings ?? [];
  if (warnings.length === 0) return null;
  return (
    <div role="status" className="grid gap-2 rounded-lg border border-destructive/30 bg-destructive-tint px-3 py-2 text-sm">
      <div className="flex items-center gap-2 font-medium text-destructive-strong">
        <ShieldAlert className="size-4 shrink-0" aria-hidden /> Будьте осторожны: в приглашении есть признаки мошенничества
      </div>
      <ul className="grid gap-1.5">
        {warnings.map((warning) => (
          <li key={warning.rule}>
            <span className="font-mono text-xs">«{warning.fragment}»</span>{" "}
            <span className="text-muted-foreground">— {warning.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const reportSchema = z.object({
  reason: z.enum(REPORT_REASONS, { error: "Выберите причину" }),
  comment: z.string().trim().max(1000, "Не больше 1000 символов"),
});

type ReportValues = z.infer<typeof reportSchema>;

function ReportForm({ invitation, onDone }: { invitation: InvitationForCandidate; onDone: () => void }) {
  const report = useReportInvitation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ReportValues>({
    resolver: zodResolver(reportSchema),
    defaultValues: { comment: "", reason: (invitation.warnings ?? []).length > 0 ? "scam" : undefined },
  });

  const onSubmit = (values: ReportValues) =>
    report.mutate(
      { invitationId: invitation.id, body: { reason: values.reason, comment: values.comment || null } },
      { onSuccess: onDone },
    );

  return (
    <>
      <DialogHeader>
        <DialogTitle>Пожаловаться на приглашение</DialogTitle>
        <DialogDescription>
          Компания «{invitation.company.company_name}», приглашение «{invitation.title}». Жалобу проверит администратор ITScout, работодатель не
          узнает, кто её отправил. Статус приглашения не изменится — отклонить его можно отдельно.
        </DialogDescription>
      </DialogHeader>
      <form id="report-form" className="grid gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormAlert message={report.isError ? apiError(report.error).message : null} />
        <fieldset className="grid gap-2" aria-describedby={errors.reason ? "report-reason-error" : undefined}>
          <legend className="mb-1 text-sm font-medium">Причина *</legend>
          <div className="grid gap-2">
            {REPORT_REASONS.map((reason) => (
              <label
                key={reason}
                className="flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2 text-sm has-[:checked]:border-primary has-[:checked]:bg-primary-tint"
              >
                <input type="radio" value={reason} className="accent-primary" {...register("reason")} />
                {REPORT_REASON_LABELS[reason]}
              </label>
            ))}
          </div>
          {errors.reason && (
            <p id="report-reason-error" className="text-xs font-medium text-destructive-strong" role="alert">
              {errors.reason.message}
            </p>
          )}
        </fieldset>
        <FormField id="report-comment" label="Что произошло" error={errors.comment?.message} hint="Необязательно">
          <Textarea id="report-comment" rows={3} aria-invalid={!!errors.comment} {...register("comment")} />
        </FormField>
      </form>
      <DialogFooter>
        <DialogClose asChild>
          <Button variant="ghost">Отмена</Button>
        </DialogClose>
        <Button type="submit" form="report-form" disabled={report.isPending}>
          {report.isPending && <Loader2 className="animate-spin" />} Отправить жалобу
        </Button>
      </DialogFooter>
    </>
  );
}
