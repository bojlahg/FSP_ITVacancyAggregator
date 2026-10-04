import { ArrowDown, ArrowUp, History, Timer } from "lucide-react";
import { CategoryBadge } from "@/components/CategoryBadge";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
// MOCK: заменить на GET /candidates/me/grade-status
import { mockGradeHistory, mockMe } from "@/mocks/candidate";

export default function GradePage() {
  return (
    <>
      <PageHeader
        eyebrow="Категория и грейд"
        title="Категория и грейд"
        description="Текущая категория, история тестов и ближайшие возможности сменить грейд. Неудачная попытка повышения не понижает текущий грейд."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <CardDescription className="font-mono text-xs tracking-wider uppercase">Текущий статус</CardDescription>
            <CategoryBadge specialization={mockMe.specialization} grade={mockMe.grade} variant="solid" size="lg" />
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="font-mono text-2xl font-extrabold">{mockMe.percentile}</div>
                <div className="text-xs text-muted-foreground">перцентиль в категории</div>
              </div>
              <div>
                <div className="font-mono text-2xl font-extrabold">{mockMe.validMonthsLeft} мес</div>
                <div className="text-xs text-muted-foreground">результат действителен</div>
              </div>
            </div>
            <Separator />
            <div className="flex items-center gap-2 text-muted-foreground">
              <Timer className="size-4 text-primary" aria-hidden />
              Следующая смена грейда — через <b className="font-mono text-foreground">{mockMe.nextGradeChangeInDays} дней</b>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button disabled>
                <ArrowUp /> Повысить
              </Button>
              <Button variant="outline" disabled>
                <ArrowDown /> Понизить
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Смена грейда не чаще раза в 90 дней. В демо-режиме доступна кнопка «Сбросить ограничения».
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="size-4 text-primary" aria-hidden /> История
            </CardTitle>
            <CardDescription>Опросы, попытки и выданные категории</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="relative space-y-5 border-l-[1.5px] border-primary pl-5">
              {mockGradeHistory.map((item, index) => (
                <li key={index} className="relative">
                  <span className="absolute top-1.5 -left-[25px] size-2 rounded-full bg-primary" aria-hidden />
                  <div className="font-mono text-xs text-muted-foreground">{item.date}</div>
                  <div className="font-medium">{item.event}</div>
                  <div className="text-sm text-muted-foreground">{item.result}</div>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
