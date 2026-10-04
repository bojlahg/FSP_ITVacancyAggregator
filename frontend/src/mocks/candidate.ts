/**
 * MOCK-ДАННЫЕ для плейсхолдеров кабинета кандидата.
 * Заменить на ответы API (GET /candidates/me/*, /vacancies, /tests/attempts/*) после генерации клиента.
 */
import type { ExplanationLine } from "@/components/ExplanationList";
import type { ApplicationStatus, InvitationStatus } from "@/components/StatusBadge";

export interface MockCandidateInvitation {
  id: string;
  company: string;
  title: string;
  description: string;
  salaryFrom: number;
  salaryTo: number;
  status: InvitationStatus;
  sentDaysAgo: number;
  expiresInDays: number;
  whyYou: ExplanationLine[];
}

export interface MockVacancy {
  id: string;
  company: string;
  title: string;
  specialization: string;
  grade: string;
  salaryFrom: number;
  salaryTo: number;
  format: "office" | "hybrid" | "remote";
  city: string;
  score: number;
  explanation: ExplanationLine[];
}

export interface MockApplication {
  id: string;
  company: string;
  title: string;
  salaryFrom: number;
  salaryTo: number;
  status: ApplicationStatus;
  sentDaysAgo: number;
}

export const mockMe = {
  displayName: "Анна Кузнецова",
  shortName: "Анна К.",
  specialization: "backend",
  grade: "middle",
  percentile: 78,
  theta: 0.42,
  profileCompleteness: 70,
  testedDaysAgo: 12,
  validMonthsLeft: 11,
  nextGradeChangeInDays: 78,
};

export const mockCandidateInvitations: MockCandidateInvitation[] = [
  {
    id: "inv-1",
    company: "Демо Банк",
    title: "Backend-разработчик в платёжную команду",
    description:
      "Команда платёжного шлюза: Python, FastAPI, PostgreSQL. Гибрид в Москве, 2 дня в офисе. Ищем человека, который любит надёжные системы и понятный код.",
    salaryFrom: 220_000,
    salaryTo: 260_000,
    status: "sent",
    sentDaysAgo: 0,
    expiresInDays: 14,
    whyYou: [
      { kind: "positive", text: "Ваша категория Backend · Middle точно совпадает с запросом" },
      { kind: "positive", text: "PostgreSQL — проверено тестом: «Базы данных» 85%" },
      { kind: "positive", text: "ФСП: 2 место, всероссийский хакатон по продуктовому программированию, 2025" },
      { kind: "warning", text: "Kafka — желательный навык, у вас нет данных" },
    ],
  },
  {
    id: "inv-2",
    company: "Демо Ритейл",
    title: "Python-разработчик сервиса рекомендаций",
    description: "Сервис персональных рекомендаций для 5 млн покупателей. Полностью удалённо.",
    salaryFrom: 200_000,
    salaryTo: 240_000,
    status: "viewed",
    sentDaysAgo: 3,
    expiresInDays: 11,
    whyYou: [
      { kind: "positive", text: "Python — проверено тестом" },
      { kind: "positive", text: "Удалённый формат совпадает с вашими предпочтениями" },
      { kind: "warning", text: "Верхняя граница вилки ниже ваших ожиданий" },
    ],
  },
];

export const mockVacancies: MockVacancy[] = [
  {
    id: "vac-1",
    company: "Демо Банк",
    title: "Backend-разработчик в платёжную команду",
    specialization: "backend",
    grade: "middle",
    salaryFrom: 220_000,
    salaryTo: 260_000,
    format: "hybrid",
    city: "Москва",
    score: 84,
    explanation: [
      { kind: "positive", text: "Категория совпадает: Backend · Middle" },
      { kind: "positive", text: "Обязательный стек проверен тестом: Python, PostgreSQL" },
      { kind: "warning", text: "Kafka — желательный навык, нет данных" },
    ],
  },
  {
    id: "vac-2",
    company: "Демо Телеком",
    title: "Разработчик биллинга",
    specialization: "backend",
    grade: "senior",
    salaryFrom: 300_000,
    salaryTo: 360_000,
    format: "remote",
    city: "Москва",
    score: 66,
    explanation: [
      { kind: "positive", text: "Специализация совпадает, грейд выше вашего" },
      { kind: "neutral", text: "Можно сдать тест на Senior через 78 дней" },
    ],
  },
];

export const mockApplications: MockApplication[] = [
  {
    id: "app-1",
    company: "Демо Банк",
    title: "Backend-разработчик в платёжную команду",
    salaryFrom: 220_000,
    salaryTo: 260_000,
    status: "viewed",
    sentDaysAgo: 2,
  },
  {
    id: "app-2",
    company: "Демо Логистика",
    title: "Python-разработчик интеграций",
    salaryFrom: 180_000,
    salaryTo: 230_000,
    status: "rejected",
    sentDaysAgo: 9,
  },
];

export const mockTopicResults = [
  { name: "Базы данных", percent: 85 },
  { name: "Python", percent: 81 },
  { name: "HTTP и API", percent: 77 },
  { name: "Алгоритмы", percent: 69 },
  { name: "Архитектура", percent: 62 },
];

export const mockGradeHistory = [
  { date: "23.09.2026", event: "Тест Backend · Middle — пройден", result: "78-й перцентиль" },
  { date: "23.09.2026", event: "Опрос: рекомендована специализация Backend", result: "Backend 0.71 · Fullstack 0.22" },
];

export const mockTestQuestion = {
  index: 3,
  total: 8,
  topic: "Python",
  text: "Что выведет этот код?",
  code: "def add(item, bucket=[]):\n    bucket.append(item)\n    return bucket\n\nadd(1)\nprint(add(2))",
  options: ["[2]", "[1, 2]", "[2, 1]", "Ошибка TypeError"],
};
