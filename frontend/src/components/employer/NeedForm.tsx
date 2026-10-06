import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useState, type BaseSyntheticEvent, type ReactNode } from "react";
import { Controller, useForm } from "react-hook-form";
import { SkillsMultiSelect } from "@/components/candidate/SkillsMultiSelect";
import { FormAlert } from "@/components/FormAlert";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import { INVALID_FORM_MESSAGE, revealFirstInvalid } from "@/lib/form-errors";
import { type NeedCreate, useIndustries } from "@/lib/employer-queries";
import { EMPTY_NEED_FORM, needFieldMap, type NeedFormValues, needSchema } from "@/lib/need-form";
import { GRADE_LABELS, SPECIALIZATION_FULL_LABELS, WORK_FORMAT_LABELS } from "@/lib/labels";
import { type Grade, type SkillOut, useGrades, useSkillCatalog, useSpecializations } from "@/lib/testing-queries";

interface NeedFormProps {
  initial?: Partial<NeedFormValues>;
  rawText?: string | null;
  submitLabel: string;
  footerNote?: ReactNode;
  pending: boolean;
  /** Отправка: возвращает промис мутации, ошибки раскладываются по полям. */
  onSubmit: (body: NeedCreate) => Promise<unknown>;
}

/**
 * Редактируемая форма потребности: и для разбора текста, и для ручного ввода, и для правки (новая версия).
 * Родитель перемонтирует форму через key, когда приходит новый черновик.
 */
export function NeedForm({ initial, rawText, submitLabel, footerNote, pending, onSubmit }: NeedFormProps) {
  const specializations = useSpecializations();
  const grades = useGrades();
  const industries = useIndustries();
  const catalog = useSkillCatalog();
  const [pickedNames, setPickedNames] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const skillNames = { ...Object.fromEntries((catalog.data ?? []).map((skill) => [skill.id, skill.name])), ...pickedNames };
  const rememberNames = (skills: SkillOut[]) =>
    setPickedNames((current) => ({ ...current, ...Object.fromEntries(skills.map((skill) => [skill.id, skill.name])) }));

  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<NeedFormValues>({
    resolver: zodResolver(needSchema),
    defaultValues: { ...EMPTY_NEED_FORM, ...initial },
    shouldFocusError: false,
  });

  const invalid = (_errors: unknown, event?: BaseSyntheticEvent) => {
    setFormError(INVALID_FORM_MESSAGE);
    revealFirstInvalid(event);
  };

  const submit = async (values: NeedFormValues, event?: BaseSyntheticEvent) => {
    setFormError(null);
    try {
      await onSubmit({
        title: values.title,
        raw_text: rawText || null,
        specialization: values.specialization,
        grade: values.grade as Grade,
        required_skills: values.requiredSkills,
        optional_skills: values.optionalSkills,
        team_description: values.teamDescription || null,
        industry: values.industry || null,
        work_format: values.workFormat || null,
        city: values.city || null,
        salary_from: values.salaryFrom,
        salary_to: values.salaryTo,
      });
    } catch (err) {
      if (applyValidationErrors(err, setError, needFieldMap)) invalid(null, event);
      else setFormError(apiError(err).message);
    }
  };

  const specOptions =
    specializations.data?.map((item) => ({ value: item.slug, label: item.name })) ??
    Object.entries(SPECIALIZATION_FULL_LABELS).map(([value, label]) => ({ value, label }));
  const gradeOptions =
    grades.data?.map((item) => ({ value: item.slug, label: item.name })) ??
    Object.entries(GRADE_LABELS).map(([value, label]) => ({ value, label }));
  const knownIndustry = (value: string) => industries.data?.some((item) => item.slug === value) ?? true;

  return (
    <form onSubmit={handleSubmit(submit, invalid)} noValidate>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <FormField id="need-title" label="Название *" error={errors.title?.message} className="sm:col-span-2">
          <Input
            id="need-title"
            placeholder="Например: Backend-разработчик в платёжную команду"
            aria-invalid={!!errors.title}
            {...register("title")}
          />
        </FormField>
        <FormField id="need-spec" label="Специализация *" error={errors.specialization?.message}>
          {/* Controller: варианты приходят из справочника позже, чем ставится значение. */}
          <Controller
            control={control}
            name="specialization"
            render={({ field }) => (
              <Select
                id="need-spec"
                aria-invalid={!!errors.specialization}
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
              >
                <option value="">Выберите специализацию</option>
                {specOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            )}
          />
        </FormField>
        <FormField id="need-grade" label="Грейд *" error={errors.grade?.message}>
          <Controller
            control={control}
            name="grade"
            render={({ field }) => (
              <Select
                id="need-grade"
                aria-invalid={!!errors.grade}
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
              >
                <option value="">Выберите грейд</option>
                {gradeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            )}
          />
        </FormField>
        <FormField
          id="need-required"
          label="Обязательный стек *"
          error={errors.requiredSkills?.message}
          hint="Вес навыка в совпадении — 1.0"
          className="sm:col-span-2"
        >
          <Controller
            control={control}
            name="requiredSkills"
            render={({ field }) => (
              <SkillsMultiSelect
                id="need-required"
                value={field.value}
                onChange={field.onChange}
                names={skillNames}
                onNamesChange={rememberNames}
                invalid={!!errors.requiredSkills}
              />
            )}
          />
        </FormField>
        <FormField id="need-optional" label="Желательный стек" hint="Вес навыка в совпадении — 0.3" className="sm:col-span-2">
          <Controller
            control={control}
            name="optionalSkills"
            render={({ field }) => (
              <SkillsMultiSelect
                id="need-optional"
                value={field.value}
                onChange={field.onChange}
                names={skillNames}
                onNamesChange={rememberNames}
              />
            )}
          />
        </FormField>
        <FormField
          id="need-team"
          label="Чем занимается команда"
          error={errors.teamDescription?.message}
          className="sm:col-span-2"
        >
          <Textarea id="need-team" rows={3} aria-invalid={!!errors.teamDescription} {...register("teamDescription")} />
        </FormField>
        <FormField id="need-industry" label="Отрасль">
          <Controller
            control={control}
            name="industry"
            render={({ field }) => (
              <Select id="need-industry" value={field.value} onChange={field.onChange} onBlur={field.onBlur}>
                <option value="">Не важно</option>
                {industries.data?.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.name}
                  </option>
                ))}
                {field.value && !knownIndustry(field.value) && <option value={field.value}>{field.value}</option>}
              </Select>
            )}
          />
        </FormField>
        <div className="grid grid-cols-2 gap-4">
          <FormField id="need-format" label="Формат">
            <Select id="need-format" {...register("workFormat")}>
              <option value="">Любой</option>
              {Object.entries(WORK_FORMAT_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField id="need-city" label="Город">
            <Input id="need-city" {...register("city")} />
          </FormField>
        </div>
        <FormField id="need-salary-from" label="Вилка от, ₽ на руки *" error={errors.salaryFrom?.message}>
          <Input
            id="need-salary-from"
            type="number"
            inputMode="numeric"
            min={0}
            step={1000}
            aria-invalid={!!errors.salaryFrom}
            {...register("salaryFrom", { valueAsNumber: true })}
          />
        </FormField>
        <FormField id="need-salary-to" label="Вилка до, ₽ на руки *" error={errors.salaryTo?.message}>
          <Input
            id="need-salary-to"
            type="number"
            inputMode="numeric"
            min={0}
            step={1000}
            aria-invalid={!!errors.salaryTo}
            {...register("salaryTo", { valueAsNumber: true })}
          />
        </FormField>
      </CardContent>
      <CardFooter className="mt-5 flex-wrap justify-between gap-3 border-t border-border-subtle pt-5">
        <span className="text-xs text-muted-foreground">{footerNote}</span>
        <Button type="submit" disabled={pending}>
          {pending && <Loader2 className="animate-spin" />}
          {submitLabel}
        </Button>
        <FormAlert message={formError} className="w-full" />
      </CardFooter>
    </form>
  );
}
