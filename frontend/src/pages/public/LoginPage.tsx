import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, Loader2, LogIn, UserRound } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { apiError } from "@/lib/api-error";
import { postLoginPath, type TokenResponse, type UserRole } from "@/lib/auth";
import { useDemoLogin, useLogin } from "@/lib/auth-queries";
import { AuthCard } from "./AuthCard";

const loginSchema = z.object({
  email: z.email("Введите корректный email"),
  password: z.string().min(1, "Введите пароль"),
});

type LoginValues = z.infer<typeof loginSchema>;

function loginErrorMessage(err: unknown): string {
  const { status, message } = apiError(err);
  if (status === 401) return "Неверный email или пароль";
  if (status === 429) return "Слишком много попыток, попробуйте позже";
  return message;
}

function demoErrorMessage(err: unknown): string {
  const { status, message } = apiError(err);
  if (status === 404) return "Демо-вход на этом сервере выключен";
  return message;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next");
  const login = useLogin();
  const demoLogin = useDemoLogin();

  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const goToCabinet = ({ user }: TokenResponse) => {
    void navigate(postLoginPath(user.role, next), { replace: true });
  };

  const onSubmit = async (values: LoginValues) => {
    demoLogin.reset();
    try {
      goToCabinet(await login.mutateAsync(values));
    } catch (err) {
      setError("root.server", { message: loginErrorMessage(err) });
    }
  };

  const onDemo = (persona: UserRole) => {
    login.reset();
    clearErrors("root");
    demoLogin.mutate(persona, { onSuccess: goToCabinet });
  };

  const busy = isSubmitting || demoLogin.isPending;
  const formError = errors.root?.server?.message ?? (demoLogin.error ? demoErrorMessage(demoLogin.error) : null);

  return (
    <AuthCard title="Вход" description="Войдите, чтобы продолжить работу в кабинете.">
      <form className="grid gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormField id="email" label="Email" error={errors.email?.message}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="name@example.ru"
            aria-invalid={!!errors.email}
            {...register("email")}
          />
        </FormField>
        <FormField id="password" label="Пароль" error={errors.password?.message}>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={!!errors.password}
            {...register("password")}
          />
        </FormField>
        <FormAlert message={formError} />
        <Button type="submit" disabled={busy} className="mt-2">
          {isSubmitting ? <Loader2 className="animate-spin" /> : <LogIn />} Войти
        </Button>
      </form>

      <div className="my-6 flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="font-mono text-xs text-muted-foreground uppercase">Демо-вход</span>
        <Separator className="flex-1" />
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <Button type="button" variant="outline" disabled={busy} onClick={() => onDemo("candidate")}>
          {demoLogin.isPending && demoLogin.variables === "candidate" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <UserRound />
          )}
          Кандидат
        </Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => onDemo("employer")}>
          {demoLogin.isPending && demoLogin.variables === "employer" ? (
            <Loader2 className="animate-spin" />
          ) : (
            <Building2 />
          )}
          Работодатель
        </Button>
      </div>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Нет аккаунта?{" "}
        <Link to="/register" className="font-medium text-primary underline-offset-4 hover:underline">
          Зарегистрироваться
        </Link>
      </p>
    </AuthCard>
  );
}
