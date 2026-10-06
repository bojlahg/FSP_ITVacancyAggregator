import { useEffect, useRef, useState } from "react";

/**
 * Считает уходы со вкладки (visibilitychange → hidden и blur окна). Одно переключение вкладки
 * вызывает оба события — считаем его один раз, пока пользователь не вернётся.
 */
export function useFocusLossCounter() {
  const [count, setCount] = useState(0);
  const awayRef = useRef(false);

  useEffect(() => {
    const leave = () => {
      if (awayRef.current) return;
      awayRef.current = true;
      setCount((current) => current + 1);
    };
    const back = () => {
      awayRef.current = false;
    };
    const onVisibility = () => (document.visibilityState === "hidden" ? leave() : back());
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", leave);
    window.addEventListener("focus", back);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", leave);
      window.removeEventListener("focus", back);
    };
  }, []);

  return { count, reset: () => setCount(0) };
}
