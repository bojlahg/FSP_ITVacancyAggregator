import { AlertTriangle, ArrowRight, Check, CheckCircle2, ChevronDown, Loader2, Pin, Send, ShieldCheck, Trophy } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { CandidateCategoryBadge } from "@/components/CategoryBadge";
import { AcceptanceLine } from "@/components/employer/AcceptanceLine";
import { ScoreTile } from "@/components/employer/ScoreTile";
import { ExplanationList } from "@/components/ExplanationList";
import { Button } from "@/components/ui/button";
import type { CandidateMatch } from "@/lib/employer-queries";
import { daysSince, formatDaysAgo, formatNumber, toPercent } from "@/lib/format";
import { workFormatsLabel } from "@/lib/labels";
import { useSkillCatalog } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

const MAX_SKILLS = 4;
const REASONS = 3;

interface MatchRowProps {
  match: CandidateMatch;
  /** Ссылка на карточку кандидата. */
  href: string;
  /** Верхняя граница вилки потребности: ожидания «в пределах вилки» или «выше вилки». */
  salaryTo: number;
  /** Навыки потребности (сначала обязательные): их показываем в ряду бейджей первыми. */
  stack: readonly string[];
  shortlistPending?: boolean;
  onToggleShortlist: () => void;
  /** Статус открытого приглашения — вместо кнопки «Пригласить». */
  invitedStatus?: string;
  onInvite: () => void;
  inviteDisabledReason?: string;
}

/**
 * Строка подборки (§8.4): score рядом с тремя причинами из того же объяснения, один ряд бейджей
 * (ФСП и навыки стека, щит — проверено тестом), ожидания моно-цифрой справа.
 */
export function MatchRow({
  match,
  href,
  salaryTo,
  stack,
  shortlistPending = false,
  onToggleShortlist,
  invitedStatus,
  onInvite,
  inviteDisabledReason,
}: MatchRowProps) {
  const { candidate, shortlisted } = match;
  const [moreOpen, setMoreOpen] = useState(false);
  const catalog = useSkillCatalog();
  const skillName = (id: string) => catalog.data?.find((skill) => skill.id === id)?.name ?? id;

  const verified = new Set(candidate.verified_skills);
  const own = [...candidate.verified_skills, ...candidate.declared_skills];
  const inStack = new Set(stack);
  // Сначала навыки стека потребности (проверенные тестом — первыми), затем остальные проверенные
  const ordered = [
    ...own.filter((id) => inStack.has(id) && verified.has(id)),
    ...own.filter((id) => inStack.has(id) && !verified.has(id)),
    ...candidate.verified_skills.filter((id) => !inStack.has(id)),
    ...candidate.declared_skills.filter((id) => !inStack.has(id)),
  ];
  const skills = ordered.slice(0, MAX_SKILLS);
  const hiddenSkills = ordered.length - skills.length;

  const salary = candidate.salary_min;
  const withinRange = salary != null && salary <= salaryTo;
  const meta = [
    candidate.city ?? "город не указан",
    workFormatsLabel(candidate.work_formats),
    candidate.relocation ? "релокация" : null,
    candidate.last_activity_at ? formatDaysAgo(daysSince(candidate.last_activity_at)) : null,
  ].filter(Boolean);
  const moreId = `match-more-${candidate.id}`;

  const fit =
    salary == null ? null : withinRange ? (
      <span className="inline-flex items-center gap-1 text-accent-foreground">
        <Check className="size-3.5" aria-hidden /> в пределах вилки
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 text-destructive-strong">
        <AlertTriangle className="size-3.5" aria-hidden /> выше вилки
      </span>
    );

  return (
    <article
      aria-label={candidate.display_name}
      className={cn(
        "flex flex-col gap-3 rounded-[10px] border bg-card p-4 transition-shadow hover:shadow-md sm:flex-row sm:flex-wrap sm:gap-x-5 sm:gap-y-4 sm:p-5",
        shortlisted && "border-primary",
      )}
    >
      <ScoreTile score={match.score} className="hidden sm:grid" />

      <div className="flex min-w-0 flex-col gap-2.5 sm:flex-[1_1_340px]">
        <div className="flex items-center gap-3">
          <ScoreTile score={match.score} size="md" className="sm:hidden" />
          <div className="flex min-w-0 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <Link to={href} className="font-mono text-base font-semibold tracking-tight hover:text-primary hover:underline">
                {candidate.display_name}
              </Link>
              <CandidateCategoryBadge candidate={candidate} className="max-sm:hidden" />
              {candidate.percentile != null && (
                <span className="text-xs text-muted-foreground max-sm:hidden">
                  {toPercent(candidate.percentile)}-й перцентиль
                </span>
              )}
              {shortlisted && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-accent-foreground">
                  <Pin className="size-3.5" aria-hidden /> в шорт-листе
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:hidden">
              <CandidateCategoryBadge candidate={candidate} />
              {candidate.percentile != null && (
                <span className="text-xs text-muted-foreground">{toPercent(candidate.percentile)}-й перцентиль</span>
              )}
            </div>
            <span className={cn("text-xs text-muted-foreground", moreOpen ? "max-sm:order-last" : "max-sm:hidden")}>
              {meta.join(" · ")}
            </span>
          </div>
        </div>

        <p className="text-sm text-muted-foreground sm:hidden">
          Ожидания{" "}
          <span className="font-mono font-semibold whitespace-nowrap text-foreground">
            {salary == null ? "скрыты" : `от ${formatNumber(salary)} ₽`}
          </span>
          {fit && <> · {fit}</>}
        </p>

        {match.explanation.lines.length > 0 && (
          <ExplanationList items={match.explanation.lines} limit={REASONS} />
        )}
        {/* В списке «высокая» у большинства и ничего не говорит — показываем только сигнал; полная строка в карточке */}
        {match.acceptance && match.acceptance.level !== "high" && <AcceptanceLine acceptance={match.acceptance} />}

        <button
          type="button"
          aria-expanded={moreOpen}
          aria-controls={moreId}
          onClick={() => setMoreOpen((open) => !open)}
          className="flex h-11 w-full items-center justify-between border-t border-border-subtle text-sm font-medium outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 sm:hidden"
        >
          Подробнее
          <ChevronDown className={cn("size-4 transition-transform", moreOpen && "rotate-180")} aria-hidden />
        </button>

        <div id={moreId} className={cn("flex-col gap-2.5", moreOpen ? "flex" : "hidden sm:flex")}>
          {(candidate.fsp.has_fsp || skills.length > 0) && (
            <ul className="flex flex-wrap items-center gap-1.5" aria-label="ФСП и навыки">
              {candidate.fsp.has_fsp && (
                <li
                  title={`Достижений ФСП: ${candidate.fsp.achievements_count}`}
                  className="inline-flex h-[22px] items-center gap-1 rounded-full bg-primary px-2 font-mono text-xs font-medium text-primary-foreground"
                >
                  <Trophy className="size-3" aria-hidden /> ФСП{candidate.fsp.max_rank ? ` · ${candidate.fsp.max_rank}` : ""}
                </li>
              )}
              {skills.map((id) =>
                verified.has(id) ? (
                  <li
                    key={id}
                    title="Проверено тестом"
                    className="inline-flex h-[22px] items-center gap-1 rounded-full bg-primary-tint px-2 font-mono text-xs font-medium text-accent-foreground"
                  >
                    <ShieldCheck className="size-3" aria-hidden />
                    {skillName(id)}
                    <span className="sr-only"> — проверено тестом</span>
                  </li>
                ) : (
                  <li
                    key={id}
                    title="Заявлено"
                    className="inline-flex h-[22px] items-center rounded-full border px-2 font-mono text-xs font-medium"
                  >
                    {skillName(id)}
                  </li>
                ),
              )}
              {hiddenSkills > 0 && (
                <li className="font-mono text-xs text-muted-foreground" title="Ещё навыки — в карточке кандидата">
                  +{hiddenSkills}
                </li>
              )}
            </ul>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2.5 sm:min-w-[180px] sm:flex-[0_1_220px] sm:items-end sm:text-right">
        <div className="hidden flex-col items-end gap-1 sm:flex">
          <span className="font-mono text-xs font-medium tracking-widest text-muted-foreground uppercase">Ожидания</span>
          <span className="font-mono text-base font-semibold whitespace-nowrap">
            {salary == null ? "скрыты" : `от ${formatNumber(salary)} ₽`}
          </span>
          {fit && <span className="text-xs text-muted-foreground">{fit}</span>}
        </div>
        <div className="flex gap-2 sm:mt-auto">
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              "size-11 border border-border sm:size-9",
              shortlisted && "border-primary bg-primary-tint text-accent-foreground",
            )}
            onClick={onToggleShortlist}
            disabled={shortlistPending}
            aria-pressed={shortlisted}
            aria-label={shortlisted ? "В шорт-листе" : "В шорт-лист"}
            title={shortlisted ? "Убрать из шорт-листа" : "В шорт-лист"}
          >
            {shortlistPending ? <Loader2 className="animate-spin" /> : <Pin className={cn(shortlisted && "fill-current")} />}
          </Button>
          {invitedStatus ? (
            <Button variant="secondary" disabled className="h-11 flex-1 sm:h-9 sm:flex-none">
              <CheckCircle2 /> {invitedStatus === "accepted" ? "Приглашение принято" : "Приглашение отправлено"}
            </Button>
          ) : (
            <Button
              onClick={onInvite}
              disabled={!!inviteDisabledReason}
              title={inviteDisabledReason}
              className="h-11 flex-1 text-base sm:h-9 sm:flex-none sm:text-sm"
            >
              <Send /> Пригласить
            </Button>
          )}
        </div>
        <Link
          to={href}
          className="inline-flex items-center gap-1 self-start text-sm font-medium text-primary hover:underline sm:self-end sm:text-[13px]"
        >
          Карточка и полное объяснение <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      </div>
    </article>
  );
}
