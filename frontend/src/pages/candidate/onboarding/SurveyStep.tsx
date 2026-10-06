import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, ClipboardList, Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Controller, useForm, type FieldErrors, type Resolver } from "react-hook-form";
import { z } from "zod";
import { SkillsMultiSelect } from "@/components/candidate/SkillsMultiSelect";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormAlert } from "@/components/FormAlert";
import { SkeletonCards } from "@/components/SkeletonCards";
import { Button } from "@/components/ui/button";
import { CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiError, applyValidationErrors } from "@/lib/api-error";
import {
  type SkillOut,
  type SurveyQuestion,
  type SurveyResult,
  useSubmitSurvey,
  useSurveyQuestions,
} from "@/lib/testing-queries";
import { cn } from "@/lib/utils";

type SalaryValue = { from: string; to: string };
type FieldValue = string | string[] | SalaryValue;
type SurveyFormValues = Record<string, FieldValue>;

const TEXT_MAX_LENGTH = 2000;
// Больше вариантов — выпадающий список вместо радиокнопок.
const RADIO_MAX_OPTIONS = 6;

// Имена полей по индексу: id вопроса может содержать точки, а react-hook-form читает их как вложенность.
const fieldName = (index: number) => `q${index}`;

function parseNumber(raw: string): number | null {
  const value = Number(raw.trim().replace(/\s/g, "").replace(",", "."));
  return raw.trim() !== "" && Number.isFinite(value) ? value : null;
}

function questionSchema(question: SurveyQuestion): z.ZodType {
  const required = question.required;
  switch (question.kind) {
    case "single":
      return required ? z.string().min(1, "Выберите вариант") : z.string();
    case "multi":
      return required ? z.array(z.string()).min(1, "Выберите хотя бы один вариант") : z.array(z.string());
    case "skills":
      return required ? z.array(z.string()).min(1, "Добавьте хотя бы один навык") : z.array(z.string());
    case "number":
      return z.string().superRefine((raw, ctx) => {
        if (raw.trim() === "") {
          if (required) ctx.addIssue({ code: "custom", message: "Введите число" });
          return;
        }
        const value = parseNumber(raw);
        if (value === null || value < 0) ctx.addIssue({ code: "custom", message: "Введите неотрицательное число" });
      });
    case "salary_range":
      return z.object({ from: z.string(), to: z.string() }).superRefine(({ from, to }, ctx) => {
        if (from.trim() === "" && to.trim() === "") {
          if (required) ctx.addIssue({ code: "custom", message: "Укажите вилку: от и до" });
          return;
        }
        const min = parseNumber(from);
        const max = parseNumber(to);
        if (min === null || max === null) {
          ctx.addIssue({ code: "custom", message: "Укажите обе границы вилки" });
        } else if (min <= 0 || max <= 0) {
          ctx.addIssue({ code: "custom", message: "Суммы должны быть больше нуля" });
        } else if (min > max) {
          ctx.addIssue({ code: "custom", message: "«От» не может быть больше «до»" });
        }
      });
    case "text":
      return required
        ? z.string().trim().min(1, "Заполните поле").max(TEXT_MAX_LENGTH, `Не длиннее ${TEXT_MAX_LENGTH} символов`)
        : z.string().max(TEXT_MAX_LENGTH, `Не длиннее ${TEXT_MAX_LENGTH} символов`);
  }
}

function defaultValue(question: SurveyQuestion): FieldValue {
  if (question.kind === "multi" || question.kind === "skills") return [];
  if (question.kind === "salary_range") return { from: "", to: "" };
  return "";
}

/** Значение формы → ответ API; пустые необязательные ответы не отправляем. */
function toAnswer(question: SurveyQuestion, value: FieldValue | undefined): unknown {
  if (value === undefined) return undefined;
  switch (question.kind) {
    case "single":
    case "text": {
      const text = typeof value === "string" ? value.trim() : "";
      return text === "" ? undefined : text;
    }
    case "multi":
    case "skills":
      return Array.isArray(value) && value.length > 0 ? value : undefined;
    case "number":
      return typeof value === "string" ? (parseNumber(value) ?? undefined) : undefined;
    case "salary_range": {
      if (typeof value !== "object" || Array.isArray(value)) return undefined;
      const from = parseNumber(value.from);
      const to = parseNumber(value.to);
      return from !== null && to !== null ? { from, to } : undefined;
    }
  }
}

function errorOf(errors: FieldErrors<SurveyFormValues>, name: string): string | undefined {
  const error = errors[name] as { message?: unknown } | undefined;
  return typeof error?.message === "string" ? error.message : undefined;
}

/** 8–10 вопросов делим на 2–3 экрана, чтобы опрос не выглядел простынёй. */
function paginate<T>(items: T[]): T[][] {
  const pageCount = items.length <= 4 ? 1 : items.length <= 8 ? 2 : 3;
  const size = Math.ceil(items.length / pageCount);
  const pages: T[][] = [];
  for (let start = 0; start < items.length; start += size) pages.push(items.slice(start, start + size));
  return pages;
}

interface SurveyStepProps {
  onDone: (result: SurveyResult) => void;
}

export function SurveyStep({ onDone }: SurveyStepProps) {
  const questions = useSurveyQuestions();

  if (questions.isPending) {
    return (
      <CardContent>
        <SkeletonCards count={2} />
      </CardContent>
    );
  }
  if (questions.isError) {
    return (
      <CardContent>
        <ErrorState
          title="Не удалось загрузить опрос"
          description={apiError(questions.error).message}
          onRetry={() => void questions.refetch()}
        />
      </CardContent>
    );
  }
  if (questions.data.length === 0) {
    return (
      <CardContent>
        <EmptyState icon={ClipboardList} title="Вопросов пока нет" description="Опрос ещё не настроен. Загляните позже." />
      </CardContent>
    );
  }
  return <SurveyForm questions={questions.data} onDone={onDone} />;
}

function SurveyForm({ questions, onDone }: { questions: SurveyQuestion[]; onDone: (result: SurveyResult) => void }) {
  const submit = useSubmitSurvey();
  const [page, setPage] = useState(0);
  const [skillNames, setSkillNames] = useState<Record<string, string>>({});

  const indexed = useMemo(() => questions.map((question, index) => ({ question, name: fieldName(index) })), [questions]);
  const pages = useMemo(() => paginate(indexed), [indexed]);

  const { resolver, defaults, apiFieldMap } = useMemo(() => {
    const shape: Record<string, z.ZodType> = {};
    const values: SurveyFormValues = {};
    const fieldMap: Record<string, string> = {};
    for (const { question, name } of indexed) {
      shape[name] = questionSchema(question);
      values[name] = defaultValue(question);
      fieldMap[question.id] = name;
    }
    return {
      resolver: zodResolver(z.object(shape)) as unknown as Resolver<SurveyFormValues>,
      defaults: values,
      apiFieldMap: fieldMap,
    };
  }, [indexed]);

  const {
    control,
    handleSubmit,
    trigger,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SurveyFormValues>({ resolver, defaultValues: defaults });

  const currentPage = pages[page] ?? [];
  const isLastPage = page === pages.length - 1;

  const onSubmit = async (values: SurveyFormValues) => {
    const answers: Record<string, unknown> = {};
    for (const { question, name } of indexed) {
      const answer = toAnswer(question, values[name]);
      if (answer !== undefined) answers[question.id] = answer;
    }
    try {
      onDone(await submit.mutateAsync(answers));
    } catch (err) {
      const { status, message } = apiError(err);
      if (!(status === 422 && applyValidationErrors(err, setError, apiFieldMap))) {
        setError("root.server", { message });
      }
    }
  };

  // Ошибка на одном из прошлых экранов — возвращаемся туда.
  const onInvalid = (invalid: FieldErrors<SurveyFormValues>) => {
    const firstPage = pages.findIndex((items) => items.some(({ name }) => invalid[name]));
    if (firstPage >= 0) setPage(firstPage);
  };

  const next = async () => {
    const valid = await trigger(currentPage.map(({ name }) => name));
    if (valid) setPage((current) => current + 1);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit, onInvalid)} noValidate>
      <CardHeader>
        <CardTitle>Расскажите о себе</CardTitle>
        <CardDescription>
          {pages.length > 1 ? `Часть ${page + 1} из ${pages.length} · ` : ""}
          По ответам предложим специализацию и подскажем грейд. Обязательные вопросы отмечены звёздочкой.
        </CardDescription>
      </CardHeader>

      <CardContent className="mt-5 grid gap-7">
        {currentPage.map(({ question, name }) => {
          const id = `survey-${name}`;
          const error = errorOf(errors, name);
          const errorId = error ? `${id}-error` : undefined;
          return (
            <fieldset key={question.id} className="grid gap-3" aria-describedby={errorId}>
              <legend className="mb-3 text-sm font-medium">
                {question.text}
                {question.required && (
                  <span className="ml-1 text-destructive-strong" aria-hidden>
                    *
                  </span>
                )}
                {question.kind === "multi" && (
                  <span className="ml-2 font-normal text-muted-foreground">можно выбрать несколько</span>
                )}
              </legend>
              <Controller
                control={control}
                name={name}
                render={({ field }) => (
                  <QuestionInput
                    id={id}
                    question={question}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    invalid={Boolean(error)}
                    describedBy={errorId}
                    skillNames={skillNames}
                    onSkillNames={(skills) =>
                      setSkillNames((current) => ({
                        ...current,
                        ...Object.fromEntries(skills.map((skill) => [skill.id, skill.name])),
                      }))
                    }
                  />
                )}
              />
              {error && (
                <p id={errorId} className="text-xs font-medium text-destructive-strong" role="alert">
                  {error}
                </p>
              )}
            </fieldset>
          );
        })}
        <FormAlert message={errors.root?.server?.message} />
      </CardContent>

      <CardFooter className="mt-5 justify-between gap-2 border-t border-border-subtle pt-5">
        <Button type="button" variant="ghost" onClick={() => setPage((current) => current - 1)} disabled={page === 0}>
          <ArrowLeft /> Назад
        </Button>
        {isLastPage ? (
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
            Узнать специализацию <ArrowRight />
          </Button>
        ) : (
          <Button type="button" onClick={() => void next()}>
            Далее <ArrowRight />
          </Button>
        )}
      </CardFooter>
    </form>
  );
}

interface QuestionInputProps {
  id: string;
  question: SurveyQuestion;
  value: FieldValue;
  onChange: (value: FieldValue) => void;
  onBlur: () => void;
  invalid: boolean;
  describedBy?: string;
  skillNames: Record<string, string>;
  onSkillNames: (skills: SkillOut[]) => void;
}

const optionClass =
  "flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm transition-colors hover:bg-muted has-[:checked]:border-primary has-[:checked]:bg-primary-tint has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/40";

function QuestionInput({
  id,
  question,
  value,
  onChange,
  onBlur,
  invalid,
  describedBy,
  skillNames,
  onSkillNames,
}: QuestionInputProps) {
  const options = question.options ?? [];
  const aria = { "aria-invalid": invalid || undefined, "aria-describedby": describedBy };

  switch (question.kind) {
    case "single": {
      const selected = typeof value === "string" ? value : "";
      if (options.length > RADIO_MAX_OPTIONS) {
        return (
          <Select id={id} value={selected} onChange={(event) => onChange(event.target.value)} onBlur={onBlur} {...aria}>
            <option value="">Выберите вариант</option>
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </Select>
        );
      }
      return (
        <div role="radiogroup" className="grid gap-2 sm:grid-cols-2" {...aria}>
          {options.map((option) => (
            <label key={option.id} className={optionClass}>
              <input
                type="radio"
                name={id}
                value={option.id}
                checked={selected === option.id}
                onChange={() => onChange(option.id)}
                onBlur={onBlur}
                className="size-4 accent-primary outline-none"
              />
              {option.label}
            </label>
          ))}
        </div>
      );
    }
    case "multi": {
      const selected = Array.isArray(value) ? value : [];
      return (
        <div className="grid gap-2 sm:grid-cols-2" {...aria}>
          {options.map((option) => (
            <label key={option.id} className={optionClass}>
              <Checkbox
                checked={selected.includes(option.id)}
                onChange={(event) =>
                  onChange(
                    event.target.checked ? [...selected, option.id] : selected.filter((item) => item !== option.id),
                  )
                }
                onBlur={onBlur}
              />
              {option.label}
            </label>
          ))}
        </div>
      );
    }
    case "skills":
      return (
        <SkillsMultiSelect
          id={id}
          value={Array.isArray(value) ? value : []}
          onChange={onChange}
          names={skillNames}
          onNamesChange={onSkillNames}
          invalid={invalid}
          describedBy={describedBy}
        />
      );
    case "number":
      return (
        <Input
          id={id}
          type="number"
          inputMode="decimal"
          min={0}
          className="max-w-48 font-mono"
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
          {...aria}
        />
      );
    case "salary_range": {
      const range = typeof value === "object" && !Array.isArray(value) ? value : { from: "", to: "" };
      return (
        <div className="flex flex-wrap items-center gap-2" {...aria}>
          <Input
            id={id}
            type="number"
            inputMode="numeric"
            min={0}
            step={5000}
            placeholder="от"
            aria-label="Зарплата от, ₽ на руки"
            className={cn("w-40 font-mono", invalid && "border-destructive")}
            value={range.from}
            onChange={(event) => onChange({ ...range, from: event.target.value })}
            onBlur={onBlur}
          />
          <span className="text-muted-foreground" aria-hidden>
            —
          </span>
          <Input
            type="number"
            inputMode="numeric"
            min={0}
            step={5000}
            placeholder="до"
            aria-label="Зарплата до, ₽ на руки"
            className={cn("w-40 font-mono", invalid && "border-destructive")}
            value={range.to}
            onChange={(event) => onChange({ ...range, to: event.target.value })}
            onBlur={onBlur}
          />
          <span className="font-mono text-sm text-muted-foreground">₽ в месяц</span>
        </div>
      );
    }
    case "text":
      return (
        <Textarea
          id={id}
          maxLength={TEXT_MAX_LENGTH}
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
          {...aria}
        />
      );
  }
}
