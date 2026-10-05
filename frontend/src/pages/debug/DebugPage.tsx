import { Bug, CheckCircle2, Loader2 } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiError } from "@/lib/api-error";
import { type DebugAction, useDebugAction, useDebugStatus } from "@/lib/debug-queries";

const ACTIONS: Record<DebugAction, { title: string; description: string; button: string; confirm?: string }> = {
  reset_cooldowns: {
    title: "Сбросить ограничения на пересдачу",
    description: "Снимает интервал между попытками теста и ограничения смены грейда — можно сразу пройти тест снова.",
    button: "Сбросить ограничения",
  },
  reset_test: {
    title: "Удалить результаты теста",
    description: "Удаляет ваши попытки и категорию: профиль вернётся к состоянию «тест не пройден».",
    button: "Удалить результаты",
    confirm: "Точно удалить попытки и категорию?",
  },
  test_email: {
    title: "Проверить почту",
    description: "Отправляет тестовое письмо на адрес вашего аккаунта.",
    button: "Отправить письмо",
  },
  reseed: {
    title: "Пересоздать демо-данные",
    description: "Очищает базу и заново генерирует демо-данные (около минуты). Экспертная разметка сохраняется, бэкап — через server-ops.",
    button: "Пересоздать",
    confirm: "Все пользователи и данные, кроме экспертной разметки, будут удалены. Продолжить?",
  },
};

/** Отладочный раздел для команды: виден только при DEBUG_TOOLS=true на сервере. */
export default function DebugPage() {
  const status = useDebugStatus();

  return (
    <>
      <PageHeader
        eyebrow="Только для команды"
        title="Отладка"
        description="Раздел включается настройкой DEBUG_TOOLS на сервере. Перед показом жюри его нужно выключить."
      />
      {status.isPending ? (
        <SkeletonCards count={2} className="max-w-3xl" />
      ) : status.isError ? (
        <ErrorState description={apiError(status.error).message} onRetry={() => void status.refetch()} />
      ) : !status.data ? (
        <EmptyState
          icon={Bug}
          title="Отладочный раздел выключен"
          description="На сервере не задан DEBUG_TOOLS=true — служебные действия недоступны."
        />
      ) : status.data.actions.length === 0 ? (
        <EmptyState icon={Bug} title="Для вашей роли действий нет" />
      ) : (
        <div className="grid max-w-3xl gap-4">
          {status.data.actions.map((action) =>
            action in ACTIONS ? <ActionCard key={action} action={action as DebugAction} /> : null,
          )}
        </div>
      )}
    </>
  );
}

function ActionCard({ action }: { action: DebugAction }) {
  const run = useDebugAction();
  const [armed, setArmed] = useState(false);
  const meta = ACTIONS[action];

  const onClick = () => {
    if (meta.confirm && !armed) {
      setArmed(true);
      return;
    }
    setArmed(false);
    run.mutate(action);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{meta.title}</CardTitle>
        <CardDescription>{meta.description}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {armed && meta.confirm && <p className="text-sm font-medium text-destructive-strong">{meta.confirm}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <Button variant={armed ? "destructive" : "outline"} onClick={onClick} disabled={run.isPending}>
            {run.isPending && <Loader2 className="animate-spin" />}
            {armed ? "Да, выполнить" : meta.button}
          </Button>
          {armed && (
            <Button variant="ghost" onClick={() => setArmed(false)}>
              Отмена
            </Button>
          )}
        </div>
        {run.isSuccess && (
          <p role="status" className="flex items-center gap-2 text-sm text-primary">
            <CheckCircle2 className="size-4" aria-hidden /> {run.data.message}
          </p>
        )}
        <FormAlert message={run.isError ? apiError(run.error).message : null} />
      </CardContent>
    </Card>
  );
}
