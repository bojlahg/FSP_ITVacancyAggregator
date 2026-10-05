import { zodResolver } from "@hookform/resolvers/zod";
import { BarChart3, Check, Gauge, Loader2, Scale, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { InstanceBody } from "@/components/explainer/InstanceBody";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import {
  type AngoffGrade,
  type AngoffHofsteeValues,
  type AngoffImpact,
  type AngoffRound,
  type AngoffSummary,
  type AngoffTasks,
  useAngoffImpact,
  useAngoffSummary,
  useAngoffTasks,
  useRateAngoff,
  useSaveAngoffHofstee,
  useStartAngoffRound2,
} from "@/lib/expert-queries";
import { useExplainerOverview } from "@/lib/explainer-queries";
import { plural } from "@/lib/format";
import { ITEM_KIND_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

// Modified Angoff, docs/implementation.md §10.4, §12.4: эксперт оценивает P(решит) для минимально компетентного
// кандидата; после раунда 1 видит данные о последствиях и может пересмотреть оценки в раунде 2
const QUICK = [10, 30, 50, 70, 90] as const;
const SAVE_DELAY_MS = 500;

type Task = AngoffTasks["tasks"][number];

export function AngoffTab() {
  const overview = useExplainerOverview();
  const [specialization, setSpecialization] = useState<string>();
  const [grade, setGrade] = useState<AngoffGrade>("middle");
  const spec = specialization ?? overview.data?.specializations[0]?.slug;

  if (overview.isPending) return <SkeletonCards count={2} />;
  if (overview.isError) {
    return <ErrorState description={apiError(overview.error).message} onRetry={() => void overview.refetch()} />;
  }
  const grades = overview.data.grades;
  const gradeName = grades.find((item) => item.grade === grade)?.name ?? grade;

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Пороги грейдов: modified Angoff</CardTitle>
          <CardDescription>
            Представьте минимально компетентного {gradeName}: того, кто только-только дотягивает до уровня. С какой
            вероятностью он решит это задание? Ответ ключа не показываем — оценивайте по сути задания. После раунда 1
            вы увидите, как ваш порог распределит кандидатов по грейдам и где пороги других экспертов, и сможете
            пересмотреть оценки во втором раунде. Действующие пороги сами не меняются.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-[minmax(0,14rem)_1fr] sm:items-end">
          <label className="grid gap-1.5 text-sm">
            <span className="text-muted-foreground">Специализация</span>
            <Select value={spec} onChange={(event) => setSpecialization(event.target.value)}>
              {overview.data.specializations.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.name}
                </option>
              ))}
            </Select>
          </label>
          <div className="grid gap-1.5 text-sm">
            <span className="text-muted-foreground">Граница грейда</span>
            <div className="grid grid-cols-4 gap-1.5" role="radiogroup" aria-label="Граница грейда">
              {grades.map((item) => (
                <Button
                  key={item.grade}
                  role="radio"
                  aria-checked={item.grade === grade}
                  variant={item.grade === grade ? "default" : "outline"}
                  className="px-1"
                  onClick={() => setGrade(item.grade)}
                >
                  {item.name}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
      {spec && <AngoffGradeWork key={`${spec}:${grade}`} specialization={spec} grade={grade} />}
      {spec && <AngoffSummaryCard specialization={spec} />}
    </div>
  );
}

function AngoffGradeWork({ specialization, grade }: { specialization: string; grade: AngoffGrade }) {
  const [round, setRound] = useState<AngoffRound>(1);
  const first = useAngoffTasks(specialization, grade, 1);
  const start = useStartAngoffRound2();
  const round1Complete = first.data?.round1_complete ?? false;

  const openRound2 = () => {
    if (first.data?.round2_started) {
      setRound(2);
      return;
    }
    start.mutate({ specialization, grade }, { onSuccess: () => setRound(2) });
  };

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2" role="radiogroup" aria-label="Раунд оценки">
        <Button
          role="radio"
          aria-checked={round === 1}
          variant={round === 1 ? "default" : "outline"}
          onClick={() => setRound(1)}
        >
          Раунд 1
        </Button>
        <Button
          role="radio"
          aria-checked={round === 2}
          variant={round === 2 ? "default" : "outline"}
          disabled={!round1Complete || start.isPending}
          onClick={openRound2}
        >
          {start.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />}
          Раунд 2
        </Button>
        <span className="text-xs text-muted-foreground">
          {round1Complete
            ? "Раунд 1 пройден: ниже — данные о последствиях; во втором раунде можно пересмотреть оценки"
            : "Раунд 2 и данные о последствиях откроются после оценки всех заданий раунда 1"}
        </span>
      </div>
      <FormAlert message={start.isError ? apiError(start.error).message : null} />
      {round1Complete && <ImpactCard specialization={specialization} grade={grade} />}
      {round1Complete && round === 1 && (
        <div>
          <Button variant="outline" onClick={openRound2} disabled={start.isPending}>
            {first.data?.round2_started ? "Перейти к раунду 2" : "Начать раунд 2 с моими оценками"}
          </Button>
        </div>
      )}
      <AngoffTaskList specialization={specialization} grade={grade} round={round} />
      {first.data && <HofsteeCard specialization={specialization} grade={grade} tasks={first.data} />}
    </div>
  );
}

function AngoffTaskList({
  specialization,
  grade,
  round,
}: {
  specialization: string;
  grade: AngoffGrade;
  round: AngoffRound;
}) {
  const tasks = useAngoffTasks(specialization, grade, round);
  if (tasks.isPending) return <SkeletonCards count={3} />;
  if (tasks.isError) {
    return <ErrorState description={apiError(tasks.error).message} onRetry={() => void tasks.refetch()} />;
  }
  const { progress } = tasks.data;
  if (progress.total === 0) {
    return (
      <EmptyState icon={Gauge} title="Заданий для оценки нет" description="В банке нет шаблонов у этого порога." />
    );
  }
  return (
    <div className="grid gap-4">
      <div className="space-y-1.5">
        <div className="flex justify-between gap-2 text-sm">
          <span className="text-muted-foreground">Оценено заданий в раунде {round}</span>
          <span className="font-mono font-bold tabular-nums">
            {progress.done} / {progress.total}
          </span>
        </div>
        <Progress value={(progress.done / progress.total) * 100} aria-label={`Оценено заданий в раунде ${round}`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {tasks.data.tasks.map((task, index) => (
          <AngoffTaskCard
            key={`${grade}:${round}:${task.template_id}`}
            task={task}
            index={index}
            specialization={specialization}
            grade={grade}
            round={round}
            step={tasks.data.rating_step}
          />
        ))}
      </div>
    </div>
  );
}

function AngoffTaskCard({
  task,
  index,
  specialization,
  grade,
  round,
  step,
}: {
  task: Task;
  index: number;
  specialization: string;
  grade: AngoffGrade;
  round: AngoffRound;
  step: number;
}) {
  const rate = useRateAngoff();
  const saved = task.rating == null ? null : Math.round(task.rating * 100);
  const [draft, setDraft] = useState<number | null>(saved);
  const stepPercent = Math.round(step * 100);

  // Автосохранение ползунка после паузы; быстрые кнопки сохраняют сразу
  useEffect(() => {
    if (draft === null || draft === saved) return;
    const timer = window.setTimeout(() => {
      rate.mutate({
        specialization,
        grade,
        round,
        template_id: task.template_id,
        rating: draft / 100,
      });
    }, SAVE_DELAY_MS);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- rate стабилен по смыслу, не перезапускаем таймер
  }, [draft, saved, specialization, grade, round, task.template_id]);

  const status = rate.isPending ? (
    <Loader2 className="size-4 animate-spin text-primary" aria-label="Сохраняем" />
  ) : saved !== null && draft === saved ? (
    <Check className="size-4 text-primary" aria-label="Сохранено" />
  ) : null;

  return (
    <Card className={cn("gap-3", saved !== null && "border-primary/40")}>
      <CardHeader className="gap-1">
        <div className="flex items-center justify-between gap-2">
          <span className="shrink-0 font-mono text-xs font-bold text-primary">Задание {index + 1}</span>
          <span className="flex flex-wrap items-center justify-end gap-1.5">
            <Badge variant="muted">{task.topic_name}</Badge>
            <Badge variant="outline">{ITEM_KIND_LABELS[task.kind] ?? task.kind}</Badge>
          </span>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="min-w-0">
          <InstanceBody instance={task.instance} kind={task.kind} />
        </div>
        <div className="grid gap-2 rounded-lg bg-muted/60 p-3">
          {round === 2 && (
            <div className="grid gap-1 text-xs text-muted-foreground">
              <span>
                Ваша оценка в раунде 1:{" "}
                <span className="font-mono font-bold text-foreground tabular-nums">{percent(task.round1_rating)}</span>
              </span>
              {task.group ? (
                <span>
                  Группа ({task.group.raters} {plural(task.group.raters, ["эксперт", "эксперта", "экспертов"])}):
                  медиана{" "}
                  <span className="font-mono font-bold text-foreground tabular-nums">{percent(task.group.median)}</span>,
                  от {percent(task.group.low)} до {percent(task.group.high)}
                </span>
              ) : (
                <span>Оценки группы появятся, когда раунд 1 пройдут хотя бы два эксперта</span>
              )}
            </div>
          )}
          <div className="flex items-center justify-between gap-2 text-sm">
            <span>Решит с вероятностью</span>
            <span className="flex items-center gap-2">
              {status}
              <span className="font-mono text-lg font-bold tabular-nums">{draft === null ? "—" : `${draft}%`}</span>
            </span>
          </div>
          <div className="grid grid-cols-5 gap-1.5">
            {QUICK.map((value) => (
              <Button
                key={value}
                size="sm"
                variant={draft === value ? "default" : "outline"}
                className="px-0 font-mono"
                onClick={() => setDraft(value)}
              >
                {value}%
              </Button>
            ))}
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={stepPercent}
            value={draft ?? 50}
            onChange={(event) => setDraft(Number(event.target.value))}
            aria-label={`Вероятность решить задание ${index + 1}, %`}
            className={cn("w-full accent-primary", draft === null && "opacity-50")}
          />
          <FormAlert message={rate.isError ? apiError(rate.error).message : null} />
        </div>
      </CardContent>
    </Card>
  );
}

function percent(value: number | null | undefined, digits = 0) {
  if (value == null) return "—";
  return `${(value * 100).toFixed(digits).replace(".", ",")}%`;
}

function fmt(value: number | null | undefined, digits = 2) {
  if (value == null) return "—";
  return (value > 0 ? "+" : value < 0 ? "−" : "") + Math.abs(value).toFixed(digits);
}

function ImpactCard({ specialization, grade }: { specialization: string; grade: AngoffGrade }) {
  const impact = useAngoffImpact(specialization, grade, true);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="size-4 text-primary" aria-hidden /> Данные о последствиях
        </CardTitle>
        <CardDescription>
          Как изменится распределение кандидатов по грейдам, если порог этого грейда станет таким, как предлагает
          группа (при одном эксперте — как предлагаете вы). Остальные пороги — действующие.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {impact.isPending ? (
          <SkeletonCards count={1} />
        ) : impact.isError ? (
          <ErrorState description={apiError(impact.error).message} onRetry={() => void impact.refetch()} />
        ) : (
          <ImpactBody impact={impact.data} />
        )}
      </CardContent>
    </Card>
  );
}

function ImpactBody({ impact }: { impact: AngoffImpact }) {
  const group = impact.group;
  return (
    <div className="grid gap-4 text-sm">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Ваш порог" value={fmt(impact.your_cut)} hint={`ниже — ${percent(impact.your_fail_rate)}`} />
        <Metric
          label="Группа: медиана"
          value={group ? fmt(group.median_cut) : "—"}
          hint={group ? `от ${fmt(group.min_cut)} до ${fmt(group.max_cut)}` : "нужно ≥ 2 экспертов"}
        />
        <Metric
          label="Действующий"
          value={fmt(impact.current_cut)}
          hint={`ниже — ${percent(impact.current_fail_rate)}`}
        />
        <Metric
          label="Предложенный"
          value={fmt(impact.proposed_cut)}
          hint={`ниже — ${percent(impact.proposed_fail_rate)}`}
        />
      </dl>
      {group?.sd != null && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Users className="size-3.5" aria-hidden /> {group.raters}{" "}
          {plural(group.raters, ["эксперт", "эксперта", "экспертов"])} прошли раунд 1, разброс порогов (SD){" "}
          {group.sd.toFixed(2)}
        </p>
      )}
      <div className="grid gap-2">
        <div className="grid grid-cols-[minmax(0,8rem)_1fr_3.5rem] gap-x-3 text-xs text-muted-foreground">
          <span>Грейд</span>
          <span>Доля кандидатов: действующие пороги / предложенный</span>
          <span className="text-right">Δ</span>
        </div>
        {impact.bands.map((band) => (
          <div key={band.band} className="grid grid-cols-[minmax(0,8rem)_1fr_3.5rem] items-center gap-x-3">
            <span className="truncate">{band.name}</span>
            <div
              className="grid gap-1"
              aria-label={`${band.name}: ${percent(band.current)} → ${percent(band.proposed)}`}
            >
              <ShareBar value={band.current} className="bg-muted-foreground/40" label={percent(band.current)} />
              <ShareBar value={band.proposed} className="bg-primary" label={percent(band.proposed)} />
            </div>
            <span className="text-right font-mono text-xs tabular-nums">
              {fmt((band.proposed - band.current) * 100, 0)}
            </span>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {impact.source === "results"
          ? `По последним результатам ${impact.candidates} кандидатов специализации.`
          : `Результатов тестов пока мало — доли по синтетической популяции из ${impact.candidates} кандидатов.`}{" "}
        Пороги — на шкале способности θ; «ниже» — доля кандидатов, не дотягивающих до грейда.
      </p>
    </div>
  );
}

function ShareBar({ value, className, label }: { value: number; className: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", className)} style={{ width: `${Math.min(100, value * 100)}%` }} />
      </div>
      <span className="w-12 text-right font-mono text-xs tabular-nums">{label}</span>
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-mono font-bold tabular-nums">{value}</dd>
      {hint && <dd className="text-xs text-muted-foreground">{hint}</dd>}
    </div>
  );
}

const percentField = z
  .number({ error: "Укажите число от 0 до 100" })
  .min(0, "Не меньше 0")
  .max(100, "Не больше 100");
const hofsteeSchema = z
  .object({ minCut: percentField, maxCut: percentField, minFail: percentField, maxFail: percentField })
  .refine((values) => values.minCut <= values.maxCut, { path: ["maxCut"], message: "Максимум меньше минимума" })
  .refine((values) => values.minFail <= values.maxFail, { path: ["maxFail"], message: "Максимум меньше минимума" });
type HofsteeForm = z.infer<typeof hofsteeSchema>;

function toForm(values: AngoffHofsteeValues): HofsteeForm {
  return {
    minCut: Math.round(values.min_cut * 100),
    maxCut: Math.round(values.max_cut * 100),
    minFail: Math.round(values.min_fail * 100),
    maxFail: Math.round(values.max_fail * 100),
  };
}

function HofsteeCard({
  specialization,
  grade,
  tasks,
}: {
  specialization: string;
  grade: AngoffGrade;
  tasks: AngoffTasks;
}) {
  const save = useSaveAngoffHofstee();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isDirty },
    reset,
  } = useForm<HofsteeForm>({
    resolver: zodResolver(hofsteeSchema),
    defaultValues: toForm(tasks.hofstee ?? tasks.hofstee_defaults),
  });

  const onSubmit = (values: HofsteeForm) =>
    save.mutate(
      {
        specialization,
        grade,
        min_cut: values.minCut / 100,
        max_cut: values.maxCut / 100,
        min_fail: values.minFail / 100,
        max_fail: values.maxFail / 100,
      },
      {
        onSuccess: (saved) => reset(toForm(saved)),
        onError: (err) => {
          const fields = { min_cut: "minCut", max_cut: "maxCut", min_fail: "minFail", max_fail: "maxFail" } as const;
          if (!applyValidationErrors(err, setError, fields)) {
            setError("root.server", { message: apiError(err).message });
          }
        },
      },
    );

  const fields = [
    { name: "minCut", label: "Порог не ниже, % верных" },
    { name: "maxCut", label: "Порог не выше, % верных" },
    { name: "minFail", label: `Не дотягивают до ${tasks.grade_name} не меньше, %` },
    { name: "maxFail", label: `Не дотягивают до ${tasks.grade_name} не больше, %` },
  ] as const;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Проверка Hofstee</CardTitle>
        <CardDescription>
          Независимо от оценок заданий: какой порог (доля верных ответов по этому набору у минимально компетентного{" "}
          {tasks.grade_name}) и какая доля кандидатов специализации ниже уровня {tasks.grade_name} для вас приемлемы? В
          сводке порог Angoff сравнивается с этим окном.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="grid gap-3" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="grid gap-3 sm:grid-cols-2">
            {fields.map((field) => (
              <FormField
                key={field.name}
                id={`hofstee-${field.name}`}
                label={field.label}
                error={errors[field.name]?.message}
              >
                <Input
                  id={`hofstee-${field.name}`}
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={100}
                  aria-invalid={!!errors[field.name]}
                  {...register(field.name, { valueAsNumber: true })}
                />
              </FormField>
            ))}
          </div>
          <FormAlert message={errors.root?.server?.message ?? null} />
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />}
              Сохранить
            </Button>
            <span className="text-xs text-muted-foreground">
              {tasks.hofstee && !isDirty
                ? "Сохранено"
                : tasks.hofstee
                  ? "Есть несохранённые изменения"
                  : "Значения по умолчанию — поправьте под себя"}
            </span>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function AngoffSummaryCard({ specialization }: { specialization: string }) {
  const summary = useAngoffSummary(specialization);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Рекомендуемые пороги</CardTitle>
        <CardDescription>
          Порог эксперта — θ, при котором ожидаемый балл по набору совпадает с суммой его оценок. В расчёт идут только
          полностью оценённые наборы; рекомендация — по последнему раунду. Действующие пороги меняет команда вручную.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {summary.isPending ? (
          <SkeletonCards count={1} />
        ) : summary.isError ? (
          <ErrorState description={apiError(summary.error).message} onRetry={() => void summary.refetch()} />
        ) : summary.data.grades.length === 0 ? (
          <EmptyState
            icon={Scale}
            title="Полных наборов пока нет"
            description="Оцените все задания у одной границы грейда — здесь появится рекомендуемый порог."
          />
        ) : (
          <div className="grid gap-3">
            {summary.data.grades.map((item) => (
              <GradeRow key={item.grade} item={item} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function GradeRow({ item }: { item: AngoffSummary["grades"][number] }) {
  const latest = item.rounds[item.rounds.length - 1];
  return (
    <div className="grid gap-3 rounded-lg border p-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-semibold">{item.grade_name}</span>
        <span className="text-xs text-muted-foreground">
          {item.items} {plural(item.items, ["задание", "задания", "заданий"])} · рекомендация по раунду{" "}
          {item.recommended_round}
        </span>
      </div>
      <dl className="grid grid-cols-3 gap-2">
        <div>
          <dt className="text-xs text-muted-foreground">По оценкам</dt>
          <dd className="font-mono font-bold tabular-nums">
            {fmt(item.recommended_cut)}
            {item.se != null && <span className="font-normal text-muted-foreground"> ±{item.se.toFixed(2)}</span>}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Сейчас</dt>
          <dd className="font-mono font-bold tabular-nums">{fmt(item.current_cut)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Разница</dt>
          <dd className="font-mono font-bold tabular-nums">{fmt(item.difference)}</dd>
        </div>
      </dl>
      {latest && latest.raters < item.recommended_raters && (
        <p className="text-xs text-muted-foreground">
          Экспертов: {latest.raters} из рекомендуемых {item.recommended_raters} — SE порога пока велика.
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[28rem] text-xs">
          <thead className="text-muted-foreground">
            <tr className="text-left">
              <th className="py-1 font-normal">Раунд</th>
              <th className="py-1 font-normal">Экспертов</th>
              <th className="py-1 font-normal">Среднее ± SE</th>
              <th className="py-1 font-normal">Медиана</th>
              <th className="py-1 font-normal">SD</th>
            </tr>
          </thead>
          <tbody className="font-mono tabular-nums">
            {item.rounds.map((round) => (
              <tr key={round.round} className="border-t">
                <td className="py-1">{round.round}</td>
                <td className="py-1">
                  {round.raters}
                  {round.incomplete_raters > 0 && (
                    <span className="text-muted-foreground"> +{round.incomplete_raters} в процессе</span>
                  )}
                </td>
                <td className="py-1">
                  {fmt(round.mean_cut)}
                  {round.se != null && ` ±${round.se.toFixed(2)}`}
                </td>
                <td className="py-1">{fmt(round.median_cut)}</td>
                <td className="py-1">{round.sd != null ? round.sd.toFixed(2) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {latest && (
        <div className="flex flex-wrap gap-1.5">
          {latest.rater_cuts.map((rater) => (
            <Badge
              key={rater.rater}
              variant={rater.you ? "default" : "muted"}
              title={`Средняя оценка ${Math.round(rater.expected_share * 100)}%`}
            >
              {rater.you ? "Вы" : rater.rater}: {fmt(rater.cut)}
              {rater.clamped && " (край шкалы)"}
            </Badge>
          ))}
        </div>
      )}
      <HofsteeLine item={item} />
    </div>
  );
}

function HofsteeLine({ item }: { item: AngoffSummary["grades"][number] }) {
  const check = item.hofstee;
  if (!check) {
    return <p className="text-xs text-muted-foreground">Проверка Hofstee: окно ещё никто не заполнил.</p>;
  }
  const box = check.box;
  return (
    <div className="grid gap-1.5 rounded-md bg-muted/60 p-2.5 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold">
          Проверка Hofstee ({check.raters} {plural(check.raters, ["эксперт", "эксперта", "экспертов"])})
        </span>
        <Badge variant={check.in_box ? "soft" : "destructive"}>
          {check.in_box ? "Порог Angoff внутри окна" : "Порог Angoff вне окна"}
        </Badge>
      </div>
      <p className="text-muted-foreground">
        Окно: порог {percent(box.min_cut)}–{percent(box.max_cut)} верных, ниже уровня {percent(box.min_fail)}–
        {percent(box.max_fail)} кандидатов.
      </p>
      <p>
        Angoff: <span className="font-mono tabular-nums">{percent(check.angoff_share)}</span> верных, ниже уровня{" "}
        <span className="font-mono tabular-nums">{percent(check.angoff_fail_rate)}</span>. Hofstee:{" "}
        <span className="font-mono tabular-nums">{percent(check.cut_share)}</span> верных (θ {fmt(check.cut_theta)}),
        ниже уровня <span className="font-mono tabular-nums">{percent(check.fail_rate)}</span>
        {!check.intersects && " — кривая не пересекает окно, взят ближний край"}.
      </p>
      <p className="text-muted-foreground">
        {item.impact_source === "results"
          ? `Доли — по результатам ${item.impact_candidates} кандидатов.`
          : `Доли — по синтетической популяции (${item.impact_candidates}): реальных результатов пока мало.`}
      </p>
    </div>
  );
}
