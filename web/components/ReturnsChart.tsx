"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { TimeReturnPoint } from "@/lib/labApi";
import { useChartDimensions } from "@/hooks/useChartDimensions";
import { clearSvgAndCreateRoot } from "@/lib/chartSvg";

const MARGIN = { top: 24, right: 24, bottom: 40, left: 56 };
const DEFAULT_WIDTH = 1040;
const DEFAULT_HEIGHT = 380;

type Props = {
  data: TimeReturnPoint[];
  /** X-axis date range so Period returns aligns with other backtest charts. */
  dateDomain?: { from: string; to: string };
  highlightRange?: { from: string; to: string } | null;
  /** When set, the bar for this date is shown with a slightly lighter shade (works with or without trade selection). */
  selectedDate?: string | null;
  /** Called when a bar is clicked with that point's date (YYYY-MM-DD). Pass null to clear. */
  onSelectPoint?: (date: string | null) => void;
  width?: number;
  height?: number;
  className?: string;
};

export function ReturnsChart({
  data,
  dateDomain,
  highlightRange = null,
  selectedDate = null,
  onSelectPoint,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  className = "",
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const { wrapperRef, w, h } = useChartDimensions(width, height);

  useEffect(() => {
    if (!data.length || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    const { root, innerWidth, innerHeight } = clearSvgAndCreateRoot(svg, w, h, MARGIN);
    const g = root.append("g");

    interface ParsedPoint {
      date: Date;
      period_return: number;
      dateStr: string;
    }
    const parsed: ParsedPoint[] = data.map((d, i) => ({
      date: new Date(d.date),
      period_return: d.period_return * 100,
      dateStr: data[i]!.date,
    }));

    const xScale = d3
      .scaleTime()
      .domain(
        dateDomain
          ? [new Date(dateDomain.from), new Date(dateDomain.to)]
          : (d3.extent(parsed, (d) => d.date) as [Date, Date])
      )
      .range([0, innerWidth]);

    const ext = d3.extent(parsed, (d) => d.period_return) as [number, number];
    const absMax = Math.max(Math.abs(ext[0] ?? 0), Math.abs(ext[1] ?? 0), 0.5);
    const yScale = d3
      .scaleLinear()
      .domain([-absMax, absMax])
      .range([innerHeight, 0]);

    const zeroY = yScale(0);

    g.append("line")
      .attr("x1", 0)
      .attr("x2", innerWidth)
      .attr("y1", zeroY)
      .attr("y2", zeroY)
      .attr("stroke", "currentColor")
      .attr("stroke-opacity", "0.2")
      .attr("stroke-dasharray", "4,4");

    const xAxisTickFormat = w < 500 ? (d: Date) => d3.timeFormat("%b")(d) : undefined;
    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .attr("class", "text-zinc-500 dark:text-zinc-400 chart-axis")
      .call(
        d3.axisBottom(xScale)
          .ticks(w < 500 ? 5 : 6)
          .tickFormat(xAxisTickFormat as (value: Date | d3.NumberValue) => string)
          .tickSizeOuter(0)
      )
      .selectAll("text")
      .attr("font-size", "14px");

    g.append("g")
      .attr("class", "text-zinc-500 dark:text-zinc-400 chart-axis")
      .call(
        d3.axisLeft(yScale).ticks(6).tickFormat((v) => `${Number(v).toFixed(2)}%`)
      )
      .selectAll("text")
      .attr("font-size", "14px");

    const barWidth = (innerWidth / parsed.length) * 0.20;
    const barXOffset = barWidth * 0.5;

    const isSingleBar = highlightRange?.from === highlightRange?.to;
    const isInHighlightRange = (d: ParsedPoint) => {
      if (!highlightRange?.from || !highlightRange?.to) return false;
      return d.dateStr >= highlightRange.from && d.dateStr <= highlightRange.to;
    };
    const isSelectedReturn = (d: ParsedPoint) => selectedDate != null && d.dateStr === selectedDate;

    g.selectAll("rect")
      .data(parsed)
      .join("rect")
      .attr("x", (d) => xScale(d.date) - barXOffset)
      .attr("width", barWidth)
      .attr("y", (d) => (d.period_return >= 0 ? yScale(d.period_return) : zeroY))
      .attr("height", (d) => Math.abs(yScale(d.period_return) - zeroY))
      .attr("fill", (d) => {
        if (isSelectedReturn(d)) {
          return d.period_return >= 0 ? "rgb(34 197 94)" : "rgb(239 68 68)";
        }
        return d.period_return >= 0 ? "rgb(5 150 105)" : "rgb(220 38 38)";
      })
      .attr("fill-opacity", (d) => {
        if (isSingleBar) return 1;
        return highlightRange && isInHighlightRange(d) ? 1 : highlightRange ? 0.35 : 1;
      })
      .attr("stroke", (d) => {
        if (isSelectedReturn(d)) return d.period_return >= 0 ? "rgb(22 163 74)" : "rgb(185 28 28)";
        return d.period_return >= 0 ? "rgb(4 120 87)" : "rgb(185 28 28)";
      })
      .attr("stroke-width", (d) => (isSelectedReturn(d) ? 2 : 1))
      .attr("stroke-opacity", (d) => (highlightRange && isInHighlightRange(d) ? 1 : highlightRange ? 0.4 : 0.6))
      .attr("cursor", "pointer")
      .style("pointer-events", "all")
      .on("click", function (_event, d) {
        if (onSelectPoint) {
          const isSelected = selectedDate === d.dateStr;
          onSelectPoint(isSelected ? null : d.dateStr);
        }
      })
      .on("mouseenter", function (event, d) {
        const wrapper = wrapperRef.current;
        const tooltip = tooltipRef.current;
        if (!wrapper || !tooltip) return;
        const [x, y] = d3.pointer(event, wrapper);
        tooltip.style.left = `${Math.min(x + 10, wrapper.getBoundingClientRect().width - 140)}px`;
        tooltip.style.top = `${y - 8}px`;
        tooltip.innerHTML = `
          <div class="font-medium">${d3.timeFormat("%d/%m/%y")(d.date)}</div>
          <div class="mt-0.5 font-mono text-sm">Return: ${d.period_return >= 0 ? "+" : ""}${d.period_return.toFixed(2)}%</div>
        `;
        tooltip.classList.remove("hidden");
      })
      .on("mousemove", function (event) {
        const wrapper = wrapperRef.current;
        const tooltip = tooltipRef.current;
        if (!wrapper || !tooltip) return;
        const [x] = d3.pointer(event, wrapper);
        tooltip.style.left = `${Math.min(x + 10, wrapper.getBoundingClientRect().width - 140)}px`;
      })
      .on("mouseleave", () => {
        tooltipRef.current?.classList.add("hidden");
      });

    if (highlightRange?.from != null && highlightRange?.to != null && !isSingleBar) {
      const fromX = xScale(new Date(highlightRange.from));
      const toX = xScale(new Date(highlightRange.to));
      const overlay = root.append("g").attr("class", "chart-highlight-overlay").attr("pointer-events", "none");
      if (fromX > 0) {
        overlay.append("rect").attr("x", 0).attr("y", 0).attr("width", fromX).attr("height", innerHeight).attr("fill", "currentColor").attr("fill-opacity", 0.45);
      }
      if (toX < innerWidth) {
        overlay.append("rect").attr("x", toX).attr("y", 0).attr("width", innerWidth - toX).attr("height", innerHeight).attr("fill", "currentColor").attr("fill-opacity", 0.45);
      }
    }
  }, [data, dateDomain, w, h, highlightRange, selectedDate, onSelectPoint, wrapperRef]);

  if (data.length === 0) return null;

  return (
    <div
      ref={wrapperRef}
      className="relative w-full min-w-0 overflow-visible min-h-[280px] sm:min-h-[260px] md:min-h-[220px] h-[70vmin] sm:h-[65vmin] md:h-[min(360px,40vw)]"
    >
      <svg
        ref={svgRef}
        className={`block w-full h-full ${className}`}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="Period returns"
      />
      <div
        ref={tooltipRef}
        className="pointer-events-none absolute z-10 hidden rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 shadow-xl"
      />
    </div>
  );
}
