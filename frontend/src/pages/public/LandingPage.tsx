import { ArrowRight, Building2, Eye, Loader2, RefreshCw, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { FormAlert } from "@/components/FormAlert";
import { LandingIllustration } from "@/components/landing/LandingIllustration";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import { postLoginPath, type TokenResponse, type UserRole, useAuth } from "@/lib/auth";
import { useDemoLogin } from "@/lib/auth-queries";
import { useExplainerOverview } from "@/lib/explainer-queries";
import { extraItemsNote, testItemsRange } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Механика в три шага вместо абзаца-описания: тест → приглашение с вилкой → контакты после принятия. */
const mechanics = [
  { label: "01 · Тест", text: "Категория «специализация × грейд» — только по тесту", key: true },
  { label: "02 · Приглашение", text: "Работодатель пишет первым и сразу указывает вилку от–до", key: true },
  { label: "03 · Контакты", text: "Открываются, только когда кандидат принял приглашение", key: false },
];

interface Step {
  title: string;
  text: string;
  /** Ключевой шаг механики — номер залит primary. */
  key?: boolean;
}

const candidateSteps: Step[] = [
  { title: "Опрос", text: "8–10 вопросов о том, чем вы занимаетесь. Система предложит специализацию." },
  { title: "Тест на грейд", text: "Адаптивный тест около 25 минут, по одному вопросу на экран." },
  { title: "Категория", text: "Вы получаете категорию «специализация × грейд», которую видят работодатели." },
  {
    title: "Приглашения",
    text: "Работодатели пишут первыми — сразу с вилкой зарплаты и объяснением «почему вы».",
    key: true,
  },
];

const employerSteps: Step[] = [
  { title: "Потребность", text: "Опишите задачу текстом — мы разберём её в стек, грейд и вилку." },
  { title: "Подборка", text: "Рекомендованные категории и кандидаты с понятным объяснением совпадения." },
  { title: "Приглашение", text: "Пишете конкретному человеку и сразу указываете вилку от–до.", key: true },
  { title: "Контакты", text: "Контакты кандидата открываются, как только он принял приглашение." },
];

// Работодатель — главное действие демо: механика «первым пишет работодатель» видна с его стороны.
const demoPersonas: { role: UserRole; label: string; icon: typeof UserRound; variant: "default" | "outline" }[] = [
  { role: "employer", label: "Посмотреть как работодатель", icon: Building2, variant: "default" },
  { role: "candidate", label: "Посмотреть как кандидат", icon: UserRound, variant: "outline" },
];

function Steps({ steps }: { steps: Step[] }) {
  return (
    <ol className="grid gap-4 md:gap-[18px]">
      {steps.map((step, index) => (
        <li key={step.title} className="flex gap-3.5 md:gap-4">
          <span
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-full border border-primary font-mono text-[13px] font-medium",
              step.key ? "bg-primary text-primary-foreground" : "text-primary",
            )}
          >
            {index + 1}
          </span>
          <div className="min-w-0 space-y-0.5">
            <h3 className="font-mono text-base font-semibold tracking-tight">{step.title}</h3>
            <p className="text-sm text-muted-foreground">{step.text}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function demoErrorMessage(err: unknown): string {
  const { status, message } = apiError(err);
  if (status === 404) return "Демо-вход на этом сервере выключен — зарегистрируйтесь или войдите";
  return message;
}

/**
 * Главное действие лендинга: демо-вход теми же готовыми аккаунтами, что и на /login — сразу в кабинет.
 * Регистрация — строкой ссылок под кнопками демо.
 */
function DemoEntry() {
  const navigate = useNavigate();
  const demoLogin = useDemoLogin();
  const { user } = useAuth();
  // Уже вошедшему демо-вход заменил бы сессию — ему в шапке «В кабинет»
  if (user) return null;

  const onDemo = (persona: UserRole) =>
    demoLogin.mutate(persona, {
      onSuccess: ({ user: signedIn }: TokenResponse) => void navigate(postLoginPath(signedIn.role, null)),
    });

  return (
    <div className="flex max-w-[640px] flex-col gap-3 rounded-xl border border-primary bg-card p-4 sm:gap-4 sm:p-6">
      <p className="flex flex-col gap-0.5 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
        <span className="flex items-center gap-2 font-mono text-xs font-medium tracking-[0.1em] text-primary uppercase">
          <Eye className="size-4 shrink-0" aria-hidden />
          Демо без регистрации
        </span>
        <span className="pl-6 text-sm text-muted-foreground sm:pl-0">
          <span className="hidden sm:inline">— </span>готовые аккаунты с данными
        </span>
      </p>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        {demoPersonas.map(({ role, label, icon: Icon, variant }) => (
          <Button
            key={role}
            type="button"
            size="lg"
            variant={variant}
            className="h-[52px] w-full sm:w-auto sm:flex-[1_1_220px]"
            disabled={demoLogin.isPending}
            onClick={() => onDemo(role)}
          >
            {demoLogin.isPending && demoLogin.variables === role ? <Loader2 className="animate-spin" /> : <Icon />}
            {label}
          </Button>
        ))}
      </div>
      <FormAlert message={demoLogin.error ? demoErrorMessage(demoLogin.error) : null} />
      <div className="flex flex-col border-t border-border-subtle pt-3 text-sm text-muted-foreground sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4 sm:gap-y-1 sm:pt-3.5">
        <span>Нет аккаунта?</span>
        <div className="flex flex-wrap gap-x-5 sm:contents">
          <Link
            to="/register?role=candidate"
            className="inline-flex min-h-11 items-center font-medium text-primary underline-offset-4 hover:underline sm:min-h-0"
          >
            Регистрация кандидата
          </Link>
          <Link
            to="/register?role=employer"
            className="inline-flex min-h-11 items-center font-medium text-primary underline-offset-4 hover:underline sm:min-h-0"
          >
            Регистрация работодателя
          </Link>
          <Link
            to="/login"
            className="hidden font-medium text-foreground underline-offset-4 hover:underline sm:inline-flex"
          >
            Войти
          </Link>
        </div>
      </div>
    </div>
  );
}

/** Живые цифры банка заданий — тот же /explainer/overview, что и на «Как работает тест». */
function BankStats() {
  const overview = useExplainerOverview();

  if (overview.isPending) {
    return (
      <div
        className="grid grid-cols-2 gap-4 border-t border-foreground pt-5 lg:grid-cols-4"
        role="status"
        aria-busy="true"
        aria-label="Загрузка цифр"
      >
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-24" />
        ))}
      </div>
    );
  }
  if (overview.isError) {
    return (
      <div className="flex flex-wrap items-center gap-3 border-t border-foreground pt-5 text-sm text-muted-foreground">
        Не удалось загрузить цифры банка заданий.
        <Button variant="link" size="sm" className="h-auto p-0" onClick={() => void overview.refetch()}>
          <RefreshCw /> Повторить
        </Button>
      </div>
    );
  }

  const { specializations, grades, active_templates: activeTemplates, extra_items_max: extraMax } = overview.data;
  if (specializations.length === 0) {
    return (
      <p className="border-t border-foreground pt-5 text-sm text-muted-foreground">Банк заданий ещё не загружен.</p>
    );
  }
  const facts = [
    { label: "Шаблонов заданий", value: activeTemplates, note: "в рабочем банке; у каждого свои числа и код на попытку" },
    { label: "Специализаций", value: specializations.length, note: specializations.map((spec) => spec.name).join(", ") },
    {
      label: "Заданий в тесте",
      value: testItemsRange(grades.map((grade) => grade.test_items)),
      note: extraItemsNote(extraMax),
    },
    { label: "Грейдов", value: grades.length, note: grades.map((grade) => grade.name).join(" → ") },
  ];

  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-6 border-t border-foreground pt-5 lg:grid-cols-4 lg:gap-8 lg:pt-6">
      {facts.map((fact) => (
        <div key={fact.label} className="flex min-w-0 flex-col gap-1 lg:gap-1.5">
          <dt className="font-mono text-xs font-medium tracking-[0.1em] text-muted-foreground uppercase">{fact.label}</dt>
          <dd className="font-mono text-3xl font-semibold tabular-nums">{fact.value}</dd>
          {fact.note && <dd className="text-sm text-muted-foreground">{fact.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

export default function LandingPage() {
  return (
    <>
      <section className="grid items-start gap-12 pt-4 pb-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-x-[72px] lg:pt-12 lg:pb-16">
        <div className="flex min-w-0 flex-col gap-6 lg:gap-7">
          <div className="inline-flex items-center gap-2 self-start rounded-full border border-primary px-3 py-1.5 font-mono text-[13px] font-medium text-primary">
            <span className="size-2 animate-pulse-dot rounded-full bg-destructive" aria-hidden />
            Спецтрек ФСП · ЛЦТ 2026
          </div>

          <div className="flex flex-col gap-4 lg:gap-5">
            <p
              aria-hidden
              className="font-mono text-[56px] leading-none font-bold tracking-[-0.025em] lg:text-[clamp(72px,6.7vw,96px)]"
            >
              <span className="text-primary">IT</span>Scout
            </p>
            <h1 className="max-w-[560px] font-mono text-xl font-medium tracking-[-0.025em] text-balance lg:text-2xl">
              <span className="sr-only">ITScout — </span>
              Платформа ИТ-подбора, где <span className="text-primary">первым пишет работодатель.</span>
            </h1>
          </div>

          <ol className="grid max-w-[640px] gap-3.5 sm:grid-cols-3 sm:gap-4">
            {mechanics.map((step) => (
              <li
                key={step.label}
                className={cn(
                  "flex flex-col gap-1 border-l-2 pl-3 sm:gap-1.5 sm:border-t-2 sm:border-l-0 sm:pt-3 sm:pl-0",
                  step.key ? "border-primary" : "border-border",
                )}
              >
                <span
                  className={cn(
                    "font-mono text-xs font-semibold tracking-[0.1em] uppercase",
                    step.key ? "text-primary" : "text-muted-foreground",
                  )}
                >
                  {step.label}
                </span>
                <span className="text-sm text-pretty">{step.text}</span>
              </li>
            ))}
          </ol>

          <DemoEntry />

          <Link
            to="/how-it-works"
            className="-mt-2 inline-flex min-h-11 items-center gap-2 self-start font-mono text-[13px] font-medium text-primary underline-offset-4 hover:underline sm:mt-0 sm:min-h-0"
          >
            Как работает тест: шаблоны, адаптивность, защита от слива
            <ArrowRight className="size-4 shrink-0" aria-hidden />
          </Link>
        </div>

        <LandingIllustration />
      </section>

      <section aria-label="ITScout в цифрах" className="pt-2 pb-10 lg:pb-14">
        <BankStats />
      </section>

      <section className="grid gap-0 md:grid-cols-2 md:gap-x-[72px] md:gap-y-12 md:pt-4 md:pb-16">
        <div className="space-y-5 border-t border-border-subtle py-8 md:border-t-0 md:py-0">
          <h2 className="flex items-center gap-2.5 font-mono text-xl font-semibold tracking-tight">
            <UserRound className="size-5 text-primary" aria-hidden /> Кандидату
          </h2>
          <Steps steps={candidateSteps} />
        </div>
        <div className="space-y-5 border-t border-border-subtle py-8 md:border-t-0 md:py-0">
          <h2 className="flex items-center gap-2.5 font-mono text-xl font-semibold tracking-tight">
            <Building2 className="size-5 text-primary" aria-hidden /> Работодателю
          </h2>
          <Steps steps={employerSteps} />
        </div>
      </section>
    </>
  );
}
