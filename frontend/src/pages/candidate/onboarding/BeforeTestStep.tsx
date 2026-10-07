import { ArrowLeft, ArrowRight, Clock } from "lucide-react";
import { StartAttemptButton } from "@/components/candidate/StartAttemptButton";
import { TestRulesList } from "@/components/candidate/TestRules";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { gradeLabel, SPECIALIZATION_FULL_LABELS } from "@/lib/labels";
import { TEST_DURATION_LABEL, testRules, useAttemptRuleText, useTestLengthText } from "@/lib/test-rules";
import { type AttemptPurpose, type Grade, useGrades, useSpecializations } from "@/lib/testing-queries";

interface BeforeTestStepProps {
  specialization: string;
  grade: Grade;
  purpose: AttemptPurpose;
  onBack: () => void;
  onStarted?: () => void;
}

export function BeforeTestStep({ specialization, grade, purpose, onBack, onStarted }: BeforeTestStepProps) {
  const specializations = useSpecializations();
  const grades = useGrades();
  const specName =
    specializations.data?.find((item) => item.slug === specialization)?.name ??
    SPECIALIZATION_FULL_LABELS[specialization] ??
    specialization;
  const gradeName = grades.data?.find((item) => item.slug === grade)?.name ?? gradeLabel(grade);
  const lengthText = useTestLengthText(grade);
  const attemptRule = useAttemptRuleText(purpose);

  return (
    <>
      <CardHeader>
        <CardTitle>Перед тестом</CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-2">
          <Badge variant="soft">{specName}</Badge>
          <Badge variant="soft">{gradeName}</Badge>
          <Badge variant="muted">
            <Clock /> {TEST_DURATION_LABEL}
          </Badge>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <TestRulesList rules={[...testRules(lengthText), attemptRule]} />
        <p className="mt-4 text-sm text-muted-foreground">
          Найдите спокойное место и 25 минут без перерывов: приостановить тест нельзя.
        </p>
      </CardContent>
      <CardFooter className="flex-wrap items-start justify-between gap-2 border-t border-border-subtle pt-5">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft /> Назад
        </Button>
        <StartAttemptButton
          params={{ specialization, grade_target: grade, purpose }}
          size="lg"
          className="justify-items-end"
          onStarted={onStarted}
          // Этот экран и есть правила теста — второе подтверждение не нужно
          confirm={false}
        >
          Начать тест <ArrowRight />
        </StartAttemptButton>
      </CardFooter>
    </>
  );
}
