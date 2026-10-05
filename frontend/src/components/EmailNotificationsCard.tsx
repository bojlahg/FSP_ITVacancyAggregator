import { Mail } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { apiError } from "@/lib/api-error";
import { useAuth } from "@/lib/auth";
import { useUpdateEmailNotifications } from "@/lib/notification-queries";

const descriptions = {
  candidate: "Новые и отозванные приглашения",
  employer: "Ответы на приглашения и новые отклики на вакансии",
} as const;

/** Переключатель писем о событиях подбора — общий для кабинетов кандидата и работодателя. */
export function EmailNotificationsCard({ role }: { role: keyof typeof descriptions }) {
  const { user } = useAuth();
  const update = useUpdateEmailNotifications();
  if (!user) return null;
  const checked = update.isPending ? update.variables : user.email_notifications;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Mail className="size-4 text-primary" aria-hidden /> Уведомления на почту
        </CardTitle>
        <CardDescription>
          {descriptions[role]}. Письма приходят на <span className="break-all">{user.email}</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2">
        <label className="flex items-center gap-3 text-sm">
          <Checkbox
            checked={checked}
            disabled={update.isPending}
            onChange={(event) => update.mutate(event.target.checked)}
          />
          Присылать письма о событиях подбора
        </label>
        {update.isError && (
          <p className="text-sm font-medium text-destructive-strong" role="alert">
            {apiError(update.error).message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
