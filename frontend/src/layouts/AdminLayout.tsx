import { Flag } from "lucide-react";
import { CabinetLayout, type CabinetNavItem } from "./CabinetLayout";

const nav: CabinetNavItem[] = [{ to: "/admin", label: "Жалобы", icon: Flag, end: true }];

export default function AdminLayout() {
  return <CabinetLayout homePath="/admin" roleLabel="Администратор" nav={nav} />;
}
