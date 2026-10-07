import type { Grade, SurveyResult } from "@/lib/testing-queries";

/**
 * Черновик онбординга в sessionStorage: F5 не сбрасывает опрос, выбор специализации и грейда.
 * Живёт до закрытия вкладки и удаляется, когда онбординг дошёл до теста. Хранилище может быть
 * недоступно (приватный режим, запрет cookies) — тогда онбординг просто работает без черновика.
 */
export interface OnboardingDraft {
  step?: number;
  surveyPage?: number;
  /** Ответы опроса по id вопроса — значения полей формы как есть. */
  surveyAnswers?: Record<string, unknown>;
  /** Названия выбранных навыков, чтобы чипы после перезагрузки показывали имя, а не id. */
  skillNames?: Record<string, string>;
  surveyResult?: SurveyResult | null;
  pickedSpecialization?: string | null;
  grade?: Grade | null;
}

const keyFor = (userId: number) => `itscout:onboarding-draft:${userId}`;

export function loadOnboardingDraft(userId: number | undefined): OnboardingDraft {
  if (userId === undefined) return {};
  try {
    const raw = window.sessionStorage.getItem(keyFor(userId));
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as OnboardingDraft) : {};
  } catch {
    return {};
  }
}

export function saveOnboardingDraft(userId: number | undefined, patch: OnboardingDraft): void {
  if (userId === undefined) return;
  try {
    window.sessionStorage.setItem(keyFor(userId), JSON.stringify({ ...loadOnboardingDraft(userId), ...patch }));
  } catch {
    // Черновик — удобство, а не данные: без хранилища онбординг работает как раньше.
  }
}

export function clearOnboardingDraft(userId: number | undefined): void {
  if (userId === undefined) return;
  try {
    window.sessionStorage.removeItem(keyFor(userId));
  } catch {
    // см. saveOnboardingDraft
  }
}
