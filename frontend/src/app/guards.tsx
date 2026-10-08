import { useState, type ReactNode } from "react";
import { Navigate, Outlet, useLocation, useSearchParams } from "react-router";
import { type AuthUser, authStore, homePathFor, postLoginPath, useAuth } from "@/lib/auth";

/** Кабинет роли: аноним → /login?next=<путь>, чужая роль → в свой кабинет. */
export function RequireRole({ role }: { role: AuthUser["role"] }) {
  const { user, signedOut } = useAuth();
  const location = useLocation();

  if (!user) {
    // Вышел сам — на главную; сессия истекла или вход не выполнен — на вход с возвратом
    if (signedOut) return <Navigate to="/" replace />;
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  if (user.role !== role) {
    return <Navigate to={homePathFor(user.role)} replace />;
  }
  // EMAIL_VERIFICATION_REQUIRED (§2): без подтверждённой почты кабинет закрыт — только экран подтверждения
  if (user.email_verification_required && !user.email_verified) {
    return <Navigate to="/verify-email" replace />;
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
