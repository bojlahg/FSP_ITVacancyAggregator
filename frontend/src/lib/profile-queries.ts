import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";
import { queryKeys } from "@/lib/testing-queries";

type Schemas = components["schemas"];

export type CandidateProfileUpdate = Schemas["CandidateProfileUpdate"];
export type ResumeParseResult = Schemas["ResumeParseResult"];
export type ExperienceItem = Schemas["ExperienceItem"];
export type PdfVariant = "full" | "public";

const CATALOG_STALE_MS = 60 * 60 * 1000;
const PDF_FALLBACK_NAME = "itscout-profile.pdf";

export const profileKeys = {
  teamRoles: ["catalog", "team-roles"] as const,
  softSkills: ["catalog", "soft-skills"] as const,
};

export function useTeamRoles() {
  return useQuery({
    queryKey: profileKeys.teamRoles,
    staleTime: CATALOG_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/catalog/team-roles");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useSoftSkills() {
  return useQuery({
    queryKey: profileKeys.softSkills,
    staleTime: CATALOG_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/catalog/soft-skills");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

/** PUT /candidates/me: форма профиля или подтверждённое предзаполнение из резюме. */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: CandidateProfileUpdate) => {
      const { data, error, response } = await api.PUT("/api/v1/candidates/me", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (profile) => queryClient.setQueryData(queryKeys.me, profile),
  });
}

/** POST /candidates/me/resume (multipart): профиль не меняется, приходит только предзаполнение. */
export function useUploadResume() {
  return useMutation({
    mutationFn: async (file: File) => {
      const { data, error, response } = await api.POST("/api/v1/candidates/me/resume", {
        // В схеме поле file описано строкой (binary); фактически отправляем FormData с файлом
        body: { file: "" },
        bodySerializer: () => {
          const form = new FormData();
          form.append("file", file);
          return form;
        },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

function filenameOf(response: Response): string {
  const header = response.headers.get("Content-Disposition") ?? "";
  return /filename="([^"]+)"/.exec(header)?.[1] ?? PDF_FALLBACK_NAME;
}

async function errorBody(blob: unknown): Promise<unknown> {
  if (!(blob instanceof Blob)) return blob;
  try {
    return JSON.parse(await blob.text()) as unknown;
  } catch {
    return null;
  }
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Скачать свой PDF-профиль: полный или как его видит работодатель до контакта. */
export function useDownloadMyPdf() {
  return useMutation({
    mutationFn: async (variant: PdfVariant) => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/profile.pdf", {
        params: { query: { variant } },
        parseAs: "blob",
      });
      if (!data || !response.ok) throw toApiError(response, await errorBody(error));
      saveBlob(data, filenameOf(response));
    },
  });
}

/** Скачать PDF-профиль кандидата (работодатель): полный только после раскрытия контактов. */
export function useDownloadCandidatePdf() {
  return useMutation({
    mutationFn: async (candidateId: number) => {
      const { data, error, response } = await api.GET("/api/v1/talent/candidates/{candidate_id}/profile.pdf", {
        params: { path: { candidate_id: candidateId } },
        parseAs: "blob",
      });
      if (!data || !response.ok) throw toApiError(response, await errorBody(error));
      saveBlob(data, filenameOf(response));
    },
  });
}

