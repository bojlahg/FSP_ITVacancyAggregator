import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router";
import { ItemScreen } from "@/components/candidate/ItemScreen";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import {
  challengeKeys,
  useAnswerChallenge,
  useChallengeAttempt,
  useChallengeQuestion,
} from "@/lib/challenge-queries";
import { toPercent } from "@/lib/format";
import type { AnswerPayload } from "@/lib/testing-queries";
import { useFocusLossCounter } from "@/lib/use-focus-loss";

export default function ChallengeRunPage() {
  const params = useParams();
  const attemptId = Number(params.attemptId);
  const queryClient = useQueryClient();
  const attempt = useChallengeAttempt(attemptId);
  const current = useChallengeQuestion(attemptId);
  const answer = useAnswerChallenge(attemptId);
  const focus = useFocusLossCounter();
  const [lateNotice, setLateNotice] = useState(false);

  // Вопросы кончились, а в кеше попытка ещё in_progress (запрос ушёл раньше, чем сервер её завершил):
  // перезапрашиваем, иначе экран покажет устаревший результат.
  const finished = current.data?.item.finished === true;
  const staleResult = finished && attempt.data !== undefined && attempt.data.status !== "completed";
  const needsRefetch = staleResult && attempt.dataUpdatedAt < current.dataUpdatedAt;
  const { refetch: refetchAttempt, isFetching: attemptFetching } = attempt;
  useEffect(() => {
    if (needsRefetch && !attemptFetching) void refetchAttempt();
  }, [needsRefetch, attemptFetching, refetchAttempt]);

  if (!Number.isFinite(attemptId)) return <Navigate to="/candidate/challenges" replace />;

  const submit = async (itemId: number, payload: AnswerPayload): Promise<boolean> => {
    try {
      const ack = await answer.mutateAsync({ itemId, response: payload, focusLostCount: focus.count });
      focus.reset();
      setLateNotice(ack.late);
      await queryClient.invalidateQueries({ queryKey: challengeKeys.current(attemptId) });
      if (ack.finished) {
        void queryClient.invalidateQueries({ queryKey: challengeKeys.attempt(attemptId) });
        void queryClient.invalidateQueries({ queryKey: challengeKeys.available });
      }
      return true;
    } catch (err) {
      if (apiError(err).code === "not_current_item") {
        answer.reset();
        // Попытка могла завершиться по дедлайну или в другой вкладке: обновляем и результат, и список челленджей
        void queryClient.invalidateQueries({ queryKey: challengeKeys.attempt(attemptId) });
        void queryClient.invalidateQueries({ queryKey: challengeKeys.available });
        await queryClient.invalidateQueries({ queryKey: challengeKeys.current(attemptId) });
        return true;
      }
      return false;
    }
  };

  const title = attempt.data ? `${attempt.data.title} · ${attempt.data.company_name}` : "Челлендж";

  if (current.isPending || attempt.isPending) {
    return (
      <div className="mx-auto max-w-3xl">
        <SkeletonCards count={1} />
      </div>
    );
  }
  if (current.isError || attempt.isError) {
    const error = current.error ?? attempt.error;
    const { status, message } = apiError(error);
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <ErrorState
          title={status === 404 ? "Попытка не найдена" : "Не удалось загрузить вопрос"}
          description={message}
          onRetry={status === 404 ? undefined : () => void current.refetch()}
        />
        <Button asChild variant="ghost">
          <Link to="/candidate/challenges">К челленджам</Link>
        </Button>
      </div>
    );
  }

  const { item, localDeadlineMs } = current.data;
  if (item.finished && staleResult) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        {needsRefetch || attempt.isFetching ? (
          <SkeletonCards count={1} />
        ) : (
          <ErrorState
            title="Результат ещё не готов"
            description="Сервер пока не завершил попытку. Обновите результат через пару секунд."
            onRetry={() => void attempt.refetch()}
          />
        )}
      </div>
    );
  }
  if (item.finished) {
    const result = attempt.data;
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <PageHeader eyebrow="Челлендж компании" title={title} />
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="size-5 text-primary" aria-hidden /> Челлендж пройден
            </CardTitle>
            <CardDescription>
              Компания видит ваш результат и ответы без контактов. Если вы ей подойдёте, она пришлёт приглашение с
              вилкой. На грейд и статусы навыков челлендж не влияет.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {result.score != null ? (
              <p className="font-mono text-2xl font-bold">
                {toPercent(result.score)}%{" "}
                <span className="text-sm font-normal text-muted-foreground">
                  верно: {result.correct} из {result.scored_total}
                </span>
              </p>
            ) : (
              <p className="text-muted-foreground">В челлендже только открытые вопросы — их читает компания.</p>
            )}
            <Button asChild variant="outline">
              <Link to="/candidate/challenges">К челленджам</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const position = item.position ?? 1;
  const total = item.total_max ?? attempt.data.total;
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="sr-only">Прохождение челленджа</h1>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm font-medium">{title}</span>
        <span className="font-mono text-sm font-medium tabular-nums">
          Вопрос {position} из {total}
        </span>
      </div>
      <Progress value={(position / total) * 100} className="mb-6" aria-label="Прогресс челленджа" />
      {lateNotice && (
        <div role="status" className="mb-4 flex items-start gap-2 rounded-lg bg-destructive-tint px-4 py-3 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
          Ответ на прошлый вопрос пришёл после окончания времени и засчитан как неверный.
        </div>
      )}
      <ItemScreen
        key={`${item.item_id}:${current.dataUpdatedAt}`}
        item={item}
        localDeadlineMs={localDeadlineMs}
        busy={answer.isPending || current.isFetching}
        loadingNext={current.isFetching && !answer.isPending}
        error={answer.isError ? apiError(answer.error).message : null}
        focusLost={focus.count}
        onSubmit={submit}
      />
    </div>
  );
}
