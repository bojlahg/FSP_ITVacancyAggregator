import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Info } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { Badge } from "@/components/ui/badge";
import { AbandonExpressButton } from "@/components/candidate/AbandonExpressButton";
import { ItemScreen } from "@/components/candidate/ItemScreen";
import { ErrorState } from "@/components/ErrorState";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import { extraItemsNote } from "@/lib/format";
import { type AnswerPayload, queryKeys, useAttempt, useCurrentItem, useSubmitAnswer } from "@/lib/testing-queries";
import { useFocusLossCounter } from "@/lib/use-focus-loss";

export default function TestPage() {
  const params = useParams();
  const attemptId = Number(params.attemptId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const attempt = useAttempt(attemptId);
  const current = useCurrentItem(attemptId);
  const answer = useSubmitAnswer(attemptId);
  const focus = useFocusLossCounter();
  // late — ответ пришёл после дедлайна; timeout — время вышло без ответа, задание пропущено
  const [notice, setNotice] = useState<"late" | "timeout" | null>(null);

  if (!Number.isFinite(attemptId)) return <Navigate to="/candidate/grade" replace />;

  const resultPath = `/candidate/test/${attemptId}/result`;

  /** true — ответ принят; false — ошибка, можно отправить ещё раз. */
  const submit = async (itemId: number, payload: AnswerPayload, timedOut: boolean): Promise<boolean> => {
    try {
      const ack = await answer.mutateAsync({ itemId, response: payload, focusLostCount: focus.count });
      focus.reset();
      setNotice(timedOut ? "timeout" : ack.late ? "late" : null);
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
        if (timedOut) setNotice("timeout");
        await queryClient.invalidateQueries({ queryKey: queryKeys.currentItem(attemptId) });
        return true;
      }
      return false;
    }
  };

  // Прерванный экспресс-тест результата не имеет — возвращаемся к категории и грейду
  if (attempt.data?.status === "abandoned") return <Navigate to="/candidate/grade" replace />;

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
  // Сервер сам пропускает задание, время которого вышло, пока вкладка была закрыта (previous_timed_out)
  const shownNotice = item.previous_timed_out ? "timeout" : notice;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="sr-only">Прохождение теста</h1>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {attempt.data ? (
          <span className="flex flex-wrap items-center gap-2">
            <CategoryBadge specialization={attempt.data.specialization} grade={attempt.data.grade_target} />
            {attempt.data.purpose === "express" && <Badge variant="soft">экспресс-тест</Badge>}
          </span>
        ) : (
          <span />
        )}
        {position !== null && (
          <span className="font-mono text-sm font-medium tabular-nums">
            Вопрос {position}
            {base !== null && upper !== null && ` из ${clarifying ? upper : base}`}
          </span>
        )}
        {position !== null && !clarifying && base !== null && upper !== null && upper > base && (
          <span className="w-full text-right text-sm text-muted-foreground">{extraItemsNote(upper - base)}</span>
        )}
      </div>
      {position !== null && upper !== null && (
        <Progress
          value={(position / (clarifying || base === null ? upper : base)) * 100}
          className="mb-6"
          aria-label="Прогресс теста"
        />
      )}

      {clarifying && upper !== null && (
        <div role="status" className="mb-4 flex items-start gap-2 rounded-lg bg-primary-tint px-4 py-3 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          Результат близок к порогу грейда, поэтому тест задаёт уточняющие вопросы — не больше {upper - (base ?? 0)}.
          Так решение о грейде будет точнее.
        </div>
      )}

      {shownNotice && (
        <div role="status" className="mb-4 flex items-start gap-2 rounded-lg bg-destructive-tint px-4 py-3 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
          {shownNotice === "timeout"
            ? "Время на прошлый вопрос вышло — он пропущен и засчитан как неверный."
            : "Ответ на прошлый вопрос пришёл после окончания времени и засчитан как неверный."}
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

      {attempt.data?.purpose === "express" && (
        <div className="mt-6 flex flex-wrap items-start justify-between gap-3 text-sm text-muted-foreground">
          <span className="pt-1.5">Экспресс-тест можно прервать: категорию и попытки он не затрагивает.</span>
          <AbandonExpressButton attemptId={attemptId} />
        </div>
      )}
    </div>
  );
}
