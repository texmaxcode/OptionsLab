"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Hook for responsive chart dimensions. Observes the wrapper element and
 * returns ref and width/height for SVG charts.
 */
export function useChartDimensions(
  defaultWidth: number,
  defaultHeight: number
): {
  wrapperRef: React.RefObject<HTMLDivElement | null>;
  w: number;
  h: number;
} {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [dimensions, setDimensions] = useState<{
    width: number;
    height: number;
  } | null>(null);

  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const update = () => {
      const { width: w, height: h } = el.getBoundingClientRect();
      if (w > 0 && h > 0)
        setDimensions({ width: Math.round(w), height: Math.round(h) });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return {
    wrapperRef,
    w: dimensions?.width ?? defaultWidth,
    h: dimensions?.height ?? defaultHeight,
  };
}
