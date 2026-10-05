import { ArrowLeft, Loader2, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { NeedForm } from "@/components/employer/NeedForm";
import { NeedTextIssues } from "@/components/employer/NeedTextIssues";
import { FormAlert } from "@/components/FormAlert";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { apiError } from "@/lib/api-error";
import { type NeedParseResult, useCreateNeed, useParseNeed } from "@/lib/employer-queries";
import { needFormValues, type NeedFormValues } from "@/lib/need-form";

const MIN_TEXT_LENGTH = 20;

const PARSER_LABELS: Record<NeedParseResult["parser"], string> = {
  dict: "Разобрано по словарю навыков",
  llm: "Разобрано словарём и языковой моделью (Yandex AI Studio)",
};

export default function NeedNewPage() {
  const navigate = useNavigate();
  const parse = useParseNeed();
  const create = useCreateNeed();
  const [rawText, setRawText] = useState("");
  const [parsed, setParsed] = useState<{ result: NeedParseResult; text: string; values: Partial<NeedFormValues> } | null>(
    null,
  );
  // Новый разбор перемонтирует форму с новыми значениями.
  const [formKey, setFormKey] = useState(0);

  const runParse = () => {
    const text = rawText.trim();
    parse.mutate(text, {
      onSuccess: (result) => {
        setParsed({ result, text, values: needFormValues(result.draft) });
        setFormKey((key) => key + 1);
      },
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
        description="Вставьте текст вакансии — мы разберём его в редактируемую форму. Или заполните форму сразу. Вилка от–до обязательна."
      />

      <div className="grid max-w-4xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="flex size-6 items-center justify-center rounded-full bg-primary font-mono text-xs text-primary-foreground">
                1
              </span>
              Текст вакансии
            </CardTitle>
            <CardDescription>Стек, грейд, формат, город и бюджет — в свободной форме. Этот шаг можно пропустить.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <Textarea
              aria-label="Текст вакансии или описание потребности"
              placeholder="Вставьте текст вакансии или опишите, кого ищете"
              rows={9}
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
            />
            <FormAlert message={parse.isError ? apiError(parse.error).message : null} />
          </CardContent>
          <CardFooter className="flex-wrap gap-3">
            <Button onClick={runParse} disabled={rawText.trim().length < MIN_TEXT_LENGTH || parse.isPending}>
              {parse.isPending ? <Loader2 className="animate-spin" /> : <Wand2 />} Разобрать
            </Button>
            {rawText.trim().length > 0 && rawText.trim().length < MIN_TEXT_LENGTH && (
              <span className="text-xs text-muted-foreground">Нужно хотя бы {MIN_TEXT_LENGTH} символов</span>
            )}
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="flex size-6 items-center justify-center rounded-full bg-primary font-mono text-xs text-primary-foreground">
                2
              </span>
              Потребность
            </CardTitle>
            <CardDescription>
              {parsed ? "Проверьте разбор и поправьте, если нужно." : "Заполните вручную или сначала разберите текст."}
            </CardDescription>
          </CardHeader>
          {parsed && (
            <CardContent className="grid gap-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Sparkles className="size-4 text-primary" aria-hidden /> {PARSER_LABELS[parsed.result.parser]}
              </div>
              <NeedTextIssues issues={parsed.result.text_issues ?? []} />
              {parsed.result.unmapped_terms.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 rounded-lg bg-destructive-tint px-3 py-2 text-sm">
                  <span className="mr-1">Не распознали:</span>
                  {parsed.result.unmapped_terms.map((term) => (
                    <Badge key={term} variant="muted" className="bg-background">
                      {term}
                    </Badge>
                  ))}
                  <span className="basis-full text-xs text-muted-foreground">
                    Этих терминов нет в справочнике навыков — добавьте близкие навыки вручную, если они важны.
                  </span>
                </div>
              )}
            </CardContent>
          )}
          <NeedForm
            key={formKey}
            initial={parsed?.values}
            rawText={parsed?.text ?? (rawText.trim() || null)}
            submitLabel="Сохранить и открыть подборку"
            footerNote="После сохранения покажем рекомендованные категории, кандидатов и покрытие вилки."
            pending={create.isPending}
            onSubmit={(body) =>
              create.mutateAsync(body).then((need) => navigate(`/employer/needs/${need.id}`))
            }
          />
        </Card>
      </div>
    </>
  );
}
