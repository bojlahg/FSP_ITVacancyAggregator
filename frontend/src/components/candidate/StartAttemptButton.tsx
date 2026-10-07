import { CalendarClock, Clock, Loader2 } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { TestRulesList } from "@/components/candidate/TestRules";
import { FormAlert } from "@/components/FormAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiError } from "@/lib/api-error";
import { formatDate } from "@/lib/format";
import { gradeLabel, specializationLabel } from "@/lib/labels";
import { TEST_DURATION_LABEL, testRules, useAttemptRuleText, useTestLengthText } from "@/lib/test-rules";
import { type StartAttemptParams, startAttemptConflict, useStartAttempt } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

interface StartAttemptButtonProps {
  params: StartAttemptParams | null;
  children: ReactNode;
  variant?: ComponentProps<typeof Button>["variant"];
  size?: ComponentProps<typeof Button>["size"];
  disabled?: boolean;
  className?: string;
  /** Попытка создана — перед переходом на экран теста. */
  onStarted?: () => void;
  /**
   * Перед стартом показать правила и подтверждение (§6.2): полный тест нельзя поставить на паузу,
   * и он учитывается в правилах грейда. По умолчанию — для всех, кроме экспресс-теста.
   */
  confirm?: boolean;
}

/**
 * Старт попытки → экран теста. 409 «attempt_in_progress» ведёт в незаконченную попытку,
 * «grade_cooldown» показывает, когда тест станет доступен.
 */
export function StartAttemptButton({
  params,
  children,
  variant,
  size,
  disabled,
  className,
  onStarted,
  confirm,
}: StartAttemptButtonProps) {
  const navigate = useNavigate();
  const start = useStartAttempt();
  const conflict = start.error ? startAttemptConflict(start.error) : null;
  const [confirming, setConfirming] = useState(false);
  const needsConfirm = confirm ?? params?.purpose !== "express";

  const begin = () => {
    if (!params || start.isPending) return;
    start.mutate(params, {
      onSuccess: (attempt) => {
        onStarted?.();
        void navigate(`/candidate/test/${attempt.id}`);
      },
      onError: (err) => {
        // Ошибку показываем под кнопкой — диалог закрываем
        setConfirming(false);
        const found = startAttemptConflict(err);
        if (found?.kind === "in_progress") void navigate(`/candidate/test/${found.attemptId}`);
      },
    });
  };

  const onClick = () => {
    if (!params || start.isPending) return;
    if (needsConfirm) setConfirming(true);
    else begin();
  };

  let errorText: ReactNode = null;
  if (conflict?.kind === "cooldown") {
    errorText = (
      <span className="flex items-start gap-2 text-sm text-muted-foreground">
        <CalendarClock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <span>
          {conflict.message}
          {conflict.availableAt && (
            <>
              {" "}
              Тест станет доступен <b className="font-mono text-foreground">{formatDate(conflict.availableAt)}</b>.
            </>
          )}
        </span>
      </span>
    );
  }

  return (
    <div className={cn("grid gap-2", className)}>
      <Button variant={variant} size={size} onClick={onClick} disabled={disabled || !params || start.isPending}>
        {start.isPending && <Loader2 className="animate-spin" aria-hidden />}
        {children}
      </Button>
      {errorText && <div role="status">{errorText}</div>}
      {start.isError && !conflict && <FormAlert message={apiError(start.error).message} />}
      {needsConfirm && params && (
        <StartAttemptDialog
          open={confirming}
          onOpenChange={(open) => !start.isPending && setConfirming(open)}
          params={params}
          pending={start.isPending}
          onConfirm={begin}
        />
      )}
    </div>
  );
}

function StartAttemptDialog({
  open,
  onOpenChange,
  params,
  pending,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  params: StartAttemptParams;
  pending: boolean;
  onConfirm: () => void;
}) {
  const lengthText = useTestLengthText(params.grade_target);
  const attemptRule = useAttemptRuleText(params.purpose);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            Тест на {specializationLabel(params.specialization)} · {gradeLabel(params.grade_target)}
          </DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-2">
            <span>Приостановить тест нельзя — начните, когда будет время без перерывов.</span>
            <Badge variant="muted">
              <Clock /> {TEST_DURATION_LABEL}
            </Badge>
          </DialogDescription>
        </DialogHeader>
        <TestRulesList rules={[...testRules(lengthText), attemptRule]} compact />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={pending}>
            Отмена
          </Button>
          <Button onClick={onConfirm} disabled={pending}>
            {pending && <Loader2 className="animate-spin" aria-hidden />}
            Начать тест
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
