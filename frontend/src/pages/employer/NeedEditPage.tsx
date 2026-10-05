import { ArrowLeft, SearchX } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router";
import { NeedForm } from "@/components/employer/NeedForm";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiError } from "@/lib/api-error";
import { parseId, useNeed, useUpdateNeed } from "@/lib/employer-queries";
import { needFormValues } from "@/lib/need-form";

export default function NeedEditPage() {
  const needId = parseId(useParams().needId);
  const navigate = useNavigate();
  const need = useNeed(needId);
  const update = useUpdateNeed(needId ?? 0);

  if (needId === null || (need.isError && apiError(need.error).status === 404)) {
    return (
      <EmptyState
        icon={SearchX}
        title="Потребность не найдена"
        action={
          <Button asChild variant="outline">
            <Link to="/employer/needs">К потребностям</Link>
          </Button>
        }
      />
    );
  }

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-3 mb-2">
        <Link to={`/employer/needs/${needId}`}>
          <ArrowLeft /> К подборке
        </Link>
      </Button>
      <PageHeader
        eyebrow={need.data ? `Правка · сейчас версия ${need.data.version}` : "Правка потребности"}
        title={need.data?.title ?? "Изменить потребность"}
        description="Сохранение создаёт новую версию: предыдущая останется в истории, шорт-лист перенесётся."
      />
      {need.isPending ? (
        <SkeletonCards count={1} className="max-w-4xl" />
      ) : need.isError ? (
        <ErrorState description={apiError(need.error).message} onRetry={() => void need.refetch()} />
      ) : (
        <Card className="max-w-4xl">
          <NeedForm
            key={need.data.id}
            initial={needFormValues(need.data)}
            rawText={need.data.raw_text}
            submitLabel="Сохранить новую версию"
            footerNote={`Будет создана версия ${need.data.version + 1}.`}
            pending={update.isPending}
            onSubmit={(body) =>
              update.mutateAsync(body).then((saved) => navigate(`/employer/needs/${saved.id}`, { replace: true }))
            }
          />
        </Card>
      )}
    </>
  );
}
