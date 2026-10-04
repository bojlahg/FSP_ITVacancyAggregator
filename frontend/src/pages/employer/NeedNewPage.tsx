import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, FileText, ListChecks, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";
import { CategoryBadge } from "@/components/CategoryBadge";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { SalaryRange } from "@/components/SalaryRange";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { GRADE_LABELS, SPECIALIZATION_FULL_LABELS } from "@/lib/labels";

const splitList = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

// Вилка от–до обязательна (инвариант продукта, docs/implementation.md §8.1 п.2).
const needSchema = z
  .object({
    title: z.string().trim().min(3, "Укажите название"),
    specialization: z.string().min(1, "Выберите специализацию"),
    grade: z.string().min(1, "Выберите грейд"),
    requiredStack: z.string().refine((value) => splitList(value).length > 0, "Укажите хотя бы один навык"),
    desiredStack: z.string(),
    industry: z.string(),
    format: z.enum(["office", "hybrid", "remote"]),
    city: z.string().trim(),
    salaryFrom: z.number({ error: "Укажите сумму" }).int().positive("Сумма должна быть больше нуля"),
    salaryTo: z.number({ error: "Укажите сумму" }).int().positive("Сумма должна быть больше нуля"),
  })
  .refine((values) => values.salaryTo >= values.salaryFrom, {
    path: ["salaryTo"],
    message: "Верхняя граница не может быть меньше нижней",
  });

type NeedValues = z.infer<typeof needSchema>;

const sampleText =
  "Ищем бэкендера уровня middle в платёжную команду. Python, FastAPI, PostgreSQL обязательно, Kafka и Docker будут плюсом. Гибрид, Москва. Бюджет 220–260 тысяч на руки. Опыт с 1С и ЕГАИС приветствуется.";

// MOCK: результат POST /needs/parse {raw_text}
const mockParsed: NeedValues & { unrecognized: string[] } = {
  title: "Backend-разработчик в платёжную команду",
  specialization: "backend",
  grade: "middle",
  requiredStack: "Python, FastAPI, PostgreSQL",
  desiredStack: "Kafka, Docker",
  industry: "Финтех",
  format: "hybrid",
  city: "Москва",
  salaryFrom: 220_000,
  salaryTo: 260_000,
  unrecognized: ["1С", "ЕГАИС"],
};

export default function NeedNewPage() {
  const [tab, setTab] = useState("text");
  const [rawText, setRawText] = useState(sampleText);
  const [parsed, setParsed] = useState<typeof mockParsed | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<NeedValues>({
    resolver: zodResolver(needSchema),
    defaultValues: {
      title: "",
      specialization: "backend",
      grade: "middle",
      requiredStack: "",
      desiredStack: "",
      industry: "",
      format: "hybrid",
      city: "",
    },
  });

  const parse = () => {
    // TODO: POST /needs/parse через useMutation (словарь → LLM); фронт только показывает результат.
    console.info("[needs] TODO: POST /needs/parse", { length: rawText.length });
    setParsed(mockParsed);
  };

  const applyParsed = () => {
    if (!parsed) return;
    const { unrecognized: _unrecognized, ...values } = parsed;
    reset(values);
    setTab("form");
  };

  const onSubmit = (values: NeedValues) => {
    // TODO: POST /needs → переход на /employer/needs/{id}
    console.info("[needs] TODO: POST /needs", {
      ...values,
      requiredStack: splitList(values.requiredStack),
      desiredStack: splitList(values.desiredStack),
    });
  };

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-3 mb-2">
        <Link to="/employer/needs">
          <ArrowLeft /> Потребности
        </Link>
      </Button>
      <PageHeader
        eyebrow="Новая потребность"
        title="Кого вы ищете?"
        description="Опишите задачу своими словами — мы разберём текст в редактируемую форму. Или заполните форму сразу. Вилка от–до обязательна."
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="text">
            <FileText /> Текстом
          </TabsTrigger>
          <TabsTrigger value="form">
            <ListChecks /> Формой
          </TabsTrigger>
        </TabsList>

        <TabsContent value="text">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Описание задачи</CardTitle>
                <CardDescription>Стек, грейд, формат, город и бюджет — в свободной форме</CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea
                  aria-label="Описание потребности"
                  rows={8}
                  value={rawText}
                  onChange={(event) => setRawText(event.target.value)}
                />
              </CardContent>
              <CardFooter>
                <Button onClick={parse} disabled={rawText.trim().length < 20}>
                  <Wand2 /> Разобрать
                </Button>
              </CardFooter>
            </Card>

            <Card className={parsed ? "" : "border-dashed"}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="size-4 text-primary" aria-hidden /> Разбор
                </CardTitle>
                <CardDescription>Проверьте и поправьте перед сохранением</CardDescription>
              </CardHeader>
              <CardContent>
                {parsed ? (
                  <dl className="grid gap-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <dt className="w-28 text-muted-foreground">Категория</dt>
                      <dd>
                        <CategoryBadge specialization={parsed.specialization} grade={parsed.grade} />
                      </dd>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <dt className="w-28 text-muted-foreground">Обязательно</dt>
                      <dd className="flex flex-wrap gap-1.5">
                        {splitList(parsed.requiredStack).map((skill) => (
                          <Badge key={skill} variant="soft">
                            {skill}
                          </Badge>
                        ))}
                      </dd>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <dt className="w-28 text-muted-foreground">Желательно</dt>
                      <dd className="flex flex-wrap gap-1.5">
                        {splitList(parsed.desiredStack).map((skill) => (
                          <Badge key={skill} variant="muted">
                            {skill}
                          </Badge>
                        ))}
                      </dd>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <dt className="w-28 text-muted-foreground">Вилка</dt>
                      <dd>
                        <SalaryRange from={parsed.salaryFrom} to={parsed.salaryTo} />
                      </dd>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <dt className="w-28 text-muted-foreground">Формат</dt>
                      <dd>Гибрид · {parsed.city}</dd>
                    </div>
                    <div className="mt-1 flex items-center gap-2 rounded-lg bg-destructive-tint px-3 py-2">
                      <span className="size-1.5 shrink-0 rounded-full bg-destructive" aria-hidden />
                      <span>
                        Не распознали: <b className="font-mono">{parsed.unrecognized.join(", ")}</b>
                      </span>
                    </div>
                    <Button className="mt-2 w-fit" variant="outline" onClick={applyParsed}>
                      Перенести в форму
                    </Button>
                  </dl>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Нажмите «Разобрать» — здесь появятся специализация, грейд, стек и вилка.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="form">
          <Card className="max-w-4xl">
            <form onSubmit={handleSubmit(onSubmit)} noValidate>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <FormField id="need-title" label="Название *" error={errors.title?.message} className="sm:col-span-2">
                  <Input id="need-title" aria-invalid={!!errors.title} {...register("title")} />
                </FormField>
                <FormField id="need-spec" label="Специализация *" error={errors.specialization?.message}>
                  <Select id="need-spec" {...register("specialization")}>
                    {Object.entries(SPECIALIZATION_FULL_LABELS).map(([slug, label]) => (
                      <option key={slug} value={slug}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </FormField>
                <FormField id="need-grade" label="Грейд *" error={errors.grade?.message}>
                  <Select id="need-grade" {...register("grade")}>
                    {Object.entries(GRADE_LABELS).map(([slug, label]) => (
                      <option key={slug} value={slug}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </FormField>
                <FormField
                  id="need-required"
                  label="Обязательный стек *"
                  error={errors.requiredStack?.message}
                  hint="Через запятую"
                >
                  <Input id="need-required" aria-invalid={!!errors.requiredStack} {...register("requiredStack")} />
                </FormField>
                <FormField id="need-desired" label="Желательный стек" hint="Через запятую">
                  <Input id="need-desired" {...register("desiredStack")} />
                </FormField>
                <FormField id="need-industry" label="Отрасль">
                  <Input id="need-industry" {...register("industry")} />
                </FormField>
                <div className="grid grid-cols-2 gap-4">
                  <FormField id="need-format" label="Формат">
                    <Select id="need-format" {...register("format")}>
                      <option value="office">Офис</option>
                      <option value="hybrid">Гибрид</option>
                      <option value="remote">Удалённо</option>
                    </Select>
                  </FormField>
                  <FormField id="need-city" label="Город">
                    <Input id="need-city" {...register("city")} />
                  </FormField>
                </div>
                <FormField id="need-salary-from" label="Вилка от, ₽ *" error={errors.salaryFrom?.message}>
                  <Input
                    id="need-salary-from"
                    type="number"
                    inputMode="numeric"
                    step={1000}
                    aria-invalid={!!errors.salaryFrom}
                    {...register("salaryFrom", { valueAsNumber: true })}
                  />
                </FormField>
                <FormField id="need-salary-to" label="Вилка до, ₽ *" error={errors.salaryTo?.message}>
                  <Input
                    id="need-salary-to"
                    type="number"
                    inputMode="numeric"
                    step={1000}
                    aria-invalid={!!errors.salaryTo}
                    {...register("salaryTo", { valueAsNumber: true })}
                  />
                </FormField>
              </CardContent>
              <CardFooter className="mt-5 justify-between gap-3 border-t border-border-subtle pt-5">
                <span className="text-xs text-muted-foreground">
                  После сохранения сразу покажем покрытие вилки по категории.
                </span>
                <Button type="submit" disabled={isSubmitting}>
                  Сохранить и открыть подборку
                </Button>
              </CardFooter>
            </form>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  );
}
