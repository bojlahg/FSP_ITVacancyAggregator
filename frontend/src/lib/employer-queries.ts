import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components, operations } from "@/api/schema";
import { apiError, toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type EmployerProfile = Schemas["EmployerProfileOut"];
export type EmployerProfileUpdate = Schemas["EmployerProfileUpdate"];
export type EmployerReputation = Schemas["EmployerReputation"];
export type Need = Schemas["NeedOut"];
export type NeedCreate = Schemas["NeedCreate"];
export type NeedDraft = Schemas["NeedDraft"];
export type NeedParseResult = Schemas["NeedParseResult"];
export type RecommendationsOut = Schemas["RecommendationsOut"];
export type CandidateMatch = Schemas["CandidateMatch"];
export type CandidateBrief = Schemas["CandidateBrief"];
export type Acceptance = Schemas["AcceptanceOut"];
export type CandidateCard = Schemas["CandidateCard"];
export type CategoryRecommendation = Schemas["CategoryRecommendation"];
export type CategoryCatalogItem = Schemas["CategoryCatalogItem"];
export type SalaryCoverage = Schemas["SalaryCoverage"];
export type InvitationCreate = Schemas["InvitationCreate"];
export type InvitationForEmployer = Schemas["InvitationForEmployer"];
export type InvitationStatus = Schemas["InvitationStatus"];
export type DeclineStats = Schemas["DeclineStats"];
export type DeclineReason = Schemas["DeclineReason"];
export type WorkFormat = Schemas["WorkFormat"];
export type IndustryOut = Schemas["IndustryOut"];

export type RecommendationsQuery = NonNullable<
  operations["get_recommendations_api_v1_needs__need_id__recommendations_get"]["parameters"]["query"]
>;
export type TalentSearchQuery = NonNullable<
  operations["search_talent_api_v1_talent_search_get"]["parameters"]["query"]
>;
export type EmployerInvitationsQuery = NonNullable<
  operations["list_sent_invitations_api_v1_employers_me_invitations_get"]["parameters"]["query"]
>;

export const employerKeys = {
  company: ["employer", "company"] as const,
  industries: ["catalog", "industries"] as const,
  needs: ["needs"] as const,
  need: (id: number) => ["needs", id] as const,
  recommendationsOf: (id: number) => ["needs", id, "recommendations"] as const,
  recommendations: (id: number, query: RecommendationsQuery) => ["needs", id, "recommendations", query] as const,
  coverage: (id: number) => ["needs", id, "salary-coverage"] as const,
  talentCategories: ["talent", "categories"] as const,
  talentSearch: (query: TalentSearchQuery) => ["talent", "search", query] as const,
  candidate: (id: number, needId: number | null) => ["talent", "candidates", id, needId] as const,
  invitationsAll: ["employer", "invitations"] as const,
  invitations: (query: EmployerInvitationsQuery) => ["employer", "invitations", query] as const,
  declineStats: (needId: number | null) => ["employer", "decline-stats", needId] as const,
};

const CATALOG_STALE_MS = 60 * 60 * 1000;

/** id из адреса → число или null (для `enabled`). */
export function parseId(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : null;
}

// ---------- компания ----------

export function useCompany() {
  return useQuery({
    queryKey: employerKeys.company,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employers/me");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useUpdateCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: EmployerProfileUpdate) => {
      const { data, error, response } = await api.PUT("/api/v1/employers/me", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (company) => queryClient.setQueryData(employerKeys.company, company),
  });
}

export function useIndustries() {
  return useQuery({
    queryKey: employerKeys.industries,
    staleTime: CATALOG_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/catalog/industries");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

// ---------- потребности ----------

export function useNeeds() {
  return useQuery({
    queryKey: employerKeys.needs,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/needs");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useNeed(needId: number | null) {
  return useQuery({
    queryKey: employerKeys.need(needId ?? 0),
    enabled: needId !== null,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/needs/{need_id}", {
        params: { path: { need_id: needId ?? 0 } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useParseNeed() {
  return useMutation({
    mutationFn: async (rawText: string) => {
      const { data, error, response } = await api.POST("/api/v1/needs/parse", { body: { raw_text: rawText } });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useCreateNeed() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: NeedCreate) => {
      const { data, error, response } = await api.POST("/api/v1/needs", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (need) => {
      queryClient.setQueryData(employerKeys.need(need.id), need);
      void queryClient.invalidateQueries({ queryKey: employerKeys.needs, exact: true });
    },
  });
}

/** PUT создаёт новую версию потребности с новым id (§8.1 п.4): шорт-лист backend переносит сам. */
export function useUpdateNeed(needId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: NeedCreate) => {
      const { data, error, response } = await api.PUT("/api/v1/needs/{need_id}", {
        params: { path: { need_id: needId } },
        body,
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (need) => {
      queryClient.setQueryData(employerKeys.need(need.id), need);
      void queryClient.invalidateQueries({ queryKey: employerKeys.needs, exact: true });
      void queryClient.invalidateQueries({ queryKey: employerKeys.need(needId), exact: true });
    },
  });
}

export function useSetNeedPublished(needId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (publish: boolean) => {
      const params = { path: { need_id: needId } };
      const { data, error, response } = publish
        ? await api.POST("/api/v1/needs/{need_id}/publish", { params })
        : await api.POST("/api/v1/needs/{need_id}/unpublish", { params });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (need) => {
      queryClient.setQueryData(employerKeys.need(need.id), need);
      void queryClient.invalidateQueries({ queryKey: employerKeys.needs, exact: true });
    },
  });
}

// ---------- подборка ----------

export function useRecommendations(needId: number | null, query: RecommendationsQuery) {
  return useQuery({
    queryKey: employerKeys.recommendations(needId ?? 0, query),
    enabled: needId !== null,
    // Смена фильтров не должна обнулять подборку на экране (§8.1 п.4).
    placeholderData: keepPreviousData,
    queryFn: async ({ signal }) => {
      const { data, error, response } = await api.GET("/api/v1/needs/{need_id}/recommendations", {
        params: { path: { need_id: needId ?? 0 }, query },
        signal,
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useSalaryCoverage(needId: number | null) {
  return useQuery({
    queryKey: employerKeys.coverage(needId ?? 0),
    enabled: needId !== null,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/needs/{need_id}/salary-coverage", {
        params: { path: { need_id: needId ?? 0 } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

function withShortlisted(match: CandidateMatch, candidateId: number, value: boolean): CandidateMatch {
  return match.candidate.id === candidateId ? { ...match, shortlisted: value } : match;
}

interface ShortlistToggle {
  match: CandidateMatch;
  add: boolean;
}

/** Шорт-лист с оптимистичным обновлением всех закэшированных подборок этой потребности. */
export function useToggleShortlist(needId: number) {
  const queryClient = useQueryClient();
  const prefix = employerKeys.recommendationsOf(needId);
  return useMutation({
    mutationFn: async ({ match, add }: ShortlistToggle) => {
      const params = { path: { need_id: needId, candidate_id: match.candidate.id } };
      const { data, error, response } = add
        ? await api.POST("/api/v1/needs/{need_id}/shortlist/{candidate_id}", { params, body: {} })
        : await api.DELETE("/api/v1/needs/{need_id}/shortlist/{candidate_id}", { params });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onMutate: async ({ match, add }) => {
      await queryClient.cancelQueries({ queryKey: prefix });
      const snapshot = queryClient.getQueriesData<RecommendationsOut>({ queryKey: prefix });
      const id = match.candidate.id;
      queryClient.setQueriesData<RecommendationsOut>({ queryKey: prefix }, (current) => {
        if (!current) return current;
        const rest = current.shortlist.filter((item) => item.candidate.id !== id);
        return {
          ...current,
          candidates: current.candidates.map((item) => withShortlisted(item, id, add)),
          out_of_filter: current.out_of_filter.map((item) => withShortlisted(item, id, add)),
          shortlist: add ? [...rest, { ...match, shortlisted: true }] : rest,
        };
      });
      return { snapshot };
    },
    onError: (_err, _vars, context) => {
      for (const [key, data] of context?.snapshot ?? []) queryClient.setQueryData(key as QueryKey, data);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: prefix });
      void queryClient.invalidateQueries({ queryKey: employerKeys.need(needId), exact: true });
    },
  });
}

// ---------- база талантов ----------

export function useTalentCategories() {
  return useQuery({
    queryKey: employerKeys.talentCategories,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/talent/categories");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useTalentSearch(query: TalentSearchQuery) {
  return useQuery({
    queryKey: employerKeys.talentSearch(query),
    placeholderData: keepPreviousData,
    queryFn: async ({ signal }) => {
      const { data, error, response } = await api.GET("/api/v1/talent/search", { params: { query }, signal });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useCandidateCard(candidateId: number | null, needId: number | null) {
  return useQuery({
    queryKey: employerKeys.candidate(candidateId ?? 0, needId),
    enabled: candidateId !== null,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/talent/candidates/{candidate_id}", {
        params: { path: { candidate_id: candidateId ?? 0 }, query: needId === null ? {} : { need_id: needId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

// ---------- приглашения ----------

export function useCreateInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: InvitationCreate) => {
      const { data, error, response } = await api.POST("/api/v1/invitations", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (invitation) => {
      void queryClient.invalidateQueries({ queryKey: employerKeys.invitationsAll });
      void queryClient.invalidateQueries({ queryKey: employerKeys.needs, exact: true });
      if (invitation.need_id !== null) {
        void queryClient.invalidateQueries({ queryKey: employerKeys.need(invitation.need_id), exact: true });
      }
    },
  });
}

/** 409 `invitation_limit`: по потребности уже максимум активных приглашений (§8.6 п.3). */
export function isInvitationLimit(err: unknown): boolean {
  const { status, code } = apiError(err);
  return status === 409 && code === "invitation_limit";
}

export function useEmployerInvitations(query: EmployerInvitationsQuery) {
  return useQuery({
    queryKey: employerKeys.invitations(query),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employers/me/invitations", { params: { query } });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useWithdrawInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (invitationId: number) => {
      const { data, error, response } = await api.POST("/api/v1/invitations/{invitation_id}/withdraw", {
        params: { path: { invitation_id: invitationId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (invitation) => {
      void queryClient.invalidateQueries({ queryKey: employerKeys.invitationsAll });
      void queryClient.invalidateQueries({ queryKey: employerKeys.needs, exact: true });
      if (invitation.need_id !== null) {
        void queryClient.invalidateQueries({ queryKey: employerKeys.need(invitation.need_id), exact: true });
      }
    },
  });
}

export function useDeclineStats(needId: number | null) {
  return useQuery({
    queryKey: employerKeys.declineStats(needId),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employers/me/decline-stats", {
        params: { query: needId === null ? {} : { need_id: needId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}
