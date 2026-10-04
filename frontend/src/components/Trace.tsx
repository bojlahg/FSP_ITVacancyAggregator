import { cn } from "@/lib/utils";

interface TraceProps {
  /** Ширина и высота SVG в px (без растяжения — скругление и точка не искажаются). */
  width?: number;
  height?: number;
  /** Радиус скругления угла. */
  radius?: number;
  /** Отразить по горизонтали: линия входит слева и уходит вниз справа. */
  flip?: boolean;
  /** Точка и в начале линии. */
  startDot?: boolean;
  className?: string;
}

const DOT_R = 4;
const PAD = DOT_R + 1;

/**
 * Фирменная «трасса» брендбука ФСП: тонкая синяя линия со скруглённым углом, заканчивающаяся точкой.
 * Декоративный элемент — скрыт от скринридеров.
 */
export function Trace({ width = 240, height = 320, radius = 40, flip = false, startDot = false, className }: TraceProps) {
  const top = PAD;
  const x = PAD;
  const path = `M ${width} ${top} H ${x + radius} Q ${x} ${top} ${x} ${top + radius} V ${height - PAD}`;

  return (
    <svg
      aria-hidden
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("pointer-events-none shrink-0", flip && "-scale-x-100", className)}
    >
      <path d={path} className="fill-none stroke-primary" strokeWidth={1.5} strokeLinecap="round" />
      <circle cx={x} cy={height - PAD} r={DOT_R} className="fill-primary" />
      {startDot && <circle cx={width - PAD} cy={top} r={DOT_R} className="fill-primary" />}
    </svg>
  );
}
