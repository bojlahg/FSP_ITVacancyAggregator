import { Scale } from "lucide-react";
import type { components } from "@/api/schema";

type NeedTextIssue = components["schemas"]["NeedTextIssue"];

/** Запрещённые требования в тексте потребности (возраст, пол, регистрация…): что нашли и почему нельзя. */
export function NeedTextIssues({ issues, className }: { issues: NeedTextIssue[]; className?: string }) {
  if (issues.length === 0) return null;
  const blocking = issues.some((issue) => issue.severity === "block");
  return (
    <div
      role="status"
      className={`grid gap-2 rounded-lg border border-destructive/30 bg-destructive-tint px-3 py-2 text-sm ${className ?? ""}`}
    >
      <div className="flex items-center gap-2 font-medium text-destructive-strong">
        <Scale className="size-4 shrink-0" aria-hidden />
        {blocking
          ? "В тексте есть запрещённые требования — с ними вакансию не опубликовать"
          : "Проверьте формулировки в тексте"}
      </div>
      <ul className="grid gap-1.5">
        {issues.map((issue) => (
          <li key={issue.rule}>
            <span className="font-mono text-xs">«{issue.fragment}»</span>{" "}
            <span className="text-muted-foreground">
              — {issue.label}. {issue.message}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
