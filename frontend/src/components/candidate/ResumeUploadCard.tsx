import { FileUp, Loader2 } from "lucide-react";
import { useId, useState, type ChangeEvent, type DragEvent } from "react";
import { FormAlert } from "@/components/FormAlert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiError } from "@/lib/api-error";
import { type ResumeParseResult, useUploadResume } from "@/lib/profile-queries";
import { cn } from "@/lib/utils";

const MAX_BYTES = 5 * 1024 * 1024;

interface ResumeUploadCardProps {
  /** Разбор пришёл: родитель подставляет prefill в форму (в профиль ничего не сохранено). */
  onParsed: (result: ResumeParseResult) => void;
}

/** Загрузка PDF-резюме → предзаполнение формы профиля (POST /candidates/me/resume, §7). */
export function ResumeUploadCard({ onParsed }: ResumeUploadCardProps) {
  const inputId = useId();
  const upload = useUploadResume();
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const send = (file: File | undefined) => {
    setLocalError(null);
    upload.reset();
    if (!file) return;
    if (file.type && file.type !== "application/pdf") {
      setLocalError("Нужен файл в формате PDF");
      return;
    }
    if (file.size > MAX_BYTES) {
      setLocalError("Файл больше 5 МБ");
      return;
    }
    upload.mutate(file, { onSuccess: onParsed });
  };

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    send(event.target.files?.[0]);
    // Тот же файл можно выбрать повторно
    event.target.value = "";
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!upload.isPending) send(event.dataTransfer.files[0]);
  };

  const error = localError ?? (upload.isError ? apiError(upload.error).message : null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Резюме</CardTitle>
        <CardDescription>
          PDF до 5 МБ — предзаполним форму, вы проверите и сохраните. На категорию и грейд резюме не влияет.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <label
          htmlFor={inputId}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center text-sm transition-colors hover:bg-muted",
            dragging && "border-primary bg-primary-tint",
            upload.isPending && "pointer-events-none opacity-70",
          )}
        >
          {upload.isPending ? (
            <Loader2 className="size-6 animate-spin text-primary" aria-hidden />
          ) : (
            <FileUp className="size-6 text-primary" aria-hidden />
          )}
          <span className="font-medium">{upload.isPending ? "Разбираем резюме…" : "Загрузить PDF"}</span>
          <span className="text-xs text-muted-foreground">Перетащите файл сюда или нажмите. Сканы без текста не распознаём</span>
          <input
            id={inputId}
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            onChange={onChange}
            disabled={upload.isPending}
          />
        </label>
        <FormAlert message={error} />
      </CardContent>
    </Card>
  );
}
