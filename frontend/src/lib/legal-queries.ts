import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type LegalDocument = Schemas["LegalDocument"];
export type LegalSlug = LegalDocument["slug"];
export type GradeDecision = Schemas["GradeDecision"];
export type Appeal = Schemas["AppealOut"];
export type AdminAppeal = Schemas["AdminAppealOut"];
export type AppealStatus = Schemas["AppealStatus"];

/** Юридические документы (docs/implementation.md §13.1) — порядок ссылок в футере и на страницах. */
export const LEGAL_LINKS: { slug: LegalSlug; label: string }[] = [
  { slug: "recommendations", label: "Правила рекомендательных технологий" },
  { slug: "privacy", label: "Политика обработки ПДн" },
  { slug: "consent-pd", label: "Согласие на обработку ПДн" },
  { slug: "consent-publication", label: "Согласие на публикацию профиля" },
];

export function isLegalSlug(value: string | undefined): value is LegalSlug {
  return LEGAL_LINKS.some((link) => link.slug === value);
}

export const legalPath = (slug: LegalSlug) => `/legal/${slug}`;

// Тексты меняются только с деплоем.
const LEGAL_STALE_MS = 60 * 60 * 1000;

export function useLegalDocument(slug: LegalSlug | undefined) {
  return useQuery({
    queryKey: ["legal", slug] as const,
    enabled: Boolean(slug),
    staleTime: LEGAL_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/legal/documents/{slug}", {
        params: { path: { slug: slug ?? "" } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

const appealKeys = {
  explanation: ["candidates", "me", "grade-explanation"] as const,
  mine: ["candidates", "me", "appeals"] as const,
  admin: (status: AppealStatus | undefined) => ["admin", "appeals", status ?? "all"] as const,
};

/** Блок «Как определён грейд»: θ̂, SE, порог, дата теста. */
export function useGradeExplanation() {
  return useQuery({
    queryKey: appealKeys.explanation,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/grade-explanation");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useMyAppeals() {
  return useQuery({
    queryKey: appealKeys.mine,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/appeals");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useCreateAppeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (comment: string) => {
      const { data, error, response } = await api.POST("/api/v1/candidates/me/appeals", { body: { comment } });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: appealKeys.mine }),
  });
}

export function useAdminAppeals(status: AppealStatus | undefined) {
  return useQuery({
    queryKey: appealKeys.admin(status),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/admin/appeals", {
        params: { query: status ? { status } : {} },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useResolveAppeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reply }: { id: number; reply: string }) => {
      const { data, error, response } = await api.POST("/api/v1/admin/appeals/{appeal_id}/resolve", {
        params: { path: { appeal_id: id } },
        body: { reply },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "appeals"] }),
  });
}
