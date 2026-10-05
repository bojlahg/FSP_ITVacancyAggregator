import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  Clock,
  Lock,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  Send,
  ShieldCheck,
  Trophy,
  Unlock,
  UserX,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { CategoryBadge } from "@/components/CategoryBadge";
import { CandidatePdfButton } from "@/components/employer/CandidatePdfButton";
import { InviteDialog } from "@/components/employer/InviteDialog";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ExplanationList } from "@/components/ExplanationList";
import { PageHeader } from "@/components/PageHeader";
import { ScoreBadge } from "@/components/ScoreBadge";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiError } from "@/lib/api-error";
import { type CandidateCard, parseId, useCandidateCard, useNeed } from "@/lib/employer-queries";
import { daysSince, formatDate, formatDaysAgo, formatNumber, plural, toPercent } from "@/lib/format";
import { FSP_LEVEL_LABELS, SKILL_STATUS_LABELS, workFormatsLabel } from "@/lib/labels";

type SkillStatus = CandidateCard["skills"][number]["status"];

const SKILL_STATUS_ORDER: SkillStatus[] = ["verified", "fsp_confirmed", "task_confirmed", "declared"];
const SKILL_BADGE: Record<SkillStatus, "soft" | "default" | "outline" | "muted"> = {
  verified: "soft",
  fsp_confirmed: "default",
  task_confirmed: "outline",
  declared: "muted",
};

export default function CandidateCardPage() {
  const candidateId = parseId(useParams().candidateId);
  const [searchParams] = useSearchParams();
  const needId = parseId(searchParams.get("need"));
  const card = useCandidateCard(candidateId, needId);
  const need = useNeed(needId);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [invited, setInvited] = useState(false);

  const back = needId ? (
    <Button asChild variant="ghost" size="sm" className="-ml-3 mb-2">
      <Link to={`/employer/needs/${needId}`}>
        <ArrowLeft /> К подборке
      </Link>
    </Button>
  ) : (
    <Button asChild variant="ghost" size="sm" className="-ml-3 mb-2">
      <Link to="/employer/search">
        <ArrowLeft /> К поиску
      </Link>
    </Button>
  );

  if (candidateId === null || (card.isError && [403, 404].includes(apiError(card.error).status))) {
    return (
      <>
        {back}
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
      </>
    );
  }
  if (card.isPending) {
    return (
      <>
        {back}
        <SkeletonCards count={3} />
      </>
    );
  }
  if (card.isError) {
    return (
      <>
        {back}
        <ErrorState description={apiError(card.error).message} onRetry={() => void card.refetch()} />
      </>
    );
  }

  const data = card.data;
  const { brief } = data;

  return (
    <>
      {back}
      <PageHeader
        eyebrow={data.contacts_unlocked ? "Карточка кандидата · контакты открыты" : "Карточка кандидата · обезличенная"}
        title={
          <span className="flex flex-wrap items-center gap-3">
            {data.contacts?.full_name ?? brief.display_name}
            <CategoryBadge specialization={brief.category.specialization} grade={brief.category.grade} variant="solid" size="md" />
          </span>
        }
        description={
          <>
            {brief.percentile != null && (
              <b className="font-mono text-foreground">{toPercent(brief.percentile)}-й перцентиль в категории. </b>
            )}
            Слепой первый просмотр: без фото, возраста и пола, фамилия скрыта до принятия приглашения.
          </>
        }
        actions={
          <>
            <CandidatePdfButton candidateId={brief.id} unlocked={data.contacts_unlocked} />
            {invited || ["sent", "viewed", "accepted"].includes(data.invitation_status ?? "") ? (
              <Button variant="secondary" disabled>
                <CheckCircle2 /> Приглашение отправлено
              </Button>
            ) : (
              <Button onClick={() => setInviteOpen(true)} disabled={needId !== null && need.isPending}>
                <Send /> Пригласить
              </Button>
            )}
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="grid content-start gap-4">
          {data.match && (
            <Card>
              <CardHeader className="grid-cols-[1fr_auto]">
                <div className="space-y-1.5">
                  <CardTitle>Совпадение с потребностью</CardTitle>
                  <CardDescription>
                    {need.data ? need.data.title : "Потребность"} · объяснение собрано из тех же компонентов, что и score
                  </CardDescription>
                </div>
                <ScoreBadge score={data.match.score} size="lg" className="row-span-2" />
              </CardHeader>
              <CardContent>
                <ExplanationList items={data.match.explanation.lines} />
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Результаты теста по темам</CardTitle>
              <CardDescription>
                {brief.last_activity_at
                  ? `Последний тест или задание — ${formatDaysAgo(daysSince(brief.last_activity_at))}`
                  : "Категория подтверждена тестом"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.topic_scores.length === 0 ? (
                <p className="text-sm text-muted-foreground">Разбивки по темам нет.</p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {data.topic_scores.map((topic) => (
                    <div key={topic.topic} className="space-y-1.5">
                      <div className="flex justify-between gap-2 text-sm">
                        <span>{topic.name}</span>
                        <span className="font-mono font-bold tabular-nums">
                          {toPercent(topic.score)}%
                          <span className="ml-1 text-xs font-normal text-muted-foreground">
                            · {topic.items} {plural(topic.items, ["задание", "задания", "заданий"])}
                          </span>
                        </span>
                      </div>
                      <Progress value={toPercent(topic.score)} />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {data.approach_answers?.length ? <ApproachCard answers={data.approach_answers} /> : null}

          <FspCard fsp={data.fsp} />

          {(data.experience.length > 0 || data.about) && (
            <Card>
              <CardHeader>
                <CardTitle>Опыт</CardTitle>
                <CardDescription>
                  {data.experience_years != null && `${data.experience_years} лет опыта. `}
                  {!data.contacts_unlocked && "Названия компаний скрыты до принятия приглашения."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {data.about && <p className="text-sm leading-relaxed">{data.about}</p>}
                {data.experience.length > 0 && (
                  <ol className="space-y-3 border-l border-border-subtle pl-4">
                    {data.experience.map((item, index) => (
                      <li key={index} className="space-y-0.5">
                        <div className="font-medium">
                          {item.position}
                          {data.contacts_unlocked && item.company && (
                            <span className="text-muted-foreground"> · {item.company}</span>
                          )}
                        </div>
                        <div className="font-mono text-xs text-muted-foreground">
                          {item.started_on ? formatDate(item.started_on) : "—"} —{" "}
                          {item.ended_on ? formatDate(item.ended_on) : "по настоящее время"}
                        </div>
                        {item.description && <p className="text-sm text-muted-foreground">{item.description}</p>}
                      </li>
                    ))}
                  </ol>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        <div className="grid content-start gap-4">
          <ContactsCard card={data} />

          <Card>
            <CardHeader>
              <CardTitle>Стек</CardTitle>
              <CardDescription>У каждого навыка — источник подтверждения</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.skills.length === 0 && <p className="text-sm text-muted-foreground">Навыки не указаны.</p>}
              {SKILL_STATUS_ORDER.map((status) => {
                const skills = data.skills.filter((skill) => skill.status === status);
                if (skills.length === 0) return null;
                return (
                  <div key={status} className="space-y-2">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      {status === "verified" && <ShieldCheck className="size-3.5 text-primary" aria-hidden />}
                      {status === "fsp_confirmed" && <Trophy className="size-3.5 text-primary" aria-hidden />}
                      {SKILL_STATUS_LABELS[status]}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {skills.map((skill) => (
                        <Badge key={skill.skill_id} variant={SKILL_BADGE[status]}>
                          {skill.name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                );
              })}
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
                  <dd className="font-mono font-bold">
                    {brief.salary_min == null ? "скрыты" : `от ${formatNumber(brief.salary_min)} ₽`}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Формат</dt>
                  <dd className="text-right">{workFormatsLabel(brief.work_formats)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Город</dt>
                  <dd className="flex items-center gap-1">
                    <MapPin className="size-3.5" aria-hidden /> {brief.city ?? "не указан"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Релокация</dt>
                  <dd>{brief.relocation ? "Готов" : "Нет"}</dd>
                </div>
                {data.industries_exp.length > 0 && (
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Отрасли</dt>
                    <dd className="text-right">{data.industries_exp.join(", ")}</dd>
                  </div>
                )}
                {data.roles.length > 0 && (
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Роли</dt>
                    <dd className="text-right">{data.roles.join(", ")}</dd>
                  </div>
                )}
                {brief.last_activity_at && (
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Свежесть</dt>
                    <dd className="flex items-center gap-1">
                      <Clock className="size-3.5" aria-hidden /> {formatDaysAgo(daysSince(brief.last_activity_at))}
                    </dd>
                  </div>
                )}
              </dl>
              {data.soft_skills.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {data.soft_skills.map((skill) => (
                    <Badge key={skill} variant="muted">
                      {skill}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <InviteDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        candidate={{ id: brief.id, display_name: brief.display_name }}
        need={need.data ?? null}
        onSent={() => setInvited(true)}
      />
    </>
  );
}

function ContactsCard({ card }: { card: CandidateCard }) {
  const contacts = card.contacts;
  if (!contacts) {
    return (
      <Card className="border-dashed bg-muted/40">
        <CardContent className="flex gap-3 text-sm">
          <Lock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <div>
            <div className="font-medium">Контакты скрыты</div>
            <div className="text-muted-foreground">Контакты откроются, когда кандидат примет приглашение.</div>
          </div>
        </CardContent>
      </Card>
    );
  }
  const rows = [
    { icon: Mail, value: contacts.email, href: contacts.email ? `mailto:${contacts.email}` : null },
    { icon: MessageCircle, value: contacts.telegram, href: null },
    { icon: Phone, value: contacts.phone, href: contacts.phone ? `tel:${contacts.phone}` : null },
  ].filter((row) => row.value);
  return (
    <Card className="border-primary bg-primary-tint">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Unlock className="size-4 text-primary" aria-hidden /> Контакты
        </CardTitle>
        <CardDescription>Кандидат принял приглашение — доступ записан в журнал.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2 text-sm">
        <div className="font-medium">{contacts.full_name}</div>
        {rows.map(({ icon: Icon, value, href }) => (
          <div key={value} className="flex items-center gap-2">
            <Icon className="size-4 text-primary" aria-hidden />
            {href ? (
              <a href={href} className="font-mono hover:text-primary hover:underline">
                {value}
              </a>
            ) : (
              <span className="font-mono">{value}</span>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function FspCard({ fsp }: { fsp: CandidateCard["fsp"] }) {
  const data = fsp?.linked && (fsp.achievements.length > 0 || fsp.ranks.length > 0) ? fsp : null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trophy className="size-4 text-primary" aria-hidden /> Федерация спортивного программирования
        </CardTitle>
        {data && (
          <CardDescription>
            {data.ownership_verified ? "Профиль подтверждён через ФСП ID" : "Профиль привязан по номеру ФСП ID"}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        {!data ? (
          <p className="text-sm text-muted-foreground">Данных ФСП нет. Профиль оценивается по тесту — это не штраф.</p>
        ) : (
          <div className="space-y-5">
            {data.ranks.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {data.ranks.map((rank) => (
                  <Badge key={`${rank.discipline}-${rank.rank}`} variant="default" title={`Присвоен ${formatDate(rank.awarded_at)}`}>
                    {rank.rank} · {rank.discipline}
                  </Badge>
                ))}
              </div>
            )}
            {data.achievements.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-sm">
                  <thead className="border-b border-border-subtle">
                    <tr className="text-left font-mono text-xs text-muted-foreground uppercase">
                      <th className="py-2 pr-3 font-medium">Соревнование</th>
                      <th className="px-3 py-2 font-medium">Уровень</th>
                      <th className="px-3 py-2 text-right font-medium">Место</th>
                      <th className="py-2 pl-3 text-right font-medium">Сила</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle">
                    {data.achievements.map((achievement, index) => (
                      <tr key={index}>
                        <td className="py-2 pr-3">
                          <div className="font-medium">{achievement.competition_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {achievement.discipline} · {formatDate(achievement.held_on)}
                            {achievement.team_role && ` · роль: ${achievement.team_role}`}
                            {achievement.prize && ` · ${achievement.prize}`}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {FSP_LEVEL_LABELS[achievement.level] ?? achievement.level}
                        </td>
                        <td className="px-3 py-2 text-right font-mono whitespace-nowrap tabular-nums">
                          <b>{achievement.place}</b>
                          <span className="text-muted-foreground"> / {achievement.participants}</span>
                        </td>
                        <td className="py-2 pl-3 text-right font-mono font-bold tabular-nums">
                          {toPercent(achievement.strength)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {data.competencies.length > 0 && (
              <div className="space-y-2">
                <div className="font-mono text-xs font-bold tracking-wider uppercase">Компетенции</div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {data.competencies.map((competency) => (
                    <div key={competency.id} className="space-y-1">
                      <div className="flex justify-between gap-2 text-sm">
                        <span>{competency.name}</span>
                        <span className="font-mono text-xs text-muted-foreground">
                          {competency.status === "confirmed" ? "подтверждена" : "есть признаки"} ·{" "}
                          {competency.evidence_count}
                        </span>
                      </div>
                      <Progress value={toPercent(competency.score)} className="h-1.5" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ApproachCard({ answers }: { answers: NonNullable<CandidateCard["approach_answers"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Открытый вопрос о подходе</CardTitle>
        <CardDescription>
          Ответ из теста. Отметки по чек-листу ставит модель, долю отмеченных считает код; в грейд и категорию не
          входит.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {answers.map((answer, index) => (
          <div key={index} className="space-y-3">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-medium">{answer.question}</p>
              {answer.score != null && (
                <span className="shrink-0 font-mono text-sm font-bold tabular-nums">{toPercent(answer.score)}%</span>
              )}
            </div>
            <p className="rounded-md bg-muted p-3 text-sm whitespace-pre-line">{answer.answer}</p>
            <ul className="space-y-1.5 text-sm">
              {answer.criteria.map((criterion) => (
                <li key={criterion.text} className="flex items-start gap-2">
                  {criterion.met ? (
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
                  ) : (
                    <Circle className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  )}
                  <span className={criterion.met ? "" : "text-muted-foreground"}>{criterion.text}</span>
                </li>
              ))}
            </ul>
            {answer.score == null && (
              <p className="text-xs text-muted-foreground">Ответ ещё не оценён по чек-листу.</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
