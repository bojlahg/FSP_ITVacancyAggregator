import { CalendarCheck, ExternalLink, Gauge, ListChecks, ScanEye, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import type { components } from "@/api/schema";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, plural, toPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

type Schemas = components["schemas"];
export type GradeConfidence = Schemas["GradeConfidence"];
export type GradeEvidence = Schemas["GradeEvidence"];
type IntegritySignals = Schemas["IntegritySignals"];

const LEVEL_BADGE: Record<string, "soft" | "outline" | "muted"> = { high: "soft", medium: "outline", low: "muted" };

/** Уверенность в грейде (§10.4.1): фраза, уровень и полоса вероятностей грейдов. На грейд не влияет. */
export function GradeConfidenceBar({ confidence, compact = false }: { confidence: GradeConfidence; compact?: boolean }) {
  const gradeIndex = confidence.bands.findIndex((band) => band.grade === confidence.grade);
  const visible = confidence.bands.filter((band) => toPercent(band.probability) >= 1);
  const summary = visible.map((band) => `${band.label} ${toPercent(band.probability)}%`).join(", ");

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Gauge className="size-4 shrink-0 text-primary" aria-hidden />
        <span className="font-medium">{confidence.text}</span>
        <Badge variant={LEVEL_BADGE[confidence.level] ?? "muted"}>{confidence.level_label} уверенность</Badge>
      </div>
      <div
        role="img"
        aria-label={`Вероятности грейдов: ${summary}`}
        className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted"
      >
        {confidence.bands.map((band, index) => (
          <div
            key={band.label}
            className={cn(
              "h-full",
              index === gradeIndex ? "bg-primary" : index > gradeIndex ? "bg-primary/45" : "bg-muted-foreground/35",
            )}
            style={{ width: `${band.probability * 100}%` }}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-xs text-muted-foreground tabular-nums" aria-hidden>
        {visible.map((band) => (
          <li key={band.label} className={cn(band.grade === confidence.grade && "font-bold text-foreground")}>
            {band.label} {toPercent(band.probability)}%
          </li>
        ))}
      </ul>
      {!compact && <p className="text-xs text-muted-foreground">{confidence.note}</p>}
    </div>
  );
}

function Fact({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <li className="flex gap-2">
      <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
      <span>{children}</span>
    </li>
  );
}

/**
 * Блок «Почему этому грейду можно верить» (§10.4.1): дата и параметры теста, уверенность, сигналы честности.
 * Кандидату — короткая версия без сигналов (они — пометка для работодателя).
 */
export function GradeEvidenceCard({
  evidence,
  integrity = null,
  audience,
}: {
  evidence: GradeEvidence;
  integrity?: IntegritySignals | null;
  audience: "employer" | "candidate";
}) {
  const items = `${evidence.items_scored} ${plural(evidence.items_scored, ["задание", "задания", "заданий"])}`;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" aria-hidden /> Почему этому грейду можно верить
        </CardTitle>
        <CardDescription>
          {audience === "employer"
            ? "Грейд присвоен по тесту на сервере ITScout — не по резюме и не языковой моделью"
            : "Что видит работодатель рядом с вашей категорией"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <GradeConfidenceBar confidence={evidence.confidence} compact={audience === "employer"} />
        <ul className="grid gap-2 sm:grid-cols-2">
          <Fact icon={CalendarCheck}>
            {evidence.tested_at ? `Тест пройден ${formatDate(evidence.tested_at)}` : "Дата теста неизвестна"}, результат
            действителен до {formatDate(evidence.valid_until)}
          </Fact>
          <Fact icon={ListChecks}>
            {evidence.adaptive ? "Адаптивный тест" : "Тест"}
            {evidence.short_mode ? " (сокращённый демо-режим)" : ""}: {items} с оценкой, задания подбирались по
            ответам;{" "}
            <span className="font-mono whitespace-nowrap tabular-nums">
              θ = {evidence.theta.toFixed(2)} ± {evidence.se.toFixed(2)}
            </span>
          </Fact>
          {audience === "employer" && integrity && (
            <Fact icon={ScanEye}>
              {integrity.flagged ? `${integrity.note} Подробности — в блоке ниже.` : integrity.note}
            </Fact>
          )}
        </ul>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <Link to={evidence.how_it_works_path} className="text-primary hover:underline">
            Как устроен тест
          </Link>
          <a
            href={evidence.validation_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            Отчёт валидации <ExternalLink className="size-3.5" aria-hidden />
          </a>
        </div>
      </CardContent>
    </Card>
  );
}
