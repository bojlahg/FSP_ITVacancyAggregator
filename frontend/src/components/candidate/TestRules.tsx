import type { TestRule } from "@/lib/test-rules";
import { cn } from "@/lib/utils";

/** Правила полного теста списком: карточки на экране «Перед тестом», компактно — в диалоге старта. */
export function TestRulesList({ rules, compact = false }: { rules: TestRule[]; compact?: boolean }) {
  return (
    <ul className={cn("grid gap-3", !compact && "sm:grid-cols-2")}>
      {rules.map(({ icon: Icon, title, text }) => (
        <li key={title} className={cn("flex gap-3", !compact && "rounded-lg border border-border-subtle p-4")}>
          <Icon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
          <div className="space-y-1">
            <div className="font-mono text-sm font-bold">{title}</div>
            <p className="text-sm text-muted-foreground">{text}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
