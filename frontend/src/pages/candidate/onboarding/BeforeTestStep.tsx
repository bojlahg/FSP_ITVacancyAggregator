import { ArrowLeft, ArrowRight, Clock, EyeOff, ListOrdered, Shuffle, Timer, Undo2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { StartAttemptButton } from "@/components/candidate/StartAttemptButton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { gradeLabel, SPECIALIZATION_FULL_LABELS } from "@/lib/labels";
import { type AttemptPurpose, type Grade, useGrades, useSpecializations } from "@/lib/testing-queries";

// docs/implementation.md §6.2 и §10.3: ~25 минут, 18 заданий двух этапов + уточняющие у порога + пилотные.
const rules: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: ListOrdered, title: "Один вопрос на экране", text: "Около 20 заданий, примерно 25 минут. Число может немного вырасти, если результат близок к порогу грейда." },
  { icon: Undo2, title: "Назад вернуться нельзя", text: "Ответ отправляется сразу. Если не знаете — выберите наиболее вероятный вариант." },
  { icon: Timer, title: "Таймер на каждый вопрос", text: "Время считает сервер. Когда оно выходит, текущий ответ отправляется автоматически." },
  { icon: EyeOff, title: "Уход со вкладки фиксируется", text: "Мы отмечаем переключения вкладок, но баллы за это не снимаем." },
  { icon: Shuffle, title: "Задания у всех разные", text: "Их сложность выверена: результаты сравниваются на общей шкале, поэтому они сопоставимы." },
];

interface BeforeTestStepProps {
  specialization: string;
  grade: Grade;
  purpose: AttemptPurpose;
  onBack: () => void;
}

export function BeforeTestStep({ specialization, grade, purpose, onBack }: BeforeTestStepProps) {
  const specializations = useSpecializations();
  const grades = useGrades();
  const specName =
    specializations.data?.find((item) => item.slug === specialization)?.name ??
    SPECIALIZATION_FULL_LABELS[specialization] ??
    specialization;
  const gradeName = grades.data?.find((item) => item.slug === grade)?.name ?? gradeLabel(grade);

  return (
    <>
      <CardHeader>
        <CardTitle>Перед тестом</CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-2">
          <Badge variant="soft">{specName}</Badge>
          <Badge variant="soft">{gradeName}</Badge>
          <Badge variant="muted">
            <Clock /> ~25 минут
          </Badge>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="grid gap-3 sm:grid-cols-2">
          {rules.map(({ icon: Icon, title, text }) => (
            <li key={title} className="flex gap-3 rounded-lg border border-border-subtle p-4">
              <Icon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
              <div className="space-y-1">
                <div className="font-mono text-sm font-bold">{title}</div>
                <p className="text-sm text-muted-foreground">{text}</p>
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm text-muted-foreground">
          Найдите спокойное место и 25 минут без перерывов: приостановить тест нельзя.
        </p>
      </CardContent>
      <CardFooter className="flex-wrap items-start justify-between gap-2 border-t border-border-subtle pt-5">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft /> Назад
        </Button>
        <StartAttemptButton params={{ specialization, grade_target: grade, purpose }} size="lg" className="justify-items-end">
          Начать тест <ArrowRight />
        </StartAttemptButton>
      </CardFooter>
    </>
  );
}
