import type { ReactNode } from "react";
import { Link } from "react-router";
import { legalPath, type LegalSlug } from "@/lib/legal-queries";

/** Ссылка на документ у галочки согласия: в новой вкладке, чтобы не потерять заполненную форму. */
export function DocLink({ slug, children }: { slug: LegalSlug; children: ReactNode }) {
  return (
    <Link
      to={legalPath(slug)}
      target="_blank"
      rel="noopener"
      className="font-medium text-primary underline underline-offset-4"
    >
      {children}
    </Link>
  );
}
