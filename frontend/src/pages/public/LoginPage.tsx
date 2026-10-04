import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, LogIn, UserRound } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { z } from "zod";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { authStore, type UserRole } from "@/lib/auth";
import { AuthCard } from "./AuthCard";

const loginSchema = z.object({
  email: z.email("Введите корректный email"),
  password: z.string().min(1, "Введите пароль"),
});

type LoginValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = (values: LoginValues) => {
    // TODO: POST /auth/login → access-токен в authStore, refresh — httpOnly cookie; редирект по роли из GET /me.
    console.info("[login] TODO: POST /auth/login", { email: values.email });
  };

  const demoLogin = (role: UserRole) => {
    // TODO: демо-вход через backend (seed-аккаунты Анна / «Демо Банк»). Пока только переход в кабинет.
    console.info("[login] TODO: demo login", role);
    authStore.set({ role });
    navigate(role === "candidate" ? "/candidate" : "/employer");
  };

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
        <Button type="submit" disabled={isSubmitting} className="mt-2">
          <LogIn /> Войти
        </Button>
      </form>

      <div className="my-6 flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="font-mono text-xs text-muted-foreground uppercase">Демо-вход</span>
        <Separator className="flex-1" />
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <Button type="button" variant="outline" onClick={() => demoLogin("candidate")}>
          <UserRound /> Кандидат
        </Button>
        <Button type="button" variant="outline" onClick={() => demoLogin("employer")}>
          <Building2 /> Работодатель
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
