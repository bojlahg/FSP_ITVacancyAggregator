import {
  ArrowLeft,
  ChevronDown,
  FilterX,
  History,
  Layers,
  ListOrdered,
  Pencil,
  Pin,
  SearchX,
  Send,
  SlidersHorizontal,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { CandidateRow } from "@/components/employer/CandidateRow";
import { InviteDialog } from "@/components/employer/InviteDialog";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { ScoreBadge } from "@/components/ScoreBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { plural } from "@/lib/format";
import { gradeLabel, specializationLabel, WORK_FORMAT_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
// MOCK: заменить на GET /needs/{id}, /needs/{id}/recommendations (фильтры уходят в query), /needs/{id}/salary-coverage
import {
  findMockNeed,
  MOCK_MAX_ACTIVE_INVITES_PER_NEED,
  mockCandidates,
  mockNeeds,
  mockRecommendedCategories,
  type MockCandidate,
} from "@/mocks/talent";

const matchLabels = {
  exact: "Точное совпадение",
  adjacent_grade: "Смежный грейд",
  adjacent_specialization: "Смежная специализация",
} as const;

const categoryKey = (specialization: string, grade: string) => `${specialization}.${grade}`;

export default function NeedDetailPage() {
  const { needId } = useParams();
  // MOCK: неизвестный id показывает первую демо-потребность, чтобы экран можно было открыть по любой ссылке.
  const need = findMockNeed(needId) ?? mockNeeds[0]!;

  // Состояние фильтров хранится в URL (docs/implementation.md §8.1 п.4) — подборка переживает перезагрузку и шаринг ссылки.
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = {
    fsp: searchParams.get("fsp") === "1",
    verified: searchParams.get("verified") === "1",
    inRange: searchParams.get("inRange") === "1",
    format: searchParams.get("format") ?? "",
    fresh: searchParams.get("fresh") ?? "",
    category: searchParams.get("cat") ?? "",
    view: searchParams.get("view") === "top" ? "top" : "groups",
  };
  const hasActiveFilters =
    filters.fsp || filters.verified || filters.inRange || !!filters.format || !!filters.fresh || !!filters.category;

  const setParam = (key: string, value: string | boolean | null) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value === null || value === false || value === "") next.delete(key);
        else next.set(key, value === true ? "1" : value);
        return next;
      },
      { replace: true },
    );
  };

  const resetFilters = () => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams();
        const view = current.get("view");
        if (view) next.set("view", view);
        return next;
      },
      { replace: true },
    );
  };

  // Шорт-лист закреплён за потребностью и не зависит от фильтров.
  // TODO: POST|DELETE /needs/{id}/shortlist/{candidate_id} вместо локального состояния.
  const [shortlist, setShortlist] = useState<string[]>(["cand-anna"]);
  const toggleShortlist = (id: string) =>
    setShortlist((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));

  const [inviteTarget, setInviteTarget] = useState<MockCandidate | null>(null);
  const [outOfFiltersOpen, setOutOfFiltersOpen] = useState(false);

  const inHardFilters = mockCandidates.filter((candidate) => !candidate.outOfFilterReason);
  const outOfFilters = mockCandidates.filter((candidate) => candidate.outOfFilterReason);

  const visible = inHardFilters
        .filter((candidate) => !filters.fsp || candidate.hasFsp)
        .filter((candidate) => !filters.verified || candidate.testVerified)
        .filter((candidate) => !filters.inRange || candidate.salaryMin <= need.salaryTo)
        .filter((candidate) => !filters.format || candidate.format === filters.format)
        .filter((candidate) => !filters.fresh || candidate.freshDays <= Number(filters.fresh))
        .filter(
          (candidate) =>
            !filters.category || categoryKey(candidate.specialization, candidate.grade) === filters.category,
        )
        .sort((a, b) => b.score - a.score);

  const groups = (() => {
    const order = mockRecommendedCategories.map((category) => categoryKey(category.specialization, category.grade));
    const byKey = new Map<string, MockCandidate[]>();
    for (const candidate of visible) {
      const key = categoryKey(candidate.specialization, candidate.grade);
      byKey.set(key, [...(byKey.get(key) ?? []), candidate]);
    }
    return [...byKey.entries()].sort(([a], [b]) => {
      const ai = order.indexOf(a);
      const bi = order.indexOf(b);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });
  })();

  const shortlisted = mockCandidates.filter((candidate) => shortlist.includes(candidate.id));
  const exactCategory = mockRecommendedCategories.find((category) => category.match === "exact");

  const renderRow = (candidate: MockCandidate) => (
    <CandidateRow
      key={candidate.id}
      candidate={candidate}
      salaryTo={need.salaryTo}
      shortlisted={shortlist.includes(candidate.id)}
      onToggleShortlist={toggleShortlist}
      explanationLimit={3}
      actions={
        <>
          <Button size="sm" onClick={() => setInviteTarget(candidate)}>
            <Send /> Пригласить
          </Button>
          <Button asChild size="sm" variant="ghost">
            <Link to={`/employer/candidates/${candidate.id}?need_id=${need.id}`}>Карточка и полное объяснение</Link>
          </Button>
        </>
      }
    />
  );

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-3 mb-2">
        <Link to="/employer/needs">
          <ArrowLeft /> Потребности
        </Link>
      </Button>

      <PageHeader
        eyebrow={
          <span className="inline-flex items-center gap-2">
            Подборка · версия {need.version}
            {need.published && <Badge variant="soft">опубликована как вакансия</Badge>}
          </span>
        }
        title={need.title}
        description="Рекомендованные категории и кандидаты, ранжированные по совпадению с потребностью. Каждое число объяснено — тем же кодом, которым посчитан score."
        actions={
          <>
            <Button variant="ghost" size="sm">
              <History /> История версий
            </Button>
            <Button variant="outline" size="sm">
              <Pencil /> Изменить потребность
            </Button>
          </>
        }
      />

      {/* Сводка потребности */}
      <Card className="mb-8 overflow-hidden py-0">
        <div className="grid divide-y divide-border-subtle md:grid-cols-4 md:divide-x md:divide-y-0">
          <div className="space-y-2 p-5">
            <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Категория</div>
            <CategoryBadge specialization={need.specialization} grade={need.grade} variant="solid" size="md" />
            <div className="text-xs text-muted-foreground">
              {need.industry} · {WORK_FORMAT_LABELS[need.format]} · {need.city}
            </div>
          </div>
          <div className="space-y-2 p-5">
            <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Вилка</div>
            <SalaryRange from={need.salaryFrom} to={need.salaryTo} className="text-lg" />
            {exactCategory && (
              <div className="space-y-1">
                <Progress value={exactCategory.coverage} className="h-1.5" />
                <div className="text-xs text-muted-foreground">
                  покрывает ожидания <b className="font-mono text-foreground">{exactCategory.coverage}%</b> кандидатов{" "}
                  {specializationLabel(exactCategory.specialization)} · {gradeLabel(exactCategory.grade)}
                </div>
              </div>
            )}
          </div>
          <div className="space-y-2 p-5">
            <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Стек</div>
            <div className="flex flex-wrap gap-1.5">
              {need.requiredStack.map((skill) => (
                <Badge key={skill} variant="soft">
                  {skill}
                </Badge>
              ))}
              {need.desiredStack.map((skill) => (
                <Badge key={skill} variant="muted" title="Желательный навык">
                  {skill}
                </Badge>
              ))}
            </div>
            <div className="text-xs text-muted-foreground">обязательный · желательный</div>
          </div>
          <div className="space-y-2 p-5">
            <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Приглашения</div>
            <div className="font-mono text-lg font-extrabold tabular-nums">
              {need.activeInvites}
              <span className="text-muted-foreground"> / {MOCK_MAX_ACTIVE_INVITES_PER_NEED}</span>
            </div>
            <Progress value={(need.activeInvites / MOCK_MAX_ACTIVE_INVITES_PER_NEED) * 100} className="h-1.5" />
            <div className="text-xs text-muted-foreground">активных слотов — приглашайте адресно</div>
          </div>
        </div>
      </Card>

      {/* Уровень 1: рекомендованные категории */}
      <section className="mb-8" aria-labelledby="rec-categories">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 id="rec-categories" className="text-lg font-extrabold">
            Рекомендованные категории
          </h2>
          {filters.category && (
            <Button variant="link" size="sm" className="h-auto p-0" onClick={() => setParam("cat", null)}>
              Показать все категории
            </Button>
          )}
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          {mockRecommendedCategories.map((category) => {
            const key = categoryKey(category.specialization, category.grade);
            const selected = filters.category === key;
            return (
              <button
                key={key}
                type="button"
                aria-pressed={selected}
                onClick={() => setParam("cat", selected ? null : key)}
                className={cn(
                  "flex flex-col gap-3 rounded-xl border bg-card p-4 text-left transition-[box-shadow,border-color] outline-none hover:shadow-md focus-visible:ring-[3px] focus-visible:ring-ring/40",
                  selected && "border-primary bg-primary-tint ring-1 ring-primary/30",
                  category.match === "exact" && !selected && "border-primary/60",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <CategoryBadge
                    specialization={category.specialization}
                    grade={category.grade}
                    variant={category.match === "exact" ? "solid" : "outline"}
                    size="md"
                  />
                  <span
                    className={cn(
                      "font-mono text-[11px] font-medium tracking-wide uppercase",
                      category.match === "exact" ? "text-primary" : "text-muted-foreground",
                    )}
                  >
                    {matchLabels[category.match]}
                  </span>
                </div>
                <div className="flex items-end gap-5">
                  <div>
                    <div className="font-mono text-2xl font-extrabold tabular-nums">{category.candidates}</div>
                    <div className="text-xs text-muted-foreground">
                      {plural(category.candidates, ["кандидат", "кандидата", "кандидатов"])}
                    </div>
                  </div>
                  <div>
                    <div className="font-mono text-2xl font-extrabold tabular-nums">{category.withFsp}</div>
                    <div className="text-xs text-muted-foreground">с ФСП</div>
                  </div>
                  <div className="flex-1">
                    <div className="mb-1 text-right font-mono text-xs font-bold tabular-nums">{category.coverage}%</div>
                    <Progress value={category.coverage} className="h-1.5" />
                    <div className="mt-1 text-right text-[11px] text-muted-foreground">покрытие вилки</div>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">{category.note}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Уровень 2: кандидаты */}
      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="grid content-start gap-4 lg:sticky lg:top-6 lg:self-start">
          <Card className="gap-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Pin className="size-4 text-primary" aria-hidden /> Шорт-лист
                <Badge variant="soft" className="ml-auto">
                  {shortlisted.length}
                </Badge>
              </CardTitle>
              <CardDescription>Закреплён за потребностью и не меняется при смене фильтров.</CardDescription>
            </CardHeader>
            <CardContent>
              {shortlisted.length === 0 ? (
                <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
                  Нажмите «В шорт-лист» у кандидата, чтобы закрепить его здесь.
                </p>
              ) : (
                <ul className="grid gap-2">
                  {shortlisted.map((candidate) => (
                    <li key={candidate.id} className="flex items-center gap-2 rounded-lg bg-muted/60 px-2 py-1.5">
                      <ScoreBadge score={candidate.score} size="sm" />
                      <Link
                        to={`/employer/candidates/${candidate.id}?need_id=${need.id}`}
                        className="min-w-0 flex-1 truncate text-sm font-medium hover:text-primary"
                      >
                        {candidate.displayName}
                      </Link>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="size-7"
                        onClick={() => toggleShortlist(candidate.id)}
                        aria-label={`Убрать ${candidate.displayName} из шорт-листа`}
                      >
                        <X />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card className="gap-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SlidersHorizontal className="size-4 text-primary" aria-hidden /> Фильтры
              </CardTitle>
              <CardDescription>Поверх подборки, без потери результата</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-3">
                <label className="flex items-center gap-3 text-sm">
                  <Checkbox checked={filters.fsp} onChange={(event) => setParam("fsp", event.target.checked)} />
                  Есть достижения ФСП
                </label>
                <label className="flex items-center gap-3 text-sm">
                  <Checkbox
                    checked={filters.verified}
                    onChange={(event) => setParam("verified", event.target.checked)}
                  />
                  Стек проверен тестом
                </label>
                <label className="flex items-center gap-3 text-sm">
                  <Checkbox checked={filters.inRange} onChange={(event) => setParam("inRange", event.target.checked)} />
                  Ожидания в пределах вилки
                </label>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="filter-format">Формат работы</Label>
                <Select
                  id="filter-format"
                  value={filters.format}
                  onChange={(event) => setParam("format", event.target.value)}
                >
                  <option value="">Любой</option>
                  <option value="office">Офис</option>
                  <option value="hybrid">Гибрид</option>
                  <option value="remote">Удалённо</option>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="filter-fresh">Свежесть результата</Label>
                <Select id="filter-fresh" value={filters.fresh} onChange={(event) => setParam("fresh", event.target.value)}>
                  <option value="">Любая</option>
                  <option value="14">До 2 недель</option>
                  <option value="30">До месяца</option>
                  <option value="90">До 3 месяцев</option>
                </Select>
              </div>
              <Button variant="ghost" size="sm" onClick={resetFilters} disabled={!hasActiveFilters}>
                <FilterX /> Сбросить фильтры
              </Button>
            </CardContent>
          </Card>
        </aside>

        <section aria-labelledby="candidates-title" className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="candidates-title" className="flex items-center gap-2 text-lg font-extrabold">
              <Users className="size-5 text-primary" aria-hidden />
              Кандидаты
              <span className="font-mono text-base font-medium text-muted-foreground">{visible.length}</span>
            </h2>
            <Tabs value={filters.view} onValueChange={(value) => setParam("view", value === "top" ? "top" : null)}>
              <TabsList>
                <TabsTrigger value="groups">
                  <Layers /> По категориям
                </TabsTrigger>
                <TabsTrigger value="top">
                  <ListOrdered /> Общий топ
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {visible.length === 0 ? (
            <EmptyState
              icon={SearchX}
              title="Под фильтры никто не подошёл"
              description="Ослабьте условия — подборка и шорт-лист при этом сохранятся."
              action={
                <Button variant="outline" onClick={resetFilters}>
                  <FilterX /> Сбросить фильтры
                </Button>
              }
            />
          ) : filters.view === "top" ? (
            <div className="grid gap-3">{visible.map(renderRow)}</div>
          ) : (
            <div className="space-y-6">
              {groups.map(([key, candidates]) => {
                const [specialization = "", grade = ""] = key.split(".");
                return (
                  <div key={key} className="space-y-3">
                    <div className="flex items-center gap-3">
                      <CategoryBadge specialization={specialization} grade={grade} variant="outline" />
                      <span className="h-px flex-1 bg-border-subtle" aria-hidden />
                      <span className="font-mono text-xs text-muted-foreground">
                        {candidates.length} {plural(candidates.length, ["кандидат", "кандидата", "кандидатов"])}
                      </span>
                    </div>
                    <div className="grid gap-3">{candidates.map(renderRow)}</div>
                  </div>
                );
              })}
            </div>
          )}

          {outOfFilters.length > 0 && (
            <div className="rounded-xl border border-dashed">
              <button
                type="button"
                onClick={() => setOutOfFiltersOpen((open) => !open)}
                aria-expanded={outOfFiltersOpen}
                className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
              >
                <span>
                  <span className="font-mono font-bold">Вне фильтров · {outOfFilters.length}</span>
                  <span className="block text-xs text-muted-foreground">
                    Не прошли жёсткие условия потребности — не скрываем, а показываем причину
                  </span>
                </span>
                <ChevronDown
                  className={cn("size-4 shrink-0 transition-transform", outOfFiltersOpen && "rotate-180")}
                  aria-hidden
                />
              </button>
              {outOfFiltersOpen && (
                <ul className="divide-y divide-border-subtle border-t border-border-subtle">
                  {outOfFilters.map((candidate) => (
                    <li key={candidate.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                      <ScoreBadge score={candidate.score} size="sm" />
                      <Link
                        to={`/employer/candidates/${candidate.id}?need_id=${need.id}`}
                        className="font-mono text-sm font-bold hover:text-primary"
                      >
                        {candidate.displayName}
                      </Link>
                      <CategoryBadge specialization={candidate.specialization} grade={candidate.grade} />
                      <span className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span className="size-1.5 shrink-0 rounded-full bg-destructive" aria-hidden />
                        {candidate.outOfFilterReason}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      </div>

      <InviteDialog
        key={inviteTarget?.id ?? "none"}
        open={inviteTarget !== null}
        onOpenChange={(open) => !open && setInviteTarget(null)}
        candidateName={inviteTarget?.displayName ?? ""}
        defaults={{
          title: need.title,
          salaryFrom: need.salaryFrom,
          salaryTo: need.salaryTo,
        }}
      />
    </>
  );
}
