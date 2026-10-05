// Ставит тему до первой отрисовки, чтобы тёмная тема не мигала белым. Отдельный файл, а не inline:
// CSP разрешает только скрипты с нашего домена. Логика выбора — та же, что в src/lib/theme.ts.
(function () {
  var choice = null;
  try {
    choice = localStorage.getItem("itscout-theme");
  } catch (e) {}
  var dark = choice === "dark" || (choice !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
})();
