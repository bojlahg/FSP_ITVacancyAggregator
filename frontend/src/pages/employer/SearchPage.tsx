import { Search, SlidersHorizontal } from "lucide-react";
import { CandidateRow } from "@/components/employer/CandidateRow";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { GRADE_LABELS, SPECIALIZATION_FULL_LABELS } from "@/lib/labels";
// MOCK: заменить на GET /talent/search (фильтры — в query и в URL)
import { mockCandidates } from "@/mocks/talent";

export default function SearchPage() {
  // TODO: состояние фильтров в URL (useSearchParams), как на экране подборки.
  const results = mockCandidates.filter((candidate) => !candidate.outOfFilterReason);

  return (
    <>
      <PageHeader
        eyebrow="Поиск по базе"
        title="Поиск по всей базе"
        description="Без потребности: фильтры по категории, стеку, ФСП, зарплате и формату. Внутри категории выше стоят кандидаты с более сильным подтверждённым профилем."
      />

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="h-fit gap-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <SlidersHorizontal className="size-4 text-primary" aria-hidden /> Фильтры
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="search-spec">Специализация</Label>
              <Select id="search-spec" defaultValue="">
                <option value="">Любая</option>
                {Object.entries(SPECIALIZATION_FULL_LABELS).map(([slug, label]) => (
                  <option key={slug} value={slug}>
                    {label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="search-grade">Грейд</Label>
              <Select id="search-grade" defaultValue="">
                <option value="">Любой</option>
                {Object.entries(GRADE_LABELS).map(([slug, label]) => (
                  <option key={slug} value={slug}>
                    {label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="search-stack">Стек</Label>
              <Input id="search-stack" placeholder="Python, PostgreSQL" />
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <Checkbox /> только проверенный тестом
              </label>
            </div>
            <div className="grid gap-2">
              <Label>Зарплатные ожидания, ₽</Label>
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder="от" inputMode="numeric" aria-label="Ожидания от" />
                <Input placeholder="до" inputMode="numeric" aria-label="Ожидания до" />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="search-fsp-discipline">Дисциплина ФСП</Label>
              <Select id="search-fsp-discipline" defaultValue="">
                <option value="">Любая</option>
                <option value="product">Продуктовое программирование</option>
                <option value="algo">Алгоритмическое программирование</option>
                <option value="security">Информационная безопасность</option>
                <option value="robotics">Программирование робототехники</option>
              </Select>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <Checkbox /> есть достижения ФСП
              </label>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="search-city">Город</Label>
              <Input id="search-city" placeholder="Москва" />
            </div>
          </CardContent>
        </Card>

        <section className="min-w-0 space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-11 pl-9" placeholder="Навык, специализация или город" aria-label="Поиск" />
          </div>
          <div className="font-mono text-sm text-muted-foreground">Найдено: {results.length}</div>
          {results.length === 0 ? (
            <EmptyState icon={Search} title="Никого не нашли" description="Попробуйте ослабить фильтры." />
          ) : (
            results.map((candidate) => <CandidateRow key={candidate.id} candidate={candidate} explanationLimit={2} />)
          )}
        </section>
      </div>
    </>
  );
}
