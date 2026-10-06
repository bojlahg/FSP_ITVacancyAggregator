import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  Eye,
  EyeOff,
  FilterX,
  FlaskConical,
  History,
  Layers,
  ListOrdered,
  Loader2,
  Mail,
  Pencil,
  Pin,
  SearchX,
  Send,
  ShieldQuestion,
  SlidersHorizontal,
  Users,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { CandidateCategoryBadge, CategoryBadge } from "@/components/CategoryBadge";
import { CandidateRow } from "@/components/employer/CandidateRow";
import { CommitInput } from "@/components/employer/CommitInput";
import { InviteDialog } from "@/components/employer/InviteDialog";
import { SalaryCoverageCard } from "@/components/employer/SalaryCoverageCard";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { NeedTextIssues } from "@/components/employer/NeedTextIssues";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { ScoreBadge } from "@/components/ScoreBadge";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiError } from "@/lib/api-error";
import {
  type CandidateBrief,
  type CandidateMatch,
  type CategoryRecommendation,
  type Need,
  parseId,
  type RecommendationsQuery,
  useIndustries,
  useNeed,
  useNeeds,
  useRecommendations,
  useSetNeedPublished,
  shortlistTarget,
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
  { value: "14", label: "До 2 недель" },
  { value: "30", label: "До месяца" },
  { value: "90", label: "До 3 месяцев" },
];
const FILTER_KEYS = ["grade", "fsp", "verified", "salary", "format", "city", "fresh", "hard"];

const groupKey = (category: { specialization: string; grade: string }) => `${category.specialization}.${category.grade}`;
const groupAnchor = (key: string) => `group-${key.replace(".", "-")}`;
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
  const hasActiveFilters = FILTER_KEYS.some((key) => params.has(key));

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

  const [inviteTarget, setInviteTarget] = useState<CandidateBrief | null>(null);
  const [invited, setInvited] = useState<Map<number, string>>(new Map());
  const [lastInvited, setLastInvited] = useState<string | null>(null);
  const [outOfFiltersOpen, setOutOfFiltersOpen] = useState(false);

  const { invitations_active: activeInvites, invitations_limit: inviteLimit } = need.stats;
  const limitReached = inviteLimit > 0 && activeInvites >= inviteLimit;

  // Клик по рекомендованной категории прокручивает к её группе (после перехода к группировке — когда придут данные).
  const scrollTarget = useRef<string | null>(null);
  const scrollToGroup = (key: string) => {
    const element = document.getElementById(groupAnchor(key));
    if (element && filters.view === "category") {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    scrollTarget.current = key;
    set({ view: null });
  };
  useEffect(() => {
    if (!scrollTarget.current || recs.isPlaceholderData) return;
    const element = document.getElementById(groupAnchor(scrollTarget.current));
    scrollTarget.current = null;
    element?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [recs.data, recs.isPlaceholderData]);

  const toggleShortlist = (match: CandidateMatch) => {
    shortlist.mutate(match.shortlisted ? { add: false, candidateId: match.candidate.id } : { add: true, match });
  };
  const pendingShortlistId = shortlist.isPending && shortlist.variables ? shortlistTarget(shortlist.variables) : undefined;

  const renderRow = (match: CandidateMatch) => {
    const invitedStatus = invited.get(match.candidate.id) ?? openInvitation(match.invitation_status);
    return (
      <CandidateRow
        key={match.candidate.id}
        candidate={match.candidate}
        href={candidateHref(match.candidate.id, need.id)}
        score={match.score}
        explanation={match.explanation.lines}
        acceptance={match.acceptance}
        salaryTo={need.salary_to}
        shortlisted={match.shortlisted}
        shortlistPending={pendingShortlistId === match.candidate.id}
        onToggleShortlist={() => toggleShortlist(match)}
        explanationLimit={3}
        actions={
          <>
            {invitedStatus ? (
              <Button size="sm" variant="secondary" disabled>
                <CheckCircle2 /> {invitedStatus === "accepted" ? "Приглашение принято" : "Приглашение отправлено"}
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => setInviteTarget(match.candidate)}
                disabled={limitReached}
                title={limitReached ? "Все слоты приглашений по потребности заняты" : undefined}
              >
                <Send /> Пригласить
              </Button>
            )}
            <Button asChild size="sm" variant="ghost">
              <Link to={candidateHref(match.candidate.id, need.id)}>Карточка и полное объяснение</Link>
            </Button>
          </>
        }
      />
    );
  };

  const data = recs.data;
  const groups = data ? groupCandidates(data.candidates, data.categories) : [];

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-3 mb-2">
        <Link to="/employer/needs">
          <ArrowLeft /> Потребности
        </Link>
      </Button>

      <PageHeader
        eyebrow={
          <span className="inline-flex flex-wrap items-center gap-2">
            Подборка · версия {need.version}
            {need.published && <Badge variant="soft">опубликована как вакансия</Badge>}
            {need.status !== "active" && <Badge variant="muted">{NEED_STATUS_LABELS[need.status]}</Badge>}
          </span>
        }
        title={need.title}
        description={
          need.team_description ??
          "Рекомендованные категории и кандидаты, ранжированные по совпадению с потребностью. Каждое число объяснено тем же кодом, которым посчитан score."
        }
        actions={
          <>
            {need.parent_id !== null && (
              <Button asChild variant="ghost" size="sm">
                <Link to={`/employer/needs/${need.parent_id}`}>
                  <History /> Версия {need.version - 1}
                </Link>
              </Button>
            )}
            <Button asChild variant="ghost" size="sm">
              <Link to={`/employer/invitations?need=${need.id}`}>
                <Mail /> Приглашения
              </Link>
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link to={`/employer/vacancy-test?need=${need.id}`}>
                <FlaskConical /> Проверка под вакансию
              </Link>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => publish.mutate(!need.published)}
              disabled={publish.isPending}
            >
              {publish.isPending ? <Loader2 className="animate-spin" /> : need.published ? <EyeOff /> : <Eye />}
              {need.published ? "Снять вакансию" : "Опубликовать как вакансию"}
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to={`/employer/needs/${need.id}/edit`}>
                <Pencil /> Изменить потребность
              </Link>
            </Button>
          </>
        }
      />

      <FormAlert message={publish.isError ? apiError(publish.error).message : null} className="mb-4" />
      <NeedTextIssues issues={need.text_issues ?? []} className="mb-4" />
      <OlderVersionNotice need={need} />

      <div className="mb-8 grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <NeedSummary need={need} activeInvites={activeInvites} inviteLimit={inviteLimit} />
        <SalaryCoverageCard need={need} />
      </div>

      {/* Уровень 1: рекомендованные категории */}
      <section className="mb-8" aria-labelledby="rec-categories">
        <h2 id="rec-categories" className="mb-3 text-lg font-extrabold">
          Рекомендованные категории
        </h2>
        {recs.isPending ? (
          <SkeletonCards count={3} className="md:grid-cols-3" />
        ) : recs.isError ? null : data && data.categories.length === 0 ? (
          <p className="rounded-xl border border-dashed px-5 py-6 text-sm text-muted-foreground">
            В базе пока нет кандидатов в подходящих категориях.
          </p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data?.categories.map((category) => (
              <CategoryCard key={groupKey(category.category)} category={category} onSelect={scrollToGroup} />
            ))}
          </div>
        )}
      </section>

      {/* Уровень 2: кандидаты */}
      <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* Своя прокрутка: фильтры длиннее экрана, а колонка «прилипает» */}
        <aside className="grid content-start gap-4 lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:self-start lg:overflow-y-auto lg:overscroll-contain lg:pr-1">
          <Card className="gap-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Pin className="size-4 text-primary" aria-hidden /> Шорт-лист
                <Badge variant="soft" className="ml-auto">
                  {data ? data.shortlist.length + data.shortlist_outside.length : need.stats.shortlisted}
                </Badge>
              </CardTitle>
              <CardDescription>Закреплён за потребностью: не меняется при смене фильтров и правке.</CardDescription>
            </CardHeader>
            <CardContent>
              {recs.isPending ? (
                <SkeletonCards count={1} />
              ) : !data || data.shortlist.length + data.shortlist_outside.length === 0 ? (
                <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
                  Нажмите «В шорт-лист» у кандидата, чтобы закрепить его здесь.
                </p>
              ) : (
                <ul className="grid gap-2">
                  {data.shortlist.map((match) => (
                    <li key={match.candidate.id} className="flex items-center gap-2 rounded-lg bg-muted/60 px-2 py-1.5">
                      <ScoreBadge score={match.score} size="sm" />
                      <Link
                        to={candidateHref(match.candidate.id, need.id)}
                        className="min-w-0 flex-1 truncate text-sm font-medium hover:text-primary"
                      >
                        {match.candidate.display_name}
                        <span className="block truncate font-mono text-[11px] text-muted-foreground">
                          {candidateCategoryLabel(match.candidate)}
                        </span>
                      </Link>
                      {!invited.has(match.candidate.id) && !openInvitation(match.invitation_status) && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="size-7"
                          onClick={() => setInviteTarget(match.candidate)}
                          disabled={limitReached}
                          aria-label={`Пригласить ${match.candidate.display_name}`}
                        >
                          <Send />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="size-7"
                        onClick={() => shortlist.mutate({ add: false, candidateId: match.candidate.id })}
                        disabled={pendingShortlistId === match.candidate.id}
                        aria-label={`Убрать ${match.candidate.display_name} из шорт-листа`}
                      >
                        <X />
                      </Button>
                    </li>
                  ))}
                  {data.shortlist_outside.map((brief) => (
                    <li key={brief.id} className="flex items-center gap-2 rounded-lg border border-dashed px-2 py-1.5">
                      <Link
                        to={candidateHref(brief.id, need.id)}
                        className="min-w-0 flex-1 truncate text-sm font-medium hover:text-primary"
                      >
                        {brief.display_name}
                        <span className="block truncate font-mono text-[11px] text-muted-foreground">
                          {candidateCategoryLabel(brief)} · не подходит под новые требования
                        </span>
                      </Link>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="size-7"
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
              <FormAlert
                message={shortlist.isError ? `Шорт-лист не сохранён: ${apiError(shortlist.error).message}` : null}
                className="mt-3"
              />
            </CardContent>
          </Card>

          <Card className="gap-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SlidersHorizontal className="size-4 text-primary" aria-hidden /> Фильтры
              </CardTitle>
              <CardDescription>Поверх подборки, без потери результата. Состояние — в адресе страницы.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-3">
                <label className="flex items-center gap-3 text-sm">
                  <Checkbox checked={filters.fsp} onChange={(event) => set({ fsp: event.target.checked })} />
                  Есть достижения ФСП
                </label>
                <label className="flex items-center gap-3 text-sm">
                  <Checkbox checked={filters.verified} onChange={(event) => set({ verified: event.target.checked })} />
                  Только навыки, проверенные тестом
                </label>
                <label className="flex items-start gap-3 text-sm">
                  <Checkbox
                    className="mt-0.5"
                    checked={filters.hard}
                    onChange={(event) => set({ hard: event.target.checked ? null : "0" })}
                  />
                  <span>
                    Жёсткие условия потребности
                    <span className="block text-xs text-muted-foreground">формат, город, ожидания выше вилки на 30%+</span>
                  </span>
                </label>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="filter-grade">Грейд</Label>
                <Select id="filter-grade" value={filters.grade ?? ""} onChange={(event) => set({ grade: event.target.value })}>
                  <option value="">Все рекомендованные</option>
                  {(grades.data ?? GRADES.map((slug) => ({ slug, name: slug }))).map((grade) => (
                    <option key={grade.slug} value={grade.slug}>
                      {grade.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="filter-salary">Ожидания не выше, ₽ на руки</Label>
                <CommitInput
                  id="filter-salary"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  step={10000}
                  placeholder="например, 250000"
                  value={filters.salary ? String(filters.salary) : ""}
                  onCommit={(value) => set({ salary: intParam(value) ?? null })}
                />
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto w-fit p-0"
                  onClick={() => set({ salary: need.salary_to })}
                >
                  в пределах вилки (до {formatNumber(need.salary_to)} ₽)
                </Button>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="filter-format">Формат работы</Label>
                <Select
                  id="filter-format"
                  value={filters.format ?? ""}
                  onChange={(event) => set({ format: event.target.value })}
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
                <Label htmlFor="filter-city">Город</Label>
                <CommitInput
                  id="filter-city"
                  placeholder="Любой"
                  value={filters.city}
                  onCommit={(value) => set({ city: value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="filter-fresh">Свежесть результата</Label>
                <Select
                  id="filter-fresh"
                  value={filters.fresh ? String(filters.fresh) : ""}
                  onChange={(event) => set({ fresh: event.target.value })}
                >
                  <option value="">Любая</option>
                  {FRESH_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </div>
              <Button variant="ghost" size="sm" onClick={() => reset(["view"])} disabled={!hasActiveFilters}>
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
              {data && (
                <span className="font-mono text-base font-medium text-muted-foreground">
                  {data.candidates.length}
                  {data.total > data.candidates.length && ` из ${data.total}`}
                </span>
              )}
              {recs.isFetching && !recs.isPending && (
                <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Обновляем подборку" />
              )}
            </h2>
            <Tabs value={filters.view} onValueChange={(value) => set({ view: value === "none" ? "top" : null })}>
              <TabsList>
                {/* Переключатель вида без панелей — без aria-controls на несуществующую панель */}
                <TabsTrigger value="category" aria-controls={undefined}>
                  <Layers /> По категориям
                </TabsTrigger>
                <TabsTrigger value="none" aria-controls={undefined}>
                  <ListOrdered /> Общий топ
                </TabsTrigger>
              </TabsList>
            </Tabs>
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
                  <Button variant="outline" onClick={() => reset(["view"])}>
                    <FilterX /> Сбросить фильтры
                  </Button>
                )
              }
            />
          ) : (
            <div className={cn("transition-opacity", recs.isPlaceholderData && "opacity-60")}>
              {filters.view === "none" ? (
                <div className="grid gap-3">{data?.candidates.map(renderRow)}</div>
              ) : (
                <div className="space-y-6">
                  {groups.map(({ key, category, items }) => (
                    <div key={key} id={groupAnchor(key)} className="scroll-mt-6 space-y-3">
                      <div className="flex items-center gap-3">
                        <CategoryBadge specialization={category.specialization} grade={category.grade} variant="outline" />
                        <span className="h-px flex-1 bg-border-subtle" aria-hidden />
                        <span className="font-mono text-xs text-muted-foreground">
                          {items.length} {plural(items.length, ["кандидат", "кандидата", "кандидатов"])}
                        </span>
                      </div>
                      <div className="grid gap-3">{items.map(renderRow)}</div>
                    </div>
                  ))}
                </div>
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
            <div className="rounded-xl border border-dashed">
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
                      <ScoreBadge score={match.score} size="sm" />
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
      </div>

      <InviteDialog
        key={inviteTarget?.id ?? "none"}
        open={inviteTarget !== null}
        onOpenChange={(open) => !open && setInviteTarget(null)}
        candidate={inviteTarget}
        need={need}
        onSent={(invitation) => {
          setInvited((current) => new Map(current).set(invitation.candidate.id, invitation.status));
          setLastInvited(invitation.candidate.display_name);
        }}
      />
    </>
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

function CategoryCard({
  category,
  onSelect,
}: {
  category: CategoryRecommendation;
  onSelect: (key: string) => void;
}) {
  const exact = category.fit === "exact";
  const coverage = category.salary_coverage === null ? null : toPercent(category.salary_coverage);
  return (
    <button
      type="button"
      onClick={() => onSelect(groupKey(category.category))}
      className={cn(
        "flex flex-col gap-3 rounded-xl border bg-card p-4 text-left transition-[box-shadow,border-color] outline-none hover:shadow-md focus-visible:ring-[3px] focus-visible:ring-ring/40",
        exact && "border-primary ring-1 ring-primary/30",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <CategoryBadge
          specialization={category.category.specialization}
          grade={category.category.grade}
          variant={exact ? "solid" : "outline"}
          size="md"
        />
        <span
          className={cn(
            "text-right font-mono text-[11px] font-medium tracking-wide uppercase",
            exact ? "text-primary" : "text-muted-foreground",
          )}
        >
          {CATEGORY_FIT_LABELS[category.fit] ?? category.fit}
        </span>
      </div>
      <div className="flex items-end gap-5">
        <div>
          <div className="font-mono text-2xl font-extrabold tabular-nums">{category.candidates_count}</div>
          <div className="text-xs text-muted-foreground">
            {plural(category.candidates_count, ["кандидат", "кандидата", "кандидатов"])}
          </div>
        </div>
        <div>
          <div className="font-mono text-2xl font-extrabold tabular-nums">{category.with_fsp_count}</div>
          <div className="text-xs text-muted-foreground">с ФСП</div>
        </div>
        {coverage !== null && (
          <div className="flex-1">
            <div className="mb-1 text-right font-mono text-xs font-bold tabular-nums">{coverage}%</div>
            <Progress value={coverage} className="h-1.5" aria-label="Покрытие вилки" />
            <div className="mt-1 text-right text-[11px] text-muted-foreground">покрытие вилки</div>
          </div>
        )}
      </div>
      <p className="text-sm text-muted-foreground">{category.reason}</p>
    </button>
  );
}

function NeedSummary({ need, activeInvites, inviteLimit }: { need: Need; activeInvites: number; inviteLimit: number }) {
  const industries = useIndustries();
  const catalog = useSkillCatalog();
  const skillName = (id: string) => catalog.data?.find((skill) => skill.id === id)?.name ?? id;
  const industry = need.industry
    ? (industries.data?.find((item) => item.slug === need.industry)?.name ?? need.industry)
    : null;
  const meta = [industry, need.work_format ? WORK_FORMAT_LABELS[need.work_format] : null, need.city].filter(Boolean);
  const required = need.required_skills ?? [];
  const optional = need.optional_skills ?? [];

  return (
    <Card className="overflow-hidden py-0">
      <div className="grid h-full divide-y divide-border-subtle sm:grid-cols-2 sm:divide-y-0">
        <div className="space-y-2 p-5 sm:border-r sm:border-b sm:border-border-subtle">
          <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Категория</div>
          <CategoryBadge specialization={need.specialization} grade={need.grade} variant="solid" size="md" />
          {meta.length > 0 && <div className="text-xs text-muted-foreground">{meta.join(" · ")}</div>}
        </div>
        <div className="space-y-2 p-5 sm:border-b sm:border-border-subtle">
          <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Вилка</div>
          <SalaryRange from={need.salary_from} to={need.salary_to} className="text-xl text-primary" />
          <div className="text-xs text-muted-foreground">указана в каждом приглашении</div>
        </div>
        <div className="space-y-2 p-5 sm:border-r sm:border-border-subtle">
          <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Стек</div>
          <div className="flex flex-wrap gap-1.5">
            {required.map((id) => (
              <Badge key={id} variant="soft" title="Обязательный навык">
                {skillName(id)}
              </Badge>
            ))}
            {optional.map((id) => (
              <Badge key={id} variant="muted" title="Желательный навык">
                {skillName(id)}
              </Badge>
            ))}
            {required.length + optional.length === 0 && <span className="text-sm text-muted-foreground">не указан</span>}
          </div>
          <div className="text-xs text-muted-foreground">
            <span className="text-primary">обязательный</span> · желательный
          </div>
        </div>
        <div className="space-y-2 p-5">
          <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Приглашения</div>
          <div className="font-mono text-xl font-extrabold tabular-nums">
            {activeInvites}
            <span className="text-muted-foreground"> / {inviteLimit}</span>
          </div>
          <Progress
            value={inviteLimit > 0 ? (activeInvites / inviteLimit) * 100 : 0}
            className="h-1.5"
            aria-label="Использовано приглашений"
          />
          <div className="text-xs text-muted-foreground">активных слотов — приглашайте адресно</div>
        </div>
      </div>
    </Card>
  );
}

/** Эта версия уже заменена новой: в списке потребностей только последние версии. */
function OlderVersionNotice({ need }: { need: Need }) {
  const needs = useNeeds();
  if (!needs.data || needs.data.some((item) => item.id === need.id)) return null;
  const newer = needs.data.find((item) => item.parent_id === need.id);
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-dashed px-4 py-3 text-sm">
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
