import { ArrowRight, Lightbulb, ShieldCheck, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { SalaryRange } from "@/components/SalaryRange";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import { formatNumber, plural, toPercent } from "@/lib/format";
import { type CandidateMarket, type MarketSkill, type MarketSuggestion, useMyMarket } from "@/lib/market-queries";
import { cn } from "@/lib/utils";

/** «Рынок вашей категории»: агрегаты по действующим потребностям, без названий компаний (§8.5). */
export function MarketCard({ className }: { className?: string }) {
  const market = useMyMarket();

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="size-4 text-primary" aria-hidden /> Рынок вашей категории
        </CardTitle>
        <CardDescription>
          Сколько компаний ищут людей вашей категории, какие у них вилки и навыки. Только сводные цифры — без
          названий компаний.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {market.isPending ? (
          <MarketSkeleton />
        ) : market.isError ? (
          <ErrorState
            variant="block"
            title="Не удалось загрузить рынок."
            description={apiError(market.error).message}
            onRetry={() => void market.refetch()}
          />
        ) : (
          <MarketBody market={market.data} />
        )}
      </CardContent>
    </Card>
  );
}

function MarketBody({ market }: { market: CandidateMarket }) {
  const count = (fit: string) => market.groups.find((group) => group.fit === fit);
  const exact = count("exact");
  const nearby = market.groups.filter((group) => group.fit !== "exact").reduce((sum, group) => sum + group.needs, 0);

  if ((exact?.needs ?? 0) + nearby === 0) {
    return (
      <EmptyState
        icon={TrendingUp}
        title="Потребностей в вашей категории пока нет"
        description="Как только компании начнут искать людей вашей и соседних категорий, здесь появятся вилки и навыки."
        className="py-8"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          value={exact?.needs ?? 0}
          label={`${plural(exact?.needs ?? 0, ["потребность", "потребности", "потребностей"])} в вашей категории`}
          hint={`из них открытых вакансий: ${exact?.vacancies ?? 0}`}
        />
        <Stat value={nearby} label="рядом" hint="соседний грейд и смежные специализации" />
        <Stat
          value={market.matching_needs ?? "—"}
          label="подходят вам по навыкам"
          hint={market.matching_needs == null ? "покажем, когда потребностей станет больше" : "своя и соседние категории"}
        />
      </div>

      {market.suppressed ? (
        <div className="flex gap-3 rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <p>
            Потребностей пока мало — меньше {market.min_needs} от разных компаний. Вилки и навыки покажем, когда их
            станет больше: по одной-двум потребностям можно узнать компанию.
          </p>
        </div>
      ) : (
        <>
          {market.scope === "neighbourhood" && (
            <p className="text-xs text-muted-foreground">
              В вашей категории пока мало потребностей, поэтому вилки и навыки — вместе с соседними категориями (
              {market.scope_needs}).
            </p>
          )}
          <div className="grid gap-6 lg:grid-cols-2">
            {market.salary && <SalaryBlock salary={market.salary} />}
            <SkillsBlock skills={market.skills} />
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ value, label, hint }: { value: number | string; label: string; hint?: string }) {
  return (
    <div className="rounded-xl bg-muted p-4">
      <div className="font-mono text-3xl font-extrabold tabular-nums">{value}</div>
      <div className="text-sm">{label}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const positionCopy: Record<string, string> = {
  below: "ниже медианной вилки — можно смело просить больше",
  within: "внутри медианной вилки",
  above: "выше медианной вилки — подходящих предложений будет меньше",
  unknown: "не указаны — укажите их в профиле, чтобы сравнить",
};

function SalaryBlock({ salary }: { salary: NonNullable<CandidateMarket["salary"]> }) {
  return (
    <section className="space-y-3">
      <h3 className="font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">Зарплата</h3>
      <div>
        <SalaryRange
          from={salary.median_from}
          to={salary.median_to}
          className="text-lg whitespace-normal sm:text-xl sm:whitespace-nowrap"
        />
        <div className="text-xs text-muted-foreground">медианная вилка потребностей</div>
      </div>
      <p className="text-sm">
        Ваши ожидания{salary.candidate_min != null && <> от {formatNumber(salary.candidate_min)} ₽</>} —{" "}
        <span className={cn(salary.position === "above" && "font-semibold")}>{positionCopy[salary.position]}</span>
      </p>
      {salary.covered_share != null && (
        <div className="space-y-1">
          <Bar required={salary.covered_share} optional={0} label="Доля вилок, покрывающих ожидания" />
          <div className="text-xs text-muted-foreground">
            верх вилки покрывает ваши ожидания в {toPercent(salary.covered_share)}% потребностей
          </div>
        </div>
      )}
    </section>
  );
}

const statusBadge: Record<MarketSkill["status"], { label: string; variant: "soft" | "muted" | "outline" | "destructive" }> = {
  verified: { label: "проверено тестом", variant: "soft" },
  fsp_confirmed: { label: "подтверждено ФСП", variant: "soft" },
  task_confirmed: { label: "подтверждено заданием", variant: "soft" },
  declared: { label: "заявлено", variant: "muted" },
  parent_only: { label: "есть базовый навык", variant: "muted" },
  missing: { label: "нет в профиле", variant: "destructive" },
};

function SkillsBlock({ skills }: { skills: MarketSkill[] }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">
          Востребованные навыки
        </h3>
        {skills.length > 0 && <span className="text-xs text-muted-foreground">доля потребностей</span>}
      </div>
      {skills.length === 0 ? (
        <p className="text-sm text-muted-foreground">Потребности не указывают навыков.</p>
      ) : (
        // Строки — подсетка одной сетки: полосы и статусы выровнены по колонкам
        <ul className="space-y-3 sm:grid sm:grid-cols-[minmax(4.5rem,7rem)_minmax(3rem,1fr)_2.5rem_auto] sm:gap-x-3 sm:gap-y-2 sm:space-y-0">
          {skills.map((skill) => {
            const badge = statusBadge[skill.status];
            const share = toPercent(skill.required_share + skill.optional_share);
            return (
              <li
                key={skill.skill_id}
                className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 gap-y-1.5 sm:col-span-4 sm:min-h-8 sm:grid-cols-subgrid sm:gap-y-0"
              >
                <span className="col-start-1 row-start-1 truncate text-sm font-medium" title={skill.name}>
                  {skill.name}
                </span>
                <Bar
                  className="col-span-full row-start-2 sm:col-span-1 sm:col-start-2 sm:row-start-1"
                  required={skill.required_share}
                  optional={skill.optional_share}
                  label={`${skill.name}: обязателен в ${toPercent(skill.required_share)}%, желателен в ${toPercent(skill.optional_share)}%`}
                />
                <span className="col-start-2 row-start-1 text-right font-mono text-xs tabular-nums sm:col-start-3">
                  {share}%
                </span>
                <Badge variant={badge.variant} className="col-start-3 row-start-1 sm:col-start-4">
                  {badge.label}
                </Badge>
              </li>
            );
          })}
        </ul>
      )}
      <div className="flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-primary" aria-hidden /> обязательный
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-primary-pale" aria-hidden /> желательный
        </span>
      </div>
    </section>
  );
}

function Bar({
  required,
  optional,
  label,
  className,
}: {
  required: number;
  optional: number;
  label: string;
  className?: string;
}) {
  return (
    <div className={cn("flex h-1.5 overflow-hidden rounded-full bg-secondary", className)} role="img" aria-label={label}>
      <div className="bg-primary" style={{ width: `${Math.min(100, required * 100)}%` }} />
      <div className="bg-primary-pale" style={{ width: `${Math.min(100, optional * 100)}%` }} />
    </div>
  );
}

/**
 * «Что ещё поможет»: навыки, подтверждение которых добавит подходящих потребностей (§8.5).
 * Показывается в «Следующем шаге» кабинета; данные — из того же запроса, что и «Рынок вашей категории».
 */
export function MarketSuggestions({ className, fallback = null }: { className?: string; fallback?: ReactNode }) {
  const market = useMyMarket();
  if (market.isPending) {
    return (
      <div className={cn("space-y-2", className)} aria-busy="true" aria-label="Загрузка">
        <Skeleton className="h-16 rounded-lg" />
        <Skeleton className="h-8 w-40" />
      </div>
    );
  }
  // Ошибку рынка показывает его собственная карточка ниже — здесь общий совет
  if (market.isError || market.data.suggestions.length === 0) return <>{fallback}</>;
  return <SuggestionsList suggestions={market.data.suggestions} className={className} />;
}

function SuggestionsList({ suggestions, className }: { suggestions: MarketSuggestion[]; className?: string }) {
  return (
    <ul className={cn("grid gap-3", className)}>
      {suggestions.map((suggestion) => (
        <li key={suggestion.skill_id} className="space-y-3">
          <div className="flex items-start gap-2 rounded-lg bg-primary-tint p-3">
            <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <p className="text-sm">{suggestion.text}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestion.action === "confirm" ? (
              <>
                <Button asChild size="sm" variant="outline" className="max-sm:h-11">
                  <Link to="/candidate/tasks">
                    Задания <ArrowRight />
                  </Link>
                </Button>
                <Button asChild size="sm" variant="ghost" className="max-sm:h-11">
                  <Link to="/candidate/grade">Тест</Link>
                </Button>
              </>
            ) : (
              <Button asChild size="sm" variant="outline" className="max-sm:h-11">
                <Link to="/candidate/profile">
                  В профиль <ArrowRight />
                </Link>
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

function MarketSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Загрузка">
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((index) => (
          <Skeleton key={index} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}
