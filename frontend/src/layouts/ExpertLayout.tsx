import { ClipboardCheck } from "lucide-react";
import { CabinetLayout, type CabinetNavItem } from "./CabinetLayout";

const nav: CabinetNavItem[] = [{ to: "/expert", label: "Разметка и итоги", icon: ClipboardCheck, end: true }];

export default function ExpertLayout() {
  return <CabinetLayout homePath="/expert" roleLabel="Эксперт" nav={nav} />;
}
