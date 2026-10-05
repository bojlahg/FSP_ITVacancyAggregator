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
export type AngoffImpact = Schemas["AngoffImpact"];
export type AngoffHofsteeValues = Schemas["AngoffHofsteeValues"];
export type AngoffGrade = Schemas["AngoffTasks"]["grade"];
export type AngoffRound = 1 | 2;

const angoffKeys = {
  all: (specialization: string, grade: AngoffGrade) => ["expert", "angoff", "grade", specialization, grade] as const,
  tasks: (specialization: string, grade: AngoffGrade, round: AngoffRound) =>
    ["expert", "angoff", "grade", specialization, grade, "tasks", round] as const,
  impact: (specialization: string, grade: AngoffGrade) =>
    ["expert", "angoff", "grade", specialization, grade, "impact"] as const,
  summary: (specialization: string) => ["expert", "angoff", "summary", specialization] as const,
};

export function useAngoffTasks(specialization: string | undefined, grade: AngoffGrade, round: AngoffRound = 1) {
  return useQuery({
    queryKey: angoffKeys.tasks(specialization ?? "", grade, round),
    enabled: Boolean(specialization),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/expert/angoff/tasks", {
        params: { query: { specialization: specialization ?? "", grade, round } },
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
      const round = (body.round ?? 1) as AngoffRound;
      queryClient.setQueryData<AngoffTasks>(
        angoffKeys.tasks(body.specialization, body.grade, round),
        (old) =>
          old && {
            ...old,
            progress,
            round1_complete: round === 1 ? progress.done === progress.total : old.round1_complete,
            tasks: old.tasks.map((task) =>
              task.template_id === body.template_id ? { ...task, rating: body.rating } : task,
            ),
          },
      );
      // Раунд 1 меняет данные о последствиях и оценки «раунда 1» на экране раунда 2
      if (round === 1) {
        await queryClient.invalidateQueries({ queryKey: angoffKeys.impact(body.specialization, body.grade) });
        await queryClient.invalidateQueries({ queryKey: angoffKeys.tasks(body.specialization, body.grade, 2) });
      }
      await queryClient.invalidateQueries({ queryKey: angoffKeys.summary(body.specialization) });
    },
  });
}

export function useStartAngoffRound2() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["AngoffRoundStart"]) => {
      const { data, error, response } = await api.POST("/api/v1/expert/angoff/round2", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: async (_progress, body) => {
      await queryClient.invalidateQueries({ queryKey: angoffKeys.all(body.specialization, body.grade) });
      await queryClient.invalidateQueries({ queryKey: angoffKeys.summary(body.specialization) });
    },
  });
}

export function useAngoffImpact(specialization: string | undefined, grade: AngoffGrade, enabled: boolean) {
  return useQuery({
    queryKey: angoffKeys.impact(specialization ?? "", grade),
    enabled: Boolean(specialization) && enabled,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/expert/angoff/impact", {
        params: { query: { specialization: specialization ?? "", grade } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useSaveAngoffHofstee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["AngoffHofsteeRequest"]) => {
      const { data, error, response } = await api.PUT("/api/v1/expert/angoff/hofstee", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: async (values, body) => {
      for (const round of [1, 2] as const) {
        queryClient.setQueryData<AngoffTasks>(
          angoffKeys.tasks(body.specialization, body.grade, round),
          (old) => old && { ...old, hofstee: values },
        );
      }
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
