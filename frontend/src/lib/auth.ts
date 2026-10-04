import { useSyncExternalStore } from "react";

export type UserRole = "candidate" | "employer";

export interface AuthState {
  accessToken: string | null;
  role: UserRole | null;
}

// Access-токен живёт только в памяти (не в localStorage).
// TODO: refresh-токен — httpOnly cookie от backend; при 401 вызывать POST /auth/refresh и повторять запрос.
let state: AuthState = { accessToken: null, role: null };
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export const authStore = {
  get(): AuthState {
    return state;
  },
  set(next: Partial<AuthState>) {
    state = { ...state, ...next };
    emit();
  },
  clear() {
    state = { accessToken: null, role: null };
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
