import { Wallet } from "lucide-react";
import { ErrorState } from "@/components/ErrorState";
import { SalaryRange } from "@/components/SalaryRange";
import { SalaryMarketNote } from "@/components/SalaryMarketNote";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import { type Need, useSalaryCoverage } from "@/lib/employer-queries";
import { formatNumber, toPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

const compact = (value: number) => `${Math.round(value / 1000)}k`;

/** Покрытие вилки: доля кандидатов категории с ожиданиями ≤ верхней границы (§8.6 п.1) и гистограмма ожиданий. */
export function SalaryCoverageCard({ need }: { need: Need }) {
  const coverage = useSalaryCoverage(need.id);

  return (
    <Card className="gap-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wallet className="size-4 text-primary" aria-hidden /> Покрытие вилки
        </CardTitle>
        <CardDescription>
          Вилка <SalaryRange from={need.salary_from} to={need.salary_to} className="text-foreground" /> против ожиданий
          кандидатов {need.category.label}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {coverage.isPending ? (
          <div className="grid gap-3" aria-busy="true" aria-label="Загрузка">
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : coverage.isError ? (
          <ErrorState
            className="py-6"
            title="Не удалось посчитать покрытие"
            description={apiError(coverage.error).message}
            onRetry={() => void coverage.refetch()}
          />
        ) : (
          <>
            <CoverageBody
              coverage={coverage.data.coverage}
              median={coverage.data.median_expectation}
              histogram={coverage.data.histogram}
              salaryTo={need.salary_to}
            />
            <SalaryMarketNote market={coverage.data.market} className="mt-4" />
          </>
        )}
      </CardContent>
    </Card>
  );
}

interface CoverageBodyProps {
  coverage: number;
  median: number | null;
  histogram: { salary_from: number; salary_to: number; count: number }[];
  salaryTo: number;
}

function CoverageBody({ coverage, median, histogram, salaryTo }: CoverageBodyProps) {
  const percent = toPercent(coverage);
  const maxCount = Math.max(1, ...histogram.map((bucket) => bucket.count));
  return (
    <div className="grid gap-4">
      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm">
            покрывает ожидания <b className="font-mono text-2xl font-extrabold text-primary tabular-nums">{percent}%</b>{" "}
            кандидатов
          </span>
          {median !== null && (
            <span className="text-right text-xs text-muted-foreground">
              медиана ожиданий <b className="font-mono text-foreground">{formatNumber(median)} ₽</b>
            </span>
          )}
        </div>
        <Progress value={percent} aria-label="Покрытие вилки" />
      </div>

      {histogram.length > 0 && (
        <figure className="grid gap-2">
          <div className="flex h-28 items-end gap-1" role="img" aria-label="Распределение зарплатных ожиданий">
            {histogram.map((bucket) => {
              const covered = bucket.salary_to <= salaryTo;
              const partial = !covered && bucket.salary_from < salaryTo;
              return (
                <div
                  key={`${bucket.salary_from}-${bucket.salary_to}`}
                  className="group relative flex h-full flex-1 flex-col justify-end"
                  title={`${formatNumber(bucket.salary_from)} – ${formatNumber(bucket.salary_to)} ₽: ${bucket.count}`}
                >
                  <span className="mb-0.5 text-center font-mono text-[10px] text-muted-foreground tabular-nums">
                    {bucket.count > 0 ? bucket.count : ""}
                  </span>
                  <div
                    className={cn(
                      "w-full rounded-t-sm",
                      covered ? "bg-primary" : partial ? "bg-primary-pale" : "bg-border",
                    )}
                    style={{ height: `${Math.max(2, (bucket.count / maxCount) * 100)}%` }}
                  />
                </div>
              );
            })}
          </div>
          <div className="flex justify-between font-mono text-[10px] text-muted-foreground tabular-nums">
            <span>{compact(histogram[0]!.salary_from)}</span>
            <span>{compact(histogram[histogram.length - 1]!.salary_to)} ₽</span>
          </div>
          <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-primary" aria-hidden /> в пределах вилки
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-border" aria-hidden /> выше вилки
            </span>
          </figcaption>
        </figure>
      )}
    </div>
  );
}
