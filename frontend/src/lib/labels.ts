// Подписи для слагов справочников (docs/implementation.md §5).
// TODO: когда появится GET /catalog/*, брать названия из API, а здесь оставить только фолбэк.

export const SPECIALIZATION_LABELS: Record<string, string> = {
  backend: "Backend",
  frontend: "Frontend",
  qa: "QA",
  devops: "DevOps",
  data: "Data / ML",
  fullstack: "Fullstack",
  mobile: "Mobile",
  analyst: "Аналитика",
  gamedev: "GameDev",
};

export const SPECIALIZATION_FULL_LABELS: Record<string, string> = {
  backend: "Backend-разработка",
  frontend: "Frontend-разработка",
  qa: "Тестирование (QA)",
  devops: "DevOps / SRE",
  data: "Data Science / ML",
  fullstack: "Fullstack-разработка",
  mobile: "Мобильная разработка",
  analyst: "Системная и бизнес-аналитика",
  gamedev: "Разработка игр",
};

export const GRADE_LABELS: Record<string, string> = {
  intern: "Intern",
  junior: "Junior",
  middle: "Middle",
  senior: "Senior",
};

export const WORK_FORMAT_LABELS: Record<string, string> = {
  office: "Офис",
  hybrid: "Гибрид",
  remote: "Удалённо",
};

export function specializationLabel(slug: string): string {
  return SPECIALIZATION_LABELS[slug] ?? slug;
}

export function gradeLabel(slug: string): string {
  return GRADE_LABELS[slug] ?? slug;
}
