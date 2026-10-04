import { ListChecks, Plus } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Button } from "@/components/ui/button";

export default function EmployerTasksPage() {
  return (
    <>
      <PageHeader
        eyebrow="Задания"
        title="Задания для кандидатов"
        description="Короткие практические задания от компании. Решения подтверждают навыки кандидата и поднимают его свежесть в выдаче."
        actions={
          <Button disabled title="Появится в следующей версии">
            <Plus /> Новое задание
          </Button>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <EmptyState
          icon={ListChecks}
          title="Заданий пока нет"
          description="Создайте первое задание: условие, стек и срок. Решения появятся здесь с оценкой по чек-листу."
        />
        <div className="space-y-2">
          <div className="font-mono text-xs tracking-wider text-muted-foreground uppercase">Так будут выглядеть решения</div>
          <SkeletonCards count={2} />
        </div>
      </div>
    </>
  );
}
