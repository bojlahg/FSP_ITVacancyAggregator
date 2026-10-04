import { cn } from "@/lib/utils";

/** Статусы приглашения (docs/implementation.md §8.1 п.7). */
export type InvitationStatus = "sent" | "viewed" | "accepted" | "declined" | "expired" | "withdrawn";
/** Статусы отклика (docs/implementation.md §8.7). */
export type ApplicationStatus = "sent" | "viewed" | "accepted" | "rejected";

type Status = InvitationStatus | ApplicationStatus;

const config: Record<Status, { label: string; dot: string; box: string }> = {
  sent: { label: "Отправлено", dot: "bg-primary-pale", box: "border-border" },
  viewed: { label: "Просмотрено", dot: "bg-primary", box: "border-border" },
  accepted: { label: "Принято", dot: "bg-primary", box: "border-transparent bg-primary-tint text-primary" },
  declined: { label: "Отклонено", dot: "bg-destructive", box: "border-border" },
  rejected: { label: "Отклонено", dot: "bg-destructive", box: "border-border" },
  expired: { label: "Истёк срок", dot: "bg-border", box: "border-border text-muted-foreground" },
  withdrawn: { label: "Отозвано", dot: "bg-border", box: "border-border text-muted-foreground" },
};

interface StatusBadgeProps {
  status: Status;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const { label, dot, box } = config[status];
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-xs font-medium whitespace-nowrap",
        box,
        className,
      )}
    >
      <span className={cn("size-2 rounded-full", dot)} aria-hidden />
      {label}
    </span>
  );
}
