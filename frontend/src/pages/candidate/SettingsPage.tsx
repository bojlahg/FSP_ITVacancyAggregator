import { useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Trash2, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { FspLinkCard } from "@/components/candidate/FspLinkCard";
import { EmailNotificationsCard } from "@/components/EmailNotificationsCard";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { apiError } from "@/lib/api-error";
import { authStore } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import {
  type ConsentKind,
  type PrivacySettings,
  type SearchStatus,
  useCompanies,
  useConsents,
  useDeleteAccount,
  useUpdateConsent,
  useUpdatePrivacy,
  useUpdateSearchStatus,
} from "@/lib/settings-queries";
import { useCandidateMe } from "@/lib/testing-queries";

const privacyOptions: { key: "show_last_name" | "show_fsp" | "show_salary"; label: string }[] = [
  { key: "show_last_name", label: "Показывать фамилию до контакта" },
  { key: "show_fsp", label: "Показывать достижения ФСП" },
  { key: "show_salary", label: "Показывать зарплатные ожидания" },
];

const searchStatuses: { value: SearchStatus; label: string }[] = [
  { value: "active", label: "Активно ищу" },
  { value: "open", label: "Открыт к предложениям" },
  { value: "hidden", label: "Не ищу — профиль скрыт из поиска" },
];

const consentLabels: Record<ConsentKind, string> = {
  pd_processing: "Обработка персональных данных",
  profile_publication: "Публикация профиля работодателям",
  fsp_import: "Импорт данных из реестра ФСП",
};

export default function SettingsPage() {
  const me = useCandidateMe();

  return (
    <>
      <PageHeader
        eyebrow="Настройки"
        title="Настройки"
        description="Приватность, согласия, привязка ФСП ID, статус поиска и уведомления. Изменения вступают в силу сразу."
      />
      {me.isPending ? (
        <SkeletonCards count={4} />
      ) : me.isError ? (
        <ErrorState description={apiError(me.error).message} onRetry={() => void me.refetch()} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <SearchStatusCard value={me.data.search_status} />
          <PrivacyCard privacy={me.data.privacy} />
          <FspLinkCard />
          <ConsentsCard />
          <EmailNotificationsCard role="candidate" />
        </div>
      )}
    </>
  );
}

function SearchStatusCard({ value }: { value: SearchStatus }) {
  const update = useUpdateSearchStatus();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Статус поиска</CardTitle>
        <CardDescription>Влияет на то, видят ли вас работодатели</CardDescription>
      </CardHeader>
      <CardContent role="radiogroup" aria-label="Статус поиска" className="grid gap-2">
        {searchStatuses.map((status) => (
          <label
            key={status.value}
            className="flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm has-checked:border-primary has-checked:bg-primary-tint"
          >
            <input
              type="radio"
              name="search-status"
              checked={(update.isPending ? update.variables : value) === status.value}
              disabled={update.isPending}
              onChange={() => update.mutate(status.value)}
              className="accent-primary"
            />
            {status.label}
          </label>
        ))}
        {update.isError && <p className="text-sm font-medium text-destructive-strong" role="alert">{apiError(update.error).message}</p>}
      </CardContent>
    </Card>
  );
}

function PrivacyCard({ privacy }: { privacy: PrivacySettings }) {
  const update = useUpdatePrivacy();
  const [query, setQuery] = useState("");
  const hiddenIds = privacy.hidden_employer_ids ?? [];
  const hidden = useCompanies("", hiddenIds);
  const found = useCompanies(query, []);
  const save = (patch: Partial<PrivacySettings>) => update.mutate({ ...privacy, ...patch });
  const candidates = (found.data ?? []).filter((company) => !hiddenIds.includes(company.id));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" aria-hidden /> Приватность
        </CardTitle>
        <CardDescription>Слепой первый просмотр: без фото, возраста и пола</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {privacyOptions.map((option) => (
          <label key={option.key} className="flex items-center gap-3 text-sm">
            <Checkbox
              checked={privacy[option.key] ?? false}
              disabled={update.isPending}
              onChange={(event) => save({ [option.key]: event.target.checked })}
            />
            {option.label}
          </label>
        ))}
        <Separator className="my-1" />
        <div className="text-sm">
          <div className="font-medium">Скрыть профиль от компаний</div>
          <div className="text-xs text-muted-foreground">Например, от текущего работодателя</div>
          {hiddenIds.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {(hidden.data ?? []).map((company) => (
                <Badge key={company.id} variant="muted" className="gap-1">
                  {company.company_name}
                  <button
                    type="button"
                    aria-label={`Показывать профиль компании ${company.company_name}`}
                    disabled={update.isPending}
                    onClick={() => save({ hidden_employer_ids: hiddenIds.filter((id) => id !== company.id) })}
                  >
                    <X className="size-3" aria-hidden />
                  </button>
                </Badge>
              ))}
            </div>
          )}
          <Input
            className="mt-2"
            placeholder="Начните вводить название компании"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {query.trim().length >= 2 && (
            <ul className="mt-1 divide-y divide-border-subtle rounded-lg border">
              {found.isPending ? (
                <li className="px-3 py-2 text-xs text-muted-foreground">Ищем…</li>
              ) : candidates.length === 0 ? (
                <li className="px-3 py-2 text-xs text-muted-foreground">Компаний не нашли</li>
              ) : (
                candidates.map((company) => (
                  <li key={company.id}>
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left hover:bg-primary-tint"
                      onClick={() => {
                        save({ hidden_employer_ids: [...hiddenIds, company.id] });
                        setQuery("");
                      }}
                    >
                      {company.company_name}
                    </button>
                  </li>
                ))
              )}
            </ul>
          )}
        </div>
        {update.isError && <p className="text-sm font-medium text-destructive-strong" role="alert">{apiError(update.error).message}</p>}
      </CardContent>
    </Card>
  );
}

function ConsentsCard() {
  const consents = useConsents();
  const update = useUpdateConsent();
  const [deleting, setDeleting] = useState(false);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Согласия</CardTitle>
        <CardDescription>Согласие на публикацию можно отозвать — профиль исчезнет из поиска</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {consents.isPending ? (
          <SkeletonCards count={1} />
        ) : consents.isError ? (
          <ErrorState description={apiError(consents.error).message} onRetry={() => void consents.refetch()} />
        ) : (
          consents.data.map((consent) => (
            <div key={consent.kind} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span>{consentLabels[consent.kind]}</span>
              <div className="flex items-center gap-2">
                {consent.granted && consent.granted_at ? (
                  <Badge variant="muted">с {formatDate(consent.granted_at)}</Badge>
                ) : consent.revoked_at ? (
                  <Badge variant="muted">отозвано {formatDate(consent.revoked_at)}</Badge>
                ) : (
                  <Badge variant="muted">не дано</Badge>
                )}
                {consent.kind === "profile_publication" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={update.isPending}
                    onClick={() => update.mutate({ kind: consent.kind, granted: !consent.granted })}
                  >
                    {consent.granted ? "Отозвать" : "Дать"}
                  </Button>
                )}
                {consent.kind === "fsp_import" && consent.granted && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={update.isPending}
                    onClick={() => update.mutate({ kind: consent.kind, granted: false })}
                  >
                    Отозвать
                  </Button>
                )}
              </div>
            </div>
          ))
        )}
        {update.isError && <p className="text-sm font-medium text-destructive-strong" role="alert">{apiError(update.error).message}</p>}
        <p className="text-xs text-muted-foreground">
          Отзыв согласия на импорт ФСП удаляет импортированные достижения. Согласие на обработку персональных
          данных отзывается удалением аккаунта.
        </p>
        <Separator className="my-1" />
        <Button variant="destructive" className="w-fit" onClick={() => setDeleting(true)}>
          <Trash2 /> Удалить аккаунт
        </Button>
      </CardContent>
      <DeleteAccountDialog open={deleting} onOpenChange={setDeleting} />
    </Card>
  );
}

function DeleteAccountDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const remove = useDeleteAccount();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const confirm = async () => {
    await remove.mutateAsync();
    // Как при выходе: сначала уходим из кабинета, потом чистим сессию
    await navigate("/", { replace: true });
    authStore.clear();
    queryClient.removeQueries();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Удалить аккаунт?</DialogTitle>
          <DialogDescription>
            Профиль исчезнет из поиска, персональные данные будут обезличены, активные приглашения закроются. Войти
            снова под этим email не получится. Действие необратимо.
          </DialogDescription>
        </DialogHeader>
        {remove.isError && <p className="text-sm font-medium text-destructive-strong" role="alert">{apiError(remove.error).message}</p>}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Отмена
          </Button>
          <Button variant="destructive" disabled={remove.isPending} onClick={() => void confirm()}>
            <Trash2 /> Удалить навсегда
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
