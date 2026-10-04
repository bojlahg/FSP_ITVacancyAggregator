import { Clock, MapPin, Pin, PinOff, ShieldCheck, Trophy } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { ExplanationList, type ExplanationLine } from "@/components/ExplanationList";
import { ScoreBadge } from "@/components/ScoreBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDaysAgo, formatNumber } from "@/lib/format";
import { WORK_FORMAT_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

export interface CandidateRowData {
  id: string;
  displayName: string;
  specialization: string;
  grade: string;
  score: number;
  percentile: number;
  hasFsp: boolean;
  testVerified: boolean;
  freshDays: number;
  salaryMin: number;
  city: string;
  format: keyof typeof WORK_FORMAT_LABELS;
  explanation: ExplanationLine[];
}

interface CandidateRowProps {
  candidate: CandidateRowData;
  /** Верхняя граница вилки потребности — для пометки «ожидания выше вилки». */
  salaryTo?: number;
  shortlisted?: boolean;
  onToggleShortlist?: (id: string) => void;
  /** Сколько строк объяснения показывать (в списке — 2–3 причины). */
  explanationLimit?: number;
  actions?: ReactNode;
  className?: string;
}

export function CandidateRow({
  candidate,
  salaryTo,
  shortlisted = false,
  onToggleShortlist,
  explanationLimit = 4,
  actions,
  className,
}: CandidateRowProps) {
  const aboveRange = salaryTo != null && candidate.salaryMin > salaryTo;
  const initials = candidate.displayName
    .split(" ")
    .map((part) => part[0])
    .join("");

  return (
    <article
      className={cn(
        "group rounded-xl border bg-card p-5 transition-shadow hover:shadow-md",
        shortlisted && "border-primary ring-1 ring-primary/30",
        className,
      )}
    >
      <div className="flex gap-4">
        <ScoreBadge score={candidate.score} size="lg" className="hidden sm:inline-flex" />
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <ScoreBadge score={candidate.score} className="sm:hidden" />
              <div
                className="hidden size-10 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-sm font-bold sm:flex"
                aria-hidden
              >
                {initials}
              </div>
              <div className="space-y-1">
                <Link
                  to={`/employer/candidates/${candidate.id}`}
                  className="font-mono text-base font-bold hover:text-primary hover:underline"
                >
                  {candidate.displayName}
                </Link>
                <div className="flex flex-wrap items-center gap-2">
                  <CategoryBadge specialization={candidate.specialization} grade={candidate.grade} />
                  <span className="font-mono text-xs text-muted-foreground">{candidate.percentile}-й перцентиль</span>
                </div>
              </div>
            </div>
            {onToggleShortlist && (
              <Button
                variant={shortlisted ? "default" : "outline"}
                size="sm"
                onClick={() => onToggleShortlist(candidate.id)}
                aria-pressed={shortlisted}
              >
                {shortlisted ? <PinOff /> : <Pin />}
                {shortlisted ? "В шорт-листе" : "В шорт-лист"}
              </Button>
            )}
          </div>

          <div className="flex flex-wrap gap-1.5">
            {candidate.hasFsp && (
              <Badge variant="default">
                <Trophy /> ФСП
              </Badge>
            )}
            {candidate.testVerified && (
              <Badge variant="soft">
                <ShieldCheck /> проверено тестом
              </Badge>
            )}
            <Badge variant="muted">
              <Clock /> {formatDaysAgo(candidate.freshDays)}
            </Badge>
            <Badge variant="muted">
              <MapPin /> {candidate.city} · {WORK_FORMAT_LABELS[candidate.format]}
            </Badge>
            <Badge variant={aboveRange ? "destructive" : "muted"}>
              от {formatNumber(candidate.salaryMin)} ₽{aboveRange && " · выше вилки"}
            </Badge>
          </div>

          <ExplanationList items={candidate.explanation} limit={explanationLimit} />

          {actions && <div className="flex flex-wrap gap-2 pt-1">{actions}</div>}
        </div>
      </div>
    </article>
  );
}
