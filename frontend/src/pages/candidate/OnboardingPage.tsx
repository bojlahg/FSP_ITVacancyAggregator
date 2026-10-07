import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Award, Check, FileUp, PlayCircle } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { AbandonExpressButton } from "@/components/candidate/AbandonExpressButton";
import { CategoryBadge } from "@/components/CategoryBadge";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import {
  type CandidateProfile,
  type Grade,
  purposeFor,
  queryKeys,
  type SurveyResult,
  useCandidateMe,
  useGrades,
  useGradeStatus,
} from "@/lib/testing-queries";
import { cn } from "@/lib/utils";
import { BeforeTestStep } from "./onboarding/BeforeTestStep";
import { GradeStep } from "./onboarding/GradeStep";
import { SpecializationStep } from "./onboarding/SpecializationStep";
import { SurveyStep } from "./onboarding/SurveyStep";

const steps = ["Опрос", "Специализация", "Грейд", "Перед тестом"] as const;

// onboarding_step из GET /candidates/me → шаг мастера. "test" и "done" обрабатываются отдельно.
const stepIndexByOnboarding: Record<string, number> = { survey: 0, specialization: 1, grade: 2 };

export default function OnboardingPage() {
  const me = useCandidateMe();

  return (
    <>
      <PageHeader
        eyebrow="Онбординг"
        title="Получите категорию"
        description="Короткий опрос, подтверждение специализации, выбор грейда и адаптивный тест. Категорию определяет только тест."
        actions={
          // §6.2 п.2: резюме необязательно и только предзаполняет профиль
          <Button asChild variant="ghost">
            <Link to="/candidate/profile">
              <FileUp /> Заполнить профиль из PDF-резюме
            </Link>
          </Button>
        }
      />
      {me.isPending && <SkeletonCards count={1} />}
      {me.isError && (
        <ErrorState
          title="Не удалось загрузить профиль"
          description={apiError(me.error).message}
          onRetry={() => void me.refetch()}
        />
      )}
      {me.isSuccess && <OnboardingFlow me={me.data} />}
    </>
  );
}

/** Режим фиксируется по onboarding_step при входе: последующие обновления профиля не перескакивают шаги. */
function OnboardingFlow({ me }: { me: CandidateProfile }) {
  const [mode] = useState(me.onboarding_step);
  if (mode === "test") return <ResumeAttempt />;
  if (mode === "done") return <OnboardingDone me={me} />;
  return <Wizard me={me} initialStep={stepIndexByOnboarding[mode] ?? 0} />;
}

function ResumeAttempt() {
  const status = useGradeStatus();
  const attempt = status.data?.attempts.find((item) => item.status === "in_progress");

  if (status.isPending) return <SkeletonCards count={1} />;
  if (status.isError) {
    return <ErrorState description={apiError(status.error).message} onRetry={() => void status.refetch()} />;
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PlayCircle className="size-5 text-primary" aria-hidden /> У вас есть незаконченный тест
        </CardTitle>
        <CardDescription>
          Продолжите с того вопроса, на котором остановились. Таймер текущего вопроса продолжает идти.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {attempt ? (
          <div className="flex flex-wrap items-start gap-3">
            <Button asChild size="lg">
              <Link to={`/candidate/test/${attempt.id}`}>
                Продолжить тест <ArrowRight />
              </Link>
            </Button>
            {attempt.purpose === "express" && <AbandonExpressButton attemptId={attempt.id} size="lg" />}
          </div>
        ) : (
          <Button asChild variant="outline">
            <Link to="/candidate/grade">Открыть «Категория и грейд»</Link>
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function OnboardingDone({ me }: { me: CandidateProfile }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription className="flex items-center gap-2">
          <Award className="size-4 text-primary" aria-hidden /> Онбординг пройден
        </CardDescription>
        {me.category && (
          <CategoryBadge specialization={me.category.specialization} grade={me.category.grade} variant="solid" size="lg" />
        )}
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-muted-foreground">
        <p>Категория получена, работодатели видят вас в поиске. Сменить грейд можно на экране «Категория и грейд».</p>
        <div className="flex flex-wrap gap-2">
          <Button asChild>
            <Link to="/candidate/grade">
              Категория и грейд <ArrowRight />
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/candidate">В кабинет</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Wizard({ me, initialStep }: { me: CandidateProfile; initialStep: number }) {
  const queryClient = useQueryClient();
  const gradeStatus = useGradeStatus();
  const grades = useGrades();
  const [step, setStep] = useState(initialStep);
  // Результат опроса есть только в ответе POST /survey/responses — после перезагрузки страницы его нет.
  const [surveyResult, setSurveyResult] = useState<SurveyResult | null>(
    () => queryClient.getQueryData<SurveyResult>(queryKeys.surveyResult) ?? null,
  );
  const [specialization, setSpecialization] = useState<string | null>(me.specialization);
  const [grade, setGrade] = useState<Grade | null>(surveyResult?.suggested_grade ?? me.category?.grade ?? null);

  const currentGrade = me.category?.grade ?? null;

  return (
    <>
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
      <Progress value={((step + 1) / steps.length) * 100} className="mb-6" aria-label="Прогресс онбординга" />

      <Card>
        {step === 0 && (
          <SurveyStep
            onDone={(result) => {
              setSurveyResult(result);
              setGrade((current) => current ?? result.suggested_grade);
              setStep(1);
            }}
          />
        )}
        {step === 1 && (
          <SpecializationStep
            surveyResult={surveyResult}
            current={specialization}
            onBack={() => setStep(0)}
            onSurveyRequired={() => setStep(0)}
            onConfirmed={(slug) => {
              setSpecialization(slug);
              setStep(2);
            }}
          />
        )}
        {step === 2 && (
          <GradeStep
            selected={grade}
            suggested={surveyResult?.suggested_grade ?? null}
            currentGrade={currentGrade}
            cooldownDays={gradeStatus.data?.cooldown_days ?? null}
            onSelect={setGrade}
            onBack={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}
        {step === 3 && specialization && grade && (
          <BeforeTestStep
            specialization={specialization}
            grade={grade}
            purpose={purposeFor(grade, gradeStatus.data, grades.data, currentGrade)}
            onBack={() => setStep(2)}
          />
        )}
        {step === 3 && !(specialization && grade) && (
          <CardContent>
            <ErrorState
              title="Не хватает данных для теста"
              description="Подтвердите специализацию и выберите грейд."
              onRetry={() => setStep(specialization ? 2 : 1)}
            />
          </CardContent>
        )}
      </Card>
    </>
  );
}
