import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";

export type FspProfile = components["schemas"]["FspProfileOut"];

export const fspKeys = {
  mine: ["candidates", "me", "fsp"] as const,
};

export function useMyFsp() {
  return useQuery({
    queryKey: fspKeys.mine,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/fsp");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useLinkFspManual() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components["schemas"]["FspLinkRequest"]) => {
      const { data, error, response } = await api.POST("/api/v1/candidates/me/fsp/link", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (profile) => queryClient.setQueryData(fspKeys.mine, profile),
  });
}

/** Старт входа через ФСП ID: backend ставит cookie флоу и отдаёт адрес IdP, браузер уходит туда. */
export function useStartFspOidc() {
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/fsp/oidc/start", {
        params: { query: { consent: true } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: ({ authorization_url }) => window.location.assign(authorization_url),
  });
}

export function useUnlinkFsp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.DELETE("/api/v1/candidates/me/fsp");
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: fspKeys.mine }),
  });
}

/** Коды из редиректа /fsp/oidc/callback (`?fsp_oidc=error&reason=`) → текст для кандидата. */
export function fspOidcErrorMessage(reason: string | null): string {
  switch (reason) {
    case "fsp_oidc_state_invalid":
      return "Сессия входа через ФСП ID устарела. Попробуйте ещё раз.";
    case "fsp_oidc_denied":
      return "Вход через ФСП ID отменён.";
    case "fsp_oidc_code_rejected":
    case "fsp_oidc_token_invalid":
      return "ФСП ID не подтвердил вход. Попробуйте ещё раз.";
    case "fsp_oidc_no_fsp_id":
      return "В учётной записи ФСП ID нет номера участника.";
    case "fsp_id_taken":
      return "Этот ФСП ID уже привязан к другому профилю.";
    case "fsp_participant_not_found":
      return "Участник с этим ФСП ID не найден в реестре ФСП.";
    case "fsp_idp_unavailable":
    case "fsp_registry_unavailable":
      return "Сервис ФСП временно недоступен, попробуйте позже.";
    default:
      return "Не удалось привязать ФСП ID.";
  }
}
