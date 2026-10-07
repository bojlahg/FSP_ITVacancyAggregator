import { CalendarClock, CheckCircle2, ListChecks, Loader2, Send, ShieldCheck, SkipForward, Sparkles } from "lucide-react";
import { useState } from "react";
import { ItemAnswerInput } from "@/components/candidate/ItemAnswerInput";
import { CodeBlock } from "@/components/CodeBlock";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { apiError } from "@/lib/api-error";
import { formatDate, formatDateTime, toPercent } from "@/lib/format";
import { ASSIGNMENT_STATUS_LABELS, GRADED_BY_LABELS, TASK_KIND_LABELS } from "@/lib/labels";
import { type AnswerDraft, emptyDraft, isDraftEmpty, toPayload } from "@/lib/test-answer";
import { type TaskAssignment, useMyTasks, useSkipTask, useSubmitTask } from "@/lib/task-queries";

const APPROACH_MAX = 1500;

export default function CandidateTasksPage() {
  const tasks = useMyTasks();
  const active = tasks.data?.filter((task) => task.status === "offered") ?? [];
  const history = tasks.data?.filter((task) => task.status !== "offered") ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Задания"
        title="Регулярные задания"
        description="Короткие задания от работодателей по вашей категории — одно в неделю. Решённые задания подтверждают навыки и держат профиль «свежим» в выдаче. Грейд по-прежнему определяет только тест."
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid min-w-0 content-start gap-4">
          {tasks.isPending && <SkeletonCards count={2} />}
          {tasks.isError && (
            <ErrorState description={apiError(tasks.error).message} onRetry={() => void tasks.refetch()} />
          )}
          {tasks.isSuccess && tasks.data.length === 0 && (
            <EmptyState
              icon={ListChecks}
              title="Активных заданий нет"
              description="Задания предлагаются кандидатам с категорией: не больше одного активного и не чаще раза в неделю. Загляните позже."
            />
          )}
          {active.map((task) => (
            <ActiveTask key={task.id} task={task} />
          ))}
          {history.length > 0 && (
            <section className="grid gap-3">
              <h2 className="font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">История</h2>
              {history.map((task) => (
                <HistoryRow key={task.id} task={task} />
              ))}
            </section>
          )}
        </div>
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="size-4 text-primary" aria-hidden /> Как это работает
            </CardTitle>
            <CardDescription>Задания от работодателей вашей категории</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p className="flex gap-2">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              Верное решение задания с автопроверкой подтверждает навыки — в выдаче они отмечаются «подтверждено
              заданием».
            </p>
            <p className="flex gap-2">
              <CalendarClock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              Свежесть профиля снижается вдвое каждые 90 дней без проверенных действий; проверенное решение её
              обновляет.
            </p>
            <p>Работодатель видит ответ обезличенно и может сразу отправить приглашение.</p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function ActiveTask({ task }: { task: TaskAssignment }) {
  const submit = useSubmitTask();
  const skip = useSkipTask();
  const item = task.item;
  const kind = item?.kind ?? null;
  const [draft, setDraft] = useState<AnswerDraft | null>(() => (item ? emptyDraft(item) : null));
  const [text, setText] = useState("");
  const busy = submit.isPending || skip.isPending;
  const empty = item && kind && draft ? isDraftEmpty(kind, draft) : text.trim() === "";

  const onSubmit = () => {
    const response = item && kind && draft ? toPayload(kind, draft) : { text: text.trim() };
    submit.mutate({ assignmentId: task.id, response });
  };
  const error = submit.isError ? apiError(submit.error).message : skip.isError ? apiError(skip.error).message : null;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="soft">{TASK_KIND_LABELS[task.kind]}</Badge>
          <Badge variant="muted">до {formatDate(task.due_at)}</Badge>
        </div>
        <CardTitle>{task.title}</CardTitle>
        <CardDescription>{task.company_name}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {item && kind && draft ? (
          <>
            <p className="font-mono text-base leading-snug font-bold whitespace-pre-line">{item.stem}</p>
            {item.code && (
              <CodeBlock code={item.code} language={item.code_language} />
            )}
            <ItemAnswerInput item={item} kind={kind} draft={draft} onChange={setDraft} disabled={busy} />
          </>
        ) : (
          <>
            <p className="text-sm whitespace-pre-line">{task.prompt}</p>
            {task.rubric.length > 0 && (
              <div className="rounded-lg bg-muted p-3 text-sm">
                <div className="mb-1 font-medium">Что оценят</div>
                <ul className="list-inside list-disc text-muted-foreground">
                  {task.rubric.map((criterion) => (
                    <li key={criterion}>{criterion}</li>
                  ))}
                </ul>
              </div>
            )}
            <Textarea
              rows={7}
              maxLength={APPROACH_MAX}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Опишите подход: шаги, решения и почему именно так"
              aria-label="Ваш подход"
              disabled={busy}
            />
            <div className="text-right font-mono text-xs text-muted-foreground">
              {text.length}/{APPROACH_MAX}
            </div>
          </>
        )}
        <FormAlert message={error} />
      </CardContent>
      <CardFooter className="flex-wrap justify-between gap-3 border-t border-border-subtle pt-5">
        <Button variant="ghost" onClick={() => skip.mutate(task.id)} disabled={busy}>
          {skip.isPending ? <Loader2 className="animate-spin" /> : <SkipForward />} Пропустить
        </Button>
        <Button onClick={onSubmit} disabled={busy || empty}>
          {submit.isPending ? <Loader2 className="animate-spin" /> : <Send />} Отправить решение
        </Button>
      </CardFooter>
    </Card>
  );
}

function HistoryRow({ task }: { task: TaskAssignment }) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-start justify-between gap-3 pt-6">
        <div className="min-w-0 space-y-1">
          <div className="font-bold">{task.title}</div>
          <div className="text-sm text-muted-foreground">
            {task.company_name} · {TASK_KIND_LABELS[task.kind]}
            {task.submitted_at && ` · отправлено ${formatDateTime(task.submitted_at)}`}
          </div>
          {task.confirmed_skills.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1 text-sm">
              <CheckCircle2 className="size-4 text-primary" aria-hidden />
              Подтверждено заданием:
              {task.confirmed_skills.map((skill) => (
                <Badge key={skill} variant="soft">
                  {skill}
                </Badge>
              ))}
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant={task.status === "submitted" ? "soft" : "muted"}>{ASSIGNMENT_STATUS_LABELS[task.status]}</Badge>
          {task.status === "submitted" && (
            <span className="font-mono text-sm">
              {task.score === null || task.score === undefined
                ? "ждёт проверки"
                : `${toPercent(task.score)}% · ${task.graded_by ? GRADED_BY_LABELS[task.graded_by] : ""}`}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
