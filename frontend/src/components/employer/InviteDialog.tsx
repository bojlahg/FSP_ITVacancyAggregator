import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, Eye, Loader2, Lock, Send } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";
import { ExplanationList } from "@/components/ExplanationList";
import { FormAlert } from "@/components/FormAlert";
import { CandidateCategoryBadge } from "@/components/CategoryBadge";
import { ScoreTile } from "@/components/employer/ScoreTile";
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
  type CandidateMatch,
  type EmployerProfile,
  type InvitationForEmployer,
  isCompanyProfileRequired,
  isInvitationLimit,
  type Need,
  useCompany,
  useCreateInvitation,
  useNeeds,
} from "@/lib/employer-queries";
import { cn } from "@/lib/utils";

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
  /** Совпадение с этой потребностью: те же строки «почему вам» уйдут кандидату снимком при отправке. */
  match?: CandidateMatch | null;
  onSent?: (invitation: InvitationForEmployer) => void;
}

export function InviteDialog({ open, onOpenChange, candidate, need, match, onSent }: InviteDialogProps) {
  const company = useCompany();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* На телефоне — шторка снизу: кнопка отправки всегда видна, форма прокручивается над ней */}
      <DialogContent
        className={cn(
          "sm:max-w-2xl",
          "max-sm:top-auto max-sm:bottom-0 max-sm:left-0 max-sm:max-h-[calc(100dvh-2.5rem)] max-sm:max-w-none max-sm:translate-x-0 max-sm:translate-y-0 max-sm:gap-4 max-sm:rounded-t-[14px] max-sm:rounded-b-none max-sm:border-x-0 max-sm:border-b-0 max-sm:px-4 max-sm:pt-2 max-sm:pb-0",
          "max-sm:data-[state=closed]:slide-out-to-bottom max-sm:data-[state=closed]:zoom-out-100 max-sm:data-[state=open]:slide-in-from-bottom max-sm:data-[state=open]:zoom-in-100",
        )}
      >
        <span className="mx-auto h-1 w-9 rounded-full bg-border sm:hidden" aria-hidden />
        <DialogHeader>
          <DialogTitle>Приглашение · {candidate?.display_name}</DialogTitle>
          <DialogDescription>
            Вилка от–до обязательна: кандидат увидит её и объяснение «почему вам» до начала общения.
          </DialogDescription>
        </DialogHeader>
        {company.isPending ? (
          <div className="grid gap-3 max-sm:pb-4" role="status" aria-busy="true" aria-label="Загрузка">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-10 w-2/3" />
          </div>
        ) : company.data && !company.data.company_name ? (
          <CompanyRequired />
        ) : (
          candidate && (
            <InviteForm
              candidate={candidate}
              need={need ?? null}
              match={need && match ? match : null}
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
      <DialogFooter className="max-sm:pb-4">
        <DialogClose asChild>
          <Button variant="ghost">Закрыть</Button>
        </DialogClose>
      </DialogFooter>
    </>
  );
}

interface InviteFormProps {
  candidate: { id: number; display_name: string };
  need: Need | null;
  match: CandidateMatch | null;
  company: EmployerProfile | null;
  onDone: (invitation: InvitationForEmployer) => void;
}

function InviteForm({ candidate, need, match, company, onDone }: InviteFormProps) {
  const candidateId = candidate.id;
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

  const salaryField = (name: "salaryFrom" | "salaryTo", id: string, label: string) => (
    <FormField id={id} label={label} error={errors[name]?.message}>
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        min={0}
        step={1000}
        className="font-mono font-semibold max-sm:h-12"
        aria-invalid={!!errors[name]}
        {...register(name, { valueAsNumber: true })}
      />
    </FormField>
  );

  return (
    <>
      <form id="invite-form" className="grid gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormAlert message={formError} />
        {match && (
          <div className="flex flex-wrap items-center gap-2.5 rounded-lg bg-muted p-2">
            <ScoreTile score={match.score} tone="card" size="sm" />
            <span className="font-mono text-sm font-semibold">{candidate.display_name}</span>
            <CandidateCategoryBadge candidate={match.candidate} />
          </div>
        )}
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
        <fieldset className="grid min-w-0 gap-2">
          <legend className="mb-2 text-sm font-medium">
            Вилка, ₽ на руки <span className="font-normal text-muted-foreground">— обязательно</span>
          </legend>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4">
            {salaryField("salaryFrom", "invite-salary-from", "Вилка от *")}
            {salaryField("salaryTo", "invite-salary-to", "Вилка до *")}
            <FormField
              id="invite-expires"
              label="Срок ответа, дней"
              error={errors.expiresInDays?.message}
              className="col-span-2 sm:col-span-1"
            >
              <Input
                id="invite-expires"
                type="number"
                min={1}
                max={30}
                className="max-sm:h-12"
                aria-invalid={!!errors.expiresInDays}
                {...register("expiresInDays", { valueAsNumber: true })}
              />
            </FormField>
          </div>
        </fieldset>
        {match && match.explanation.lines.length > 0 && (
          <div className="grid gap-2.5 rounded-[10px] border border-border-subtle px-3.5 py-3">
            <span className="flex items-center gap-2 text-sm font-medium">
              <Eye className="size-4 text-primary" aria-hidden /> Кандидат увидит «почему вам»
            </span>
            <ExplanationList items={match.explanation.lines} />
            <span className="text-xs text-muted-foreground">
              Считается тем же кодом, что и score, и уходит снимком при отправке — правке не подлежит.
            </span>
          </div>
        )}
        <FormField id="invite-title" label="Заголовок *" error={errors.title?.message}>
          <Input id="invite-title" className="max-sm:h-12" aria-invalid={!!errors.title} {...register("title")} />
        </FormField>
        <FormField id="invite-message" label="Описание предложения *" error={errors.message?.message}>
          <Textarea id="invite-message" rows={4} aria-invalid={!!errors.message} {...register("message")} />
        </FormField>
        <fieldset className="grid min-w-0 gap-4 rounded-lg border p-4 sm:grid-cols-2">
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
        <p className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2.5 text-sm">
          <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          Контакты кандидата откроются вам, когда он примет приглашение.
        </p>
        {need && need.stats.invitations_limit > 0 && (
          <p className="font-mono text-xs text-muted-foreground">
            Активных слотов: {need.stats.invitations_active} из {need.stats.invitations_limit}
          </p>
        )}
      </form>
      <DialogFooter className="max-sm:sticky max-sm:bottom-0 max-sm:-mx-4 max-sm:gap-1 max-sm:border-t max-sm:border-border-subtle max-sm:bg-background max-sm:px-4 max-sm:pt-3 max-sm:pb-4">
        <DialogClose asChild>
          <Button variant="ghost" className="max-sm:h-11 max-sm:text-base">
            Отмена
          </Button>
        </DialogClose>
        <Button type="submit" form="invite-form" disabled={create.isPending} className="max-sm:h-12 max-sm:text-base">
          {create.isPending ? <Loader2 className="animate-spin" /> : <Send />} Отправить приглашение
        </Button>
      </DialogFooter>
    </>
  );
}
