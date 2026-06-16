"use client";

/**
 * Minimal inline trend line. Deliberately hand-rolled SVG instead of recharts
 * — these render a few-at-a-time inside LinkCards, where a full chart's
 * mount cost (and axes/tooltip we'd just hide) isn't worth it.
 */
export function Sparkline({
  values,
  viewWidth = 100,
  viewHeight = 28,
  className,
}: {
  values: number[];
  /** Internal coordinate space — actual rendered size comes from `className`. */
  viewWidth?: number;
  viewHeight?: number;
  className?: string;
}) {
  if (values.length < 2) {
    return <svg viewBox={`0 0 ${viewWidth} ${viewHeight}`} className={className} aria-hidden />;
  }

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const stepX = viewWidth / (values.length - 1);

  const points = values
    .map((v, i) => {
      const x = i * stepX;
      const y = viewHeight - ((v - min) / range) * viewHeight;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${viewWidth} ${viewHeight}`} preserveAspectRatio="none" className={className} aria-hidden>
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
