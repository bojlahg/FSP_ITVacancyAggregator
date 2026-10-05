import { z } from "zod";
import type { CandidateProfileUpdate } from "@/lib/profile-queries";
import type { CandidateProfile } from "@/lib/testing-queries";

const digits = z.string().trim().regex(/^\d*$/, "Только цифры");
const optionalText = (max: number) => z.string().trim().max(max, `Не больше ${max} символов`);

const experienceSchema = z
  .object({
    company: z.string().trim().min(1, "Укажите компанию").max(200, "Не больше 200 символов"),
    position: z.string().trim().min(1, "Укажите должность").max(200, "Не больше 200 символов"),
    // <input type="month">: «2024-06» или пусто
    startedOn: z.string(),
    endedOn: z.string(),
    description: optionalText(2000),
  })
  .refine((item) => !item.startedOn || !item.endedOn || item.endedOn >= item.startedOn, {
    path: ["endedOn"],
    message: "Окончание раньше начала",
  });

export const profileSchema = z
  .object({
    firstName: optionalText(100),
    lastName: optionalText(100),
    middleName: optionalText(100),
    contactEmail: z.union([z.literal(""), z.email("Некорректный email")]),
    phone: optionalText(32),
    telegram: optionalText(64),
    city: optionalText(100),
    relocation: z.boolean(),
    workFormats: z.array(z.enum(["office", "hybrid", "remote"])),
    salaryMin: digits,
    salaryMax: digits,
    experienceYears: z
      .string()
      .trim()
      .regex(/^(\d{1,2}([.,]\d)?)?$/, "Число лет, например 3 или 2,5"),
    roles: z.array(z.string()),
    industriesExp: z.array(z.string()),
    softSkills: z.array(z.string()),
    about: optionalText(4000),
    declaredSkills: z.array(z.string()),
    experience: z.array(experienceSchema),
  })
  .refine((values) => !values.salaryMin || !values.salaryMax || Number(values.salaryMax) >= Number(values.salaryMin), {
    path: ["salaryMax"],
    message: "Верхняя граница не может быть меньше нижней",
  });

export type ProfileFormValues = z.infer<typeof profileSchema>;

/** Ошибки 422 с сервера → поля формы. */
export const profileFieldMap = {
  first_name: "firstName",
  last_name: "lastName",
  middle_name: "middleName",
  contact_email: "contactEmail",
  phone: "phone",
  telegram: "telegram",
  city: "city",
  salary_min: "salaryMin",
  salary_max: "salaryMax",
  experience_years: "experienceYears",
  about: "about",
} as const;

/** Поля API (from_resume) → поля формы, чтобы подсветить предзаполненное из резюме. */
export const FROM_RESUME_FIELDS: Record<string, keyof ProfileFormValues> = {
  ...profileFieldMap,
  relocation: "relocation",
  work_formats: "workFormats",
  roles: "roles",
  industries_exp: "industriesExp",
  soft_skills: "softSkills",
  declared_skills: "declaredSkills",
  experience: "experience",
};

const toMonth = (value?: string | null) => (value ? value.slice(0, 7) : "");
const fromMonth = (value: string) => (value ? `${value}-01` : null);
const toNumber = (value: string) => (value ? Number(value.replace(",", ".")) : null);

type ProfileSource = Pick<
  CandidateProfileUpdate,
  | "first_name"
  | "last_name"
  | "middle_name"
  | "contact_email"
  | "phone"
  | "telegram"
  | "city"
  | "relocation"
  | "work_formats"
  | "salary_min"
  | "salary_max"
  | "experience_years"
  | "roles"
  | "industries_exp"
  | "soft_skills"
  | "about"
  | "experience"
>;

function baseValues(source: ProfileSource, declaredSkills: string[]): ProfileFormValues {
  return {
    firstName: source.first_name ?? "",
    lastName: source.last_name ?? "",
    middleName: source.middle_name ?? "",
    contactEmail: source.contact_email ?? "",
    phone: source.phone ?? "",
    telegram: source.telegram ?? "",
    city: source.city ?? "",
    relocation: source.relocation ?? false,
    workFormats: source.work_formats ?? [],
    salaryMin: source.salary_min != null ? String(source.salary_min) : "",
    salaryMax: source.salary_max != null ? String(source.salary_max) : "",
    experienceYears: source.experience_years != null ? String(source.experience_years).replace(".", ",") : "",
    roles: source.roles ?? [],
    industriesExp: source.industries_exp ?? [],
    softSkills: source.soft_skills ?? [],
    about: source.about ?? "",
    declaredSkills,
    experience: (source.experience ?? []).map((item) => ({
      company: item.company,
      position: item.position,
      startedOn: toMonth(item.started_on),
      endedOn: toMonth(item.ended_on),
      description: item.description ?? "",
    })),
  };
}

/** Сохранённый профиль → форма. В форме только заявленные навыки: проверенные тестом не редактируются. */
export function formFromProfile(profile: CandidateProfile): ProfileFormValues {
  const declared = profile.skills.filter((skill) => skill.sources.includes("declared")).map((skill) => skill.skill_id);
  return baseValues(profile, declared);
}

/** Предзаполнение из резюме → форма. */
export function formFromPrefill(prefill: CandidateProfileUpdate): ProfileFormValues {
  return baseValues(prefill, (prefill.declared_skills ?? []).map((item) => item.skill_id));
}

/** Поля профиля, которых нет в форме: PUT заменяет профиль целиком, поэтому передаём их как есть. */
type KeptFields = Pick<CandidateProfile, "search_status" | "industries_pref">;

/** Форма → тело PUT /candidates/me (статус поиска и интересные отрасли меняются в других местах). */
export function profileBody(values: ProfileFormValues, kept: KeptFields): CandidateProfileUpdate {
  return {
    first_name: values.firstName || null,
    last_name: values.lastName || null,
    middle_name: values.middleName || null,
    contact_email: values.contactEmail || null,
    phone: values.phone || null,
    telegram: values.telegram || null,
    city: values.city || null,
    relocation: values.relocation,
    work_formats: values.workFormats,
    salary_min: toNumber(values.salaryMin),
    salary_max: toNumber(values.salaryMax),
    experience_years: toNumber(values.experienceYears),
    roles: values.roles,
    industries_exp: values.industriesExp,
    industries_pref: kept.industries_pref,
    soft_skills: values.softSkills,
    about: values.about || null,
    search_status: kept.search_status,
    declared_skills: values.declaredSkills.map((skillId) => ({ skill_id: skillId })),
    experience: values.experience.map((item) => ({
      company: item.company,
      position: item.position,
      started_on: fromMonth(item.startedOn),
      ended_on: fromMonth(item.endedOn),
      description: item.description || null,
    })),
  };
}
