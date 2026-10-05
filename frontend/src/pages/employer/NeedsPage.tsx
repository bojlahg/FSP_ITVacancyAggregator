import { ArrowRight, Pin, Plus, Target } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import { useIndustries, useNeeds } from "@/lib/employer-queries";
import { formatDate } from "@/lib/format";
import { NEED_STATUS_LABELS, WORK_FORMAT_LABELS } from "@/lib/labels";

export default function NeedsPage() {
  const needs = useNeeds();
  const industries = useIndustries();
  const industryName = (slug: string) => industries.data?.find((item) => item.slug === slug)?.name ?? slug;

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

      {needs.isPending ? (
        <SkeletonCards count={3} className="lg:grid-cols-2 2xl:grid-cols-3" />
      ) : needs.isError ? (
        <ErrorState description={apiError(needs.error).message} onRetry={() => void needs.refetch()} />
      ) : needs.data.length === 0 ? (
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
          {needs.data.map((need) => {
            const { invitations_active: active, invitations_limit: limit, shortlisted } = need.stats;
            const meta = [
              need.industry ? industryName(need.industry) : null,
              need.work_format ? WORK_FORMAT_LABELS[need.work_format] : null,
              need.city,
            ].filter(Boolean);
            return (
              <Card key={need.id}>
                <CardHeader>
                  <div className="flex flex-wrap items-center gap-2">
                    <CategoryBadge specialization={need.specialization} grade={need.grade} />
                    {need.published && <Badge variant="outline">вакансия</Badge>}
                    {need.status !== "active" && <Badge variant="muted">{NEED_STATUS_LABELS[need.status]}</Badge>}
                    <Badge variant="muted">v{need.version}</Badge>
                  </div>
                  <CardTitle className="mt-2 text-lg">{need.title}</CardTitle>
                  <CardDescription>
                    {meta.length > 0 && `${meta.join(" · ")} · `}создана {formatDate(need.created_at)}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <SalaryRange from={need.salary_from} to={need.salary_to} className="text-lg" />
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="flex items-center gap-2">
                      <Pin className="size-4 text-primary" aria-hidden />
                      <span>
                        <b className="font-mono">{shortlisted}</b> в шорт-листе
                      </span>
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-muted-foreground">
                        Приглашения <span className="font-mono">{active} / {limit}</span>
                      </div>
                      <Progress value={limit > 0 ? (active / limit) * 100 : 0} className="h-1.5" aria-label="Использовано приглашений" />
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
            );
          })}
        </div>
      )}
    </>
  );
}
