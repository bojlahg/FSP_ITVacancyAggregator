import { Link, Outlet, useLocation } from "react-router";
import { LegalLinks } from "@/components/LegalLinks";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { homePathFor, useAuth } from "@/lib/auth";

export default function PublicLayout() {
  const { pathname } = useLocation();
  const isLanding = pathname === "/";
  const { user } = useAuth();

  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden px-4 py-6 sm:px-8 lg:px-16 lg:py-8">
      <header className="relative z-10 flex flex-wrap items-center justify-between gap-4">
        <Link to="/" aria-label="ITScout — на главную">
          <Logo className="h-8 sm:h-9" />
        </Link>
        <div className="flex items-center gap-4">
          <span className="hidden font-mono text-xs tracking-wide text-muted-foreground md:inline">
            Лидеры цифровой трансформации 2026 · спецтрек ФСП
          </span>
          {pathname !== "/how-it-works" && (
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <Link to="/how-it-works">Как работает тест</Link>
            </Button>
          )}
          {user ? (
            <Button asChild variant={isLanding ? "outline" : "ghost"} size="sm">
              <Link to={homePathFor(user.role)}>В кабинет</Link>
            </Button>
          ) : (
            <>
              {pathname !== "/login" && (
                <Button asChild variant={isLanding ? "outline" : "ghost"} size="sm">
                  <Link to="/login">Войти</Link>
                </Button>
              )}
              {pathname !== "/register" && (
                <Button asChild size="sm">
                  <Link to="/register">Зарегистрироваться</Link>
                </Button>
              )}
            </>
          )}
        </div>
      </header>

      <main className="relative z-10 flex flex-1 flex-col">
        <Outlet />
      </main>

      <footer className="relative z-10 flex flex-wrap justify-between gap-4 pt-8 font-mono text-xs text-muted-foreground">
        <span>itscout.ru</span>
        <LegalLinks />
        <span>© 2026 · Федерация спортивного программирования России</span>
      </footer>
    </div>
  );
}
