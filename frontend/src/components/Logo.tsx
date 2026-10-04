import logoDark from "@/assets/brand/logo_01.svg";
import logoLight from "@/assets/brand/logo_01w.svg";
import { cn } from "@/lib/utils";

interface LogoProps {
  /** light — тёмный текст для светлого фона (по умолчанию), dark — светлый текст для тёмного фона. */
  tone?: "light" | "dark";
  className?: string;
}

export function Logo({ tone = "light", className }: LogoProps) {
  return (
    <img
      src={tone === "light" ? logoLight : logoDark}
      alt="Федерация спортивного программирования России"
      className={cn("h-8 w-auto", className)}
    />
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
