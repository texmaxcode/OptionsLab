"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { DrawdownPoint } from "@/lib/labApi";
import { useChartDimensions } from "@/hooks/useChartDimensions";
import { clearSvgAndCreateRoot } from "@/lib/chartSvg";

const MARGIN = { top: 24, right: 32, bottom: 40, left: 64 };
const DEFAULT_WIDTH = 1040;
const DEFAULT_HEIGHT = 420;

type Props = {
  data: DrawdownPoint[];
  highlightRange?: { from: string; to: string } | null;
  width?: number;
  height?: number;
  className?: string;
};

export function DrawdownChart({
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
        drawdown: d.drawdown,
      }))
      .sort((a, b) => a.date.getTime() - b.date.getTime());

    const xScale = d3
      .scaleTime()
      .domain(d3.extent(parsed, (d) => d.date) as [Date, Date])
      .range([0, innerWidth]);

    const yMax = Math.max(d3.max(parsed, (d) => d.drawdown) ?? 0, 0.1);
    const yScale = d3.scaleLinear().domain([0, yMax]).range([innerHeight, 0]);

    const area = d3
      .area<{ date: Date; drawdown: number }>()
      .x((d) => xScale(d.date))
      .y0(innerHeight)
      .y1((d) => yScale(d.drawdown))
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
        d3.axisLeft(yScale).ticks(6).tickFormat((v) => `${Number(v).toFixed(1)}%`)
      )
      .selectAll("text")
      .attr("font-size", "14px");

    g.insert("path", ":first-child")
      .datum(parsed)
      .attr("fill", "rgb(220 38 38)")
      .attr("fill-opacity", "0.25")
      .attr("d", area);

    g.append("path")
      .datum(parsed)
      .attr("fill", "none")
      .attr("stroke", "rgb(220 38 38)")
      .attr("stroke-width", 2)
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .attr(
        "d",
        d3
          .line<{ date: Date; drawdown: number }>()
          .x((d) => xScale(d.date))
          .y((d) => yScale(d.drawdown))
          .curve(d3.curveMonotoneX)(parsed)
      );

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

    // Crosshair + tooltip for drawdown chart
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
      .attr("fill", "rgb(220 38 38)")
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

    const bisectDate = d3.bisector<{ date: Date; drawdown: number }, Date>((d) => d.date).center;

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
        const cy = yScale(d.drawdown);

        focusLineX.attr("x1", cx).attr("x2", cx);
        focusLineY.attr("y1", cy).attr("y2", cy);
        focusDot.attr("cx", cx).attr("cy", cy);

        const dateFormatter = w < 500 ? d3.timeFormat("%b %Y") : d3.timeFormat("%Y-%m-%d");
        const label = `${dateFormatter(d.date)} · ${d.drawdown.toFixed(1)}%`;
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
      className="w-full min-w-0 overflow-visible min-h-[300px] sm:min-h-[280px] md:min-h-[240px] h-[75vmin] sm:h-[70vmin] md:h-[min(380px,42vw)]"
    >
      <svg
        ref={svgRef}
        className={`block w-full h-full ${className}`}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="Drawdown"
      />
    </div>
  );
}
