import { Check, Gauge, Loader2, Scale } from "lucide-react";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { InstanceBody } from "@/components/explainer/InstanceBody";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { apiError } from "@/lib/api-error";
import {
  type AngoffGrade,
  type AngoffSummary,
  type AngoffTasks,
  useAngoffSummary,
  useAngoffTasks,
  useRateAngoff,
} from "@/lib/expert-queries";
import { useExplainerOverview } from "@/lib/explainer-queries";
import { plural } from "@/lib/format";
import { ITEM_KIND_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

// Modified Angoff, docs/implementation.md §10.4: эксперт оценивает P(решит) для минимально компетентного кандидата
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
            вероятностью он решит это задание? Ответ ключа не показываем — оценивайте по сути задания. Из оценок
            выводится рекомендуемый порог; действующие пороги сами не меняются.
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
      {spec && <AngoffTaskList specialization={spec} grade={grade} />}
      {spec && <AngoffSummaryCard specialization={spec} />}
    </div>
  );
}

function AngoffTaskList({ specialization, grade }: { specialization: string; grade: AngoffGrade }) {
  const tasks = useAngoffTasks(specialization, grade);
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
          <span className="text-muted-foreground">Оценено заданий</span>
          <span className="font-mono font-bold tabular-nums">
            {progress.done} / {progress.total}
          </span>
        </div>
        <Progress value={(progress.done / progress.total) * 100} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {tasks.data.tasks.map((task, index) => (
          <AngoffTaskCard
            key={`${grade}:${task.template_id}`}
            task={task}
            index={index}
            specialization={specialization}
            grade={grade}
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
  step,
}: {
  task: Task;
  index: number;
  specialization: string;
  grade: AngoffGrade;
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
        template_id: task.template_id,
        rating: draft / 100,
      });
    }, SAVE_DELAY_MS);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- rate стабилен по смыслу, не перезапускаем таймер
  }, [draft, saved, specialization, grade, task.template_id]);

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

function fmt(value: number | null, digits = 2) {
  if (value == null) return "—";
  return (value > 0 ? "+" : value < 0 ? "−" : "") + Math.abs(value).toFixed(digits);
}

function AngoffSummaryCard({ specialization }: { specialization: string }) {
  const summary = useAngoffSummary(specialization);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Рекомендуемые пороги</CardTitle>
        <CardDescription>
          Порог эксперта — θ, при котором ожидаемый балл по набору совпадает с суммой его оценок. В расчёт идут только
          полностью оценённые наборы. Действующие пороги меняет команда вручную.
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
  return (
    <div className="grid gap-2 rounded-lg border p-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-semibold">{item.grade_name}</span>
        <span className="text-xs text-muted-foreground">
          {item.raters} {plural(item.raters, ["эксперт", "эксперта", "экспертов"])} · {item.items}{" "}
          {plural(item.items, ["задание", "задания", "заданий"])}
          {item.incomplete_raters > 0 && ` · ещё ${item.incomplete_raters} в процессе`}
        </span>
      </div>
      <dl className="grid grid-cols-3 gap-2">
        <div>
          <dt className="text-xs text-muted-foreground">По оценкам</dt>
          <dd className="font-mono font-bold tabular-nums">
            {fmt(item.mean_cut)}
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
      <div className="flex flex-wrap gap-1.5">
        {item.rater_cuts.map((rater) => (
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
      {item.sd != null && <p className="text-xs text-muted-foreground">Разброс экспертов (SD): {item.sd.toFixed(2)}</p>}
    </div>
  );
}
