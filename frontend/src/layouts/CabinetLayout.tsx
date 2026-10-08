import type { LucideIcon } from "lucide-react";
import { Bug, Loader2, LogOut, Menu, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
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
  const closeRef = useRef<HTMLButtonElement>(null);
  const openRef = useRef<HTMLButtonElement>(null);
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

  // Шторка на телефоне: фокус на «Закрыть», Escape закрывает, фокус возвращается к кнопке меню
  useEffect(() => {
    if (!menuOpen) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    const opener = openRef.current;
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, [menuOpen]);

  const email = user?.email ?? "";
  const initials = email.slice(0, 2).toUpperCase();
  // Во время теста (handle.focus) меню и ссылки кабинета скрыты: один промах мышью уводит со страницы
  const focus = useMatches().some((match) => (match.handle as RouteHandle | undefined)?.focus);

  if (focus) {
    return (
      <div className="flex min-h-dvh flex-col bg-background">
        <header className="sticky top-0 z-20 border-b border-border-subtle bg-background/95 backdrop-blur">
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-10">
            {/* На телефоне в строку не помещается и наезжает на переключатель темы */}
            <ProductMark className="min-w-0 sm:flex-row sm:items-center sm:gap-3" />
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
          className="fixed inset-0 z-30 bg-ink/60 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}

      {/* На телефоне — шторка слева поверх страницы, закрытая убрана из дерева доступности; с lg — колонка */}
      <aside
        role={menuOpen ? "dialog" : undefined}
        aria-modal={menuOpen || undefined}
        aria-label={menuOpen ? "Меню кабинета" : undefined}
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-76 max-w-[85vw] flex-col overflow-hidden rounded-r-2xl border-r border-border-subtle bg-card transition-[transform,visibility] lg:visible lg:sticky lg:top-0 lg:h-dvh lg:w-64 lg:max-w-none lg:translate-x-0 lg:rounded-none lg:bg-background",
          menuOpen ? "visible translate-x-0" : "invisible -translate-x-full",
        )}
      >
        <div className="flex items-start justify-between gap-2 py-1.5 pr-1.5 pl-5 lg:px-5 lg:pt-6 lg:pb-4">
          <Link to={homePath} onClick={() => setMenuOpen(false)} className="max-lg:pt-3">
            <ProductMark />
          </Link>
          <Button
            ref={closeRef}
            variant="ghost"
            size="icon"
            className="size-11 lg:hidden"
            onClick={() => setMenuOpen(false)}
            aria-label="Закрыть меню"
          >
            <X className="size-5" />
          </Button>
        </div>
        <div className="border-b border-border-subtle px-5 pb-3 lg:border-b-0 lg:pb-4">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary px-2.5 py-0.5 font-mono text-xs font-medium text-primary">
            <span className="size-1.5 rounded-full bg-destructive" aria-hidden />
            {roleLabel}
          </span>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-2 lg:px-3 lg:pt-0 lg:pb-3" aria-label="Разделы кабинета">
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
                          "flex min-h-12 items-center gap-3 rounded-md px-3 py-2 text-[15px] font-medium transition-colors lg:min-h-0 lg:text-sm",
                          isActive
                            ? "bg-primary-tint text-primary"
                            : "text-foreground hover:bg-muted hover:text-foreground",
                        )
                      }
                    >
                      <Icon className="size-[18px] shrink-0 lg:size-4" aria-hidden />
                      {label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="space-y-2 border-t border-border-subtle px-4 py-3 lg:py-4">
          <div className="flex items-center gap-3">
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
              className="max-lg:size-11"
              onClick={() => void onLogout()}
              disabled={logout.isPending}
              aria-label="Выйти"
              title="Выйти"
            >
              {logout.isPending ? <Loader2 className="animate-spin" /> : <LogOut />}
            </Button>
          </div>
          <div className="flex items-center justify-between gap-2 lg:hidden">
            <span className="font-mono text-xs font-medium tracking-wider text-muted-foreground uppercase">Тема</span>
            <ThemeToggle size="lg" />
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-border-subtle bg-background/95 px-1.5 backdrop-blur lg:hidden">
          <Button
            ref={openRef}
            variant="ghost"
            size="icon"
            className="size-11"
            onClick={() => setMenuOpen(true)}
            aria-label="Открыть меню"
            aria-expanded={menuOpen}
          >
            <Menu className="size-5" />
          </Button>
          <Link to={homePath} className="font-mono text-base font-extrabold text-primary">
            IT<span className="text-foreground">Scout</span>
          </Link>
          <ThemeToggle className="mr-2.5" />
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
