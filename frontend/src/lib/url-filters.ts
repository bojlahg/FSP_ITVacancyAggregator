import { useSearchParams } from "react-router";

export type ParamValue = string | number | boolean | readonly string[] | null | undefined;

/**
 * Фильтры экрана в адресной строке (§8.1 п.4): переживают перезагрузку и пересылку ссылки.
 * false, null и пустая строка удаляют параметр; true пишется как «1»; массив — повторяющийся параметр.
 */
export function useUrlFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  const set = (changes: Record<string, ParamValue>) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (Array.isArray(value)) {
            next.delete(key);
            for (const item of value) next.append(key, item);
          } else if (value === null || value === undefined || value === false || value === "") next.delete(key);
          else next.set(key, value === true ? "1" : String(value));
        }
        return next;
      },
      { replace: true },
    );
  };

  /** Сбросить всё, кроме перечисленных ключей. */
  const reset = (keep: string[] = []) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams();
        for (const key of keep) {
          const value = current.get(key);
          if (value !== null) next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );
  };

  return { params: searchParams, set, reset };
}

/** Положительное целое из параметра или undefined. */
export function intParam(value: string | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

/** Значение параметра, только если оно из допустимого списка. */
export function enumParam<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return allowed.find((item) => item === value);
}
