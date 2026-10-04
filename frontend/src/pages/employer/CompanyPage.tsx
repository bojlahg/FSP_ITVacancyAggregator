import { zodResolver } from "@hookform/resolvers/zod";
import { Save } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

// MOCK: список отраслей придёт из GET /catalog/industries
const industries = ["Финтех", "E-commerce", "Госсектор", "Телеком", "Медтех", "Геймдев", "Промышленность", "EdTech", "Медиа", "Другое"];

const companySchema = z.object({
  name: z.string().trim().min(2, "Укажите название компании"),
  inn: z
    .string()
    .trim()
    .regex(/^(\d{10}|\d{12})?$/, "ИНН — 10 или 12 цифр"),
  industry: z.string().min(1, "Выберите отрасль"),
  description: z.string().trim().max(2000, "Не больше 2000 символов"),
  website: z.union([z.literal(""), z.url("Введите адрес сайта, например https://example.ru")]),
  recruiterContact: z.string().trim().min(3, "Укажите контакт рекрутера"),
});

type CompanyValues = z.infer<typeof companySchema>;

export default function CompanyPage() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<CompanyValues>({
    resolver: zodResolver(companySchema),
    // MOCK: значения из GET /employers/me
    defaultValues: {
      name: "Демо Банк",
      inn: "",
      industry: "Финтех",
      description: "Цифровой банк для малого бизнеса. Разрабатываем платёжную платформу и мобильный банк.",
      website: "",
      recruiterContact: "Мария, @demo_bank_hr",
    },
  });

  const onSubmit = (values: CompanyValues) => {
    // TODO: PUT /employers/me
    console.info("[company] TODO: PUT /employers/me", values);
  };

  return (
    <>
      <PageHeader
        eyebrow="Профиль компании"
        title="Профиль компании"
        description="Кандидаты видят название, отрасль и описание в приглашении. ИНН необязателен — он понадобится для верификации работодателя."
      />
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>О компании</CardTitle>
          <CardDescription>Поля со звёздочкой обязательны</CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <FormField id="company-name" label="Название *" error={errors.name?.message}>
              <Input id="company-name" aria-invalid={!!errors.name} {...register("name")} />
            </FormField>
            <FormField id="company-inn" label="ИНН" error={errors.inn?.message} hint="Необязательно">
              <Input id="company-inn" inputMode="numeric" aria-invalid={!!errors.inn} {...register("inn")} />
            </FormField>
            <FormField id="company-industry" label="Отрасль *" error={errors.industry?.message}>
              <Select id="company-industry" aria-invalid={!!errors.industry} {...register("industry")}>
                {industries.map((industry) => (
                  <option key={industry} value={industry}>
                    {industry}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField id="company-website" label="Сайт" error={errors.website?.message}>
              <Input
                id="company-website"
                type="url"
                placeholder="https://"
                aria-invalid={!!errors.website}
                {...register("website")}
              />
            </FormField>
            <FormField
              id="company-description"
              label="Описание"
              error={errors.description?.message}
              className="sm:col-span-2"
            >
              <Textarea id="company-description" rows={4} aria-invalid={!!errors.description} {...register("description")} />
            </FormField>
            <FormField
              id="company-recruiter"
              label="Контакт рекрутера *"
              error={errors.recruiterContact?.message}
              hint="Кандидат увидит его после принятия приглашения"
              className="sm:col-span-2"
            >
              <Input id="company-recruiter" aria-invalid={!!errors.recruiterContact} {...register("recruiterContact")} />
            </FormField>
          </CardContent>
          <CardFooter className="mt-5 border-t border-border-subtle pt-5">
            <Button type="submit" disabled={isSubmitting || !isDirty}>
              <Save /> Сохранить
            </Button>
          </CardFooter>
        </form>
      </Card>
    </>
  );
}
