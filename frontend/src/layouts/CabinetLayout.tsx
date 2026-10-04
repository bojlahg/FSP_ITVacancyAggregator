import type { LucideIcon } from "lucide-react";
import { LogOut, Menu, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { ProductMark } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { authStore } from "@/lib/auth";
import { cn } from "@/lib/utils";

export interface CabinetNavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Точное совпадение пути для подсветки (для индексного маршрута кабинета). */
  end?: boolean;
}

interface CabinetLayoutProps {
  homePath: string;
  roleLabel: string;
  nav: CabinetNavItem[];
  user: { name: string; caption: string };
}

export function CabinetLayout({ homePath, roleLabel, nav, user }: CabinetLayoutProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();

  const logout = () => {
    // TODO: POST /auth/logout, затем очистка кэша TanStack Query.
    authStore.clear();
    navigate("/");
  };

  const initials = user.name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2);

  return (
    <div className="flex min-h-dvh bg-background">
      {/* Затемнение под мобильным меню */}
      {menuOpen && (
        <button
          type="button"
          aria-label="Закрыть меню"
          className="fixed inset-0 z-30 bg-ink/40 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border-subtle bg-background transition-transform lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0",
          menuOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-start justify-between gap-2 px-5 pt-6 pb-4">
          <Link to={homePath} onClick={() => setMenuOpen(false)}>
            <ProductMark />
          </Link>
          <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={() => setMenuOpen(false)} aria-label="Закрыть меню">
            <X />
          </Button>
        </div>
        <div className="px-5 pb-4">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary px-2.5 py-0.5 font-mono text-xs font-medium text-primary">
            <span className="size-1.5 rounded-full bg-destructive" aria-hidden />
            {roleLabel}
          </span>
        </div>

        <nav className="flex-1 overflow-y-auto px-3" aria-label="Разделы кабинета">
          <ul className="space-y-0.5">
            {nav.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  onClick={() => setMenuOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-primary-tint text-primary"
                        : "text-foreground hover:bg-muted hover:text-foreground",
                    )
                  }
                >
                  <Icon className="size-4 shrink-0" aria-hidden />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex items-center gap-3 border-t border-border-subtle px-4 py-4">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink font-mono text-sm font-bold text-ink-foreground">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">{user.name}</div>
            <div className="truncate text-xs text-muted-foreground">{user.caption}</div>
          </div>
          <Button variant="ghost" size="icon-sm" onClick={logout} aria-label="Выйти" title="Выйти">
            <LogOut />
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-border-subtle bg-background/95 px-4 py-3 backdrop-blur lg:hidden">
          <Button variant="ghost" size="icon-sm" onClick={() => setMenuOpen(true)} aria-label="Открыть меню">
            <Menu />
          </Button>
          <Link to={homePath} className="font-mono text-base font-extrabold text-primary">
            IT<span className="text-foreground">Scout</span>
          </Link>
          <span className="w-8" aria-hidden />
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
