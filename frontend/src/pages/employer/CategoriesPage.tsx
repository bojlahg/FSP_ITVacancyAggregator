import { Link } from "react-router";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { GRADE_LABELS, SPECIALIZATION_FULL_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
// MOCK: заменить на GET /talent/categories
import { mockCategoryCatalog } from "@/mocks/talent";

const grades = Object.keys(GRADE_LABELS);
const maxCount = Math.max(...Object.values(mockCategoryCatalog).flatMap((row) => Object.values(row)));

export default function CategoriesPage() {
  return (
    <>
      <PageHeader
        eyebrow="Каталог категорий"
        title="Каталог категорий"
        description="Все кандидаты разложены по категориям «специализация × грейд». Категорию определяет только тест, поэтому внутри неё кандидаты сопоставимы."
      />
      <Card>
        <CardHeader>
          <CardTitle>Кандидаты по категориям</CardTitle>
          <CardDescription>Число кандидатов с действующей категорией и согласием на публикацию</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-separate border-spacing-1.5 text-sm">
            <thead>
              <tr>
                <th className="text-left font-mono text-xs font-medium text-muted-foreground uppercase">
                  Специализация
                </th>
                {grades.map((grade) => (
                  <th key={grade} className="font-mono text-xs font-medium text-muted-foreground uppercase">
                    {GRADE_LABELS[grade]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(mockCategoryCatalog).map(([specialization, row]) => (
                <tr key={specialization}>
                  <th scope="row" className="pr-3 text-left font-medium whitespace-nowrap">
                    {SPECIALIZATION_FULL_LABELS[specialization]}
                  </th>
                  {grades.map((grade) => {
                    const count = row[grade] ?? 0;
                    const strong = count / maxCount > 0.5;
                    return (
                      <td key={grade} className="p-0">
                        <Link
                          to={`/employer/search?spec=${specialization}&grade=${grade}`}
                          className={cn(
                            "flex h-14 flex-col items-center justify-center rounded-lg font-mono transition-shadow hover:shadow-md hover:ring-1 hover:ring-primary",
                            strong ? "bg-primary text-primary-foreground" : count > 0 ? "bg-primary-tint text-primary" : "bg-muted text-muted-foreground",
                          )}
                        >
                          <span className="text-lg font-extrabold tabular-nums">{count}</span>
                        </Link>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-4 text-xs text-muted-foreground">
            Скоро: Fullstack, Mobile, аналитика и GameDev — направления есть в справочнике, тесты появятся после MVP.
          </p>
        </CardContent>
      </Card>
    </>
  );
}
