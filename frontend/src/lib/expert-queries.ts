import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";
import { authStore } from "@/lib/auth";

type Schemas = components["schemas"];

export type ExpertTask = Schemas["ExpertTask"];
export type ExpertSummary = Schemas["ExpertSummary"];

const keys = {
  next: ["expert", "next"] as const,
  summary: ["expert", "summary"] as const,
};

export function useRegisterExpert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["RegisterExpertRequest"]) => {
      const { data, error, response } = await api.POST("/api/v1/auth/register-expert", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (token) => {
      queryClient.removeQueries();
      authStore.setSession(token);
    },
  });
}

export function useExpertTask() {
  return useQuery({
    queryKey: keys.next,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/expert/next");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useLabelPair() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ pairId, label }: { pairId: number; label: number }) => {
      const { data, error, response } = await api.POST("/api/v1/expert/pairs/{pair_id}/label", {
        params: { path: { pair_id: pairId } },
        body: { label },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expert"] });
    },
  });
}

export function useExpertSummary() {
  return useQuery({
    queryKey: keys.summary,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/expert/summary");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export type AngoffTasks = Schemas["AngoffTasks"];
export type AngoffSummary = Schemas["AngoffSummary"];
export type AngoffGrade = Schemas["AngoffTasks"]["grade"];

const angoffKeys = {
  tasks: (specialization: string, grade: AngoffGrade) => ["expert", "angoff", "tasks", specialization, grade] as const,
  summary: (specialization: string) => ["expert", "angoff", "summary", specialization] as const,
};

export function useAngoffTasks(specialization: string | undefined, grade: AngoffGrade) {
  return useQuery({
    queryKey: angoffKeys.tasks(specialization ?? "", grade),
    enabled: Boolean(specialization),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/expert/angoff/tasks", {
        params: { query: { specialization: specialization ?? "", grade } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useRateAngoff() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["AngoffRatingRequest"]) => {
      const { data, error, response } = await api.PUT("/api/v1/expert/angoff/ratings", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    // Автосохранение: оценка и прогресс обновляются в кэше без перезагрузки списка заданий
    onSuccess: async (progress, body) => {
      queryClient.setQueryData<AngoffTasks>(
        angoffKeys.tasks(body.specialization, body.grade),
        (old) =>
          old && {
            ...old,
            progress,
            tasks: old.tasks.map((task) =>
              task.template_id === body.template_id ? { ...task, rating: body.rating } : task,
            ),
          },
      );
      await queryClient.invalidateQueries({ queryKey: angoffKeys.summary(body.specialization) });
    },
  });
}

export function useAngoffSummary(specialization: string | undefined) {
  return useQuery({
    queryKey: angoffKeys.summary(specialization ?? ""),
    enabled: Boolean(specialization),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/expert/angoff/summary", {
        params: { query: { specialization: specialization ?? "" } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}
