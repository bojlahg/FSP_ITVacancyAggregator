import { CircleCheck, Loader2, MailCheck, MailX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { FormAlert } from "@/components/FormAlert";
import { Button } from "@/components/ui/button";
import { apiError } from "@/lib/api-error";
import { api } from "@/api/client";
import { authStore, homePathFor, useAuth } from "@/lib/auth";
import { useLogout, useResendVerification, useVerifyEmail } from "@/lib/auth-queries";
import { AuthCard } from "./AuthCard";

function ContinueLink() {
  const { user } = useAuth();
  return (
    <Button asChild>
      {user ? <Link to={homePathFor(user.role)}>Перейти в кабинет</Link> : <Link to="/login">Войти</Link>}
    </Button>
  );
}

function VerifyToken({ token }: { token: string }) {
  const verify = useVerifyEmail();
  const { mutate } = verify;
  // Токен одноразовый: проверяем ровно один раз, в том числе при двойном эффекте StrictMode.
  const sentFor = useRef<string | null>(null);

  useEffect(() => {
    if (sentFor.current === token) return;
    sentFor.current = token;
    mutate(token);
  }, [token, mutate]);

  if (verify.isSuccess) {
    return (
      <AuthCard title="Почта подтверждена">
        <div className="space-y-5">
          <div className="flex size-12 items-center justify-center rounded-full bg-primary-tint text-primary">
            <CircleCheck className="size-6" aria-hidden />
          </div>
          <p className="text-sm leading-relaxed">Спасибо! Адрес почты подтверждён.</p>
          <ContinueLink />
        </div>
      </AuthCard>
    );
  }

  if (verify.isError) {
    const { status, message } = apiError(verify.error);
    return (
      <AuthCard title="Ссылка не сработала">
        <div className="space-y-5">
          <div className="flex size-12 items-center justify-center rounded-full bg-destructive-tint text-destructive">
            <MailX className="size-6" aria-hidden />
          </div>
          <p className="text-sm leading-relaxed">
            {status === 400
              ? "Ссылка устарела или уже использована. Запросите новое письмо в кабинете."
              : message}
          </p>
          <ContinueLink />
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Проверяем ссылку" description="Подтверждаем адрес почты, это займёт пару секунд.">
      <div className="flex items-center gap-3 text-sm text-muted-foreground" aria-busy="true">
        <Loader2 className="size-5 animate-spin text-primary" aria-hidden />
        Проверка токена…
      </div>
    </AuthCard>
  );
}

/** Подтверждение обязательно (EMAIL_VERIFICATION_REQUIRED): проверить статус ещё раз или выйти. */
function RequiredActions() {
  const navigate = useNavigate();
  const logout = useLogout();
  const [checking, setChecking] = useState(false);
  const [notYet, setNotYet] = useState(false);

  const recheck = async () => {
    setChecking(true);
    setNotYet(false);
    const { data } = await api.GET("/api/v1/me").catch(() => ({ data: undefined }));
    setChecking(false);
    if (!data) return;
    authStore.setUser(data);
    if (data.email_verified) await navigate(homePathFor(data.role), { replace: true });
    else setNotYet(true);
  };

  const signOut = async () => {
    await logout.mutateAsync();
    await navigate("/", { replace: true });
    authStore.clear(true);
  };

  return (
    <>
      {notYet && <p className="text-sm text-muted-foreground">Почта пока не подтверждена — откройте ссылку из письма.</p>}
      <div className="flex flex-wrap gap-2">
        <Button disabled={checking} onClick={() => void recheck()}>
          {checking && <Loader2 className="animate-spin" />}Я подтвердил — продолжить
        </Button>
        <Button variant="ghost" disabled={logout.isPending} onClick={() => void signOut()}>
          Выйти
        </Button>
      </div>
    </>
  );
}

function CheckInbox() {
  const location = useLocation();
  const { user } = useAuth();
  const resend = useResendVerification();
  const email = (location.state as { email?: string } | null)?.email ?? user?.email;
  const required = !!user && user.email_verification_required && !user.email_verified;

  return (
    <AuthCard title="Подтвердите почту">
      <div className="space-y-5">
        <div className="flex size-12 items-center justify-center rounded-full bg-primary-tint text-primary">
          <MailCheck className="size-6" aria-hidden />
        </div>
        <p className="text-sm leading-relaxed">
          Мы отправили письмо со ссылкой {email ? <b className="font-mono">на {email}</b> : "на указанный адрес"}.
          Перейдите по ней, чтобы подтвердить адрес. Ссылка действует 24 часа.
        </p>
        {required && (
          <p className="text-sm leading-relaxed">Кабинет откроется после подтверждения почты.</p>
        )}
        <p className="text-sm text-muted-foreground">Не пришло письмо — проверьте «Спам» или отправьте ещё раз.</p>
        {resend.isSuccess && <p className="text-sm text-primary">Письмо отправлено повторно.</p>}
        <FormAlert message={resend.isError ? apiError(resend.error).message : null} />
        <div className="flex flex-wrap gap-2">
          {user ? (
            <Button variant="outline" disabled={resend.isPending} onClick={() => resend.mutate()}>
              {resend.isPending && <Loader2 className="animate-spin" />}
              Отправить ещё раз
            </Button>
          ) : null}
          {!required && <ContinueLink />}
        </div>
        {required && <RequiredActions />}
      </div>
    </AuthCard>
  );
}

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  return token ? <VerifyToken key={token} token={token} /> : <CheckInbox />;
}
