import { AlertTriangle, Check, HelpCircle } from "lucide-react";
import type { components } from "@/api/schema";
import { cn } from "@/lib/utils";

type SalaryMarket = components["schemas"]["SalaryMarketCheck"];

const STYLE: Record<SalaryMarket["verdict"], { Icon: typeof Check; className: string }> = {
  ok: { Icon: Check, className: "bg-primary-tint text-foreground [&>svg]:text-primary" },
  below_market: { Icon: AlertTriangle, className: "bg-destructive-tint text-foreground [&>svg]:text-destructive" },
  suspicious_high: { Icon: AlertTriangle, className: "bg-destructive-tint text-foreground [&>svg]:text-destructive" },
  unknown: { Icon: HelpCircle, className: "bg-muted text-muted-foreground" },
};

/** Вилка против ожиданий категории (§24): в рынке, ниже рынка или подозрительно выше. */
export function SalaryMarketNote({ market, className }: { market: SalaryMarket; className?: string }) {
  const { Icon, className: tone } = STYLE[market.verdict];
  return (
    <p className={cn("flex items-start gap-2 rounded-md px-3 py-2 text-sm leading-snug", tone, className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{market.message}</span>
    </p>
  );
}

/** Короткая пометка рядом с вилкой — только когда есть о чём предупредить. */
export function SalaryMarketBadge({ market }: { market: SalaryMarket }) {
  if (market.verdict !== "below_market" && market.verdict !== "suspicious_high") return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-destructive-tint px-2 py-0.5 font-mono text-xs text-foreground">
      <AlertTriangle className="size-3 text-destructive" aria-hidden />
      {market.verdict === "below_market" ? "ниже рынка" : "выше рынка — уточните"}
    </span>
  );
}
