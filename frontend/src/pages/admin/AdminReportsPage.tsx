import { Flag, Loader2 } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  type ReportForAdmin,
  type ReportStatus,
  useInvitationReports,
  useResolveReport,
} from "@/lib/admin-queries";
import { apiError } from "@/lib/api-error";
import { formatDate } from "@/lib/format";

const REASON_LABELS: Record<ReportForAdmin["reason"], string> = {
  scam: "мошенничество",
  discrimination: "дискриминация",
  fake_company: "компания не та",
  spam: "спам",
  other: "другое",
};

const FILTERS: { value: ReportStatus | null; label: string }[] = [
  { value: "open", label: "Открытые" },
  { value: "resolved", label: "Рассмотренные" },
  { value: null, label: "Все" },
];

export default function AdminReportsPage() {
  const [status, setStatus] = useState<ReportStatus | null>("open");
  const reports = useInvitationReports(status);

  return (
    <>
      <PageHeader
        eyebrow="Модерация"
        title="Жалобы на приглашения"
        description="Кандидаты жалуются на мошенничество, дискриминацию и спам. Автоматически ничего не блокируется: решение и меры — за администратором."
      />
      <div
        className="mb-4 flex flex-wrap gap-2"
        role="group"
        aria-label="Фильтр по статусу"
      >
        {FILTERS.map((filter) => (
          <Button
            key={filter.label}
            size="sm"
            variant={status === filter.value ? "default" : "outline"}
            aria-pressed={status === filter.value}
            onClick={() => setStatus(filter.value)}
          >
            {filter.label}
          </Button>
        ))}
      </div>
      {reports.isPending ? (
        <SkeletonCards count={2} />
      ) : reports.isError ? (
        <ErrorState
          description={apiError(reports.error).message}
          onRetry={() => void reports.refetch()}
        />
      ) : reports.data.length === 0 ? (
        <EmptyState
          icon={Flag}
          title="Жалоб нет"
          description="Новые жалобы кандидатов появятся здесь."
        />
      ) : (
        <div className="grid gap-4">
          {reports.data.map((report) => (
            <ReportCard key={report.id} report={report} />
          ))}
        </div>
      )}
    </>
  );
}

function ReportCard({ report }: { report: ReportForAdmin }) {
  const resolve = useResolveReport();
  const [resolution, setResolution] = useState("");
  const open = report.status === "open";
  const inputId = `resolution-${report.id}`;

  return (
    <Card className="gap-4">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <Badge variant={open ? "destructive" : "muted"}>
            {open ? "открыта" : "рассмотрена"}
          </Badge>
          {REASON_LABELS[report.reason]} ·{" "}
          {report.company_name ?? `работодатель #${report.employer_id}`}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Жалоба от {formatDate(report.created_at)} на приглашение #
          {report.invitation_id}
        </p>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        {report.comment && (
          <p>
            <span className="font-medium">Кандидат:</span> {report.comment}
          </p>
        )}
        <div className="rounded-lg bg-muted/60 p-3">
          <div className="mb-1 font-medium">«{report.invitation_title}»</div>
          <p className="whitespace-pre-line text-muted-foreground">
            {report.invitation_message}
          </p>
        </div>
        {report.warnings.length > 0 && (
          <ul className="grid gap-1">
            {report.warnings.map((warning) => (
              <li key={warning.rule}>
                <span className="font-mono text-xs">«{warning.fragment}»</span>{" "}
                <span className="text-muted-foreground">— {warning.label}</span>
              </li>
            ))}
          </ul>
        )}
        {!open && report.resolution && (
          <p>
            <span className="font-medium">
              Решение
              {report.resolved_at ? ` (${formatDate(report.resolved_at)})` : ""}
              :
            </span>{" "}
            {report.resolution}
          </p>
        )}
      </CardContent>
      {open && (
        <CardFooter
          className="grid gap-2 border-t border-border-subtle pt-4"
        >
          <label htmlFor={inputId} className="text-sm font-medium">
            Что сделано
          </label>
          <Textarea
            id={inputId}
            rows={2}
            value={resolution}
            onChange={(event) => setResolution(event.target.value)}
            placeholder="Например: работодатель предупреждён, вакансия снята"
          />
          <FormAlert
            message={resolve.isError ? apiError(resolve.error).message : null}
          />
          <div>
            <Button
              size="sm"
              disabled={resolve.isPending || resolution.trim().length === 0}
              onClick={() =>
                resolve.mutate({
                  reportId: report.id,
                  resolution: resolution.trim(),
                })
              }
            >
              {resolve.isPending && <Loader2 className="animate-spin" />}{" "}
              Закрыть жалобу
            </Button>
          </div>
        </CardFooter>
      )}
    </Card>
  );
}
