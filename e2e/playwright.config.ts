import { defineConfig, devices } from "@playwright/test";

// Демо-сценарий docs/implementation.md §18 против прода (по умолчанию) или любого стенда из E2E_BASE_URL.
const baseURL = process.env.E2E_BASE_URL ?? "https://itscout.ru";
const ci = !!process.env.CI;

export default defineConfig({
  testDir: "./tests",
  // Полный тест кандидата — около 20 заданий; сценарий работодателя — десяток экранов.
  timeout: 8 * 60_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 2,
  retries: ci ? 1 : 0,
  forbidOnly: ci,
  reporter: [["list"]],
  use: {
    baseURL,
    locale: "ru-RU",
    timezoneId: "Europe/Moscow",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    // Без трейсов, видео и HTML-отчёта: в них попадают значения fill() (пароли) и refresh-cookie,
    // а артефакты CI станут публичными вместе с репозиторием. При падении — только скриншот.
    trace: "off",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
