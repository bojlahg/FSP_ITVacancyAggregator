import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import { useRegisterExpert } from "@/lib/expert-queries";
import { GuestOnly } from "@/app/guards";
import { AuthCard } from "./AuthCard";

const joinSchema = z.object({
  code: z.string().trim().min(1, "Введите код-приглашение"),
  email: z.email("Введите корректный email"),
  password: z.string().min(8, "Минимум 8 символов").max(128, "Не длиннее 128 символов"),
  consentPersonalData: z.boolean().refine((value) => value, "Без этого согласия регистрация невозможна"),
});

type JoinValues = z.infer<typeof joinSchema>;

const apiFieldMap = {
  code: "code",
  email: "email",
  password: "password",
  consent_pd_processing: "consentPersonalData",
} as const;

/** Регистрация эксперта по коду-приглашению (docs/implementation.md §12.2). */
export default function ExpertJoinPage() {
  return (
    <GuestOnly>
      <ExpertJoinForm />
    </GuestOnly>
  );
}

function ExpertJoinForm() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const registerExpert = useRegisterExpert();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<JoinValues>({
    resolver: zodResolver(joinSchema),
    defaultValues: { code: searchParams.get("code") ?? "", email: "", password: "", consentPersonalData: false },
  });

  const onSubmit = async (values: JoinValues) => {
    try {
      await registerExpert.mutateAsync({
        code: values.code,
        email: values.email,
        password: values.password,
        consent_pd_processing: values.consentPersonalData,
      });
      void navigate("/expert", { replace: true });
    } catch (err) {
      const { status, message } = apiError(err);
      if (status === 409) {
        setError("email", { type: "server", message: "Этот email уже зарегистрирован" });
      } else if (status === 403) {
        setError("code", { type: "server", message: "Код-приглашение не подходит" });
      } else if (status === 404) {
        setError("root.server", { message: "Экспертная разметка сейчас закрыта" });
      } else if (!(status === 422 && applyValidationErrors(err, setError, apiFieldMap))) {
        setError("root.server", {
          message: status === 429 ? "Слишком много попыток, попробуйте позже" : message,
        });
      }
    }
  };

  return (
    <AuthCard
      title="Эксперт разметки"
      description="Оцените, подходит ли кандидат под потребность работодателя. Ваши оценки — независимая проверка качества подбора ITScout."
    >
      <form className="grid gap-5" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormField id="code" label="Код-приглашение" error={errors.code?.message}>
          <Input id="code" autoComplete="off" aria-invalid={!!errors.code} {...register("code")} />
        </FormField>
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
        <FormField id="password" label="Пароль" error={errors.password?.message} hint="Не короче 8 символов">
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.password}
            {...register("password")}
          />
        </FormField>
        <div className="grid gap-1">
          <label className="flex items-start gap-3 text-sm leading-snug">
            <Checkbox className="mt-0.5" aria-invalid={!!errors.consentPersonalData} {...register("consentPersonalData")} />
            <span>
              Согласен на обработку персональных данных <span className="text-muted-foreground">(152-ФЗ)</span>
            </span>
          </label>
          {errors.consentPersonalData && (
            <p className="pl-7 text-xs font-medium text-destructive-strong" role="alert">
              {errors.consentPersonalData.message}
            </p>
          )}
        </div>

        <FormAlert message={errors.root?.server?.message ?? null} />

        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="animate-spin" />}
          Начать разметку
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Уже размечали?{" "}
        <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
          Войти
        </Link>
      </p>
    </AuthCard>
  );
}
