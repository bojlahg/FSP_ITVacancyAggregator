import {
  Award,
  Briefcase,
  ClipboardList,
  LayoutDashboard,
  ListChecks,
  Trophy,
  Mail,
  Send,
  Settings,
  UserRound,
} from "lucide-react";
import { useCandidateMe } from "@/lib/testing-queries";
import { CabinetLayout, type CabinetNavItem } from "./CabinetLayout";

const CLASSIC = "Классический поиск";
const EXTRA = "Дополнительно";
const ONBOARDING_PATH = "/candidate/onboarding";

// Основное — обратная механика (первым пишет работодатель); отклики на вакансии — отдельным блоком ниже
const nav: CabinetNavItem[] = [
  { to: "/candidate", label: "Главная", icon: LayoutDashboard, end: true },
  { to: "/candidate/invitations", label: "Приглашения", icon: Mail },
  { to: "/candidate/grade", label: "Категория и грейд", icon: Award },
  { to: "/candidate/profile", label: "Профиль и резюме", icon: UserRound },
  { to: ONBOARDING_PATH, label: "Онбординг", icon: ClipboardList },
  { to: "/candidate/vacancies", label: "Вакансии", icon: Briefcase, group: CLASSIC },
  { to: "/candidate/applications", label: "Отклики", icon: Send, group: CLASSIC },
  { to: "/candidate/tasks", label: "Задания", icon: ListChecks, group: EXTRA },
  { to: "/candidate/challenges", label: "Челленджи", icon: Trophy, group: EXTRA },
  { to: "/candidate/settings", label: "Настройки", icon: Settings },
];

export default function CandidateLayout() {
  const me = useCandidateMe();
  // Онбординг в меню, пока нет категории; пока профиль грузится — не показываем, при ошибке — оставляем
  const onboardingDone = me.data ? me.data.onboarding_step === "done" && me.data.category !== null : !me.isError;
  const items = onboardingDone ? nav.filter((item) => item.to !== ONBOARDING_PATH) : nav;
  return <CabinetLayout homePath="/candidate" roleLabel="Кандидат" nav={items} />;
}
