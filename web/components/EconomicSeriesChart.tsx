"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { EconomicSeriesPoint } from "@/lib/economicApi";
import { useChartDimensions } from "@/hooks/useChartDimensions";
import { clearSvgAndCreateRoot } from "@/lib/chartSvg";

const MARGIN = { top: 24, right: 32, bottom: 40, left: 72 };
const DEFAULT_WIDTH = 1040;
const DEFAULT_HEIGHT = 360;

type Props = {
  data: EconomicSeriesPoint[];
  width?: number;
  height?: number;
  className?: string;
  yLabel?: string;
  compactDates?: boolean;
};

export function EconomicSeriesChart({
  data,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  className = "",
  yLabel,
  compactDates = false,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const { wrapperRef, w, h } = useChartDimensions(width, height);

  useEffect(() => {
    if (!data.length || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    const { root, innerWidth, innerHeight } = clearSvgAndCreateRoot(svg, w, h, MARGIN);
    const g = root.append("g");

    const parsed = data
      .filter((d) => d.value != null)
      .map((d) => ({
        date: new Date(d.date),
        value: d.value as number,
      }))
      .sort((a, b) => a.date.getTime() - b.date.getTime());

    if (!parsed.length) {
      return;
    }

    const xScale = d3
      .scaleTime()
      .domain(d3.extent(parsed, (d) => d.date) as [Date, Date])
      .range([0, innerWidth]);

    const yExtent = d3.extent(parsed, (d) => d.value) as [number, number];
    const yPadding = (yExtent[1] - yExtent[0]) * 0.2 || 1;
    const yScale = d3
      .scaleLinear()
      .domain([yExtent[0] - yPadding, yExtent[1] + yPadding])
      .nice()
      .range([innerHeight, 0]);

    const xAxisTickFormat = compactDates
      ? d3.timeFormat("%b %y") // e.g. Jan 25
      : w < 500
      ? d3.timeFormat("%Y")
      : d3.timeFormat("%Y-%m");

    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .attr("class", "text-zinc-500 dark:text-zinc-400 chart-axis")
      .call(
        d3
          .axisBottom(xScale)
          .ticks(compactDates ? 6 : w < 500 ? 5 : 8)
          .tickFormat(xAxisTickFormat as (value: Date | d3.NumberValue) => string)
          .tickSizeOuter(0),
      )
      .selectAll("text")
      .attr("font-size", "12px");

    const yAxis = d3.axisLeft(yScale).ticks(6);
    g.append("g")
      .attr("class", "text-zinc-500 dark:text-zinc-400 chart-axis")
      .call(yAxis)
      .selectAll("text")
      .attr("font-size", "12px");

    if (yLabel) {
      g.append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -innerHeight / 2)
        .attr("y", -MARGIN.left + 16)
        .attr("text-anchor", "middle")
        .attr("fill", "currentColor")
        .attr("class", "text-xs text-zinc-500 dark:text-zinc-400")
        .text(yLabel);
    }

    const line = d3
      .line<{ date: Date; value: number }>()
      .x((d) => xScale(d.date))
      .y((d) => yScale(d.value))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(parsed)
      .attr("fill", "none")
      .attr("stroke", "rgb(34 197 94)")
      .attr("stroke-width", 2)
      .attr("d", line);

    // Crosshair + tooltip
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
      .attr("fill", "rgb(34 197 94)")
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

        const dateFormatter = compactDates ? d3.timeFormat("%b %Y") : d3.timeFormat("%Y-%m-%d");
        const label = `${dateFormatter(d.date)} · ${d.value.toFixed(3)}`;
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
  }, [data, w, h, yLabel, compactDates]);

  return (
    <div
      ref={wrapperRef}
      className={className}
      style={{ height }}
    >
      <svg
        ref={svgRef}
        role="img"
        aria-label="Economic time-series chart"
        width="100%"
        height="100%"
        style={{ display: "block" }}
      />
    </div>
  );
}

