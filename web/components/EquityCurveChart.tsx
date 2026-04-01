"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { EquityCurvePoint } from "@/lib/labApi";
import { useChartDimensions } from "@/hooks/useChartDimensions";
import { clearSvgAndCreateRoot, type ChartHighlightRange } from "@/lib/chartSvg";

const MARGIN = { top: 24, right: 32, bottom: 40, left: 72 };
const DEFAULT_WIDTH = 1040;
const DEFAULT_HEIGHT = 460;

export type { ChartHighlightRange };

type Props = {
  data: EquityCurvePoint[];
  highlightRange?: ChartHighlightRange | null;
  width?: number;
  height?: number;
  className?: string;
};

export function EquityCurveChart({
  data,
  highlightRange = null,
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

    const parsed = data
      .map((d) => ({
        date: new Date(d.date),
        value: d.value,
      }))
      .sort((a, b) => a.date.getTime() - b.date.getTime());

    const xScale = d3
      .scaleTime()
      .domain(d3.extent(parsed, (d) => d.date) as [Date, Date])
      .range([0, innerWidth]);

    const yMin = d3.min(parsed, (d) => d.value) ?? 0;
    const yMax = d3.max(parsed, (d) => d.value) ?? 1;
    const yPadding = (yMax - yMin) * 0.05 || 1;
    const yScale = d3
      .scaleLinear()
      .domain([yMin - yPadding, yMax + yPadding])
      .range([innerHeight, 0]);

    const line = d3
      .line<{ date: Date; value: number }>()
      .x((d) => xScale(d.date))
      .y((d) => yScale(d.value))
      .curve(d3.curveMonotoneX);

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
        d3.axisLeft(yScale).ticks(6).tickFormat((v) => `$${Number(v).toLocaleString()}`)
      )
      .selectAll("text")
      .attr("font-size", "14px");

    g.append("path")
      .datum(parsed)
      .attr("fill", "none")
      .attr("stroke", "rgb(5 150 105)")
      .attr("stroke-width", 2)
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .attr("d", line);

    const area = d3
      .area<{ date: Date; value: number }>()
      .x((d) => xScale(d.date))
      .y0(innerHeight)
      .y1((d) => yScale(d.value))
      .curve(d3.curveMonotoneX);

    g.insert("path", ":first-child")
      .datum(parsed)
      .attr("fill", "rgb(5 150 105)")
      .attr("fill-opacity", "0.12")
      .attr("d", area);

    if (highlightRange?.from != null && highlightRange?.to != null) {
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

    // Crosshair + tooltip for equity curve
    const focusGroup = g.append("g").style("display", "none");

    const focusLineX = focusGroup
      .append("line")
      .attr("stroke", "rgba(148, 163, 184, 0.8)")
      .attr("stroke-dasharray", "4 4")
      .attr("y1", 0)
      .attr("y2", innerHeight);

    const focusLineY = focusGroup
      .append("line")
      .attr("stroke", "rgba(148, 163, 184, 0.8)")
      .attr("stroke-dasharray", "4 4")
      .attr("x1", 0)
      .attr("x2", innerWidth);

    const focusDot = focusGroup
      .append("circle")
      .attr("r", 4)
      .attr("fill", "rgb(5 150 105)")
      .attr("stroke", "white")
      .attr("stroke-width", 1.5);

    const tooltip = g
      .append("g")
      .style("display", "none")
      .attr("pointer-events", "none");

    const tooltipBg = tooltip
      .append("rect")
      .attr("fill", "rgba(15, 23, 42, 0.9)")
      .attr("stroke", "rgba(148, 163, 184, 0.9)")
      .attr("rx", 4)
      .attr("ry", 4);

    const tooltipText = tooltip
      .append("text")
      .attr("fill", "white")
      .attr("font-size", 11)
      .attr("x", 8)
      .attr("y", 14);

    const bisectDate = d3.bisector<{ date: Date; value: number }, Date>((d) => d.date).center;

    g.append("rect")
      .attr("fill", "transparent")
      .attr("pointer-events", "all")
      .attr("width", innerWidth)
      .attr("height", innerHeight)
      .on("mouseenter", () => {
        focusGroup.style("display", null);
        tooltip.style("display", null);
      })
      .on("mouseleave", () => {
        focusGroup.style("display", "none");
        tooltip.style("display", "none");
      })
      .on("mousemove", (event) => {
        const [mx] = d3.pointer(event);
        const x0 = xScale.invert(mx);
        const idx = bisectDate(parsed, x0);
        const d = parsed[Math.max(0, Math.min(parsed.length - 1, idx))];
        const cx = xScale(d.date);
        const cy = yScale(d.value);

        focusLineX.attr("x1", cx).attr("x2", cx);
        focusLineY.attr("y1", cy).attr("y2", cy);
        focusDot.attr("cx", cx).attr("cy", cy);

        const dateFormatter = w < 500 ? d3.timeFormat("%b %Y") : d3.timeFormat("%Y-%m-%d");
        const label = `${dateFormatter(d.date)} · $${d.value.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}`;
        tooltipText.text(label);
        const bbox = (tooltipText.node() as SVGGraphicsElement).getBBox();
        tooltipBg
          .attr("width", bbox.width + 16)
          .attr("height", bbox.height + 10);

        let tx = cx + 10;
        let ty = cy - bbox.height - 16;
        if (tx + bbox.width + 20 > innerWidth) {
          tx = cx - bbox.width - 26;
        }
        if (ty < 0) {
          ty = cy + 16;
        }
        tooltip.attr("transform", `translate(${tx},${ty})`);
      });
  }, [data, w, h, highlightRange]);

  if (data.length === 0) return null;

  return (
    <div
      ref={wrapperRef}
      className="w-full min-w-0 overflow-visible min-h-[340px] sm:min-h-[300px] md:min-h-[260px] h-[80vmin] sm:h-[75vmin] md:h-[min(400px,45vw)]"
    >
      <svg
        ref={svgRef}
        className={`block w-full h-full ${className}`}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="Equity curve"
      />
    </div>
  );
}
