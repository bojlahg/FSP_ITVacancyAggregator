import type { LucideIcon } from "lucide-react";
import { Bug, Loader2, LogOut, Menu, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, NavLink, Outlet, useMatches, useNavigate } from "react-router";
import type { RouteHandle } from "@/app/DocumentTitle";
import { LegalLinks } from "@/components/LegalLinks";
import { ProductMark } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { authStore, useAuth } from "@/lib/auth";
import { useLogout } from "@/lib/auth-queries";
import { useDebugStatus } from "@/lib/debug-queries";
import { cn } from "@/lib/utils";

export interface CabinetNavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Точное совпадение пути для подсветки (для индексного маршрута кабинета). */
  end?: boolean;
  /** Подпись группы: соседние пункты с одной подписью выводятся блоком под ней. */
  group?: string;
}

interface NavSection {
  group?: string;
  items: CabinetNavItem[];
}

/** Соседние пункты с одинаковой группой — одна секция меню. */
function navSections(nav: CabinetNavItem[]): NavSection[] {
  const sections: NavSection[] = [];
  for (const item of nav) {
    const last = sections.at(-1);
    if (last && last.group === item.group) last.items.push(item);
    else sections.push({ group: item.group, items: [item] });
  }
  return sections;
}

interface CabinetLayoutProps {
  homePath: string;
  roleLabel: string;
  nav: CabinetNavItem[];
  /** Пункт «Отладка» — только если на сервере включён DEBUG_TOOLS. */
  debugLink?: boolean;
}

export function CabinetLayout({ homePath, roleLabel, nav: baseNav, debugLink = true }: CabinetLayoutProps) {
  const debug = useDebugStatus();
  const nav = debugLink && debug.data ? [...baseNav, { to: `${homePath}/debug`, label: "Отладка", icon: Bug }] : baseNav;
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const logout = useLogout();

  const onLogout = async () => {
    await logout.mutateAsync();
    // Сначала уходим из кабинета, потом чистим сессию — иначе guard кабинета отправит на /login.
    await navigate("/", { replace: true });
    authStore.clear();
    queryClient.removeQueries();
  };

  const email = user?.email ?? "";
  const initials = email.slice(0, 2).toUpperCase();
  // Во время теста (handle.focus) меню и ссылки кабинета скрыты: один промах мышью уводит со страницы
  const focus = useMatches().some((match) => (match.handle as RouteHandle | undefined)?.focus);

  if (focus) {
    return (
      <div className="flex min-h-dvh flex-col bg-background">
        <header className="sticky top-0 z-20 border-b border-border-subtle bg-background/95 backdrop-blur">
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-10">
            <ProductMark className="flex-row items-center gap-3" />
            <ThemeToggle />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-10">
          <Outlet />
        </main>
      </div>
    );
  }

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

        <nav className="flex-1 overflow-y-auto px-3 pb-3" aria-label="Разделы кабинета">
          {navSections(nav).map((section, index) => (
            <div
              key={section.group ?? `section-${index}`}
              className={cn(index > 0 && "mt-3 border-t border-border-subtle pt-3")}
            >
              {section.group && (
                <div
                  id={`cabinet-nav-group-${index}`}
                  className="px-3 pb-1 font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase"
                >
                  {section.group}
                </div>
              )}
              <ul className="space-y-0.5" aria-labelledby={section.group ? `cabinet-nav-group-${index}` : undefined}>
                {section.items.map(({ to, label, icon: Icon, end }) => (
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
            </div>
          ))}
        </nav>

        <div className="flex items-center gap-3 border-t border-border-subtle px-4 py-4">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink font-mono text-sm font-bold text-ink-foreground">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium" title={email}>
              {email}
            </div>
            <div className="truncate text-xs text-muted-foreground">{roleLabel}</div>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => void onLogout()}
            disabled={logout.isPending}
            aria-label="Выйти"
            title="Выйти"
          >
            {logout.isPending ? <Loader2 className="animate-spin" /> : <LogOut />}
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
          <ThemeToggle />
        </header>
        <div className="mx-auto hidden w-full max-w-7xl justify-end px-10 pt-4 lg:flex">
          <ThemeToggle />
        </div>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:pt-4 lg:pb-10">
          <Outlet />
        </main>
        <footer className="mx-auto w-full max-w-7xl px-4 pb-6 font-mono text-xs text-muted-foreground sm:px-6 lg:px-10">
          <LegalLinks />
        </footer>
      </div>
    </div>
  );
}
