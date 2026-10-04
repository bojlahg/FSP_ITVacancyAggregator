import { Loader2 } from "lucide-react";

/** Показывается, пока грузится код ленивого маршрута при первом открытии. */
export function RouteFallback() {
  return (
    <div className="flex min-h-dvh items-center justify-center" aria-busy="true">
      <Loader2 className="size-6 animate-spin text-primary" aria-label="Загрузка" />
    </div>
  );
}
