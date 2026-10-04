import { Loader2, MailCheck } from "lucide-react";
import { Link, useLocation, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { AuthCard } from "./AuthCard";

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const token = searchParams.get("token");
  const email = (location.state as { email?: string } | null)?.email;

  if (token) {
    // TODO: POST /auth/verify-email {token} через useMutation; при успехе — в онбординг, при ошибке — «ссылка устарела».
    return (
      <AuthCard title="Проверяем ссылку" description="Подтверждаем адрес почты, это займёт пару секунд.">
        <div className="flex items-center gap-3 text-sm text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin text-primary" aria-hidden />
          Проверка токена…
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Подтвердите почту">
      <div className="space-y-5">
        <div className="flex size-12 items-center justify-center rounded-full bg-primary-tint text-primary">
          <MailCheck className="size-6" aria-hidden />
        </div>
        <p className="text-sm leading-relaxed">
          Мы отправили письмо со ссылкой {email ? <b className="font-mono">на {email}</b> : "на указанный адрес"}.
          Перейдите по ней, чтобы активировать аккаунт. Ссылка действует 24 часа.
        </p>
        <p className="text-sm text-muted-foreground">
          Пока почта не подтверждена, кабинет недоступен. Не пришло письмо — проверьте «Спам» или отправьте ещё раз.
        </p>
        <div className="flex flex-wrap gap-2">
          {/* TODO: POST /auth/resend-verification */}
          <Button variant="outline" onClick={() => console.info("[verify] TODO: resend verification")}>
            Отправить ещё раз
          </Button>
          <Button asChild variant="ghost">
            <Link to="/login">Ко входу</Link>
          </Button>
        </div>
      </div>
    </AuthCard>
  );
}
