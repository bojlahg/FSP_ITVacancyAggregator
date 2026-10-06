import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Download, Eye, FileText, Loader2, Plus, Save, Trash2, X } from "lucide-react";
import { useState, type BaseSyntheticEvent, type ReactNode } from "react";
import { Controller, useFieldArray, useForm, type Control, type FieldPath } from "react-hook-form";
import { Link } from "react-router";
import { ResumeUploadCard } from "@/components/candidate/ResumeUploadCard";
import { SkillsMultiSelect } from "@/components/candidate/SkillsMultiSelect";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import { INVALID_FORM_MESSAGE, revealFirstInvalid } from "@/lib/form-errors";
import { useIndustries } from "@/lib/employer-queries";
import { gradeLabel, SKILL_STATUS_LABELS, WORK_FORMAT_LABELS } from "@/lib/labels";
import {
  FROM_RESUME_FIELDS,
  formFromPrefill,
  formFromProfile,
  profileBody,
  profileFieldMap,
  type ProfileFormValues,
  profileSchema,
} from "@/lib/profile-form";
import {
  type PdfVariant,
  type ResumeParseResult,
  useDownloadMyPdf,
  useSoftSkills,
  useTeamRoles,
  useUpdateProfile,
} from "@/lib/profile-queries";
import { type CandidateProfile, type SkillOut, useCandidateMe, useSkillCatalog } from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

const WORK_FORMATS = ["office", "hybrid", "remote"] as const;
const EMPTY_JOB = { company: "", position: "", startedOn: "", endedOn: "", description: "" };

export default function ProfilePage() {
  const me = useCandidateMe();
  const download = useDownloadMyPdf();
  const [pendingVariant, setPendingVariant] = useState<PdfVariant | null>(null);

  const downloadPdf = (variant: PdfVariant) => {
    setPendingVariant(variant);
    download.mutate(variant, { onSettled: () => setPendingVariant(null) });
  };

  return (
    <>
      <PageHeader
        eyebrow="Профиль и резюме"
        title="Профиль"
        description="Данные профиля видят работодатели: фамилия, контакты и названия компаний скрыты до принятого приглашения. Резюме помогает заполнить форму быстрее, но не влияет на категорию."
        actions={
          <>
            <Button variant="outline" onClick={() => downloadPdf("public")} disabled={download.isPending || !me.data}>
              {pendingVariant === "public" ? <Loader2 className="animate-spin" /> : <Eye />} Как видит работодатель
            </Button>
            <Button onClick={() => downloadPdf("full")} disabled={download.isPending || !me.data}>
              {pendingVariant === "full" ? <Loader2 className="animate-spin" /> : <Download />} PDF-профиль
            </Button>
          </>
        }
      />
      <FormAlert message={download.isError ? apiError(download.error).message : null} className="mb-4" />

      {me.isPending ? (
        <SkeletonCards count={3} />
      ) : me.isError ? (
        <ErrorState description={apiError(me.error).message} onRetry={() => void me.refetch()} />
      ) : (
        <ProfileForm profile={me.data} />
      )}
    </>
  );
}

function ProfileForm({ profile }: { profile: CandidateProfile }) {
  const update = useUpdateProfile();
  const catalog = useSkillCatalog();
  const teamRoles = useTeamRoles();
  const softSkills = useSoftSkills();
  const industries = useIndustries();
  const [pickedNames, setPickedNames] = useState<Record<string, string>>({});
  const [resume, setResume] = useState<ResumeParseResult | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: formFromProfile(profile),
    shouldFocusError: false,
  });
  const invalid = (_errors: unknown, event?: BaseSyntheticEvent) => {
    setFormError(INVALID_FORM_MESSAGE);
    revealFirstInvalid(event);
  };
  const jobs = useFieldArray({ control, name: "experience" });

  const skillNames = {
    ...Object.fromEntries((catalog.data ?? []).map((skill) => [skill.id, skill.name])),
    ...Object.fromEntries(profile.skills.map((skill) => [skill.skill_id, skill.name])),
    ...pickedNames,
  };
  const rememberNames = (skills: SkillOut[]) =>
    setPickedNames((current) => ({ ...current, ...Object.fromEntries(skills.map((skill) => [skill.id, skill.name])) }));

  const fromResume = new Set((resume?.from_resume ?? []).map((field) => FROM_RESUME_FIELDS[field]).filter(Boolean));
  const mark = (field: keyof ProfileFormValues) =>
    fromResume.has(field) ? (
      <Badge variant="soft" className="ml-2 align-middle">
        из резюме
      </Badge>
    ) : null;

  const applyResume = (result: ResumeParseResult) => {
    setSaved(false);
    setResume(result);
    // Форма становится «грязной»: в профиль ничего не попадёт, пока кандидат не нажмёт «Сохранить»
    reset(formFromPrefill(result.prefill), { keepDefaultValues: true });
  };

  const submit = async (values: ProfileFormValues, event?: BaseSyntheticEvent) => {
    setFormError(null);
    setSaved(false);
    try {
      const updated = await update.mutateAsync(profileBody(values, profile));
      reset(formFromProfile(updated));
      setSaved(true);
      setResume(null);
    } catch (err) {
      if (applyValidationErrors(err, setError, profileFieldMap)) invalid(null, event);
      else setFormError(apiError(err).message);
    }
  };

  const verified = profile.skills.filter((skill) => skill.status !== "declared");

  return (
    <form onSubmit={handleSubmit(submit, invalid)} noValidate className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="grid content-start gap-4">
        {resume && (
          <ResumeSummary
            result={resume}
            onDiscard={() => {
              setResume(null);
              reset(formFromProfile(profile));
            }}
          />
        )}
        {saved && !isDirty && (
          <div role="status" className="flex items-center gap-2 rounded-md border border-primary/30 bg-primary-tint px-3 py-2 text-sm text-primary">
            <CheckCircle2 className="size-4" aria-hidden /> Профиль сохранён
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Основное</CardTitle>
            <CardDescription>Работодатель до контакта видит только имя и первую букву фамилии.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            <FormField id="first-name" label={<>Имя{mark("firstName")}</>} error={errors.firstName?.message}>
              <Input id="first-name" aria-invalid={!!errors.firstName} {...register("firstName")} />
            </FormField>
            <FormField id="last-name" label={<>Фамилия{mark("lastName")}</>} error={errors.lastName?.message}>
              <Input id="last-name" aria-invalid={!!errors.lastName} {...register("lastName")} />
            </FormField>
            <FormField id="middle-name" label={<>Отчество{mark("middleName")}</>} error={errors.middleName?.message}>
              <Input id="middle-name" aria-invalid={!!errors.middleName} {...register("middleName")} />
            </FormField>
            <FormField id="city" label={<>Город{mark("city")}</>} error={errors.city?.message}>
              <Input id="city" aria-invalid={!!errors.city} {...register("city")} />
            </FormField>
            <FormField
              id="experience-years"
              label={<>Стаж в ИТ, лет{mark("experienceYears")}</>}
              error={errors.experienceYears?.message}
            >
              <Input id="experience-years" inputMode="decimal" aria-invalid={!!errors.experienceYears} {...register("experienceYears")} />
            </FormField>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox {...register("relocation")} /> Готов(а) к переезду{mark("relocation")}
              </label>
            </div>
            <fieldset className="grid gap-2 sm:col-span-3">
              <legend className="mb-2 text-sm font-medium">Формат работы{mark("workFormats")}</legend>
              <Controller
                control={control}
                name="workFormats"
                render={({ field }) => (
                  <div className="flex flex-wrap gap-4">
                    {WORK_FORMATS.map((format) => (
                      <label key={format} className="flex items-center gap-2 text-sm">
                        <Checkbox
                          checked={field.value.includes(format)}
                          onChange={(event) =>
                            field.onChange(
                              event.target.checked ? [...field.value, format] : field.value.filter((item) => item !== format),
                            )
                          }
                        />
                        {WORK_FORMAT_LABELS[format]}
                      </label>
                    ))}
                  </div>
                )}
              />
            </fieldset>
            <FormField id="salary-min" label={<>Ожидания от, ₽ на руки{mark("salaryMin")}</>} error={errors.salaryMin?.message}>
              <Input id="salary-min" inputMode="numeric" aria-invalid={!!errors.salaryMin} {...register("salaryMin")} />
            </FormField>
            <FormField id="salary-max" label={<>Ожидания до, ₽ на руки{mark("salaryMax")}</>} error={errors.salaryMax?.message}>
              <Input id="salary-max" inputMode="numeric" aria-invalid={!!errors.salaryMax} {...register("salaryMax")} />
            </FormField>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Контакты</CardTitle>
            <CardDescription>Откроются работодателю только после принятого приглашения или вашего отклика.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            <FormField id="contact-email" label={<>Email{mark("contactEmail")}</>} error={errors.contactEmail?.message}>
              <Input id="contact-email" type="email" aria-invalid={!!errors.contactEmail} {...register("contactEmail")} />
            </FormField>
            <FormField id="phone" label={<>Телефон{mark("phone")}</>} error={errors.phone?.message}>
              <Input id="phone" type="tel" aria-invalid={!!errors.phone} {...register("phone")} />
            </FormField>
            <FormField id="telegram" label={<>Telegram{mark("telegram")}</>} error={errors.telegram?.message}>
              <Input id="telegram" placeholder="@username" aria-invalid={!!errors.telegram} {...register("telegram")} />
            </FormField>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Стек{mark("declaredSkills")}</CardTitle>
            <CardDescription>
              Здесь — заявленные навыки. Статус «проверено тестом» ставит только тест, его нельзя добавить вручную.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Controller
              control={control}
              name="declaredSkills"
              render={({ field }) => (
                <SkillsMultiSelect
                  id="declared-skills"
                  value={field.value}
                  onChange={field.onChange}
                  names={skillNames}
                  onNamesChange={rememberNames}
                />
              )}
            />
            {resume && resume.unmapped_terms.length > 0 && (
              <p className="mt-3 text-xs text-muted-foreground">
                Нет в справочнике навыков: {resume.unmapped_terms.join(", ")}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Опыт работы{mark("experience")}</CardTitle>
            <CardDescription>Названия компаний работодатель увидит только после контакта.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {jobs.fields.length === 0 && (
              <p className="text-sm text-muted-foreground">Мест работы пока нет — добавьте вручную или загрузите резюме.</p>
            )}
            {jobs.fields.map((job, index) => {
              const jobErrors = errors.experience?.[index];
              return (
                <div key={job.id} className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2">
                  <FormField id={`job-${index}-position`} label="Должность *" error={jobErrors?.position?.message}>
                    <Input id={`job-${index}-position`} aria-invalid={!!jobErrors?.position} {...register(`experience.${index}.position`)} />
                  </FormField>
                  <FormField id={`job-${index}-company`} label="Компания *" error={jobErrors?.company?.message}>
                    <Input id={`job-${index}-company`} aria-invalid={!!jobErrors?.company} {...register(`experience.${index}.company`)} />
                  </FormField>
                  <FormField id={`job-${index}-start`} label="Начало" error={jobErrors?.startedOn?.message}>
                    <Input id={`job-${index}-start`} type="month" aria-invalid={!!jobErrors?.startedOn} {...register(`experience.${index}.startedOn`)} />
                  </FormField>
                  <FormField id={`job-${index}-end`} label="Окончание" hint="Пусто — по настоящее время" error={jobErrors?.endedOn?.message}>
                    <Input id={`job-${index}-end`} type="month" aria-invalid={!!jobErrors?.endedOn} {...register(`experience.${index}.endedOn`)} />
                  </FormField>
                  <FormField
                    id={`job-${index}-description`}
                    label="Чем занимались"
                    error={jobErrors?.description?.message}
                    className="sm:col-span-2"
                  >
                    <Textarea id={`job-${index}-description`} rows={3} {...register(`experience.${index}.description`)} />
                  </FormField>
                  <div className="sm:col-span-2">
                    <Button type="button" variant="ghost" size="sm" onClick={() => jobs.remove(index)}>
                      <Trash2 /> Удалить место работы
                    </Button>
                  </div>
                </div>
              );
            })}
            <Button type="button" variant="outline" size="sm" onClick={() => jobs.append(EMPTY_JOB)}>
              <Plus /> Добавить место работы
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>О себе</CardTitle>
            <CardDescription>Роли, отрасли и софт-скиллы помогают работодателю понять, чем вы сильны.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-5">
            <FormField id="about" label={<>Коротко о себе{mark("about")}</>} error={errors.about?.message}>
              <Textarea
                id="about"
                rows={4}
                placeholder="Проекты и задачи, которые вам интересны"
                aria-invalid={!!errors.about}
                {...register("about")}
              />
            </FormField>
            <ChipsField control={control} name="roles" label={<>Роли в команде{mark("roles")}</>} options={teamRoles.data} />
            <ChipsField
              control={control}
              name="industriesExp"
              label={<>Отрасли, где был опыт{mark("industriesExp")}</>}
              options={industries.data}
            />
            <ChipsField control={control} name="softSkills" label={<>Софт-скиллы{mark("softSkills")}</>} options={softSkills.data} />
          </CardContent>
          <CardFooter className="flex flex-wrap items-center gap-3 border-t border-border-subtle pt-5">
            <Button type="submit" disabled={update.isPending || !isDirty}>
              {update.isPending ? <Loader2 className="animate-spin" /> : <Save />} Сохранить профиль
            </Button>
            {isDirty && <span className="text-xs text-muted-foreground">Есть несохранённые изменения</span>}
            <FormAlert message={formError} className="w-full" />
          </CardFooter>
        </Card>
      </div>

      <div className="grid content-start gap-4">
        <ResumeUploadCard onParsed={applyResume} />
        <Card>
          <CardHeader>
            <CardTitle>Подтверждённый стек</CardTitle>
            <CardDescription>Навыки, подтверждённые тестом, ФСП или заданиями.</CardDescription>
          </CardHeader>
          <CardContent>
            {verified.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Пока нет. Пройдите <Link to="/candidate/grade" className="text-primary underline underline-offset-4">тест</Link> —
                навыки по его заданиям получат статус «проверено тестом».
              </p>
            ) : (
              <ul className="flex flex-wrap gap-1.5">
                {verified.map((skill) => (
                  <li key={skill.skill_id}>
                    <Badge variant={skill.status === "verified" ? "soft" : "outline"} title={SKILL_STATUS_LABELS[skill.status]}>
                      {skill.name}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        {profile.category && (
          <Card>
            <CardHeader>
              <CardTitle>Категория</CardTitle>
              <CardDescription>Определена тестом, резюме её не меняет.</CardDescription>
            </CardHeader>
            <CardContent className="font-mono text-sm font-bold">{profile.category.label}</CardContent>
          </Card>
        )}
      </div>
    </form>
  );
}

function ResumeSummary({ result, onDiscard }: { result: ResumeParseResult; onDiscard: () => void }) {
  const filled = result.from_resume ?? [];
  const warnings = result.warnings ?? [];
  return (
    <Card className="border-primary/40">
      <CardHeader className="grid-cols-[1fr_auto]">
        <div className="space-y-1.5">
          <CardTitle className="flex items-center gap-2">
            <FileText className="size-4 text-primary" aria-hidden /> Предзаполнено из резюме
          </CardTitle>
          <CardDescription>
            {filled.length > 0
              ? `Заполнили полей: ${filled.length}. Проверьте отмеченные «из резюме» и нажмите «Сохранить профиль» — до этого в профиль ничего не попадёт.`
              : "Новых данных для профиля не нашли."}
            {result.parser === "llm" && " Разбор дополнен языковой моделью — проверьте внимательно."}
          </CardDescription>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onDiscard}>
          <X /> Отменить
        </Button>
      </CardHeader>
      {(warnings.length > 0 || result.suggested_grade) && (
        <CardContent className="space-y-2 text-sm">
          {warnings.map((warning) => (
            <p key={warning} className="text-destructive-strong">
              {warning}
            </p>
          ))}
          {result.suggested_grade && (
            <p className="text-muted-foreground">
              Подсказка по стажу: <b className="font-mono text-foreground">{gradeLabel(result.suggested_grade)}</b>. Грейд вы
              выбираете сами, а подтверждает его тест.
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}

interface ChipsFieldProps {
  control: Control<ProfileFormValues>;
  name: Extract<FieldPath<ProfileFormValues>, "roles" | "industriesExp" | "softSkills">;
  label: ReactNode;
  options?: { slug: string; name: string }[];
}

/** Мультивыбор из короткого справочника кнопками-чипами. */
function ChipsField({ control, name, label, options }: ChipsFieldProps) {
  return (
    <fieldset className="grid gap-2">
      <legend className="mb-2 text-sm font-medium">{label}</legend>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <div className="flex flex-wrap gap-1.5">
            {(options ?? []).map((option) => {
              const active = field.value.includes(option.slug);
              return (
                <button
                  key={option.slug}
                  type="button"
                  aria-pressed={active}
                  onClick={() =>
                    field.onChange(active ? field.value.filter((item) => item !== option.slug) : [...field.value, option.slug])
                  }
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                    active ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted",
                  )}
                >
                  {option.name}
                </button>
              );
            })}
            {!options && <span className="text-xs text-muted-foreground">Загружаем справочник…</span>}
          </div>
        )}
      />
    </fieldset>
  );
}
