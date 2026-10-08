import { Clock, EyeOff, Info, Loader2, Send } from "lucide-react";
import { useEffect, useId, useRef, useState, type ClipboardEvent, type MouseEvent } from "react";
import { ItemAnswerInput } from "@/components/candidate/ItemAnswerInput";
import { CodeBlock } from "@/components/CodeBlock";
import { FormAlert } from "@/components/FormAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { formatTimer } from "@/lib/format";
import { type AnswerDraft, emptyDraft, isDraftEmpty, toPayload } from "@/lib/test-answer";
import type { AnswerPayload, CurrentItem } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

// Автоотправка срабатывает на секунду раньше серверного дедлайна, чтобы ответ успел дойти и не стал «поздним».
const AUTO_SUBMIT_LEAD_MS = 1000;
const TICK_MS = 250;
// Последние секунды таймер подсвечивается.
const WARN_SECONDS = 15;

export interface ItemScreenProps {
  item: CurrentItem;
  localDeadlineMs: number | null;
  busy: boolean;
  loadingNext: boolean;
  error: string | null;
  focusLost: number;
  /** timedOut — время вышло, а ответ так и не выбран: задание уходит пустым (пропущено). */
  onSubmit: (itemId: number, payload: AnswerPayload, timedOut: boolean) => Promise<boolean>;
}

const blockCopy = (event: ClipboardEvent | MouseEvent) => event.preventDefault();

/** Экран одного задания с таймером и автоотправкой: общий для теста категории и челленджей компаний. */
export function ItemScreen({ item, localDeadlineMs, busy, loadingNext, error, focusLost, onSubmit }: ItemScreenProps) {
  const kind = item.kind ?? "single_choice";
  const questionId = useId();
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
    const ok = await onSubmit(item.item_id, toPayload(kind, draft), expired && isDraftEmpty(kind, draft));
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
    <Card className="gap-0 py-0">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (canSubmit) void send();
        }}
        aria-labelledby={questionId}
      >
        <div className="flex flex-col gap-4 p-4 sm:p-6">
          {/* Копирование и контекстное меню в тексте вопроса отключены (§10.6). */}
          <div className="space-y-4 select-none" onCopy={blockCopy} onCut={blockCopy} onContextMenu={blockCopy}>
            <div className="flex items-start justify-between gap-6">
              <div className="min-w-0 flex-1 space-y-2">
                {kind === "open_approach" && <Badge variant="soft">Открытый вопрос</Badge>}
                <h2
                  id={questionId}
                  className="font-mono text-lg leading-[1.625rem] font-semibold tracking-tight whitespace-pre-line sm:pt-1 sm:text-xl sm:leading-7"
                >
                  {item.stem}
                </h2>
              </div>
              {/* На телефоне таймер живёт в нижней панели рядом с «Ответить» — его видно при любой прокрутке */}
              {remainingSec !== null && (
                <ItemTimer remainingSec={remainingSec} limitSec={limitSec} className="hidden sm:flex" />
              )}
            </div>
            {item.code && <CodeBlock code={item.code} language={item.code_language} />}
          </div>
          <div onContextMenu={blockCopy}>
            <ItemAnswerInput item={item} kind={kind} draft={draft} onChange={setDraft} disabled={busy || expired} />
          </div>
          <FormAlert message={error} />
        </div>

        {/* На телефоне панель ответа прилипает к низу экрана: кнопка всегда под пальцем */}
        <div className="sticky bottom-0 z-10 flex flex-col gap-2 rounded-b-xl border-t border-border-subtle bg-card px-4 py-3 sm:static sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-x-6 sm:gap-y-3 sm:px-6 sm:py-4">
          <span className="flex flex-col gap-1 text-xs text-muted-foreground max-sm:items-center max-sm:text-center sm:text-sm">
            <span className="inline-flex items-center gap-2">
              <Info className="hidden size-4 shrink-0 sm:block" aria-hidden />
              Вернуться к предыдущему вопросу нельзя
            </span>
            {focusLost > 0 && (
              <span className="inline-flex items-center gap-1.5 text-xs">
                <EyeOff className="size-3.5 shrink-0" aria-hidden /> Уходов со вкладки на этом вопросе: {focusLost} —
                отмечается, но не штрафуется
              </span>
            )}
          </span>
          <div className="flex items-center gap-2">
            {remainingSec !== null && (
              <ItemTimer remainingSec={remainingSec} limitSec={limitSec} className="sm:hidden" />
            )}
            <Button type="submit" size="lg" disabled={!canSubmit} className="max-sm:flex-1">
              {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
              {loadingNext ? "Загружаем следующий…" : expired && busy ? "Время вышло, отправляем…" : "Ответить"}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}

function ItemTimer({
  remainingSec,
  limitSec,
  className,
}: {
  remainingSec: number;
  limitSec: number | null;
  className?: string;
}) {
  const warn = remainingSec <= WARN_SECONDS;
  return (
    <div className={cn("shrink-0 flex-col gap-1.5", className)}>
      <span
        role="timer"
        aria-label="Осталось времени на вопрос"
        className={cn(
          "inline-flex h-10 items-center gap-2 rounded-full border px-3.5 font-mono text-base font-semibold tabular-nums sm:h-8 sm:px-3 sm:text-sm",
          warn ? "border-destructive text-destructive-strong" : "border-border",
        )}
      >
        <Clock className={cn("size-4", warn ? "text-destructive-strong" : "text-primary")} aria-hidden />
        {formatTimer(remainingSec)}
      </span>
      {limitSec ? (
        <Progress
          value={(remainingSec / limitSec) * 100}
          className="hidden h-1 sm:block"
          indicatorClassName={cn(warn && "bg-destructive", "duration-300")}
          aria-label="Оставшееся время"
        />
      ) : null}
    </div>
  );
}
