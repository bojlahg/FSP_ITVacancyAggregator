import {
  Briefcase,
  Check,
  ChevronDown,
  ExternalLink,
  Inbox,
  Loader2,
  Mail,
  MessageCircle,
  Phone,
  Send,
  Unlock,
  User,
  X,
} from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router";
import { CandidateCategoryBadge, CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ExplanationList } from "@/components/ExplanationList";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { ScoreBadge } from "@/components/ScoreBadge";
import { SkeletonCards } from "@/components/SkeletonCards";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import { type Need, useNeeds } from "@/lib/employer-queries";
import { formatDate, plural } from "@/lib/format";
import { NEED_STATUS_LABELS, WORK_FORMAT_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import {
  type ApplicationForEmployer,
  OPEN_APPLICATION_STATUSES,
  useDecideApplication,
  useNeedApplications,
  useViewApplication,
} from "@/lib/vacancy-queries";

const candidateHref = (candidateId: number, needId: number) => `/employer/candidates/${candidateId}?need=${needId}`;

export default function EmployerVacanciesPage() {
  const needs = useNeeds();
  // null — пользователь ещё ничего не раскрывал: по умолчанию открыта первая вакансия с откликами.
  const [openIds, setOpenIds] = useState<Set<number> | null>(null);

  const vacancies = (needs.data ?? []).filter((need) => need.published);
  const opened = openIds ?? new Set(vacancies.filter((v) => v.stats.applications > 0).slice(0, 1).map((v) => v.id));

  const toggle = (id: number) => {
    const next = new Set(opened);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setOpenIds(next);
  };

  return (
    <>
      <PageHeader
        eyebrow="Вакансии и отклики"
        title="Вакансии и отклики"
        description="Вакансия — это опубликованная потребность. Отклик сразу открывает контакты кандидата; отклики отсортированы по тому же score, что и подборка."
      />
      {needs.isPending ? (
        <SkeletonCards count={2} />
      ) : needs.isError ? (
        <ErrorState description={apiError(needs.error).message} onRetry={() => void needs.refetch()} />
      ) : vacancies.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="Опубликованных вакансий нет"
          description="Опубликуйте любую потребность — она появится в списке вакансий у кандидатов, и они смогут откликаться сами."
          action={
            <Button asChild variant="outline">
              <Link to="/employer/needs">К потребностям</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4">
          {vacancies.map((vacancy) => (
            <VacancyCard
              key={vacancy.id}
              vacancy={vacancy}
              open={opened.has(vacancy.id)}
              onToggle={() => toggle(vacancy.id)}
            />
          ))}
        </div>
      )}
    </>
  );
}

function VacancyCard({ vacancy, open, onToggle }: { vacancy: Need; open: boolean; onToggle: () => void }) {
  const count = vacancy.stats.applications;
  const place = [vacancy.city, vacancy.work_format ? WORK_FORMAT_LABELS[vacancy.work_format] : null].filter(Boolean);
  const listId = `vacancy-${vacancy.id}-applications`;

  return (
    <Card>
      <CardHeader className="gap-y-3 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <CategoryBadge specialization={vacancy.category.specialization} grade={vacancy.category.grade} />
            {vacancy.status === "closed" && <Badge variant="muted">{NEED_STATUS_LABELS.closed}</Badge>}
          </div>
          <CardTitle className="text-lg">
            <Link to={`/employer/needs/${vacancy.id}`} className="hover:text-primary hover:underline">
              {vacancy.title}
            </Link>
          </CardTitle>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <SalaryRange from={vacancy.salary_from} to={vacancy.salary_to} className="text-foreground" />
            {place.length > 0 && <span>{place.join(" · ")}</span>}
            {vacancy.published_at && <span>опубликована {formatDate(vacancy.published_at)}</span>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:flex-col sm:items-end">
          <Button
            variant={open ? "secondary" : "outline"}
            size="sm"
            onClick={onToggle}
            aria-expanded={open}
            aria-controls={listId}
          >
            <Send /> {count} {plural(count, ["отклик", "отклика", "откликов"])}
            <ChevronDown className={cn("transition-transform", open && "rotate-180")} aria-hidden />
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link to={`/employer/needs/${vacancy.id}`}>Подборка</Link>
          </Button>
        </div>
      </CardHeader>
      {open && (
        <CardContent id={listId} className="border-t border-border-subtle pt-5">
          <ApplicationsList needId={vacancy.id} />
        </CardContent>
      )}
    </Card>
  );
}

function ApplicationsList({ needId }: { needId: number }) {
  const applications = useNeedApplications(needId);
  const view = useViewApplication(needId);
  const decide = useDecideApplication(needId);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  // POST /view — один раз за сессию на отклик, даже если его раскрыли несколько раз.
  const viewSent = useRef(new Set<number>());

  const toggle = (application: ApplicationForEmployer) => {
    const opening = !expanded.has(application.id);
    setExpanded((current) => {
      const next = new Set(current);
      if (opening) next.add(application.id);
      else next.delete(application.id);
      return next;
    });
    if (opening && application.status === "sent" && !viewSent.current.has(application.id)) {
      viewSent.current.add(application.id);
      view.mutate(application.id);
    }
  };

  if (applications.isPending) {
    return (
      <div className="grid gap-2" aria-busy="true" aria-label="Загрузка откликов">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
    );
  }
  if (applications.isError) {
    return (
      <ErrorState
        title="Не удалось загрузить отклики"
        description={apiError(applications.error).message}
        onRetry={() => void applications.refetch()}
      />
    );
  }
  if (applications.data.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="Откликов пока нет"
        description="Кандидаты видят вакансию в своём списке, отсортированном по совпадению. Пока ждёте — пригласите сильных кандидатов из подборки сами."
        action={
          <Button asChild variant="outline" size="sm">
            <Link to={`/employer/needs/${needId}`}>К подборке</Link>
          </Button>
        }
        className="py-8"
      />
    );
  }

  return (
    <div className="grid gap-3">
      <FormAlert message={decide.isError ? `Не удалось сохранить решение: ${apiError(decide.error).message}` : null} />
      <ul className="grid gap-3">
        {applications.data.map((application) => (
          <ApplicationRow
            key={application.id}
            needId={needId}
            application={application}
            open={expanded.has(application.id)}
            onToggle={() => toggle(application)}
            deciding={decide.isPending && decide.variables.applicationId === application.id}
            onDecide={(accept) => decide.mutate({ applicationId: application.id, accept })}
          />
        ))}
      </ul>
    </div>
  );
}

interface ApplicationRowProps {
  needId: number;
  application: ApplicationForEmployer;
  open: boolean;
  onToggle: () => void;
  deciding: boolean;
  onDecide: (accept: boolean) => void;
}

function ApplicationRow({ needId, application, open, onToggle, deciding, onDecide }: ApplicationRowProps) {
  const { candidate } = application;
  const canDecide = OPEN_APPLICATION_STATUSES.includes(application.status);
  // null — снимок совпадения не сохранился: не выдаём это за оценку.
  const score = application.match_score;
  const detailsId = `application-${application.id}`;

  return (
    <li
      className={cn(
        "rounded-lg border",
        application.status === "sent" && "border-primary ring-1 ring-primary/20",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={detailsId}
        className="flex w-full flex-wrap items-center gap-3 rounded-lg px-4 py-3 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
      >
        {score !== null ? (
          <ScoreBadge score={score} size="sm" />
        ) : (
          <span
            className="inline-flex h-7 min-w-9 items-center justify-center rounded-lg bg-muted font-mono text-sm text-muted-foreground"
            title="Совпадение не рассчитано"
          >
            —
          </span>
        )}
        <span className="min-w-[11rem] flex-1 space-y-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{candidate.display_name}</span>
            <CandidateCategoryBadge candidate={candidate} />
            {application.status === "sent" && <span className="font-mono text-xs font-bold text-primary">новый</span>}
          </span>
          <span className="block text-xs text-muted-foreground">
            отклик {formatDate(application.created_at)}
            {candidate.city && ` · ${candidate.city}`}
          </span>
        </span>
        <StatusBadge status={application.status} />
        <ChevronDown
          className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>

      {open && (
        <div id={detailsId} className="grid gap-4 border-t border-border-subtle px-4 py-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-4 text-sm">
              <div className="space-y-1">
                <div className="font-mono text-xs font-bold tracking-wider uppercase">Сопроводительный текст</div>
                {application.cover_note ? (
                  <p className="leading-relaxed whitespace-pre-line">{application.cover_note}</p>
                ) : (
                  <p className="text-muted-foreground">Кандидат откликнулся без сопроводительного текста.</p>
                )}
              </div>
              <ContactsBlock application={application} />
            </div>
            <div className="h-fit rounded-lg bg-muted/60 p-4">
              <div className="mb-2 font-mono text-xs font-bold tracking-wider uppercase">Почему подходит</div>
              {application.match_explanation.lines.length === 0 ? (
                <p className="text-sm text-muted-foreground">Объяснение совпадения не сохранилось.</p>
              ) : (
                <ExplanationList items={application.match_explanation.lines} />
              )}
              <p className="mt-3 text-xs text-muted-foreground">Снимок на момент отклика — его же видит кандидат.</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {canDecide && (
              <>
                <Button size="sm" onClick={() => onDecide(true)} disabled={deciding}>
                  {deciding ? <Loader2 className="animate-spin" /> : <Check />} Принять
                </Button>
                <Button size="sm" variant="outline" onClick={() => onDecide(false)} disabled={deciding}>
                  <X /> Отклонить
                </Button>
              </>
            )}
            <Button asChild size="sm" variant="ghost">
              <Link to={candidateHref(candidate.id, needId)}>
                <ExternalLink /> Карточка кандидата
              </Link>
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

/** Контакты уже открыты откликом: кандидат сам начал общение (§8.7). */
function ContactsBlock({ application }: { application: ApplicationForEmployer }) {
  const { contacts } = application;
  const channels = [
    { icon: MessageCircle, label: "Telegram", value: contacts.telegram, href: null },
    { icon: Mail, label: "Email", value: contacts.email, href: contacts.email ? `mailto:${contacts.email}` : null },
    { icon: Phone, label: "Телефон", value: contacts.phone, href: contacts.phone ? `tel:${contacts.phone}` : null },
  ].filter((channel) => channel.value);

  return (
    <div className="space-y-2 rounded-lg border px-3 py-2.5">
      <div className="flex items-center gap-1.5 font-medium">
        <User className="size-4 text-primary" aria-hidden /> {contacts.full_name}
      </div>
      {channels.length === 0 ? (
        <p className="text-xs text-muted-foreground">Кандидат не указал каналы связи.</p>
      ) : (
        <ul className="grid gap-1">
          {channels.map(({ icon: Icon, label, value, href }) => (
            <li key={label} className="flex items-center gap-2">
              <Icon className="size-3.5 text-muted-foreground" aria-label={label} />
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
      )}
      <p className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Unlock className="size-3" aria-hidden /> Контакты открыты откликом кандидата
      </p>
    </div>
  );
}
