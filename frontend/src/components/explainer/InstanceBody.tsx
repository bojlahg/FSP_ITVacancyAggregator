import type { components } from "@/api/schema";
import { CodeBlock } from "@/components/CodeBlock";
import { cn } from "@/lib/utils";

type Instance = components["schemas"]["ExplainerInstance"];

/**
 * Текст, код и варианты экземпляра задания — без ключа ответа (его API и не отдаёт).
 * stretch — код занимает свободную высоту карточки: у соседних карточек варианты встают на одну линию.
 */
export function InstanceBody({
  instance,
  kind,
  stretch = false,
}: {
  instance: Instance;
  kind: string;
  stretch?: boolean;
}) {
  return (
    <>
      <p className="text-sm leading-relaxed whitespace-pre-line">{instance.stem}</p>
      {instance.code && (
        <CodeBlock code={instance.code} language={instance.code_language} compact className={cn("mt-3", stretch && "flex-1")} />
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
