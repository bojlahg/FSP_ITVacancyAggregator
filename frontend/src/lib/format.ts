const rubFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });

/** 220000 → «220 000» (неразрывные пробелы, как в ru-RU) */
export function formatNumber(value: number): string {
  return rubFormatter.format(value);
}

/** «220 000 – 260 000 ₽», «от 220 000 ₽», «до 260 000 ₽» */
export function formatSalaryRange(from?: number | null, to?: number | null): string {
  if (from != null && to != null) return `${formatNumber(from)} – ${formatNumber(to)} ₽`;
  if (from != null) return `от ${formatNumber(from)} ₽`;
  if (to != null) return `до ${formatNumber(to)} ₽`;
  return "не указана";
}

const pluralRules = new Intl.PluralRules("ru-RU");

/** plural(5, ["кандидат", "кандидата", "кандидатов"]) → «кандидатов» */
export function plural(count: number, forms: [one: string, few: string, many: string]): string {
  const rule = pluralRules.select(count);
  if (rule === "one") return forms[0];
  if (rule === "few") return forms[1];
  return forms[2];
}

/** «12 дней назад», «сегодня» */
export function formatDaysAgo(days: number): string {
  if (days <= 0) return "сегодня";
  if (days === 1) return "вчера";
  return `${days} ${plural(days, ["день", "дня", "дней"])} назад`;
}
