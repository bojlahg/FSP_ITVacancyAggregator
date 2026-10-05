import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type VacancyTestPreview = Schemas["VacancyTestPreview"];
export type VacancyTestPreviewRequest = Schemas["VacancyTestPreviewRequest"];
export type PreviewItem = Schemas["PreviewItem"];
export type VacancyExample = Schemas["VacancyExample"];

const EXAMPLES_STALE_MS = 60 * 60 * 1000;

export function useVacancyExamples() {
  return useQuery({
    queryKey: ["vacancy-tests", "examples"] as const,
    staleTime: EXAMPLES_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/vacancy-tests/examples");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

/** POST /vacancy-tests/preview: blueprint, примеры заданий (без ключей ответов) и черновики LLM (§10.7). */
export function useVacancyTestPreview() {
  return useMutation({
    mutationFn: async (body: VacancyTestPreviewRequest) => {
      const { data, error, response } = await api.POST("/api/v1/vacancy-tests/preview", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}
