import { Link2, ShieldCheck, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

// docs/implementation.md §6.4 — значения по умолчанию для приватности
const privacyOptions = [
  { id: "show-last-name", label: "Показывать фамилию до контакта", checked: false },
  { id: "show-fsp", label: "Показывать достижения ФСП", checked: true },
  { id: "show-salary", label: "Показывать зарплатные ожидания", checked: true },
];

const searchStatuses = [
  { value: "active", label: "Активно ищу" },
  { value: "open", label: "Открыт к предложениям" },
  { value: "not_looking", label: "Не ищу — профиль скрыт из поиска" },
];

// MOCK: даты согласий из GET /candidates/me
const consents = [
  { label: "Обработка персональных данных", date: "23.09.2026" },
  { label: "Публикация профиля работодателям", date: "23.09.2026" },
];

export default function SettingsPage() {
  // TODO: PUT /candidates/me/privacy, /candidates/me/consents; формы на react-hook-form.
  return (
    <>
      <PageHeader
        eyebrow="Настройки"
        title="Настройки"
        description="Приватность, согласия, привязка ФСП ID и статус поиска. Изменения вступают в силу сразу."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Статус поиска</CardTitle>
            <CardDescription>Влияет на то, видят ли вас работодатели</CardDescription>
          </CardHeader>
          <CardContent role="radiogroup" aria-label="Статус поиска" className="grid gap-2">
            {searchStatuses.map((status, index) => (
              <label
                key={status.value}
                className="flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm has-checked:border-primary has-checked:bg-primary-tint"
              >
                <input type="radio" name="search-status" defaultChecked={index === 1} className="accent-primary" />
                {status.label}
              </label>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-primary" aria-hidden /> Приватность
            </CardTitle>
            <CardDescription>Слепой первый просмотр: без фото, возраста и пола</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {privacyOptions.map((option) => (
              <label key={option.id} className="flex items-center gap-3 text-sm">
                <Checkbox defaultChecked={option.checked} /> {option.label}
              </label>
            ))}
            <Separator className="my-1" />
            <div className="text-sm">
              <div className="font-medium">Скрыть профиль от компаний</div>
              <div className="text-xs text-muted-foreground">Например, от текущего работодателя</div>
              <Input className="mt-2" placeholder="Начните вводить название компании" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Link2 className="size-4 text-primary" aria-hidden /> ФСП ID
            </CardTitle>
            <CardDescription>
              Достижения ФСП поднимают вас в выдаче. Без привязки профиль работает полностью.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 sm:flex-row">
            <Input placeholder="Например, FSP-000123" aria-label="ФСП ID" />
            <Button variant="outline">Привязать</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Согласия</CardTitle>
            <CardDescription>Согласие на публикацию можно отозвать — профиль исчезнет из поиска</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {consents.map((consent) => (
              <div key={consent.label} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>{consent.label}</span>
                <Badge variant="muted">с {consent.date}</Badge>
              </div>
            ))}
            <Separator className="my-1" />
            <Button variant="destructive" className="w-fit">
              <Trash2 /> Удалить аккаунт
            </Button>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
