import { ArrowRight, Plus, Target, Users } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { formatDaysAgo } from "@/lib/format";
import { WORK_FORMAT_LABELS } from "@/lib/labels";
// MOCK: заменить на GET /needs
import { MOCK_MAX_ACTIVE_INVITES_PER_NEED, mockNeeds } from "@/mocks/talent";

export default function NeedsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Потребности"
        title="Потребности"
        description="Потребность — приватный запрос на подбор, а не публичная вакансия. По каждой строится подборка кандидатов; её можно опубликовать как вакансию."
        actions={
          <Button asChild>
            <Link to="/employer/needs/new">
              <Plus /> Новая потребность
            </Link>
          </Button>
        }
      />

      {mockNeeds.length === 0 ? (
        <EmptyState
          icon={Target}
          title="Потребностей пока нет"
          description="Опишите, кого ищете, — текстом или формой. Мы разберём запрос и соберём подборку."
          action={
            <Button asChild>
              <Link to="/employer/needs/new">Создать потребность</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
          {mockNeeds.map((need) => (
            <Card key={need.id}>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-2">
                  <CategoryBadge specialization={need.specialization} grade={need.grade} />
                  {need.published && <Badge variant="outline">вакансия</Badge>}
                  <Badge variant="muted">v{need.version}</Badge>
                </div>
                <CardTitle className="mt-2 text-lg">{need.title}</CardTitle>
                <CardDescription>
                  {need.industry} · {WORK_FORMAT_LABELS[need.format]} · {need.city} · обновлена{" "}
                  {formatDaysAgo(need.updatedDaysAgo)}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <SalaryRange from={need.salaryFrom} to={need.salaryTo} className="text-lg" />
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <Users className="size-4 text-primary" aria-hidden />
                    <span>
                      <b className="font-mono">{need.candidatesCount}</b> в подборке
                    </span>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground">
                      Приглашения {need.activeInvites} / {MOCK_MAX_ACTIVE_INVITES_PER_NEED}
                    </div>
                    <Progress value={(need.activeInvites / MOCK_MAX_ACTIVE_INVITES_PER_NEED) * 100} className="h-1.5" />
                  </div>
                </div>
              </CardContent>
              <CardFooter className="mt-auto border-t border-border-subtle pt-5">
                <Button asChild variant="outline" className="w-full">
                  <Link to={`/employer/needs/${need.id}`}>
                    Открыть подборку <ArrowRight />
                  </Link>
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
