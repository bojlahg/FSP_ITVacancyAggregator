import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

/** Ошибка формы целиком (не привязанная к полю): ответ API, сеть и т. п. */
export function FormAlert({ message, className }: { message?: string | null; className?: string }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive-tint px-3 py-2 text-sm text-destructive-strong",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  );
}
