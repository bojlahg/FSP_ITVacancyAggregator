import { zodResolver } from "@hookform/resolvers/zod";
import { Send } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { FormField } from "@/components/FormField";
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

// Вилка от–до обязательна в приглашении (инвариант продукта, docs/implementation.md §8.1 п.6).
const inviteSchema = z
  .object({
    title: z.string().trim().min(3, "Укажите заголовок"),
    description: z.string().trim().min(10, "Опишите предложение хотя бы в паре предложений"),
    salaryFrom: z.number({ error: "Укажите сумму" }).int().positive("Сумма должна быть больше нуля"),
    salaryTo: z.number({ error: "Укажите сумму" }).int().positive("Сумма должна быть больше нуля"),
    contactMethod: z.enum(["recruiter", "telegram", "email", "phone"]),
    expiresInDays: z.number({ error: "Укажите срок" }).int().min(1, "Минимум 1 день").max(30, "Максимум 30 дней"),
  })
  .refine((values) => values.salaryTo >= values.salaryFrom, {
    path: ["salaryTo"],
    message: "Верхняя граница не может быть меньше нижней",
  });

export type InviteValues = z.infer<typeof inviteSchema>;

interface InviteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  candidateName: string;
  defaults?: Partial<InviteValues>;
}

export function InviteDialog({ open, onOpenChange, candidateName, defaults }: InviteDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: {
      title: "",
      description: "",
      contactMethod: "recruiter",
      expiresInDays: 14,
      ...defaults,
    },
  });

  const onSubmit = (values: InviteValues) => {
    // TODO: POST /invitations (useMutation) — снимок объяснения прикладывает backend.
    console.info("[invite] TODO: POST /invitations", values);
    reset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Приглашение · {candidateName}</DialogTitle>
          <DialogDescription>
            Кандидат увидит вилку и объяснение «почему вам» до начала общения. Контакты откроются после принятия.
          </DialogDescription>
        </DialogHeader>
        <form id="invite-form" className="grid gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <FormField id="invite-title" label="Заголовок" error={errors.title?.message}>
            <Input id="invite-title" aria-invalid={!!errors.title} {...register("title")} />
          </FormField>
          <FormField id="invite-description" label="Описание предложения" error={errors.description?.message}>
            <Textarea id="invite-description" aria-invalid={!!errors.description} {...register("description")} />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="invite-salary-from" label="Вилка от, ₽" error={errors.salaryFrom?.message}>
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
            <FormField id="invite-salary-to" label="Вилка до, ₽" error={errors.salaryTo?.message}>
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
            <FormField id="invite-contact" label="Способ связи">
              <Select id="invite-contact" {...register("contactMethod")}>
                <option value="recruiter">Через рекрутера</option>
                <option value="telegram">Telegram</option>
                <option value="email">Email</option>
                <option value="phone">Телефон</option>
              </Select>
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
        </form>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Отмена</Button>
          </DialogClose>
          <Button type="submit" form="invite-form" disabled={isSubmitting}>
            <Send /> Отправить приглашение
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
