import { zodResolver } from "@hookform/resolvers/zod";
import { Briefcase, Building2, CheckCircle2, FilterX, GraduationCap, Loader2, MapPin, Search, Send, Unlock } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";
import { CategoryBadge } from "@/components/CategoryBadge";
import { CommitInput } from "@/components/employer/CommitInput";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ExplanationList } from "@/components/ExplanationList";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { ScoreBadge } from "@/components/ScoreBadge";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiError } from "@/lib/api-error";
import { WORK_FORMAT_LABELS } from "@/lib/labels";
import { type Grade, useCandidateMe, useGrades, useSpecializations } from "@/lib/testing-queries";
import { enumParam, useUrlFilters } from "@/lib/url-filters";
import { cn } from "@/lib/utils";
import {
  isAlreadyApplied,
  isCategoryRequired,
  type Vacancy,
  type VacanciesQuery,
  useApply,
  useVacancies,
} from "@/lib/vacancy-queries";

const GRADES: readonly Grade[] = ["intern", "junior", "middle", "senior"];
const FILTER_KEYS = ["q", "spec", "grade"];
const COVER_NOTE_MAX = 2000;
const EXPLANATION_PREVIEW = 4;

export default function CandidateVacanciesPage() {
  const { params, set, reset } = useUrlFilters();
  const specializations = useSpecializations();
  const grades = useGrades();
  const me = useCandidateMe();
  const [applying, setApplying] = useState<Vacancy | null>(null);

  const filters = {
    q: params.get("q") ?? "",
    spec: params.get("spec") ?? "",
    grade: enumParam(params.get("grade"), GRADES),
  };
  const hasActiveFilters = FILTER_KEYS.some((key) => params.has(key));
  const query: VacanciesQuery = {
    match: true,
    ...(filters.q && { q: filters.q }),
    ...(filters.spec && { specialization: filters.spec }),
    ...(filters.grade && { grade: filters.grade }),
  };
  const vacancies = useVacancies(query);
  const noCategory = me.data !== undefined && me.data.category === null;

  return (
    <>
      <PageHeader
        eyebrow="Вакансии"
        title="Вакансии"
        description="Классический путь: откликайтесь сами. Сначала показываем вакансии под вашу категорию — с тем же объяснением совпадения, что видит работодатель."
      />

      {noCategory && <NoCategoryNotice className="mb-6" />}

      <div className="mb-6 grid gap-3 md:grid-cols-[minmax(0,1fr)_200px_160px_auto] md:items-end">
        <div className="grid gap-2">
          <Label htmlFor="vacancies-q">Поиск</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <CommitInput
              id="vacancies-q"
              type="search"
              className="pl-9"
              placeholder="Название или навык, например Python"
              value={filters.q}
              onCommit={(value) => set({ q: value })}
            />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="vacancies-spec">Специализация</Label>
          <Select id="vacancies-spec" value={filters.spec} onChange={(event) => set({ spec: event.target.value })}>
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
          <Label htmlFor="vacancies-grade">Грейд</Label>
          <Select id="vacancies-grade" value={filters.grade ?? ""} onChange={(event) => set({ grade: event.target.value })}>
            <option value="">Любой</option>
            {(grades.data ?? GRADES.map((slug) => ({ slug, name: slug }))).map((grade) => (
              <option key={grade.slug} value={grade.slug}>
                {grade.name}
              </option>
            ))}
          </Select>
        </div>
        <Button variant="ghost" onClick={() => reset()} disabled={!hasActiveFilters}>
          <FilterX /> Сбросить
        </Button>
      </div>

      {vacancies.isPending ? (
        <SkeletonCards count={4} className="lg:grid-cols-2" />
      ) : vacancies.isError ? (
        <ErrorState description={apiError(vacancies.error).message} onRetry={() => void vacancies.refetch()} />
      ) : vacancies.data.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title={hasActiveFilters ? "По этим условиям вакансий нет" : "Открытых вакансий пока нет"}
          description={
            hasActiveFilters
              ? "Смягчите фильтры или сбросьте поиск."
              : "Загляните позже — работодатели публикуют новые вакансии каждый день."
          }
          action={
            hasActiveFilters && (
              <Button variant="outline" onClick={() => reset()}>
                <FilterX /> Сбросить фильтры
              </Button>
            )
          }
        />
      ) : (
        <div className={cn("grid gap-4 lg:grid-cols-2", vacancies.isPlaceholderData && "opacity-60")}>
          {vacancies.data.map((vacancy) => (
            <VacancyCard key={vacancy.id} vacancy={vacancy} onApply={() => setApplying(vacancy)} />
          ))}
        </div>
      )}

      <Dialog open={applying !== null} onOpenChange={(open) => !open && setApplying(null)}>
        <DialogContent>
          {applying && <ApplyForm key={applying.id} vacancy={applying} onDone={() => setApplying(null)} />}
        </DialogContent>
      </Dialog>
    </>
  );
}

function NoCategoryNotice({ className }: { className?: string }) {
  return (
    <div
      role="status"
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/30 bg-primary-tint px-4 py-3 text-sm",
        className,
      )}
    >
      <span className="flex items-start gap-2">
        <GraduationCap className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <span>
          Откликаться можно после теста: работодатель сравнивает отклики по категории. Пока у вас нет категории —
          вакансии видны без оценки совпадения.
        </span>
      </span>
      <Button asChild size="sm">
        <Link to="/candidate/onboarding">Пройти тест</Link>
      </Button>
    </div>
  );
}

function VacancyCard({ vacancy, onApply }: { vacancy: Vacancy; onApply: () => void }) {
  const [showAll, setShowAll] = useState(false);
  const lines = vacancy.match_explanation?.lines ?? [];
  const hidden = lines.length - EXPLANATION_PREVIEW;
  const place = [vacancy.city, vacancy.work_format ? WORK_FORMAT_LABELS[vacancy.work_format] : null].filter(Boolean);

  return (
    <Card className={cn(vacancy.applied && "bg-muted/40")}>
      <CardHeader className="grid-cols-[minmax(0,1fr)_auto]">
        <div className="min-w-0 space-y-2">
          <CardTitle className="text-lg">{vacancy.title}</CardTitle>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
              <Building2 className="size-3.5" aria-hidden /> {vacancy.company.company_name}
            </span>
            {place.length > 0 && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="size-3.5" aria-hidden />
                {place.join(" · ")}
              </span>
            )}
          </div>
        </div>
        {vacancy.match_score !== null && vacancy.match_score !== undefined && (
          <ScoreBadge score={vacancy.match_score} className="row-span-2" />
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <CategoryBadge specialization={vacancy.category.specialization} grade={vacancy.category.grade} />
          <SalaryRange from={vacancy.salary_from} to={vacancy.salary_to} />
        </div>
        {lines.length > 0 ? (
          <div>
            <ExplanationList items={lines} limit={showAll ? undefined : EXPLANATION_PREVIEW} />
            {hidden > 0 && (
              <button
                type="button"
                onClick={() => setShowAll((value) => !value)}
                className="mt-1.5 text-xs font-medium text-primary underline-offset-4 hover:underline"
              >
                {showAll ? "Свернуть" : `Ещё ${hidden}`}
              </button>
            )}
          </div>
        ) : (
          vacancy.team_description && <p className="line-clamp-3 text-sm text-muted-foreground">{vacancy.team_description}</p>
        )}
      </CardContent>
      <CardFooter className="mt-auto flex-wrap gap-3 border-t border-border-subtle pt-5">
        {vacancy.applied ? (
          <>
            <Badge variant="soft">
              <CheckCircle2 /> Вы откликнулись
            </Badge>
            <Link to="/candidate/applications" className="text-sm text-primary underline-offset-4 hover:underline">
              Мои отклики
            </Link>
          </>
        ) : (
          <Button onClick={onApply}>
            <Send /> Откликнуться
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}

const applySchema = z.object({
  coverNote: z.string().trim().max(COVER_NOTE_MAX, `Не больше ${COVER_NOTE_MAX} символов`),
});

type ApplyValues = z.infer<typeof applySchema>;

function ApplyForm({ vacancy, onDone }: { vacancy: Vacancy; onDone: () => void }) {
  const apply = useApply();
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<ApplyValues>({ resolver: zodResolver(applySchema), defaultValues: { coverNote: "" } });
  const length = useWatch({ control, name: "coverNote" }).length;

  const onSubmit = (values: ApplyValues) =>
    apply.mutate(
      { vacancyId: vacancy.id, body: { cover_note: values.coverNote || null } },
      { onSuccess: onDone },
    );

  const categoryRequired = apply.isError && isCategoryRequired(apply.error);
  const alreadyApplied = apply.isError && isAlreadyApplied(apply.error);

  return (
    <>
      <DialogHeader>
        <DialogTitle>Отклик на вакансию</DialogTitle>
        <DialogDescription>
          {vacancy.company.company_name}: «{vacancy.title}»
        </DialogDescription>
      </DialogHeader>

      <form id="apply-form" className="grid gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="flex items-start gap-2 rounded-lg border border-primary/30 bg-primary-tint px-3 py-2.5 text-sm" role="note">
          <Unlock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <span>
            <b>Отклик сразу откроет работодателю ваши контакты</b> — имя, email, телефон и Telegram из профиля. Отозвать
            отклик нельзя.
          </span>
        </div>

        {categoryRequired ? (
          <div
            role="alert"
            className="grid gap-2 rounded-md border border-destructive/30 bg-destructive-tint px-3 py-2.5 text-sm"
          >
            <span>
              Откликаться можно после теста: работодатель сравнивает отклики по категории «специализация × грейд».
            </span>
            <Link to="/candidate/onboarding" className="font-medium text-primary underline-offset-4 hover:underline">
              Пройти тест и получить категорию
            </Link>
          </div>
        ) : alreadyApplied ? (
          <FormAlert message="Вы уже откликались на эту вакансию — отклик есть в разделе «Мои отклики»." />
        ) : (
          <FormAlert message={apply.isError ? apiError(apply.error).message : null} />
        )}

        <FormField
          id="apply-cover-note"
          label="Сопроводительный текст"
          error={errors.coverNote?.message}
          hint={`Необязательно · ${length} / ${COVER_NOTE_MAX}`}
        >
          <Textarea
            id="apply-cover-note"
            rows={5}
            maxLength={COVER_NOTE_MAX + 200}
            placeholder="Пара фраз о том, почему вам интересна эта вакансия"
            aria-invalid={!!errors.coverNote}
            aria-describedby={errors.coverNote ? "apply-cover-note-error" : undefined}
            {...register("coverNote")}
          />
        </FormField>
      </form>

      <DialogFooter>
        <DialogClose asChild>
          <Button variant="ghost">{alreadyApplied ? "Закрыть" : "Отмена"}</Button>
        </DialogClose>
        <Button type="submit" form="apply-form" disabled={apply.isPending || categoryRequired || alreadyApplied}>
          {apply.isPending ? <Loader2 className="animate-spin" /> : <Send />} Откликнуться
        </Button>
      </DialogFooter>
    </>
  );
}
