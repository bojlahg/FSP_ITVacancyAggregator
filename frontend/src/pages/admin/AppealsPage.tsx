import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Scale } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { CategoryBadge } from "@/components/CategoryBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { apiError } from "@/lib/api-error";
import { formatDateTime } from "@/lib/format";
import { type AdminAppeal, type AppealStatus, useAdminAppeals, useResolveAppeal } from "@/lib/legal-queries";

const TABS: { value: AppealStatus | "all"; label: string }[] = [
  { value: "open", label: "На рассмотрении" },
  { value: "resolved", label: "Рассмотренные" },
  { value: "all", label: "Все" },
];

/** Возражения кандидатов против категории (152-ФЗ ст. 16): отвечает человек, грейд сам не меняется. */
export default function AppealsPage() {
  const [tab, setTab] = useState<AppealStatus | "all">("open");
  const appeals = useAdminAppeals(tab === "all" ? undefined : tab);

  return (
    <>
      <PageHeader
        eyebrow="Администратор"
        title="Обращения по грейду"
        description="Кандидаты оспаривают категорию, присвоенную тестом. Проверьте попытку и ответьте: ответ увидит кандидат в разделе «Категория и грейд». Сам ответ категорию не меняет — её меняет только повторный тест."
      />
      <Tabs value={tab} onValueChange={(value) => setTab(value as AppealStatus | "all")} className="mb-4">
        <TabsList className="max-w-full">
          {TABS.map((item) => (
            // Вкладки — фильтр списка без отдельных панелей
            <TabsTrigger key={item.value} value={item.value} aria-controls={undefined}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {appeals.isPending ? (
        <SkeletonCards count={2} />
      ) : appeals.isError ? (
        <ErrorState description={apiError(appeals.error).message} onRetry={() => void appeals.refetch()} />
      ) : appeals.data.length === 0 ? (
        <EmptyState icon={Scale} title="Обращений нет" description="Новые обращения кандидатов появятся здесь." />
      ) : (
        <div className="grid gap-4">
          {appeals.data.map((appeal) => (
            <AppealCard key={appeal.id} appeal={appeal} />
          ))}
        </div>
      )}
    </>
  );
}

const replySchema = z.object({
  reply: z.string().trim().min(1, "Напишите ответ кандидату").max(2000, "Не длиннее 2000 символов"),
});
type ReplyValues = z.infer<typeof replySchema>;

function AppealCard({ appeal }: { appeal: AdminAppeal }) {
  const resolve = useResolveAppeal();
  const fieldId = `reply-${appeal.id}`;
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ReplyValues>({ resolver: zodResolver(replySchema), defaultValues: { reply: "" } });

  const onSubmit = async (values: ReplyValues) => {
    try {
      await resolve.mutateAsync({ id: appeal.id, reply: values.reply });
    } catch (err) {
      setError("root.server", { message: apiError(err).message });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>
            {appeal.candidate_name} <span className="font-mono text-xs text-muted-foreground">#{appeal.candidate_id}</span>
          </span>
          <Badge variant={appeal.status === "open" ? "soft" : "muted"}>
            {appeal.status === "open" ? "на рассмотрении" : "рассмотрено"}
          </Badge>
        </CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-2">
          <CategoryBadge specialization={appeal.category.specialization} grade={appeal.category.grade} />
          <span className="font-mono text-xs tabular-nums">
            θ̂ {appeal.theta.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          {!appeal.category_is_current && <Badge variant="muted">категория уже сменилась</Badge>}
          <span className="font-mono text-xs">{formatDateTime(appeal.created_at)}</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="break-words whitespace-pre-line">{appeal.comment}</p>
        {appeal.status === "resolved" ? (
          <div className="rounded-md bg-primary-tint p-3">
            <div className="mb-1 font-mono text-xs font-bold text-primary">
              Ответ{appeal.resolved_at ? ` · ${formatDateTime(appeal.resolved_at)}` : ""}
            </div>
            <p className="break-words whitespace-pre-line">{appeal.reply}</p>
          </div>
        ) : (
          <form className="grid gap-3" onSubmit={handleSubmit(onSubmit)} noValidate>
            <FormField id={fieldId} label="Ответ кандидату" error={errors.reply?.message}>
              <Textarea id={fieldId} rows={3} maxLength={2000} aria-invalid={!!errors.reply} {...register("reply")} />
            </FormField>
            <FormAlert message={errors.root?.server?.message ?? null} />
            <Button type="submit" className="w-fit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="animate-spin" />}
              Ответить и закрыть
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
