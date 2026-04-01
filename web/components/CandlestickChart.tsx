"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import { useChartDimensions } from "@/hooks/useChartDimensions";

export interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const MARGIN = { top: 20, right: 24, bottom: 44, left: 64 };
const VOLUME_HEIGHT_RATIO = 0.16;
const BAR_PADDING = 0.3;
const DEFAULT_WIDTH = 1040;
const DEFAULT_HEIGHT = 520;

const UP_COLOR = "rgb(5 150 105)";
const DOWN_COLOR = "rgb(220 38 38)";

type Props = {
  data: OHLCVBar[];
  highlightedIndices?: number[];
  width?: number;
  height?: number;
  className?: string;
};

export function CandlestickChart({
  data,
  highlightedIndices = [],
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  className = "",
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const { wrapperRef, w, h } = useChartDimensions(width, height);

  const showTooltip = useCallback((index: number, event: React.MouseEvent | MouseEvent) => {
    const d = data[index];
    if (!d || !tooltipRef.current || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const x = "clientX" in event ? event.clientX - rect.left : 0;
    const y = "clientY" in event ? event.clientY - rect.top : 0;
    const fmt = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const dateStr = new Date(d.date).toLocaleDateString(undefined, {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
    tooltipRef.current.innerHTML = `
      <div class="font-semibold">${dateStr}</div>
      <div class="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs">
        <span>Open</span><span class="font-mono">${fmt(d.open)}</span>
        <span>High</span><span class="font-mono">${fmt(d.high)}</span>
        <span>Low</span><span class="font-mono">${fmt(d.low)}</span>
        <span>Close</span><span class="font-mono">${fmt(d.close)}</span>
        <span>Volume</span><span class="font-mono">${d.volume.toLocaleString()}</span>
      </div>
    `;
    const tooltipW = 180;
    const tooltipH = 100;
    let left = x + 12;
    let top = y - 8;
    if (y > rect.height * 0.5) {
      top = Math.max(y - tooltipH - 8, 8);
    } else {
      top = Math.max(y - 8, 8);
    }
    if (left + tooltipW > rect.width - 8) left = rect.width - tooltipW - 8;
    if (left < 8) left = 8;
    tooltipRef.current.style.left = `${left}px`;
    tooltipRef.current.style.top = `${top}px`;
    tooltipRef.current.classList.remove("hidden");
  }, [data, wrapperRef]);

  const hideTooltip = useCallback(() => {
    if (tooltipRef.current) tooltipRef.current.classList.add("hidden");
    setHoverIndex(null);
  }, []);

  useEffect(() => {
    if (!data.length || !svgRef.current) return;

    const parsed = [...data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((d) => ({
        date: new Date(d.date),
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
        volume: d.volume,
      }));

    const innerHeight = h - MARGIN.top - MARGIN.bottom;
    const innerWidth = w - MARGIN.left - MARGIN.right;
    const volumeHeight = innerHeight * VOLUME_HEIGHT_RATIO;
    const priceHeight = innerHeight * (1 - VOLUME_HEIGHT_RATIO) - 6;

    const xScale = d3
      .scaleBand()
      .domain(parsed.map((d) => d.date.getTime().toString()))
      .range([0, innerWidth])
      .padding(BAR_PADDING);

    const priceMin = Math.min(...parsed.map((d) => d.low));
    const priceMax = Math.max(...parsed.map((d) => d.high));
    const pricePadding = (priceMax - priceMin || 0.01) * 0.12;
    const yScalePrice = d3
      .scaleLinear()
      .domain([priceMin - pricePadding, priceMax + pricePadding])
      .range([priceHeight, 0]);

    const volMax = Math.max(...parsed.map((d) => d.volume), 1);
    const yScaleVol = d3.scaleLinear().domain([0, volMax]).range([volumeHeight, 0]);

    const barWidth = xScale.bandwidth();

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    svg.attr("viewBox", `0 0 ${w} ${h}`).attr("preserveAspectRatio", "xMidYMid meet");

    const g = svg.append("g").attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

    g.append("g")
      .attr("class", "text-zinc-500 dark:text-zinc-400 chart-axis")
      .call(
        d3.axisLeft(yScalePrice)
          .ticks(8)
          .tickFormat((v) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
      )
      .selectAll("text")
      .attr("font-size", "13px")
      .attr("font-weight", "500");

    const priceGroup = g.append("g").attr("class", "price-bars");
    parsed.forEach((d, i) => {
      const key = d.date.getTime().toString();
      const x = (xScale(key) ?? 0) + barWidth / 2;
      const color = d.close >= d.open ? UP_COLOR : DOWN_COLOR;
      const group = priceGroup.append("g").attr("data-bar-index", i);

      group
        .append("line")
        .attr("x1", x).attr("y1", yScalePrice(d.low)).attr("x2", x).attr("y2", yScalePrice(d.high))
        .attr("stroke", color).attr("stroke-width", 2.5).attr("stroke-linecap", "round");

      const tickLen = barWidth * 0.4;
      group
        .append("line")
        .attr("x1", x - tickLen).attr("y1", yScalePrice(d.open)).attr("x2", x).attr("y2", yScalePrice(d.open))
        .attr("stroke", color).attr("stroke-width", 2.5).attr("stroke-linecap", "round");
      group
        .append("line")
        .attr("x1", x).attr("y1", yScalePrice(d.close)).attr("x2", x + tickLen).attr("y2", yScalePrice(d.close))
        .attr("stroke", color).attr("stroke-width", 2.5).attr("stroke-linecap", "round");

      priceGroup
        .append("rect")
        .attr("data-bar-index", i)
        .attr("x", (xScale(key) ?? 0) - 4)
        .attr("y", 0)
        .attr("width", barWidth + 8)
        .attr("height", priceHeight)
        .attr("fill", "transparent")
        .attr("cursor", "pointer")
        .on("mouseenter", function (event) {
          setHoverIndex(i);
          showTooltip(i, event);
        })
        .on("mousemove", (event) => showTooltip(i, event))
        .on("mouseleave", hideTooltip);
    });

    const volGap = g.append("g").attr("class", "volume-section").attr("transform", `translate(0,${priceHeight + 12})`);

    volGap
      .append("line")
      .attr("x1", 0).attr("y1", yScaleVol(0)).attr("x2", innerWidth).attr("y2", yScaleVol(0))
      .attr("stroke", "currentColor").attr("stroke-opacity", 0.2).attr("stroke-width", 1).attr("stroke-dasharray", "4 2");

    parsed.forEach((d, i) => {
      const key = d.date.getTime().toString();
      const x = xScale(key) ?? 0;
      const color = d.close >= d.open ? UP_COLOR : DOWN_COLOR;
      const barTop = yScaleVol(d.volume);
      const barH = Math.max(2, yScaleVol(0) - barTop);

      volGap
        .append("rect")
        .attr("class", "volume-bar")
        .attr("data-bar-index", i)
        .attr("x", x).attr("y", barTop).attr("width", barWidth).attr("height", barH)
        .attr("fill", color).attr("fill-opacity", 0.7).attr("cursor", "pointer");

      volGap
        .append("rect")
        .attr("data-bar-index", i)
        .attr("x", x - 2).attr("y", 0).attr("width", barWidth + 4).attr("height", volumeHeight)
        .attr("fill", "transparent").attr("cursor", "pointer")
        .on("mouseenter", function (event) {
          setHoverIndex(i);
          showTooltip(i, event);
        })
        .on("mousemove", (event) => showTooltip(i, event))
        .on("mouseleave", hideTooltip);
    });

    const formatDate = (key: string) => d3.timeFormat("%d/%m/%y")(new Date(Number(key)));
    const tickCount = w < 500 ? 5 : 10;
    const tickStep = Math.max(1, Math.floor(parsed.length / tickCount));
    const tickValues = parsed
      .filter((_, i) => i % tickStep === 0 || i === parsed.length - 1)
      .map((d) => d.date.getTime().toString());

    g.append("g")
      .attr("transform", `translate(0,${priceHeight + volumeHeight + 12})`)
      .attr("class", "text-zinc-500 dark:text-zinc-400 chart-axis")
      .call(
        d3.axisBottom(xScale)
          .tickValues(tickValues)
          .tickFormat((key) => formatDate(key as string))
          .tickSizeOuter(0)
      )
      .selectAll("text")
      .attr("font-size", "12px");

    volGap
      .append("text")
      .attr("x", 0).attr("y", volumeHeight / 2)
      .attr("fill", "currentColor").attr("font-size", "11px").attr("text-anchor", "start")
      .attr("transform", "rotate(-90)").attr("class", "text-zinc-500 dark:text-zinc-400")
      .text("Volume");

    // Apply selection highlight immediately after draw so it shows on first load
    const highlightSet = new Set(highlightedIndices);
    const nonSelectedOpacity = 0.35;
    svg.selectAll(".price-bars g[data-bar-index]").each(function (_, i) {
      const el = d3.select(this);
      const dimmedByPage = highlightSet.size > 0 && !highlightSet.has(i);
      el.attr("opacity", dimmedByPage ? nonSelectedOpacity : 1);
      el.selectAll("line").attr("stroke-width", "2.5");
    });
    svg.selectAll(".volume-section rect.volume-bar").each(function (_, i) {
      const el = d3.select(this);
      const dimmedByPage = highlightSet.size > 0 && !highlightSet.has(i);
      el.attr("fill-opacity", dimmedByPage ? nonSelectedOpacity : 1);
      el.attr("stroke", "none").attr("stroke-width", "0");
    });
  }, [data, w, h, showTooltip, hideTooltip, highlightedIndices]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || !data.length) return;

    const run = () => {
      const highlightSet = new Set(highlightedIndices);
      const priceGroups = svg.querySelectorAll(".price-bars g[data-bar-index]");
      const volumeBars = svg.querySelectorAll(".volume-section rect.volume-bar");
      const nonSelectedOpacity = 0.35;

      priceGroups.forEach((el, i) => {
        const isHovered = hoverIndex === i;
        const isPageHighlighted = highlightSet.has(i);
        const dimmedByHover = hoverIndex != null && !isHovered;
        const dimmedByPage = highlightSet.size > 0 && !isPageHighlighted;
        const opacity = dimmedByHover ? nonSelectedOpacity : dimmedByPage ? nonSelectedOpacity : 1;
        el.setAttribute("opacity", String(opacity));
        const lines = el.querySelectorAll("line");
        const strokeWidth = isHovered ? "3.5" : "2.5";
        lines.forEach((line) => line.setAttribute("stroke-width", strokeWidth));
      });

      volumeBars.forEach((el) => {
        const idx = el.getAttribute("data-bar-index");
        const i = idx != null ? Number(idx) : -1;
        const isPageHighlighted = highlightSet.has(i);
        const dimmedByHover = hoverIndex != null && hoverIndex !== i;
        const dimmedByPage = highlightSet.size > 0 && !isPageHighlighted;
        const opacity = dimmedByHover ? nonSelectedOpacity : dimmedByPage ? nonSelectedOpacity : 1;
        el.setAttribute("fill-opacity", String(opacity));
        el.setAttribute("stroke", "none");
        el.setAttribute("stroke-width", "0");
      });
    };

    run();
    const id = requestAnimationFrame(run);
    return () => cancelAnimationFrame(id);
  }, [hoverIndex, data.length, highlightedIndices]);

  if (data.length === 0) return null;

  return (
    <div
      ref={wrapperRef}
      className={`relative w-full min-w-0 min-h-[300px] h-[min(75vh,900px)] ${className}`}
    >
      <svg
        ref={svgRef}
        className="block w-full h-full"
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="OHLC price and volume chart"
      />
      <div
        ref={tooltipRef}
        className="pointer-events-none absolute z-10 hidden rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 shadow-xl"
      />
    </div>
  );
}
