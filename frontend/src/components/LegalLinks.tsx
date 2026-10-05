import { Link } from "react-router";
import { LEGAL_LINKS, legalPath } from "@/lib/legal-queries";
import { cn } from "@/lib/utils";

/** Ссылки на политику, согласия и правила рекомендаций (149-ФЗ ст. 10.2-2) — в футере сайта и кабинетов. */
export function LegalLinks({ className }: { className?: string }) {
  return (
    <nav aria-label="Правовая информация" className={cn("flex flex-wrap gap-x-4 gap-y-1", className)}>
      {LEGAL_LINKS.filter((link) => link.slug === "recommendations" || link.slug === "privacy").map((link) => (
        <Link key={link.slug} to={legalPath(link.slug)} className="underline-offset-4 hover:text-foreground hover:underline">
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
