import { Zap } from "lucide-react";
import { useState } from "react";
import { StartAttemptButton } from "@/components/candidate/StartAttemptButton";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { plural } from "@/lib/format";
import { gradeLabel } from "@/lib/labels";
import { type Grade, type GradeStatus, useGrades } from "@/lib/testing-queries";

interface ExpressTestCardProps {
  express: NonNullable<GradeStatus["express"]>;
  specialization: string;
  defaultGrade: Grade;
  disabled: boolean;
  /** Идёт незаконченный экспресс-тест: подсказываем, как его завершить. */
  unfinishedExpress?: boolean;
}

/** Экспресс-тест (§10.3.1): короткая проверка уровня — категорию не присваивает и попытки не тратит. */
export function ExpressTestCard({
  express,
  specialization,
  defaultGrade,
  disabled,
  unfinishedExpress = false,
}: ExpressTestCardProps) {
  const grades = useGrades();
  const [grade, setGrade] = useState<Grade>(defaultGrade);
  const minutes = Math.max(3, Math.round(express.items / 2));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Zap className="size-4 text-primary" aria-hidden /> Экспресс-тест · ~{minutes} мин
        </CardTitle>
        <CardDescription>
          {express.items} {plural(express.items, ["задание", "задания", "заданий"])} той же механики: адаптивный подбор,
          свои экземпляры, время на ответ считает сервер. Покажет, проходите ли вы порог выбранного грейда.{" "}
          <b className="text-foreground">Категорию не присваивает</b> и попытки смены грейда не тратит — подходит,
          чтобы познакомиться с тестом. До {express.per_day} в сутки.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-[minmax(0,12rem)_auto] sm:items-end">
        <div className="grid gap-1.5">
          <Label htmlFor="express-grade">Грейд</Label>
          <Select id="express-grade" value={grade} onChange={(event) => setGrade(event.target.value as Grade)}>
            {(grades.data ?? []).map((item) => (
              <option key={item.slug} value={item.slug}>
                {gradeLabel(item.slug)}
              </option>
            ))}
          </Select>
        </div>
        <StartAttemptButton
          variant="outline"
          disabled={disabled}
          className="justify-items-start"
          params={{ specialization, grade_target: grade, purpose: "express" }}
        >
          <Zap /> Пройти экспресс-тест
        </StartAttemptButton>
        {unfinishedExpress && (
          <p className="text-sm text-muted-foreground sm:col-span-2">
            Предыдущий экспресс-тест не закончен — продолжите его или завершите кнопкой «Завершить экспресс-тест» в
            блоке «Текущий статус».
          </p>
        )}
      </CardContent>
    </Card>
  );
}
