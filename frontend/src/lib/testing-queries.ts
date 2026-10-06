import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { apiError, toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type Grade = Schemas["Grade"];
export type AttemptPurpose = Schemas["AttemptPurpose"];
export type CandidateProfile = Schemas["CandidateProfileOut"];
export type GradeStatus = Schemas["GradeStatus"];
export type GradeOut = Schemas["GradeOut"];
export type SpecializationOut = Schemas["SpecializationOut"];
export type SurveyQuestion = Schemas["SurveyQuestion"];
export type SurveyResult = Schemas["SurveyResult"];
export type SkillOut = Schemas["SkillOut"];
export type CurrentItem = Schemas["CurrentItem"];
export type AnswerPayload = Schemas["AnswerPayload"];
export type AttemptResultOut = Schemas["AttemptResultOut"];

export const queryKeys = {
  me: ["candidates", "me"] as const,
  gradeStatus: ["candidates", "me", "grade-status"] as const,
  specializations: ["catalog", "specializations"] as const,
  grades: ["catalog", "grades"] as const,
  skills: (q: string) => ["catalog", "skills", q] as const,
  surveyQuestions: ["survey", "questions"] as const,
  /** Результат последнего опроса в этой сессии: GET для него в API нет. */
  surveyResult: ["survey", "result"] as const,
  attempt: (id: number) => ["tests", "attempts", id] as const,
  currentItem: (id: number) => ["tests", "attempts", id, "current"] as const,
  attemptResult: (id: number) => ["tests", "attempts", id, "result"] as const,
};

// Справочники меняются только при деплое.
const CATALOG_STALE_MS = 60 * 60 * 1000;

export function useCandidateMe() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useGradeStatus() {
  return useQuery({
    queryKey: queryKeys.gradeStatus,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/grade-status");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useSpecializations() {
  return useQuery({
    queryKey: queryKeys.specializations,
    staleTime: CATALOG_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/catalog/specializations");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useGrades() {
  return useQuery({
    queryKey: queryKeys.grades,
    staleTime: CATALOG_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/catalog/grades");
      if (!data) throw toApiError(response, error);
      return [...data].sort((a, b) => a.order - b.order);
    },
  });
}

export function useSkillSearch(q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: queryKeys.skills(query),
    enabled: query.length > 0,
    staleTime: CATALOG_STALE_MS,
    queryFn: async ({ signal }) => {
      const { data, error, response } = await api.GET("/api/v1/catalog/skills", {
        params: { query: { q: query } },
        signal,
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

/** Весь справочник навыков — чтобы показать названия по id (без q сервер отдаёт полный список). */
export function useSkillCatalog(enabled = true) {
  return useQuery({
    queryKey: queryKeys.skills(""),
    enabled,
    staleTime: CATALOG_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/catalog/skills");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useSurveyQuestions() {
  return useQuery({
    queryKey: queryKeys.surveyQuestions,
    staleTime: CATALOG_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/survey/questions");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useSubmitSurvey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (answers: Record<string, unknown>) => {
      const { data, error, response } = await api.POST("/api/v1/survey/responses", { body: { answers } });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.surveyResult, result);
      void queryClient.invalidateQueries({ queryKey: queryKeys.me, exact: true });
    },
  });
}

export function useConfirmSpecialization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (specialization: string) => {
      const { data, error, response } = await api.POST("/api/v1/survey/specialization", {
        body: { specialization },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.me, exact: true }),
  });
}

export interface StartAttemptParams {
  specialization: string;
  grade_target: Grade;
  purpose: AttemptPurpose;
}

export function useStartAttempt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: StartAttemptParams) => {
      const { data, error, response } = await api.POST("/api/v1/tests/attempts", { body });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onSuccess: (attempt) => {
      queryClient.setQueryData(queryKeys.attempt(attempt.id), attempt);
      void queryClient.invalidateQueries({ queryKey: queryKeys.me });
    },
  });
}

export function useAttempt(attemptId: number) {
  return useQuery({
    queryKey: queryKeys.attempt(attemptId),
    enabled: Number.isFinite(attemptId),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/tests/attempts/{attempt_id}", {
        params: { path: { attempt_id: attemptId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export interface CurrentItemWithClock {
  item: CurrentItem;
  /**
   * Дедлайн ответа в часах браузера (мс). Сервер — источник истины: его дедлайн переводится
   * в локальное время по заголовку Date ответа, чтобы расхождение часов не сдвигало таймер.
   */
  localDeadlineMs: number | null;
}

export function localDeadline(item: CurrentItem, response: Response, receivedAt: number): number | null {
  if (!item.deadline_at) return null;
  const serverDeadline = Date.parse(item.deadline_at);
  if (Number.isNaN(serverDeadline)) return null;
  const dateHeader = response.headers.get("Date");
  // Date округлён вниз до секунды — берём середину секунды.
  const serverNow = dateHeader ? Date.parse(dateHeader) + 500 : Number.NaN;
  const skew = Number.isNaN(serverNow) ? 0 : serverNow - receivedAt;
  let deadline = serverDeadline - skew;
  if (item.time_limit_sec != null) deadline = Math.min(deadline, receivedAt + item.time_limit_sec * 1000);
  return deadline;
}

export function useCurrentItem(attemptId: number) {
  return useQuery({
    queryKey: queryKeys.currentItem(attemptId),
    enabled: Number.isFinite(attemptId),
    // Новое задание запрашиваем только после ответа: фоновый refetch не должен подменять вопрос.
    staleTime: Infinity,
    gcTime: 0,
    queryFn: async (): Promise<CurrentItemWithClock> => {
      const { data, error, response } = await api.GET("/api/v1/tests/attempts/{attempt_id}/current", {
        params: { path: { attempt_id: attemptId } },
      });
      if (!data) throw toApiError(response, error);
      return { item: data, localDeadlineMs: localDeadline(data, response, Date.now()) };
    },
  });
}

export interface SubmitAnswerParams {
  itemId: number;
  response: AnswerPayload;
  focusLostCount: number;
}

export function useSubmitAnswer(attemptId: number) {
  return useMutation({
    mutationFn: async ({ itemId, response: answer, focusLostCount }: SubmitAnswerParams) => {
      const { data, error, response } = await api.POST("/api/v1/tests/attempts/{attempt_id}/answer", {
        params: { path: { attempt_id: attemptId } },
        body: { item_id: itemId, response: answer, focus_lost_count: focusLostCount },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useAttemptResult(attemptId: number) {
  return useQuery({
    queryKey: queryKeys.attemptResult(attemptId),
    enabled: Number.isFinite(attemptId),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/tests/attempts/{attempt_id}/result", {
        params: { path: { attempt_id: attemptId } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export type StartAttemptConflict =
  | { kind: "in_progress"; attemptId: number }
  | { kind: "cooldown"; availableAt: string | null; message: string };

/** 409 при старте попытки: незаконченная попытка или действующий интервал между тестами (§6.3). */
export function startAttemptConflict(err: unknown): StartAttemptConflict | null {
  const { status, code, message, details } = apiError(err);
  if (status !== 409) return null;
  if (code === "attempt_in_progress" && isRecord(details) && typeof details.attempt_id === "number") {
    return { kind: "in_progress", attemptId: details.attempt_id };
  }
  if (code === "grade_cooldown") {
    const availableAt = isRecord(details) && typeof details.available_at === "string" ? details.available_at : null;
    return { kind: "cooldown", availableAt, message };
  }
  return null;
}

const GRADE_FALLBACK_ORDER: Record<Grade, number> = { intern: 0, junior: 1, middle: 2, senior: 3 };

export function gradeOrder(grade: Grade, grades?: GradeOut[]): number {
  return grades?.find((item) => item.slug === grade)?.order ?? GRADE_FALLBACK_ORDER[grade];
}

const ACTION_PURPOSE: Record<string, AttemptPurpose> = {
  calibrate: "calibration",
  upgrade: "upgrade",
  downgrade: "downgrade",
  reconfirm: "calibration",
  retest: "calibration",
};

/**
 * Назначение попытки на грейд target (§6.3): без категории — калибровка; с категорией — повышение
 * или понижение относительно текущего грейда. Если grade-status прислал действие для этого грейда,
 * берём назначение из него.
 */
export function purposeFor(
  target: Grade,
  status: GradeStatus | undefined,
  grades: GradeOut[] | undefined,
  currentGrade?: Grade | null,
): AttemptPurpose {
  const action = status?.actions.find((item) => item.grade === target);
  const fromAction = action ? ACTION_PURPOSE[action.action] : undefined;
  if (fromAction) return fromAction;
  const current = status ? status.current?.category.grade : currentGrade;
  if (!current) return "calibration";
  const diff = gradeOrder(target, grades) - gradeOrder(current, grades);
  if (diff > 0) return "upgrade";
  if (diff < 0) return "downgrade";
  return "calibration";
}
