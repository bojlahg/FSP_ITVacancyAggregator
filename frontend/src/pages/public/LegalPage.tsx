import { FileText } from "lucide-react";
import { Link, useParams } from "react-router";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError } from "@/lib/api-error";
import { formatDate } from "@/lib/format";
import { isLegalSlug, LEGAL_LINKS, legalPath, type LegalDocument, useLegalDocument } from "@/lib/legal-queries";
import { cn } from "@/lib/utils";

/** Редакция хранится как дата ISO (POLICY_VERSION) — показываем её по-русски. */
function edition(version: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(version) ? `от ${formatDate(version)}` : version;
}

/** Политика, согласия и правила рекомендаций (docs/implementation.md §13.1): тексты из backend/content/legal. */
export default function LegalPage() {
  const { slug } = useParams();
  const known = isLegalSlug(slug);
  const doc = useLegalDocument(known ? slug : undefined);

  return (
    <div className="mx-auto grid w-full max-w-5xl gap-8 py-8 lg:grid-cols-[1fr_15rem] lg:py-12">
      <article className="min-w-0">
        {!known ? (
          <EmptyState
            icon={FileText}
            title="Документ не найден"
            description="Возможно, ссылка устарела. Все документы — в списке рядом."
          />
        ) : doc.isPending ? (
          <div className="space-y-4" role="status" aria-busy="true" aria-label="Загрузка">
            <Skeleton className="h-9 w-3/4" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : doc.isError ? (
          <ErrorState description={apiError(doc.error).message} onRetry={() => void doc.refetch()} />
        ) : (
          <LegalBody doc={doc.data} />
        )}
      </article>

      <nav aria-label="Документы" className="lg:sticky lg:top-8 lg:self-start">
        <h2 className="mb-3 font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">Документы</h2>
        <ul className="grid gap-1">
          {LEGAL_LINKS.map((link) => (
            <li key={link.slug}>
              <Link
                to={legalPath(link.slug)}
                aria-current={link.slug === slug ? "page" : undefined}
                className={cn(
                  "block rounded-md px-3 py-2 text-sm transition-colors",
                  link.slug === slug ? "bg-primary-tint font-medium text-primary" : "hover:bg-muted",
                )}
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
        <Button asChild variant="ghost" size="sm" className="mt-3">
          <Link to="/how-it-works">Как работает тест</Link>
        </Button>
      </nav>
    </div>
  );
}

function LegalBody({ doc }: { doc: LegalDocument }) {
  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <h1 className="text-2xl font-extrabold md:text-3xl">{doc.title}</h1>
        <Badge variant="muted">Редакция {edition(doc.version)}</Badge>
        <p className="max-w-3xl leading-relaxed text-muted-foreground">{doc.summary}</p>
      </header>

      {doc.sections.map((section) => (
        <section key={section.heading} className="space-y-3">
          <h2 className="font-mono text-lg font-bold">{section.heading}</h2>
          {(section.paragraphs ?? []).map((text) => (
            <p key={text} className="leading-relaxed">
              {text}
            </p>
          ))}
          {section.items && section.items.length > 0 && (
            <ul className="list-disc space-y-1.5 pl-5 leading-relaxed marker:text-primary">
              {section.items.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          )}
          {section.table && <LegalTableView table={section.table} />}
        </section>
      ))}
    </div>
  );
}

/** Таблица карточками: на ширине телефона читается без горизонтальной прокрутки. */
function LegalTableView({ table }: { table: NonNullable<LegalDocument["sections"][number]["table"]> }) {
  const [nameColumn, valueColumn, ...restColumns] = table.columns;
  return (
    <ul className="grid gap-2" aria-label={table.columns.join(", ")}>
      {table.rows.map(([name, value, ...rest]) => (
        <li key={name} className="rounded-lg border border-border-subtle p-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-medium">
              <span className="sr-only">{nameColumn}: </span>
              {name}
            </span>
            <span className="font-mono text-sm font-bold text-primary tabular-nums">
              <span className="sr-only">{valueColumn}: </span>
              {value}
            </span>
          </div>
          {rest.map((text, index) => (
            <p key={index} className="mt-1 text-sm leading-relaxed text-muted-foreground">
              <span className="sr-only">{restColumns[index]}: </span>
              {text}
            </p>
          ))}
        </li>
      ))}
    </ul>
  );
}
