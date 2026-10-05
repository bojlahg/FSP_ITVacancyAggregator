import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Loader2, Save, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { AtsIntegrationCard } from "@/components/employer/AtsIntegrationCard";
import { EmailNotificationsCard } from "@/components/EmailNotificationsCard";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import {
  type EmployerProfile,
  type EmployerReputation,
  useCompany,
  useIndustries,
  useUpdateCompany,
} from "@/lib/employer-queries";
import { formatHours, formatNumber, toPercent } from "@/lib/format";

const companySchema = z.object({
  companyName: z.string().trim().min(2, "Укажите название компании"),
  inn: z
    .string()
    .trim()
    .regex(/^(\d{10}|\d{12})?$/, "ИНН — 10 или 12 цифр"),
  industry: z.string(),
  description: z.string().trim().max(2000, "Не больше 2000 символов"),
  website: z.union([z.literal(""), z.url("Введите адрес сайта, например https://example.ru")]),
  contactName: z.string().trim().min(2, "Укажите контактное лицо"),
  contactEmail: z.union([z.literal(""), z.email("Введите корректный email")]),
  contactPhone: z.string().trim(),
  contactTelegram: z.string().trim(),
});

type CompanyValues = z.infer<typeof companySchema>;

const fieldMap = {
  company_name: "companyName",
  inn: "inn",
  industry: "industry",
  description: "description",
  website: "website",
  contact_name: "contactName",
  contact_email: "contactEmail",
  contact_phone: "contactPhone",
  contact_telegram: "contactTelegram",
} as const;

function toValues(company: EmployerProfile): CompanyValues {
  return {
    companyName: company.company_name ?? "",
    inn: company.inn ?? "",
    industry: company.industry ?? "",
    description: company.description ?? "",
    website: company.website ?? "",
    contactName: company.contact_name ?? "",
    contactEmail: company.contact_email ?? "",
    contactPhone: company.contact_phone ?? "",
    contactTelegram: company.contact_telegram ?? "",
  };
}

export default function CompanyPage() {
  const company = useCompany();

  return (
    <>
      <PageHeader
        eyebrow="Профиль компании"
        title="Профиль компании"
        description="Кандидаты видят название, отрасль, описание и показатели добросовестности в каждом приглашении. ИНН необязателен — он понадобится для верификации работодателя."
      />
      {company.isPending ? (
        <SkeletonCards count={2} className="max-w-5xl" />
      ) : company.isError ? (
        <ErrorState description={apiError(company.error).message} onRetry={() => void company.refetch()} />
      ) : (
        <div className="grid max-w-6xl gap-4 lg:grid-cols-[1fr_320px]">
          <CompanyForm key={company.data.id} company={company.data} />
          <ReputationCard reputation={company.data.reputation} />
        </div>
      )}
      {company.isSuccess && (
        <div className="mt-4 grid max-w-6xl gap-4">
          <EmailNotificationsCard role="employer" />
          <AtsIntegrationCard />
        </div>
      )}
    </>
  );
}

function CompanyForm({ company }: { company: EmployerProfile }) {
  const update = useUpdateCompany();
  const industries = useIndustries();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const {
    register,
    control,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isDirty },
  } = useForm<CompanyValues>({ resolver: zodResolver(companySchema), defaultValues: toValues(company) });

  const onSubmit = (values: CompanyValues) => {
    setFormError(null);
    setSaved(false);
    update.mutate(
      {
        company_name: values.companyName,
        inn: values.inn || null,
        industry: values.industry || null,
        description: values.description || null,
        website: values.website || null,
        contact_name: values.contactName,
        contact_email: values.contactEmail || null,
        contact_phone: values.contactPhone || null,
        contact_telegram: values.contactTelegram || null,
      },
      {
        onSuccess: (savedCompany) => {
          reset(toValues(savedCompany));
          setSaved(true);
        },
        onError: (err) => {
          if (!applyValidationErrors(err, setError, fieldMap)) setFormError(apiError(err).message);
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>О компании</CardTitle>
        <CardDescription>Поля со звёздочкой обязательны</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <FormAlert message={formError} className="sm:col-span-2" />
          <FormField id="company-name" label="Название *" error={errors.companyName?.message}>
            <Input id="company-name" aria-invalid={!!errors.companyName} {...register("companyName")} />
          </FormField>
          <FormField id="company-inn" label="ИНН" error={errors.inn?.message} hint="Необязательно">
            <Input id="company-inn" inputMode="numeric" aria-invalid={!!errors.inn} {...register("inn")} />
          </FormField>
          <FormField id="company-industry" label="Отрасль" error={errors.industry?.message}>
            <Controller
              control={control}
              name="industry"
              render={({ field }) => (
                <Select
                  id="company-industry"
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  disabled={industries.isPending}
                >
                  <option value="">Не указана</option>
                  {industries.data?.map((item) => (
                    <option key={item.slug} value={item.slug}>
                      {item.name}
                    </option>
                  ))}
                  {field.value && industries.data && !industries.data.some((item) => item.slug === field.value) && (
                    <option value={field.value}>{field.value}</option>
                  )}
                </Select>
              )}
            />
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
          <FormField id="company-description" label="Описание" error={errors.description?.message} className="sm:col-span-2">
            <Textarea id="company-description" rows={4} aria-invalid={!!errors.description} {...register("description")} />
          </FormField>

          <div className="pt-2 font-mono text-xs font-bold tracking-wider uppercase sm:col-span-2">Контакт рекрутера</div>
          <p className="-mt-2 text-xs text-muted-foreground sm:col-span-2">
            Подставляется в приглашения по умолчанию — кандидат увидит его, когда примет приглашение.
          </p>
          <FormField id="company-contact-name" label="Контактное лицо *" error={errors.contactName?.message}>
            <Input id="company-contact-name" aria-invalid={!!errors.contactName} {...register("contactName")} />
          </FormField>
          <FormField id="company-contact-telegram" label="Telegram" error={errors.contactTelegram?.message}>
            <Input id="company-contact-telegram" placeholder="@username" {...register("contactTelegram")} />
          </FormField>
          <FormField id="company-contact-email" label="Email" error={errors.contactEmail?.message}>
            <Input
              id="company-contact-email"
              type="email"
              aria-invalid={!!errors.contactEmail}
              {...register("contactEmail")}
            />
          </FormField>
          <FormField id="company-contact-phone" label="Телефон" error={errors.contactPhone?.message}>
            <Input id="company-contact-phone" type="tel" {...register("contactPhone")} />
          </FormField>
        </CardContent>
        <CardFooter className="mt-5 gap-3 border-t border-border-subtle pt-5">
          <Button type="submit" disabled={update.isPending || !isDirty}>
            {update.isPending ? <Loader2 className="animate-spin" /> : <Save />} Сохранить
          </Button>
          {saved && !isDirty && (
            <span className="flex items-center gap-1.5 text-sm text-primary" role="status">
              <CheckCircle2 className="size-4" aria-hidden /> Сохранено
            </span>
          )}
        </CardFooter>
      </form>
    </Card>
  );
}

function rate(value: number | null): string {
  return value === null ? "—" : `${toPercent(value)}%`;
}

function ReputationCard({ reputation }: { reputation: EmployerReputation }) {
  const rows = [
    { label: "Отправлено приглашений", value: formatNumber(reputation.invitations_sent) },
    { label: "Доля принятых", value: rate(reputation.acceptance_rate) },
    { label: "Доля отозванных", value: rate(reputation.withdrawn_rate) },
    {
      label: "Медиана ответа на отклики",
      value: reputation.median_response_hours === null ? "—" : formatHours(reputation.median_response_hours),
    },
  ];
  return (
    <Card className="h-fit">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" aria-hidden /> Репутация
        </CardTitle>
        <CardDescription>
          Кандидат видит эти показатели в приглашении. Каждое приглашение у нас — с реальной вилкой.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-3">
          {rows.map((row) => (
            <div key={row.label} className="flex items-baseline justify-between gap-3 border-b border-border-subtle pb-2 last:border-0">
              <dt className="text-sm text-muted-foreground">{row.label}</dt>
              <dd className="font-mono text-lg font-extrabold tabular-nums">{row.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
