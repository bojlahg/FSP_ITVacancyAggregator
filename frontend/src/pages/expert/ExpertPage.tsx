import { CheckCircle2, ClipboardCheck, Loader2, ShieldCheck, Trophy } from "lucide-react";
import { type ReactNode, useEffect } from "react";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { SkeletonCards } from "@/components/SkeletonCards";
import { StatCard } from "@/components/StatCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiError } from "@/lib/api-error";
import { type ExpertTask, useExpertSummary, useExpertTask, useLabelPair } from "@/lib/expert-queries";
import { formatExperience, formatNumber, plural, toPercent } from "@/lib/format";
import { SKILL_STATUS_LABELS, WORK_FORMAT_LABELS, workFormatsLabel } from "@/lib/labels";
import { AngoffTab } from "@/pages/expert/AngoffTab";

// Шкала оценки пары, docs/implementation.md §12.2
const LABELS = [
  { value: 0, title: "Не подходит", hint: "Не тот профиль или уровень" },
  { value: 1, title: "Слабо", hint: "Совпадает немногое, звать не стоит" },
  { value: 2, title: "С оговорками", hint: "Позвал бы, но есть пробелы" },
  { value: 3, title: "Подходит", hint: "Позвал бы на собеседование сразу" },
] as const;

export default function ExpertPage() {
  return (
    <>
      <PageHeader
        eyebrow="Экспертная разметка"
        title="Подходит ли кандидат под потребность?"
        description="Оценивайте вслепую: score, объяснение и место в выдаче скрыты. Оценки сравнивают выдачу ITScout с поиском по ключевым словам."
      />
      <Tabs defaultValue="label">
        <TabsList>
          <TabsTrigger value="label">Разметка</TabsTrigger>
          <TabsTrigger value="summary">Итоги</TabsTrigger>
          <TabsTrigger value="angoff">Пороги (Angoff)</TabsTrigger>
        </TabsList>
        <TabsContent value="label" className="mt-4">
          <LabelingTab />
        </TabsContent>
        <TabsContent value="summary" className="mt-4">
          <SummaryTab />
        </TabsContent>
        <TabsContent value="angoff" className="mt-4">
          <AngoffTab />
        </TabsContent>
      </Tabs>
    </>
  );
}

function LabelingTab() {
  const task = useExpertTask();
  const labelPair = useLabelPair();
  const pairId = task.data?.pair_id ?? null;
  const busy = labelPair.isPending || task.isFetching;

  const submit = (label: number) => {
    if (pairId === null || busy) return;
    labelPair.mutate({ pairId, label }, { onSuccess: () => window.scrollTo({ top: 0, behavior: "smooth" }) });
  };

  // Клавиши 0–3 ставят оценку: разметка десятков пар без мыши
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLElement && ["INPUT", "TEXTAREA"].includes(event.target.tagName)) return;
      const value = Number(event.key);
      if (event.key.length === 1 && value >= 0 && value <= 3) submit(value);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (task.isPending) return <SkeletonCards count={2} />;
  if (task.isError) {
    return <ErrorState description={apiError(task.error).message} onRetry={() => void task.refetch()} />;
  }
  const { progress, need, candidate } = task.data;
  if (progress.total === 0) {
    return (
      <EmptyState
        icon={ClipboardCheck}
        title="Пар для разметки пока нет"
        description="Набор пар собирается из активных потребностей работодателей. Загляните позже."
      />
    );
  }
  if (pairId === null || !need || !candidate) {
    return (
      <EmptyState
        icon={CheckCircle2}
        title="Все пары размечены"
        description={`Спасибо! Вы оценили ${progress.done} ${plural(progress.done, ["пару", "пары", "пар"])}. Итоги — на соседней вкладке.`}
      />
    );
  }

  return (
    <div className="grid gap-4">
      <div className="space-y-1.5">
        <div className="flex justify-between gap-2 text-sm">
          <span className="text-muted-foreground">Прогресс</span>
          <span className="font-mono font-bold tabular-nums">
            {progress.done} / {progress.total}
          </span>
        </div>
        <Progress value={(progress.done / progress.total) * 100} aria-label="Размечено пар" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <NeedCard need={need} />
        <BlindCandidate card={candidate} />
      </div>

      <Card className="gap-3 border-primary py-4 shadow-md md:sticky md:bottom-2 md:z-10">
        <CardHeader className="px-4">
          <CardTitle>Ваша оценка</CardTitle>
          <CardDescription className="max-md:hidden">
            Можно клавишами 0–3. Ответ сохраняется сразу, следующая пара откроется сама.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 px-4">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {LABELS.map((item) => (
              <Button
                key={item.value}
                variant={item.value >= 2 ? "default" : "outline"}
                className="h-auto flex-col items-start gap-0.5 py-2 text-left whitespace-normal"
                disabled={busy}
                onClick={() => submit(item.value)}
              >
                <span className="font-mono font-bold">
                  {item.value} · {item.title}
                </span>
                <span className="text-xs font-normal opacity-80 max-sm:hidden">{item.hint}</span>
              </Button>
            ))}
          </div>
          {busy && <Loader2 className="size-4 animate-spin text-primary" aria-label="Сохраняем" />}
          <FormAlert message={labelPair.isError ? apiError(labelPair.error).message : null} />
        </CardContent>
      </Card>
    </div>
  );
}

function NeedCard({ need }: { need: NonNullable<ExpertTask["need"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription className="font-mono text-xs uppercase">Потребность работодателя</CardDescription>
        <CardTitle>{need.title}</CardTitle>
        <CardDescription>{need.category}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 text-sm">
        <SkillList title="Обязательные навыки" skills={need.required_skills} variant="default" />
        <SkillList title="Желательные навыки" skills={need.optional_skills} variant="muted" />
        <dl className="grid gap-2">
          <Row label="Вилка">
            <SalaryRange from={need.salary_from} to={need.salary_to} />
          </Row>
          {need.work_format && <Row label="Формат">{WORK_FORMAT_LABELS[need.work_format] ?? need.work_format}</Row>}
          {need.city && <Row label="Город">{need.city}</Row>}
          {need.industry && <Row label="Отрасль">{need.industry}</Row>}
        </dl>
        {need.team_description && <p className="rounded-md bg-muted p-3 whitespace-pre-line">{need.team_description}</p>}
      </CardContent>
    </Card>
  );
}

function BlindCandidate({ card }: { card: NonNullable<ExpertTask["candidate"]> }) {
  const { brief } = card;
  const fsp = card.fsp?.linked ? card.fsp : null;
  return (
    <Card>
      <CardHeader>
        <CardDescription className="font-mono text-xs uppercase">Кандидат · обезличенно</CardDescription>
        <CardTitle className="flex flex-wrap items-center gap-2">
          {brief.display_name}
          <CategoryBadge specialization={brief.category.specialization} grade={brief.category.grade} variant="solid" />
        </CardTitle>
        <CardDescription>
          {brief.percentile != null && `${toPercent(brief.percentile)}-й перцентиль в категории · `}
          {card.experience_years != null ? `опыт ${formatExperience(card.experience_years)}` : "опыт не указан"}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 text-sm">
        {card.topic_scores.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {card.topic_scores.map((topic) => (
              <div key={topic.topic} className="space-y-1">
                <div className="flex justify-between gap-2">
                  <span>{topic.name}</span>
                  <span className="font-mono font-bold tabular-nums">{toPercent(topic.score)}%</span>
                </div>
                <Progress value={toPercent(topic.score)} className="h-1.5" aria-label={topic.name} />
              </div>
            ))}
          </div>
        )}
        <div className="grid gap-2">
          <div className="text-xs text-muted-foreground">Стек</div>
          {card.skills.length === 0 ? (
            <p className="text-muted-foreground">Навыки не указаны.</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {card.skills.map((skill) => (
                <Badge
                  key={skill.skill_id}
                  variant={skill.status === "declared" ? "muted" : "soft"}
                  title={SKILL_STATUS_LABELS[skill.status]}
                >
                  {skill.status === "verified" && <ShieldCheck aria-hidden />}
                  {skill.status === "fsp_confirmed" && <Trophy aria-hidden />}
                  {skill.name}
                </Badge>
              ))}
            </div>
          )}
        </div>
        {card.about && <p className="leading-relaxed">{card.about}</p>}
        {card.experience.length > 0 && (
          <ul className="grid gap-1.5 border-l border-border-subtle pl-3">
            {card.experience.map((item, index) => (
              <li key={index}>
                <span className="font-medium">{item.position}</span>
                {item.description && <span className="text-muted-foreground"> — {item.description}</span>}
              </li>
            ))}
          </ul>
        )}
        {fsp && (fsp.ranks.length > 0 || fsp.achievements.length > 0) && (
          <div className="flex flex-wrap items-center gap-1.5">
            <Trophy className="size-4 text-primary" aria-hidden />
            {fsp.ranks.map((rank) => (
              <Badge key={`${rank.discipline}-${rank.rank}`} variant="outline">
                {rank.rank} · {rank.discipline}
              </Badge>
            ))}
            {fsp.achievements.length > 0 && (
              <span className="text-muted-foreground">
                {fsp.achievements.length} {plural(fsp.achievements.length, ["соревнование", "соревнования", "соревнований"])} ФСП
              </span>
            )}
          </div>
        )}
        <dl className="grid gap-2">
          <Row label="Ожидания">
            <span className="font-mono font-bold">
              {brief.salary_min == null ? "скрыты" : `от ${formatNumber(brief.salary_min)} ₽`}
            </span>
          </Row>
          <Row label="Формат">{workFormatsLabel(brief.work_formats)}</Row>
          <Row label="Город">
            {brief.city ?? "не указан"}
            {brief.relocation && ", готов к релокации"}
          </Row>
        </dl>
      </CardContent>
    </Card>
  );
}

function SkillList({ title, skills, variant }: { title: string; skills: string[]; variant: "default" | "muted" }) {
  if (skills.length === 0) return null;
  return (
    <div className="grid gap-2">
      <div className="text-xs text-muted-foreground">{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {skills.map((skill) => (
          <Badge key={skill} variant={variant}>
            {skill}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

function SummaryTab() {
  const summary = useExpertSummary();
  if (summary.isPending) return <SkeletonCards count={2} />;
  if (summary.isError) {
    return <ErrorState description={apiError(summary.error).message} onRetry={() => void summary.refetch()} />;
  }
  const data = summary.data;
  if (data.labels === 0) {
    return (
      <EmptyState
        icon={ClipboardCheck}
        title="Оценок пока нет"
        description="Метрики появятся после первых размеченных пар."
      />
    );
  }
  const fmt = (value: number | null, digits = 2) => (value == null ? "—" : value.toFixed(digits));
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Экспертов" value={data.raters} />
        <StatCard label="Оценок" value={data.labels} />
        <StatCard label="Пар размечено" value={`${data.pairs_labeled} / ${data.pairs_total}`} />
        <StatCard
          label="Спирмен score ↔ оценка"
          value={fmt(data.spearman)}
          hint={`по ${data.spearman_pairs} ${plural(data.spearman_pairs, ["паре", "парам", "парам"])}`}
        />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Точность первых пяти (P@5)</CardTitle>
          <CardDescription>
            Доля релевантных в топ-5 по потребности; релевантна пара со средней оценкой не ниже{" "}
            {data.relevant_from}. Считаются только потребности, где размечены все пять.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {data.rankers.map((ranker) => (
            <div key={ranker.name} className="space-y-1.5">
              <div className="flex justify-between gap-2 text-sm">
                <span>{ranker.name}</span>
                <span className="font-mono font-bold tabular-nums">
                  {fmt(ranker.precision_at_5)}
                  <span className="ml-1 text-xs font-normal text-muted-foreground">
                    · {ranker.needs} {plural(ranker.needs, ["потребность", "потребности", "потребностей"])}
                  </span>
                </span>
              </div>
              <Progress value={ranker.precision_at_5 == null ? 0 : ranker.precision_at_5 * 100} aria-label={ranker.name} />
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Согласие экспертов</CardTitle>
          <CardDescription>
            По парам, которые оценили двое и больше: {data.agreement_pairs}. Взвешенная κ учитывает, насколько
            далеко разошлись оценки.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-2 text-sm">
            <Row label="Точное совпадение">
              <span className="font-mono font-bold">
                {data.exact_agreement == null ? "—" : `${toPercent(data.exact_agreement)}%`}
              </span>
            </Row>
            <Row label="Квадратично взвешенная κ">
              <span className="font-mono font-bold">{fmt(data.weighted_kappa)}</span>
            </Row>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
