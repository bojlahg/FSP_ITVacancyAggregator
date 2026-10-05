import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type TaskAssignment = Schemas["TaskAssignmentForCandidate"];
export type EmployerTask = Schemas["EmployerTaskOut"];
export type EmployerTaskCreate = Schemas["EmployerTaskCreate"];
export type TaskSubmission = Schemas["TaskSubmissionForEmployer"];
export type TaskTemplateOption = Schemas["TaskTemplateOption"];
export type AssignmentStatus = Schemas["AssignmentStatus"];

export const taskKeys = {
  mine: ["candidates", "me", "tasks"] as const,
  employer: ["employer", "tasks"] as const,
  submissions: (taskId: number) => ["employer", "tasks", taskId, "submissions"] as const,
  templates: (specialization: string | null, needId: number | null) =>
    ["employer", "tasks", "templates", specialization, needId] as const,
};

// ---------- кандидат ----------

export function useMyTasks() {
  return useQuery({
    queryKey: taskKeys.mine,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/tasks");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

function useReplaceAssignment() {
  const queryClient = useQueryClient();
  return (updated: TaskAssignment) => {
    queryClient.setQueryData<TaskAssignment[]>(taskKeys.mine, (current) =>
      current?.map((item) => (item.id === updated.id ? updated : item)),
    );
    // Подтверждённые навыки видны в профиле
    void queryClient.invalidateQueries({ queryKey: ["candidates", "me"], exact: true });
  };
}

export function useSubmitTask() {
  const replace = useReplaceAssignment();
  return useMutation({
    mutationFn: async ({ assignmentId, response: answer }: { assignmentId: number; response: Schemas["AnswerPayload"] }) => {
      const { data, error, response } = await api.POST("/api/v1/tasks/assignments/{assignment_id}/submit", {
        params: { path: { assignment_id: assignmentId } },
        body: { response: answer },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: replace,
  });
}

export function useSkipTask() {
  const replace = useReplaceAssignment();
  return useMutation({
    mutationFn: async (assignmentId: number) => {
      const { data, error, response } = await api.POST("/api/v1/tasks/assignments/{assignment_id}/skip", {
        params: { path: { assignment_id: assignmentId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: replace,
  });
}

// ---------- работодатель ----------

export function useEmployerTasks() {
  return useQuery({
    queryKey: taskKeys.employer,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employer-tasks");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: EmployerTaskCreate) => {
      const { data, error, response } = await api.POST("/api/v1/employer-tasks", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: taskKeys.employer, exact: true }),
  });
}

export function useTaskTemplates(specialization: string | null, needId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: taskKeys.templates(specialization, needId),
    enabled: enabled && (specialization !== null || needId !== null),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employer-tasks/templates", {
        params: { query: needId !== null ? { need_id: needId } : { specialization: specialization ?? undefined } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useTaskSubmissions(taskId: number | null) {
  return useQuery({
    queryKey: taskKeys.submissions(taskId ?? 0),
    enabled: taskId !== null,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/employer-tasks/{task_id}/submissions", {
        params: { path: { task_id: taskId ?? 0 } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useRateSubmission(taskId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ assignmentId, rating }: { assignmentId: number; rating: number }) => {
      const { data, error, response } = await api.POST(
        "/api/v1/employer-tasks/{task_id}/submissions/{assignment_id}/rate",
        { params: { path: { task_id: taskId, assignment_id: assignmentId } }, body: { rating } },
      );
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (updated) => {
      queryClient.setQueryData<TaskSubmission[]>(taskKeys.submissions(taskId), (current) =>
        current?.map((item) => (item.assignment_id === updated.assignment_id ? updated : item)),
      );
      void queryClient.invalidateQueries({ queryKey: taskKeys.employer, exact: true });
    },
  });
}
