import {
  Award,
  Briefcase,
  ClipboardList,
  LayoutDashboard,
  ListChecks,
  Mail,
  Send,
  Settings,
  UserRound,
} from "lucide-react";
import { CabinetLayout, type CabinetNavItem } from "./CabinetLayout";

const nav: CabinetNavItem[] = [
  { to: "/candidate", label: "Главная", icon: LayoutDashboard, end: true },
  { to: "/candidate/invitations", label: "Приглашения", icon: Mail },
  { to: "/candidate/grade", label: "Категория и грейд", icon: Award },
  { to: "/candidate/profile", label: "Профиль и резюме", icon: UserRound },
  { to: "/candidate/vacancies", label: "Вакансии", icon: Briefcase },
  { to: "/candidate/applications", label: "Отклики", icon: Send },
  { to: "/candidate/tasks", label: "Задания", icon: ListChecks },
  { to: "/candidate/onboarding", label: "Онбординг", icon: ClipboardList },
  { to: "/candidate/settings", label: "Настройки", icon: Settings },
];

export default function CandidateLayout() {
  return <CabinetLayout homePath="/candidate" roleLabel="Кандидат" nav={nav} />;
}
