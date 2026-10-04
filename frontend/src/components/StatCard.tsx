import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: LucideIcon;
  className?: string;
}

export function StatCard({ label, value, hint, icon: Icon, className }: StatCardProps) {
  return (
    <Card className={cn("gap-0", className)}>
      <CardContent className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">{label}</span>
          {Icon && <Icon className="size-4 text-primary" aria-hidden />}
        </div>
        <div className="font-mono text-3xl font-extrabold tabular-nums">{value}</div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  );
}
