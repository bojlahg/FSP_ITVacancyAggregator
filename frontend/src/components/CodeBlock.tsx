import { cn } from "@/lib/utils";

const TAB_WIDTH = 4;

/** Ширина ведущего отступа строки в символах (таб — TAB_WIDTH). */
function indentWidth(line: string): number {
  const lead = /^[ \t]*/.exec(line)?.[0] ?? "";
  return [...lead].reduce((width, char) => width + (char === "\t" ? TAB_WIDTH : 1), 0);
}

/**
 * Код к заданию. Длинные строки переносятся, а не уезжают вбок: на телефоне идёт таймер,
 * и строку с данными нельзя заставлять прокручивать. Перенесённая часть сдвинута на 2 символа
 * глубже отступа своей строки — структура Python и вложенность читаются как в исходнике.
 */
export function CodeBlock({
  code,
  language,
  compact = false,
  className,
}: {
  code: string;
  language?: string | null;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("overflow-hidden rounded-lg bg-ink text-ink-foreground", className)}>
      {language && (
        <div
          className={cn(
            "border-b border-ink-foreground/15 font-mono text-xs opacity-70",
            compact ? "px-3 py-1" : "px-4 py-1.5",
          )}
        >
          {language}
        </div>
      )}
      <pre
        tabIndex={0}
        role="region"
        aria-label="Код к заданию"
        className={cn(
          "font-mono leading-relaxed whitespace-pre-wrap wrap-anywhere [tab-size:4] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          compact ? "p-3 text-xs" : "p-4 text-sm",
        )}
      >
        <code>
          {code.split("\n").map((line, index) => {
            const hang = indentWidth(line) + 2;
            return (
              <span key={index} className="block" style={{ paddingLeft: `${hang}ch`, textIndent: `-${hang}ch` }}>
                {line || " "}
              </span>
            );
          })}
        </code>
      </pre>
    </div>
  );
}
