import { Flag, Scale } from "lucide-react";
import { CabinetLayout, type CabinetNavItem } from "./CabinetLayout";

const nav: CabinetNavItem[] = [
  { to: "/admin", label: "Жалобы", icon: Flag, end: true },
  { to: "/admin/appeals", label: "Обращения по грейду", icon: Scale },
];

export default function AdminLayout() {
  return <CabinetLayout homePath="/admin" roleLabel="Администратор" nav={nav} />;
}
