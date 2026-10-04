import { CalendarClock, ListChecks, Sparkles } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function CandidateTasksPage() {
  return (
    <>
      <PageHeader
        eyebrow="Задания"
        title="Регулярные задания"
        description="Короткие задания по вашей специализации. Решённые задания подтверждают навыки и держат профиль «свежим» в выдаче работодателей."
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <EmptyState
          icon={ListChecks}
          title="Активных заданий нет"
          description="Новое задание появится в начале недели. Мы пришлём уведомление на почту."
        />
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="size-4 text-primary" aria-hidden /> Как это работает
            </CardTitle>
            <CardDescription>Задания от платформы и от работодателей</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p className="flex gap-2">
              <CalendarClock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              Свежесть профиля снижается вдвое каждые 90 дней без подтверждённых действий.
            </p>
            <div className="space-y-2 pt-2" aria-hidden>
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
