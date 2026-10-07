import { useEffect } from "react";
import { Outlet, useMatches } from "react-router";

const DEFAULT_TITLE = "ITScout — платформа ИТ-подбора ФСП";

/** handle маршрута в router.tsx. */
export interface RouteHandle {
  /** Название вкладки браузера. */
  title?: string;
  /** Режим фокуса: кабинет прячет меню и навигацию (идёт тест, §6.2). */
  focus?: boolean;
}

/** Корневой элемент маршрутов: «<Страница> — ITScout» по самому глубокому маршруту с title. */
export function TitledOutlet() {
  const matches = useMatches();
  const title = matches
    .map((match) => (match.handle as RouteHandle | undefined)?.title)
    .filter(Boolean)
    .at(-1);

  useEffect(() => {
    document.title = title ? `${title} — ITScout` : DEFAULT_TITLE;
  }, [title]);

  return <Outlet />;
}
