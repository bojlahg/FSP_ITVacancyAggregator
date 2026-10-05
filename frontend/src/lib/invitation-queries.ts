import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type InvitationForCandidate = Schemas["InvitationForCandidate"];
export type DeclineRequest = Schemas["DeclineRequest"];
export type ReportRequest = Schemas["ReportRequest"];

export const candidateInvitationKeys = {
  all: ["candidates", "me", "invitations"] as const,
};

export function useMyInvitations() {
  return useQuery({
    queryKey: candidateInvitationKeys.all,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/invitations");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

/** Подменяет приглашение в кэше списка ответом сервера (у приглашения новый статус). */
function useReplaceInCache() {
  const queryClient = useQueryClient();
  return (updated: InvitationForCandidate) => {
    queryClient.setQueryData<InvitationForCandidate[]>(candidateInvitationKeys.all, (current) =>
      current?.map((item) => (item.id === updated.id ? updated : item)),
    );
  };
}

export function useViewInvitation() {
  const replace = useReplaceInCache();
  return useMutation({
    mutationFn: async (invitationId: number) => {
      const { data, error, response } = await api.POST("/api/v1/invitations/{invitation_id}/view", {
        params: { path: { invitation_id: invitationId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: replace,
  });
}

export function useAcceptInvitation() {
  const replace = useReplaceInCache();
  return useMutation({
    mutationFn: async (invitationId: number) => {
      const { data, error, response } = await api.POST("/api/v1/invitations/{invitation_id}/accept", {
        params: { path: { invitation_id: invitationId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: replace,
  });
}

export function useDeclineInvitation() {
  const replace = useReplaceInCache();
  return useMutation({
    mutationFn: async ({ invitationId, body }: { invitationId: number; body: DeclineRequest }) => {
      const { data, error, response } = await api.POST("/api/v1/invitations/{invitation_id}/decline", {
        params: { path: { invitation_id: invitationId } },
        body,
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: replace,
  });
}

export function useReportInvitation() {
  const replace = useReplaceInCache();
  return useMutation({
    mutationFn: async ({ invitationId, body }: { invitationId: number; body: ReportRequest }) => {
      const { data, error, response } = await api.POST("/api/v1/invitations/{invitation_id}/report", {
        params: { path: { invitation_id: invitationId } },
        body,
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: replace,
  });
}
