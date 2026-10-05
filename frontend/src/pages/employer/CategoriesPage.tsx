import { ArrowRight, Grid3x3, Trophy } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { apiError } from "@/lib/api-error";
import { type CategoryCatalogItem, useTalentCategories } from "@/lib/employer-queries";
import { formatNumber, plural, toPercent } from "@/lib/format";
import { gradeOrder, useGrades, useSpecializations } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

export default function CategoriesPage() {
  const categories = useTalentCategories();
  const specializations = useSpecializations();
  const grades = useGrades();

  const specName = (slug: string) => specializations.data?.find((item) => item.slug === slug)?.name ?? slug;

  // Группы по специализации, внутри — по порядку грейдов.
  const groups = new Map<string, CategoryCatalogItem[]>();
  for (const item of categories.data ?? []) {
    const list = groups.get(item.category.specialization) ?? [];
    list.push(item);
    groups.set(item.category.specialization, list);
  }
  for (const list of groups.values()) {
    list.sort((a, b) => gradeOrder(a.category.grade, grades.data) - gradeOrder(b.category.grade, grades.data));
  }
  const maxCount = Math.max(1, ...(categories.data ?? []).map((item) => item.candidates_count));

  return (
    <>
      <PageHeader
        eyebrow="Каталог категорий"
        title="Каталог категорий"
        description="Все кандидаты разложены по категориям «специализация × грейд». Категорию определяет только тест, поэтому внутри неё кандидаты сопоставимы. Нажмите на категорию, чтобы открыть поиск по ней."
      />

      {categories.isPending ? (
        <SkeletonCards count={4} className="md:grid-cols-2 xl:grid-cols-4" />
      ) : categories.isError ? (
        <ErrorState description={apiError(categories.error).message} onRetry={() => void categories.refetch()} />
      ) : categories.data.length === 0 ? (
        <EmptyState
          icon={Grid3x3}
          title="Каталог пока пуст"
          description="Категории появятся, когда кандидаты пройдут тест и дадут согласие на публикацию профиля."
        />
      ) : (
        <div className="space-y-8">
          {[...groups.entries()].map(([specialization, items]) => (
            <section key={specialization} aria-labelledby={`spec-${specialization}`}>
              <h2 id={`spec-${specialization}`} className="mb-3 text-lg font-extrabold">
                {specName(specialization)}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {items.map((item) => (
                  <CategoryTile key={`${specialization}.${item.category.grade}`} item={item} maxCount={maxCount} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

function CategoryTile({ item, maxCount }: { item: CategoryCatalogItem; maxCount: number }) {
  const { category } = item;
  const strong = item.candidates_count / maxCount > 0.5;
  const empty = item.candidates_count === 0;
  return (
    <Link
      to={`/employer/search?spec=${encodeURIComponent(category.specialization)}&grade=${category.grade}`}
      className={cn(
        "group flex flex-col gap-3 rounded-xl border bg-card p-4 transition-[box-shadow,border-color] outline-none hover:border-primary hover:shadow-md focus-visible:ring-[3px] focus-visible:ring-ring/40",
        strong && "border-primary/60",
        empty && "opacity-70",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <CategoryBadge specialization={category.specialization} grade={category.grade} variant={strong ? "solid" : "soft"} />
        <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" aria-hidden />
      </div>
      <div className="flex items-end gap-5">
        <div>
          <div className="font-mono text-3xl font-extrabold tabular-nums">{item.candidates_count}</div>
          <div className="text-xs text-muted-foreground">
            {plural(item.candidates_count, ["кандидат", "кандидата", "кандидатов"])}
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1 font-mono text-xl font-extrabold tabular-nums">
            <Trophy className="size-4 text-primary" aria-hidden /> {item.with_fsp_count}
          </div>
          <div className="text-xs text-muted-foreground">с ФСП</div>
        </div>
      </div>
      <dl className="grid gap-1 border-t border-border-subtle pt-3 text-xs">
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Медианный перцентиль</dt>
          <dd className="font-mono font-bold">{item.median_percentile === null ? "—" : toPercent(item.median_percentile)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Медиана ожиданий</dt>
          <dd className="font-mono font-bold">{item.median_salary === null ? "—" : `${formatNumber(item.median_salary)} ₽`}</dd>
        </div>
      </dl>
    </Link>
  );
}
