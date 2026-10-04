import { Briefcase, MapPin, Send } from "lucide-react";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ExplanationList } from "@/components/ExplanationList";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { ScoreBadge } from "@/components/ScoreBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { WORK_FORMAT_LABELS } from "@/lib/labels";
// MOCK: заменить на GET /vacancies?match=true
import { mockVacancies } from "@/mocks/candidate";

export default function CandidateVacanciesPage() {
  return (
    <>
      <PageHeader
        eyebrow="Вакансии"
        title="Вакансии"
        description="Классический путь: откликайтесь сами. Сначала показываем вакансии под вашу категорию — с тем же объяснением совпадения, что видит работодатель."
      />
      {mockVacancies.length === 0 ? (
        <EmptyState icon={Briefcase} title="Подходящих вакансий нет" description="Загляните позже — список обновляется." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {mockVacancies.map((vacancy) => (
            <Card key={vacancy.id}>
              <CardHeader className="grid-cols-[1fr_auto]">
                <div className="space-y-2">
                  <CardTitle className="text-lg">{vacancy.title}</CardTitle>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                    <span>{vacancy.company}</span>
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="size-3.5" aria-hidden />
                      {vacancy.city} · {WORK_FORMAT_LABELS[vacancy.format]}
                    </span>
                  </div>
                </div>
                <ScoreBadge score={vacancy.score} className="row-span-2" />
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap items-center gap-3">
                  <CategoryBadge specialization={vacancy.specialization} grade={vacancy.grade} />
                  <SalaryRange from={vacancy.salaryFrom} to={vacancy.salaryTo} />
                </div>
                <ExplanationList items={vacancy.explanation} />
              </CardContent>
              <CardFooter className="border-t border-border-subtle pt-5">
                {/* TODO: POST /vacancies/{id}/apply с сопроводительным текстом */}
                <Button onClick={() => console.info("[vacancies] TODO: apply", vacancy.id)}>
                  <Send /> Откликнуться
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
