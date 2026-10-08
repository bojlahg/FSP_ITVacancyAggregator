import { Wallet } from "lucide-react";
import { ErrorState } from "@/components/ErrorState";
import { SalaryMarketNote } from "@/components/SalaryMarketNote";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import { type Need, useSalaryCoverage } from "@/lib/employer-queries";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const compact = (value: number) => `${Math.round(value / 1000)}k`;

/**
 * Ожидания кандидатов категории потребности (§8.6 п.1): гистограмма против вилки и рынок.
 * Само покрытие вилки — в сводке потребности; здесь распределение, из которого оно посчитано.
 */
export function SalaryCoverageCard({ need, className }: { need: Need; className?: string }) {
  const coverage = useSalaryCoverage(need.id);

  return (
    <section
      aria-labelledby="category-expectations"
      className={cn("flex flex-col gap-3 rounded-[10px] border bg-card p-5", className)}
    >
      <h3 id="category-expectations" className="flex items-center gap-2 font-mono text-base font-semibold tracking-tight">
        <Wallet className="size-4 text-primary" aria-hidden /> Ожидания категории
      </h3>
      <p className="text-xs text-muted-foreground">Кандидаты {need.category.label} по ожиданиям, ₽ на руки</p>
      {coverage.isPending ? (
        <div className="grid gap-3" role="status" aria-busy="true" aria-label="Загрузка">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ) : coverage.isError ? (
        <ErrorState
          className="py-6"
          title="Не удалось построить распределение"
          description={apiError(coverage.error).message}
          onRetry={() => void coverage.refetch()}
        />
      ) : (
        <>
          {coverage.data.histogram.length === 0 ? (
            <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
              В категории пока нет кандидатов с указанными ожиданиями.
            </p>
          ) : (
            <Histogram histogram={coverage.data.histogram} salaryTo={need.salary_to} />
          )}
          <SalaryMarketNote market={coverage.data.market} />
        </>
      )}
    </section>
  );
}

interface HistogramProps {
  histogram: { salary_from: number; salary_to: number; count: number }[];
  salaryTo: number;
}

function Histogram({ histogram, salaryTo }: HistogramProps) {
  const maxCount = Math.max(1, ...histogram.map((bucket) => bucket.count));
  const inRange = histogram.filter((bucket) => bucket.salary_to <= salaryTo).map((bucket) => bucket.count);
  const above = histogram.filter((bucket) => bucket.salary_to > salaryTo).map((bucket) => bucket.count);
  return (
    <figure className="grid gap-2">
      <div
        className="flex h-28 items-end gap-1 pt-4"
        role="img"
        aria-label={`Гистограмма ожиданий: в пределах вилки ${inRange.join(", ") || "0"}; выше вилки ${above.join(", ") || "0"} кандидатов`}
      >
        {histogram.map((bucket) => {
          const covered = bucket.salary_to <= salaryTo;
          const partial = !covered && bucket.salary_from < salaryTo;
          return (
            <div
              key={`${bucket.salary_from}-${bucket.salary_to}`}
              className="relative flex h-full flex-1 flex-col justify-end"
              title={`${formatNumber(bucket.salary_from)} – ${formatNumber(bucket.salary_to)} ₽: ${bucket.count}`}
            >
              <span className="mb-0.5 text-center font-mono text-[10px] text-muted-foreground tabular-nums">
                {bucket.count > 0 ? bucket.count : ""}
              </span>
              <div
                className={cn("w-full rounded-t-sm", covered ? "bg-primary" : partial ? "bg-primary-pale" : "bg-border")}
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
  );
}
