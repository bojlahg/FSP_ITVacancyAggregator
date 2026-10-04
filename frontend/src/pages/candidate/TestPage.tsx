import { Clock } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
// MOCK: заменить на GET /tests/attempts/{id}/current (без ключа ответа)
import { mockTestQuestion } from "@/mocks/candidate";

// Отображение таймера на клиенте; реальное время ответа считает сервер (docs/implementation.md §10).
const DEMO_DURATION_SEC = 25 * 60;

function formatTimer(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export default function TestPage() {
  const { attemptId } = useParams();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<number | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(DEMO_DURATION_SEC);
  const question = mockTestQuestion;

  useEffect(() => {
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const submit = () => {
    // TODO: POST /tests/attempts/{id}/answer {item_id, response}; после последнего — на экран результата.
    console.info("[test] TODO: submit answer", { attemptId, selected });
    navigate(`/candidate/test/${attemptId}/result`);
  };

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="sr-only">Прохождение теста</h1>
      <div className="mb-6 space-y-3">
        <div className="flex items-center justify-between gap-4">
          <span className="font-mono text-sm font-medium">
            Вопрос {question.index} из {question.total}
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-sm font-bold tabular-nums",
              secondsLeft < 120 ? "border-destructive" : "border-border",
            )}
            aria-label="Осталось времени"
          >
            <Clock className="size-4 text-primary" aria-hidden />
            {formatTimer(secondsLeft)}
          </span>
        </div>
        <Progress value={(question.index / question.total) * 100} />
      </div>

      <Card>
        <CardHeader>
          <Badge variant="soft">{question.topic}</Badge>
          <CardTitle className="mt-2 text-xl">{question.text}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <pre className="overflow-x-auto rounded-lg bg-ink p-4 text-sm leading-relaxed text-ink-foreground">
            <code>{question.code}</code>
          </pre>
          <div role="radiogroup" aria-label="Варианты ответа" className="grid gap-2">
            {question.options.map((option, index) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={selected === index}
                onClick={() => setSelected(index)}
                className={cn(
                  "flex items-center gap-3 rounded-lg border px-4 py-3 text-left font-mono text-sm transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                  selected === index ? "border-primary bg-primary-tint text-primary" : "hover:bg-muted",
                )}
              >
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-bold",
                    selected === index ? "border-primary bg-primary text-primary-foreground" : "border-border",
                  )}
                >
                  {String.fromCharCode(65 + index)}
                </span>
                {option}
              </button>
            ))}
          </div>
        </CardContent>
        <CardFooter className="justify-between gap-3 border-t border-border-subtle pt-5">
          <span className="text-xs text-muted-foreground">Вернуться к предыдущему вопросу нельзя</span>
          <Button onClick={submit} disabled={selected === null}>
            Ответить
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
