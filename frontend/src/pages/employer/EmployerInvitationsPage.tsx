import { Mail } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { formatDaysAgo } from "@/lib/format";
// MOCK: заменить на GET /employers/me/invitations и /employers/me/decline-stats
import { mockDeclineStats, mockEmployerInvitations } from "@/mocks/talent";

export default function EmployerInvitationsPage() {
  const declinedTotal = mockDeclineStats.reduce((sum, item) => sum + item.count, 0);

  return (
    <>
      <PageHeader
        eyebrow="Приглашения"
        title="Приглашения"
        description="Статусы всех отправленных приглашений и агрегат причин отказов — чтобы понимать, что поправить в предложении."
      />

      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <Card className="py-0">
          <CardContent className="overflow-x-auto px-0">
            {mockEmployerInvitations.length === 0 ? (
              <EmptyState
                icon={Mail}
                title="Вы ещё никого не пригласили"
                description="Откройте подборку по потребности и пригласите подходящих кандидатов."
                className="m-5"
              />
            ) : (
              <table className="w-full min-w-[640px] text-sm">
                <thead className="border-b border-border-subtle">
                  <tr className="text-left font-mono text-xs text-muted-foreground uppercase">
                    <th className="px-5 py-3 font-medium">Кандидат</th>
                    <th className="px-3 py-3 font-medium">Потребность</th>
                    <th className="px-3 py-3 font-medium">Вилка</th>
                    <th className="px-3 py-3 font-medium">Статус</th>
                    <th className="px-5 py-3 text-right font-medium">Отправлено</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {mockEmployerInvitations.map((invitation) => (
                    <tr key={invitation.id}>
                      <td className="px-5 py-3">
                        <Link
                          to={`/employer/candidates/${invitation.candidateId}`}
                          className="font-mono font-bold hover:text-primary"
                        >
                          {invitation.candidateName}
                        </Link>
                        <div className="mt-1">
                          <CategoryBadge specialization={invitation.specialization} grade={invitation.grade} />
                        </div>
                      </td>
                      <td className="max-w-56 px-3 py-3 text-muted-foreground">{invitation.needTitle}</td>
                      <td className="px-3 py-3">
                        <SalaryRange from={invitation.salaryFrom} to={invitation.salaryTo} />
                      </td>
                      <td className="px-3 py-3">
                        <StatusBadge status={invitation.status} />
                        {invitation.declineReason && (
                          <div className="mt-1 text-xs text-muted-foreground">{invitation.declineReason}</div>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right text-muted-foreground">
                        {formatDaysAgo(invitation.sentDaysAgo)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Причины отказов</CardTitle>
            <CardDescription>
              {declinedTotal > 0 && mockDeclineStats[0]
                ? `${mockDeclineStats[0].count} из ${declinedTotal} отказов — ${mockDeclineStats[0].reason.toLowerCase()}`
                : "Отказов пока нет"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {mockDeclineStats.map((item) => (
              <div key={item.reason} className="space-y-1.5">
                <div className="flex justify-between text-sm">
                  <span>{item.reason}</span>
                  <span className="font-mono font-bold">{item.count}</span>
                </div>
                <Progress value={(item.count / declinedTotal) * 100} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
