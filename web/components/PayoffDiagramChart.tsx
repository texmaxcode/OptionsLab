"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { PayoffPoint } from "@/lib/researchApi";
import { useChartDimensions } from "@/hooks/useChartDimensions";
import { clearSvgAndCreateRoot } from "@/lib/chartSvg";

const MARGIN = { top: 24, right: 24, bottom: 40, left: 56 };
const DEFAULT_WIDTH = 640;
const DEFAULT_HEIGHT = 320;

type Props = {
  data: PayoffPoint[];
  width?: number;
  height?: number;
  className?: string;
};

export function PayoffDiagramChart({
  data,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  className = "",
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const { wrapperRef, w, h } = useChartDimensions(width, height);

  useEffect(() => {
    if (!data.length || !svgRef.current) return;
    const { root, innerWidth, innerHeight } = clearSvgAndCreateRoot(
      d3.select(svgRef.current),
      w,
      h,
      MARGIN
    );
    const g = root.append("g");

    const xMin = d3.min(data, (d) => d.underlying) ?? 0;
    const xMax = d3.max(data, (d) => d.underlying) ?? 1;
    const xPadding = (xMax - xMin) * 0.05 || 0.01;
    const xScale = d3
      .scaleLinear()
      .domain([xMin - xPadding, xMax + xPadding])
      .range([0, innerWidth]);

    const yMin = d3.min(data, (d) => d.payoff) ?? 0;
    const yMax = d3.max(data, (d) => d.payoff) ?? 1;
    const yExtent = Math.max(yMax - yMin, 0.1);
    const yCenter = (yMin + yMax) / 2;
    const yScale = d3
      .scaleLinear()
      .domain([yCenter - yExtent / 2 - 0.1, yCenter + yExtent / 2 + 0.1])
      .range([innerHeight, 0]);

    // curveLinear: payoff-at-expiry is piecewise linear; monotone curves would round kinks.
    const line = d3
      .line<PayoffPoint>()
      .x((d) => xScale(d.underlying))
      .y((d) => yScale(d.payoff))
      .curve(d3.curveLinear);

    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .attr("class", "text-zinc-500 dark:text-zinc-400 chart-axis")
      .call(
        d3.axisBottom(xScale).ticks(6).tickSizeOuter(0)
      )
      .selectAll("text")
      .attr("font-size", "12px");

    g.append("g")
      .attr("class", "text-zinc-500 dark:text-zinc-400 chart-axis")
      .call(
        d3.axisLeft(yScale).ticks(6).tickFormat((v) => `$${Number(v).toFixed(2)}`)
      )
      .selectAll("text")
      .attr("font-size", "12px");

    const zeroY = yScale(0);
    if (zeroY >= 0 && zeroY <= innerHeight) {
      g.append("line")
        .attr("x1", 0)
        .attr("x2", innerWidth)
        .attr("y1", zeroY)
        .attr("y2", zeroY)
        .attr("stroke", "currentColor")
        .attr("stroke-opacity", 0.3)
        .attr("stroke-dasharray", "4 2");
    }

    g.append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", "rgb(5 150 105)")
      .attr("stroke-width", 2)
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .attr("d", line);
  }, [data, w, h]);

  if (data.length === 0) return null;

  return (
    <div
      ref={wrapperRef}
      className="w-full min-w-0 overflow-visible min-h-[280px] h-[min(320px,60vmin)]"
    >
      <svg
        ref={svgRef}
        className={`block w-full h-full ${className}`}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="Payoff diagram"
      />
    </div>
  );
}
