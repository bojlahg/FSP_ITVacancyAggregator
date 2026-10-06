export const INVALID_FORM_MESSAGE = "Не сохранено: проверьте поля, отмеченные красным";

/**
 * Кнопка сохранения внизу длинной формы, а ошибка может быть у поля выше экрана: прокручиваем к первому
 * неверному полю (по aria-invalid — так находятся и поля-контроллеры без ref).
 */
export function revealFirstInvalid(event?: { target: EventTarget | null }) {
  const form = event?.target instanceof HTMLFormElement ? event.target : null;
  requestAnimationFrame(() => {
    const field = form?.querySelector<HTMLElement>('[aria-invalid="true"]');
    if (!field) return;
    field.scrollIntoView({ block: "center", behavior: "smooth" });
    field.focus({ preventScroll: true });
  });
}
