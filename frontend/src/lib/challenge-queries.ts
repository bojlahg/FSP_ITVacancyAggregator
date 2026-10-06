import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";
import { localDeadline, type CurrentItemWithClock, type SubmitAnswerParams } from "@/lib/testing-queries";

type Schemas = components["schemas"];

export type Challenge = Schemas["ChallengeOut"];
export type ChallengeCreate = Schemas["ChallengeCreate"];
export type ChallengeCard = Schemas["ChallengeCard"];
export type ChallengeSolver = Schemas["ChallengeSolver"];
export type ChallengeAttempt = Schemas["ChallengeAttemptResult"];

export const challengeKeys = {
  employer: ["employer", "challenges"] as const,
  solvers: (id: number) => ["employer", "challenges", id, "solvers"] as const,
  available: ["challenges"] as const,
  attempt: (id: number) => ["challenge-attempts", id] as const,
  current: (id: number) => ["challenge-attempts", id, "current"] as const,
};

// ---------- работодатель ----------

export function useEmployerChallenges() {
  return useQuery({
    queryKey: challengeKeys.employer,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employer-challenges");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useCreateChallenge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ChallengeCreate) => {
      const { data, error, response } = await api.POST("/api/v1/employer-challenges", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: challengeKeys.employer }),
  });
}

export function useChallengeAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, action }: { id: number; action: "publish" | "close" }) => {
      const params = { path: { challenge_id: id } };
      const { data, error, response } =
        action === "publish"
          ? await api.POST("/api/v1/employer-challenges/{challenge_id}/publish", { params })
          : await api.POST("/api/v1/employer-challenges/{challenge_id}/close", { params });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: challengeKeys.employer }),
  });
}

export function useChallengeSolvers(id: number, enabled: boolean) {
  return useQuery({
    queryKey: challengeKeys.solvers(id),
    enabled,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employer-challenges/{challenge_id}/solvers", {
        params: { path: { challenge_id: id } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

// ---------- кандидат ----------

export function useAvailableChallenges() {
  return useQuery({
    queryKey: challengeKeys.available,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/challenges");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useStartChallenge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (challengeId: number) => {
      const { data, error, response } = await api.POST("/api/v1/challenges/{challenge_id}/start", {
        params: { path: { challenge_id: challengeId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: challengeKeys.available }),
  });
}

export function useChallengeAttempt(attemptId: number) {
  return useQuery({
    queryKey: challengeKeys.attempt(attemptId),
    enabled: Number.isFinite(attemptId),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/challenge-attempts/{attempt_id}", {
        params: { path: { attempt_id: attemptId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useChallengeQuestion(attemptId: number) {
  return useQuery({
    queryKey: challengeKeys.current(attemptId),
    enabled: Number.isFinite(attemptId),
    // Как в тесте: новый вопрос — только после ответа, фоновый refetch не подменяет вопрос
    staleTime: Infinity,
    gcTime: 0,
    queryFn: async (): Promise<CurrentItemWithClock> => {
      const { data, error, response } = await api.GET("/api/v1/challenge-attempts/{attempt_id}/current", {
        params: { path: { attempt_id: attemptId } },
      });
      if (!data) throw toApiError(response, error);
      return { item: data, localDeadlineMs: localDeadline(data, response, Date.now()) };
    },
  });
}

export function useAnswerChallenge(attemptId: number) {
  return useMutation({
    mutationFn: async ({ itemId, response: answer, focusLostCount }: SubmitAnswerParams) => {
      const { data, error, response } = await api.POST("/api/v1/challenge-attempts/{attempt_id}/answer", {
        params: { path: { attempt_id: attemptId } },
        body: { item_id: itemId, response: answer, focus_lost_count: focusLostCount },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}
