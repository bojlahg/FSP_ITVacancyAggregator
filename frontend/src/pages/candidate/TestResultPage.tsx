import { ArrowUpRight, PartyPopper } from "lucide-react";
import { Link } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { PageHeader } from "@/components/PageHeader";
import { Trace } from "@/components/Trace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
// MOCK: заменить на GET /tests/attempts/{id}/result
import { mockMe, mockTopicResults } from "@/mocks/candidate";

export default function TestResultPage() {
  return (
    <>
      <PageHeader
        eyebrow="Результат теста"
        title="Тест пройден"
        description="Категория присвоена по результату теста. Её видят работодатели в поиске и подборках."
      />

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card className="relative overflow-hidden">
          <Trace width={200} height={160} radius={36} className="absolute top-0 right-0 hidden sm:block" />
          <CardHeader>
            <CardDescription className="flex items-center gap-2">
              <PartyPopper className="size-4 text-primary" aria-hidden /> Ваша категория
            </CardDescription>
            <CategoryBadge specialization={mockMe.specialization} grade={mockMe.grade} variant="solid" size="lg" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-5xl font-extrabold text-primary tabular-nums">{mockMe.percentile}</span>
              <span className="text-sm text-muted-foreground">перцентиль среди кандидатов Backend · Middle</span>
            </div>
            <div className="rounded-lg bg-primary-tint p-4 text-sm">
              Результат уверенный — можно сразу попробовать тест на <b>Senior</b>: в период калибровки это можно сделать
              один раз без ожидания.
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <Link to="/candidate">В кабинет</Link>
              </Button>
              <Button variant="outline">
                Тест на грейд выше <ArrowUpRight />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Разбор по темам</CardTitle>
            <CardDescription>Доля верных ответов с учётом сложности заданий</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {mockTopicResults.map((topic) => (
              <div key={topic.name} className="space-y-1.5">
                <div className="flex justify-between text-sm">
                  <span>{topic.name}</span>
                  <span className="font-mono font-bold tabular-nums">{topic.percent}%</span>
                </div>
                <Progress value={topic.percent} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
