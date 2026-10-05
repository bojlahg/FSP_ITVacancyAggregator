import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { toApiError } from "@/lib/api-error";
import { useAuth } from "@/lib/auth";

export type DebugAction = "reset_cooldowns" | "reset_test" | "test_email" | "reseed";

/** Статус отладочного раздела: null — раздел выключен (DEBUG_TOOLS не задан, сервер отвечает 404). */
export function useDebugStatus() {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["debug", "status", user?.id],
    enabled: !!user,
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/debug/status");
      if (response.status === 404) return null;
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

const PATHS = {
  reset_cooldowns: "/api/v1/debug/reset-cooldowns",
  reset_test: "/api/v1/debug/reset-test",
  test_email: "/api/v1/debug/test-email",
  reseed: "/api/v1/debug/reseed",
} as const;

export function useDebugAction() {
  return useMutation({
    mutationFn: async (action: DebugAction) => {
      const { data, error, response } = await api.POST(PATHS[action]);
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}
