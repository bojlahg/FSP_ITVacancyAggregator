import { Clock, Loader2, MapPin, Pin, PinOff, ShieldCheck, Trophy } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { ExplanationList, type ExplanationLine } from "@/components/ExplanationList";
import { ScoreBadge } from "@/components/ScoreBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CandidateBrief } from "@/lib/employer-queries";
import { daysSince, formatDaysAgo, formatNumber, toPercent } from "@/lib/format";
import { workFormatsLabel } from "@/lib/labels";
import { useSkillCatalog } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

const MAX_SKILLS = 6;

interface CandidateRowProps {
  candidate: CandidateBrief;
  /** Ссылка на карточку кандидата. */
  href: string;
  /** match-score с потребностью; без потребности (поиск) — не показывается. */
  score?: number;
  explanation?: ExplanationLine[];
  /** Верхняя граница вилки потребности — для пометки «ожидания выше вилки». */
  salaryTo?: number;
  shortlisted?: boolean;
  shortlistPending?: boolean;
  onToggleShortlist?: () => void;
  /** Сколько строк объяснения показывать (в списке — 2–3 причины). */
  explanationLimit?: number;
  actions?: ReactNode;
  className?: string;
}

function initialsOf(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2);
}

export function CandidateRow({
  candidate,
  href,
  score,
  explanation,
  salaryTo,
  shortlisted = false,
  shortlistPending = false,
  onToggleShortlist,
  explanationLimit = 3,
  actions,
  className,
}: CandidateRowProps) {
  const catalog = useSkillCatalog();
  const skillName = (id: string) => catalog.data?.find((skill) => skill.id === id)?.name ?? id;

  const aboveRange = salaryTo != null && candidate.salary_min != null && candidate.salary_min > salaryTo;
  const verified = candidate.verified_skills.slice(0, MAX_SKILLS);
  const declared = candidate.declared_skills.slice(0, Math.max(0, MAX_SKILLS - verified.length));

  return (
    <article
      className={cn(
        "group rounded-xl border bg-card p-5 transition-shadow hover:shadow-md",
        shortlisted && "border-primary ring-1 ring-primary/30",
        className,
      )}
    >
      <div className="flex gap-4">
        {score != null && <ScoreBadge score={score} size="lg" className="hidden sm:inline-flex" />}
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              {score != null && <ScoreBadge score={score} className="sm:hidden" />}
              <div
                className="hidden size-10 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-sm font-bold sm:flex"
                aria-hidden
              >
                {initialsOf(candidate.display_name)}
              </div>
              <div className="space-y-1">
                <Link to={href} className="font-mono text-base font-bold hover:text-primary hover:underline">
                  {candidate.display_name}
                </Link>
                <div className="flex flex-wrap items-center gap-2">
                  <CategoryBadge specialization={candidate.category.specialization} grade={candidate.category.grade} />
                  {candidate.percentile != null && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {toPercent(candidate.percentile)}-й перцентиль в категории
                    </span>
                  )}
                </div>
              </div>
            </div>
            {onToggleShortlist && (
              <Button
                variant={shortlisted ? "default" : "outline"}
                size="sm"
                onClick={onToggleShortlist}
                disabled={shortlistPending}
                aria-pressed={shortlisted}
              >
                {shortlistPending ? <Loader2 className="animate-spin" /> : shortlisted ? <PinOff /> : <Pin />}
                {shortlisted ? "В шорт-листе" : "В шорт-лист"}
              </Button>
            )}
          </div>

          <div className="flex flex-wrap gap-1.5">
            {candidate.fsp.has_fsp && (
              <Badge variant="default" title={`Достижений ФСП: ${candidate.fsp.achievements_count}`}>
                <Trophy /> ФСП{candidate.fsp.max_rank ? ` · ${candidate.fsp.max_rank}` : ""}
              </Badge>
            )}
            {candidate.verified_skills.length > 0 && (
              <Badge variant="soft">
                <ShieldCheck /> проверено тестом
              </Badge>
            )}
            {candidate.last_activity_at && (
              <Badge variant="muted" title="Последний тест или задание">
                <Clock /> {formatDaysAgo(daysSince(candidate.last_activity_at))}
              </Badge>
            )}
            <Badge variant="muted">
              <MapPin /> {candidate.city ?? "город не указан"} · {workFormatsLabel(candidate.work_formats)}
              {candidate.relocation && " · релокация"}
            </Badge>
            <Badge variant={aboveRange ? "destructive" : "muted"}>
              {candidate.salary_min == null
                ? "ожидания скрыты"
                : `от ${formatNumber(candidate.salary_min)} ₽${aboveRange ? " · выше вилки" : ""}`}
            </Badge>
          </div>

          {(verified.length > 0 || declared.length > 0) && (
            <div className="flex flex-wrap gap-1.5 text-xs">
              {verified.map((id) => (
                <span key={id} className="rounded-md bg-primary-tint px-2 py-0.5 font-mono text-primary" title="Проверено тестом">
                  {skillName(id)}
                </span>
              ))}
              {declared.map((id) => (
                <span key={id} className="rounded-md border px-2 py-0.5 font-mono text-muted-foreground" title="Заявлено">
                  {skillName(id)}
                </span>
              ))}
            </div>
          )}

          {explanation && explanation.length > 0 && <ExplanationList items={explanation} limit={explanationLimit} />}

          {actions && <div className="flex flex-wrap gap-2 pt-1">{actions}</div>}
        </div>
      </div>
    </article>
  );
}
