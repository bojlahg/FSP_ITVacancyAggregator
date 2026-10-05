import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";
import { queryKeys } from "@/lib/testing-queries";

type Schemas = components["schemas"];

export type PrivacySettings = Schemas["PrivacySettings"];
export type ConsentOut = Schemas["ConsentOut"];
export type ConsentKind = Schemas["ConsentKind"];
export type SearchStatus = Schemas["SearchStatus"];
export type CompanyRef = Schemas["CompanyRef"];

export const settingsKeys = {
  consents: ["candidates", "me", "consents"] as const,
  companies: (q: string, ids: number[]) => ["candidates", "me", "companies", q, ids] as const,
};

export function useUpdatePrivacy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: PrivacySettings) => {
      const { data, error, response } = await api.PUT("/api/v1/candidates/me/privacy", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.me }),
  });
}

export function useUpdateSearchStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (searchStatus: SearchStatus) => {
      const { data, error, response } = await api.PUT("/api/v1/candidates/me/search-status", {
        body: { search_status: searchStatus },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (profile) => queryClient.setQueryData(queryKeys.me, profile),
  });
}

export function useConsents() {
  return useQuery({
    queryKey: settingsKeys.consents,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/consents");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useUpdateConsent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["ConsentUpdate"]) => {
      const { data, error, response } = await api.PUT("/api/v1/candidates/me/consents", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (consents) => {
      queryClient.setQueryData(settingsKeys.consents, consents);
      // Отзыв согласия на импорт ФСП отвязывает ФСП ID — профиль нужно перечитать
      void queryClient.invalidateQueries({ queryKey: queryKeys.me });
    },
  });
}

/** Поиск компаний по названию (q от 2 символов) или названия уже скрытых по id. */
export function useCompanies(q: string, ids: number[]) {
  const query = q.trim();
  return useQuery({
    queryKey: settingsKeys.companies(query, ids),
    enabled: query.length >= 2 || ids.length > 0,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/companies", {
        params: { query: query.length >= 2 ? { q: query } : { ids } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useDeleteAccount() {
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.DELETE("/api/v1/candidates/me");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}
