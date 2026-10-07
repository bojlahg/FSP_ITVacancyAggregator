import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, Loader2, Send } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import {
  type EmployerProfile,
  type InvitationForEmployer,
  isCompanyProfileRequired,
  isInvitationLimit,
  type Need,
  useCompany,
  useCreateInvitation,
  useNeeds,
} from "@/lib/employer-queries";

const DEFAULT_EXPIRES_DAYS = 14;

// Вилка от–до обязательна в приглашении (инвариант продукта, docs/implementation.md §8.1 п.6).
const inviteSchema = z
  .object({
    needId: z.string(),
    title: z.string().trim().min(3, "Укажите заголовок"),
    message: z.string().trim().min(10, "Опишите предложение хотя бы в паре предложений"),
    salaryFrom: z.number({ error: "Укажите сумму" }).int().positive("Сумма должна быть больше нуля"),
    salaryTo: z.number({ error: "Укажите сумму" }).int().positive("Сумма должна быть больше нуля"),
    contactName: z.string().trim().min(2, "Укажите контактное лицо"),
    contactEmail: z.union([z.literal(""), z.email("Введите корректный email")]),
    contactTelegram: z.string().trim(),
    contactPhone: z.string().trim(),
    expiresInDays: z.number({ error: "Укажите срок" }).int().min(1, "Минимум 1 день").max(30, "Максимум 30 дней"),
  })
  .refine((values) => values.salaryTo >= values.salaryFrom, {
    path: ["salaryTo"],
    message: "Верхняя граница не может быть меньше нижней",
  })
  .refine((values) => !!(values.contactEmail || values.contactTelegram || values.contactPhone), {
    path: ["contactTelegram"],
    message: "Укажите хотя бы один способ связи: Telegram, email или телефон",
  });

type InviteValues = z.infer<typeof inviteSchema>;

const fieldMap = {
  title: "title",
  message: "message",
  salary_from: "salaryFrom",
  salary_to: "salaryTo",
  name: "contactName",
  email: "contactEmail",
  telegram: "contactTelegram",
  phone: "contactPhone",
  expires_in_days: "expiresInDays",
} as const;

interface InviteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  candidate: { id: number; display_name: string } | null;
  /** Потребность, из которой приглашаем: заголовок, вилка и привязка подставляются из неё. */
  need?: Need | null;
  onSent?: (invitation: InvitationForEmployer) => void;
}

export function InviteDialog({ open, onOpenChange, candidate, need, onSent }: InviteDialogProps) {
  const company = useCompany();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Приглашение · {candidate?.display_name}</DialogTitle>
          <DialogDescription>
            Кандидат увидит вилку и объяснение «почему вам» до начала общения. Его контакты откроются вам после того, как
            он примет приглашение.
          </DialogDescription>
        </DialogHeader>
        {company.isPending ? (
          <div className="grid gap-3" role="status" aria-busy="true" aria-label="Загрузка">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-10 w-2/3" />
          </div>
        ) : company.data && !company.data.company_name ? (
          <CompanyRequired />
        ) : (
          candidate && (
            <InviteForm
              candidateId={candidate.id}
              need={need ?? null}
              company={company.data ?? null}
              onDone={(invitation) => {
                onSent?.(invitation);
                onOpenChange(false);
              }}
            />
          )
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Кандидат видит компанию по названию: без него приглашение не отправить (409 company_profile_required). */
function CompanyRequired() {
  return (
    <>
      <div
        role="alert"
        className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive-tint px-3 py-2 text-sm text-destructive-strong"
      >
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>
          Заполните название компании в профиле перед отправкой приглашения: кандидат увидит, кто его приглашает.{" "}
          <Link to="/employer/company" className="font-medium underline underline-offset-2">
            Перейти в профиль компании
          </Link>
        </span>
      </div>
      <DialogFooter>
        <DialogClose asChild>
          <Button variant="ghost">Закрыть</Button>
        </DialogClose>
      </DialogFooter>
    </>
  );
}

interface InviteFormProps {
  candidateId: number;
  need: Need | null;
  company: EmployerProfile | null;
  onDone: (invitation: InvitationForEmployer) => void;
}

function InviteForm({ candidateId, need, company, onDone }: InviteFormProps) {
  const create = useCreateInvitation();
  // Без потребности даём выбрать её из списка: тогда снимок объяснения и лимит приглашений считаются по ней.
  const needs = useNeeds();
  const [formError, setFormError] = useState<string | null>(null);
  const [companyMissing, setCompanyMissing] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    setValue,
    formState: { errors },
  } = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: {
      needId: need ? String(need.id) : "",
      title: need?.title ?? "",
      message: need?.team_description ?? "",
      salaryFrom: need?.salary_from,
      salaryTo: need?.salary_to,
      contactName: company?.contact_name ?? "",
      contactEmail: company?.contact_email ?? "",
      contactTelegram: company?.contact_telegram ?? "",
      contactPhone: company?.contact_phone ?? "",
      expiresInDays: DEFAULT_EXPIRES_DAYS,
    },
  });

  const pickNeed = (id: string) => {
    const picked = needs.data?.find((item) => String(item.id) === id);
    if (!picked) return;
    setValue("title", picked.title);
    setValue("salaryFrom", picked.salary_from);
    setValue("salaryTo", picked.salary_to);
  };

  const onSubmit = (values: InviteValues) => {
    setFormError(null);
    create.mutate(
      {
        candidate_id: candidateId,
        need_id: values.needId ? Number(values.needId) : null,
        title: values.title,
        message: values.message,
        salary_from: values.salaryFrom,
        salary_to: values.salaryTo,
        contact_method: {
          name: values.contactName,
          email: values.contactEmail || null,
          telegram: values.contactTelegram || null,
          phone: values.contactPhone || null,
        },
        expires_in_days: values.expiresInDays,
      },
      {
        onSuccess: onDone,
        onError: (err) => {
          if (isCompanyProfileRequired(err)) {
            setCompanyMissing(true);
            return;
          }
          if (isInvitationLimit(err)) {
            const limit = need?.stats.invitations_limit;
            setFormError(
              `По этой потребности уже ${limit ? `${limit} активных приглашений` : "максимум активных приглашений"}. Слот освободится, когда кандидат ответит или истечёт срок, — либо отзовите одно из приглашений.`,
            );
            return;
          }
          if (!applyValidationErrors(err, setError, fieldMap)) setFormError(apiError(err).message);
        },
      },
    );
  };

  if (companyMissing) return <CompanyRequired />;

  return (
    <>
      <form id="invite-form" className="grid gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormAlert message={formError} />
        {!need && (
          <FormField id="invite-need" label="Потребность" hint="Необязательно: приглашение можно отправить и без неё">
            <Select
              id="invite-need"
              {...register("needId", { onChange: (event) => pickNeed(event.target.value) })}
              disabled={needs.isPending}
            >
              <option value="">Без привязки к потребности</option>
              {needs.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title} · {item.category.label}
                </option>
              ))}
            </Select>
          </FormField>
        )}
        <FormField id="invite-title" label="Заголовок *" error={errors.title?.message}>
          <Input id="invite-title" aria-invalid={!!errors.title} {...register("title")} />
        </FormField>
        <FormField id="invite-message" label="Описание предложения *" error={errors.message?.message}>
          <Textarea id="invite-message" rows={4} aria-invalid={!!errors.message} {...register("message")} />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-3">
          <FormField id="invite-salary-from" label="Вилка от, ₽ на руки *" error={errors.salaryFrom?.message}>
            <Input
              id="invite-salary-from"
              type="number"
              inputMode="numeric"
              min={0}
              step={1000}
              aria-invalid={!!errors.salaryFrom}
              {...register("salaryFrom", { valueAsNumber: true })}
            />
          </FormField>
          <FormField id="invite-salary-to" label="Вилка до, ₽ на руки *" error={errors.salaryTo?.message}>
            <Input
              id="invite-salary-to"
              type="number"
              inputMode="numeric"
              min={0}
              step={1000}
              aria-invalid={!!errors.salaryTo}
              {...register("salaryTo", { valueAsNumber: true })}
            />
          </FormField>
          <FormField id="invite-expires" label="Срок ответа, дней" error={errors.expiresInDays?.message}>
            <Input
              id="invite-expires"
              type="number"
              min={1}
              max={30}
              aria-invalid={!!errors.expiresInDays}
              {...register("expiresInDays", { valueAsNumber: true })}
            />
          </FormField>
        </div>
        <fieldset className="grid gap-4 rounded-lg border p-4 sm:grid-cols-2">
          <legend className="px-1 font-mono text-xs font-bold tracking-wider uppercase">Как с вами связаться</legend>
          <FormField id="invite-contact-name" label="Контактное лицо *" error={errors.contactName?.message}>
            <Input id="invite-contact-name" aria-invalid={!!errors.contactName} {...register("contactName")} />
          </FormField>
          <FormField id="invite-contact-telegram" label="Telegram" error={errors.contactTelegram?.message}>
            <Input
              id="invite-contact-telegram"
              placeholder="@username"
              aria-invalid={!!errors.contactTelegram}
              {...register("contactTelegram")}
            />
          </FormField>
          <FormField id="invite-contact-email" label="Email" error={errors.contactEmail?.message}>
            <Input
              id="invite-contact-email"
              type="email"
              aria-invalid={!!errors.contactEmail}
              {...register("contactEmail")}
            />
          </FormField>
          <FormField id="invite-contact-phone" label="Телефон" error={errors.contactPhone?.message}>
            <Input id="invite-contact-phone" type="tel" aria-invalid={!!errors.contactPhone} {...register("contactPhone")} />
          </FormField>
        </fieldset>
      </form>
      <DialogFooter>
        <DialogClose asChild>
          <Button variant="ghost">Отмена</Button>
        </DialogClose>
        <Button type="submit" form="invite-form" disabled={create.isPending}>
          {create.isPending ? <Loader2 className="animate-spin" /> : <Send />} Отправить приглашение
        </Button>
      </DialogFooter>
    </>
  );
}
