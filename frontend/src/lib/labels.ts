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

export const ATTEMPT_PURPOSE_LABELS: Record<string, string> = {
  calibration: "Калибровка",
  upgrade: "Повышение",
  downgrade: "Понижение",
  vacancy_preview: "Проверка под вакансию",
};

export const ATTEMPT_STATUS_LABELS: Record<string, string> = {
  in_progress: "Идёт",
  completed: "Завершена",
  abandoned: "Прервана",
  expired: "Истекла",
};

export const ATTEMPT_RESULT_LABELS: Record<string, string> = {
  fail: "Не пройден",
  pass: "Пройден",
  confident_pass: "Пройден уверенно",
};

export function workFormatsLabel(formats: readonly string[]): string {
  return formats.length === 0 ? "формат не указан" : formats.map((item) => WORK_FORMAT_LABELS[item] ?? item).join(" / ");
}

/** Причины отказа от приглашения (§8.5). */
export const DECLINE_REASON_LABELS: Record<string, string> = {
  salary: "Зарплата",
  stack: "Стек",
  work_format: "Формат работы",
  company: "Компания",
  not_looking: "Не ищу работу",
  other: "Другое",
};

/** Насколько рекомендованная категория совпадает с потребностью (§8.1 п.3). */
export const CATEGORY_FIT_LABELS: Record<string, string> = {
  exact: "Точное совпадение",
  adjacent_grade: "Смежный грейд",
  adjacent_specialization: "Смежная специализация",
  adjacent_both: "Смежные грейд и специализация",
};

/** Статус навыка: проверено тестом / подтверждено ФСП / заявлено (§8.3, компонент skills). */
export const SKILL_STATUS_LABELS: Record<string, string> = {
  verified: "проверено тестом",
  fsp_confirmed: "подтверждено ФСП",
  task_confirmed: "подтверждено заданием",
  declared: "заявлено",
};

export const FSP_LEVEL_LABELS: Record<string, string> = {
  international: "Международный",
  national: "Всероссийский",
  interregional: "Межрегиональный",
  regional: "Региональный",
  municipal: "Муниципальный",
};

export const NEED_STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  active: "Активна",
  closed: "Закрыта",
};

export const ASSIGNMENT_STATUS_LABELS: Record<string, string> = {
  offered: "Активно",
  submitted: "Решение отправлено",
  expired: "Срок истёк",
  skipped: "Пропущено",
};

export const TASK_KIND_LABELS: Record<string, string> = {
  auto: "Автопроверка",
  approach: "Подход к решению",
};

export const GRADED_BY_LABELS: Record<string, string> = {
  auto: "автопроверка",
  llm: "чек-лист",
  employer: "оценка работодателя",
};

export const ITEM_KIND_LABELS: Record<string, string> = {
  single_choice: "один вариант",
  multi_choice: "несколько вариантов",
  numeric: "числовой ответ",
  ordering: "упорядочивание",
  code_output: "что выведет код",
  sql_result: "результат SQL",
  open_approach: "открытый подход",
};
