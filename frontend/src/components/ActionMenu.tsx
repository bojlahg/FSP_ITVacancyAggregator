import type { LucideIcon } from "lucide-react";
import { Loader2, MoreHorizontal } from "lucide-react";
import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ActionMenuItem {
  label: string;
  icon?: LucideIcon;
  /** Ссылка внутри приложения — или onSelect для действия. */
  to?: string;
  onSelect?: () => void;
  disabled?: boolean;
  pending?: boolean;
}

interface ActionMenuProps {
  /** Доступное имя кнопки: что спрятано в меню. */
  label: string;
  items: ActionMenuItem[];
  className?: string;
}

const itemClass =
  "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-popover-foreground outline-none hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:text-accent-foreground aria-disabled:pointer-events-none aria-disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0";

/**
 * Меню «…» для второстепенных действий экрана: настоящая кнопка, стрелки и Escape с клавиатуры,
 * закрывается кликом мимо. Без зависимостей — пунктов немного, позиционирование простое.
 */
export function ActionMenu({ label, items, className }: ActionMenuProps) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const menuItems = () => [...(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])];

  useEffect(() => {
    if (!open) return;
    menuItems()[0]?.focus();
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open]);

  const close = (focusTrigger: boolean) => {
    setOpen(false);
    if (focusTrigger) triggerRef.current?.focus();
  };

  const onMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const list = menuItems();
    const index = list.indexOf(document.activeElement as HTMLElement);
    if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      list[(index + step + list.length) % list.length]?.focus();
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      list[event.key === "Home" ? 0 : list.length - 1]?.focus();
    } else if (event.key === "Tab") {
      setOpen(false);
    }
  };

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        title={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
          }
        }}
        className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "border border-border")}
      >
        <MoreHorizontal aria-hidden />
      </button>
      {open && (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label={label}
          onKeyDown={onMenuKeyDown}
          className="absolute top-full right-0 z-40 mt-1 grid w-max max-w-[calc(100vw-2rem)] min-w-56 gap-0.5 rounded-lg border bg-popover p-1 shadow-lg"
        >
          {items.map((item) => {
            const Icon = item.pending ? Loader2 : item.icon;
            const content = (
              <>
                {Icon && <Icon className={cn(item.pending && "animate-spin")} aria-hidden />}
                {item.label}
              </>
            );
            return item.to && !item.disabled ? (
              <Link key={item.label} to={item.to} role="menuitem" tabIndex={-1} className={itemClass} onClick={() => setOpen(false)}>
                {content}
              </Link>
            ) : (
              <button
                key={item.label}
                type="button"
                role="menuitem"
                tabIndex={-1}
                aria-disabled={item.disabled || item.pending || undefined}
                className={itemClass}
                onClick={() => {
                  if (item.disabled || item.pending) return;
                  item.onSelect?.();
                  close(true);
                }}
              >
                {content}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
