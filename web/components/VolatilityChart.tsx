"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import { useChartDimensions } from "@/hooks/useChartDimensions";
import { clearSvgAndCreateRoot } from "@/lib/chartSvg";

const MARGIN = { top: 24, right: 80, bottom: 40, left: 60 };
const DEFAULT_HEIGHT = 300;

export interface VolSeriesPoint {
  date: string;
  value: number;
}

export interface VolSeries {
  label: string;
  color: string;
  data: VolSeriesPoint[];
}

type Props = {
  series: VolSeries[];
  className?: string;
  height?: number;
  yLabel?: string;
  formatY?: (v: number) => string;
};

export function VolatilityChart({
  series,
  className = "",
  height = DEFAULT_HEIGHT,
  yLabel = "Volatility",
  formatY = (v) => `${(v * 100).toFixed(1)}%`,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const { wrapperRef, w, h } = useChartDimensions(800, height);

  useEffect(() => {
    if (!svgRef.current) return;
    const allPoints = series.flatMap((s) =>
      s.data.map((d) => ({ date: new Date(d.date), value: d.value, label: s.label })),
    );
    if (!allPoints.length) return;

    const svg = d3.select(svgRef.current);
    const { root, innerWidth, innerHeight } = clearSvgAndCreateRoot(svg, w, h, MARGIN);

    const allDates = allPoints.map((d) => d.date);
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(allDates) as [Date, Date])
      .range([0, innerWidth]);

    const allValues = allPoints.map((d) => d.value);
    const [vMin, vMax] = d3.extent(allValues) as [number, number];
    const pad = (vMax - vMin) * 0.15 || 0.01;
    const yScale = d3
      .scaleLinear()
      .domain([Math.max(0, vMin - pad), vMax + pad])
      .nice()
      .range([innerHeight, 0]);

    // Axes
    root
      .append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .attr("class", "chart-axis")
      .call(
        d3
          .axisBottom(xScale)
          .ticks(w < 500 ? 4 : 6)
          .tickFormat(d3.timeFormat("%b %y") as (v: Date | d3.NumberValue) => string)
          .tickSizeOuter(0),
      )
      .selectAll("text")
      .attr("font-size", "11px");

    root
      .append("g")
      .attr("class", "chart-axis")
      .call(d3.axisLeft(yScale).ticks(5).tickFormat(formatY as (v: d3.NumberValue) => string))
      .selectAll("text")
      .attr("font-size", "11px");

    if (yLabel) {
      root
        .append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -innerHeight / 2)
        .attr("y", -MARGIN.left + 14)
        .attr("text-anchor", "middle")
        .attr("fill", "currentColor")
        .attr("font-size", "11px")
        .text(yLabel);
    }

    // Lines per series
    const line = d3
      .line<VolSeriesPoint>()
      .x((d) => xScale(new Date(d.date)))
      .y((d) => yScale(d.value))
      .curve(d3.curveMonotoneX)
      .defined((d) => d.value != null && !isNaN(d.value));

    series.forEach((s) => {
      if (!s.data.length) return;
      root
        .append("path")
        .datum(s.data)
        .attr("fill", "none")
        .attr("stroke", s.color)
        .attr("stroke-width", 2)
        .attr("d", line);
    });

    // Legend
    const legend = root.append("g").attr("transform", `translate(${innerWidth + 8}, 0)`);
    series.forEach((s, i) => {
      const row = legend.append("g").attr("transform", `translate(0, ${i * 18})`);
      row.append("line").attr("x1", 0).attr("x2", 14).attr("stroke", s.color).attr("stroke-width", 2);
      row
        .append("text")
        .attr("x", 18)
        .attr("dy", "0.35em")
        .attr("fill", "currentColor")
        .attr("font-size", "11px")
        .text(s.label);
    });

    // Crosshair overlay
    const focus = root.append("g").style("display", "none");
    const focusLine = focus
      .append("line")
      .attr("stroke", "rgba(148,163,184,0.6)")
      .attr("stroke-dasharray", "4 4")
      .attr("y1", 0)
      .attr("y2", innerHeight);

    const tooltip = root.append("g").style("display", "none").attr("pointer-events", "none");
    const tooltipBg = tooltip
      .append("rect")
      .attr("fill", "rgba(15,23,42,0.92)")
      .attr("stroke", "rgba(148,163,184,0.8)")
      .attr("rx", 4);
    const tooltipLines: d3.Selection<SVGTextElement, unknown, null, undefined>[] = [];
    series.forEach((s, i) => {
      tooltipLines.push(
        tooltip
          .append("text")
          .attr("fill", s.color)
          .attr("font-size", 11)
          .attr("x", 8)
          .attr("y", 14 + i * 14),
      );
    });
    const tooltipDate = tooltip
      .append("text")
      .attr("fill", "rgba(148,163,184,0.9)")
      .attr("font-size", 10)
      .attr("x", 8)
      .attr("y", 14 + series.length * 14);

    // Find closest point per series at x
    const parsedSeries = series.map((s) =>
      s.data
        .filter((d) => d.value != null)
        .map((d) => ({ date: new Date(d.date), value: d.value }))
        .sort((a, b) => a.date.getTime() - b.date.getTime()),
    );
    const bisect = d3.bisector<{ date: Date; value: number }, Date>((d) => d.date).center;

    root
      .append("rect")
      .attr("fill", "transparent")
      .attr("pointer-events", "all")
      .attr("width", innerWidth)
      .attr("height", innerHeight)
      .on("mouseenter", () => {
        focus.style("display", null);
        tooltip.style("display", null);
      })
      .on("mouseleave", () => {
        focus.style("display", "none");
        tooltip.style("display", "none");
      })
      .on("mousemove", (event) => {
        const [mx] = d3.pointer(event);
        const x0 = xScale.invert(mx);
        focusLine.attr("x1", mx).attr("x2", mx);

        let maxWidth = 0;
        parsedSeries.forEach((pts, i) => {
          if (!pts.length) return;
          const idx = Math.max(0, Math.min(pts.length - 1, bisect(pts, x0)));
          const pt = pts[idx];
          const label = `${series[i].label}: ${formatY(pt.value)}`;
          tooltipLines[i].text(label);
          const bbox = (tooltipLines[i].node() as SVGGraphicsElement | null)?.getBBox();
          if (bbox && bbox.width > maxWidth) maxWidth = bbox.width;
          tooltipDate.text(d3.timeFormat("%Y-%m-%d")(pt.date));
        });
        const totalHeight = 14 + series.length * 14 + 14;
        tooltipBg.attr("width", maxWidth + 16).attr("height", totalHeight);

        let tx = mx + 10;
        if (tx + maxWidth + 20 > innerWidth) tx = mx - maxWidth - 26;
        tooltip.attr("transform", `translate(${tx}, 4)`);
      });
  }, [series, w, h, yLabel, formatY]);

  return (
    <div ref={wrapperRef} className={className} style={{ height }}>
      <svg
        ref={svgRef}
        role="img"
        aria-label="Volatility chart"
        width="100%"
        height="100%"
        style={{ display: "block" }}
      />
    </div>
  );
}
