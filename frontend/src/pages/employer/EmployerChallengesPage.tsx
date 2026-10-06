import { zodResolver } from "@hookform/resolvers/zod";
import { Check, ChevronDown, Inbox, Loader2, Pencil, Plus, Send, Trash2, Trophy } from "lucide-react";
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
import { apiError, applyValidationErrors } from "@/lib/api-error";
import {
  CHALLENGE_LIMITS,
  type Challenge,
  type ChallengeCreate,
  type ChallengeTextIssue,
  useChallengeAction,
  useChallengeSolvers,
  useCreateChallenge,
  useEmployerChallenges,
  useUpdateChallenge,
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

const L = CHALLENGE_LIMITS;
const optionText = (line: string) => line.replace(/^\*\s*/, "");
const toNumber = (value: string) => Number(value.trim().replace(",", "."));
const isInteger = (value: string) => /^\d+$/.test(value.trim());

const questionSchema = z
  .object({
    kind: z.enum(["single_choice", "multi_choice", "numeric", "open_approach"]),
    text: z
      .string()
      .trim()
      .min(1, "Напишите вопрос")
      .max(L.questionTextMax, `Не длиннее ${L.questionTextMax} символов`),
    // Фрагмент кода в форме не редактируется, но при правке черновика сохраняется
    code: z.string(),
    options: z.string(),
    number: z.string(),
    tolerance: z.string(),
    rubric: z.string(),
  })
  .superRefine((q, ctx) => {
    if (q.kind === "single_choice" || q.kind === "multi_choice") {
      const options = lines(q.options);
      const correct = options.filter((line) => line.startsWith("*")).length;
      const texts = options.map((line) => optionText(line).toLowerCase());
      const issue = (message: string) => ctx.addIssue({ code: "custom", path: ["options"], message });
      if (options.length < L.optionsMin || options.length > L.optionsMax)
        issue(`Нужно от ${L.optionsMin} до ${L.optionsMax} вариантов`);
      else if (texts.some((text) => !text)) issue("Вариант не может быть пустым");
      else if (texts.some((text) => text.length > L.optionTextMax))
        issue(`Вариант — не длиннее ${L.optionTextMax} символов`);
      else if (new Set(texts).size !== texts.length) issue("Варианты ответа не должны повторяться");
      else if (q.kind === "single_choice" && correct !== 1) issue("Отметьте звёздочкой ровно один верный вариант");
      else if (correct < 1) issue("Отметьте звёздочкой верные варианты");
    }
    if (q.kind === "numeric") {
      if (q.number.trim() === "" || !Number.isFinite(toNumber(q.number)))
        ctx.addIssue({ code: "custom", path: ["number"], message: "Укажите верный ответ числом" });
      const tolerance = q.tolerance.trim() === "" ? 0 : toNumber(q.tolerance);
      if (!Number.isFinite(tolerance) || tolerance < 0)
        ctx.addIssue({ code: "custom", path: ["tolerance"], message: "Отклонение — неотрицательное число" });
    }
    if (q.kind === "open_approach") {
      const rubric = lines(q.rubric);
      if (rubric.length > L.rubricMax)
        ctx.addIssue({ code: "custom", path: ["rubric"], message: `Не больше ${L.rubricMax} критериев` });
      else if (rubric.some((item) => item.length > L.rubricItemMax))
        ctx.addIssue({ code: "custom", path: ["rubric"], message: `Критерий — не длиннее ${L.rubricItemMax} символов` });
    }
  });

const challengeSchema = z
  .object({
    title: z.string().trim().min(1, "Название обязательно").max(L.titleMax, `Не длиннее ${L.titleMax} символов`),
    description: z
      .string()
      .trim()
      .min(1, "Опишите, кого ищете")
      .max(L.descriptionMax, `Не длиннее ${L.descriptionMax} символов`),
    specialization: z.string().min(1, "Выберите специализацию"),
    grade: z.string(),
    timePerQuestion: z
      .string()
      .refine(
        (value) =>
          value.trim() === "" ||
          (isInteger(value) && Number(value) >= L.timePerQuestionMinSec && Number(value) <= L.timePerQuestionMaxSec),
        `Целое число от ${L.timePerQuestionMinSec} до ${L.timePerQuestionMaxSec}`,
      ),
    perAttempt: z.string(),
    questions: z
      .array(questionSchema)
      .min(L.questionsMin, `Нужно хотя бы ${L.questionsMin} вопроса`)
      .max(L.questionsMax, `Не больше ${L.questionsMax} вопросов`),
  })
  .superRefine((values, ctx) => {
    const sample = values.perAttempt.trim();
    if (sample && (!isInteger(sample) || Number(sample) < L.questionsMin || Number(sample) > values.questions.length))
      ctx.addIssue({
        code: "custom",
        path: ["perAttempt"],
        message: `Целое число от ${L.questionsMin} до числа вопросов (${values.questions.length})`,
      });
  });
type ChallengeFormValues = z.infer<typeof challengeSchema>;
type QuestionFormValues = ChallengeFormValues["questions"][number];

const emptyQuestion = (kind: Kind = "single_choice"): QuestionFormValues => ({
  kind,
  text: "",
  code: "",
  options: "",
  number: "",
  tolerance: "0",
  rubric: "",
});

const emptyChallenge = (): ChallengeFormValues => ({
  title: "",
  description: "",
  specialization: "",
  grade: "",
  timePerQuestion: String(L.timePerQuestionDefaultSec),
  perAttempt: "",
  questions: [emptyQuestion(), emptyQuestion(), emptyQuestion("open_approach")],
});

/** Черновик → значения формы: верные варианты снова со звёздочкой, критерии и варианты — по строке. */
function toFormValues(challenge: Challenge): ChallengeFormValues {
  return {
    title: challenge.title,
    description: challenge.description,
    specialization: challenge.specialization,
    grade: challenge.grade ?? "",
    timePerQuestion: challenge.time_per_question_sec != null ? String(challenge.time_per_question_sec) : "",
    perAttempt: challenge.questions_per_attempt != null ? String(challenge.questions_per_attempt) : "",
    questions: challenge.questions.map((q) => ({
      kind: q.kind,
      text: q.text,
      code: q.code ?? "",
      options: (q.options ?? []).map((o) => `${o.correct ? "* " : ""}${o.text}`).join("\n"),
      number: q.number != null ? String(q.number) : "",
      tolerance: String(q.tolerance ?? 0),
      rubric: (q.rubric ?? []).join("\n"),
    })),
  };
}

function toBody(values: ChallengeFormValues, skills: string[]): ChallengeCreate {
  return {
    title: values.title,
    description: values.description,
    specialization: values.specialization,
    grade: values.grade ? (values.grade as (typeof GRADES)[number]) : null,
    skills,
    time_per_question_sec: values.timePerQuestion.trim() ? Number(values.timePerQuestion) : null,
    questions_per_attempt: values.perAttempt.trim() ? Number(values.perAttempt) : null,
    questions: values.questions.map((q) => ({
      kind: q.kind,
      text: q.text,
      code: q.code.trim() || null,
      options:
        q.kind === "single_choice" || q.kind === "multi_choice"
          ? lines(q.options).map((line) => ({ text: optionText(line), correct: line.startsWith("*") }))
          : [],
      number: q.kind === "numeric" ? toNumber(q.number) : null,
      tolerance: q.kind === "numeric" && q.tolerance.trim() ? toNumber(q.tolerance) : 0,
      rubric: q.kind === "open_approach" ? lines(q.rubric) : [],
    })),
  };
}

// 422 Pydantic: поле — последний элемент loc (вложенные ошибки вопросов уходят в общее сообщение формы)
const challengeFieldMap = {
  title: "title",
  description: "description",
  specialization: "specialization",
  time_per_question_sec: "timePerQuestion",
  questions_per_attempt: "perAttempt",
} as const;

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
            description={`Создайте первый: ${L.questionsMin}–${L.questionsMax} вопросов с выбором, числом или открытым ответом. Публикуйте, когда будете готовы.`}
          />
        )}
        {challenges.data?.map((challenge) => <ChallengeItem key={challenge.id} challenge={challenge} />)}
      </div>
    </>
  );
}

interface ChallengeFormProps {
  /** Черновик для правки; без него форма создаёт новый челлендж. */
  challenge?: Challenge;
  /** Почему черновик не опубликовался — показывается над формой, чтобы было видно, что исправить. */
  notice?: string | null;
  onDone: () => void;
}

function ChallengeForm({ challenge, notice, onDone }: ChallengeFormProps) {
  const specializations = useSpecializations();
  const create = useCreateChallenge();
  const update = useUpdateChallenge();
  const saving = create.isPending || update.isPending;
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ChallengeFormValues>({
    resolver: zodResolver(challengeSchema),
    defaultValues: challenge ? toFormValues(challenge) : emptyChallenge(),
  });
  const { fields, append, remove } = useFieldArray({ control, name: "questions" });
  const kinds = useWatch({ control, name: "questions" });
  const questionsError = errors.questions?.message ?? errors.questions?.root?.message;
  const p = challenge ? `ch${challenge.id}` : "ch-new";

  const submit = async (values: ChallengeFormValues) => {
    setFormError(null);
    try {
      if (challenge) await update.mutateAsync({ id: challenge.id, body: toBody(values, challenge.skills ?? []) });
      else await create.mutateAsync(toBody(values, []));
      onDone();
    } catch (err) {
      if (!applyValidationErrors(err, setError, challengeFieldMap)) setFormError(apiError(err).message);
    }
  };

  return (
    <Card className={challenge ? undefined : "mb-6"}>
      <CardHeader>
        <CardTitle>{challenge ? `Черновик · ${challenge.title}` : "Новый челлендж"}</CardTitle>
        <CardDescription>
          Сохраняется черновиком — опубликуйте его из списка. Варианты ответа пишите по одному в строке, верные отметьте
          звёздочкой в начале: «* 201 Created». Кандидаты увидят варианты в своём порядке и без звёздочек.
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(submit)} noValidate>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <FormAlert message={notice ?? null} className="md:col-span-2" />
          <FormField id={`${p}-title`} label="Название" error={errors.title?.message} className="md:col-span-2">
            <Input id={`${p}-title`} aria-invalid={!!errors.title} {...register("title")} />
          </FormField>
          <FormField id={`${p}-desc`} label="Кого ищете" error={errors.description?.message} className="md:col-span-2">
            <Textarea id={`${p}-desc`} rows={3} aria-invalid={!!errors.description} {...register("description")} />
          </FormField>
          <FormField id={`${p}-spec`} label="Специализация" error={errors.specialization?.message}>
            <Select id={`${p}-spec`} aria-invalid={!!errors.specialization} {...register("specialization")}>
              <option value="">Выберите</option>
              {specializations.data?.map((spec) => (
                <option key={spec.slug} value={spec.slug}>
                  {SPECIALIZATION_FULL_LABELS[spec.slug] ?? spec.name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField id={`${p}-grade`} label="Грейд">
            <Select id={`${p}-grade`} {...register("grade")}>
              <option value="">Любой</option>
              {GRADES.map((grade) => (
                <option key={grade} value={grade}>
                  {GRADE_LABELS[grade]}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField
            id={`${p}-time`}
            label="Секунд на вопрос"
            hint={`От ${L.timePerQuestionMinSec} до ${L.timePerQuestionMaxSec}, считает сервер`}
            error={errors.timePerQuestion?.message}
          >
            <Input
              id={`${p}-time`}
              type="number"
              inputMode="numeric"
              min={L.timePerQuestionMinSec}
              max={L.timePerQuestionMaxSec}
              aria-invalid={!!errors.timePerQuestion}
              {...register("timePerQuestion")}
            />
          </FormField>
          <FormField
            id={`${p}-sample`}
            label="Показывать кандидату вопросов"
            hint="Пусто — все. Меньше, чем написано, — каждому достанется своя случайная часть"
            error={errors.perAttempt?.message}
          >
            <Input
              id={`${p}-sample`}
              type="number"
              inputMode="numeric"
              min={L.questionsMin}
              aria-invalid={!!errors.perAttempt}
              {...register("perAttempt")}
            />
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
                      id={`${p}-q${index}-kind`}
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
                  <FormField id={`${p}-q${index}-text`} label="Вопрос" error={err?.text?.message}>
                    <Textarea id={`${p}-q${index}-text`} rows={2} {...register(`questions.${index}.text`)} />
                  </FormField>
                  {(kind === "single_choice" || kind === "multi_choice") && (
                    <FormField
                      id={`${p}-q${index}-options`}
                      label="Варианты, по одному в строке; верные — со звёздочкой"
                      error={err?.options?.message}
                    >
                      <Textarea
                        id={`${p}-q${index}-options`}
                        rows={4}
                        placeholder={"* Верный вариант\nНеверный вариант"}
                        {...register(`questions.${index}.options`)}
                      />
                    </FormField>
                  )}
                  {kind === "numeric" && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <FormField id={`${p}-q${index}-number`} label="Верный ответ" error={err?.number?.message}>
                        <Input id={`${p}-q${index}-number`} inputMode="decimal" {...register(`questions.${index}.number`)} />
                      </FormField>
                      <FormField id={`${p}-q${index}-tol`} label="Допустимое отклонение" error={err?.tolerance?.message}>
                        <Input
                          id={`${p}-q${index}-tol`}
                          inputMode="decimal"
                          aria-invalid={!!err?.tolerance}
                          {...register(`questions.${index}.tolerance`)}
                        />
                      </FormField>
                    </div>
                  )}
                  {kind === "open_approach" && (
                    <FormField
                      id={`${p}-q${index}-rubric`}
                      label={`На что смотреть в ответе (по строке, до ${L.rubricMax}, необязательно)`}
                      hint="Ответ не оценивается автоматически — вы прочитаете его в списке решивших"
                      error={err?.rubric?.message}
                    >
                      <Textarea id={`${p}-q${index}-rubric`} rows={3} {...register(`questions.${index}.rubric`)} />
                    </FormField>
                  )}
                </li>
              );
            })}
          </ol>
          <div className="grid gap-2 md:col-span-2">
            {questionsError && (
              <p className="text-xs font-medium text-destructive-strong" role="alert">
                {questionsError}
              </p>
            )}
            <div>
              <Button
                type="button"
                variant="outline"
                onClick={() => append(emptyQuestion())}
                disabled={fields.length >= L.questionsMax}
              >
                <Plus /> Добавить вопрос
              </Button>
            </div>
          </div>
          <FormAlert message={formError} className="md:col-span-2" />
        </CardContent>
        <CardFooter className="flex-wrap gap-3 border-t border-border-subtle pt-5">
          <Button type="submit" disabled={saving}>
            {saving ? <Loader2 className="animate-spin" /> : <Plus />} Сохранить черновик
          </Button>
          <Button type="button" variant="ghost" onClick={onDone}>
            Отмена
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

/** Сообщение об ошибке публикации; у 409 challenge_text_discriminatory — с найденными фрагментами. */
function actionErrorMessage(error: unknown): string {
  const { message, details } = apiError(error);
  const issues = (details as { issues?: ChallengeTextIssue[] } | null)?.issues ?? [];
  if (issues.length === 0) return message;
  return `${message}: ${issues.map((issue) => `«${issue.fragment}» — ${issue.label}`).join("; ")}`;
}

function ChallengeItem({ challenge }: { challenge: Challenge }) {
  const action = useChallengeAction();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const scope = `${SPECIALIZATION_FULL_LABELS[challenge.specialization] ?? challenge.specialization} · ${
    challenge.grade ? GRADE_LABELS[challenge.grade] : "все грейды"
  }`;
  const actionError = action.isError ? actionErrorMessage(action.error) : null;
  const { stats } = challenge;

  if (editing && challenge.status === "draft") {
    return (
      <ChallengeForm
        challenge={challenge}
        notice={actionError}
        onDone={() => {
          // Текст исправлен или правка отменена: старая ошибка публикации больше не актуальна
          action.reset();
          setEditing(false);
        }}
      />
    );
  }
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
        <Button
          variant="outline"
          size="sm"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-label={`Решившие «${challenge.title}»`}
        >
          <ChevronDown className={open ? "rotate-180" : undefined} /> Решившие
        </Button>
      </CardHeader>
      {(challenge.status !== "closed" || action.isError) && (
        <CardContent className="flex flex-wrap items-center gap-3">
          {challenge.status === "draft" && (
            <>
              <Button
                size="sm"
                onClick={() => action.mutate({ id: challenge.id, action: "publish" })}
                disabled={action.isPending}
                aria-label={`Опубликовать «${challenge.title}»`}
              >
                Опубликовать
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditing(true)}
                disabled={action.isPending}
                aria-label={`Редактировать «${challenge.title}»`}
              >
                <Pencil /> Редактировать
              </Button>
            </>
          )}
          {challenge.status === "published" && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => action.mutate({ id: challenge.id, action: "close" })}
              disabled={action.isPending}
              aria-label={`Закрыть «${challenge.title}»`}
            >
              Закрыть
            </Button>
          )}
          <FormAlert message={actionError} className="w-full" />
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
  // Повторное приглашение того же кандидата сервер отклонит — после отправки кнопку выключаем
  const [invited, setInvited] = useState<ReadonlySet<number>>(() => new Set());
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
                invited.has(solver.candidate.id) ? (
                  <Button size="sm" variant="outline" disabled>
                    <Check /> Приглашение отправлено
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={() => setInviteTarget(solver.candidate)}
                    aria-label={`Пригласить ${solver.candidate.display_name}`}
                  >
                    <Send /> Пригласить
                  </Button>
                )
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
            {solver.open_answers.map((answer, index) => (
              <div key={index} className="grid gap-1 text-sm">
                <span className="font-medium">{answer.question}</span>
                <p className="rounded-md bg-muted p-3 whitespace-pre-line">{answer.answer || "Ответа нет"}</p>
              </div>
            ))}
          </li>
        ))}
      </ol>
      <InviteDialog
        key={inviteTarget?.id ?? "none"}
        open={inviteTarget !== null}
        onOpenChange={(value) => !value && setInviteTarget(null)}
        candidate={inviteTarget}
        onSent={(invitation) => setInvited((current) => new Set(current).add(invitation.candidate.id))}
      />
    </>
  );
}

