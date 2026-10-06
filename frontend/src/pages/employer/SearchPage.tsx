import { ChevronLeft, ChevronRight, FilterX, Loader2, Search, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { SkillsMultiSelect } from "@/components/candidate/SkillsMultiSelect";
import { CandidateRow } from "@/components/employer/CandidateRow";
import { CommitInput } from "@/components/employer/CommitInput";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { apiError } from "@/lib/api-error";
import { type TalentSearchQuery, useTalentSearch } from "@/lib/employer-queries";
import { formatNumber } from "@/lib/format";
import { WORK_FORMAT_LABELS } from "@/lib/labels";
import { type Grade, type SkillOut, useGrades, useSkillCatalog, useSpecializations } from "@/lib/testing-queries";
import { enumParam, intParam, useUrlFilters } from "@/lib/url-filters";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;
const GRADES: readonly Grade[] = ["intern", "junior", "middle", "senior"];
const FORMATS = ["office", "hybrid", "remote"] as const;
const SORTS = ["vps", "percentile", "fresh"] as const;
const SORT_LABELS: Record<(typeof SORTS)[number], string> = {
  vps: "Сила подтверждённого профиля",
  percentile: "Перцентиль в категории",
  fresh: "Свежесть результата",
};
const FRESH_OPTIONS = [
  { value: "14", label: "До 2 недель" },
  { value: "30", label: "До месяца" },
  { value: "90", label: "До 3 месяцев" },
];
const FILTER_KEYS = ["spec", "grade", "skill", "verified", "fsp", "salary", "format", "city", "fresh"];

export default function SearchPage() {
  const { params, set, reset } = useUrlFilters();
  const specializations = useSpecializations();
  const grades = useGrades();
  const catalog = useSkillCatalog();
  const [pickedNames, setPickedNames] = useState<Record<string, string>>({});

  const filters = {
    spec: params.get("spec") ?? "",
    grade: enumParam(params.get("grade"), GRADES),
    skills: params.getAll("skill"),
    verified: params.get("verified") === "1",
    fsp: params.get("fsp") === "1",
    salary: intParam(params.get("salary")),
    format: enumParam(params.get("format"), FORMATS),
    city: params.get("city") ?? "",
    fresh: intParam(params.get("fresh")),
    sort: enumParam(params.get("sort"), SORTS) ?? "vps",
    page: Math.max(0, (intParam(params.get("page")) ?? 1) - 1),
  };
  const hasActiveFilters = FILTER_KEYS.some((key) => params.has(key));

  const query: TalentSearchQuery = {
    sort: filters.sort,
    offset: filters.page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(filters.spec && { specialization: filters.spec }),
    ...(filters.grade && { grade: filters.grade }),
    ...(filters.skills.length > 0 && { skills: filters.skills }),
    ...(filters.verified && { verified_only: true }),
    ...(filters.fsp && { has_fsp: true }),
    ...(filters.salary && { salary_max: filters.salary }),
    ...(filters.format && { work_format: filters.format }),
    ...(filters.city && { city: filters.city }),
    ...(filters.fresh && { fresh_days: filters.fresh }),
  };
  const search = useTalentSearch(query);

  // Любой фильтр возвращает на первую страницу.
  const setFilter = (changes: Parameters<typeof set>[0]) => set({ ...changes, page: null });
  const setSkills = (ids: string[]) => setFilter({ skill: ids });

  const skillNames = {
    ...Object.fromEntries((catalog.data ?? []).map((skill) => [skill.id, skill.name])),
    ...pickedNames,
  };
  const rememberNames = (skills: SkillOut[]) =>
    setPickedNames((current) => ({ ...current, ...Object.fromEntries(skills.map((skill) => [skill.id, skill.name])) }));

  const total = search.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        eyebrow="Поиск по базе"
        title="Поиск по всей базе"
        description="Без потребности: фильтры по категории, стеку, ФСП, зарплате и формату. Внутри категории выше стоят кандидаты с более сильным подтверждённым профилем."
      />

      <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="h-fit gap-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <SlidersHorizontal className="size-4 text-primary" aria-hidden /> Фильтры
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="search-spec">Специализация</Label>
              <Select id="search-spec" value={filters.spec} onChange={(event) => setFilter({ spec: event.target.value })}>
                <option value="">Любая</option>
                {specializations.data?.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.name}
                  </option>
                ))}
                {filters.spec && !specializations.data?.some((item) => item.slug === filters.spec) && (
                  <option value={filters.spec}>{filters.spec}</option>
                )}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="search-grade">Грейд</Label>
              <Select
                id="search-grade"
                value={filters.grade ?? ""}
                onChange={(event) => setFilter({ grade: event.target.value })}
              >
                <option value="">Любой</option>
                {(grades.data ?? GRADES.map((slug) => ({ slug, name: slug }))).map((grade) => (
                  <option key={grade.slug} value={grade.slug}>
                    {grade.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="search-skills">Стек</Label>
              <SkillsMultiSelect
                id="search-skills"
                value={filters.skills}
                onChange={setSkills}
                names={skillNames}
                onNamesChange={rememberNames}
              />
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <Checkbox checked={filters.verified} onChange={(event) => setFilter({ verified: event.target.checked })} />
                только проверенный тестом
              </label>
            </div>
            <label className="flex items-center gap-3 text-sm">
              <Checkbox checked={filters.fsp} onChange={(event) => setFilter({ fsp: event.target.checked })} />
              Есть достижения ФСП
            </label>
            <div className="grid gap-2">
              <Label htmlFor="search-salary">Ожидания не выше, ₽ на руки</Label>
              <CommitInput
                id="search-salary"
                type="number"
                inputMode="numeric"
                min={0}
                step={10000}
                placeholder="например, 250000"
                value={filters.salary ? String(filters.salary) : ""}
                onCommit={(value) => setFilter({ salary: intParam(value) ?? null })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="search-format">Формат работы</Label>
              <Select
                id="search-format"
                value={filters.format ?? ""}
                onChange={(event) => setFilter({ format: event.target.value })}
              >
                <option value="">Любой</option>
                {FORMATS.map((format) => (
                  <option key={format} value={format}>
                    {WORK_FORMAT_LABELS[format]}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="search-city">Город</Label>
              <CommitInput
                id="search-city"
                placeholder="Любой"
                value={filters.city}
                onCommit={(value) => setFilter({ city: value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="search-fresh">Свежесть результата</Label>
              <Select
                id="search-fresh"
                value={filters.fresh ? String(filters.fresh) : ""}
                onChange={(event) => setFilter({ fresh: event.target.value })}
              >
                <option value="">Любая</option>
                {FRESH_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </div>
            <Button variant="ghost" size="sm" onClick={() => reset(["sort"])} disabled={!hasActiveFilters}>
              <FilterX /> Сбросить фильтры
            </Button>
          </CardContent>
        </Card>

        <section className="min-w-0 space-y-3" aria-labelledby="search-results">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="search-results" className="flex items-center gap-2 font-mono text-sm text-muted-foreground">
              {search.data ? `Найдено: ${formatNumber(total)}` : "Поиск…"}
              {search.isFetching && !search.isPending && (
                <Loader2 className="size-4 animate-spin" aria-label="Обновляем результаты" />
              )}
            </h2>
            <div className="flex items-center gap-2">
              <Label htmlFor="search-sort" className="text-xs text-muted-foreground">
                Сортировка
              </Label>
              <Select
                id="search-sort"
                className="h-9 w-auto"
                value={filters.sort}
                onChange={(event) => setFilter({ sort: event.target.value === "vps" ? null : event.target.value })}
              >
                {SORTS.map((sort) => (
                  <option key={sort} value={sort}>
                    {SORT_LABELS[sort]}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {search.isPending ? (
            <SkeletonCards count={4} />
          ) : search.isError ? (
            <ErrorState description={apiError(search.error).message} onRetry={() => void search.refetch()} />
          ) : search.data.items.length === 0 ? (
            <EmptyState
              icon={Search}
              title="Никого не нашли"
              description="Попробуйте ослабить фильтры."
              action={
                hasActiveFilters && (
                  <Button variant="outline" onClick={() => reset(["sort"])}>
                    <FilterX /> Сбросить фильтры
                  </Button>
                )
              }
            />
          ) : (
            <>
              <div className={cn("grid gap-3 transition-opacity", search.isPlaceholderData && "opacity-60")}>
                {search.data.items.map((candidate) => (
                  <CandidateRow key={candidate.id} candidate={candidate} href={`/employer/candidates/${candidate.id}`} />
                ))}
              </div>
              {pages > 1 && (
                <nav className="flex items-center justify-between gap-3 pt-2" aria-label="Страницы результатов">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={filters.page === 0}
                    onClick={() => set({ page: filters.page > 1 ? filters.page : null })}
                  >
                    <ChevronLeft /> Назад
                  </Button>
                  <span className="font-mono text-sm text-muted-foreground tabular-nums">
                    {filters.page + 1} / {pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={filters.page + 1 >= pages}
                    onClick={() => set({ page: filters.page + 2 })}
                  >
                    Дальше <ChevronRight />
                  </Button>
                </nav>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}
