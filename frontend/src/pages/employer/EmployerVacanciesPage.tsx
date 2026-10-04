import { Briefcase, Send } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
// MOCK: вакансия = потребность с published=true; отклики — GET /needs/{id}/applications
import { mockNeeds } from "@/mocks/talent";

const mockApplicationsCount: Record<string, number> = {
  "need-backend-payments": 6,
  "need-devops-platform": 2,
};

export default function EmployerVacanciesPage() {
  const vacancies = mockNeeds.filter((need) => need.published);

  return (
    <>
      <PageHeader
        eyebrow="Вакансии и отклики"
        title="Вакансии и отклики"
        description="Вакансия — это опубликованная потребность. Отклик сразу открывает контакты кандидата; отклики отсортированы по тому же score, что и подборка."
      />
      {vacancies.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="Опубликованных вакансий нет"
          description="Опубликуйте любую потребность — она появится в списке вакансий у кандидатов."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {vacancies.map((vacancy) => (
            <Card key={vacancy.id}>
              <CardHeader>
                <CategoryBadge specialization={vacancy.specialization} grade={vacancy.grade} />
                <CardTitle className="mt-2 text-lg">{vacancy.title}</CardTitle>
                <CardDescription>
                  <SalaryRange from={vacancy.salaryFrom} to={vacancy.salaryTo} className="text-foreground" />
                </CardDescription>
              </CardHeader>
              <CardContent className="flex items-center gap-2 text-sm">
                <Send className="size-4 text-primary" aria-hidden />
                Откликов: <b className="font-mono">{mockApplicationsCount[vacancy.id] ?? 0}</b>
                <Badge variant="soft" className="ml-2">
                  новые: 2
                </Badge>
              </CardContent>
              <CardFooter className="gap-2 border-t border-border-subtle pt-5">
                <Button variant="outline" size="sm">
                  Отклики
                </Button>
                <Button asChild variant="ghost" size="sm">
                  <Link to={`/employer/needs/${vacancy.id}`}>Подборка</Link>
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
