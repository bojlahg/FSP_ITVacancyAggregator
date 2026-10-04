/**
 * MOCK-ДАННЫЕ для плейсхолдеров экранов работодателя.
 * Заменить на ответы API (GET /needs/{id}/recommendations, /talent/*) после генерации клиента.
 * Локальные типы ниже — временные: после `npm run gen:api` использовать типы из src/api/schema.d.ts.
 */
import type { ExplanationLine } from "@/components/ExplanationList";
import type { InvitationStatus } from "@/components/StatusBadge";

export interface MockCandidate {
  id: string;
  displayName: string;
  specialization: string;
  grade: string;
  score: number;
  percentile: number;
  hasFsp: boolean;
  testVerified: boolean;
  freshDays: number;
  salaryMin: number;
  city: string;
  format: "office" | "hybrid" | "remote";
  relocation: boolean;
  explanation: ExplanationLine[];
  /** Если задано — кандидат не прошёл жёсткий фильтр и попадает в блок «Вне фильтров». */
  outOfFilterReason?: string;
  topics: { name: string; percent: number }[];
  verifiedStack: string[];
  declaredStack: string[];
  fspAchievements: string[];
  industries: string[];
}

export interface MockNeed {
  id: string;
  title: string;
  specialization: string;
  grade: string;
  salaryFrom: number;
  salaryTo: number;
  format: "office" | "hybrid" | "remote";
  city: string;
  requiredStack: string[];
  desiredStack: string[];
  industry: string;
  version: number;
  candidatesCount: number;
  activeInvites: number;
  published: boolean;
  updatedDaysAgo: number;
}

export interface MockRecommendedCategory {
  specialization: string;
  grade: string;
  match: "exact" | "adjacent_grade" | "adjacent_specialization";
  candidates: number;
  withFsp: number;
  coverage: number;
  note: string;
}

export interface MockEmployerInvitation {
  id: string;
  candidateId: string;
  candidateName: string;
  specialization: string;
  grade: string;
  needTitle: string;
  salaryFrom: number;
  salaryTo: number;
  status: InvitationStatus;
  sentDaysAgo: number;
  declineReason?: string;
}

/** Лимит активных приглашений на потребность (docs/implementation.md §8.6 п.3); в проде — из конфига backend. */
export const MOCK_MAX_ACTIVE_INVITES_PER_NEED = 15;

export const mockNeeds: MockNeed[] = [
  {
    id: "need-backend-payments",
    title: "Backend-разработчик в платёжную команду",
    specialization: "backend",
    grade: "middle",
    salaryFrom: 220_000,
    salaryTo: 260_000,
    format: "hybrid",
    city: "Москва",
    requiredStack: ["Python", "PostgreSQL", "FastAPI"],
    desiredStack: ["Kafka", "Docker"],
    industry: "Финтех",
    version: 2,
    candidatesCount: 37,
    activeInvites: 4,
    published: true,
    updatedDaysAgo: 1,
  },
  {
    id: "need-frontend-retail",
    title: "Frontend-разработчик личного кабинета",
    specialization: "frontend",
    grade: "junior",
    salaryFrom: 120_000,
    salaryTo: 160_000,
    format: "remote",
    city: "Санкт-Петербург",
    requiredStack: ["React", "TypeScript"],
    desiredStack: ["Next.js", "Playwright"],
    industry: "E-commerce",
    version: 1,
    candidatesCount: 52,
    activeInvites: 2,
    published: false,
    updatedDaysAgo: 4,
  },
  {
    id: "need-devops-platform",
    title: "DevOps-инженер платформенной команды",
    specialization: "devops",
    grade: "senior",
    salaryFrom: 330_000,
    salaryTo: 400_000,
    format: "remote",
    city: "Москва",
    requiredStack: ["Kubernetes", "Terraform", "Linux"],
    desiredStack: ["Go", "Prometheus"],
    industry: "Телеком",
    version: 3,
    candidatesCount: 14,
    activeInvites: 6,
    published: true,
    updatedDaysAgo: 7,
  },
];

export const mockRecommendedCategories: MockRecommendedCategory[] = [
  {
    specialization: "backend",
    grade: "middle",
    match: "exact",
    candidates: 37,
    withFsp: 12,
    coverage: 64,
    note: "Точное совпадение · ваша вилка покрывает ожидания 64%",
  },
  {
    specialization: "backend",
    grade: "senior",
    match: "adjacent_grade",
    candidates: 9,
    withFsp: 4,
    coverage: 30,
    note: "Грейд выше · ожидания выше вилки у 70%",
  },
  {
    specialization: "fullstack",
    grade: "middle",
    match: "adjacent_specialization",
    candidates: 21,
    withFsp: 5,
    coverage: 71,
    note: "Смежная специализация · сильный backend-стек",
  },
];

export const mockCandidates: MockCandidate[] = [
  {
    id: "cand-anna",
    displayName: "Анна К.",
    specialization: "backend",
    grade: "middle",
    score: 84,
    percentile: 78,
    hasFsp: true,
    testVerified: true,
    freshDays: 12,
    salaryMin: 240_000,
    city: "Москва",
    format: "hybrid",
    relocation: false,
    explanation: [
      { kind: "positive", text: "Категория совпадает: Middle Backend, подтверждено тестом (78-й перцентиль)" },
      { kind: "positive", text: "PostgreSQL — проверено тестом: «Базы данных» 85%" },
      { kind: "positive", text: "Python — проверено тестом, FastAPI — заявлено" },
      {
        kind: "positive",
        text: "ФСП: 2 место, всероссийский хакатон по продуктовому программированию (роль backend), 2025",
      },
      { kind: "warning", text: "Kafka — нет данных" },
    ],
    topics: [
      { name: "Базы данных", percent: 85 },
      { name: "Python", percent: 81 },
      { name: "HTTP и API", percent: 77 },
      { name: "Алгоритмы", percent: 69 },
      { name: "Архитектура", percent: 62 },
    ],
    verifiedStack: ["Python", "PostgreSQL", "SQL", "Git"],
    declaredStack: ["FastAPI", "Docker", "Redis"],
    fspAchievements: [
      "2 место · Всероссийский хакатон по продуктовому программированию · 2025 · роль backend",
      "Финалист · Кубок России по продуктовому программированию · 2024",
    ],
    industries: ["Финтех", "E-commerce"],
  },
  {
    id: "cand-dmitry",
    displayName: "Дмитрий С.",
    specialization: "backend",
    grade: "middle",
    score: 79,
    percentile: 71,
    hasFsp: false,
    testVerified: true,
    freshDays: 5,
    salaryMin: 230_000,
    city: "Москва",
    format: "office",
    relocation: false,
    explanation: [
      { kind: "positive", text: "Категория совпадает: Middle Backend, подтверждено тестом (71-й перцентиль)" },
      { kind: "positive", text: "Python и FastAPI — проверено тестом" },
      { kind: "positive", text: "Свежий результат: тест 5 дней назад" },
      { kind: "warning", text: "PostgreSQL — заявлено, тестом не проверено" },
    ],
    topics: [
      { name: "Python", percent: 83 },
      { name: "HTTP и API", percent: 80 },
      { name: "Базы данных", percent: 58 },
    ],
    verifiedStack: ["Python", "FastAPI"],
    declaredStack: ["PostgreSQL", "Celery"],
    fspAchievements: [],
    industries: ["Финтех"],
  },
  {
    id: "cand-olga",
    displayName: "Ольга М.",
    specialization: "backend",
    grade: "middle",
    score: 76,
    percentile: 66,
    hasFsp: true,
    testVerified: true,
    freshDays: 40,
    salaryMin: 210_000,
    city: "Казань",
    format: "remote",
    relocation: true,
    explanation: [
      { kind: "positive", text: "Категория совпадает: Middle Backend, подтверждено тестом (66-й перцентиль)" },
      { kind: "positive", text: "ФСП: 1 место, региональные соревнования по продуктовому программированию, 2025" },
      { kind: "positive", text: "Ожидания от 210 000 ₽ — в пределах вилки" },
      { kind: "warning", text: "FastAPI — нет данных, есть только Python" },
    ],
    topics: [
      { name: "Алгоритмы", percent: 88 },
      { name: "Python", percent: 74 },
      { name: "Базы данных", percent: 70 },
    ],
    verifiedStack: ["Python", "PostgreSQL"],
    declaredStack: ["Django"],
    fspAchievements: ["1 место · Региональные соревнования по продуктовому программированию · 2025"],
    industries: ["Госсектор", "EdTech"],
  },
  {
    id: "cand-sergey",
    displayName: "Сергей П.",
    specialization: "backend",
    grade: "senior",
    score: 72,
    percentile: 54,
    hasFsp: true,
    testVerified: true,
    freshDays: 21,
    salaryMin: 290_000,
    city: "Москва",
    format: "hybrid",
    relocation: false,
    explanation: [
      { kind: "positive", text: "Грейд выше целевого: Senior Backend, подтверждено тестом" },
      { kind: "positive", text: "Kafka и PostgreSQL — проверено тестом" },
      { kind: "warning", text: "Ожидания от 290 000 ₽ — выше вилки (до 260 000 ₽)" },
    ],
    topics: [
      { name: "Архитектура", percent: 86 },
      { name: "Базы данных", percent: 82 },
      { name: "Очереди сообщений", percent: 79 },
    ],
    verifiedStack: ["Python", "PostgreSQL", "Kafka"],
    declaredStack: ["Kubernetes"],
    fspAchievements: ["3 место · Всероссийские соревнования по информационной безопасности · 2024"],
    industries: ["Финтех", "Телеком"],
  },
  {
    id: "cand-timur",
    displayName: "Тимур А.",
    specialization: "fullstack",
    grade: "middle",
    score: 68,
    percentile: 61,
    hasFsp: false,
    testVerified: false,
    freshDays: 75,
    salaryMin: 200_000,
    city: "Новосибирск",
    format: "remote",
    relocation: false,
    explanation: [
      { kind: "positive", text: "Смежная специализация: Fullstack Middle" },
      { kind: "positive", text: "Python — подтверждено регулярным заданием" },
      { kind: "warning", text: "Последнее подтверждённое действие 75 дней назад" },
    ],
    topics: [
      { name: "JavaScript", percent: 77 },
      { name: "Python", percent: 64 },
    ],
    verifiedStack: ["TypeScript"],
    declaredStack: ["Python", "PostgreSQL", "React"],
    fspAchievements: [],
    industries: ["E-commerce"],
  },
  {
    id: "cand-elena",
    displayName: "Елена В.",
    specialization: "backend",
    grade: "middle",
    score: 64,
    percentile: 49,
    hasFsp: false,
    testVerified: true,
    freshDays: 2,
    salaryMin: 330_000,
    city: "Москва",
    format: "office",
    relocation: false,
    outOfFilterReason: "Ожидания от 330 000 ₽ выше верхней границы вилки больше чем на 30%",
    explanation: [
      { kind: "positive", text: "Категория совпадает: Middle Backend, подтверждено тестом" },
      { kind: "warning", text: "Ожидания от 330 000 ₽ — выше вилки (до 260 000 ₽)" },
    ],
    topics: [{ name: "Python", percent: 72 }],
    verifiedStack: ["Python"],
    declaredStack: ["PostgreSQL"],
    fspAchievements: [],
    industries: ["Медтех"],
  },
  {
    id: "cand-artem",
    displayName: "Артём Н.",
    specialization: "backend",
    grade: "middle",
    score: 61,
    percentile: 44,
    hasFsp: true,
    testVerified: true,
    freshDays: 30,
    salaryMin: 200_000,
    city: "Екатеринбург",
    format: "office",
    relocation: false,
    outOfFilterReason: "Только офис в другом городе, релокация не рассматривается",
    explanation: [
      { kind: "positive", text: "Категория совпадает: Middle Backend" },
      { kind: "warning", text: "Офис в Екатеринбурге, релокация не рассматривается" },
    ],
    topics: [{ name: "Базы данных", percent: 75 }],
    verifiedStack: ["Python", "PostgreSQL"],
    declaredStack: [],
    fspAchievements: ["Участник · Чемпионат России по спортивному программированию · 2024"],
    industries: ["Промышленность"],
  },
];

export const mockEmployerInvitations: MockEmployerInvitation[] = [
  {
    id: "inv-1",
    candidateId: "cand-anna",
    candidateName: "Анна К.",
    specialization: "backend",
    grade: "middle",
    needTitle: "Backend-разработчик в платёжную команду",
    salaryFrom: 220_000,
    salaryTo: 260_000,
    status: "accepted",
    sentDaysAgo: 2,
  },
  {
    id: "inv-2",
    candidateId: "cand-dmitry",
    candidateName: "Дмитрий С.",
    specialization: "backend",
    grade: "middle",
    needTitle: "Backend-разработчик в платёжную команду",
    salaryFrom: 220_000,
    salaryTo: 260_000,
    status: "viewed",
    sentDaysAgo: 3,
  },
  {
    id: "inv-3",
    candidateId: "cand-sergey",
    candidateName: "Сергей П.",
    specialization: "backend",
    grade: "senior",
    needTitle: "Backend-разработчик в платёжную команду",
    salaryFrom: 220_000,
    salaryTo: 260_000,
    status: "declined",
    sentDaysAgo: 6,
    declineReason: "Зарплата",
  },
  {
    id: "inv-4",
    candidateId: "cand-olga",
    candidateName: "Ольга М.",
    specialization: "backend",
    grade: "middle",
    needTitle: "Backend-разработчик в платёжную команду",
    salaryFrom: 220_000,
    salaryTo: 260_000,
    status: "sent",
    sentDaysAgo: 0,
  },
  {
    id: "inv-5",
    candidateId: "cand-timur",
    candidateName: "Тимур А.",
    specialization: "fullstack",
    grade: "middle",
    needTitle: "Frontend-разработчик личного кабинета",
    salaryFrom: 120_000,
    salaryTo: 160_000,
    status: "expired",
    sentDaysAgo: 16,
  },
];

export const mockDeclineStats = [
  { reason: "Зарплата", count: 3 },
  { reason: "Формат работы", count: 1 },
  { reason: "Стек", count: 1 },
];

/** Каталог категорий: число кандидатов по «специализация × грейд». */
export const mockCategoryCatalog: Record<string, Record<string, number>> = {
  backend: { intern: 18, junior: 64, middle: 37, senior: 9 },
  frontend: { intern: 22, junior: 52, middle: 41, senior: 11 },
  qa: { intern: 15, junior: 33, middle: 19, senior: 6 },
  devops: { intern: 4, junior: 12, middle: 17, senior: 14 },
  data: { intern: 11, junior: 26, middle: 15, senior: 5 },
};

export function findMockCandidate(id: string | undefined): MockCandidate | undefined {
  return mockCandidates.find((candidate) => candidate.id === id);
}

export function findMockNeed(id: string | undefined): MockNeed | undefined {
  return mockNeeds.find((need) => need.id === id);
}
