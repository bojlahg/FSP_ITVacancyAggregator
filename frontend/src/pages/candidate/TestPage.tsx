import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Clock, EyeOff, Info, Loader2, Send } from "lucide-react";
import { useEffect, useRef, useState, type ClipboardEvent, type MouseEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { ItemAnswerInput } from "@/components/candidate/ItemAnswerInput";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import { formatTimer } from "@/lib/format";
import { type AnswerDraft, emptyDraft, isDraftEmpty, toPayload } from "@/lib/test-answer";
import {
  type AnswerPayload,
  type CurrentItem,
  queryKeys,
  useAttempt,
  useCurrentItem,
  useSubmitAnswer,
} from "@/lib/testing-queries";
import { useFocusLossCounter } from "@/lib/use-focus-loss";
import { cn } from "@/lib/utils";

// Автоотправка срабатывает на секунду раньше серверного дедлайна, чтобы ответ успел дойти и не стал «поздним».
const AUTO_SUBMIT_LEAD_MS = 1000;
const TICK_MS = 250;
// Последние секунды таймер подсвечивается.
const WARN_SECONDS = 15;

export default function TestPage() {
  const params = useParams();
  const attemptId = Number(params.attemptId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const attempt = useAttempt(attemptId);
  const current = useCurrentItem(attemptId);
  const answer = useSubmitAnswer(attemptId);
  const focus = useFocusLossCounter();
  const [lateNotice, setLateNotice] = useState(false);

  if (!Number.isFinite(attemptId)) return <Navigate to="/candidate/grade" replace />;

  const resultPath = `/candidate/test/${attemptId}/result`;

  /** true — ответ принят; false — ошибка, можно отправить ещё раз. */
  const submit = async (itemId: number, payload: AnswerPayload): Promise<boolean> => {
    try {
      const ack = await answer.mutateAsync({ itemId, response: payload, focusLostCount: focus.count });
      focus.reset();
      setLateNotice(ack.late);
      if (ack.finished) {
        // Профиль и grade-status (ключи под ["candidates", "me"]) изменились: новая категория, история.
        void queryClient.invalidateQueries({ queryKey: queryKeys.me });
        void navigate(resultPath, { replace: true });
      } else {
        await queryClient.invalidateQueries({ queryKey: queryKeys.currentItem(attemptId) });
      }
      return true;
    } catch (err) {
      // Задание уже сменилось (ответ из другой вкладки или по дедлайну) — просто берём актуальное.
      if (apiError(err).code === "not_current_item") {
        answer.reset();
        await queryClient.invalidateQueries({ queryKey: queryKeys.currentItem(attemptId) });
        return true;
      }
      return false;
    }
  };

  if (current.isPending) {
    return (
      <div className="mx-auto max-w-3xl">
        <SkeletonCards count={1} />
      </div>
    );
  }
  if (current.isError) {
    const { status, message } = apiError(current.error);
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <ErrorState
          title={status === 404 ? "Попытка не найдена" : "Не удалось загрузить вопрос"}
          description={message}
          onRetry={status === 404 ? undefined : () => void current.refetch()}
        />
        <Button asChild variant="ghost">
          <Link to="/candidate/grade">К категории и грейду</Link>
        </Button>
      </div>
    );
  }

  const { item, localDeadlineMs } = current.data;
  if (item.finished) return <Navigate to={resultPath} replace />;

  const position = item.position ?? (attempt.data ? attempt.data.answered + 1 : null);
  // §10.3: base — задания без уточняющих, max — с уточняющими у порога грейда («из 20–24»)
  const base = item.total_estimate ?? attempt.data?.total_estimate ?? null;
  const max = item.total_max ?? attempt.data?.total_max ?? base;
  const upper = max !== null && position !== null ? Math.max(max, position) : max;
  const clarifying = position !== null && base !== null && position > base;
  const busy = answer.isPending || current.isFetching;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="sr-only">Прохождение теста</h1>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {attempt.data ? (
          <CategoryBadge specialization={attempt.data.specialization} grade={attempt.data.grade_target} />
        ) : (
          <span />
        )}
        {position !== null && (
          <span className="font-mono text-sm font-medium tabular-nums">
            Вопрос {position}
            {base !== null && upper !== null && (upper > base ? ` из ${base}–${upper}` : ` из ${upper}`)}
          </span>
        )}
      </div>
      {position !== null && upper !== null && (
        <Progress value={(position / upper) * 100} className="mb-6" aria-label="Прогресс теста" />
      )}

      {clarifying && upper !== null && (
        <div role="status" className="mb-4 flex items-start gap-2 rounded-lg bg-primary-tint px-4 py-3 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          Результат близок к порогу грейда, поэтому тест задаёт уточняющие вопросы — не больше {upper - (base ?? 0)}.
          Так решение о грейде будет точнее.
        </div>
      )}

      {lateNotice && (
        <div role="status" className="mb-4 flex items-start gap-2 rounded-lg bg-destructive-tint px-4 py-3 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
          Ответ на прошлый вопрос пришёл после окончания времени и засчитан как неверный.
        </div>
      )}

      <ItemScreen
        // Новое задание — новый экземпляр: черновик ответа, таймер и защита от повторной отправки сбрасываются.
        key={`${item.item_id}:${current.dataUpdatedAt}`}
        item={item}
        localDeadlineMs={localDeadlineMs}
        busy={busy}
        loadingNext={current.isFetching && !answer.isPending}
        error={answer.isError ? apiError(answer.error).message : null}
        focusLost={focus.count}
        onSubmit={submit}
      />
    </div>
  );
}

interface ItemScreenProps {
  item: CurrentItem;
  localDeadlineMs: number | null;
  busy: boolean;
  loadingNext: boolean;
  error: string | null;
  focusLost: number;
  onSubmit: (itemId: number, payload: AnswerPayload) => Promise<boolean>;
}

const blockCopy = (event: ClipboardEvent | MouseEvent) => event.preventDefault();

export function ItemScreen({ item, localDeadlineMs, busy, loadingNext, error, focusLost, onSubmit }: ItemScreenProps) {
  const kind = item.kind ?? "single_choice";
  const [draft, setDraft] = useState<AnswerDraft>(() => emptyDraft(item));
  const [now, setNow] = useState(() => Date.now());
  const submittedRef = useRef(false);
  const autoTriedRef = useRef(false);

  const deadline = localDeadlineMs === null ? null : localDeadlineMs - AUTO_SUBMIT_LEAD_MS;

  useEffect(() => {
    if (deadline === null) return;
    const timer = window.setInterval(() => setNow(Date.now()), TICK_MS);
    return () => window.clearInterval(timer);
  }, [deadline]);

  const remainingSec = deadline === null ? null : Math.max(0, Math.ceil((deadline - now) / 1000));
  const expired = remainingSec === 0;
  const limitSec = item.time_limit_sec ?? null;

  const send = async () => {
    if (submittedRef.current || item.item_id == null) return;
    submittedRef.current = true;
    const ok = await onSubmit(item.item_id, toPayload(kind, draft));
    if (!ok) submittedRef.current = false;
  };

  // Время вышло — отправляем то, что успели выбрать (или пустой ответ). Автоматически — один раз;
  // если запрос упал, кандидат может отправить вручную.
  useEffect(() => {
    if (!expired || autoTriedRef.current) return;
    autoTriedRef.current = true;
    void send();
  });

  const canSubmit = !busy && (expired || !isDraftEmpty(kind, draft));

  return (
    <Card>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (canSubmit) void send();
        }}
        className="flex flex-col gap-5"
      >
        <CardHeader className="gap-3">
          <div className="flex items-center justify-between gap-3">
            {kind === "open_approach" ? <Badge variant="soft">Открытый вопрос</Badge> : <span />}
            {remainingSec !== null && (
              <span
                role="timer"
                aria-label="Осталось времени на вопрос"
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-sm font-bold tabular-nums",
                  remainingSec <= WARN_SECONDS ? "border-destructive text-destructive-strong" : "border-border",
                )}
              >
                <Clock className="size-4 text-primary" aria-hidden />
                {formatTimer(remainingSec)}
              </span>
            )}
          </div>
          {remainingSec !== null && limitSec && (
            <Progress
              value={(remainingSec / limitSec) * 100}
              className="h-1"
              indicatorClassName={cn(remainingSec <= WARN_SECONDS && "bg-destructive", "duration-300")}
              aria-label="Оставшееся время"
            />
          )}
        </CardHeader>

        {/* Копирование и контекстное меню в тексте вопроса отключены (§10.6). */}
        <CardContent className="space-y-4">
          <div className="space-y-4 select-none" onCopy={blockCopy} onCut={blockCopy} onContextMenu={blockCopy}>
            <p className="font-mono text-lg leading-snug font-bold whitespace-pre-line">{item.stem}</p>
            {item.code && (
              <div className="overflow-hidden rounded-lg bg-ink text-ink-foreground">
                {item.code_language && (
                  <div className="border-b border-ink-foreground/15 px-4 py-1.5 font-mono text-xs opacity-70">
                    {item.code_language}
                  </div>
                )}
                <pre
                  tabIndex={0}
                  role="region"
                  aria-label="Код к заданию"
                  className="overflow-x-auto p-4 font-mono text-sm leading-relaxed focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <code>{item.code}</code>
                </pre>
              </div>
            )}
          </div>
          <div onContextMenu={blockCopy}>
            <ItemAnswerInput item={item} kind={kind} draft={draft} onChange={setDraft} disabled={busy || expired} />
          </div>
          <FormAlert message={error} />
        </CardContent>

        <CardFooter className="flex-wrap justify-between gap-3 border-t border-border-subtle pt-5">
          <span className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>Вернуться к предыдущему вопросу нельзя</span>
            {focusLost > 0 && (
              <span className="inline-flex items-center gap-1.5">
                <EyeOff className="size-3.5" aria-hidden /> Уходов со вкладки на этом вопросе: {focusLost} — отмечается,
                но не штрафуется
              </span>
            )}
          </span>
          <Button type="submit" disabled={!canSubmit}>
            {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
            {loadingNext ? "Загружаем следующий…" : expired && busy ? "Время вышло, отправляем…" : "Ответить"}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
