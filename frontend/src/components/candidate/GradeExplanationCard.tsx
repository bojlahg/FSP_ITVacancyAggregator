import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, MessageSquareWarning, Scale } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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

function num(value: number): string {
  return value.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Блок «Как определён грейд» (152-ФЗ ст. 16): решение принимает тест, возражение рассматривает человек. */
export function GradeExplanationCard() {
  const explanation = useGradeExplanation();
  const appeals = useMyAppeals();

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Scale className="size-4 text-primary" aria-hidden /> Как определён грейд
        </CardTitle>
        <CardDescription>
          Категорию определяет только тест — не резюме, не опрос и не ИИ.{" "}
          <Link to={legalPath("recommendations")} className="text-primary underline underline-offset-4">
            Правила подбора
          </Link>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5 text-sm">
        {explanation.isPending || appeals.isPending ? (
          <SkeletonCards count={1} />
        ) : explanation.isError || appeals.isError ? (
          <ErrorState
            description={apiError(explanation.error ?? appeals.error).message}
            onRetry={() => {
              void explanation.refetch();
              void appeals.refetch();
            }}
          />
        ) : explanation.data.current === null ? (
          <p className="text-muted-foreground">
            Категории пока нет. После теста здесь будет видно, с каким порогом сравнивался ваш результат, и появится
            возможность его оспорить.
          </p>
        ) : (
          <>
            <Decision decision={explanation.data.current} />
            <Separator />
            <AppealBlock decision={explanation.data.current} appeals={appeals.data} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Decision({ decision }: { decision: GradeDecision }) {
  const grade = gradeLabel(decision.category.grade);
  // Шкала от порога ниже до порога выше с запасом: видно, где θ̂ относительно границ грейда
  const low = decision.cut - 1;
  const high = (decision.next_cut ?? decision.cut + 1) + 0.5;
  const position = (value: number) => `${Math.min(100, Math.max(0, ((value - low) / (high - low)) * 100))}%`;

  return (
    <div className="space-y-4">
      <p>
        Категорию <b>{decision.category.label}</b> присвоил тест, завершённый{" "}
        <b className="font-mono">{formatDate(decision.tested_at)}</b>. Оценка способности θ̂ сравнивается с порогом
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

      <div className="space-y-1.5" aria-hidden>
        <div className="relative h-2 rounded-full bg-muted">
          <span
            className="absolute inset-y-0 rounded-full bg-primary-tint"
            style={{
              left: position(decision.cut),
              right: decision.next_cut !== null ? `calc(100% - ${position(decision.next_cut)})` : 0,
            }}
          />
          {decision.se !== null && (
            <span
              className="absolute inset-y-0 rounded-full bg-primary/30"
              style={{
                left: position(decision.theta - decision.se),
                right: `calc(100% - ${position(decision.theta + decision.se)})`,
              }}
            />
          )}
          <span className="absolute -top-1 h-4 w-0.5 bg-foreground" style={{ left: position(decision.cut) }} />
          {decision.next_cut !== null && (
            <span className="absolute -top-1 h-4 w-0.5 bg-border" style={{ left: position(decision.next_cut) }} />
          )}
          <span
            className="absolute -top-1 size-4 -translate-x-1/2 rounded-full border-2 border-background bg-primary"
            style={{ left: position(decision.theta) }}
          />
        </div>
        <div className="flex justify-between font-mono text-xs text-muted-foreground">
          <span>ниже порога</span>
          <span>{grade}</span>
          <span>{decision.next_grade ? gradeLabel(decision.next_grade) : "выше"}</span>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Результат действует до {formatDate(decision.valid_until)}. Подробно о заданиях и шкале —{" "}
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl space-y-1">
          <h3 className="font-mono text-sm font-bold">Не согласны с результатом?</h3>
          <p className="text-muted-foreground">
            Опишите, что пошло не так. Обращение прочитает человек из команды ITScout и ответит здесь. Ответ сам по себе
            грейд не меняет — изменить его может только тест.
          </p>
        </div>
        {!open && !pending && (
          <Button variant="outline" onClick={() => setOpen(true)}>
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
    </div>
  );
}
