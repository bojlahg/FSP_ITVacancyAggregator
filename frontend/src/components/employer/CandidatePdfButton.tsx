import { Braces, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiError } from "@/lib/api-error";
import { useDownloadCandidateJsonResume, useDownloadCandidatePdf } from "@/lib/profile-queries";

interface CandidatePdfButtonProps {
  candidateId: number;
  /** Полный PDF с контактами — только после раскрытия контактов, иначе обезличенный. */
  unlocked: boolean;
}

/** PDF-профиль кандидата (§7) и экспорт в JSON Resume для ATS. */
export function CandidatePdfButton({ candidateId, unlocked }: CandidatePdfButtonProps) {
  const download = useDownloadCandidatePdf();
  const exportJson = useDownloadCandidateJsonResume();
  const failed = download.error ?? exportJson.error;
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex flex-wrap justify-end gap-2">
      <Button
        variant="outline"
        onClick={() => download.mutate(candidateId)}
        disabled={download.isPending}
        title={unlocked ? "PDF с контактами" : "Обезличенный PDF: контакты откроются после принятого приглашения"}
      >
        {download.isPending ? <Loader2 className="animate-spin" /> : <Download />}
        {unlocked ? "PDF-профиль" : "PDF без контактов"}
      </Button>
      <Button
        variant="outline"
        onClick={() => exportJson.mutate(candidateId)}
        disabled={exportJson.isPending}
        title="JSON Resume с расширением x-itscout — для загрузки в ATS"
      >
        {exportJson.isPending ? <Loader2 className="animate-spin" /> : <Braces />}
        JSON Resume
      </Button>
      </div>
      {failed && (
        <span role="alert" className="text-xs text-destructive-strong">
          {apiError(failed).message}
        </span>
      )}
    </div>
  );
}
