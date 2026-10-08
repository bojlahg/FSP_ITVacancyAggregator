import { AlertTriangle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
  /**
   * screen — экран или крупный раздел не загрузился: как EmptyState, но с «Повторить».
   * block — не загрузился один блок внутри карточки: строка-предупреждение, красный только у иконки.
   */
  variant?: "screen" | "block";
}

export function ErrorState({
  title = "Не удалось загрузить данные",
  description = "Проверьте соединение и попробуйте ещё раз.",
  onRetry,
  className,
  variant = "screen",
}: ErrorStateProps) {
  if (variant === "block") {
    return (
      // Кнопка уходит вправо, только когда блок достаточно широкий (container query, а не ширина экрана)
      <div role="alert" className={cn("@container rounded-lg bg-destructive-tint p-3 text-sm", className)}>
        <div className="flex flex-col gap-3 @md:flex-row @md:items-center">
          <div className="flex min-w-0 flex-1 items-start gap-2">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
            <div className="min-w-0">
              <span className="font-medium">{title}</span>
              {description && <span className="text-muted-foreground"> {description}</span>}
            </div>
          </div>
          {onRetry && (
            <Button variant="outline" size="sm" className="self-start bg-card @md:self-auto" onClick={onRetry}>
              <RotateCw /> Повторить
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      role="alert"
      className={cn("flex flex-col items-center gap-3 rounded-xl border bg-card px-6 py-10 text-center", className)}
    >
      <div className="flex size-12 items-center justify-center rounded-full bg-destructive-tint text-destructive-strong">
        <AlertTriangle className="size-6" aria-hidden />
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-bold">{title}</h3>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">{description}</p>
      </div>
      {onRetry && (
        <Button size="sm" className="mt-1" onClick={onRetry}>
          <RotateCw /> Повторить
        </Button>
      )}
    </div>
  );
}
