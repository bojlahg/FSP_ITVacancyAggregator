import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, Loader2, UserRound } from "lucide-react";
import { useForm, useWatch } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import type { UserRole } from "@/lib/auth";
import { useRegister } from "@/lib/auth-queries";
import { cn } from "@/lib/utils";
import { AuthCard } from "./AuthCard";

// docs/implementation.md §6.1: согласие на ПДн обязательно всем; на публикацию профиля — кандидату.
const registerSchema = z
  .object({
    email: z.email("Введите корректный email"),
    password: z.string().min(8, "Минимум 8 символов").max(128, "Не длиннее 128 символов"),
    role: z.enum(["candidate", "employer"]),
    consentPersonalData: z.boolean().refine((value) => value, "Без этого согласия регистрация невозможна"),
    consentPublishProfile: z.boolean(),
  })
  .refine((values) => values.role !== "candidate" || values.consentPublishProfile, {
    path: ["consentPublishProfile"],
    message: "Нужно, чтобы работодатели могли найти вас в поиске",
  });

type RegisterValues = z.infer<typeof registerSchema>;

// Поля RegisterRequest → поля формы, для раскладки ошибок 422 по последнему элементу loc.
const apiFieldMap = {
  email: "email",
  password: "password",
  role: "role",
  consent_pd_processing: "consentPersonalData",
  consent_profile_publication: "consentPublishProfile",
} as const;

// Куда вести после регистрации: кандидата — в онбординг, работодателя — заполнять компанию.
const afterRegisterPath: Record<UserRole, string> = {
  candidate: "/candidate/onboarding",
  employer: "/employer/company",
};

const roles: { value: UserRole; label: string; icon: typeof UserRound }[] = [
  { value: "candidate", label: "Я кандидат", icon: UserRound },
  { value: "employer", label: "Я работодатель", icon: Building2 },
];

export default function RegisterPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const registerUser = useRegister();
  const initialRole: UserRole = searchParams.get("role") === "employer" ? "employer" : "candidate";

  const {
    register,
    handleSubmit,
    control,
    setValue,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: "",
      password: "",
      role: initialRole,
      consentPersonalData: false,
      consentPublishProfile: false,
    },
  });

  const role = useWatch({ control, name: "role" });

  const onSubmit = async (values: RegisterValues) => {
    try {
      const { user } = await registerUser.mutateAsync({
        email: values.email,
        password: values.password,
        role: values.role,
        consent_pd_processing: values.consentPersonalData,
        consent_profile_publication: values.role === "candidate" && values.consentPublishProfile,
      });
      const target = user.role === "candidate" || user.role === "employer" ? afterRegisterPath[user.role] : "/";
      void navigate(target, { replace: true });
    } catch (err) {
      const { status, message } = apiError(err);
      if (status === 409) {
        setError("email", { type: "server", message: "Этот email уже зарегистрирован" });
      } else if (!(status === 422 && applyValidationErrors(err, setError, apiFieldMap))) {
        setError("root.server", {
          message: status === 429 ? "Слишком много попыток, попробуйте позже" : message,
        });
      }
    }
  };

  return (
    <AuthCard title="Регистрация" description="Создайте аккаунт кандидата или работодателя.">
      <form className="grid gap-5" onSubmit={handleSubmit(onSubmit)} noValidate>
        <div role="radiogroup" aria-label="Роль" className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">
          {roles.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={role === value}
              onClick={() => setValue("role", value, { shouldValidate: false })}
              className={cn(
                "flex items-center justify-center gap-2 rounded-md px-3 py-2 font-mono text-sm font-medium whitespace-nowrap transition-colors max-sm:gap-1.5 max-sm:px-2 max-sm:text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                role === value ? "bg-background text-primary shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </button>
          ))}
        </div>

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
        <FormField
          id="password"
          label="Пароль"
          error={errors.password?.message}
          hint="Не короче 8 символов"
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.password}
            {...register("password")}
          />
        </FormField>

        <fieldset className="grid gap-3">
          <legend className="sr-only">Согласия</legend>
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
          {role === "candidate" && (
            <div className="grid gap-1">
              <label className="flex items-start gap-3 text-sm leading-snug">
                <Checkbox
                  className="mt-0.5"
                  aria-invalid={!!errors.consentPublishProfile}
                  {...register("consentPublishProfile")}
                />
                <span>
                  Согласен на публикацию профиля работодателям{" "}
                  <span className="text-muted-foreground">(можно отозвать в настройках)</span>
                </span>
              </label>
              {errors.consentPublishProfile && (
                <p className="pl-7 text-xs font-medium text-destructive-strong" role="alert">
                  {errors.consentPublishProfile.message}
                </p>
              )}
            </div>
          )}
        </fieldset>

        <FormAlert message={errors.root?.server?.message ?? (errors.role ? errors.role.message : null)} />

        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="animate-spin" />}
          Зарегистрироваться
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Уже есть аккаунт?{" "}
        <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
          Войти
        </Link>
      </p>
    </AuthCard>
  );
}
