import { Clock, EyeOff, Loader2, Send } from "lucide-react";
import { useEffect, useRef, useState, type ClipboardEvent, type MouseEvent } from "react";
import { ItemAnswerInput } from "@/components/candidate/ItemAnswerInput";
import { CodeBlock } from "@/components/CodeBlock";
import { FormAlert } from "@/components/FormAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
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
            {item.code && <CodeBlock code={item.code} language={item.code_language} />}
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
