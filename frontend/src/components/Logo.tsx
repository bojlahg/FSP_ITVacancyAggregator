import logoDark from "@/assets/brand/logo_01.svg";
import logoLight from "@/assets/brand/logo_01w.svg";
import { cn } from "@/lib/utils";

interface LogoProps {
  /** auto — по теме сайта (по умолчанию); light — тёмный текст для светлого фона, dark — светлый для тёмного. */
  tone?: "auto" | "light" | "dark";
  className?: string;
}

const ALT = "Федерация спортивного программирования России";

export function Logo({ tone = "auto", className }: LogoProps) {
  if (tone !== "auto") {
    return <img src={tone === "light" ? logoLight : logoDark} alt={ALT} className={cn("h-8 w-auto", className)} />;
  }
  return (
    <>
      <img src={logoLight} alt={ALT} className={cn("h-8 w-auto dark:hidden", className)} />
      <img src={logoDark} alt={ALT} className={cn("hidden h-8 w-auto dark:inline", className)} />
    </>
  );
}

/** Логотип ФСП + название продукта для шапок кабинетов. */
export function ProductMark({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <Logo className="h-6" />
      <span className="font-mono text-lg leading-none font-extrabold tracking-tight text-primary">
        IT<span className="text-foreground">Scout</span>
      </span>
    </div>
  );
}
