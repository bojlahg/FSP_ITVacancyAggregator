import { useMutation } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";
import { authStore } from "@/lib/auth";

/** Письма о приглашениях и откликах (§8.9): настройка хранится у пользователя, ответ — свежий UserOut. */
export function useUpdateEmailNotifications() {
  return useMutation({
    mutationFn: async (enabled: boolean) => {
      const body: components["schemas"]["NotificationSettings"] = { email_notifications: enabled };
      const { data, error, response } = await api.PUT("/api/v1/me/notifications", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (user) => authStore.setUser(user),
  });
}
