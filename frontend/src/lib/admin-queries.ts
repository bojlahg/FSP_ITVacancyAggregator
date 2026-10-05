import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";

export type ReportForAdmin = components["schemas"]["ReportForAdmin"];
export type ReportStatus = ReportForAdmin["status"];

export function useInvitationReports(status: ReportStatus | null) {
  return useQuery({
    queryKey: ["admin", "invitation-reports", status],
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/api/v1/admin/invitation-reports",
        {
          params: { query: status ? { status } : {} },
        },
      );
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useResolveReport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      reportId,
      resolution,
    }: {
      reportId: number;
      resolution: string;
    }) => {
      const { data, error, response } = await api.POST(
        "/api/v1/admin/invitation-reports/{report_id}/resolve",
        {
          params: { path: { report_id: reportId } },
          body: { resolution },
        },
      );
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["admin", "invitation-reports"] }),
  });
}
