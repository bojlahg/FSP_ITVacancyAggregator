import { Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiError } from "@/lib/api-error";
import { useDownloadCandidatePdf } from "@/lib/profile-queries";

interface CandidatePdfButtonProps {
  candidateId: number;
  /** Полный PDF с контактами — только после раскрытия контактов, иначе обезличенный. */
  unlocked: boolean;
}

/** Скачать стандартный PDF-профиль кандидата (GET /talent/candidates/{id}/profile.pdf, §7). */
export function CandidatePdfButton({ candidateId, unlocked }: CandidatePdfButtonProps) {
  const download = useDownloadCandidatePdf();
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="outline"
        onClick={() => download.mutate(candidateId)}
        disabled={download.isPending}
        title={unlocked ? "PDF с контактами" : "Обезличенный PDF: контакты откроются после принятого приглашения"}
      >
        {download.isPending ? <Loader2 className="animate-spin" /> : <Download />}
        {unlocked ? "PDF-профиль" : "PDF без контактов"}
      </Button>
      {download.isError && (
        <span role="alert" className="text-xs text-destructive-strong">
          {apiError(download.error).message}
        </span>
      )}
    </div>
  );
}
