import type { components } from "@/api/schema";

type Instance = components["schemas"]["ExplainerInstance"];

/** Текст, код и варианты экземпляра задания — без ключа ответа (его API и не отдаёт). */
export function InstanceBody({ instance, kind }: { instance: Instance; kind: string }) {
  return (
    <>
      <p className="text-sm leading-relaxed whitespace-pre-line">{instance.stem}</p>
      {instance.code && (
        <div className="mt-3 overflow-hidden rounded-lg bg-ink text-ink-foreground">
          {instance.code_language && (
            <div className="border-b border-ink-foreground/15 px-3 py-1 font-mono text-xs opacity-70">
              {instance.code_language}
            </div>
          )}
          <pre className="overflow-x-auto p-3 font-mono text-xs leading-relaxed">
            <code>{instance.code}</code>
          </pre>
        </div>
      )}
      {instance.options.length > 0 ? (
        <ul className="mt-3 grid gap-1.5 text-sm">
          {instance.options.map((option) => (
            <li key={option.id} className="flex gap-2 rounded-md bg-secondary/60 px-2.5 py-1.5">
              <span className="font-mono text-xs leading-5 text-muted-foreground">{option.id})</span>
              <span className="min-w-0 break-words">{option.text}</span>
            </li>
          ))}
        </ul>
      ) : (
        kind === "numeric" && (
          <div className="mt-3 rounded-md border border-dashed px-3 py-2 font-mono text-xs text-muted-foreground">
            Ответ — число
          </div>
        )
      )}
    </>
  );
}
