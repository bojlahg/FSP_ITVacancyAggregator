import { useSyncExternalStore } from "react";
import type { components } from "@/api/schema";

export type AuthUser = components["schemas"]["UserOut"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type UserRole = components["schemas"]["RegisterRequest"]["role"];

export type AuthStatus = "unknown" | "authenticated" | "anonymous";

export interface AuthState {
  accessToken: string | null;
  user: AuthUser | null;
  /** unknown — сессия ещё не восстановлена через POST /auth/refresh при старте. */
  status: AuthStatus;
}

// Access-токен живёт только в памяти (не в localStorage); refresh-токен — httpOnly cookie от backend.
let state: AuthState = { accessToken: null, user: null, status: "unknown" };
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export const authStore = {
  get(): AuthState {
    return state;
  },
  setSession(token: TokenResponse) {
    state = { accessToken: token.access_token, user: token.user, status: "authenticated" };
    emit();
  },
  setUser(user: AuthUser) {
    state = { ...state, user };
    emit();
  },
  clear() {
    state = { accessToken: null, user: null, status: "anonymous" };
    emit();
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

export function useAuth(): AuthState {
  return useSyncExternalStore(authStore.subscribe, authStore.get, authStore.get);
}

/** Главная страница кабинета для роли. У admin своего кабинета нет. */
export function homePathFor(role: AuthUser["role"]): string {
  if (role === "candidate") return "/candidate";
  if (role === "employer") return "/employer";
  return "/";
}

/**
 * Куда вести после входа: `next` из адреса, если это внутренний путь кабинета этой роли,
 * иначе — главная кабинета. Защищает от open redirect на чужой домен.
 */
export function postLoginPath(role: AuthUser["role"], next: string | null): string {
  const home = homePathFor(role);
  if (next && next.startsWith("/") && !next.startsWith("//") && home !== "/") {
    if (next === home || next.startsWith(`${home}/`) || next.startsWith(`${home}?`)) return next;
  }
  return home;
}
