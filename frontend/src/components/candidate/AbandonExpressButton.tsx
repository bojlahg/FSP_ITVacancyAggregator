import { Loader2, Square } from "lucide-react";
import { type ComponentProps, useState } from "react";
import { FormAlert } from "@/components/FormAlert";
import { Button } from "@/components/ui/button";
import { apiError } from "@/lib/api-error";
import { useAbandonExpress } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

interface AbandonExpressButtonProps {
  attemptId: number;
  onDone?: () => void;
  size?: ComponentProps<typeof Button>["size"];
  /** На экране вопроса кнопка тихая (ghost), чтобы не спорить с «Ответить». */
  variant?: "outline" | "ghost";
  className?: string;
}

/** «Завершить экспресс-тест» с подтверждением: попытка закрывается без результата и больше не блокирует тесты. */
export function AbandonExpressButton({ attemptId, onDone, size = "sm", variant = "outline", className }: AbandonExpressButtonProps) {
  const abandon = useAbandonExpress();
  const [confirming, setConfirming] = useState(false);

  if (!confirming) {
    return (
      <Button variant={variant} size={size} className={className} onClick={() => setConfirming(true)}>
        <Square aria-hidden /> Завершить экспресс-тест
      </Button>
    );
  }
  return (
    <div className={cn("grid gap-2", className)} role="group" aria-label="Подтверждение завершения экспресс-теста">
      <span className="text-sm text-muted-foreground">
        Экспресс-тест закроется без результата. Категорию и попытки смены грейда он не затрагивает.
      </span>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="destructive"
          size={size}
          disabled={abandon.isPending}
          onClick={() => abandon.mutate(attemptId, { onSuccess: () => onDone?.() })}
        >
          {abandon.isPending && <Loader2 className="animate-spin" aria-hidden />} Да, завершить
        </Button>
        <Button variant="ghost" size={size} disabled={abandon.isPending} onClick={() => setConfirming(false)}>
          Отмена
        </Button>
      </div>
      {abandon.isError && <FormAlert message={apiError(abandon.error).message} />}
    </div>
  );
}
