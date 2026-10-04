import { ArrowLeft, ArrowRight, Check, Clock, Upload } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { GRADE_LABELS, SPECIALIZATION_FULL_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

const steps = ["Опрос", "Специализация", "Грейд", "Тест"] as const;

// MOCK: варианты ответа придут из GET /survey/questions
const dailyActivities = [
  "Пишу серверную логику и API",
  "Верстаю интерфейсы и работаю с UI-фреймворками",
  "Настраиваю CI/CD, инфраструктуру и мониторинг",
  "Пишу автотесты и проверяю качество",
  "Анализирую данные и обучаю модели",
];

// MOCK: топ-2 из POST /survey/responses
const recommended = [
  { slug: "backend", weight: 0.71 },
  { slug: "fullstack", weight: 0.22 },
];

const gradeHints: Record<string, string> = {
  intern: "Учёба или первые проекты",
  junior: "Опыт меньше года",
  middle: "Опыт 1–3 года",
  senior: "Опыт больше 3 лет",
};

export default function OnboardingPage() {
  const [step, setStep] = useState(0);
  const [specialization, setSpecialization] = useState("backend");
  const [grade, setGrade] = useState("middle");

  return (
    <>
      <PageHeader
        eyebrow="Онбординг"
        title="Получите категорию"
        description="Четыре шага: короткий опрос, подтверждение специализации, выбор грейда и адаптивный тест. Категорию определяет только тест."
      />

      <ol className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Шаги онбординга">
        {steps.map((label, index) => (
          <li
            key={label}
            aria-current={index === step ? "step" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg border px-3 py-2.5",
              index === step && "border-primary bg-primary-tint",
              index < step && "border-border-subtle",
            )}
          >
            <span
              className={cn(
                "flex size-7 shrink-0 items-center justify-center rounded-full border-[1.5px] font-mono text-xs font-bold",
                index <= step ? "border-primary text-primary" : "border-border text-muted-foreground",
                index < step && "bg-primary text-primary-foreground",
              )}
            >
              {index < step ? <Check className="size-3.5" aria-hidden /> : index + 1}
            </span>
            <span className={cn("font-mono text-sm font-medium", index === step ? "text-primary" : "text-foreground")}>
              {label}
            </span>
          </li>
        ))}
      </ol>
      <Progress value={((step + 1) / steps.length) * 100} className="mb-6" />

      <Card>
        {step === 0 && (
          <>
            <CardHeader>
              <CardTitle>Чем вы занимаетесь каждый день?</CardTitle>
              <CardDescription>Вопрос 1 из 9 · можно выбрать несколько вариантов</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2">
              {dailyActivities.map((activity) => (
                <label key={activity} className="flex items-center gap-3 rounded-lg border px-4 py-3 text-sm hover:bg-muted">
                  <Checkbox /> {activity}
                </label>
              ))}
              <div className="mt-3 flex items-center gap-3 rounded-lg border border-dashed px-4 py-3 text-sm text-muted-foreground">
                <Upload className="size-4 text-primary" aria-hidden />
                Необязательно: загрузите PDF-резюме, чтобы предзаполнить профиль.
              </div>
            </CardContent>
          </>
        )}

        {step === 1 && (
          <>
            <CardHeader>
              <CardTitle>Мы предлагаем специализацию</CardTitle>
              <CardDescription>Рассчитано по ответам опроса. Подтвердите или выберите другую.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              {recommended.map((option) => (
                <button
                  key={option.slug}
                  type="button"
                  onClick={() => setSpecialization(option.slug)}
                  aria-pressed={specialization === option.slug}
                  className={cn(
                    "rounded-xl border p-4 text-left transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                    specialization === option.slug ? "border-primary bg-primary-tint" : "hover:bg-muted",
                  )}
                >
                  <div className="font-mono font-bold">{SPECIALIZATION_FULL_LABELS[option.slug]}</div>
                  <div className="mt-2 flex items-center gap-2">
                    <Progress value={option.weight * 100} className="h-1.5" />
                    <span className="font-mono text-xs tabular-nums">{Math.round(option.weight * 100)}%</span>
                  </div>
                </button>
              ))}
            </CardContent>
          </>
        )}

        {step === 2 && (
          <>
            <CardHeader>
              <CardTitle>Выберите грейд для теста</CardTitle>
              <CardDescription>
                Подсказка по вашему стажу (2 года): <b>Middle</b>. Если тест не пройден — предложим грейд ниже.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-4">
              {Object.entries(GRADE_LABELS).map(([slug, label]) => (
                <button
                  key={slug}
                  type="button"
                  onClick={() => setGrade(slug)}
                  aria-pressed={grade === slug}
                  className={cn(
                    "rounded-xl border p-4 text-left transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                    grade === slug ? "border-primary bg-primary-tint" : "hover:bg-muted",
                  )}
                >
                  <div className="font-mono text-lg font-extrabold">{label}</div>
                  <div className="text-xs text-muted-foreground">{gradeHints[slug]}</div>
                </button>
              ))}
            </CardContent>
          </>
        )}

        {step === 3 && (
          <>
            <CardHeader>
              <CardTitle>Перед тестом</CardTitle>
              <CardDescription>
                {SPECIALIZATION_FULL_LABELS[specialization]} · {GRADE_LABELS[grade]}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-2">
                <Badge variant="soft">
                  <Clock /> ~25 минут
                </Badge>
                <Badge variant="muted">по одному вопросу на экран</Badge>
                <Badge variant="muted">вернуться назад нельзя</Badge>
              </div>
              <p className="text-muted-foreground">
                Задания подбираются адаптивно: все кандидаты специализации оцениваются на одной шкале, поэтому результаты
                сопоставимы. Время ответа считает сервер. Повтор на тот же грейд — не раньше чем через 30 дней.
              </p>
            </CardContent>
          </>
        )}

        <CardFooter className="justify-between gap-2 border-t border-border-subtle pt-5">
          <Button variant="ghost" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0}>
            <ArrowLeft /> Назад
          </Button>
          {step < steps.length - 1 ? (
            <Button onClick={() => setStep((current) => current + 1)}>
              Далее <ArrowRight />
            </Button>
          ) : (
            // TODO: POST /tests/attempts {specialization, grade_target, purpose} → переход на попытку
            <Button asChild>
              <Link to="/candidate/test/demo">
                Начать тест <ArrowRight />
              </Link>
            </Button>
          )}
        </CardFooter>
      </Card>
    </>
  );
}
