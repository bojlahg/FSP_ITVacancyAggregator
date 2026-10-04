import createClient, { type Middleware } from "openapi-fetch";
import { authStore } from "@/lib/auth";
import type { paths } from "./schema";

const AUTH_PATH_PREFIX = "/api/v1/auth/";

// Пути в OpenAPI уже содержат префикс /api/v1, поэтому baseUrl пустой (тот же origin; в dev — прокси Vite).
export const api = createClient<paths>({
  baseUrl: "",
  credentials: "include",
});

let refreshInFlight: Promise<boolean> | null = null;

/**
 * POST /auth/refresh по httpOnly cookie. Single-flight: параллельные вызовы получают один и тот же промис,
 * поэтому несколько одновременных 401 приводят к одному refresh (cookie ротируется ровно один раз).
 * true — новый access-токен в authStore; false — сессии нет, store очищен.
 */
export function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const { data } = await api.POST("/api/v1/auth/refresh");
      if (data) {
        authStore.setSession(data);
        return true;
      }
    } catch {
      // Сеть недоступна: живую сессию не сбрасываем, следующий 401 попробует снова.
      if (authStore.get().status !== "unknown") return false;
    }
    authStore.clear();
    return false;
  })().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

let bootstrapPromise: Promise<void> | null = null;

/** Тихое восстановление сессии при старте приложения; повторные вызовы (StrictMode) ждут первый. */
export function bootstrapSession(): Promise<void> {
  bootstrapPromise ??= refreshSession().then(() => undefined);
  return bootstrapPromise;
}

function bearerOf(request: Request): string | null {
  const header = request.headers.get("Authorization");
  return header?.startsWith("Bearer ") ? header.slice("Bearer ".length) : null;
}

// Копии исходных запросов для повтора после refresh (тело Request читается только один раз).
const replayable = new Map<string, Request>();

const authMiddleware: Middleware = {
  onRequest({ request, schemaPath, id }) {
    const { accessToken } = authStore.get();
    if (accessToken) {
      request.headers.set("Authorization", `Bearer ${accessToken}`);
    }
    if (accessToken && !schemaPath.startsWith(AUTH_PATH_PREFIX)) {
      replayable.set(id, request.clone());
    }
    return request;
  },
  async onResponse({ response, id, options }) {
    const original = replayable.get(id);
    replayable.delete(id);
    if (response.status !== 401 || !original) return undefined;

    // Если другой запрос уже обновил токен, пока этот был в пути, — просто повторяем с новым.
    const sentToken = bearerOf(original);
    const current = authStore.get().accessToken;
    const refreshed = current && current !== sentToken ? true : await refreshSession();
    const token = authStore.get().accessToken;
    if (!refreshed || !token) return undefined;

    original.headers.set("Authorization", `Bearer ${token}`);
    const doFetch = options.fetch;
    return doFetch(original);
  },
  onError({ id }) {
    replayable.delete(id);
  },
};

api.use(authMiddleware);
