import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, Inbox, Loader2, Plus, Send, Trash2, Trophy } from "lucide-react";
import { useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { CandidateRow } from "@/components/employer/CandidateRow";
import { InviteDialog } from "@/components/employer/InviteDialog";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiError } from "@/lib/api-error";
import {
  type Challenge,
  type ChallengeCreate,
  useChallengeAction,
  useChallengeSolvers,
  useCreateChallenge,
  useEmployerChallenges,
} from "@/lib/challenge-queries";
import type { CandidateBrief } from "@/lib/employer-queries";
import { formatDate, formatDateTime, toPercent } from "@/lib/format";
import { GRADE_LABELS, SPECIALIZATION_FULL_LABELS } from "@/lib/labels";
import { useSpecializations } from "@/lib/testing-queries";

const GRADES = ["intern", "junior", "middle", "senior"] as const;
const KINDS = {
  single_choice: "Один верный вариант",
  multi_choice: "Несколько верных вариантов",
  numeric: "Число",
  open_approach: "Открытый ответ",
} as const;
type Kind = keyof typeof KINDS;
const STATUS_LABELS: Record<string, string> = { draft: "черновик", published: "опубликован", closed: "закрыт" };

const lines = (text: string) =>
  text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

const questionSchema = z
  .object({
    kind: z.enum(["single_choice", "multi_choice", "numeric", "open_approach"]),
    text: z.string().trim().min(1, "Напишите вопрос"),
    options: z.string(),
    number: z.string(),
    tolerance: z.string(),
    rubric: z.string(),
  })
  .superRefine((q, ctx) => {
    if (q.kind === "single_choice" || q.kind === "multi_choice") {
      const options = lines(q.options);
      const correct = options.filter((line) => line.startsWith("*")).length;
      if (options.length < 2) ctx.addIssue({ code: "custom", path: ["options"], message: "Нужно хотя бы два варианта" });
      else if (q.kind === "single_choice" && correct !== 1)
        ctx.addIssue({ code: "custom", path: ["options"], message: "Отметьте звёздочкой ровно один верный вариант" });
      else if (correct < 1)
        ctx.addIssue({ code: "custom", path: ["options"], message: "Отметьте звёздочкой верные варианты" });
    }
    if (q.kind === "numeric") {
      const value = q.number.trim().replace(",", ".");
      if (value === "" || !Number.isFinite(Number(value)))
        ctx.addIssue({ code: "custom", path: ["number"], message: "Укажите верный ответ числом" });
    }
  });

const challengeSchema = z.object({
  title: z.string().trim().min(1, "Название обязательно").max(200),
  description: z.string().trim().min(1, "Опишите, кого ищете").max(4000),
  specialization: z.string().min(1, "Выберите специализацию"),
  grade: z.string(),
  timePerQuestion: z.string(),
  perAttempt: z.string(),
  questions: z.array(questionSchema).min(1),
});
type ChallengeFormValues = z.infer<typeof challengeSchema>;

const emptyQuestion = (kind: Kind = "single_choice") => ({
  kind,
  text: "",
  options: "",
  number: "",
  tolerance: "0",
  rubric: "",
});

function toBody(values: ChallengeFormValues): ChallengeCreate {
  return {
    title: values.title,
    description: values.description,
    specialization: values.specialization,
    grade: values.grade ? (values.grade as (typeof GRADES)[number]) : null,
    skills: [],
    time_per_question_sec: values.timePerQuestion ? Number(values.timePerQuestion) : null,
    questions_per_attempt: values.perAttempt ? Number(values.perAttempt) : null,
    questions: values.questions.map((q) => ({
      kind: q.kind,
      text: q.text,
      options:
        q.kind === "single_choice" || q.kind === "multi_choice"
          ? lines(q.options).map((line) => ({ text: line.replace(/^\*\s*/, ""), correct: line.startsWith("*") }))
          : [],
      number: q.kind === "numeric" ? Number(q.number.replace(",", ".")) : null,
      tolerance: q.kind === "numeric" ? Number(q.tolerance.replace(",", ".") || 0) : 0,
      rubric: q.kind === "open_approach" ? lines(q.rubric) : [],
    })),
  };
}

export default function EmployerChallengesPage() {
  const challenges = useEmployerChallenges();
  const [creating, setCreating] = useState(false);
  return (
    <>
      <PageHeader
        eyebrow="Челленджи"
        title="Челленджи компании"
        description="Свои вопросы для кандидатов нужной категории. Кандидаты проходят челлендж по желанию, вы видите решивших по результату — обезличенно, с кнопкой «Пригласить». Вопросы не откалиброваны, поэтому на грейд и навыки кандидата челлендж не влияет."
        actions={
          !creating && (
            <Button onClick={() => setCreating(true)}>
              <Plus /> Новый челлендж
            </Button>
          )
        }
      />
      {creating && <ChallengeForm onDone={() => setCreating(false)} />}
      <div className="grid gap-4">
        {challenges.isPending && <SkeletonCards count={2} />}
        {challenges.isError && (
          <ErrorState description={apiError(challenges.error).message} onRetry={() => void challenges.refetch()} />
        )}
        {challenges.isSuccess && challenges.data.length === 0 && !creating && (
          <EmptyState
            icon={Trophy}
            title="Челленджей пока нет"
            description="Создайте первый: 3–20 вопросов с выбором, числом или открытым ответом. Публикуйте, когда будете готовы."
          />
        )}
        {challenges.data?.map((challenge) => <ChallengeItem key={challenge.id} challenge={challenge} />)}
      </div>
    </>
  );
}

function ChallengeForm({ onDone }: { onDone: () => void }) {
  const specializations = useSpecializations();
  const create = useCreateChallenge();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<ChallengeFormValues>({
    resolver: zodResolver(challengeSchema),
    defaultValues: {
      title: "",
      description: "",
      specialization: "",
      grade: "",
      timePerQuestion: "90",
      perAttempt: "",
      questions: [emptyQuestion(), emptyQuestion(), emptyQuestion("open_approach")],
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "questions" });
  const kinds = useWatch({ control, name: "questions" });

  const submit = async (values: ChallengeFormValues) => {
    setFormError(null);
    try {
      await create.mutateAsync(toBody(values));
      onDone();
    } catch (err) {
      setFormError(apiError(err).message);
    }
  };

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Новый челлендж</CardTitle>
        <CardDescription>
          Сохраняется черновиком — опубликуйте его из списка. Варианты ответа пишите по одному в строке, верные отметьте
          звёздочкой в начале: «* 201 Created». Кандидаты увидят варианты в своём порядке и без звёздочек.
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(submit)} noValidate>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <FormField id="ch-title" label="Название" error={errors.title?.message} className="md:col-span-2">
            <Input id="ch-title" aria-invalid={!!errors.title} {...register("title")} />
          </FormField>
          <FormField id="ch-desc" label="Кого ищете" error={errors.description?.message} className="md:col-span-2">
            <Textarea id="ch-desc" rows={3} aria-invalid={!!errors.description} {...register("description")} />
          </FormField>
          <FormField id="ch-spec" label="Специализация" error={errors.specialization?.message}>
            <Select id="ch-spec" aria-invalid={!!errors.specialization} {...register("specialization")}>
              <option value="">Выберите</option>
              {specializations.data?.map((spec) => (
                <option key={spec.slug} value={spec.slug}>
                  {SPECIALIZATION_FULL_LABELS[spec.slug] ?? spec.name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField id="ch-grade" label="Грейд">
            <Select id="ch-grade" {...register("grade")}>
              <option value="">Любой</option>
              {GRADES.map((grade) => (
                <option key={grade} value={grade}>
                  {GRADE_LABELS[grade]}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField id="ch-time" label="Секунд на вопрос" hint="От 20 до 600, считает сервер">
            <Input id="ch-time" type="number" inputMode="numeric" {...register("timePerQuestion")} />
          </FormField>
          <FormField
            id="ch-sample"
            label="Показывать кандидату вопросов"
            hint="Пусто — все. Меньше, чем написано, — каждому достанется своя случайная часть"
          >
            <Input id="ch-sample" type="number" inputMode="numeric" {...register("perAttempt")} />
          </FormField>

          <ol className="grid gap-4 md:col-span-2">
            {fields.map((field, index) => {
              const kind = kinds[index]?.kind ?? field.kind;
              const err = errors.questions?.[index];
              return (
                <li key={field.id} className="grid gap-3 rounded-lg border p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold text-muted-foreground">#{index + 1}</span>
                    <Select
                      id={`ch-q${index}-kind`}
                      aria-label={`Вид вопроса ${index + 1}`}
                      className="w-auto"
                      {...register(`questions.${index}.kind`)}
                    >
                      {Object.entries(KINDS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </Select>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="ml-auto"
                      onClick={() => remove(index)}
                      disabled={fields.length <= 1}
                      aria-label={`Удалить вопрос ${index + 1}`}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                  <FormField id={`ch-q${index}-text`} label="Вопрос" error={err?.text?.message}>
                    <Textarea id={`ch-q${index}-text`} rows={2} {...register(`questions.${index}.text`)} />
                  </FormField>
                  {(kind === "single_choice" || kind === "multi_choice") && (
                    <FormField
                      id={`ch-q${index}-options`}
                      label="Варианты, по одному в строке; верные — со звёздочкой"
                      error={err?.options?.message}
                    >
                      <Textarea
                        id={`ch-q${index}-options`}
                        rows={4}
                        placeholder={"* Верный вариант\nНеверный вариант"}
                        {...register(`questions.${index}.options`)}
                      />
                    </FormField>
                  )}
                  {kind === "numeric" && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <FormField id={`ch-q${index}-number`} label="Верный ответ" error={err?.number?.message}>
                        <Input id={`ch-q${index}-number`} inputMode="decimal" {...register(`questions.${index}.number`)} />
                      </FormField>
                      <FormField id={`ch-q${index}-tol`} label="Допустимое отклонение">
                        <Input id={`ch-q${index}-tol`} inputMode="decimal" {...register(`questions.${index}.tolerance`)} />
                      </FormField>
                    </div>
                  )}
                  {kind === "open_approach" && (
                    <FormField
                      id={`ch-q${index}-rubric`}
                      label="На что смотреть в ответе (по строке, необязательно)"
                      hint="Ответ не оценивается автоматически — вы прочитаете его в списке решивших"
                    >
                      <Textarea id={`ch-q${index}-rubric`} rows={3} {...register(`questions.${index}.rubric`)} />
                    </FormField>
                  )}
                </li>
              );
            })}
          </ol>
          <div className="md:col-span-2">
            <Button type="button" variant="outline" onClick={() => append(emptyQuestion())}>
              <Plus /> Добавить вопрос
            </Button>
          </div>
          <FormAlert message={formError} className="md:col-span-2" />
        </CardContent>
        <CardFooter className="flex-wrap gap-3 border-t border-border-subtle pt-5">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? <Loader2 className="animate-spin" /> : <Plus />} Сохранить черновик
          </Button>
          <Button type="button" variant="ghost" onClick={onDone}>
            Отмена
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

function ChallengeItem({ challenge }: { challenge: Challenge }) {
  const action = useChallengeAction();
  const [open, setOpen] = useState(false);
  const scope = `${SPECIALIZATION_FULL_LABELS[challenge.specialization] ?? challenge.specialization} · ${
    challenge.grade ? GRADE_LABELS[challenge.grade] : "все грейды"
  }`;
  const issues = (apiError(action.error).details as { issues?: { label: string; fragment: string }[] } | null)?.issues;
  const { stats } = challenge;
  return (
    <Card>
      <CardHeader className="grid-cols-[1fr_auto]">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={challenge.status === "published" ? "default" : "muted"}>
              {STATUS_LABELS[challenge.status]}
            </Badge>
            <Badge variant="muted">{scope}</Badge>
          </div>
          <CardTitle>{challenge.title}</CardTitle>
          <CardDescription>
            Создан {formatDate(challenge.created_at)} · вопросов {challenge.questions.length} · начали {stats.started} ·
            прошли {stats.completed}
            {stats.average_score != null && ` · средний результат ${toPercent(stats.average_score)}%`}
          </CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
          <ChevronDown className={open ? "rotate-180" : undefined} /> Решившие
        </Button>
      </CardHeader>
      {(challenge.status !== "closed" || action.isError) && (
        <CardContent className="flex flex-wrap items-center gap-3">
          {challenge.status === "draft" && (
            <Button
              size="sm"
              onClick={() => action.mutate({ id: challenge.id, action: "publish" })}
              disabled={action.isPending}
            >
              Опубликовать
            </Button>
          )}
          {challenge.status === "published" && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => action.mutate({ id: challenge.id, action: "close" })}
              disabled={action.isPending}
            >
              Закрыть
            </Button>
          )}
          <FormAlert
            message={
              action.isError
                ? `${apiError(action.error).message}${issues?.length ? `: ${issues.map((i) => `«${i.fragment}» — ${i.label}`).join("; ")}` : ""}`
                : null
            }
            className="w-full"
          />
        </CardContent>
      )}
      {open && (
        <CardContent>
          <Solvers challenge={challenge} />
        </CardContent>
      )}
    </Card>
  );
}

function Solvers({ challenge }: { challenge: Challenge }) {
  const solvers = useChallengeSolvers(challenge.id, true);
  const [inviteTarget, setInviteTarget] = useState<CandidateBrief | null>(null);
  if (solvers.isPending) return <SkeletonCards count={1} />;
  if (solvers.isError) {
    return <ErrorState description={apiError(solvers.error).message} onRetry={() => void solvers.refetch()} />;
  }
  if (solvers.data.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="Пока никто не прошёл"
        description={
          challenge.status === "draft"
            ? "Опубликуйте челлендж — его увидят кандидаты выбранной категории."
            : "Кандидаты категории видят челлендж в своём кабинете и проходят по желанию."
        }
      />
    );
  }
  return (
    <>
      <ol className="grid gap-3">
        {solvers.data.map((solver) => (
          <li key={solver.attempt_id} className="grid gap-3 rounded-lg border p-4">
            <CandidateRow
              candidate={solver.candidate}
              href={`/employer/candidates/${solver.candidate.id}`}
              className="border-0 p-0 shadow-none"
              actions={
                <Button size="sm" onClick={() => setInviteTarget(solver.candidate)}>
                  <Send /> Пригласить
                </Button>
              }
            />
            <div className="flex flex-wrap items-center gap-2 border-t border-border-subtle pt-3 text-sm">
              <span className="font-mono font-bold">
                {solver.score != null ? `${toPercent(solver.score)}%` : "только открытые ответы"}
              </span>
              {solver.scored_total > 0 && (
                <span className="text-muted-foreground">
                  верно {solver.correct} из {solver.scored_total}
                </span>
              )}
              {solver.finished_at && (
                <span className="text-muted-foreground">· {formatDateTime(solver.finished_at)}</span>
              )}
            </div>
            {solver.open_answers.map((answer) => (
              <div key={answer.question} className="grid gap-1 text-sm">
                <span className="font-medium">{answer.question}</span>
                <p className="rounded-md bg-muted p-3 whitespace-pre-line">{answer.answer || "Ответа нет"}</p>
              </div>
            ))}
          </li>
        ))}
      </ol>
      <InviteDialog
        open={inviteTarget !== null}
        onOpenChange={(value) => !value && setInviteTarget(null)}
        candidate={inviteTarget}
      />
    </>
  );
}
