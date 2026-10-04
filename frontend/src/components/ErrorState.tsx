import { AlertTriangle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "Не удалось загрузить данные",
  description = "Проверьте соединение и попробуйте ещё раз.",
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn("flex flex-col items-center gap-3 rounded-xl border bg-destructive-tint px-6 py-10 text-center", className)}
    >
      <AlertTriangle className="size-6 text-destructive" aria-hidden />
      <div className="space-y-1">
        <h3 className="text-base font-bold">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw /> Повторить
        </Button>
      )}
    </div>
  );
}
