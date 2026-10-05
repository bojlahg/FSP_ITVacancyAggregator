import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components, operations } from "@/api/schema";
import { apiError, toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type Vacancy = Schemas["VacancyOut"];
export type ApplyRequest = Schemas["ApplyRequest"];
export type ApplicationForCandidate = Schemas["ApplicationForCandidate"];
export type ApplicationForEmployer = Schemas["ApplicationForEmployer"];
export type ApplicationStatus = Schemas["ApplicationStatus"];
export type VacanciesQuery = NonNullable<operations["list_vacancies_api_v1_vacancies_get"]["parameters"]["query"]>;

export const vacancyKeys = {
  all: ["vacancies"] as const,
  list: (query: VacanciesQuery) => ["vacancies", "list", query] as const,
  myApplications: ["candidates", "me", "applications"] as const,
  /** Под префиксом потребности: правка потребности инвалидирует и отклики по ней. */
  needApplications: (needId: number) => ["needs", needId, "applications"] as const,
};

/** Отклик ещё ждёт решения работодателя (§8.7: sent → viewed → accepted | rejected). */
export const OPEN_APPLICATION_STATUSES: readonly ApplicationStatus[] = ["sent", "viewed"];

// ---------- кандидат ----------

export function useVacancies(query: VacanciesQuery) {
  return useQuery({
    queryKey: vacancyKeys.list(query),
    placeholderData: keepPreviousData,
    queryFn: async ({ signal }) => {
      const { data, error, response } = await api.GET("/api/v1/vacancies", { params: { query }, signal });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useApply() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: vacancyKeys.all });
    void queryClient.invalidateQueries({ queryKey: vacancyKeys.myApplications });
  };
  return useMutation({
    mutationFn: async ({ vacancyId, body }: { vacancyId: number; body: ApplyRequest }) => {
      const { data, error, response } = await api.POST("/api/v1/vacancies/{vacancy_id}/apply", {
        params: { path: { vacancy_id: vacancyId } },
        body,
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: invalidate,
    // already_applied: список устарел (отклик с другой вкладки) — подтянуть бейдж «Вы откликнулись».
    onError: (err) => {
      if (isAlreadyApplied(err)) invalidate();
    },
  });
}

/** 409 `already_applied`: на эту вакансию (любую её версию) уже есть отклик. */
export function isAlreadyApplied(err: unknown): boolean {
  const { status, code } = apiError(err);
  return status === 409 && code === "already_applied";
}

/** 409 `category_required`: откликаться можно только с категорией, полученной по тесту. */
export function isCategoryRequired(err: unknown): boolean {
  const { status, code } = apiError(err);
  return status === 409 && code === "category_required";
}

export function useMyApplications() {
  return useQuery({
    queryKey: vacancyKeys.myApplications,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/applications");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

// ---------- работодатель ----------

export function useNeedApplications(needId: number, enabled = true) {
  return useQuery({
    queryKey: vacancyKeys.needApplications(needId),
    enabled,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/needs/{need_id}/applications", {
        params: { path: { need_id: needId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

/** Подменяет отклик в кэше списка по вакансии ответом сервера (новый статус). */
function useReplaceInCache(needId: number) {
  const queryClient = useQueryClient();
  return (updated: ApplicationForEmployer) => {
    queryClient.setQueryData<ApplicationForEmployer[]>(vacancyKeys.needApplications(needId), (current) =>
      current?.map((item) => (item.id === updated.id ? updated : item)),
    );
  };
}

export function useViewApplication(needId: number) {
  const replace = useReplaceInCache(needId);
  return useMutation({
    mutationFn: async (applicationId: number) => {
      const { data, error, response } = await api.POST("/api/v1/applications/{application_id}/view", {
        params: { path: { application_id: applicationId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: replace,
  });
}

export function useDecideApplication(needId: number) {
  const queryClient = useQueryClient();
  const replace = useReplaceInCache(needId);
  return useMutation({
    mutationFn: async ({ applicationId, accept }: { applicationId: number; accept: boolean }) => {
      const params = { path: { application_id: applicationId } };
      const { data, error, response } = accept
        ? await api.POST("/api/v1/applications/{application_id}/accept", { params })
        : await api.POST("/api/v1/applications/{application_id}/reject", { params });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: replace,
    // application_closed: решение уже принято в другой вкладке — показать актуальный статус.
    onError: () => void queryClient.invalidateQueries({ queryKey: vacancyKeys.needApplications(needId) }),
  });
}
