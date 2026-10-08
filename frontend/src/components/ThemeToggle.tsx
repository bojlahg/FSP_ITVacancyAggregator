import type { LucideIcon } from "lucide-react";
import { Monitor, Moon, Sun } from "lucide-react";
import { setTheme, useTheme, type ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";

const OPTIONS: { value: ThemeChoice; label: string; icon: LucideIcon }[] = [
  { value: "system", label: "Авто — как в системе", icon: Monitor },
  { value: "light", label: "Светлая тема", icon: Sun },
  { value: "dark", label: "Тёмная тема", icon: Moon },
];

/** size="lg" — кнопки 44 px для касания (шторка меню на телефоне). */
export function ThemeToggle({ className, size = "default" }: { className?: string; size?: "default" | "lg" }) {
  const current = useTheme();
  return (
    <div
      role="group"
      aria-label="Тема оформления"
      className={cn("inline-flex shrink-0 items-center gap-0.5 rounded-md border border-border-subtle p-0.5", className)}
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          aria-pressed={current === value}
          aria-label={label}
          title={label}
          onClick={() => setTheme(value)}
          className={cn(
            "flex items-center justify-center rounded-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
            size === "lg" ? "size-11 rounded-md" : "size-7",
            current === value ? "bg-primary-tint text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          <Icon className="size-4" aria-hidden />
        </button>
      ))}
    </div>
  );
}
