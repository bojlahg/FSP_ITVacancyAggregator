import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type ApiKey = Schemas["ApiKeyOut"];
export type ApiKeyCreated = Schemas["ApiKeyCreated"];
export type Webhook = Schemas["WebhookOut"];
export type WebhookDelivery = Schemas["WebhookDeliveryOut"];

const keys = {
  apiKeys: ["integrations", "api-keys"] as const,
  webhook: ["integrations", "webhook"] as const,
  deliveries: ["integrations", "deliveries"] as const,
};

export function useApiKeys() {
  return useQuery({
    queryKey: keys.apiKeys,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employers/me/api-keys");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) => {
      const { data, error, response } = await api.POST("/api/v1/employers/me/api-keys", { body: { name } });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.apiKeys }),
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (keyId: number) => {
      const { error, response } = await api.DELETE("/api/v1/employers/me/api-keys/{key_id}", {
        params: { path: { key_id: keyId } },
      });
      if (!response.ok) throw toApiError(response, error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.apiKeys }),
  });
}

export function useWebhook() {
  return useQuery({
    queryKey: keys.webhook,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employers/me/webhook");
      if (!response.ok) throw toApiError(response, error);
      return data ?? null;
    },
  });
}

export function useSaveWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["WebhookUpdate"]) => {
      const { data, error, response } = await api.PUT("/api/v1/employers/me/webhook", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (hook) => queryClient.setQueryData(keys.webhook, hook),
  });
}

export function useRotateWebhookSecret() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/v1/employers/me/webhook/rotate-secret");
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (hook) => queryClient.setQueryData(keys.webhook, hook),
  });
}

export function useDeleteWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/api/v1/employers/me/webhook");
      if (!response.ok) throw toApiError(response, error);
    },
    onSuccess: () => queryClient.setQueryData(keys.webhook, null),
  });
}

export function useWebhookDeliveries(enabled: boolean) {
  return useQuery({
    queryKey: keys.deliveries,
    enabled,
    // Доставка идёт в фоне — список обновляется сам, пока есть ожидающие
    refetchInterval: (query) => (query.state.data?.some((item) => item.status === "pending") ? 3000 : false),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employers/me/webhook/deliveries");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useTestWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/v1/employers/me/webhook/test");
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.deliveries }),
  });
}

export function useRetryDelivery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (deliveryId: number) => {
      const { data, error, response } = await api.POST(
        "/api/v1/employers/me/webhook/deliveries/{delivery_id}/retry",
        { params: { path: { delivery_id: deliveryId } } },
      );
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.deliveries }),
  });
}
