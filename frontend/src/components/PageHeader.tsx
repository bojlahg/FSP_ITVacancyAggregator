import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  /** Надстрочник над заголовком: раздел, хлебные крошки, бейдж. */
  eyebrow?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({ title, description, eyebrow, actions, className }: PageHeaderProps) {
  return (
    <header className={cn("flex flex-col gap-4 pb-6 md:flex-row md:items-end md:justify-between", className)}>
      <div className="min-w-0 flex-1 space-y-2">
        {eyebrow && <div className="font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">{eyebrow}</div>}
        <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">{title}</h1>
        {description && <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground md:text-base">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 md:max-w-[55%] md:shrink-0 md:justify-end">{actions}</div>}
    </header>
  );
}
