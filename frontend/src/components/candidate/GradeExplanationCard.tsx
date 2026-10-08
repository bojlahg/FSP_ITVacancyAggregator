import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, Loader2, MessageSquareWarning, Scale } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { apiError } from "@/lib/api-error";
import { formatDate, toPercent } from "@/lib/format";
import { gradeLabel } from "@/lib/labels";
import {
  type Appeal,
  type GradeDecision,
  legalPath,
  useCreateAppeal,
  useGradeExplanation,
  useMyAppeals,
} from "@/lib/legal-queries";
import { cn } from "@/lib/utils";

function num(value: number): string {
  return value.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * Блок «Как определён грейд» (152-ФЗ ст. 16): решение принимает тест, возражение рассматривает человек.
 * Объяснение свёрнуто — в заголовке θ̂ и пороги; «Оспорить» — отдельной строкой под ним.
 */
export function GradeExplanationCard({ className }: { className?: string }) {
  const explanation = useGradeExplanation();
  const appeals = useMyAppeals();
  const [open, setOpen] = useState(false);

  if (explanation.isPending || appeals.isPending) {
    return (
      <div className={cn("grid gap-4", className)} role="status" aria-busy="true" aria-label="Загрузка">
        <Skeleton className="h-[74px] rounded-xl" />
        <Skeleton className="h-16 rounded-xl" />
      </div>
    );
  }
  if (explanation.isError || appeals.isError) {
    return (
      <div className={cn("rounded-xl border bg-card p-5", className)}>
        <h2 className="mb-3 flex items-center gap-2 font-mono text-base font-bold">
          <Scale className="size-4 text-primary" aria-hidden /> Как определён грейд
        </h2>
        <ErrorState
          variant="block"
          title="Не удалось загрузить объяснение грейда."
          description={apiError(explanation.error ?? appeals.error).message}
          onRetry={() => {
            void explanation.refetch();
            void appeals.refetch();
          }}
        />
      </div>
    );
  }

  const decision = explanation.data.current;
  return (
    <div className={cn("grid gap-4", className)}>
      <section className="rounded-xl border bg-card" aria-labelledby="grade-explanation-title">
        <button
          type="button"
          aria-expanded={open}
          aria-controls="grade-explanation-body"
          onClick={() => setOpen((value) => !value)}
          className="flex w-full items-center gap-3 rounded-xl p-5 text-left transition-colors outline-none hover:bg-muted/50 focus-visible:ring-[3px] focus-visible:ring-ring/40"
        >
          <Scale className="size-4 shrink-0 text-primary" aria-hidden />
          <span className="flex min-w-0 flex-1 flex-col gap-0.5 sm:flex-row sm:flex-wrap sm:items-baseline sm:gap-x-4">
            <span id="grade-explanation-title" className="font-mono text-base font-bold">
              Как определён грейд
            </span>
            <span className="font-mono text-xs text-muted-foreground tabular-nums sm:text-[13px]">
              {decision ? decisionSummary(decision) : "появится после первого теста"}
            </span>
          </span>
          <ChevronDown
            className={cn("size-5 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
            aria-hidden
          />
        </button>
        <div id="grade-explanation-body" hidden={!open} className="space-y-4 border-t border-border-subtle p-5 text-sm">
          <p className="text-muted-foreground">
            Категорию определяет только тест — не резюме, не опрос и не ИИ.{" "}
            <Link to={legalPath("recommendations")} className="text-primary underline underline-offset-4">
              Правила подбора
            </Link>
          </p>
          {decision ? (
            <Decision decision={decision} />
          ) : (
            <p className="text-muted-foreground">
              Категории пока нет. После теста здесь будет видно, с каким порогом сравнивался ваш результат, и появится
              возможность его оспорить.
            </p>
          )}
        </div>
      </section>
      {decision && <AppealBlock decision={decision} appeals={appeals.data} />}
    </div>
  );
}

/** «θ 0,78 ± 0,45 · порог Middle 0,20 · порог Senior 1,20» — видно без раскрытия блока. */
function decisionSummary(decision: GradeDecision): string {
  const parts = [`θ ${num(decision.theta)}${decision.se === null ? "" : ` ± ${num(decision.se)}`}`];
  parts.push(`порог ${gradeLabel(decision.category.grade)} ${num(decision.cut)}`);
  if (decision.next_grade && decision.next_cut !== null) {
    parts.push(`порог ${gradeLabel(decision.next_grade)} ${num(decision.next_cut)}`);
  }
  return parts.join(" · ");
}

function Decision({ decision }: { decision: GradeDecision }) {
  const grade = gradeLabel(decision.category.grade);

  return (
    <div className="space-y-4">
      <p>
        Категорию <b>{decision.category.label}</b> присвоил тест, завершённый{" "}
        <b className="font-mono">{formatDate(decision.tested_at)}</b> Оценка способности θ̂ сравнивается с порогом
        грейда на шкале специализации: θ̂ не ниже порога — грейд подтверждён.
        {decision.result === "confident_pass" && " Результат с запасом больше погрешности — можно пробовать следующий грейд."}
      </p>

      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="θ̂ — ваш результат" value={num(decision.theta)} />
        <Stat label="погрешность SE" value={decision.se === null ? "—" : `± ${num(decision.se)}`} />
        <Stat label={`порог ${grade}`} value={num(decision.cut)} />
        <Stat
          label={decision.next_grade ? `порог ${gradeLabel(decision.next_grade)}` : "перцентиль в категории"}
          value={
            decision.next_cut !== null
              ? num(decision.next_cut)
              : decision.percentile === null
                ? "—"
                : `${toPercent(decision.percentile)}`
          }
        />
      </dl>

      <p className="text-xs text-muted-foreground">
        Результат действует до {formatDate(decision.valid_until)} Подробно о заданиях и шкале —{" "}
        <Link to="/how-it-works" className="text-primary underline underline-offset-4">
          как работает тест
        </Link>
        .
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col-reverse">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-mono text-xl font-extrabold tabular-nums">{value}</dd>
    </div>
  );
}

const appealSchema = z.object({
  comment: z
    .string()
    .trim()
    .min(10, "Опишите подробнее — от 10 символов")
    .max(2000, "Не длиннее 2000 символов"),
});
type AppealValues = z.infer<typeof appealSchema>;

function AppealBlock({ decision, appeals }: { decision: GradeDecision; appeals: Appeal[] }) {
  const [open, setOpen] = useState(false);
  const create = useCreateAppeal();
  const pending = appeals.find(
    (appeal) =>
      appeal.status === "open" &&
      appeal.category.specialization === decision.category.specialization &&
      appeal.category.grade === decision.category.grade,
  );
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<AppealValues>({ resolver: zodResolver(appealSchema), defaultValues: { comment: "" } });

  const onSubmit = async (values: AppealValues) => {
    try {
      await create.mutateAsync(values.comment);
      reset();
      setOpen(false);
    } catch (err) {
      setError("root.server", { message: apiError(err).message });
    }
  };

  return (
    <section aria-label="Оспорить результат" className="space-y-4 rounded-xl border border-border-subtle p-4 text-sm sm:px-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-3xl text-muted-foreground">
          <b className="font-medium text-foreground">Не согласны с результатом?</b> Опишите, что пошло не так.
          Обращение прочитает человек из команды ITScout и ответит здесь. Ответ сам по себе грейд не меняет — изменить
          его может только тест.
        </p>
        {!open && !pending && (
          <Button variant="outline" className="max-sm:w-full" onClick={() => setOpen(true)}>
            <MessageSquareWarning /> Оспорить
          </Button>
        )}
      </div>

      {open && !pending && (
        <form className="grid gap-3" onSubmit={handleSubmit(onSubmit)} noValidate>
          <FormField id="appeal-comment" label="Что не так с результатом" error={errors.comment?.message}>
            <Textarea
              id="appeal-comment"
              rows={4}
              maxLength={2000}
              aria-invalid={!!errors.comment}
              placeholder="Например: в тесте попались задания по стеку, с которым я не работаю"
              {...register("comment")}
            />
          </FormField>
          <FormAlert message={errors.root?.server?.message ?? null} />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="animate-spin" />}
              Отправить на проверку
            </Button>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Отмена
            </Button>
          </div>
        </form>
      )}

      {appeals.length > 0 && (
        <ul className="grid gap-3" aria-label="Мои обращения">
          {appeals.map((appeal) => (
            <li key={appeal.id} className="space-y-2 rounded-lg border border-border-subtle p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={appeal.status === "open" ? "soft" : "muted"}>
                  {appeal.status === "open" ? "на рассмотрении" : "рассмотрено"}
                </Badge>
                <span className="font-mono text-xs text-muted-foreground">
                  {appeal.category.label} · {formatDate(appeal.created_at)}
                </span>
              </div>
              <p className="break-words whitespace-pre-line">{appeal.comment}</p>
              {appeal.reply && (
                <div className="rounded-md bg-primary-tint p-3">
                  <div className="mb-1 font-mono text-xs font-bold text-primary">
                    Ответ{appeal.resolved_at ? ` · ${formatDate(appeal.resolved_at)}` : ""}
                  </div>
                  <p className="break-words whitespace-pre-line">{appeal.reply}</p>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
