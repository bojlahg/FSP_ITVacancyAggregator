import {
  Briefcase,
  Building2,
  FlaskConical,
  Grid3x3,
  LayoutDashboard,
  ListChecks,
  Mail,
  Search,
  Target,
} from "lucide-react";
import { CabinetLayout, type CabinetNavItem } from "./CabinetLayout";

const nav: CabinetNavItem[] = [
  { to: "/employer", label: "Главная", icon: LayoutDashboard, end: true },
  { to: "/employer/needs", label: "Потребности", icon: Target },
  { to: "/employer/search", label: "Поиск по базе", icon: Search },
  { to: "/employer/categories", label: "Каталог категорий", icon: Grid3x3 },
  { to: "/employer/invitations", label: "Приглашения", icon: Mail },
  { to: "/employer/vacancies", label: "Вакансии и отклики", icon: Briefcase },
  { to: "/employer/vacancy-test", label: "Проверка под вакансию", icon: FlaskConical },
  { to: "/employer/tasks", label: "Задания", icon: ListChecks },
  { to: "/employer/company", label: "Профиль компании", icon: Building2 },
];

export default function EmployerLayout() {
  // TODO: заменить на данные GET /me + GET /employers/me и защитить маршрут.
  return (
    <CabinetLayout
      homePath="/employer"
      roleLabel="Работодатель"
      nav={nav}
      user={{ name: "Мария Рекрутер", caption: "Демо Банк" }}
    />
  );
}
