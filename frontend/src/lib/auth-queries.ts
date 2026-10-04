import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";
import { authStore } from "@/lib/auth";

type Schemas = components["schemas"];

/** Новая сессия: токен в память, кэш прошлого пользователя — прочь. */
function useStartSession() {
  const queryClient = useQueryClient();
  return (token: Schemas["TokenResponse"]) => {
    queryClient.removeQueries();
    authStore.setSession(token);
  };
}

export function useLogin() {
  const startSession = useStartSession();
  return useMutation({
    mutationFn: async (body: Schemas["LoginRequest"]) => {
      const { data, error, response } = await api.POST("/api/v1/auth/login", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: startSession,
  });
}

export function useDemoLogin() {
  const startSession = useStartSession();
  return useMutation({
    mutationFn: async (persona: Schemas["DemoLoginRequest"]["persona"]) => {
      const { data, error, response } = await api.POST("/api/v1/auth/demo-login", { body: { persona } });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: startSession,
  });
}

export function useRegister() {
  const startSession = useStartSession();
  return useMutation({
    mutationFn: async (body: Schemas["RegisterRequest"]) => {
      const { data, error, response } = await api.POST("/api/v1/auth/register", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: startSession,
  });
}

/**
 * Выход. Store очищается вызывающим после ухода со страницы кабинета (см. CabinetLayout),
 * иначе guard кабинета успеет перекинуть на /login.
 */
export function useLogout() {
  return useMutation({
    mutationFn: async () => {
      // Ошибку сервера игнорируем: локальная сессия всё равно завершается.
      await api.POST("/api/v1/auth/logout").catch(() => undefined);
    },
  });
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: async (token: string) => {
      const { data, error, response } = await api.POST("/api/v1/auth/verify-email", { body: { token } });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => {
      const { user } = authStore.get();
      if (user) authStore.setUser({ ...user, email_verified: true });
    },
  });
}

export function useResendVerification() {
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/v1/auth/resend-verification");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}
