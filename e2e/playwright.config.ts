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
  reporter: ci ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL,
    locale: "ru-RU",
    timezoneId: "Europe/Moscow",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
