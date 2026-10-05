import { ArrowRight, BookOpen, RefreshCw, ShieldCheck, Shuffle, UserRound } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { IccChart, InformationChart } from "@/components/explainer/ExplainerCharts";
import { InstanceBody } from "@/components/explainer/InstanceBody";
import { SCENARIO_STYLE } from "@/components/explainer/scenario-style";
import { Trace } from "@/components/Trace";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useExplainerDiversity,
  useExplainerInformation,
  useExplainerInstances,
  useExplainerOverview,
  useExplainerTemplates,
  type ExplainerGrade,
  type ExplainerInstances,
  type ExplainerOverview,
  type ExplainerScenario,
  type ExplainerTemplate,
} from "@/lib/explainer-queries";
import { ITEM_KIND_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

type Grade = ExplainerGrade["grade"];
type Instance = ExplainerInstances["instances"][number];

const INSTANCE_COUNT = 3;
const DEFAULT_GRADE: Grade = "middle";
const MAX_SEED = 2_000_000_000;

function randomSeeds(count: number): number[] {
  const seeds = new Set<number>();
  while (seeds.size < count) seeds.add(Math.floor(Math.random() * MAX_SEED));
  return [...seeds];
}

function percent(value: number, digits = 0): string {
  return `${(value * 100).toLocaleString("ru-RU", { maximumFractionDigits: digits, minimumFractionDigits: 0 })}%`;
}

function num(value: number, digits = 2): string {
  return value.toLocaleString("ru-RU", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Ноль в выборке из n — это «меньше 1/n», а не «никогда». */
function atLeast(value: number, sample: number): string {
  return value > 0 ? percent(value, 1) : `<${percent(1 / sample, 1)}`;
}

/** Шаблон по умолчанию — «что выведет код»: на нём разница экземпляров видна сразу. */
function defaultTemplate(templates: ExplainerTemplate[]): ExplainerTemplate | undefined {
  return templates.find((t) => t.kind === "code_output") ?? templates[0];
}

function SectionTitle({ id, index, title, lead }: { id: string; index: string; title: string; lead: ReactNode }) {
  return (
    <div className="max-w-3xl space-y-3">
      <div className="font-mono text-xs font-bold tracking-[0.08em] text-primary">{index}</div>
      <h2 id={id} className="text-2xl font-extrabold sm:text-3xl">
        {title}
      </h2>
      <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">{lead}</p>
    </div>
  );
}

function Pills<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              "h-9 rounded-full border-[1.5px] px-3.5 font-mono text-sm font-medium transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
              selected
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-background text-foreground hover:border-primary hover:text-primary",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function Stat({ value, label, hint }: { value: ReactNode; label: string; hint?: ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-4 sm:p-5">
      <div className="font-mono text-3xl font-extrabold text-primary tabular-nums sm:text-4xl">{value}</div>
      <div className="mt-2 text-sm font-semibold">{label}</div>
      {hint && <div className="mt-1 text-xs leading-relaxed text-muted-foreground">{hint}</div>}
    </div>
  );
}

// ——— 1. Шаблоны и экземпляры ———

function InstanceCard({ instance, index, kind }: { instance: Instance; index: number; kind: string }) {
  return (
    <article className="flex flex-col rounded-xl border bg-card p-4 shadow-xs">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="font-mono text-xs font-bold text-primary">Кандидат {index + 1}</span>
        <span className="font-mono text-[11px] text-muted-foreground">seed {instance.seed}</span>
      </div>
      <InstanceBody instance={instance} kind={kind} />
    </article>
  );
}

function TemplateMeta({ template, grades }: { template: ExplainerTemplate; grades: ExplainerGrade[] }) {
  const items = [
    { label: "Тема", value: template.topic_name },
    { label: "Вид", value: ITEM_KIND_LABELS[template.kind] ?? template.kind },
    { label: "Сложность", value: template.difficulty },
    { label: "Навыки", value: template.skills.join(", ") || "—" },
  ];
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {items.map((item) => (
          <div key={item.label}>
            <dt className="font-mono text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">
              {item.label}
            </dt>
            <dd className="mt-0.5 text-sm font-semibold">{item.value}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-2">
        <Badge variant="soft" title="Сложность на IRT-шкале специализации">
          b = {num(template.b)}
        </Badge>
        <Badge variant="muted" title="Дискриминация: насколько резко растёт вероятность успеха у порога">
          a = {num(template.a)}
        </Badge>
        <Badge variant="muted" title="Вероятность угадать">
          c = {num(template.c)}
        </Badge>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">
        Порог ближайшего грейда:{" "}
        {grades
          .filter((g) => g.cut <= template.b)
          .map((g) => g.name)
          .at(-1) ?? "ниже Стажёра"}
        . Параметры общие для всех экземпляров шаблона — поэтому разные задания сопоставимы.
      </p>
    </div>
  );
}

function TemplatesSection({
  specialization,
  overview,
  template,
  templates,
  templatesState,
  onTemplate,
}: {
  specialization: string;
  overview: ExplainerOverview;
  template: ExplainerTemplate | undefined;
  templates: ExplainerTemplate[];
  templatesState: { isPending: boolean; isError: boolean; refetch: () => void };
  onTemplate: (id: string) => void;
}) {
  const count = Math.min(INSTANCE_COUNT, overview.max_seeds);
  const [seeds, setSeeds] = useState(() => randomSeeds(count));
  const instances = useExplainerInstances(template?.id, seeds);

  const byTopic = new Map<string, ExplainerTemplate[]>();
  for (const item of templates) byTopic.set(item.topic_name, [...(byTopic.get(item.topic_name) ?? []), item]);

  function pickRandom() {
    const others = templates.filter((t) => t.id !== template?.id);
    const next = others[Math.floor(Math.random() * others.length)];
    if (next) onTemplate(next.id);
    setSeeds(randomSeeds(count));
  }

  return (
    <section aria-labelledby="templates-title" className="space-y-8 border-t border-border-subtle py-14">
      <SectionTitle
        id="templates-title"
        index="01"
        title="Один шаблон — тысячи заданий"
        lead={
          <>
            В банке лежат не готовые вопросы, а <b className="text-foreground">шаблоны</b>: одна проверяемая идея и
            одна калиброванная сложность. Числа, имена, код и варианты ответа генерируются для каждой попытки из
            случайного seed. Ключи ответов на эту страницу, как и в сам тест, не передаются.
          </>
        }
      />

      {templatesState.isPending ? (
        <Skeleton className="h-10 w-full max-w-xl" />
      ) : templatesState.isError ? (
        <ErrorState title="Не удалось загрузить шаблоны" onRetry={templatesState.refetch} />
      ) : templates.length === 0 || !template ? (
        <EmptyState
          title="Для специализации пока нет шаблонов"
          description={`Банк ${specialization} пуст — выберите другую специализацию.`}
        />
      ) : (
        <>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
            <label className="min-w-0 flex-1 space-y-1.5 lg:max-w-xl">
              <span className="font-mono text-xs font-medium tracking-[0.06em] text-muted-foreground uppercase">
                Шаблон · {templates.length} в банке
              </span>
              <Select value={template.id} onChange={(event) => onTemplate(event.target.value)} className="font-mono">
                {[...byTopic.entries()].map(([topic, items]) => (
                  <optgroup key={topic} label={topic}>
                    {items.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.id} · b={num(item.b, 1)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Select>
            </label>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={pickRandom}>
                <Shuffle /> Случайный шаблон
              </Button>
              <Button onClick={() => setSeeds(randomSeeds(count))} disabled={instances.isFetching}>
                <RefreshCw className={cn(instances.isFetching && "animate-spin")} /> Сгенерировать ещё
              </Button>
            </div>
          </div>

          {instances.isError ? (
            <ErrorState title="Не удалось сгенерировать задания" onRetry={() => void instances.refetch()} />
          ) : !instances.data ? (
            <div className="grid gap-4 md:grid-cols-3" aria-busy="true" aria-label="Загрузка">
              {Array.from({ length: count }, (_, index) => (
                <Skeleton key={index} className="h-64 rounded-xl" />
              ))}
            </div>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-3">
                {instances.data.instances.map((instance, index) => (
                  <InstanceCard key={instance.seed} instance={instance} index={index} kind={template.kind} />
                ))}
              </div>
              <div className="grid gap-6 rounded-xl border bg-primary-tint/50 p-4 sm:p-6 lg:grid-cols-[1fr_1.2fr]">
                <TemplateMeta template={instances.data.template} grades={overview.grades} />
                <figure className="space-y-2">
                  <figcaption className="text-sm font-semibold">
                    Вероятность верного ответа в зависимости от уровня θ
                  </figcaption>
                  <div className="h-48">
                    <IccChart icc={instances.data.icc} grades={overview.grades} />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Кривая 3PL: P(θ) = c + (1 − c) / (1 + e<sup>−a(θ − b)</sup>). Вертикали — пороги грейдов.
                  </p>
                </figure>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}

// ——— 2. Адаптивный тест ———

function ItemsStrip({ scenario }: { scenario: ExplainerScenario }) {
  const position = (b: number) => `${((Math.max(-4, Math.min(4, b)) + 4) / 8) * 100}%`;
  const stageClass: Record<number, string> = { 1: "bg-chart-1", 2: "bg-chart-2", 3: "bg-destructive" };
  return (
    <div className="relative mt-3 h-6" aria-label="Сложность заданий одной симулированной попытки">
      <div className="absolute top-1/2 right-0 left-0 h-px bg-border" />
      {scenario.items.map((item, index) => (
        <span
          key={index}
          className={cn(
            "absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card",
            stageClass[item.stage] ?? "bg-chart-3",
          )}
          style={{ left: position(item.b), marginTop: item.stage === 2 ? 6 : item.stage === 3 ? -6 : -1 }}
          title={`Этап ${item.stage}: b = ${num(item.b)}`}
        />
      ))}
    </div>
  );
}

function ScenarioCard({ scenario, grades }: { scenario: ExplainerScenario; grades: ExplainerGrade[] }) {
  const style = SCENARIO_STYLE[scenario.scenario];
  const nearest = grades.reduce((best, g) =>
    Math.abs(g.cut - scenario.stage2_target) < Math.abs(best.cut - scenario.stage2_target) ? g : best,
  );
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-center gap-2">
        <span className={cn("h-0.5 w-5 rounded-full", style.dot)} aria-hidden />
        <h3 className="font-sans text-sm font-bold">{scenario.label}</h3>
        <span className="ml-auto font-mono text-xs text-muted-foreground">θ = {num(scenario.theta_true, 1)}</span>
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <dt className="text-[11px] text-muted-foreground">заданий</dt>
          <dd className="font-mono text-lg font-bold tabular-nums">{num(scenario.items_mean, 1)}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-muted-foreground">ошибка SE</dt>
          <dd className="font-mono text-lg font-bold tabular-nums">{num(scenario.se_mean)}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-muted-foreground">прошли</dt>
          <dd className="font-mono text-lg font-bold tabular-nums">{percent(scenario.pass_share)}</dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-muted-foreground">
        Этап 2 уходит к b ≈ {num(scenario.stage2_target, 1)} — около порога {nearest.name}.
      </p>
      <ItemsStrip scenario={scenario} />
    </div>
  );
}

function AdaptiveSection({ specialization, overview }: { specialization: string; overview: ExplainerOverview }) {
  const [grade, setGrade] = useState<Grade>(DEFAULT_GRADE);
  const information = useExplainerInformation(specialization, grade);
  const gradeName = overview.grades.find((g) => g.grade === grade)?.name ?? grade;
  const split = num(overview.stage_split, 1);

  const steps = [
    {
      title: `Этап 1 · ${overview.stage1_items} заданий`,
      text: `Сложность около порога грейда, на который идёт тест, темы — по квотам blueprint специализации.`,
    },
    {
      title: `Этап 2 · ${overview.stage2_items} заданий`,
      text: `θ̂ выше порога на ${split} и больше — блок у следующего порога; ниже на ${split} — блок ниже; иначе — снова у порога.`,
    },
    {
      title: `Уточнение · до ${overview.extra_items_max}`,
      text: "Пока порог внутри погрешности (|θ̂ − порог| < SE), добавляются задания у порога. Решение — по EAP-оценке θ̂.",
    },
  ];

  return (
    <section aria-labelledby="adaptive-title" className="space-y-8 border-t border-border-subtle py-14">
      <SectionTitle
        id="adaptive-title"
        index="02"
        title="Адаптивный тест"
        lead="Тест собирается из банка по ходу ответов (двухэтапный MST). Точнее всего он измеряет там, где принимается решение о грейде, — у порога. Ниже — настоящий планировщик теста на симулированных кандидатах."
      />

      <ol className="grid gap-4 md:grid-cols-3">
        {steps.map((step, index) => (
          <li key={step.title} className="flex gap-3 rounded-xl border bg-card p-4">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full border-[1.5px] border-primary font-mono text-sm font-bold text-primary">
              {index + 1}
            </span>
            <div className="space-y-1">
              <h3 className="text-sm font-bold">{step.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{step.text}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="space-y-4 rounded-xl border bg-card p-4 sm:p-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-base font-bold">Информационная функция теста на грейд {gradeName}</h3>
            <p className="text-xs text-muted-foreground">
              Чем выше кривая, тем меньше ошибка оценки в этой точке шкалы.
            </p>
          </div>
          <Pills
            label="Грейд теста"
            value={grade}
            onChange={setGrade}
            options={overview.grades.map((g) => ({ value: g.grade, label: g.name }))}
          />
        </div>

        {information.isError ? (
          <ErrorState title="Не удалось посчитать кривые" onRetry={() => void information.refetch()} />
        ) : !information.data ? (
          <Skeleton className="h-72 w-full" />
        ) : (
          <>
            <div className={cn("h-72 sm:h-80", information.isFetching && "opacity-60 transition-opacity")}>
              <InformationChart
                scenarios={information.data.scenarios}
                grades={information.data.grades}
                activeGrade={grade}
              />
            </div>
            <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs" aria-label="Легенда">
              {information.data.scenarios.map((scenario) => (
                <li key={scenario.scenario} className="flex items-center gap-2">
                  <svg width="22" height="6" aria-hidden>
                    <line
                      x1="0"
                      y1="3"
                      x2="22"
                      y2="3"
                      stroke={SCENARIO_STYLE[scenario.scenario].color}
                      strokeWidth="2"
                      strokeDasharray={SCENARIO_STYLE[scenario.scenario].dash}
                    />
                  </svg>
                  {scenario.label} (θ = {num(scenario.theta_true, 1)})
                </li>
              ))}
              <li className="flex items-center gap-2 text-muted-foreground">
                <span className="h-3 w-px bg-destructive" aria-hidden /> порог {gradeName}
              </li>
            </ul>
            <div className="grid gap-4 md:grid-cols-3">
              {information.data.scenarios.map((scenario) => (
                <ScenarioCard key={scenario.scenario} scenario={scenario} grades={information.data.grades} />
              ))}
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Каждый сценарий — {information.data.simulations} попыток настоящим планировщиком
              {information.data.stack_module ? ` (стек-модуль ${information.data.stack_module})` : ""}; ответы
              симулированы по модели 3PL с параметрами a, b, c из банка. Точки под карточками — задания одной попытки
              по сложности: <span className="text-chart-1">●</span> этап 1, <span className="text-chart-2">●</span>{" "}
              этап 2, <span className="text-destructive">●</span> уточнение.
            </p>
          </>
        )}
      </div>
    </section>
  );
}

// ——— 3. Утечка ———

function LeakSection({
  specialization,
  overview,
  template,
}: {
  specialization: string;
  overview: ExplainerOverview;
  template: ExplainerTemplate | undefined;
}) {
  const diversity = useExplainerDiversity(template?.id, overview.max_sample);
  const information = useExplainerInformation(specialization, DEFAULT_GRADE);
  const middle = overview.grades.find((g) => g.grade === DEFAULT_GRADE)?.name ?? DEFAULT_GRADE;

  return (
    <section aria-labelledby="leak-title" className="space-y-8 border-t border-border-subtle py-14">
      <SectionTitle
        id="leak-title"
        index="03"
        title="Почему слив ответов не работает"
        lead="Список вопросов можно пересказать, но ключ из чужой попытки не подходит: у каждого кандидата свои числа, код и варианты. Выучить шаблон значит выучить концепцию — а это и есть то, что проверяет тест."
      />

      {!template ? (
        <EmptyState title="Выберите шаблон" description="Цифры считаются для шаблона из раздела 01." />
      ) : diversity.isError || information.isError ? (
        <ErrorState
          title="Не удалось посчитать разнообразие"
          onRetry={() => {
            void diversity.refetch();
            void information.refetch();
          }}
        />
      ) : !diversity.data || !information.data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-36 rounded-xl" />
          ))}
        </div>
      ) : (
        <>
          <div className={cn("grid gap-4 sm:grid-cols-2 lg:grid-cols-4", diversity.isFetching && "opacity-60")}>
            <Stat
              value={`${diversity.data.distinct}/${diversity.data.sample}`}
              label="разных экземпляров"
              hint={
                <>
                  Шаблон <span className="font-mono break-all">{diversity.data.template_id}</span> отрендерен{" "}
                  {diversity.data.sample} раз.
                </>
              }
            />
            <Stat
              value={atLeast(diversity.data.collision_probability, diversity.data.sample)}
              label="шанс, что двоим выпадет одно и то же"
              hint="Совпадение текста, кода и набора вариантов у двух случайных попыток."
            />
            <Stat
              value={atLeast(diversity.data.leak_match_share, diversity.data.sample)}
              label={`новых совпадут с ${diversity.data.leak_size} слитыми`}
              hint={`Даже если слить ${diversity.data.leak_size} экземпляров с ответами, остальные кандидаты получат другие.`}
            />
            <Stat
              value={`${percent(information.data.template_overlap)} → ${percent(information.data.instance_overlap, 2)}`}
              label="общих шаблонов → общих заданий"
              hint={`У двух тестов на ${middle} из 30 симулированных подряд: шаблоны могут повторяться, конкретные задания — почти никогда. Шаблоны с долей показов выше 25% временно исключаются, поэтому в короткой серии общих шаблонов меньше, чем в отчёте валидации по всей популяции (там около 40%); общих заданий и там доли процента.`}
            />
          </div>
          <div className="flex items-start gap-3 rounded-xl border bg-primary-tint/50 p-4 text-sm leading-relaxed">
            <ShieldCheck className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
            <p>
              Кроме параметризации: лимит времени на каждое задание считает сервер, вернуться назад нельзя, уходы со
              вкладки фиксируются флагом, а между попытками на тот же грейд — 30 дней. LLM не выдаёт задания
              кандидатам: он только пишет черновики шаблонов, которые проходят ревью и калибровку.
            </p>
          </div>
        </>
      )}
    </section>
  );
}

// ——— Страница ———

export default function HowItWorksPage() {
  const overview = useExplainerOverview();
  const [specialization, setSpecialization] = useState<string>();
  const [templateBySpec, setTemplateBySpec] = useState<Record<string, string>>({});

  const specs = overview.data?.specializations ?? [];
  const activeSpec = specialization ?? specs[0]?.slug;
  const templates = useExplainerTemplates(activeSpec);
  const list = templates.data ?? [];
  const chosenId = activeSpec ? templateBySpec[activeSpec] : undefined;
  const template = list.find((t) => t.id === chosenId) ?? defaultTemplate(list);

  return (
    <>
      <Trace width={300} height={200} radius={44} className="absolute top-24 -right-16 hidden xl:block" />

      <section className="max-w-4xl space-y-6 pt-12 pb-10 lg:pt-16">
        <div className="inline-flex items-center gap-2.5 rounded-full border-[1.5px] border-primary px-3.5 py-1.5 font-mono text-sm font-medium text-primary">
          <span className="size-2 animate-pulse-dot rounded-full bg-destructive" aria-hidden />
          Механика тестирования
        </div>
        <h1 className="text-[clamp(40px,8vw,84px)] leading-[0.98] font-extrabold tracking-[-0.03em]">
          Как работает <span className="text-primary">тест</span>
        </h1>
        <p className="max-w-[46em] text-base leading-relaxed text-muted-foreground">
          Грейд определяет только тест: калиброванный банк параметризованных шаблонов, двухэтапная адаптивная сборка
          и оценка на общей IRT-шкале специализации. Всё ниже считается вживую тем же кодом, что проводит настоящий
          тест.
        </p>
      </section>

      {overview.isPending ? (
        <div className="space-y-4 pb-16" aria-busy="true" aria-label="Загрузка">
          <Skeleton className="h-10 w-full max-w-lg" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      ) : overview.isError ? (
        <ErrorState className="mb-16" onRetry={() => void overview.refetch()} />
      ) : specs.length === 0 || !activeSpec ? (
        <EmptyState className="mb-16" title="Тестов пока нет" description="Банк заданий ещё не загружен." />
      ) : (
        <>
          <dl className="grid grid-cols-2 border-t-[1.5px] border-ink sm:grid-cols-4">
            {[
              { label: "Шаблонов в банке", value: overview.data.active_templates },
              { label: "Специализаций", value: specs.length },
              {
                label: "Заданий в тесте",
                value: `${overview.data.stage1_items + overview.data.stage2_items}+${overview.data.extra_items_max}`,
              },
              { label: "Грейдов на шкале", value: overview.data.grades.length },
            ].map((fact) => (
              <div key={fact.label} className="pt-4 pr-4 pb-2">
                <dt className="font-mono text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">
                  {fact.label}
                </dt>
                <dd className="mt-1 font-mono text-2xl font-bold tabular-nums">{fact.value}</dd>
              </div>
            ))}
          </dl>

          <div className="sticky top-0 z-20 -mx-4 mt-8 border-b border-border-subtle bg-background/95 px-4 py-3 backdrop-blur sm:-mx-8 sm:px-8 lg:-mx-16 lg:px-16">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
              <span className="font-mono text-xs font-medium tracking-[0.06em] text-muted-foreground uppercase">
                Специализация
              </span>
              <Pills
                label="Специализация"
                value={activeSpec}
                onChange={setSpecialization}
                options={specs.map((s) => ({ value: s.slug, label: s.name.replace(/-разработка$/, "") }))}
              />
            </div>
          </div>

          <TemplatesSection
            key={activeSpec}
            specialization={activeSpec}
            overview={overview.data}
            template={template}
            templates={list}
            templatesState={{
              isPending: templates.isPending,
              isError: templates.isError,
              refetch: () => void templates.refetch(),
            }}
            onTemplate={(id) => setTemplateBySpec((prev) => ({ ...prev, [activeSpec]: id }))}
          />
          <AdaptiveSection specialization={activeSpec} overview={overview.data} />
          <LeakSection specialization={activeSpec} overview={overview.data} template={template} />
        </>
      )}

      <section className="my-6 grid gap-6 rounded-2xl bg-ink p-6 text-ink-foreground sm:p-10 lg:grid-cols-[1.4fr_1fr] lg:items-center">
        <div className="space-y-3">
          <h2 className="text-2xl font-extrabold sm:text-3xl">Проверьте на себе</h2>
          <p className="text-sm leading-relaxed opacity-80 sm:text-base">
            Около 25 минут, по одному заданию на экран. Результат — категория «специализация × грейд», которую видят
            работодатели.
          </p>
        </div>
        <div className="flex flex-wrap gap-3 lg:justify-end">
          <Button asChild size="lg">
            <Link to="/register?role=candidate">
              <UserRound /> Пройти тест
            </Link>
          </Button>
          <Button asChild size="lg" variant="ink" className="border border-ink-foreground/30">
            <a href="/api/docs">
              <BookOpen /> Документация API <ArrowRight />
            </a>
          </Button>
        </div>
      </section>
    </>
  );
}
