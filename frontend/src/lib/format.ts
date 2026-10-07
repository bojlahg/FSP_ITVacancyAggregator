const rubFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });

/** 220000 → «220 000» (неразрывные пробелы, как в ru-RU) */
export function formatNumber(value: number): string {
  return rubFormatter.format(value);
}

/** Все суммы на платформе — на руки, после НДФЛ (docs/implementation.md §2). */
export const NET = "на руки";

/** «220 000 – 260 000 ₽ на руки», «от 220 000 ₽ на руки», «до 260 000 ₽ на руки» */
export function formatSalaryRange(from?: number | null, to?: number | null): string {
  if (from != null && to != null) return `${formatNumber(from)} – ${formatNumber(to)} ₽ ${NET}`;
  if (from != null) return `от ${formatNumber(from)} ₽ ${NET}`;
  if (to != null) return `до ${formatNumber(to)} ₽ ${NET}`;
  return "не указана";
}

/** «Можно добавить до 4 уточняющих»: одна формулировка числа заданий на всех экранах (§10.3). */
export function extraItemsNote(extra: number): string {
  return extra > 0 ? `может добавиться до ${extra} уточняющих у порога грейда` : "";
}

const pluralRules = new Intl.PluralRules("ru-RU");

/** plural(5, ["кандидат", "кандидата", "кандидатов"]) → «кандидатов» */
export function plural(count: number, forms: [one: string, few: string, many: string]): string {
  const rule = pluralRules.select(count);
  if (rule === "one") return forms[0];
  if (rule === "few") return forms[1];
  return forms[2];
}

/** Стаж «3 года 5 мес.»: дробные годы показываем в годах и месяцах. */
export function formatExperience(years: number): string {
  const months = Math.round(years * 12);
  const whole = Math.floor(months / 12);
  const rest = months % 12;
  const parts = [];
  if (whole > 0) parts.push(`${whole} ${plural(whole, ["год", "года", "лет"])}`);
  if (rest > 0) parts.push(`${rest} мес.`);
  return parts.length > 0 ? parts.join(" ") : "меньше месяца";
}

/** «12 дней назад», «сегодня» */
export function formatDaysAgo(days: number): string {
  if (days <= 0) return "сегодня";
  if (days === 1) return "вчера";
  return `${days} ${plural(days, ["день", "дня", "дней"])} назад`;
}

const dateFormatter = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" });
const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
});

/** ISO-дата → «12 октября 2026 г.» */
export function formatDate(iso: string): string {
  return dateFormatter.format(new Date(iso));
}

/** ISO-дата → «12 октября, 14:30» */
export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

/** Доля 0..1 → целые проценты. */
export function toPercent(share: number): number {
  return Math.round(Math.min(1, Math.max(0, share)) * 100);
}

/** Секунды → «мм:сс» */
export function formatTimer(totalSeconds: number): string {
  const safe = Math.max(0, totalSeconds);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/** Сколько полных дней прошло с ISO-даты (для бейджа свежести). */
export function daysSince(iso: string): number {
  const diff = Date.now() - new Date(iso).getTime();
  return Math.max(0, Math.floor(diff / 86_400_000));
}

/** Часы → «5 ч», «2 дн.» */
export function formatHours(hours: number): string {
  if (hours < 24) return `${Math.max(1, Math.round(hours))} ч`;
  return `${Math.round(hours / 24)} дн.`;
}
