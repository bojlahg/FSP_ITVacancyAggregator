import { Building2, ChevronDown, Send } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ExplanationList } from "@/components/ExplanationList";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { ScoreBadge } from "@/components/ScoreBadge";
import { SkeletonCards } from "@/components/SkeletonCards";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { apiError } from "@/lib/api-error";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { type ApplicationForCandidate, useMyApplications } from "@/lib/vacancy-queries";

const STATUS_HINTS: Record<ApplicationForCandidate["status"], string> = {
  sent: "Работодатель ещё не открывал отклик.",
  viewed: "Работодатель посмотрел отклик и ваши контакты.",
  accepted: "Работодатель готов продолжить — ждите связи по вашим контактам.",
  rejected: "Работодатель решил не продолжать.",
};

export default function ApplicationsPage() {
  const applications = useMyApplications();
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggle = (id: number) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <>
      <PageHeader
        eyebrow="Отклики"
        title="Мои отклики"
        description="Отклик сразу открывает работодателю ваши контакты. Здесь видно, на каком этапе каждый отклик."
      />
      {applications.isPending ? (
        <SkeletonCards count={3} />
      ) : applications.isError ? (
        <ErrorState description={apiError(applications.error).message} onRetry={() => void applications.refetch()} />
      ) : applications.data.length === 0 ? (
        <EmptyState
          icon={Send}
          title="Вы ещё не откликались"
          description="Найдите подходящую вакансию в разделе «Вакансии»."
          action={
            <Button asChild variant="outline">
              <Link to="/candidate/vacancies">К вакансиям</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3">
          {applications.data.map((application) => (
            <ApplicationCard
              key={application.id}
              application={application}
              open={expanded.has(application.id)}
              onToggle={() => toggle(application.id)}
            />
          ))}
        </div>
      )}
    </>
  );
}

interface ApplicationCardProps {
  application: ApplicationForCandidate;
  open: boolean;
  onToggle: () => void;
}

function ApplicationCard({ application, open, onToggle }: ApplicationCardProps) {
  const { vacancy } = application;
  const lines = vacancy.match_explanation?.lines ?? [];
  const detailsId = `application-${application.id}`;

  return (
    <Card className="gap-4">
      <CardHeader>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls={detailsId}
          className="grid w-full gap-3 rounded-md text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 md:grid-cols-[minmax(0,1fr)_auto]"
        >
          <span className="min-w-0 space-y-1.5">
            <span className="flex flex-wrap items-center gap-2">
              <StatusBadge status={application.status} />
              <CategoryBadge specialization={vacancy.category.specialization} grade={vacancy.category.grade} />
            </span>
            <span className="block font-mono text-lg leading-tight font-bold">{vacancy.title}</span>
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
                <Building2 className="size-3.5" aria-hidden /> {vacancy.company.company_name}
              </span>
              <span>отклик {formatDate(application.created_at)}</span>
              {application.responded_at && <span>ответ {formatDate(application.responded_at)}</span>}
            </span>
          </span>
          <span className="flex items-center gap-3 md:flex-col md:items-end">
            <SalaryRange from={vacancy.salary_from} to={vacancy.salary_to} className="text-lg text-primary" />
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              {open ? "Свернуть" : "Подробнее"}
              <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} aria-hidden />
            </span>
          </span>
        </button>
      </CardHeader>

      {open && (
        <CardContent id={detailsId} className="grid gap-5 md:grid-cols-2">
          <div className="space-y-3 text-sm">
            <p className="text-muted-foreground">{STATUS_HINTS[application.status]}</p>
            <div className="space-y-1">
              <div className="font-mono text-xs font-bold tracking-wider uppercase">Ваш сопроводительный текст</div>
              {application.cover_note ? (
                <p className="leading-relaxed whitespace-pre-line">{application.cover_note}</p>
              ) : (
                <p className="text-muted-foreground">Без сопроводительного текста.</p>
              )}
            </div>
          </div>
          <div className="h-fit rounded-lg bg-muted/60 p-4">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="font-mono text-xs font-bold tracking-wider uppercase">Почему вы</span>
              {vacancy.match_score !== null && vacancy.match_score !== undefined && (
                <ScoreBadge score={vacancy.match_score} size="sm" />
              )}
            </div>
            {lines.length === 0 ? (
              <p className="text-sm text-muted-foreground">Объяснение совпадения не сохранилось.</p>
            ) : (
              <ExplanationList items={lines} />
            )}
            <p className="mt-3 text-xs text-muted-foreground">
              Снимок на момент отклика — именно его видит работодатель.
            </p>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
