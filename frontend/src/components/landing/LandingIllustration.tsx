import { Lock, Mail } from "lucide-react";
import { CategoryBadge } from "@/components/CategoryBadge";
import { ExplanationList, type ExplanationLine } from "@/components/ExplanationList";
import { SalaryFigure } from "@/components/SalaryFigure";
import { Trace } from "@/components/Trace";

// Пример объяснения из docs/implementation.md §8.4 — иллюстрация на лендинге, не данные API.
const sampleExplanation: ExplanationLine[] = [
  { kind: "positive", text: "Категория совпадает: Backend · Middle, подтверждено тестом" },
  { kind: "positive", text: "PostgreSQL — проверено тестом: «Базы данных» 85%" },
  { kind: "positive", text: "ФСП: 2 место, всероссийский хакатон по продуктовому программированию, 2025" },
  { kind: "warning", text: "Kafka — нет данных" },
];

function StepCaption({ children }: { children: string }) {
  return (
    <figcaption className="mb-3 font-mono text-xs font-medium tracking-[0.1em] text-muted-foreground uppercase">
      {children}
    </figcaption>
  );
}

/**
 * Механика в картинке: шаг 1 — кандидат в подборке работодателя (score → имя → причины),
 * шаг 2 — приглашение с вилкой и закрытыми контактами. Статичная иллюстрация, не данные API.
 */
export function LandingIllustration() {
  return (
    <div className="relative flex min-w-0 flex-col pt-8 lg:pt-10">
      {/* Фирменная трасса огибает угол иллюстрации, как на заглушке infra/site/index.html */}
      <Trace width={200} height={120} radius={32} flip className="absolute top-0 -right-2 hidden sm:block lg:-right-6" />

      <figure>
        <StepCaption>Шаг 1 · работодатель видит в подборке</StepCaption>
        <div className="flex flex-col gap-4 rounded-xl border bg-card p-4 sm:p-6">
          <div className="flex items-start gap-4">
            <span
              role="img"
              aria-label="Совпадение 84 из 100"
              className="grid size-14 shrink-0 place-items-center rounded-lg bg-primary font-mono text-[28px] leading-none font-bold text-primary-foreground tabular-nums"
            >
              84
            </span>
            <div className="flex min-w-0 flex-col gap-1.5">
              <div className="font-mono text-lg font-semibold tracking-tight">Анна К.</div>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <CategoryBadge specialization="backend" grade="middle" />
                <span className="text-xs text-muted-foreground">78-й перцентиль в категории</span>
              </div>
            </div>
          </div>
          <ExplanationList items={sampleExplanation} className="space-y-2" />
        </div>
      </figure>

      <div aria-hidden className="flex items-center gap-3 py-1 pl-[43px] sm:pl-[51px]">
        <span className="h-10 w-[1.5px] bg-primary" />
        <span className="font-mono text-xs font-medium text-primary">Пригласить</span>
      </div>

      <figure>
        <StepCaption>Шаг 2 · работодатель пишет первым</StepCaption>
        <div className="flex flex-col gap-3.5 rounded-xl border-2 border-primary bg-card p-4 sm:p-6">
          <div className="flex flex-col gap-0.5 sm:flex-row sm:flex-wrap sm:items-baseline sm:justify-between sm:gap-3">
            <div className="flex items-center gap-2 font-mono text-base font-semibold tracking-tight">
              <Mail className="size-4 shrink-0 text-primary" aria-hidden />
              Демо Банк → Анна К.
            </div>
            <span className="text-xs text-muted-foreground">Backend-разработчик в платёжную команду</span>
          </div>
          <SalaryFigure from={220_000} to={260_000} className="text-[22px] leading-7" />
          <p className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2.5 text-sm">
            <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
            <span>Контакты Анны откроются, когда она примет приглашение</span>
          </p>
        </div>
      </figure>

      <p className="mt-5 text-sm leading-relaxed text-pretty text-muted-foreground">
        Объяснение, а не магия: оценка и строки «почему» считаются одним кодом из одних и тех же данных. Работодатель
        видит, почему кандидат в выдаче, а кандидат — почему пришло приглашение.
      </p>
    </div>
  );
}
