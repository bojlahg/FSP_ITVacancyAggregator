import { Bot, FileText, FlaskConical, Info, Layers, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiError } from "@/lib/api-error";
import { parseId, useNeeds } from "@/lib/employer-queries";
import { GRADE_LABELS, ITEM_KIND_LABELS, SPECIALIZATION_LABELS } from "@/lib/labels";
import { useSkillCatalog } from "@/lib/testing-queries";
import {
  type PreviewItem,
  type VacancyTestPreview,
  type VacancyTestPreviewRequest,
  useVacancyExamples,
  useVacancyTestPreview,
} from "@/lib/vacancy-test-queries";

const MIN_TEXT = 20;
const TEXT_SOURCE = "text";

export default function VacancyTestPage() {
  const [searchParams] = useSearchParams();
  const needs = useNeeds();
  const examples = useVacancyExamples();
  const preview = useVacancyTestPreview();
  const [source, setSource] = useState<string>(() => String(parseId(searchParams.get("need")) ?? TEXT_SOURCE));
  const [text, setText] = useState("");
  const [request, setRequest] = useState<VacancyTestPreviewRequest | null>(null);

  const needId = source === TEXT_SOURCE ? null : parseId(source);
  const canBuild = needId !== null || text.trim().length >= MIN_TEXT;

  const run = (body: VacancyTestPreviewRequest) => {
    setRequest(body);
    preview.mutate(body);
  };
  const build = () => run(needId !== null ? { need_id: needId } : { raw_text: text.trim() });
  const regenerate = (current: VacancyTestPreview) => {
    if (request) run({ ...request, regenerate_seed: current.seed + 1 });
  };

  return (
    <>
      <PageHeader
        eyebrow="Проверка под вакансию"
        title="Проверка под вакансию"
        description="Как платформа проверит кандидата под вашу вакансию: требования → blueprint теста по темам → примеры заданий из калиброванного банка. Повторная генерация даёт другие экземпляры тех же шаблонов той же сложности."
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Источник</CardTitle>
            <CardDescription>Потребность компании или текст вакансии</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <Select aria-label="Потребность" value={source} onChange={(event) => setSource(event.target.value)}>
              <option value={TEXT_SOURCE}>Текст вакансии</option>
              {(needs.data ?? []).map((need) => (
                <option key={need.id} value={String(need.id)}>
                  {need.title}
                </option>
              ))}
            </Select>
            {needs.isError && <FormAlert message={`Потребности не загрузились: ${apiError(needs.error).message}`} />}
            {needId === null && (
              <>
                <Textarea
                  rows={9}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="Вставьте описание вакансии: стек, обязанности, грейд"
                  aria-label="Текст вакансии"
                />
                <div className="space-y-2">
                  <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Демо-вакансии</div>
                  <div className="flex flex-wrap gap-2">
                    {examples.isPending && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />}
                    {examples.isError && <span className="text-xs text-muted-foreground">Не загрузились</span>}
                    {examples.data?.map((example) => (
                      <Button
                        key={example.slug}
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setText(example.raw_text);
                          run({ raw_text: example.raw_text });
                        }}
                      >
                        <FileText /> {example.title}
                      </Button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </CardContent>
          <CardFooter>
            <Button onClick={build} disabled={!canBuild || preview.isPending}>
              {preview.isPending ? <Loader2 className="animate-spin" /> : <FlaskConical />} Построить проверку
            </Button>
          </CardFooter>
        </Card>

        <div className="grid min-w-0 content-start gap-4">
          {preview.isPending && !preview.data && <SkeletonCards count={3} />}
          {preview.isError && (
            <ErrorState
              title="Не удалось построить проверку"
              description={apiError(preview.error).message}
              onRetry={request ? () => run(request) : undefined}
            />
          )}
          {preview.isIdle && (
            <EmptyState
              icon={FlaskConical}
              title="Выберите потребность или вставьте текст"
              description="Покажем разобранные требования, как сместятся веса тем теста и три примера заданий."
            />
          )}
          {preview.data && !preview.isError && (
            <PreviewResult data={preview.data} busy={preview.isPending} onRegenerate={() => regenerate(preview.data)} />
          )}
        </div>
      </div>
    </>
  );
}

function PreviewResult({
  data,
  busy,
  onRegenerate,
}: {
  data: VacancyTestPreview;
  busy: boolean;
  onRegenerate: () => void;
}) {
  const skills = useSkillCatalog();
  const skillNames = useMemo(() => new Map((skills.data ?? []).map((skill) => [skill.id, skill.name])), [skills.data]);
  const name = (id: string) => skillNames.get(id) ?? id;
  const { requirements, blueprint } = data;
  const required = requirements.required_skills ?? [];
  const optional = requirements.optional_skills ?? [];
  const maxItems = Math.max(1, ...blueprint.topics.map((topic) => Math.max(topic.items, topic.base_items)));
  const category = `${SPECIALIZATION_LABELS[blueprint.specialization] ?? blueprint.specialization} · ${
    GRADE_LABELS[blueprint.grade] ?? blueprint.grade
  }`;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>1. Требования</CardTitle>
          <CardDescription>
            {requirements.title ?? "Без названия"} · {category}
            {!requirements.grade && " (грейд не указан — взят Middle)"}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-muted-foreground">Обязательно:</span>
            {required.length === 0 && <span className="text-muted-foreground">—</span>}
            {required.map((skill) => (
              <Badge key={skill} variant="soft">
                {name(skill)}
              </Badge>
            ))}
          </div>
          {optional.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-muted-foreground">Желательно:</span>
              {optional.map((skill) => (
                <Badge key={skill} variant="muted">
                  {name(skill)}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="size-4 text-primary" aria-hidden /> 2. Blueprint под вакансию
          </CardTitle>
          <CardDescription>
            {blueprint.total_items} оцениваемых заданий по темам · {category}
            {blueprint.stack_modules.length > 0 && ` · стек-модули: ${blueprint.stack_modules.join(", ")}`}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-2.5">
            {blueprint.topics.map((topic) => {
              const delta = topic.items - topic.base_items;
              return (
                <div
                  key={topic.topic}
                  className="grid grid-cols-[minmax(0,10rem)_1fr_4.5rem] items-center gap-3 text-sm"
                >
                  <span className="truncate" title={topic.name}>
                    {topic.name}
                  </span>
                  <Progress value={(topic.items / maxItems) * 100} aria-label={`${topic.name}: ${topic.items}`} />
                  <span className="text-right font-mono text-xs">
                    <span className="font-bold">{topic.items}</span>
                    {delta !== 0 && (
                      <span className={delta > 0 ? "text-primary" : "text-muted-foreground"}>
                        {" "}
                        ({delta > 0 ? "+" : ""}
                        {delta})
                      </span>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
          {blueprint.weight_changes.length > 0 && (
            <ul className="grid gap-1 border-t border-border-subtle pt-3 text-xs text-muted-foreground">
              {blueprint.weight_changes.map((change) => (
                <li key={change}>• {change}</li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="grid-cols-[1fr_auto]">
          <div>
            <CardTitle>3. Примеры заданий</CardTitle>
            <CardDescription>
              Генерация seed {data.seed} · ключи ответов не показываются никому, включая работодателя
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={onRegenerate} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <RefreshCw />} Ещё вариант
          </Button>
        </CardHeader>
        <CardContent>
          {data.sample_items.length === 0 ? (
            <p className="text-sm text-muted-foreground">В банке нет шаблонов под эти темы.</p>
          ) : (
            <ol className="grid gap-3">
              {data.sample_items.map((item, index) => (
                <SampleItem key={item.template_id} item={item} index={index} />
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="size-4 text-primary" aria-hidden /> 4. Черновики LLM
          </CardTitle>
          <CardDescription>Для навыков вакансии, которых нет в банке шаблонов</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm">
          {data.uncovered_skills.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-muted-foreground">Нет в банке:</span>
              {data.uncovered_skills.map((skill) => (
                <Badge key={skill.id} variant="muted">
                  {skill.name}
                </Badge>
              ))}
            </div>
          )}
          <p className="flex gap-2 text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden /> {data.llm_note}
          </p>
          {data.llm_drafts.map((draft) => (
            <div key={draft.title} className="rounded-lg border border-dashed p-3">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <Sparkles className="size-3.5 text-primary" aria-hidden />
                <span className="font-bold">{draft.title}</span>
                <Badge variant="muted">pilot · не влияет на оценку до калибровки</Badge>
              </div>
              <p>{draft.stem}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </>
  );
}

function SampleItem({ item, index }: { item: PreviewItem; index: number }) {
  return (
    <li className="rounded-lg border p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs font-bold text-muted-foreground">#{index + 1}</span>
        <Badge variant="soft">{item.topic_name}</Badge>
        <Badge variant="muted">
          {item.difficulty} · b={item.difficulty_b.toFixed(2)}
        </Badge>
        <Badge variant="muted">{ITEM_KIND_LABELS[item.kind] ?? item.kind}</Badge>
      </div>
      <p className="text-sm whitespace-pre-line">{item.stem}</p>
      {item.code && (
        <div className="mt-2 overflow-hidden rounded-lg bg-ink text-ink-foreground">
          {item.code_language && (
            <div className="border-b border-ink-foreground/15 px-3 py-1 font-mono text-xs opacity-70">
              {item.code_language}
            </div>
          )}
          <pre className="overflow-x-auto p-3 font-mono text-xs leading-relaxed">
            <code>{item.code}</code>
          </pre>
        </div>
      )}
      {item.options.length > 0 && (
        <ul className="mt-2 grid gap-1 text-sm">
          {item.options.map((option) => (
            <li key={option.id} className="flex gap-2">
              <span className="font-mono text-xs text-muted-foreground">{option.id})</span>
              <span>{option.text}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 font-mono text-xs text-muted-foreground">
        шаблон {item.template_id} · навыки: {item.skills.join(", ") || "—"}
      </div>
    </li>
  );
}
