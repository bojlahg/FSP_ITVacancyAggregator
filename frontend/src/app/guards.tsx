import { useState, type ReactNode } from "react";
import { Navigate, Outlet, useLocation, useSearchParams } from "react-router";
import { type AuthUser, authStore, homePathFor, postLoginPath, useAuth } from "@/lib/auth";

/** Кабинет роли: аноним → /login?next=<путь>, чужая роль → в свой кабинет. */
export function RequireRole({ role }: { role: AuthUser["role"] }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  if (user.role !== role) {
    return <Navigate to={homePathFor(user.role)} replace />;
  }
  return <Outlet />;
}

/**
 * Вход и регистрация для уже вошедшего — сразу в кабинет. Статус берётся на момент открытия страницы:
 * после успешного входа страница сама уводит пользователя (в `next` или на онбординг), и guard ей не мешает.
 */
export function GuestOnly({ children }: { children: ReactNode }) {
  const [initialUser] = useState(() => authStore.get().user);
  const [searchParams] = useSearchParams();

  if (initialUser) {
    return <Navigate to={postLoginPath(initialUser.role, searchParams.get("next"))} replace />;
  }
  return children;
}
