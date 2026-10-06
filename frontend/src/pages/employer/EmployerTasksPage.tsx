import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, ChevronDown, Inbox, ListChecks, Loader2, Plus, Send, Star, XCircle } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
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
import { type CandidateBrief, parseId, useNeed, useNeeds } from "@/lib/employer-queries";
import { formatDate, formatDateTime, toPercent } from "@/lib/format";
import { GRADE_LABELS, GRADED_BY_LABELS, SPECIALIZATION_FULL_LABELS, TASK_KIND_LABELS } from "@/lib/labels";
import {
  type EmployerTask,
  type TaskSubmission,
  useCreateTask,
  useEmployerTasks,
  useRateSubmission,
  useTaskSubmissions,
  useTaskTemplates,
} from "@/lib/task-queries";
import { useSpecializations } from "@/lib/testing-queries";

const GRADES = ["intern", "junior", "middle", "senior"] as const;
const RATINGS = [1, 2, 3, 4, 5] as const;

const taskSchema = z
  .object({
    title: z.string().trim().min(3, "Укажите название"),
    kind: z.enum(["auto", "approach"]),
    needId: z.string(),
    specialization: z.string(),
    grade: z.string(),
    templateId: z.string(),
    prompt: z.string().trim().max(4000, "Не больше 4000 символов"),
    rubric: z.string(),
  })
  .refine((values) => values.needId !== "" || values.specialization !== "", {
    path: ["specialization"],
    message: "Выберите потребность или специализацию",
  })
  .refine((values) => values.kind !== "auto" || values.templateId !== "", {
    path: ["templateId"],
    message: "Выберите тему и уровень",
  })
  .refine((values) => values.kind !== "approach" || values.prompt.length > 0, {
    path: ["prompt"],
    message: "Опишите задачу",
  });

type TaskFormValues = z.infer<typeof taskSchema>;

const fieldMap = {
  title: "title",
  specialization: "specialization",
  pool: "templateId",
  prompt: "prompt",
  rubric: "rubric",
} as const;

export default function EmployerTasksPage() {
  const tasks = useEmployerTasks();
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        eyebrow="Задания"
        title="Задания для кандидатов"
        description="Короткие задания для кандидатов категории: задание из банка с автопроверкой по выбранной теме или вопрос о подходе. Каждому кандидату предлагается одно задание в неделю; верные решения подтверждают навыки, ответы видны обезличенно."
        actions={
          <Button onClick={() => setCreating((value) => !value)} variant={creating ? "outline" : "default"}>
            <Plus /> {creating ? "Скрыть форму" : "Новое задание"}
          </Button>
        }
      />
      {creating && <CreateTaskCard onCreated={() => setCreating(false)} />}
      <div className="grid gap-4">
        {tasks.isPending && <SkeletonCards count={2} />}
        {tasks.isError && <ErrorState description={apiError(tasks.error).message} onRetry={() => void tasks.refetch()} />}
        {tasks.isSuccess && tasks.data.length === 0 && !creating && (
          <EmptyState
            icon={ListChecks}
            title="Заданий пока нет"
            description="Создайте первое задание: выберите тему из банка под потребность или задайте вопрос о подходе с чек-листом."
            action={
              <Button onClick={() => setCreating(true)}>
                <Plus /> Новое задание
              </Button>
            }
          />
        )}
        {tasks.data?.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </div>
    </>
  );
}

function CreateTaskCard({ onCreated }: { onCreated: () => void }) {
  const needs = useNeeds();
  const specializations = useSpecializations();
  const create = useCreateTask();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<TaskFormValues>({
    resolver: zodResolver(taskSchema),
    defaultValues: {
      title: "",
      kind: "auto",
      needId: "",
      specialization: "",
      grade: "",
      templateId: "",
      prompt: "",
      rubric: "",
    },
  });
  const [kind, rawNeedId, rawSpecialization] = useWatch({ control, name: ["kind", "needId", "specialization"] });
  const needId = parseId(rawNeedId);
  const specialization = rawSpecialization || null;
  const templates = useTaskTemplates(specialization, needId, kind === "auto");

  const submit = async (values: TaskFormValues) => {
    setFormError(null);
    const need = needs.data?.find((item) => item.id === needId);
    try {
      await create.mutateAsync({
        title: values.title,
        kind: values.kind,
        need_id: needId,
        specialization: need?.specialization ?? values.specialization,
        grade: values.grade ? (values.grade as (typeof GRADES)[number]) : null,
        pool: values.kind === "auto" ? values.templateId : null,
        prompt: values.kind === "approach" ? values.prompt : null,
        rubric:
          values.kind === "approach"
            ? values.rubric
                .split("\n")
                .map((line) => line.trim())
                .filter(Boolean)
            : [],
      });
      onCreated();
    } catch (err) {
      if (!applyValidationErrors(err, setError, fieldMap)) setFormError(apiError(err).message);
    }
  };

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Новое задание</CardTitle>
        <CardDescription>
          С потребностью задание получают кандидаты её категории, а темы подбираются под её навыки — тот же
          blueprint, что в «Проверке под вакансию».
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(submit)} noValidate>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <FormField id="task-title" label="Название" error={errors.title?.message} className="md:col-span-2">
            <Input id="task-title" aria-invalid={!!errors.title} {...register("title")} />
          </FormField>
          <FormField id="task-kind" label="Вид">
            <Select id="task-kind" {...register("kind")}>
              <option value="auto">{TASK_KIND_LABELS.auto} — задание из банка</option>
              <option value="approach">{TASK_KIND_LABELS.approach} — текст и чек-лист</option>
            </Select>
          </FormField>
          <FormField id="task-need" label="Потребность">
            <Select id="task-need" {...register("needId")}>
              <option value="">Без потребности</option>
              {needs.data?.map((need) => (
                <option key={need.id} value={String(need.id)}>
                  {need.title}
                </option>
              ))}
            </Select>
          </FormField>
          {needId === null && (
            <FormField id="task-spec" label="Специализация" error={errors.specialization?.message}>
              <Select id="task-spec" aria-invalid={!!errors.specialization} {...register("specialization")}>
                <option value="">Выберите</option>
                {specializations.data
                  ?.filter((spec) => spec.has_test)
                  .map((spec) => (
                    <option key={spec.slug} value={spec.slug}>
                      {SPECIALIZATION_FULL_LABELS[spec.slug] ?? spec.name}
                    </option>
                  ))}
              </Select>
            </FormField>
          )}
          <FormField id="task-grade" label="Грейд" hint={needId !== null ? "Пусто — грейд потребности" : undefined}>
            <Select id="task-grade" {...register("grade")}>
              <option value="">{needId !== null ? "Как в потребности" : "Любой"}</option>
              {GRADES.map((grade) => (
                <option key={grade} value={grade}>
                  {GRADE_LABELS[grade]}
                </option>
              ))}
            </Select>
          </FormField>
          {kind === "auto" ? (
            <FormField
              id="task-template"
              label="Тема и уровень"
              error={errors.templateId?.message}
              hint="Каждый кандидат получит своё задание из этой группы банка — с другими числами и вариантами. Тексты заданий заранее не показываются: так банк нельзя выгрузить"
              className="md:col-span-2"
            >
              <Select
                id="task-template"
                aria-invalid={!!errors.templateId}
                disabled={!templates.data}
                {...register("templateId")}
              >
                <option value="">
                  {templates.isFetching
                    ? "Загружаем темы…"
                    : templates.isError
                      ? "Темы не загрузились"
                      : "Выберите тему и уровень"}
                </option>
                {templates.data?.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.matches_need ? "★ " : ""}
                    {option.name}
                    {option.skills.length > 0 && ` · ${option.skills.slice(0, 4).join(", ")}`}
                  </option>
                ))}
              </Select>
            </FormField>
          ) : (
            <>
              <FormField id="task-prompt" label="Задача" error={errors.prompt?.message} className="md:col-span-2">
                <Textarea id="task-prompt" rows={4} aria-invalid={!!errors.prompt} {...register("prompt")} />
              </FormField>
              <FormField
                id="task-rubric"
                label="Чек-лист (по критерию в строке)"
                error={errors.rubric?.message}
                hint="Бинарные критерии, до 6. Без LLM ответ оцениваете вы по шкале 1–5"
                className="md:col-span-2"
              >
                <Textarea id="task-rubric" rows={4} {...register("rubric")} />
              </FormField>
            </>
          )}
          <FormAlert message={formError} className="md:col-span-2" />
        </CardContent>
        <CardFooter className="mt-5">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? <Loader2 className="animate-spin" /> : <Plus />} Создать задание
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

function TaskCard({ task }: { task: EmployerTask }) {
  const [open, setOpen] = useState(false);
  const scope = `${SPECIALIZATION_FULL_LABELS[task.specialization] ?? task.specialization} · ${
    task.grade ? GRADE_LABELS[task.grade] : "все грейды"
  }`;
  return (
    <Card>
      <CardHeader className="grid-cols-[1fr_auto]">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="soft">{TASK_KIND_LABELS[task.kind]}</Badge>
            <Badge variant="muted">{scope}</Badge>
            {task.awaiting_rating > 0 && <Badge variant="outline">ждут оценки: {task.awaiting_rating}</Badge>}
          </div>
          <CardTitle>{task.title}</CardTitle>
          <CardDescription>
            Создано {formatDate(task.created_at)} · предложено {task.assignments_total} · решений {task.submissions}
            {task.pool_name && ` · ${task.pool_name}`}
          </CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
          <ChevronDown className={open ? "rotate-180" : undefined} /> Решения
        </Button>
      </CardHeader>
      {open && (
        <CardContent>
          {task.prompt && <p className="mb-3 text-sm whitespace-pre-line text-muted-foreground">{task.prompt}</p>}
          <Submissions task={task} />
        </CardContent>
      )}
    </Card>
  );
}

function Submissions({ task }: { task: EmployerTask }) {
  const submissions = useTaskSubmissions(task.id);
  const need = useNeed(task.need_id ?? null);
  const [inviteTarget, setInviteTarget] = useState<CandidateBrief | null>(null);

  if (submissions.isPending) return <SkeletonCards count={1} />;
  if (submissions.isError) {
    return <ErrorState description={apiError(submissions.error).message} onRetry={() => void submissions.refetch()} />;
  }
  if (submissions.data.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="Решений пока нет"
        description="Кандидаты категории получают задание при следующем входе в раздел заданий — не чаще раза в неделю."
      />
    );
  }
  return (
    <>
      <div className="grid gap-3">
        {submissions.data.map((submission) => (
          <SubmissionRow
            key={submission.assignment_id}
            task={task}
            submission={submission}
            onInvite={() => setInviteTarget(submission.candidate)}
          />
        ))}
      </div>
      <InviteDialog
        open={inviteTarget !== null}
        onOpenChange={(open) => !open && setInviteTarget(null)}
        candidate={inviteTarget}
        need={need.data ?? null}
      />
    </>
  );
}

function SubmissionRow({
  task,
  submission,
  onInvite,
}: {
  task: EmployerTask;
  submission: TaskSubmission;
  onInvite: () => void;
}) {
  const rate = useRateSubmission(task.id);
  const hits = submission.rubric_hits ?? [];
  const rubric = task.rubric ?? [];
  const href = `/employer/candidates/${submission.candidate.id}${task.need_id ? `?need=${task.need_id}` : ""}`;
  const score =
    submission.score === null || submission.score === undefined
      ? "ждёт оценки"
      : `${toPercent(submission.score)}% · ${submission.graded_by ? GRADED_BY_LABELS[submission.graded_by] : ""}`;

  return (
    <div className="grid gap-3 rounded-lg border p-4">
      <CandidateRow
        candidate={submission.candidate}
        href={href}
        className="border-0 p-0 shadow-none"
        actions={
          <Button size="sm" onClick={onInvite}>
            <Send /> Пригласить
          </Button>
        }
      />
      <div className="grid gap-2 border-t border-border-subtle pt-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono font-bold">{score}</span>
          {submission.submitted_at && (
            <span className="text-muted-foreground">отправлено {formatDateTime(submission.submitted_at)}</span>
          )}
        </div>
        {submission.response?.text && <p className="rounded-md bg-muted p-3 whitespace-pre-line">{submission.response.text}</p>}
        {hits.length > 0 && (
          <ul className="grid gap-1">
            {hits.map((hit, index) => (
              <li key={rubric[index] ?? index} className="flex items-center gap-2">
                {hit ? (
                  <CheckCircle2 className="size-4 text-primary" aria-label="выполнен" />
                ) : (
                  <XCircle className="size-4 text-muted-foreground" aria-label="не выполнен" />
                )}
                {rubric[index]}
              </li>
            ))}
          </ul>
        )}
        {task.kind === "approach" && (
          <div className="flex flex-wrap items-center gap-1">
            <span className="mr-1 text-muted-foreground">Ваша оценка:</span>
            {RATINGS.map((rating) => (
              <Button
                key={rating}
                size="sm"
                variant={submission.employer_rating === rating ? "default" : "outline"}
                onClick={() => rate.mutate({ assignmentId: submission.assignment_id, rating })}
                disabled={rate.isPending}
                aria-label={`Оценка ${rating}`}
              >
                <Star /> {rating}
              </Button>
            ))}
          </div>
        )}
        <FormAlert message={rate.isError ? apiError(rate.error).message : null} />
      </div>
    </div>
  );
}
