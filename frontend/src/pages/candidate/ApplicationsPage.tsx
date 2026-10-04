import { Send } from "lucide-react";
import { Link } from "react-router";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatDaysAgo } from "@/lib/format";
// MOCK: заменить на GET /candidates/me/applications
import { mockApplications } from "@/mocks/candidate";

export default function ApplicationsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Отклики"
        title="Мои отклики"
        description="Отклик сразу открывает работодателю ваши контакты. Здесь видно, на каком этапе каждый отклик."
      />
      {mockApplications.length === 0 ? (
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
        <Card className="py-0">
          <CardContent className="px-0">
            <ul className="divide-y divide-border-subtle">
              {mockApplications.map((application) => (
                <li key={application.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                  <div className="min-w-0">
                    <div className="font-medium">{application.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {application.company} · {formatDaysAgo(application.sentDaysAgo)}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <SalaryRange from={application.salaryFrom} to={application.salaryTo} className="text-sm" />
                    <StatusBadge status={application.status} />
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  );
}
