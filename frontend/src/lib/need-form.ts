import { z } from "zod";
import type { NeedDraft } from "@/lib/employer-queries";

// Вилка от–до обязательна (инвариант продукта, docs/implementation.md §8.1 п.2).
export const needSchema = z
  .object({
    title: z.string().trim().min(3, "Укажите название"),
    specialization: z.string().min(1, "Выберите специализацию"),
    grade: z.string().min(1, "Выберите грейд"),
    requiredSkills: z.array(z.string()).min(1, "Добавьте хотя бы один обязательный навык"),
    optionalSkills: z.array(z.string()),
    teamDescription: z.string().trim().max(2000, "Не больше 2000 символов"),
    industry: z.string(),
    workFormat: z.enum(["", "office", "hybrid", "remote"]),
    city: z.string().trim(),
    salaryFrom: z.number({ error: "Укажите сумму" }).int().positive("Сумма должна быть больше нуля"),
    salaryTo: z.number({ error: "Укажите сумму" }).int().positive("Сумма должна быть больше нуля"),
  })
  .refine((values) => values.salaryTo >= values.salaryFrom, {
    path: ["salaryTo"],
    message: "Верхняя граница не может быть меньше нижней",
  });

export type NeedFormValues = z.infer<typeof needSchema>;

export const needFieldMap = {
  title: "title",
  specialization: "specialization",
  grade: "grade",
  required_skills: "requiredSkills",
  optional_skills: "optionalSkills",
  team_description: "teamDescription",
  industry: "industry",
  work_format: "workFormat",
  city: "city",
  salary_from: "salaryFrom",
  salary_to: "salaryTo",
} as const;

/** Черновик разбора или сохранённая потребность → значения формы. */
export function needFormValues(draft: NeedDraft): Partial<NeedFormValues> {
  return {
    title: draft.title ?? "",
    specialization: draft.specialization ?? "",
    grade: draft.grade ?? "",
    requiredSkills: draft.required_skills ?? [],
    optionalSkills: draft.optional_skills ?? [],
    teamDescription: draft.team_description ?? "",
    industry: draft.industry ?? "",
    workFormat: draft.work_format ?? "",
    city: draft.city ?? "",
    salaryFrom: draft.salary_from ?? undefined,
    salaryTo: draft.salary_to ?? undefined,
  };
}

export const EMPTY_NEED_FORM: Partial<NeedFormValues> = {
  title: "",
  specialization: "",
  grade: "",
  requiredSkills: [],
  optionalSkills: [],
  teamDescription: "",
  industry: "",
  workFormat: "",
  city: "",
};
