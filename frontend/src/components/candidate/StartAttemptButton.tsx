import { CalendarClock, Loader2 } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { useNavigate } from "react-router";
import { FormAlert } from "@/components/FormAlert";
import { Button } from "@/components/ui/button";
import { apiError } from "@/lib/api-error";
import { formatDate } from "@/lib/format";
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
}: StartAttemptButtonProps) {
  const navigate = useNavigate();
  const start = useStartAttempt();
  const conflict = start.error ? startAttemptConflict(start.error) : null;

  const onClick = () => {
    if (!params || start.isPending) return;
    start.mutate(params, {
      onSuccess: (attempt) => {
        onStarted?.();
        void navigate(`/candidate/test/${attempt.id}`);
      },
      onError: (err) => {
        const found = startAttemptConflict(err);
        if (found?.kind === "in_progress") void navigate(`/candidate/test/${found.attemptId}`);
      },
    });
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
    </div>
  );
}
