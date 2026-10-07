import { ArrowRight, Building2, Eye, Loader2, RefreshCw, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { ExplanationList, type ExplanationLine } from "@/components/ExplanationList";
import { FormAlert } from "@/components/FormAlert";
import { SalaryRange } from "@/components/SalaryRange";
import { ScoreBadge } from "@/components/ScoreBadge";
import { Trace } from "@/components/Trace";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import { postLoginPath, type TokenResponse, type UserRole, useAuth } from "@/lib/auth";
import { useDemoLogin } from "@/lib/auth-queries";
import { useExplainerOverview } from "@/lib/explainer-queries";
import { extraItemsNote, testItemsRange } from "@/lib/format";

const candidateSteps = [
  { title: "Опрос", text: "8–10 вопросов о том, чем вы занимаетесь. Система предложит специализацию." },
  { title: "Тест на грейд", text: "Адаптивный тест около 25 минут, по одному вопросу на экран." },
  { title: "Категория", text: "Вы получаете категорию «специализация × грейд», которую видят работодатели." },
  { title: "Приглашения", text: "Работодатели пишут первыми — сразу с вилкой зарплаты и объяснением «почему вы»." },
];

const employerSteps = [
  { title: "Потребность", text: "Опишите задачу текстом — мы разберём её в стек, грейд и вилку." },
  { title: "Подборка", text: "Рекомендованные категории и кандидаты с понятным объяснением совпадения." },
  { title: "Приглашение", text: "Пишете конкретному человеку и сразу указываете вилку от–до." },
  { title: "Контакты", text: "Контакты кандидата открываются, как только он принял приглашение." },
];

// Пример объяснения из docs/implementation.md §8.4 — иллюстрация на лендинге, не данные API.
const sampleExplanation: ExplanationLine[] = [
  { kind: "positive", text: "Категория совпадает: Middle Backend, подтверждено тестом (78-й перцентиль)" },
  { kind: "positive", text: "PostgreSQL — проверено тестом: «Базы данных» 85%" },
  { kind: "positive", text: "ФСП: 2 место, всероссийский хакатон по продуктовому программированию, 2025" },
  { kind: "warning", text: "Kafka — нет данных" },
];

const demoPersonas: { role: UserRole; label: string; icon: typeof UserRound }[] = [
  { role: "candidate", label: "Посмотреть как кандидат", icon: UserRound },
  { role: "employer", label: "Посмотреть как работодатель", icon: Building2 },
];

function Steps({ steps }: { steps: { title: string; text: string }[] }) {
  return (
    <ol className="grid gap-5">
      {steps.map((step, index) => (
        <li key={step.title} className="flex gap-4">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full border-[1.5px] border-primary font-mono text-sm font-bold text-primary">
            {index + 1}
          </span>
          <div className="space-y-1">
            <h3 className="text-base font-bold">{step.title}</h3>
            <p className="text-sm leading-relaxed text-muted-foreground">{step.text}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function SampleCard() {
  return (
    <figure className="space-y-3">
      <figcaption className="font-mono text-xs font-medium tracking-[0.06em] text-muted-foreground uppercase">
        Так кандидат выглядит в подборке
      </figcaption>
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2">
            <div className="font-mono text-base font-bold">Анна К.</div>
            <CategoryBadge specialization="backend" grade="middle" />
          </div>
          <ScoreBadge score={84} size="lg" />
        </div>
        <ExplanationList items={sampleExplanation} className="mt-4" />
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border-subtle pt-4">
          <Badge variant="soft">ФСП</Badge>
          <Badge variant="muted">проверено тестом</Badge>
          <span className="ml-auto text-xs text-muted-foreground">
            Приглашение: <SalaryRange from={220_000} to={260_000} className="text-foreground" />
          </span>
        </div>
      </div>
      <p className="text-sm leading-relaxed text-muted-foreground">
        Объяснение, а не магия: оценка и строки «почему» считаются одним кодом из одних и тех же данных. Работодатель
        видит, почему кандидат в выдаче, а кандидат — почему пришло приглашение.
      </p>
    </figure>
  );
}

function demoErrorMessage(err: unknown): string {
  const { status, message } = apiError(err);
  if (status === 404) return "Демо-вход на этом сервере выключен — зарегистрируйтесь или войдите";
  return message;
}

/** Демо-вход теми же готовыми аккаунтами, что и на /login: сразу в кабинет, без регистрации. */
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
    <div className="mt-6 max-w-xl space-y-3 rounded-xl border border-dashed border-primary p-4">
      <p className="flex items-center gap-2 text-sm">
        <Eye className="size-4 shrink-0 text-primary" aria-hidden />
        <span>
          <b>Демо без регистрации</b>
          <span className="text-muted-foreground"> — готовые аккаунты с данными</span>
        </span>
      </p>
      <div className="flex flex-wrap gap-2">
        {demoPersonas.map(({ role, label, icon: Icon }) => (
          <Button key={role} type="button" variant="outline" disabled={demoLogin.isPending} onClick={() => onDemo(role)}>
            {demoLogin.isPending && demoLogin.variables === role ? <Loader2 className="animate-spin" /> : <Icon />}
            {label}
          </Button>
        ))}
      </div>
      <FormAlert message={demoLogin.error ? demoErrorMessage(demoLogin.error) : null} />
    </div>
  );
}

/** Живые цифры банка заданий — тот же /explainer/overview, что и на «Как работает тест». */
function BankStats() {
  const overview = useExplainerOverview();

  if (overview.isPending) {
    return (
      <div
        className="grid grid-cols-2 gap-4 border-t-[1.5px] border-foreground pt-4 lg:grid-cols-4"
        role="status"
        aria-busy="true"
        aria-label="Загрузка цифр"
      >
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-20" />
        ))}
      </div>
    );
  }
  if (overview.isError) {
    return (
      <div className="flex flex-wrap items-center gap-3 border-t-[1.5px] border-foreground pt-4 text-sm text-muted-foreground">
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
      <p className="border-t-[1.5px] border-foreground pt-4 text-sm text-muted-foreground">
        Банк заданий ещё не загружен.
      </p>
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
    <dl className="grid grid-cols-2 border-t-[1.5px] border-foreground lg:grid-cols-4">
      {facts.map((fact) => (
        <div key={fact.label} className="min-w-0 pt-4 pr-4 pb-2">
          <dt className="font-mono text-xs font-medium tracking-[0.06em] text-muted-foreground uppercase">
            {fact.label}
          </dt>
          <dd className="mt-1 font-mono text-3xl font-bold tabular-nums">{fact.value}</dd>
          {fact.note && <dd className="mt-1 text-sm text-muted-foreground">{fact.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

export default function LandingPage() {
  return (
    <>
      <section className="grid items-center gap-12 py-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-16 lg:py-20">
        <div className="flex min-w-0 flex-col">
          <div className="mb-8 inline-flex items-center gap-2.5 self-start rounded-full border-[1.5px] border-primary px-3.5 py-1.5 font-mono text-sm font-medium text-primary">
            <span className="size-2 animate-pulse-dot rounded-full bg-destructive" aria-hidden />
            Спецтрек ФСП · ЛЦТ 2026
          </div>

          <h1 className="text-[clamp(56px,9vw,112px)] leading-[0.95] font-extrabold tracking-[-0.04em] text-primary">
            IT<span className="text-foreground">Scout</span>
          </h1>
          <p className="mt-7 max-w-[28em] font-mono text-[clamp(18px,2.2vw,24px)] leading-snug font-medium">
            Платформа ИТ-подбора, где первым пишет работодатель.
          </p>
          <p className="mt-5 max-w-[40em] text-base leading-relaxed text-muted-foreground">
            Кандидаты проходят тестирование на грейд и попадают в категорию «специализация × грейд». Работодатель
            выбирает нужную категорию и отправляет приглашение конкретному человеку, сразу с вилкой зарплаты.
            Достижения в соревнованиях ФСП поднимают кандидата в выдаче.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button asChild size="lg">
              <Link to="/register?role=candidate">
                <UserRound /> Регистрация кандидата
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/register?role=employer">
                <Building2 /> Регистрация работодателя
              </Link>
            </Button>
            <Button asChild size="lg" variant="link">
              <Link to="/login">
                Войти <ArrowRight />
              </Link>
            </Button>
          </div>

          <DemoEntry />

          <Link
            to="/how-it-works"
            className="mt-6 self-start font-mono text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            Как работает тест: шаблоны, адаптивность, защита от слива{" "}
            <ArrowRight className="inline size-4 align-[-3px]" aria-hidden />
          </Link>
        </div>

        <div className="relative min-w-0">
          {/* Фирменная трасса огибает угол карточки, как на заглушке infra/site/index.html */}
          <Trace width={220} height={150} radius={40} flip className="absolute -top-8 -right-8 hidden xl:block" />
          <div className="relative">
            <SampleCard />
          </div>
        </div>
      </section>

      <section aria-label="ITScout в цифрах" className="pb-14">
        <BankStats />
      </section>

      <section className="grid gap-10 border-t border-border-subtle py-16 md:grid-cols-2 lg:gap-16">
        <div className="space-y-6">
          <h2 className="flex items-center gap-2 text-xl font-extrabold">
            <UserRound className="size-5 text-primary" aria-hidden /> Кандидату
          </h2>
          <Steps steps={candidateSteps} />
        </div>
        <div className="space-y-6">
          <h2 className="flex items-center gap-2 text-xl font-extrabold">
            <Building2 className="size-5 text-primary" aria-hidden /> Работодателю
          </h2>
          <Steps steps={employerSteps} />
        </div>
      </section>
    </>
  );
}
