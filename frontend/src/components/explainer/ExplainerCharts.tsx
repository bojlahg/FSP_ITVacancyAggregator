import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { SCENARIO_STYLE } from "@/components/explainer/scenario-style";
import type { ExplainerGrade, ExplainerInstances, ExplainerScenario } from "@/lib/explainer-queries";


const AXIS_TICK = { fill: "var(--muted-foreground)", fontSize: 11, fontFamily: "var(--font-mono)" };
const THETA_TICKS = [-4, -3, -2, -1, 0, 1, 2, 3, 4];

function formatTheta(value: number): string {
  return value.toLocaleString("ru-RU", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function CutLines({ grades, active }: { grades: ExplainerGrade[]; active?: string }) {
  return grades.map((grade) => (
    <ReferenceLine
      key={grade.grade}
      x={grade.cut}
      stroke={grade.grade === active ? "var(--destructive)" : "var(--border)"}
      strokeWidth={grade.grade === active ? 1.5 : 1}
      strokeDasharray={grade.grade === active ? undefined : "3 3"}
      label={{
        // Подписи порогов на узком графике сливаются: полное имя только у выбранного, у остальных — буква
        value: grade.grade === active ? grade.name : grade.name.slice(0, 1),
        position: grade.grade === active ? "top" : "insideTopLeft",
        fill: grade.grade === active ? "var(--foreground)" : "var(--muted-foreground)",
        fontSize: 10,
        fontFamily: "var(--font-mono)",
      }}
    />
  ));
}

type InfoRow = { theta: number } & Partial<Record<ExplainerScenario["scenario"], number>> &
  Partial<Record<`se_${ExplainerScenario["scenario"]}`, number>>;

function InformationTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as InfoRow;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-mono font-bold">θ = {formatTheta(Number(label))}</div>
      <ul className="grid gap-1">
        {payload.map((entry) => {
          const key = entry.dataKey as ExplainerScenario["scenario"];
          return (
            <li key={key} className="flex items-center gap-2">
              <span className={`size-2 shrink-0 rounded-full ${SCENARIO_STYLE[key].dot}`} aria-hidden />
              <span className="text-muted-foreground">{entry.name}</span>
              <span className="ml-auto pl-3 font-mono tabular-nums">
                I = {Number(entry.value).toFixed(1)} · SE = {row[`se_${key}`]?.toFixed(2)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Средняя информационная функция MST-теста для трёх симулированных кандидатов. */
export function InformationChart({
  scenarios,
  grades,
  activeGrade,
}: {
  scenarios: ExplainerScenario[];
  grades: ExplainerGrade[];
  activeGrade: string;
}) {
  const rows: InfoRow[] = (scenarios[0]?.information ?? []).map((point, index) => {
    const row: InfoRow = { theta: point.theta };
    for (const scenario of scenarios) {
      const value = scenario.information[index];
      row[scenario.scenario] = value?.information;
      row[`se_${scenario.scenario}`] = value?.se;
    }
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} margin={{ top: 18, right: 8, bottom: 4, left: -16 }}>
        <CartesianGrid vertical={false} stroke="var(--border-subtle)" />
        <XAxis
          dataKey="theta"
          type="number"
          domain={[-4, 4]}
          ticks={THETA_TICKS}
          tick={AXIS_TICK}
          tickLine={false}
          axisLine={{ stroke: "var(--border)" }}
        />
        <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={44} allowDecimals={false} />
        <CutLines grades={grades} active={activeGrade} />
        <Tooltip content={InformationTooltip} cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "2 2" }} />
        {scenarios.map((scenario) => (
          <Line
            key={scenario.scenario}
            dataKey={scenario.scenario}
            name={scenario.label}
            type="monotone"
            stroke={SCENARIO_STYLE[scenario.scenario].color}
            strokeDasharray={SCENARIO_STYLE[scenario.scenario].dash}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--background)" }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function IccTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 font-mono text-xs shadow-md">
      θ = {formatTheta(Number(label))} · P = {Math.round(Number(payload[0]?.value) * 100)}%
    </div>
  );
}

/** Характеристическая кривая шаблона: вероятность верного ответа по 3PL. */
export function IccChart({ icc, grades }: { icc: ExplainerInstances["icc"]; grades: ExplainerGrade[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={icc} margin={{ top: 18, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} stroke="var(--border-subtle)" />
        <XAxis
          dataKey="theta"
          type="number"
          domain={[-4, 4]}
          ticks={THETA_TICKS}
          tick={AXIS_TICK}
          tickLine={false}
          axisLine={{ stroke: "var(--border)" }}
        />
        <YAxis
          domain={[0, 1]}
          ticks={[0, 0.5, 1]}
          tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
          tick={AXIS_TICK}
          tickLine={false}
          axisLine={false}
          width={48}
        />
        <CutLines grades={grades} />
        <Tooltip content={IccTooltip} cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "2 2" }} />
        <Line
          dataKey="value"
          type="monotone"
          stroke="var(--chart-1)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--background)" }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
