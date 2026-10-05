import type { ExplainerScenario } from "@/lib/explainer-queries";

// Цвета — только токены темы (index.css): сценарии различаются и цветом, и штрихом линии.
export const SCENARIO_STYLE: Record<ExplainerScenario["scenario"], { color: string; dash?: string; dot: string }> = {
  below: { color: "var(--chart-3)", dash: "6 4", dot: "bg-chart-3" },
  at: { color: "var(--chart-1)", dot: "bg-chart-1" },
  above: { color: "var(--chart-4)", dash: "2 3", dot: "bg-chart-4" },
};
