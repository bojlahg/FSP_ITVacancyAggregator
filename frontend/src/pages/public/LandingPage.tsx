import { ArrowRight, Building2, UserRound } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { ExplanationList, type ExplanationLine } from "@/components/ExplanationList";
import { SalaryRange } from "@/components/SalaryRange";
import { ScoreBadge } from "@/components/ScoreBadge";
import { Trace } from "@/components/Trace";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const facts = [
  { label: "Задача", value: "Агрегатор ИТ-вакансий с профилем ФСП" },
  { label: "MVP", value: "11 октября 2026" },
  { label: "Механика", value: "Тест → категория → приглашение" },
];

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

export default function LandingPage() {
  return (
    <>
      {/* Фирменная трасса, как на заглушке infra/site/index.html */}
      <Trace
        width={420}
        height={620}
        radius={44}
        startDot={false}
        className="absolute top-10 -right-16 hidden xl:block"
      />

      <section className="flex max-w-5xl flex-col justify-center py-16 lg:py-24">
        <div className="mb-8 inline-flex items-center gap-2.5 self-start rounded-full border-[1.5px] border-primary px-3.5 py-1.5 font-mono text-sm font-medium text-primary">
          <span className="size-2 animate-pulse-dot rounded-full bg-destructive" aria-hidden />
          Спецтрек ФСП · ЛЦТ 2026
        </div>

        <h1 className="text-[clamp(56px,12vw,132px)] leading-[0.95] font-extrabold tracking-[-0.04em] text-primary">
          IT<span className="text-foreground">Scout</span>
        </h1>
        <p className="mt-7 max-w-[28em] font-mono text-[clamp(18px,2.4vw,26px)] leading-snug font-medium">
          Платформа ИТ-подбора, где первым пишет работодатель.
        </p>
        <p className="mt-5 max-w-[46em] text-base leading-relaxed text-muted-foreground">
          Кандидаты проходят тестирование на грейд и попадают в категорию «специализация × грейд». Работодатель
          выбирает нужную категорию и отправляет приглашение конкретному человеку, сразу с вилкой зарплаты.
          Достижения в соревнованиях ФСП поднимают кандидата в выдаче.
        </p>

        <div className="mt-10 flex flex-wrap items-center gap-3">
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
        <Link
          to="/how-it-works"
          className="mt-5 self-start font-mono text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          Как работает тест: шаблоны, адаптивность, защита от слива <ArrowRight className="inline size-4 align-[-3px]" aria-hidden />
        </Link>

        <dl className="mt-14 grid grid-cols-1 border-t-[1.5px] border-ink sm:grid-cols-3">
          {facts.map((fact) => (
            <div key={fact.label} className="pt-4 pr-5">
              <dt className="font-mono text-xs font-medium tracking-[0.06em] text-muted-foreground uppercase">
                {fact.label}
              </dt>
              <dd className="mt-1.5 font-mono text-base font-bold">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="grid gap-10 border-t border-border-subtle py-16 lg:grid-cols-[1fr_1fr_1.1fr] lg:gap-12">
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

        <div className="space-y-4">
          <h2 className="text-xl font-extrabold">Объяснение, а не магия</h2>
          <p className="text-sm text-muted-foreground">
            Score и объяснение считаются одним кодом из одних и тех же компонентов. Работодатель видит, почему кандидат
            в выдаче, а кандидат — почему пришло приглашение.
          </p>
          <div className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-2">
                <div className="font-mono text-base font-bold">Анна К.</div>
                <CategoryBadge specialization="backend" grade="middle" />
              </div>
              <ScoreBadge score={84} />
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
        </div>
      </section>
    </>
  );
}
