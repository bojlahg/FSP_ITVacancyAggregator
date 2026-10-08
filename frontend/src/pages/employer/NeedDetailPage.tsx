import {
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronDown,
  Eye,
  EyeOff,
  FilterX,
  FlaskConical,
  History,
  Loader2,
  Mail,
  Pencil,
  Pin,
  SearchX,
  Send,
  ShieldQuestion,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, useParams } from "react-router";
import { ActionMenu, type ActionMenuItem } from "@/components/ActionMenu";
import { CandidateCategoryBadge, CategoryBadge } from "@/components/CategoryBadge";
import { CommitInput } from "@/components/employer/CommitInput";
import { InviteDialog } from "@/components/employer/InviteDialog";
import { MatchRow } from "@/components/employer/MatchRow";
import { NeedTextIssues } from "@/components/employer/NeedTextIssues";
import { SalaryCoverageCard } from "@/components/employer/SalaryCoverageCard";
import { ScoreTile } from "@/components/employer/ScoreTile";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { SalaryRange } from "@/components/SalaryRange";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import {
  type CandidateBrief,
  type CandidateMatch,
  type CategoryRecommendation,
  cityOptions,
  type Need,
  parseId,
  type RecommendationsQuery,
  shortlistTarget,
  useIndustries,
  useNeed,
  useNeeds,
  useRecommendations,
  useSalaryCoverage,
  useSetNeedPublished,
  useTalentCities,
  useToggleShortlist,
} from "@/lib/employer-queries";
import { formatNumber, plural, toPercent } from "@/lib/format";
import { CATEGORY_FIT_LABELS, candidateCategoryLabel, NEED_STATUS_LABELS, WORK_FORMAT_LABELS } from "@/lib/labels";
import { type Grade, useGrades, useSkillCatalog } from "@/lib/testing-queries";
import { enumParam, intParam, useUrlFilters } from "@/lib/url-filters";
import { cn } from "@/lib/utils";

const GRADES: readonly Grade[] = ["intern", "junior", "middle", "senior"];
const FORMATS = ["office", "hybrid", "remote"] as const;
const FRESH_OPTIONS = [
  { value: "14", label: "до 2 недель" },
  { value: "30", label: "до месяца" },
  { value: "90", label: "до 3 месяцев" },
];
const FILTER_KEYS = ["grade", "fsp", "verified", "salary", "format", "city", "fresh", "hard"];
// Сколько строк показывать сразу: в группе без выбранной категории и в плоском списке (шаг «Показать ещё»)
const GROUP_PREVIEW = 5;
const PAGE_STEP = 10;

const groupKey = (category: { specialization: string; grade: string }) => `${category.specialization}.${category.grade}`;
const candidateHref = (candidateId: number, needId: number) => `/employer/candidates/${candidateId}?need=${needId}`;

export default function NeedDetailPage() {
  const needId = parseId(useParams().needId);
  const need = useNeed(needId);

  if (needId === null || (need.isError && apiError(need.error).status === 404)) {
    return (
      <EmptyState
        icon={SearchX}
        title="Потребность не найдена"
        description="Возможно, она удалена или принадлежит другой компании."
        action={
          <Button asChild variant="outline">
            <Link to="/employer/needs">К потребностям</Link>
          </Button>
        }
      />
    );
  }
  if (need.isPending) return <SkeletonCards count={3} />;
  if (need.isError) {
    return <ErrorState description={apiError(need.error).message} onRetry={() => void need.refetch()} />;
  }
  return <NeedView key={need.data.id} need={need.data} />;
}

function NeedView({ need }: { need: Need }) {
  const { params, set, reset } = useUrlFilters();
  const grades = useGrades();
  const cities = useTalentCities();

  // Фильтры живут в URL (§8.1 п.4) и уходят в query API; подборку считает только backend.
  const filters = {
    grade: enumParam(params.get("grade"), GRADES),
    fsp: params.get("fsp") === "1",
    verified: params.get("verified") === "1",
    salary: intParam(params.get("salary")),
    format: enumParam(params.get("format"), FORMATS),
    city: params.get("city") ?? "",
    fresh: intParam(params.get("fresh")),
    hard: params.get("hard") !== "0",
    view: params.get("view") === "top" ? ("none" as const) : ("category" as const),
  };
  // Выбранная категория — фильтр отображения поверх того же ответа: score и порядок не меняются
  const selectedCategory = filters.view === "category" ? params.get("cat") : null;
  const activeFilters = FILTER_KEYS.filter((key) => params.has(key)).length;
  const hasActiveFilters = activeFilters > 0;

  const query: RecommendationsQuery = {
    group_by: filters.view,
    ...(filters.grade && { grade: filters.grade }),
    ...(filters.fsp && { has_fsp: true }),
    ...(filters.verified && { verified_only: true }),
    ...(filters.salary && { salary_max: filters.salary }),
    ...(filters.format && { work_format: filters.format }),
    ...(filters.city && { city: filters.city }),
    ...(filters.fresh && { fresh_days: filters.fresh }),
    ...(!filters.hard && { apply_hard_filters: false }),
  };
  const recs = useRecommendations(need.id, query);
  const shortlist = useToggleShortlist(need.id);
  const publish = useSetNeedPublished(need.id);

  const [inviteTarget, setInviteTarget] = useState<CandidateMatch | null>(null);
  const [invited, setInvited] = useState<Map<number, string>>(new Map());
  const [lastInvited, setLastInvited] = useState<string | null>(null);
  const [outOfFiltersOpen, setOutOfFiltersOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  // «Показать ещё»: счётчик сбрасывается при смене фильтров и вида
  const listKey = params.toString();
  const [shown, setShown] = useState({ key: listKey, count: PAGE_STEP });
  const shownCount = shown.key === listKey ? shown.count : PAGE_STEP;

  const { invitations_active: activeInvites, invitations_limit: inviteLimit } = need.stats;
  const limitReached = inviteLimit > 0 && activeInvites >= inviteLimit;
  const stack = [...(need.required_skills ?? []), ...(need.optional_skills ?? [])];

  const toggleShortlist = (match: CandidateMatch) => {
    shortlist.mutate(match.shortlisted ? { add: false, candidateId: match.candidate.id } : { add: true, match });
  };
  const pendingShortlistId = shortlist.isPending && shortlist.variables ? shortlistTarget(shortlist.variables) : undefined;
  const selectCategory = (key: string | null) => set({ cat: key, view: null });

  const renderRow = (match: CandidateMatch) => (
    <MatchRow
      key={match.candidate.id}
      match={match}
      href={candidateHref(match.candidate.id, need.id)}
      salaryTo={need.salary_to}
      stack={stack}
      shortlistPending={pendingShortlistId === match.candidate.id}
      onToggleShortlist={() => toggleShortlist(match)}
      invitedStatus={invited.get(match.candidate.id) ?? openInvitation(match.invitation_status)}
      onInvite={() => setInviteTarget(match)}
      inviteDisabledReason={limitReached ? "Все слоты приглашений по потребности заняты" : undefined}
    />
  );

  const data = recs.data;
  const groups = data ? groupCandidates(data.candidates, data.categories) : [];
  const selected = selectedCategory ? groups.find((group) => group.key === selectedCategory) : undefined;
  const selectedLabel = selectedCategory
    ? (data?.categories.find((item) => groupKey(item.category) === selectedCategory)?.category.label ?? null)
    : null;
  const flatList = filters.view === "none" ? (data?.candidates ?? []) : selectedCategory ? (selected?.items ?? []) : null;

  const menuItems: ActionMenuItem[] = [
    ...(need.parent_id !== null
      ? [{ label: `Версия ${need.version - 1}`, icon: History, to: `/employer/needs/${need.parent_id}` }]
      : []),
    { label: "Приглашения", icon: Mail, to: `/employer/invitations?need=${need.id}` },
    { label: "Проверка под вакансию", icon: FlaskConical, to: `/employer/vacancy-test?need=${need.id}` },
    {
      label: need.published ? "Снять вакансию" : "Опубликовать как вакансию",
      icon: need.published ? EyeOff : Eye,
      pending: publish.isPending,
      onSelect: () => publish.mutate(!need.published),
    },
  ];

  return (
    <div className="flex flex-col gap-6 lg:gap-8">
      <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div className="flex min-w-0 flex-[1_1_520px] flex-col gap-2">
          <Link
            to="/employer/needs"
            className="inline-flex min-h-11 items-center gap-1.5 self-start text-sm font-medium text-muted-foreground hover:text-foreground sm:min-h-0"
          >
            <ArrowLeft className="size-4" aria-hidden /> Потребности
          </Link>
          <div className="flex flex-wrap items-center gap-2.5 sm:mt-2">
            <span className="font-mono text-xs font-medium tracking-widest text-muted-foreground uppercase">
              Подборка · версия {need.version}
            </span>
            {need.published && <Badge variant="soft">опубликована как вакансия</Badge>}
            {need.status !== "active" && <Badge variant="muted">{NEED_STATUS_LABELS[need.status]}</Badge>}
          </div>
          <h1 className="font-mono text-2xl font-bold tracking-tight text-balance sm:text-3xl">{need.title}</h1>
          <p className="max-w-3xl text-base text-pretty text-muted-foreground max-sm:hidden">
            {need.team_description ??
              "Рекомендованные категории и кандидаты, ранжированные по совпадению с потребностью. Каждое число объяснено тем же кодом, которым посчитан score."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline">
            <Link to={`/employer/needs/${need.id}/edit`}>
              <Pencil /> Изменить потребность
            </Link>
          </Button>
          <ActionMenu label="Ещё: приглашения, проверка под вакансию, публикация вакансии" items={menuItems} />
        </div>
      </header>

      {(publish.isError || (need.text_issues ?? []).length > 0) && (
        <div className="grid gap-4">
          <FormAlert message={publish.isError ? apiError(publish.error).message : null} />
          <NeedTextIssues issues={need.text_issues ?? []} />
        </div>
      )}
      <OlderVersionNotice need={need} />

      <NeedSummary need={need} activeInvites={activeInvites} inviteLimit={inviteLimit} />

      <section aria-labelledby="rec-categories" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="rec-categories" className="font-mono text-lg font-semibold tracking-tight sm:text-xl">
            Рекомендованные категории
          </h2>
          <span className="text-xs text-muted-foreground max-sm:hidden">
            Выберите категорию — список кандидатов ниже обновится
          </span>
        </div>
        {recs.isPending ? (
          <div className="flex gap-2 overflow-hidden sm:grid sm:grid-cols-[repeat(auto-fit,minmax(min(168px,100%),1fr))]">
            {[0, 1, 2, 3].map((index) => (
              <Skeleton key={index} className="h-11 w-36 shrink-0 rounded-full sm:h-28 sm:w-auto sm:rounded-[10px]" />
            ))}
          </div>
        ) : recs.isError ? (
          <p className="text-sm text-muted-foreground">Категории появятся, когда подборка загрузится.</p>
        ) : data && data.categories.length === 0 ? (
          <p className="rounded-[10px] border border-dashed px-5 py-6 text-sm text-muted-foreground">
            В базе пока нет кандидатов в подходящих категориях.
          </p>
        ) : (
          <div className="relative -mx-4 flex gap-2 overflow-x-auto px-4 pb-0.5 sm:mx-0 sm:grid sm:grid-cols-[repeat(auto-fit,minmax(min(168px,100%),1fr))] sm:overflow-visible sm:px-0 sm:pb-0">
            {data?.categories.map((category) => {
              const key = groupKey(category.category);
              const active = selectedCategory === key;
              return (
                <CategoryTab
                  key={key}
                  category={category}
                  active={active}
                  onSelect={() => selectCategory(active ? null : key)}
                />
              );
            })}
          </div>
        )}
      </section>

      <div className="flex flex-wrap items-start gap-6">
        <section aria-labelledby="candidates-title" className="flex min-w-0 flex-[999_1_520px] flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2
              id="candidates-title"
              className="flex flex-wrap items-baseline gap-x-2.5 font-mono text-lg font-semibold tracking-tight sm:text-xl"
            >
              Кандидаты
              {data && (
                <span className="font-mono text-sm font-medium text-muted-foreground">
                  {selectedCategory && selectedLabel
                    ? `${selected?.items.length ?? 0} в ${selectedLabel}`
                    : `${data.candidates.length}${data.total > data.candidates.length ? ` из ${data.total}` : ""}`}
                </span>
              )}
              {recs.isFetching && !recs.isPending && (
                <Loader2 className="size-4 animate-spin self-center text-muted-foreground" aria-label="Обновляем подборку" />
              )}
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="ghost"
                className="h-11 border border-border sm:hidden"
                aria-expanded={filtersOpen}
                aria-controls="need-filters"
                onClick={() => setFiltersOpen((open) => !open)}
              >
                <SlidersHorizontal /> Фильтры
                {activeFilters > 0 && <span className="font-semibold text-primary">· {activeFilters}</span>}
              </Button>
              <ViewSwitch
                value={filters.view}
                onChange={(view) => set(view === "none" ? { view: "top", cat: null } : { view: null })}
                total={data?.candidates.length}
              />
            </div>
          </div>

          <div
            id="need-filters"
            role="group"
            aria-label="Фильтры поверх подборки"
            className={cn(
              "flex-wrap items-center gap-2 rounded-[10px] border border-border-subtle bg-card p-3",
              filtersOpen ? "flex" : "hidden sm:flex",
            )}
          >
            <SlidersHorizontal className="size-4 text-muted-foreground max-sm:hidden" aria-hidden />
            <ToggleChip
              checked={filters.hard}
              onChange={(checked) => set({ hard: checked ? null : "0" })}
              title="Формат, город и ожидания выше вилки на 30%+. Кто не прошёл — в блоке «Вне фильтров»"
            >
              Жёсткие условия потребности
            </ToggleChip>
            <ToggleChip checked={filters.fsp} onChange={(checked) => set({ fsp: checked })}>
              Есть достижения ФСП
            </ToggleChip>
            <ToggleChip
              checked={filters.verified}
              onChange={(checked) => set({ verified: checked })}
              title="Хотя бы один обязательный навык потребности проверен тестом"
            >
              Навык из стека проверен тестом
            </ToggleChip>
            <SelectChip
              label="Грейд"
              active={!!filters.grade}
              value={filters.grade ?? ""}
              onChange={(value) => set({ grade: value })}
            >
              <option value="">все рекомендованные</option>
              {(grades.data ?? GRADES.map((slug) => ({ slug, name: slug }))).map((grade) => (
                <option key={grade.slug} value={grade.slug}>
                  {grade.name}
                </option>
              ))}
            </SelectChip>
            <InputChip label="Ожидания до" ariaLabel="Ожидания не выше, ₽ на руки" active={!!filters.salary} suffix="₽">
              <CommitInput
                id="filter-salary"
                aria-label="Ожидания не выше, ₽ на руки"
                type="number"
                inputMode="numeric"
                min={0}
                step={10000}
                placeholder="любые"
                value={filters.salary ? String(filters.salary) : ""}
                onCommit={(value) => set({ salary: intParam(value) ?? null })}
                className={chipInputClass("w-20")}
              />
            </InputChip>
            {filters.salary !== need.salary_to && (
              <Button
                variant="link"
                size="sm"
                className="h-8 px-1"
                onClick={() => set({ salary: need.salary_to })}
              >
                в пределах вилки
              </Button>
            )}
            <SelectChip
              label="Формат"
              ariaLabel="Формат работы"
              active={!!filters.format}
              value={filters.format ?? ""}
              onChange={(value) => set({ format: value })}
            >
              <option value="">любой</option>
              {FORMATS.map((format) => (
                <option key={format} value={format}>
                  {WORK_FORMAT_LABELS[format]}
                </option>
              ))}
            </SelectChip>
            <SelectChip label="Город" active={!!filters.city} value={filters.city} onChange={(value) => set({ city: value })}>
              <option value="">любой</option>
              {cityOptions(cities.data ?? [], filters.city).map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
            </SelectChip>
            <SelectChip
              label="Свежесть"
              ariaLabel="Свежесть результата"
              active={!!filters.fresh}
              value={filters.fresh ? String(filters.fresh) : ""}
              onChange={(value) => set({ fresh: value })}
            >
              <option value="">любая</option>
              {FRESH_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </SelectChip>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" className="h-8" onClick={() => reset(["view", "cat"])}>
                <FilterX /> Сбросить
              </Button>
            )}
            <span className="text-xs text-muted-foreground sm:ml-auto">
              Фильтры не меняют подборку — состояние в адресе
            </span>
          </div>

          {lastInvited && (
            <div
              role="status"
              className="flex items-start gap-2 rounded-lg border border-primary/30 bg-primary-tint px-4 py-3 text-sm"
            >
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              <span className="flex-1">
                Приглашение для <b>{lastInvited}</b> отправлено. Статус — в разделе{" "}
                <Link to={`/employer/invitations?need=${need.id}`} className="text-primary underline-offset-4 hover:underline">
                  «Приглашения»
                </Link>
                .
              </span>
              <button
                type="button"
                onClick={() => setLastInvited(null)}
                className="rounded-sm text-muted-foreground hover:text-foreground"
                aria-label="Скрыть уведомление"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
          )}
          {limitReached && (
            <FormAlert
              message={`Заняты все ${inviteLimit} слотов приглашений. Слот освободится, когда кандидат ответит, истечёт срок или вы отзовёте приглашение.`}
            />
          )}

          {recs.isPending ? (
            <SkeletonCards count={3} />
          ) : recs.isError ? (
            <ErrorState
              title="Не удалось собрать подборку"
              description={apiError(recs.error).message}
              onRetry={() => void recs.refetch()}
            />
          ) : data && data.candidates.length === 0 ? (
            <EmptyState
              icon={SearchX}
              title={hasActiveFilters ? "Под фильтры никто не подошёл" : "Подходящих кандидатов пока нет"}
              description={
                data.unconfirmed.length > 0
                  ? "Ниже — кандидаты этой специализации, у которых тест ещё не подтвердил грейд."
                  : hasActiveFilters
                    ? "Ослабьте условия — шорт-лист при этом сохранится."
                    : "Загляните в блок «Вне фильтров» или расширьте вилку и стек."
              }
              action={
                hasActiveFilters && (
                  <Button variant="outline" onClick={() => reset(["view", "cat"])}>
                    <FilterX /> Сбросить фильтры
                  </Button>
                )
              }
            />
          ) : flatList && flatList.length === 0 ? (
            <EmptyState
              icon={SearchX}
              title="В этой категории под условия никто не подошёл"
              description="Категория посчитана по всей базе, а список — по текущим фильтрам и топу подборки."
              action={
                <Button variant="outline" onClick={() => selectCategory(null)}>
                  Все категории
                </Button>
              }
            />
          ) : (
            <div className={cn("grid gap-3 transition-opacity", recs.isPlaceholderData && "opacity-60")}>
              {flatList ? (
                <>
                  {flatList.slice(0, shownCount).map(renderRow)}
                  {flatList.length > shownCount && (
                    <Button
                      variant="ghost"
                      className="h-11 border border-border"
                      onClick={() => setShown({ key: listKey, count: shownCount + PAGE_STEP })}
                    >
                      Показать ещё {Math.min(PAGE_STEP, flatList.length - shownCount)} из {flatList.length - shownCount}
                    </Button>
                  )}
                </>
              ) : (
                groups.map(({ key, category, items }) => (
                  <div key={key} className="grid gap-3">
                    <div className="mt-2 flex items-center gap-3 first:mt-0">
                      <CategoryBadge specialization={category.specialization} grade={category.grade} variant="outline" />
                      <span className="h-px flex-1 bg-border-subtle" aria-hidden />
                      <span className="font-mono text-xs text-muted-foreground">
                        {items.length} {plural(items.length, ["кандидат", "кандидата", "кандидатов"])}
                      </span>
                    </div>
                    {items.slice(0, GROUP_PREVIEW).map(renderRow)}
                    {items.length > GROUP_PREVIEW && (
                      <Button variant="ghost" className="h-11 border border-border" onClick={() => selectCategory(key)}>
                        Показать ещё {items.length - GROUP_PREVIEW} в {category.label}
                      </Button>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {data && data.unconfirmed.length > 0 && (
            <section aria-labelledby="unconfirmed-title" className="space-y-3 border-t border-dashed pt-6">
              <div className="space-y-1">
                <h3 id="unconfirmed-title" className="flex flex-wrap items-center gap-2 font-mono text-base font-bold">
                  <ShieldQuestion className="size-4 text-muted-foreground" aria-hidden />
                  Без подтверждённого грейда
                  <span className="font-medium text-muted-foreground">
                    {data.unconfirmed.length}
                    {data.unconfirmed_total > data.unconfirmed.length && ` из ${data.unconfirmed_total}`}
                  </span>
                </h3>
                <p className="text-xs text-muted-foreground">
                  Специализация совпадает, но тест грейд не подтвердил. Показываем после всех кандидатов с категорией:
                  категория и результат теста в score не учтены.
                </p>
              </div>
              <div className={cn("grid gap-3 transition-opacity", recs.isPlaceholderData && "opacity-60")}>
                {data.unconfirmed.map(renderRow)}
              </div>
            </section>
          )}

          {data && data.out_of_filter.length > 0 && (
            <div className="rounded-[10px] border border-dashed">
              <button
                type="button"
                onClick={() => setOutOfFiltersOpen((open) => !open)}
                aria-expanded={outOfFiltersOpen}
                className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
              >
                <span>
                  <span className="font-mono font-bold">Вне фильтров · {data.out_of_filter.length}</span>
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
                  {data.out_of_filter.map((match) => (
                    <li key={match.candidate.id} className="flex flex-wrap items-start gap-3 px-5 py-3">
                      <ScoreTile score={match.score} size="sm" />
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            to={candidateHref(match.candidate.id, need.id)}
                            className="font-mono text-sm font-bold hover:text-primary"
                          >
                            {match.candidate.display_name}
                          </Link>
                          <CandidateCategoryBadge candidate={match.candidate} />
                        </div>
                        <ul className="space-y-0.5">
                          {(match.out_of_filter_reasons ?? []).map((reason) => (
                            <li key={reason} className="flex items-center gap-2 text-sm text-muted-foreground">
                              <span className="size-1.5 shrink-0 rounded-full bg-destructive" aria-hidden />
                              {reason}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <Button
                        variant={match.shortlisted ? "default" : "outline"}
                        size="sm"
                        onClick={() => toggleShortlist(match)}
                        disabled={pendingShortlistId === match.candidate.id}
                        aria-pressed={match.shortlisted}
                      >
                        <Pin /> {match.shortlisted ? "В шорт-листе" : "В шорт-лист"}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>

        <aside aria-label="Шорт-лист и ожидания категории" className="flex min-w-0 flex-[1_1_280px] flex-col gap-4">
          <section aria-labelledby="shortlist-title" className="flex flex-col gap-3 rounded-[10px] border bg-card p-5">
            <div className="flex items-center justify-between gap-2">
              <h3 id="shortlist-title" className="flex items-center gap-2 font-mono text-base font-semibold tracking-tight">
                <Pin className="size-4 text-primary" aria-hidden /> Шорт-лист
              </h3>
              <span className="grid h-[22px] min-w-[22px] place-items-center rounded-full bg-primary-tint px-1.5 font-mono text-xs font-semibold text-accent-foreground">
                {data ? data.shortlist.length + data.shortlist_outside.length : need.stats.shortlisted}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">Закреплён за потребностью: не меняется при смене фильтров и правке.</p>
            {recs.isPending ? (
              <Skeleton className="h-12 w-full" />
            ) : !data || data.shortlist.length + data.shortlist_outside.length === 0 ? (
              <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
                Нажмите на булавку у кандидата, чтобы закрепить его здесь.
              </p>
            ) : (
              <ul className="grid gap-2">
                {data.shortlist.map((match) => (
                  <li key={match.candidate.id} className="flex items-center gap-2.5 rounded-lg bg-muted p-2">
                    <ScoreTile score={match.score} tone="card" size="sm" />
                    <Link
                      to={candidateHref(match.candidate.id, need.id)}
                      className="min-w-0 flex-1 font-mono text-sm font-semibold hover:text-primary"
                    >
                      <span className="block truncate">{match.candidate.display_name}</span>
                      <span className="block font-mono text-xs font-normal text-muted-foreground">
                        {candidateCategoryLabel(match.candidate)}
                      </span>
                    </Link>
                    {!invited.has(match.candidate.id) && !openInvitation(match.invitation_status) && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="text-primary"
                        onClick={() => setInviteTarget(match)}
                        disabled={limitReached}
                        aria-label={`Пригласить ${match.candidate.display_name}`}
                      >
                        <Send />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-muted-foreground"
                      onClick={() => shortlist.mutate({ add: false, candidateId: match.candidate.id })}
                      disabled={pendingShortlistId === match.candidate.id}
                      aria-label={`Убрать ${match.candidate.display_name} из шорт-листа`}
                    >
                      <X />
                    </Button>
                  </li>
                ))}
                {data.shortlist_outside.map((brief) => (
                  <li key={brief.id} className="flex items-center gap-2.5 rounded-lg border border-dashed p-2">
                    <Link
                      to={candidateHref(brief.id, need.id)}
                      className="min-w-0 flex-1 font-mono text-sm font-semibold hover:text-primary"
                    >
                      <span className="block truncate">{brief.display_name}</span>
                      <span className="block font-mono text-xs font-normal text-muted-foreground">
                        {candidateCategoryLabel(brief)} · не подходит под новые требования
                      </span>
                    </Link>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-muted-foreground"
                      onClick={() => shortlist.mutate({ add: false, candidateId: brief.id })}
                      disabled={pendingShortlistId === brief.id}
                      aria-label={`Убрать ${brief.display_name} из шорт-листа`}
                    >
                      <X />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            <FormAlert message={shortlist.isError ? `Шорт-лист не сохранён: ${apiError(shortlist.error).message}` : null} />
          </section>

          <SalaryCoverageCard need={need} />
        </aside>
      </div>

      <InviteDialog
        key={inviteTarget?.candidate.id ?? "none"}
        open={inviteTarget !== null}
        onOpenChange={(open) => !open && setInviteTarget(null)}
        candidate={inviteTarget?.candidate ?? null}
        need={need}
        match={inviteTarget}
        onSent={(invitation) => {
          setInvited((current) => new Map(current).set(invitation.candidate.id, invitation.status));
          setLastInvited(invitation.candidate.display_name);
        }}
      />
    </div>
  );
}

interface CandidateGroup {
  key: string;
  category: NonNullable<CandidateBrief["category"]>;
  items: CandidateMatch[];
}

/** Группы в порядке рекомендованных категорий; порядок внутри группы — как прислал backend. */
function groupCandidates(candidates: CandidateMatch[], categories: CategoryRecommendation[]): CandidateGroup[] {
  const order = categories.map((item) => groupKey(item.category));
  const byKey = new Map<string, CandidateGroup>();
  for (const match of candidates) {
    // В основном списке только кандидаты с категорией; без подтверждённого грейда — отдельный блок
    const category = match.candidate.category;
    if (!category) continue;
    const key = groupKey(category);
    const group = byKey.get(key) ?? { key, category, items: [] };
    group.items.push(match);
    byKey.set(key, group);
  }
  const rank = (key: string) => {
    const index = order.indexOf(key);
    return index === -1 ? order.length : index;
  };
  return [...byKey.values()].sort((a, b) => rank(a.key) - rank(b.key));
}

/** Рекомендованная категория как переключатель-фильтр списка: число, ФСП и покрытие вилки одной полосой. */
function CategoryTab({
  category,
  active,
  onSelect,
}: {
  category: CategoryRecommendation;
  active: boolean;
  onSelect: () => void;
}) {
  const coverage = category.salary_coverage === null ? null : toPercent(category.salary_coverage);
  const fit = CATEGORY_FIT_LABELS[category.fit] ?? category.fit;
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onSelect}
      title={category.reason}
      className={cn(
        "relative flex shrink-0 items-center gap-2 rounded-full border text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
        "h-11 px-3.5 sm:h-auto sm:flex-col sm:items-stretch sm:rounded-[10px] sm:px-3.5 sm:py-3",
        active ? "border-2 border-primary bg-primary-tint" : "border-border bg-card hover:bg-muted/60",
      )}
    >
      <span className="font-mono text-[13px] leading-4 font-semibold whitespace-nowrap text-accent-foreground">
        {category.category.label}
      </span>
      <span className="flex items-baseline gap-1.5">
        <span className="font-mono text-[13px] font-semibold tabular-nums sm:text-xl">{category.candidates_count}</span>
        <span className="text-xs text-muted-foreground max-sm:sr-only">
          <span className="sr-only">{plural(category.candidates_count, ["кандидат", "кандидата", "кандидатов"])} </span>·{" "}
          {category.with_fsp_count} с ФСП
        </span>
      </span>
      {coverage !== null && (
        <span className={cn("h-1 rounded-full max-sm:hidden", active ? "bg-card" : "bg-muted")} aria-hidden>
          <span className="block h-1 rounded-full bg-primary" style={{ width: `${coverage}%` }} />
        </span>
      )}
      <span className="text-xs text-muted-foreground max-sm:sr-only">
        {fit.toLowerCase()}
        {coverage !== null && ` · вилка ${coverage}%`}
      </span>
    </button>
  );
}

function ViewSwitch({
  value,
  onChange,
  total,
}: {
  value: "category" | "none";
  onChange: (value: "category" | "none") => void;
  total?: number;
}) {
  const options = [
    { value: "category" as const, label: "По категориям" },
    { value: "none" as const, label: total != null ? `Общий топ · ${total}` : "Общий топ" },
  ];
  return (
    <div role="group" aria-label="Порядок списка" className="flex h-11 gap-0.5 rounded-[10px] bg-muted p-[3px] sm:h-9">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "rounded-lg px-2.5 font-mono text-[13px] font-medium outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 sm:px-3",
            value === option.value ? "bg-card text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

const chipClass = (active: boolean) =>
  cn(
    "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] font-medium transition-colors outline-none",
    "focus-visible:ring-[3px] focus-visible:ring-ring/40 has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/40",
    active ? "border-primary bg-primary-tint text-accent-foreground" : "border-border hover:bg-muted/60",
  );

const chipInputClass = (width: string) =>
  cn(
    "h-7 rounded-none border-0 bg-transparent p-0 text-[13px] shadow-none focus-visible:ring-0 dark:bg-transparent",
    "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
    width,
  );

/** Флажок-чип: role=checkbox, чтобы фильтр читался и переключался как флажок. */
function ToggleChip({
  checked,
  onChange,
  title,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  title?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      title={title}
      onClick={() => onChange(!checked)}
      className={chipClass(checked)}
    >
      {checked && <Check className="size-3.5" aria-hidden />}
      {children}
    </button>
  );
}

function SelectChip({
  label,
  ariaLabel,
  active,
  value,
  onChange,
  children,
}: {
  label: string;
  ariaLabel?: string;
  active: boolean;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <span className={cn(chipClass(active), "relative pr-7")}>
      <span aria-hidden>{label}:</span>
      <select
        aria-label={ariaLabel ?? label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="cursor-pointer appearance-none bg-transparent text-[13px] font-medium outline-none [&>option]:bg-popover [&>option]:text-popover-foreground"
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 size-3.5 text-muted-foreground" aria-hidden />
    </span>
  );
}

function InputChip({
  label,
  ariaLabel,
  active,
  suffix,
  children,
}: {
  label: string;
  ariaLabel: string;
  active: boolean;
  suffix?: string;
  children: ReactNode;
}) {
  return (
    <span className={chipClass(active)} title={ariaLabel}>
      <span aria-hidden>{label}:</span>
      {children}
      {suffix && <span aria-hidden>{suffix}</span>}
    </span>
  );
}

/** Сводка потребности одной карточкой: категория, вилка, покрытие, приглашения и строка стека. На телефоне свёрнута. */
function NeedSummary({ need, activeInvites, inviteLimit }: { need: Need; activeInvites: number; inviteLimit: number }) {
  const [open, setOpen] = useState(false);
  const industries = useIndustries();
  const catalog = useSkillCatalog();
  const coverage = useSalaryCoverage(need.id);
  const skillName = (id: string) => catalog.data?.find((skill) => skill.id === id)?.name ?? id;
  const industry = need.industry
    ? (industries.data?.find((item) => item.slug === need.industry)?.name ?? need.industry)
    : null;
  const meta = [industry, need.work_format ? WORK_FORMAT_LABELS[need.work_format] : null, need.city].filter(Boolean);
  const required = need.required_skills ?? [];
  const optional = need.optional_skills ?? [];
  const percent = coverage.data ? toPercent(coverage.data.coverage) : null;
  const invitesShare = inviteLimit > 0 ? Math.min(100, (activeInvites / inviteLimit) * 100) : 0;

  return (
    <section aria-label="Сводка потребности" className="flex flex-col gap-3">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="need-summary"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-3 rounded-[10px] border bg-card py-3 pr-3 pl-3.5 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 sm:hidden"
      >
        <span className="flex min-w-0 flex-1 flex-col gap-1.5">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
            <CategoryBadge specialization={need.specialization} grade={need.grade} variant="solid" />
            <SalaryRange from={need.salary_from} to={need.salary_to} className="text-sm font-semibold" />
          </span>
          <span className="text-xs text-muted-foreground">
            {percent !== null && <b className="font-mono text-foreground">покрытие {percent}% · </b>}
            описание, стек, приглашения
          </span>
        </span>
        <ChevronDown className={cn("size-4 shrink-0 transition-transform", open && "rotate-180")} aria-hidden />
      </button>

      <div id="need-summary" className={cn("flex-col gap-3", open ? "flex" : "hidden sm:flex")}>
        {need.team_description && <p className="text-sm text-muted-foreground sm:hidden">{need.team_description}</p>}
        <div className="overflow-hidden rounded-[10px] border bg-card">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(min(220px,100%),1fr))] divide-border-subtle max-sm:divide-y sm:[&>*:not(:last-child)]:border-r sm:[&>*]:border-border-subtle">
            <SummaryCell label="Категория">
              <CategoryBadge specialization={need.specialization} grade={need.grade} variant="solid" size="md" />
              {meta.length > 0 && <span className="text-xs text-muted-foreground">{meta.join(" · ")}</span>}
            </SummaryCell>
            <SummaryCell label="Вилка">
              <span className="font-mono text-lg font-semibold whitespace-nowrap text-primary tabular-nums sm:text-xl">
                {formatNumber(need.salary_from)} – {formatNumber(need.salary_to)} ₽
              </span>
              <span className="text-xs text-muted-foreground">на руки · указана в каждом приглашении</span>
            </SummaryCell>
            <SummaryCell label="Покрытие вилки">
              {coverage.isPending ? (
                <Skeleton className="h-7 w-32" />
              ) : coverage.isError ? (
                <span className="text-xs text-muted-foreground">
                  Не удалось посчитать.{" "}
                  <button type="button" className="text-primary hover:underline" onClick={() => void coverage.refetch()}>
                    Повторить
                  </button>
                </span>
              ) : (
                <>
                  <p className="flex flex-wrap items-baseline gap-x-2 text-xs text-muted-foreground">
                    <b className="font-mono text-xl font-semibold text-foreground tabular-nums">{percent}%</b>
                    ожиданий кандидатов
                  </p>
                  <Bar value={percent ?? 0} />
                  {coverage.data.median_expectation !== null && (
                    <span className="text-xs text-muted-foreground">
                      медиана ожиданий{" "}
                      <b className="font-mono font-semibold whitespace-nowrap text-foreground">
                        {formatNumber(coverage.data.median_expectation)} ₽
                      </b>
                    </span>
                  )}
                </>
              )}
            </SummaryCell>
            <SummaryCell label="Приглашения">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-mono text-xl font-semibold tabular-nums">
                  {activeInvites} / {inviteLimit}
                </span>
                <Link to={`/employer/invitations?need=${need.id}`} className="text-xs font-medium text-primary hover:underline">
                  Все приглашения
                </Link>
              </div>
              <Bar value={invitesShare} />
              <span className="text-xs text-muted-foreground">активных слотов — приглашайте адресно</span>
            </SummaryCell>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border-subtle px-5 py-3.5 sm:px-6">
            <span className="font-mono text-xs font-medium tracking-widest text-muted-foreground uppercase">Стек</span>
            <ul className="flex flex-wrap gap-1.5" aria-label="Стек потребности">
              {required.map((id) => (
                <li
                  key={id}
                  title="Обязательный навык"
                  className="inline-flex h-6 items-center rounded-full bg-primary-tint px-2.5 font-mono text-xs font-medium text-accent-foreground"
                >
                  {skillName(id)}
                </li>
              ))}
              {optional.map((id) => (
                <li
                  key={id}
                  title="Желательный навык"
                  className="inline-flex h-6 items-center rounded-full border px-2.5 font-mono text-xs font-medium"
                >
                  {skillName(id)}
                </li>
              ))}
              {required.length + optional.length === 0 && <li className="text-sm text-muted-foreground">не указан</li>}
            </ul>
            {required.length + optional.length > 0 && (
              <span className="text-xs text-muted-foreground">
                <span className="text-accent-foreground">заливка</span> — обязательный · рамка — желательный
              </span>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function SummaryCell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2.5 px-5 py-4 sm:px-6 sm:py-5">
      <span className="font-mono text-xs font-medium tracking-widest text-muted-foreground uppercase">{label}</span>
      {children}
    </div>
  );
}

function Bar({ value }: { value: number }) {
  return (
    <span className="block h-1.5 rounded-full bg-muted" aria-hidden>
      <span className="block h-1.5 rounded-full bg-primary" style={{ width: `${value}%` }} />
    </span>
  );
}

/** Эта версия уже заменена новой: в списке потребностей только последние версии. */
function OlderVersionNotice({ need }: { need: Need }) {
  const needs = useNeeds();
  if (!needs.data || needs.data.some((item) => item.id === need.id)) return null;
  const newer = needs.data.find((item) => item.parent_id === need.id);
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed px-4 py-3 text-sm">
      <History className="size-4 text-muted-foreground" aria-hidden />
      Это прежняя версия потребности — её подборка только для истории.
      {newer ? (
        <Link to={`/employer/needs/${newer.id}`} className="text-primary underline-offset-4 hover:underline">
          Открыть версию {newer.version}
        </Link>
      ) : (
        <Link to="/employer/needs" className="text-primary underline-offset-4 hover:underline">
          К актуальным потребностям
        </Link>
      )}
    </div>
  );
}

/** Повторно пригласить нельзя, пока приглашение активно или уже принято; после отказа или истечения — можно. */
function openInvitation(status: CandidateMatch["invitation_status"]): string | undefined {
  return status === "sent" || status === "viewed" || status === "accepted" ? status : undefined;
}
