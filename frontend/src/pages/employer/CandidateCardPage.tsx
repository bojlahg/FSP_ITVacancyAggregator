import type { LucideIcon } from "lucide-react";
import {
  ArrowLeft,
  BarChart3,
  Briefcase,
  CalendarCheck,
  CheckCircle2,
  ChevronDown,
  Circle,
  ExternalLink,
  Info,
  ListChecks,
  ListTree,
  Lock,
  Mail,
  MapPin,
  MessageCircle,
  MessageSquareText,
  Phone,
  Pin,
  Scale,
  ScanEye,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  Trophy,
  Unlock,
  UserX,
} from "lucide-react";
import { type ReactNode, useState, useSyncExternalStore } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { CandidateCategoryBadge } from "@/components/CategoryBadge";
import { AcceptanceLine } from "@/components/employer/AcceptanceLine";
import { CandidatePdfButton } from "@/components/employer/CandidatePdfButton";
import { InviteDialog } from "@/components/employer/InviteDialog";
import { ScoreTile } from "@/components/employer/ScoreTile";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ExplanationList } from "@/components/ExplanationList";
import { FormAlert } from "@/components/FormAlert";
import { GradeConfidenceBar } from "@/components/GradeConfidence";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import {
  type CandidateCard,
  type Need,
  parseId,
  useCandidateCard,
  useIndustries,
  useNeed,
  useToggleShortlist,
} from "@/lib/employer-queries";
import { daysSince, formatDate, formatDaysAgo, formatExperience, formatNumber, plural, toPercent } from "@/lib/format";
import { FSP_LEVEL_LABELS, SKILL_STATUS_LABELS, workFormatsLabel } from "@/lib/labels";
import { useSoftSkills, useTeamRoles } from "@/lib/profile-queries";
import { useSkillCatalog } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

type SkillState = CandidateCard["skills"][number];

const PHONE_QUERY = "(max-width: 639px)";
const MOBILE_REASONS = 3;

/** На телефоне блоки карточки — аккордеоны, на широком экране — карточки сеткой. */
function useIsPhone(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const media = window.matchMedia(PHONE_QUERY);
      media.addEventListener("change", notify);
      return () => media.removeEventListener("change", notify);
    },
    () => window.matchMedia(PHONE_QUERY).matches,
  );
}

export default function CandidateCardPage() {
  const candidateId = parseId(useParams().candidateId);
  const [searchParams] = useSearchParams();
  const needId = parseId(searchParams.get("need"));
  const card = useCandidateCard(candidateId, needId);
  const need = useNeed(needId);

  const back = (
    <Link
      to={needId ? `/employer/needs/${needId}` : "/employer/search"}
      className="inline-flex min-h-11 items-center gap-1.5 self-start text-sm font-medium text-muted-foreground hover:text-foreground sm:min-h-0"
    >
      <ArrowLeft className="size-4" aria-hidden />
      {needId ? (need.data ? `Подборка: ${need.data.title}` : "К подборке") : "К поиску"}
    </Link>
  );

  if (candidateId === null || (card.isError && [403, 404].includes(apiError(card.error).status))) {
    return (
      <div className="flex flex-col gap-4">
        {back}
        <EmptyState
          icon={UserX}
          title="Кандидат не найден"
          description="Профиль скрыт или кандидат отозвал согласие на публикацию."
          action={
            <Button asChild variant="outline">
              <Link to="/employer/search">К поиску</Link>
            </Button>
          }
        />
      </div>
    );
  }
  if (card.isPending) {
    return (
      <div className="flex flex-col gap-4">
        {back}
        <SkeletonCards count={3} />
      </div>
    );
  }
  if (card.isError) {
    return (
      <div className="flex flex-col gap-4">
        {back}
        <ErrorState description={apiError(card.error).message} onRetry={() => void card.refetch()} />
      </div>
    );
  }

  return (
    <CardView
      key={card.data.brief.id}
      data={card.data}
      need={need.data ?? null}
      needId={needId}
      needPending={needId !== null && need.isPending}
      back={back}
    />
  );
}

function CardView({
  data,
  need,
  needId,
  needPending,
  back,
}: {
  data: CandidateCard;
  need: Need | null;
  needId: number | null;
  needPending: boolean;
  back: ReactNode;
}) {
  const phone = useIsPhone();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [invited, setInvited] = useState(false);
  const shortlist = useToggleShortlist(needId ?? 0);
  const { brief, match } = data;
  const name = data.contacts?.full_name ?? brief.display_name;
  const withinRange = need && brief.salary_min != null ? brief.salary_min <= need.salary_to : null;

  const inviteState =
    data.invitation_status === "accepted"
      ? "accepted"
      : invited || ["sent", "viewed"].includes(data.invitation_status ?? "")
        ? "sent"
        : null;
  const inviteButton = (className?: string) =>
    inviteState ? (
      <Button variant="secondary" disabled className={className}>
        <CheckCircle2 /> {inviteState === "accepted" ? "Приглашение принято" : "Приглашение отправлено"}
      </Button>
    ) : (
      <Button onClick={() => setInviteOpen(true)} disabled={needPending} className={className}>
        <Send /> Пригласить
      </Button>
    );
  // Шорт-лист — только из подборки: он закреплён за потребностью
  const shortlistButton = (iconOnly: boolean) =>
    match && needId !== null ? (
      <Button
        variant="ghost"
        size={iconOnly ? "icon" : "lg"}
        className={cn(
          "border border-border",
          iconOnly && "size-12",
          match.shortlisted && "border-primary bg-primary-tint text-accent-foreground hover:bg-primary-tint",
        )}
        onClick={() =>
          shortlist.mutate(match.shortlisted ? { add: false, candidateId: brief.id } : { add: true, match })
        }
        disabled={shortlist.isPending}
        aria-pressed={match.shortlisted}
        aria-label={iconOnly ? (match.shortlisted ? "В шорт-листе" : "В шорт-лист") : undefined}
        title={match.shortlisted ? "Убрать из шорт-листа" : "Закрепить за потребностью"}
      >
        <Pin className={cn(match.shortlisted && "fill-current")} />
        {!iconOnly && (match.shortlisted ? "В шорт-листе" : "В шорт-лист")}
      </Button>
    ) : null;

  const sections = cardSections(data, need);

  return (
    <div className={cn("flex flex-col gap-4 sm:gap-6", phone && "pb-24")}>
      {back}

      <section
        aria-label="Кандидат"
        className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6 sm:gap-y-4 sm:rounded-[10px] sm:border sm:bg-card sm:p-6"
      >
        {!phone && (
          <span
            aria-hidden
            className="grid size-[72px] shrink-0 place-items-center rounded-full bg-muted font-mono text-2xl font-semibold"
          >
            {initialsOf(name)}
          </span>
        )}
        <div className="flex min-w-0 flex-col gap-2 sm:flex-[1_1_420px]">
          <span className="font-mono text-xs font-medium tracking-widest text-muted-foreground uppercase">
            {data.contacts_unlocked ? "Карточка кандидата · контакты открыты" : "Карточка кандидата · обезличенная"}
          </span>
          <div className="flex items-center gap-3.5">
            {phone &&
              (match ? (
                <ScoreTile score={match.score} tone="solid" />
              ) : (
                <span
                  aria-hidden
                  className="grid size-14 shrink-0 place-items-center rounded-full bg-muted font-mono text-xl font-semibold"
                >
                  {initialsOf(name)}
                </span>
              ))}
            <div className="flex min-w-0 flex-col gap-2">
              <h1 className="font-mono text-2xl font-bold tracking-tight sm:text-3xl">{name}</h1>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <CandidateCategoryBadge candidate={brief} variant={phone ? "soft" : "solid"} size={phone ? "sm" : "md"} />
                {brief.percentile != null && (
                  <span className="text-xs text-muted-foreground sm:text-sm">
                    {toPercent(brief.percentile)}-й перцентиль{phone ? "" : " в категории"}
                  </span>
                )}
                {brief.fsp.has_fsp && (
                  <Badge title={`Достижений ФСП: ${brief.fsp.achievements_count}`}>
                    <Trophy /> ФСП{brief.fsp.max_rank ? ` · ${brief.fsp.max_rank}` : ""}
                  </Badge>
                )}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <MapPin className="size-4" aria-hidden /> {brief.city ?? "город не указан"} ·{" "}
              {workFormatsLabel(brief.work_formats)}
            </span>
            <span>
              Ожидания{" "}
              <span className="font-mono font-semibold whitespace-nowrap text-foreground">
                {brief.salary_min == null ? "скрыты" : `от ${formatNumber(brief.salary_min)} ₽`}
              </span>
              {brief.salary_min != null && " на руки"}
              {withinRange !== null && (
                <span className={withinRange ? "text-accent-foreground" : "text-destructive-strong"}>
                  {" "}
                  · {withinRange ? "в пределах вилки" : "выше вилки"}
                </span>
              )}
            </span>
          </div>
          {!brief.grade_confirmed && (
            <p className="text-sm font-medium">Грейд не подтверждён тестом — навыки тестом не проверены.</p>
          )}
        </div>
        {!phone && (
          <div className="flex flex-none flex-wrap items-center gap-2">
            {shortlistButton(false)}
            {inviteButton("h-12 px-5 text-base")}
          </div>
        )}
      </section>
      <FormAlert message={shortlist.isError ? `Шорт-лист не сохранён: ${apiError(shortlist.error).message}` : null} />

      {match && <WhyCard match={match} need={need} phone={phone} />}

      {phone ? (
        <div className="overflow-hidden rounded-[10px] border bg-card">
          {sections.map((section, index) => (
            <AccordionSection key={section.id} section={section} first={index === 0} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(min(480px,100%),1fr))] items-start gap-6">
          {sections.map((section) => (
            <section
              key={section.id}
              aria-labelledby={`card-${section.id}`}
              className="flex min-w-0 flex-col gap-4 rounded-[10px] border bg-card p-6"
            >
              <h2 id={`card-${section.id}`} className="flex items-center gap-2 font-mono text-base font-semibold tracking-tight">
                <section.icon className="size-4 text-primary" aria-hidden /> {section.title}
              </h2>
              {section.body}
            </section>
          ))}
        </div>
      )}

      {match && phone && (
        <p className="text-xs text-muted-foreground">
          Объяснение, а не магия: оценка и строки «почему» считаются одним кодом из одних и тех же данных.
        </p>
      )}

      {phone && (
        <div className="fixed inset-x-0 bottom-0 z-30 flex gap-2 border-t border-border-subtle bg-background px-4 pt-3 pb-4">
          {shortlistButton(true)}
          {inviteButton("h-12 flex-1 text-base")}
        </div>
      )}

      <InviteDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        candidate={{ id: brief.id, display_name: brief.display_name }}
        need={need}
        match={match}
        onSent={() => setInvited(true)}
      />
    </div>
  );
}

/** «Почему в подборке»: score и полный список причин — одним блоком, из одного объяснения. */
function WhyCard({ match, need, phone }: { match: NonNullable<CandidateCard["match"]>; need: Need | null; phone: boolean }) {
  const [all, setAll] = useState(false);
  const lines = match.explanation.lines;
  const caption = need ? `Score по потребности «${need.title}»` : "Score по потребности";
  if (phone) {
    const hidden = lines.length - MOBILE_REASONS;
    return (
      <section aria-labelledby="why-title" className="flex flex-col gap-3">
        <h2 id="why-title" className="sr-only">
          Почему в подборке
        </h2>
        <span className="text-xs text-muted-foreground">
          {caption}: <b className="font-mono text-foreground">{Math.round(match.score)}</b>
        </span>
        <ExplanationList items={lines} limit={all ? undefined : MOBILE_REASONS} />
        {match.acceptance && all && <AcceptanceLine acceptance={match.acceptance} />}
        {(hidden > 0 || match.acceptance) && (
          <Button variant="ghost" className="h-11 justify-between border border-border" aria-expanded={all} onClick={() => setAll((v) => !v)}>
            {all ? "Свернуть причины" : "Все причины"}
            <span className="ml-auto font-mono text-xs text-muted-foreground">{lines.length}</span>
            <ChevronDown className={cn("transition-transform", all && "rotate-180")} aria-hidden />
          </Button>
        )}
      </section>
    );
  }
  return (
    <section
      aria-labelledby="why-title"
      className="flex flex-wrap gap-x-8 gap-y-5 rounded-[10px] border bg-card p-6"
    >
      <div className="flex w-[148px] flex-none flex-col gap-2">
        <ScoreTile score={match.score} tone="solid" />
        <span className="text-xs text-muted-foreground">{caption}</span>
      </div>
      <div className="flex min-w-0 flex-[1_1_480px] flex-col gap-3">
        <h2 id="why-title" className="font-mono text-xl font-semibold tracking-tight">
          Почему в подборке
        </h2>
        <ExplanationList items={lines} className="space-y-2" />
        {match.acceptance && <AcceptanceLine acceptance={match.acceptance} />}
        <p className="mt-1 border-t border-border-subtle pt-3 text-xs text-muted-foreground">
          Объяснение, а не магия: оценка и строки «почему» считаются одним кодом из одних и тех же данных.
        </p>
      </div>
    </section>
  );
}

interface CardSection {
  id: string;
  title: string;
  icon: LucideIcon;
  /** Короткая подпись справа в свёрнутом аккордеоне на телефоне. */
  hint?: string;
  defaultOpen?: boolean;
  body: ReactNode;
}

function cardSections(data: CandidateCard, need: Need | null): CardSection[] {
  const evidence = data.grade_evidence;
  const fsp = data.fsp?.linked && (data.fsp.achievements.length > 0 || data.fsp.ranks.length > 0) ? data.fsp : null;
  const bestPlace = fsp?.achievements.length ? Math.min(...fsp.achievements.map((item) => item.place)) : null;
  const sections: CardSection[] = [
    {
      id: "skills",
      title: need ? "Навыки и стек потребности" : "Навыки",
      icon: ListTree,
      defaultOpen: true,
      body: <SkillsBlock skills={data.skills} need={need} />,
    },
    {
      id: "test",
      title: "Категория и честность теста",
      icon: ShieldCheck,
      hint: evidence ? `${toPercent(evidence.confidence.at_least)}%` : undefined,
      body: <TestHonesty data={data} />,
    },
    {
      id: "topics",
      title: "Результаты теста по темам",
      icon: BarChart3,
      hint: data.topic_scores.length ? String(data.topic_scores.length) : undefined,
      body: <TopicScores data={data} />,
    },
    {
      id: "fsp",
      title: "Достижения ФСП",
      icon: Trophy,
      hint: bestPlace ? `${bestPlace} место` : undefined,
      body: <FspBlock fsp={fsp} />,
    },
    {
      id: "contacts",
      title: "Контакты",
      icon: data.contacts ? Unlock : Lock,
      hint: data.contacts ? "открыты" : "после принятия",
      body: <ContactsBlock card={data} />,
    },
    { id: "terms", title: "Условия", icon: SlidersHorizontal, body: <TermsBlock card={data} /> },
  ];
  if (data.experience.length > 0 || data.about) {
    sections.push({ id: "experience", title: "Опыт", icon: Briefcase, body: <ExperienceBlock card={data} /> });
  }
  if (data.approach_answers?.length) {
    sections.push({
      id: "approach",
      title: "Открытый вопрос о подходе",
      icon: MessageSquareText,
      body: <ApproachBlock answers={data.approach_answers} />,
    });
  }
  if (data.integrity?.flagged) {
    sections.push({
      id: "integrity",
      title: "Стоит уточнить на собеседовании",
      icon: Info,
      body: <IntegrityBlock signals={data.integrity} />,
    });
  }
  return sections;
}

function AccordionSection({ section, first }: { section: CardSection; first: boolean }) {
  const [open, setOpen] = useState(section.defaultOpen ?? false);
  const bodyId = `card-section-${section.id}`;
  return (
    <div className={cn(!first && "border-t border-border-subtle")}>
      <h2>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen((value) => !value)}
          className="flex min-h-12 w-full items-center gap-3 px-4 text-left text-sm font-medium outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 focus-visible:ring-inset"
        >
          <section.icon className="size-4 shrink-0 text-primary" aria-hidden />
          <span className="flex-1">{section.title}</span>
          {section.hint && <span className="font-mono text-xs text-muted-foreground">{section.hint}</span>}
          <ChevronDown className={cn("size-4 shrink-0 transition-transform", open && "rotate-180")} aria-hidden />
        </button>
      </h2>
      <div id={bodyId} hidden={!open} className="px-4 pb-4">
        {section.body}
      </div>
    </div>
  );
}

const statusChip = (status: SkillState["status"] | null) =>
  status === null ? (
    <span className="text-xs text-muted-foreground">нет в профиле</span>
  ) : status === "verified" ? (
    <span className="inline-flex h-[22px] items-center gap-1 rounded-full bg-primary-tint px-2 font-mono text-xs font-medium whitespace-nowrap text-accent-foreground">
      <ShieldCheck className="size-3" aria-hidden /> {SKILL_STATUS_LABELS.verified}
    </span>
  ) : status === "fsp_confirmed" ? (
    <span className="inline-flex h-[22px] items-center gap-1 rounded-full bg-primary px-2 font-mono text-xs font-medium whitespace-nowrap text-primary-foreground">
      <Trophy className="size-3" aria-hidden /> {SKILL_STATUS_LABELS.fsp_confirmed}
    </span>
  ) : (
    <span
      className={cn(
        "inline-flex h-[22px] items-center rounded-full border px-2 font-mono text-xs font-medium whitespace-nowrap",
        status === "task_confirmed" && "border-primary text-accent-foreground",
      )}
    >
      {SKILL_STATUS_LABELS[status] ?? status}
    </span>
  );

/** Навыки — таблицей «навык | в потребности | статус»: у каждого виден источник подтверждения. */
function SkillsBlock({ skills, need }: { skills: CandidateCard["skills"]; need: Need | null }) {
  const catalog = useSkillCatalog();
  const skillName = (id: string) => byId.get(id)?.name ?? catalog.data?.find((skill) => skill.id === id)?.name ?? id;
  const byId = new Map(skills.map((skill) => [skill.skill_id, skill]));
  const required = need?.required_skills ?? [];
  const optional = need?.optional_skills ?? [];
  const stack = need ? [...required.map((id) => ({ id, required: true })), ...optional.map((id) => ({ id, required: false }))] : [];
  const inStack = new Set(stack.map((item) => item.id));
  const rest = skills.filter((skill) => !inStack.has(skill.skill_id));
  const rows = need
    ? stack.map((item) => ({ id: item.id, name: skillName(item.id), role: item.required ? "обязательный" : "желательный", status: byId.get(item.id)?.status ?? null }))
    : skills.map((skill) => ({ id: skill.skill_id, name: skill.name, role: null, status: skill.status }));
  if (rows.length === 0 && rest.length === 0) return <p className="text-sm text-muted-foreground">Навыки не указаны.</p>;
  return (
    <div className="flex flex-col gap-3">
      {rows.length > 0 && (
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="max-sm:sr-only">
              <tr className="border-b border-border-subtle text-left font-mono text-xs tracking-widest text-muted-foreground uppercase">
                <th scope="col" className="py-2 pr-3 font-medium">
                  Навык
                </th>
                {need && (
                  <th scope="col" className="py-2 pr-3 font-medium max-sm:hidden">
                    В потребности
                  </th>
                )}
                <th scope="col" className="py-2 font-medium">
                  Статус
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="py-3 pr-3 font-mono font-medium">
                    {row.name}
                    {row.role && <span className="block font-sans text-xs font-normal text-muted-foreground sm:hidden">{row.role}</span>}
                  </td>
                  {need && (
                    <td className={cn("py-3 pr-3 max-sm:hidden", row.role === "желательный" && "text-muted-foreground")}>{row.role}</td>
                  )}
                  <td className="py-3 text-right sm:text-left">{statusChip(row.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {need && rest.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>Ещё в профиле:</span>
          {rest.map((skill) => (
            <span
              key={skill.skill_id}
              title={SKILL_STATUS_LABELS[skill.status]}
              className={cn(
                "inline-flex h-[22px] items-center gap-1 rounded-full px-2 font-mono text-xs font-medium",
                skill.status === "verified" ? "bg-primary-tint text-accent-foreground" : "border text-foreground",
              )}
            >
              {skill.status === "verified" && <ShieldCheck className="size-3" aria-hidden />}
              {skill.name}
              {skill.status === "verified" && <span className="sr-only"> — проверено тестом</span>}
            </span>
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground">Щит — навык проверен тестом; остальное заявлено кандидатом или подтверждено ФСП и заданиями.</p>
    </div>
  );
}

function Fact({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <li className="flex gap-2">
      <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
      <span>{children}</span>
    </li>
  );
}

/** Дата и параметры теста, уверенность в грейде (§10.4.1) и сигналы честности — без повторного счёта на фронте. */
function TestHonesty({ data }: { data: CandidateCard }) {
  const evidence = data.grade_evidence;
  if (!evidence) {
    return (
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-muted-foreground">
          {data.brief.grade_confirmed
            ? "Категория подтверждена тестом; подробности теста недоступны."
            : "Грейд не подтверждён: тест не пройден или ещё не сдан, категории нет."}
        </p>
        <Note />
      </div>
    );
  }
  const items = `${evidence.items_scored} ${plural(evidence.items_scored, ["задание", "задания", "заданий"])}`;
  return (
    <div className="flex flex-col gap-4 text-sm">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(180px,100%),1fr))] gap-x-6 gap-y-3">
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-base font-semibold whitespace-nowrap">
            {evidence.tested_at ? formatDate(evidence.tested_at) : "—"}
          </span>
          <span className="text-xs text-muted-foreground">тест пройден</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-base font-semibold whitespace-nowrap">{formatDate(evidence.valid_until)}</span>
          <span className="text-xs text-muted-foreground">результат действителен до</span>
        </div>
      </div>
      <div className="border-t border-border-subtle pt-4">
        <GradeConfidenceBar confidence={evidence.confidence} compact />
      </div>
      <ul className="grid gap-2">
        <Fact icon={ListChecks}>
          {evidence.adaptive ? "Адаптивный тест" : "Тест"}
          {evidence.short_mode ? " (сокращённый демо-режим)" : ""}: {items} с оценкой, задания подбирались по ответам;{" "}
          <span className="font-mono whitespace-nowrap tabular-nums">
            θ = {evidence.theta.toFixed(2).replace(".", ",")} ± {evidence.se.toFixed(2).replace(".", ",")}
          </span>
        </Fact>
        {data.integrity && (
          <Fact icon={ScanEye}>
            {data.integrity.flagged ? `${data.integrity.note} Подробности — в блоке «Стоит уточнить».` : data.integrity.note}
          </Fact>
        )}
        <Fact icon={CalendarCheck}>
          {data.brief.last_activity_at
            ? `Последний тест или задание — ${formatDaysAgo(daysSince(data.brief.last_activity_at))}`
            : "Категория подтверждена тестом"}
        </Fact>
      </ul>
      <Note />
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <Link to={evidence.how_it_works_path} className="text-primary hover:underline">
          Как устроен тест
        </Link>
        <a
          href={evidence.validation_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-primary hover:underline"
        >
          Отчёт валидации <ExternalLink className="size-3.5" aria-hidden />
        </a>
      </div>
    </div>
  );
}

function Note() {
  return (
    <p className="flex items-start gap-2 rounded-[10px] bg-primary-tint px-4 py-3 text-sm">
      <Scale className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
      Грейд выставляет только тест — не резюме и не ИИ.
    </p>
  );
}

function TopicScores({ data }: { data: CandidateCard }) {
  if (data.topic_scores.length === 0) return <p className="text-sm text-muted-foreground">Разбивки по темам нет.</p>;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {data.topic_scores.map((topic) => (
        <div key={topic.topic} className="space-y-1.5">
          <div className="flex justify-between gap-2 text-sm">
            <span>{topic.name}</span>
            <span className="font-mono font-bold whitespace-nowrap tabular-nums">
              {toPercent(topic.score)}%
              <span className="ml-1 text-xs font-normal text-muted-foreground">
                · {topic.items} {plural(topic.items, ["задание", "задания", "заданий"])}
              </span>
            </span>
          </div>
          <Progress value={toPercent(topic.score)} aria-label={`${topic.name}: ${toPercent(topic.score)}%`} />
        </div>
      ))}
    </div>
  );
}

function FspBlock({ fsp }: { fsp: NonNullable<CandidateCard["fsp"]> | null }) {
  if (!fsp) return <p className="text-sm text-muted-foreground">Данных ФСП нет. Профиль оценивается по тесту — это не штраф.</p>;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        {fsp.ownership_verified ? "Профиль подтверждён через ФСП ID" : "Профиль привязан по номеру ФСП ID"} · бонус к профилю, не
        замена теста.
      </p>
      {fsp.ranks.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {fsp.ranks.map((rank) => (
            <Badge key={`${rank.discipline}-${rank.rank}`} title={`Присвоен ${formatDate(rank.awarded_at)}`}>
              {rank.rank} · {rank.discipline}
            </Badge>
          ))}
        </div>
      )}
      {fsp.achievements.length > 0 && (
        <ul className="grid gap-2">
          {fsp.achievements.map((achievement, index) => (
            <li key={index} className="flex items-start gap-3 rounded-lg bg-muted p-3">
              <span className="inline-flex h-6 shrink-0 items-center gap-1 rounded-full bg-primary px-2.5 font-mono text-xs font-medium text-primary-foreground">
                <Trophy className="size-3" aria-hidden /> {achievement.place} место
              </span>
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="text-sm font-medium">{achievement.competition_name}</div>
                <div className="text-xs text-muted-foreground">
                  {FSP_LEVEL_LABELS[achievement.level] ?? achievement.level} · {achievement.discipline} ·{" "}
                  {formatDate(achievement.held_on)} · {achievement.place} из {achievement.participants}
                  {achievement.team_role && ` · роль: ${achievement.team_role}`}
                  {achievement.prize && ` · ${achievement.prize}`}
                </div>
              </div>
              <span className="shrink-0 font-mono text-xs text-muted-foreground" title="Сила результата">
                {toPercent(achievement.strength)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {fsp.competencies.length > 0 && (
        <div className="space-y-2">
          <div className="font-mono text-xs font-bold tracking-wider uppercase">Компетенции</div>
          <div className="grid gap-3">
            {fsp.competencies.map((competency) => (
              <div key={competency.id} className="space-y-1">
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="min-w-0">{competency.name}</span>
                  <span className="shrink-0 font-mono text-xs whitespace-nowrap text-muted-foreground">
                    {competency.status === "confirmed" ? "подтверждена" : "есть признаки"} · {competency.evidence_count}
                  </span>
                </div>
                <Progress value={toPercent(competency.score)} className="h-1.5" aria-label={competency.name} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ContactsBlock({ card }: { card: CandidateCard }) {
  const contacts = card.contacts;
  const pdf = <CandidatePdfButton candidateId={card.brief.id} unlocked={card.contacts_unlocked} align="start" />;
  if (!contacts) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-start gap-2 rounded-lg bg-muted p-3 text-sm">
          <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <span>
            <span className="font-medium">Контакты скрыты</span>. Откроются, когда кандидат примет приглашение. Слепой
            первый просмотр: без фото, возраста и пола, фамилия скрыта.
          </span>
        </div>
        <p className="text-xs text-muted-foreground">Приглашение — всегда с вилкой от–до.</p>
        {pdf}
      </div>
    );
  }
  const rows = [
    { icon: Mail, value: contacts.email, href: contacts.email ? `mailto:${contacts.email}` : null },
    { icon: MessageCircle, value: contacts.telegram, href: null },
    { icon: Phone, value: contacts.phone, href: contacts.phone ? `tel:${contacts.phone}` : null },
  ].filter((row) => row.value);
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-2 rounded-lg border border-primary bg-primary-tint p-3 text-sm">
        <div className="font-medium">{contacts.full_name}</div>
        {rows.map(({ icon: Icon, value, href }) => (
          <div key={value} className="flex items-center gap-2">
            <Icon className="size-4 text-primary" aria-hidden />
            {href ? (
              <a href={href} className="font-mono break-all hover:text-primary hover:underline">
                {value}
              </a>
            ) : (
              <span className="font-mono break-all">{value}</span>
            )}
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">Кандидат принял приглашение — доступ записан в журнал.</p>
      {pdf}
    </div>
  );
}

function TermsBlock({ card }: { card: CandidateCard }) {
  const { brief } = card;
  const industries = useIndustries();
  const teamRoles = useTeamRoles();
  const softSkills = useSoftSkills();
  const row = (label: string, value: ReactNode) => (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
  return (
    <div className="flex flex-col gap-4">
      <dl className="grid gap-2.5 text-sm">
        {row(
          "Ожидания",
          <span className="font-mono font-semibold">
            {brief.salary_min == null ? "скрыты" : `от ${formatNumber(brief.salary_min)} ₽ на руки`}
          </span>,
        )}
        {row("Формат", workFormatsLabel(brief.work_formats))}
        {row("Город", brief.city ?? "не указан")}
        {row("Релокация", brief.relocation ? "Готов" : "Нет")}
        {card.industries_exp.length > 0 && row("Отрасли", catalogNames(card.industries_exp, industries.data))}
        {card.roles.length > 0 && row("Роли", catalogNames(card.roles, teamRoles.data))}
        {brief.last_activity_at && row("Свежесть", formatDaysAgo(daysSince(brief.last_activity_at)))}
      </dl>
      {card.soft_skills.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {card.soft_skills.map((skill) => (
            <Badge key={skill} variant="muted">
              {catalogNames([skill], softSkills.data)}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function ExperienceBlock({ card }: { card: CandidateCard }) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        {card.experience_years != null && `Опыт — ${formatExperience(card.experience_years)}. `}
        {!card.contacts_unlocked && "Названия компаний скрыты до принятия приглашения."}
      </p>
      {card.about && <p className="text-sm leading-relaxed">{card.about}</p>}
      {card.experience.length > 0 && (
        <ol className="space-y-3 border-l border-border-subtle pl-4">
          {card.experience.map((item, index) => (
            <li key={index} className="space-y-0.5">
              <div className="font-medium">
                {item.position}
                {card.contacts_unlocked && item.company && <span className="text-muted-foreground"> · {item.company}</span>}
              </div>
              <div className="font-mono text-xs text-muted-foreground">
                {item.started_on ? formatDate(item.started_on) : "—"} —{" "}
                {item.ended_on ? formatDate(item.ended_on) : "по настоящее время"}
              </div>
              {item.description && <p className="text-sm text-muted-foreground">{item.description}</p>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function IntegrityBlock({ signals }: { signals: NonNullable<CandidateCard["integrity"]> }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">{signals.note}</p>
      <ul className="list-disc space-y-1.5 pl-5 text-sm">
        {signals.reasons.map((reason) => (
          <li key={reason.code}>{reason.text}</li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">
        Статистическая пометка по рисунку и времени ответов, а не вывод о недобросовестности. Решение принимает человек.
      </p>
    </div>
  );
}

function ApproachBlock({ answers }: { answers: NonNullable<CandidateCard["approach_answers"]> }) {
  return (
    <div className="space-y-6">
      <p className="text-xs text-muted-foreground">
        Ответ из теста. Отметки по чек-листу ставит модель, долю отмеченных считает код; в грейд и категорию не входит.
      </p>
      {answers.map((answer, index) => (
        <div key={index} className="space-y-3">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-medium">{answer.question}</p>
            {answer.score != null && (
              <span className="shrink-0 font-mono text-sm font-bold tabular-nums">{toPercent(answer.score)}%</span>
            )}
          </div>
          <p className="rounded-md bg-muted p-3 text-sm whitespace-pre-line">{answer.answer}</p>
          <ul className="space-y-1.5 text-sm">
            {answer.criteria.map((criterion) => (
              <li key={criterion.text} className="flex items-start gap-2">
                {criterion.met ? (
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" aria-label="Выполнено" />
                ) : (
                  <Circle className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label="Не выполнено" />
                )}
                <span className={criterion.met ? "" : "text-muted-foreground"}>{criterion.text}</span>
              </li>
            ))}
          </ul>
          {answer.score == null && <p className="text-xs text-muted-foreground">Ответ ещё не оценён по чек-листу.</p>}
        </div>
      ))}
    </div>
  );
}

/** Названия из справочника вместо слагов; пока справочник грузится или слаг неизвестен — сам слаг. */
function catalogNames(slugs: readonly string[], catalog: readonly { slug: string; name: string }[] | undefined): string {
  return slugs.map((slug) => catalog?.find((item) => item.slug === slug)?.name ?? slug).join(", ");
}

function initialsOf(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
