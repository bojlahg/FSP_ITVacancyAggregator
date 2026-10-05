import { useSyncExternalStore } from "react";

/** Выбор пользователя: «Авто» — как в системе, иначе явно светлая или тёмная. */
export type ThemeChoice = "system" | "light" | "dark";

// Тот же ключ читает public/theme-init.js до загрузки приложения.
const STORAGE_KEY = "itscout-theme";
const media = window.matchMedia("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();

function read(): ThemeChoice {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "light" || value === "dark") return value;
  } catch {
    // хранилище недоступно (приватный режим) — остаёмся на системной теме
  }
  return "system";
}

let choice = read();

function apply(): void {
  const dark = choice === "dark" || (choice === "system" && media.matches);
  document.documentElement.classList.toggle("dark", dark);
}

function notify(): void {
  for (const listener of listeners) listener();
}

media.addEventListener("change", () => {
  if (choice === "system") apply();
});

// Выбор в другой вкладке применяется и здесь.
window.addEventListener("storage", (event) => {
  if (event.key !== STORAGE_KEY) return;
  choice = read();
  apply();
  notify();
});

export function setTheme(next: ThemeChoice): void {
  choice = next;
  try {
    if (next === "system") localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // не сохранилось — тема всё равно применится до перезагрузки
  }
  apply();
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTheme(): ThemeChoice {
  return useSyncExternalStore(subscribe, () => choice);
}
