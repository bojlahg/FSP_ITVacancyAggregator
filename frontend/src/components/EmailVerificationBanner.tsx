import { Loader2, MailWarning, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { apiError } from "@/lib/api-error";
import { useAuth } from "@/lib/auth";
import { useResendVerification } from "@/lib/auth-queries";

/** Напоминание подтвердить почту. Не блокирует работу: подтверждение пока необязательно. */
export function EmailVerificationBanner() {
  const { user } = useAuth();
  const resend = useResendVerification();
  const [dismissed, setDismissed] = useState(false);

  if (!user || user.email_verified || dismissed) return null;

  return (
    <div
      role="status"
      className="mb-6 flex flex-wrap items-center gap-3 rounded-lg border border-primary/30 bg-primary-tint px-4 py-3 text-sm"
    >
      <MailWarning className="size-5 shrink-0 text-primary" aria-hidden />
      <div className="min-w-[12rem] flex-1">
        <p>
          Подтвердите почту — письмо отправлено на <b className="font-mono [overflow-wrap:anywhere]">{user.email}</b>
        </p>
        {resend.isSuccess && <p className="mt-0.5 text-xs text-muted-foreground">Письмо отправлено ещё раз.</p>}
        {resend.isError && (
          <p className="mt-0.5 text-xs font-medium text-destructive-strong" role="alert">
            {apiError(resend.error).status === 429
              ? "Слишком много попыток, попробуйте позже"
              : apiError(resend.error).message}
          </p>
        )}
      </div>
      <Button
        variant="outline"
        size="sm"
        disabled={resend.isPending || resend.isSuccess}
        onClick={() => resend.mutate()}
      >
        {resend.isPending && <Loader2 className="animate-spin" />}
        Отправить ещё раз
      </Button>
      <Button variant="ghost" size="icon-sm" onClick={() => setDismissed(true)} aria-label="Скрыть" title="Скрыть">
        <X />
      </Button>
    </div>
  );
}
