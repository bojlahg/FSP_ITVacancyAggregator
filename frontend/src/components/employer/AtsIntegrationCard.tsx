import { zodResolver } from "@hookform/resolvers/zod";
import { Check, Copy, KeyRound, Loader2, RefreshCw, Send, Trash2, Webhook as WebhookIcon } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import { formatDateTime } from "@/lib/format";
import {
  type ApiKeyCreated,
  type Webhook,
  type WebhookDelivery,
  useApiKeys,
  useCreateApiKey,
  useDeleteWebhook,
  useRetryDelivery,
  useRevokeApiKey,
  useRotateWebhookSecret,
  useSaveWebhook,
  useTestWebhook,
  useWebhook,
  useWebhookDeliveries,
} from "@/lib/integrations-queries";

const EVENT_LABELS: Record<string, string> = {
  "invitation.accepted": "Приглашение принято",
  "invitation.declined": "Приглашение отклонено",
  "application.created": "Новый отклик",
  ping: "Проверка",
};

const STATUS: Record<WebhookDelivery["status"], { label: string; variant: "soft" | "muted" | "destructive" }> = {
  delivered: { label: "доставлено", variant: "soft" },
  pending: { label: "в очереди", variant: "muted" },
  failed: { label: "не доставлено", variant: "destructive" },
};

/** Интеграция с ATS (docs/anti-fraud-ats.md §2): API-ключи и webhook. */
export function AtsIntegrationCard() {
  return (
    <Card className="max-w-6xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <WebhookIcon className="size-4 text-primary" aria-hidden /> Интеграция с ATS
        </CardTitle>
        <CardDescription>
          Подключите Huntflow, Talantix, Potok или свою систему: по API-ключу ATS работает с теми же методами, что и
          кабинет, а webhook сообщает о принятых приглашениях и откликах. Документация — в{" "}
          <a href="/api/docs" className="font-medium text-primary underline-offset-4 hover:underline">
            Swagger
          </a>
          .
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <ApiKeysSection />
        <Separator className="lg:hidden" />
        <WebhookSection />
      </CardContent>
    </Card>
  );
}

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => setCopied(true));
      }}
      aria-label={label}
    >
      {copied ? <Check /> : <Copy />}
      {copied ? "Скопировано" : "Копировать"}
    </Button>
  );
}

const keySchema = z.object({ name: z.string().trim().min(1, "Назовите ключ").max(100, "Не длиннее 100 символов") });

function ApiKeysSection() {
  const keys = useApiKeys();
  const create = useCreateApiKey();
  const revoke = useRevokeApiKey();
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<z.infer<typeof keySchema>>({ resolver: zodResolver(keySchema), defaultValues: { name: "" } });

  const onSubmit = (values: z.infer<typeof keySchema>) =>
    create.mutate(values.name, {
      onSuccess: (key) => {
        setCreated(key);
        reset();
      },
      onError: (err) => {
        if (!applyValidationErrors(err, setError, { name: "name" })) {
          setError("root.server", { message: apiError(err).message });
        }
      },
    });

  return (
    <section className="grid content-start gap-4">
      <h3 className="flex items-center gap-2 font-mono text-sm font-bold">
        <KeyRound className="size-4 text-primary" aria-hidden /> API-ключи
      </h3>
      <form className="flex items-start gap-2" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormField id="api-key-name" label="Название" error={errors.name?.message} className="flex-1">
          <Input id="api-key-name" placeholder="Например, Huntflow" aria-invalid={!!errors.name} {...register("name")} />
        </FormField>
        <Button type="submit" className="mt-6" disabled={create.isPending}>
          {create.isPending && <Loader2 className="animate-spin" />}
          Выпустить
        </Button>
      </form>
      <FormAlert message={errors.root?.server?.message ?? null} />

      {created && (
        <div className="grid gap-2 rounded-lg border border-primary bg-primary-tint p-3 text-sm" role="status">
          <div className="font-medium">Ключ «{created.name}» — скопируйте сейчас, он больше не будет показан</div>
          <code className="rounded bg-background px-2 py-1 font-mono text-xs break-all">{created.key}</code>
          <div className="flex flex-wrap items-center gap-2">
            <CopyButton value={created.key} label="Копировать API-ключ" />
            <span className="text-xs text-muted-foreground">Передавайте в заголовке X-API-Key</span>
          </div>
        </div>
      )}

      {keys.isPending ? (
        <SkeletonCards count={1} />
      ) : keys.isError ? (
        <ErrorState description={apiError(keys.error).message} onRetry={() => void keys.refetch()} />
      ) : keys.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">Ключей пока нет.</p>
      ) : (
        <ul className="divide-y divide-border-subtle text-sm">
          {keys.data.map((key) => (
            <li key={key.id} className="flex items-center justify-between gap-3 py-2">
              <div className="min-w-0">
                <div className="font-medium">{key.name}</div>
                <div className="font-mono text-xs text-muted-foreground">
                  itsk_{key.prefix}_… · {key.last_used_at ? `использован ${formatDateTime(key.last_used_at)}` : "не использовался"}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(key.id)}
                aria-label={`Отозвать ключ ${key.name}`}
              >
                <Trash2 /> Отозвать
              </Button>
            </li>
          ))}
        </ul>
      )}
      {revoke.isError && <FormAlert message={apiError(revoke.error).message} />}
    </section>
  );
}

function WebhookSection() {
  const webhook = useWebhook();
  if (webhook.isPending) return <SkeletonCards count={1} />;
  if (webhook.isError) {
    return <ErrorState description={apiError(webhook.error).message} onRetry={() => void webhook.refetch()} />;
  }
  return <WebhookForm key={webhook.data?.updated_at ?? "new"} hook={webhook.data} />;
}

const webhookSchema = z.object({
  url: z.url({ protocol: /^https?$/, message: "Нужен адрес https://…" }).max(500, "Не длиннее 500 символов"),
  enabled: z.boolean(),
});

function WebhookForm({ hook }: { hook: Webhook | null }) {
  const save = useSaveWebhook();
  const rotate = useRotateWebhookSecret();
  const remove = useDeleteWebhook();
  const test = useTestWebhook();
  const deliveries = useWebhookDeliveries(hook !== null);
  const retry = useRetryDelivery();
  const [showSecret, setShowSecret] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isDirty },
  } = useForm<z.infer<typeof webhookSchema>>({
    resolver: zodResolver(webhookSchema),
    defaultValues: { url: hook?.url ?? "", enabled: hook?.enabled ?? true },
  });

  const onSubmit = (values: z.infer<typeof webhookSchema>) =>
    save.mutate(values, {
      onError: (err) => {
        const { status, message } = apiError(err);
        if (status === 422 && !applyValidationErrors(err, setError, { url: "url", enabled: "enabled" })) {
          setError("url", { type: "server", message });
        } else if (status !== 422) {
          setError("root.server", { message });
        }
      },
    });

  const mutationError = [rotate, remove, test, retry].find((item) => item.isError)?.error;

  return (
    <section className="grid content-start gap-4">
      <h3 className="flex items-center gap-2 font-mono text-sm font-bold">
        <WebhookIcon className="size-4 text-primary" aria-hidden /> Webhook
      </h3>
      <form className="grid gap-3" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormField id="webhook-url" label="Адрес приёма событий" error={errors.url?.message}>
          <Input
            id="webhook-url"
            type="url"
            placeholder="https://ats.example.ru/hooks/itscout"
            aria-invalid={!!errors.url}
            {...register("url")}
          />
        </FormField>
        <label className="flex items-center gap-3 text-sm">
          <Checkbox {...register("enabled")} /> Отправлять события
        </label>
        <FormAlert message={errors.root?.server?.message ?? null} />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={save.isPending || (hook !== null && !isDirty)}>
            {save.isPending && <Loader2 className="animate-spin" />}
            {hook ? "Сохранить" : "Подключить"}
          </Button>
          {hook && (
            <Button type="button" variant="ghost" disabled={remove.isPending} onClick={() => remove.mutate()}>
              <Trash2 /> Удалить
            </Button>
          )}
        </div>
      </form>

      {hook && (
        <>
          <div className="grid gap-2 text-sm">
            <div className="text-xs text-muted-foreground">
              Секрет подписи: заголовок <code className="font-mono">X-ITScout-Signature: t=…,v1=…</code> — HMAC-SHA256
              от «t.тело запроса»
            </div>
            <code className="rounded bg-muted px-2 py-1 font-mono text-xs break-all">
              {showSecret ? hook.secret : "•".repeat(24)}
            </code>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setShowSecret((value) => !value)}>
                {showSecret ? "Скрыть" : "Показать"}
              </Button>
              <CopyButton value={hook.secret} label="Копировать секрет подписи" />
              <Button type="button" variant="outline" size="sm" disabled={rotate.isPending} onClick={() => rotate.mutate()}>
                <RefreshCw /> Новый секрет
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {(hook.events ?? []).map((event) => (
                <Badge key={event} variant="muted" title={event}>
                  {EVENT_LABELS[event] ?? event}
                </Badge>
              ))}
            </div>
          </div>

          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">Последние доставки</span>
              <Button type="button" size="sm" variant="secondary" disabled={test.isPending} onClick={() => test.mutate()}>
                <Send /> Отправить проверку
              </Button>
            </div>
            {deliveries.isPending ? (
              <SkeletonCards count={1} />
            ) : deliveries.isError ? (
              <ErrorState description={apiError(deliveries.error).message} onRetry={() => void deliveries.refetch()} />
            ) : deliveries.data.length === 0 ? (
              <p className="text-sm text-muted-foreground">Событий ещё не было.</p>
            ) : (
              <ul className="divide-y divide-border-subtle text-sm">
                {deliveries.data.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3 py-2">
                    <div className="min-w-0">
                      <div className="font-medium">{EVENT_LABELS[item.event] ?? item.event}</div>
                      <div className="font-mono text-xs text-muted-foreground">
                        {formatDateTime(item.created_at)} · попыток {item.attempts}
                        {item.last_error && ` · ${item.last_error}`}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant={STATUS[item.status].variant}>{STATUS[item.status].label}</Badge>
                      {item.status === "failed" && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={retry.isPending}
                          onClick={() => retry.mutate(item.id)}
                        >
                          Повторить
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
      {mutationError && <FormAlert message={apiError(mutationError).message} />}
    </section>
  );
}
