import { Download, FileUp } from "lucide-react";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

// MOCK: стек придёт из GET /candidates/me с источником каждого навыка
const verifiedStack = ["Python", "PostgreSQL", "SQL", "Git"];
const declaredStack = ["FastAPI", "Docker", "Redis"];

export default function ProfilePage() {
  return (
    <>
      <PageHeader
        eyebrow="Профиль и резюме"
        title="Профиль"
        description="Данные профиля видят работодатели (фамилия скрыта до контакта). Резюме помогает заполнить форму быстрее, но не влияет на категорию."
        actions={
          <Button variant="outline" disabled title="Будет доступно после подключения backend">
            <Download /> PDF-профиль
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card>
          <CardHeader>
            <CardTitle>Основное</CardTitle>
            <CardDescription>TODO: форма на react-hook-form + zod, сохранение через PUT /candidates/me</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <FormField id="first-name" label="Имя">
              <Input id="first-name" defaultValue="Анна" />
            </FormField>
            <FormField id="last-name" label="Фамилия" hint="Работодатель видит только первую букву">
              <Input id="last-name" defaultValue="Кузнецова" />
            </FormField>
            <FormField id="city" label="Город">
              <Input id="city" defaultValue="Москва" />
            </FormField>
            <FormField id="format" label="Формат работы">
              <Select id="format" defaultValue="hybrid">
                <option value="office">Офис</option>
                <option value="hybrid">Гибрид</option>
                <option value="remote">Удалённо</option>
              </Select>
            </FormField>
            <FormField id="salary-from" label="Ожидания, от ₽">
              <Input id="salary-from" inputMode="numeric" defaultValue="240000" />
            </FormField>
            <FormField id="salary-to" label="Ожидания, до ₽">
              <Input id="salary-to" inputMode="numeric" defaultValue="280000" />
            </FormField>
            <FormField id="about" label="О себе" className="sm:col-span-2">
              <Textarea id="about" placeholder="Коротко о проектах и задачах, которые вам интересны" />
            </FormField>
          </CardContent>
        </Card>

        <div className="grid content-start gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Резюме</CardTitle>
              <CardDescription>PDF до 5 МБ — предзаполним форму, вы подтвердите данные.</CardDescription>
            </CardHeader>
            <CardContent>
              <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center text-sm hover:bg-muted">
                <FileUp className="size-6 text-primary" aria-hidden />
                <span className="font-medium">Загрузить PDF</span>
                <span className="text-xs text-muted-foreground">Сканы без текста пока не распознаём</span>
                <input type="file" accept="application/pdf" className="sr-only" disabled />
              </label>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Стек</CardTitle>
              <CardDescription>У каждого навыка есть источник и статус.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <div className="text-xs text-muted-foreground">Проверено тестом</div>
                <div className="flex flex-wrap gap-1.5">
                  {verifiedStack.map((skill) => (
                    <Badge key={skill} variant="soft">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <div className="text-xs text-muted-foreground">Заявлено</div>
                <div className="flex flex-wrap gap-1.5">
                  {declaredStack.map((skill) => (
                    <Badge key={skill} variant="muted">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
