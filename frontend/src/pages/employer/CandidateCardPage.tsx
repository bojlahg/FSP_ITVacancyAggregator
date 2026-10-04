import { ArrowLeft, Clock, Download, Lock, MapPin, Send, ShieldCheck, Trophy, UserX } from "lucide-react";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { InviteDialog } from "@/components/employer/InviteDialog";
import { EmptyState } from "@/components/EmptyState";
import { ExplanationList } from "@/components/ExplanationList";
import { PageHeader } from "@/components/PageHeader";
import { ScoreBadge } from "@/components/ScoreBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { formatDaysAgo, formatNumber } from "@/lib/format";
import { WORK_FORMAT_LABELS } from "@/lib/labels";
// MOCK: заменить на GET /talent/candidates/{id}?need_id= (обезличенная карточка; контактов нет без contact_unlocks)
import { findMockCandidate, findMockNeed } from "@/mocks/talent";

export default function CandidateCardPage() {
  const { candidateId } = useParams();
  const [searchParams] = useSearchParams();
  const [inviteOpen, setInviteOpen] = useState(false);
  const candidate = findMockCandidate(candidateId);
  const need = findMockNeed(searchParams.get("need_id") ?? undefined);

  if (!candidate) {
    return (
      <EmptyState
        icon={UserX}
        title="Кандидат не найден"
        description="Профиль скрыт или кандидат отозвал согласие на публикацию."
        action={
          <Button asChild variant="outline">
            <Link to="/employer/search">К поиску</Link>
          </Button>
        }
      />
    );
  }

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-3 mb-2">
        <Link to={need ? `/employer/needs/${need.id}` : "/employer/search"}>
          <ArrowLeft /> {need ? "К подборке" : "К поиску"}
        </Link>
      </Button>

      <PageHeader
        eyebrow="Карточка кандидата · обезличенная"
        title={
          <span className="flex flex-wrap items-center gap-3">
            {candidate.displayName}
            <CategoryBadge specialization={candidate.specialization} grade={candidate.grade} variant="solid" size="md" />
          </span>
        }
        description="Слепой первый просмотр: без фото, возраста и пола, фамилия скрыта. Контакты откроются, когда кандидат примет приглашение."
        actions={
          <>
            <Button variant="outline" disabled title="Будет доступно после подключения backend">
              <Download /> PDF
            </Button>
            <Button onClick={() => setInviteOpen(true)}>
              <Send /> Пригласить
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="grid content-start gap-4">
          {need && (
            <Card>
              <CardHeader className="grid-cols-[1fr_auto]">
                <div>
                  <CardTitle>Совпадение с потребностью</CardTitle>
                  <CardDescription>{need.title}</CardDescription>
                </div>
                <ScoreBadge score={candidate.score} size="lg" className="row-span-2" />
              </CardHeader>
              <CardContent>
                <ExplanationList items={candidate.explanation} />
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Результаты теста по темам</CardTitle>
              <CardDescription>
                {candidate.percentile}-й перцентиль в категории · тест {formatDaysAgo(candidate.freshDays)}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              {candidate.topics.map((topic) => (
                <div key={topic.name} className="space-y-1.5">
                  <div className="flex justify-between text-sm">
                    <span>{topic.name}</span>
                    <span className="font-mono font-bold tabular-nums">{topic.percent}%</span>
                  </div>
                  <Progress value={topic.percent} />
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="size-4 text-primary" aria-hidden /> Достижения ФСП
              </CardTitle>
              <CardDescription>Подтверждено реестром Федерации спортивного программирования</CardDescription>
            </CardHeader>
            <CardContent>
              {candidate.fspAchievements.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Нет привязанного профиля ФСП. Это не штраф — профиль оценивается по тесту.
                </p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {candidate.fspAchievements.map((achievement) => (
                    <li key={achievement} className="flex gap-2">
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden />
                      {achievement}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid content-start gap-4">
          <Card className="border-dashed bg-muted/40">
            <CardContent className="flex gap-3 text-sm">
              <Lock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              <div>
                <div className="font-medium">Контакты скрыты</div>
                <div className="text-muted-foreground">Откроются после того, как кандидат примет приглашение.</div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Стек</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <ShieldCheck className="size-3.5 text-primary" aria-hidden /> Проверено тестом
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.verifiedStack.map((skill) => (
                    <Badge key={skill} variant="soft">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
              {candidate.declaredStack.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs text-muted-foreground">Заявлено</div>
                  <div className="flex flex-wrap gap-1.5">
                    {candidate.declaredStack.map((skill) => (
                      <Badge key={skill} variant="muted">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Условия</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-2.5 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Ожидания</dt>
                  <dd className="font-mono font-bold">от {formatNumber(candidate.salaryMin)} ₽</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Формат</dt>
                  <dd>{WORK_FORMAT_LABELS[candidate.format]}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Город</dt>
                  <dd className="flex items-center gap-1">
                    <MapPin className="size-3.5" aria-hidden /> {candidate.city}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Релокация</dt>
                  <dd>{candidate.relocation ? "Готов" : "Нет"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Отрасли</dt>
                  <dd className="text-right">{candidate.industries.join(", ")}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Свежесть</dt>
                  <dd className="flex items-center gap-1">
                    <Clock className="size-3.5" aria-hidden /> {formatDaysAgo(candidate.freshDays)}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </div>
      </div>

      <InviteDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        candidateName={candidate.displayName}
        defaults={need ? { title: need.title, salaryFrom: need.salaryFrom, salaryTo: need.salaryTo } : undefined}
      />
    </>
  );
}
