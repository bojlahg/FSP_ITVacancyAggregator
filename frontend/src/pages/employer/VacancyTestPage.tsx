import { FlaskConical, RefreshCw } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
// MOCK: заменить на POST /vacancy-tests/preview {raw_text | need_id}
import { mockNeeds } from "@/mocks/talent";

const mockBlueprint = [
  { topic: "Python", weight: 30 },
  { topic: "Базы данных", weight: 30 },
  { topic: "HTTP и API", weight: 20 },
  { topic: "Очереди сообщений", weight: 10 },
  { topic: "Алгоритмы", weight: 10 },
];

const mockExampleSets = [
  [
    { topic: "Базы данных", difficulty: "средняя", text: "Какой индекс ускорит запрос с фильтром по status и сортировкой по created_at?" },
    { topic: "Python", difficulty: "средняя", text: "Что выведет функция с изменяемым аргументом по умолчанию после двух вызовов?" },
    { topic: "HTTP и API", difficulty: "лёгкая", text: "Какой код ответа вернуть при повторном создании ресурса с тем же ключом идемпотентности?" },
  ],
  [
    { topic: "Базы данных", difficulty: "средняя", text: "Какой уровень изоляции защитит от неповторяемого чтения при переводе между счетами?" },
    { topic: "Python", difficulty: "средняя", text: "В каком порядке выполнятся корутины, запущенные через asyncio.gather?" },
    { topic: "HTTP и API", difficulty: "лёгкая", text: "Какой заголовок нужен, чтобы клиент повторил запрос не раньше чем через 30 секунд?" },
  ],
];

export default function VacancyTestPage() {
  const [generation, setGeneration] = useState(0);
  const examples = mockExampleSets[generation % mockExampleSets.length] ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Проверка под вакансию"
        title="Проверка под вакансию"
        description="Покажем, как платформа проверит кандидата под вашу вакансию: blueprint теста по темам и примеры заданий. Повторная генерация даёт другие задания той же сложности."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle>Источник</CardTitle>
            <CardDescription>Выберите потребность или вставьте текст вакансии</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <Select aria-label="Потребность" defaultValue={mockNeeds[0]?.id}>
              {mockNeeds.map((need) => (
                <option key={need.id} value={need.id}>
                  {need.title}
                </option>
              ))}
            </Select>
            <Textarea rows={6} placeholder="…или вставьте описание вакансии" aria-label="Текст вакансии" />
          </CardContent>
          <CardFooter>
            {/* TODO: POST /vacancy-tests/preview */}
            <Button onClick={() => setGeneration((value) => value + 1)}>
              <FlaskConical /> Построить проверку
            </Button>
          </CardFooter>
        </Card>

        <div className="grid content-start gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Blueprint</CardTitle>
              <CardDescription>Доля заданий по темам · Backend · Middle</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              {mockBlueprint.map((item) => (
                <div key={item.topic} className="grid grid-cols-[140px_1fr_40px] items-center gap-3 text-sm">
                  <span>{item.topic}</span>
                  <Progress value={item.weight * 2} />
                  <span className="text-right font-mono font-bold">{item.weight}%</span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="grid-cols-[1fr_auto]">
              <div>
                <CardTitle>Примеры заданий</CardTitle>
                <CardDescription>Генерация №{generation + 1} · ключи ответов не показываются</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => setGeneration((value) => value + 1)}>
                <RefreshCw /> Ещё вариант
              </Button>
            </CardHeader>
            <CardContent>
              <ol className="grid gap-3">
                {examples.map((example, index) => (
                  <li key={example.text} className="rounded-lg border p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-muted-foreground">#{index + 1}</span>
                      <Badge variant="soft">{example.topic}</Badge>
                      <Badge variant="muted">сложность: {example.difficulty}</Badge>
                    </div>
                    <p className="text-sm">{example.text}</p>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
