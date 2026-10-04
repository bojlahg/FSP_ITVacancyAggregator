import { Building2, Check, Clock, Mail, X } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ExplanationList } from "@/components/ExplanationList";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { formatDaysAgo } from "@/lib/format";
// MOCK: заменить на GET /candidates/me/invitations
import { mockCandidateInvitations, type MockCandidateInvitation } from "@/mocks/candidate";

const declineReasons = [
  { value: "salary", label: "Зарплата" },
  { value: "stack", label: "Стек" },
  { value: "format", label: "Формат работы" },
  { value: "company", label: "Компания" },
  { value: "not_looking", label: "Не ищу работу" },
];

export default function CandidateInvitationsPage() {
  const [declining, setDeclining] = useState<MockCandidateInvitation | null>(null);

  return (
    <>
      <PageHeader
        eyebrow="Приглашения"
        title="Приглашения"
        description="Работодатели пишут первыми и сразу указывают вилку. Примете приглашение — работодатель увидит ваши контакты, а вы — контакт рекрутера."
      />

      {mockCandidateInvitations.length === 0 ? (
        <EmptyState
          icon={Mail}
          title="Приглашений пока нет"
          description="Как только работодатель выберет вас в подборке, приглашение появится здесь."
        />
      ) : (
        <div className="grid gap-4">
          {mockCandidateInvitations.map((invitation) => (
            <Card key={invitation.id}>
              <CardHeader>
                <CardTitle className="text-lg">{invitation.title}</CardTitle>
                <CardDescription className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="inline-flex items-center gap-1.5">
                    <Building2 className="size-3.5" aria-hidden /> {invitation.company}
                  </span>
                  <span>{formatDaysAgo(invitation.sentDaysAgo)}</span>
                  <span className="inline-flex items-center gap-1.5">
                    <Clock className="size-3.5" aria-hidden /> ответить в течение {invitation.expiresInDays} дн.
                  </span>
                </CardDescription>
                <CardAction>
                  <StatusBadge status={invitation.status} />
                </CardAction>
              </CardHeader>
              <CardContent className="grid gap-5 md:grid-cols-[1fr_1fr]">
                <div className="space-y-3">
                  <SalaryRange from={invitation.salaryFrom} to={invitation.salaryTo} className="text-xl text-primary" />
                  <p className="text-sm leading-relaxed text-muted-foreground">{invitation.description}</p>
                </div>
                <div className="rounded-lg bg-muted/60 p-4">
                  <div className="mb-2 font-mono text-xs font-bold tracking-wider uppercase">Почему вам</div>
                  <ExplanationList items={invitation.whyYou} />
                </div>
              </CardContent>
              <CardFooter className="gap-2 border-t border-border-subtle pt-5">
                {/* TODO: POST /invitations/{id}/accept */}
                <Button onClick={() => console.info("[invitations] TODO: accept", invitation.id)}>
                  <Check /> Принять
                </Button>
                <Button variant="outline" onClick={() => setDeclining(invitation)}>
                  <X /> Отклонить
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={declining !== null} onOpenChange={(open) => !open && setDeclining(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Отклонить приглашение</DialogTitle>
            <DialogDescription>
              {declining?.company}: «{declining?.title}». Причина поможет работодателю делать более точные предложения.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="decline-reason">Причина</Label>
            <Select id="decline-reason" defaultValue="salary">
              {declineReasons.map((reason) => (
                <option key={reason.value} value={reason.value}>
                  {reason.label}
                </option>
              ))}
            </Select>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="ghost">Отмена</Button>
            </DialogClose>
            {/* TODO: POST /invitations/{id}/decline {reason} */}
            <Button
              onClick={() => {
                console.info("[invitations] TODO: decline", declining?.id);
                setDeclining(null);
              }}
            >
              Отклонить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
