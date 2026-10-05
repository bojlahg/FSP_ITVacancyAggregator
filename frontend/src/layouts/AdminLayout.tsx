import { Bug } from "lucide-react";
import { CabinetLayout, type CabinetNavItem } from "./CabinetLayout";

const nav: CabinetNavItem[] = [{ to: "/admin", label: "Отладка", icon: Bug, end: true }];

export default function AdminLayout() {
  return <CabinetLayout homePath="/admin" roleLabel="Администратор" nav={nav} debugLink={false} />;
}
