import { Clock, Loader2, Play, Trophy } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { apiError } from "@/lib/api-error";
import { type ChallengeCard, useAvailableChallenges, useStartChallenge } from "@/lib/challenge-queries";
import { toPercent } from "@/lib/format";
import { GRADE_LABELS } from "@/lib/labels";

export default function CandidateChallengesPage() {
  const challenges = useAvailableChallenges();
  return (
    <>
      <PageHeader
        eyebrow="Челленджи"
        title="Челленджи компаний"
        description="Компании публикуют свои вопросы для кандидатов вашей категории. Пройдите челлендж, если компания вам интересна: она увидит результат и ответы без ваших контактов и сможет пригласить первой. Одна попытка, время на вопрос считает сервер. На грейд челленджи не влияют."
      />
      <div className="grid gap-4">
        {challenges.isPending && <SkeletonCards count={2} />}
        {challenges.isError && (
          <ErrorState description={apiError(challenges.error).message} onRetry={() => void challenges.refetch()} />
        )}
        {challenges.isSuccess && challenges.data.length === 0 && (
          <EmptyState
            icon={Trophy}
            title="Пока нет челленджей для вашей категории"
            description="Челленджи появятся, когда компании опубликуют вопросы для вашей специализации и грейда."
          />
        )}
        {challenges.data?.map((challenge) => <ChallengeItem key={challenge.id} challenge={challenge} />)}
      </div>
    </>
  );
}

function ChallengeItem({ challenge }: { challenge: ChallengeCard }) {
  const start = useStartChallenge();
  const navigate = useNavigate();
  const done = challenge.attempt_status === "completed";
  const begin = async () => {
    const attempt = await start.mutateAsync(challenge.id);
    void navigate(`/candidate/challenges/${attempt.attempt_id}`);
  };
  const minutes = Math.ceil((challenge.questions * challenge.time_per_question_sec) / 60);
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="soft">{challenge.company_name}</Badge>
          {challenge.grade && <Badge variant="muted">{GRADE_LABELS[challenge.grade]}</Badge>}
          {done && <Badge variant="outline">пройден</Badge>}
        </div>
        <CardTitle>{challenge.title}</CardTitle>
        <CardDescription className="whitespace-pre-line">{challenge.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Clock className="size-4" aria-hidden /> {challenge.questions} вопросов · до {minutes} мин
        </span>
        {challenge.skills.length > 0 && <span>навыки: {challenge.skills.join(", ")}</span>}
      </CardContent>
      <CardFooter className="flex-wrap gap-3 border-t border-border-subtle pt-5">
        {done ? (
          <span className="text-sm">
            Ваш результат:{" "}
            <b className="font-mono">{challenge.score != null ? `${toPercent(challenge.score)}%` : "отправлен"}</b>
          </span>
        ) : challenge.attempt_id ? (
          <Button asChild>
            <Link to={`/candidate/challenges/${challenge.attempt_id}`}>
              <Play /> Продолжить
            </Link>
          </Button>
        ) : (
          <Button onClick={() => void begin()} disabled={start.isPending}>
            {start.isPending ? <Loader2 className="animate-spin" /> : <Play />} Начать
          </Button>
        )}
        <FormAlert message={start.isError ? apiError(start.error).message : null} className="w-full" />
      </CardFooter>
    </Card>
  );
}
