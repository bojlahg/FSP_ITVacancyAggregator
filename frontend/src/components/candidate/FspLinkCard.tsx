import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, KeyRound, Link2, Loader2, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router";
import { z } from "zod";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import {
  type FspProfile,
  fspOidcErrorMessage,
  useLinkFspManual,
  useMyFsp,
  useStartFspOidc,
  useUnlinkFsp,
} from "@/lib/fsp-queries";

const linkSchema = z.object({
  fspId: z.string().trim().max(64, "Слишком длинный ФСП ID"),
  consent: z.boolean().refine((value) => value, "Нужно согласие на импорт данных из реестра ФСП"),
});

type LinkValues = z.infer<typeof linkSchema>;

/** Итог возврата с ФСП ID (`?fsp_oidc=linked|error&reason=`): показываем один раз и убираем из адреса. */
function useOidcOutcome() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [outcome] = useState(() => {
    const status = searchParams.get("fsp_oidc");
    if (!status) return null;
    return status === "linked"
      ? { ok: true, message: "ФСП ID подтверждён, достижения импортированы." }
      : { ok: false, message: fspOidcErrorMessage(searchParams.get("reason")) };
  });
  const hasOutcomeParams = searchParams.has("fsp_oidc");

  useEffect(() => {
    if (!hasOutcomeParams) return;
    setSearchParams(
      (params) => {
        params.delete("fsp_oidc");
        params.delete("reason");
        return params;
      },
      { replace: true },
    );
  }, [hasOutcomeParams, setSearchParams]);

  return outcome;
}

/** Привязка ФСП ID (§9.3): вход через ФСП ID (OIDC) подтверждает владение, ручной ввод — нет. */
export function FspLinkCard() {
  const fsp = useMyFsp();
  const outcome = useOidcOutcome();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link2 className="size-4 text-primary" aria-hidden /> ФСП ID
        </CardTitle>
        <CardDescription>Достижения ФСП поднимают вас в выдаче. Без привязки профиль работает полностью.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {outcome?.ok && (
          <p className="flex items-center gap-1.5 text-sm text-primary" role="status">
            <CheckCircle2 className="size-4" aria-hidden /> {outcome.message}
          </p>
        )}
        <FormAlert message={outcome && !outcome.ok ? outcome.message : null} />
        {fsp.isPending ? (
          <div className="grid gap-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-2/3" />
          </div>
        ) : fsp.isError ? (
          <ErrorState description={apiError(fsp.error).message} onRetry={() => void fsp.refetch()} />
        ) : fsp.data.linked ? (
          <LinkedFsp profile={fsp.data} />
        ) : (
          <LinkFspForm />
        )}
      </CardContent>
    </Card>
  );
}

function OidcButton({ onStart, pending }: { onStart: () => void; pending: boolean }) {
  return (
    <Button type="button" onClick={onStart} disabled={pending} className="w-fit">
      {pending ? <Loader2 className="animate-spin" aria-hidden /> : <KeyRound aria-hidden />} Войти через ФСП ID
    </Button>
  );
}

function LinkedFsp({ profile }: { profile: FspProfile }) {
  const startOidc = useStartFspOidc();
  const unlink = useUnlinkFsp();
  const error = startOidc.error ?? unlink.error;

  return (
    <div className="grid gap-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono font-bold">{profile.fsp_id}</span>
        {profile.ownership_verified ? (
          <Badge variant="soft">владение подтверждено ФСП ID</Badge>
        ) : (
          <Badge variant="muted">введён вручную, владение не подтверждено</Badge>
        )}
      </div>
      <p className="text-muted-foreground">
        Результатов: <span className="font-mono">{profile.achievements.length}</span>, разрядов:{" "}
        <span className="font-mono">{profile.ranks.length}</span>
      </p>
      <FormAlert message={error ? apiError(error).message : null} />
      <div className="flex flex-wrap gap-2">
        {!profile.ownership_verified && (
          <OidcButton onStart={() => startOidc.mutate()} pending={startOidc.isPending || startOidc.isSuccess} />
        )}
        <Button variant="outline" onClick={() => unlink.mutate()} disabled={unlink.isPending}>
          <Trash2 aria-hidden /> Отвязать и удалить данные
        </Button>
      </div>
    </div>
  );
}

function LinkFspForm() {
  const link = useLinkFspManual();
  const startOidc = useStartFspOidc();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    trigger,
    setError,
    formState: { errors },
  } = useForm<LinkValues>({ resolver: zodResolver(linkSchema), defaultValues: { fspId: "", consent: false } });

  const onStartOidc = async () => {
    setFormError(null);
    if (!(await trigger("consent"))) return;
    startOidc.mutate(undefined, { onError: (err) => setFormError(apiError(err).message) });
  };

  const onManual = (values: LinkValues) => {
    setFormError(null);
    if (!values.fspId) {
      setError("fspId", { type: "required", message: "Введите ФСП ID" });
      return;
    }
    link.mutate(
      { fsp_id: values.fspId, consent: values.consent },
      {
        onError: (err) => {
          if (!applyValidationErrors(err, setError, { fsp_id: "fspId", consent: "consent" })) {
            setFormError(apiError(err).message);
          }
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit(onManual)} noValidate className="grid gap-3">
      <FormAlert message={formError} />
      <label className="flex items-start gap-3 text-sm">
        <Checkbox className="mt-0.5" aria-invalid={!!errors.consent} {...register("consent")} />
        <span>Согласен на импорт моих результатов и разрядов из реестра ФСП</span>
      </label>
      {errors.consent && (
        <p className="text-xs font-medium text-destructive-strong" role="alert">
          {errors.consent.message}
        </p>
      )}
      <OidcButton onStart={() => void onStartOidc()} pending={startOidc.isPending || startOidc.isSuccess} />
      <p className="text-xs text-muted-foreground">
        Вход через ФСП ID подтверждает, что достижения ваши. Ручной ввод помечается «владение не подтверждено».
      </p>
      <Separator />
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          placeholder="Например, FSP-2026-7781"
          aria-label="ФСП ID"
          aria-invalid={!!errors.fspId}
          {...register("fspId")}
        />
        <Button type="submit" variant="outline" disabled={link.isPending}>
          {link.isPending && <Loader2 className="animate-spin" aria-hidden />} Привязать вручную
        </Button>
      </div>
      {errors.fspId && (
        <p className="text-xs font-medium text-destructive-strong" role="alert">
          {errors.fspId.message}
        </p>
      )}
    </form>
  );
}
