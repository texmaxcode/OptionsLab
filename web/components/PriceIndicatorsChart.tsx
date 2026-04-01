"use client";

import { useEffect, useRef, type MouseEvent } from "react";
import * as d3 from "d3";
import type { PricePoint, IndicatorPoint } from "@/lib/labApi";
import { useChartDimensions } from "@/hooks/useChartDimensions";

export interface TradeMarker {
  id: string;
  entry_date: string;
  entry_price: number;
  exit_date: string | null;
  exit_price: number | null;
  direction: string;
  size: number;
  pnl: number;
  pnl_pct: number | null;
}

const MARGIN = { top: 24, right: 52, bottom: 40, left: 72 };
const DEFAULT_WIDTH = 1040;
const DEFAULT_HEIGHT = 440;

const SERIES_COLORS = [
  "rgb(30 64 175)",   // close / blue
  "rgb(5 150 105)",   // sma_fast / emerald
  "rgb(161 98 7)",    // sma_slow / amber
  "rgb(126 34 206)",  // rsi / violet
];

type Props = {
  priceSeries: PricePoint[];
  indicatorSeries: IndicatorPoint[] | null;
  trades?: TradeMarker[] | null;
  activeTradeId?: string | null;
  onSelectTrade?: (id: string) => void;
  highlightRange?: { from: string; to: string } | null;
  width?: number;
  height?: number;
  className?: string;
};

export function PriceIndicatorsChart({
  priceSeries,
  indicatorSeries,
  trades,
  activeTradeId,
  onSelectTrade,
  highlightRange = null,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  className = "",
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const { wrapperRef, w, h } = useChartDimensions(width, height);

  useEffect(() => {
    if (!priceSeries.length || !svgRef.current) return;

    const innerWidth = w - MARGIN.left - MARGIN.right;
    const innerHeight = h - MARGIN.top - MARGIN.bottom;

    const priceParsed = priceSeries.map((d) => ({
      date: new Date(d.date),
      close: d.close,
    }));
    const dates = priceParsed.map((d) => d.date);
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(dates) as [Date, Date])
      .range([0, innerWidth]);

    const indicatorNames = indicatorSeries?.length
      ? Object.keys(indicatorSeries[0].indicators || {}).filter((k) => k !== "close")
      : [];
    const hasRsi = indicatorNames.includes("rsi");
    const priceIndicators = indicatorNames.filter((k) => k !== "rsi");
    const priceValues = [...priceParsed.map((d) => d.close)];
    indicatorSeries?.forEach((p) => {
      priceIndicators.forEach((k) => {
        const v = p.indicators?.[k];
        if (v != null) priceValues.push(v);
      });
    });
    const priceMin = Math.min(...priceValues, 0);
    const priceMax = Math.max(...priceValues, 1);
    const pricePadding = (priceMax - priceMin) * 0.05 || 0.01;
    const yScalePrice = d3
      .scaleLinear()
      .domain([priceMin - pricePadding, priceMax + pricePadding])
      .range([innerHeight, 0]);
    const rsiValues =
      indicatorSeries?.flatMap((p) =>
        p.indicators?.rsi != null ? [p.indicators.rsi] : []
      ) ?? [];
    const yScaleRsi = d3
      .scaleLinear()
      .domain([0, 100])
      .range([innerHeight, 0]);

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    svg
      .attr("viewBox", `0 0 ${w} ${h}`)
      .attr("preserveAspectRatio", "xMidYMid meet")
      .attr("class", "overflow-visible");

    const g = svg
      .append("g")
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

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
        d3.axisLeft(yScalePrice).ticks(6).tickFormat((v) => `$${Number(v).toLocaleString()}`)
      )
      .selectAll("text")
      .attr("font-size", "14px");

    if (hasRsi && rsiValues.length) {
      g.append("g")
        .attr("transform", `translate(${innerWidth},0)`)
        .attr("class", "text-zinc-500 dark:text-zinc-400 chart-axis")
        .call(d3.axisRight(yScaleRsi).ticks(5).tickFormat((v) => `${v}`))
        .selectAll("text")
        .attr("font-size", "13px");
    }

    const line = (
      vals: { date: Date; value: number }[],
      color: string,
      useRsiScale: boolean
    ) => {
      const yScale = useRsiScale ? yScaleRsi : yScalePrice;
      g.append("path")
        .datum(vals)
        .attr("fill", "none")
        .attr("stroke", color)
        .attr("stroke-width", 2)
        .attr("stroke-linecap", "round")
        .attr("stroke-linejoin", "round")
        .attr(
          "d",
          d3
            .line<{ date: Date; value: number }>()
            .x((d) => xScale(d.date))
            .y((d) => yScale(d.value))
            .curve(d3.curveMonotoneX)(vals)
        );
    };

    line(
      priceParsed.map((d) => ({ date: d.date, value: d.close })),
      SERIES_COLORS[0],
      false
    );

    const nameColors: Record<string, string> = {};
    let colorIdx = 1;
    indicatorNames.forEach((name) => {
      const color = SERIES_COLORS[colorIdx % SERIES_COLORS.length];
      nameColors[name] = color;
      const vals =
        indicatorSeries?.map((p) => ({
          date: new Date(p.date),
          value: p.indicators?.[name] ?? 0,
        })) ?? [];
      if (vals.length) line(vals, color, name === "rsi");
      colorIdx++;
    });

    const legendItems: { label: string; color: string }[] = [
      { label: "Close", color: SERIES_COLORS[0] },
      ...indicatorNames.map((name) => ({
        label: name.toUpperCase(),
        color: nameColors[name],
      })),
    ];

    const legend = g.append("g").attr("transform", "translate(0,-12)");
    let legendX = 0;
    legendItems.forEach((item) => {
      const group = legend.append("g").attr("transform", `translate(${legendX},0)`);
      group
        .append("line")
        .attr("x1", 0)
        .attr("y1", 0)
        .attr("x2", 16)
        .attr("y2", 0)
        .attr("stroke", item.color)
        .attr("stroke-width", 2)
        .attr("stroke-linecap", "round");
      const text = group
        .append("text")
        .attr("x", 20)
        .attr("y", 3)
        .attr("fill", "currentColor")
        .attr("font-size", 12)
        .text(item.label);
      const textWidth = (text.node() as SVGTextElement | null)?.getBBox().width ?? 0;
      legendX += 20 + textWidth + 16;
    });
    // Crosshair for price series (close)
    if (priceParsed.length && wrapperRef.current && tooltipRef.current) {
      const tooltipEl = tooltipRef.current;
      const wrapperEl = wrapperRef.current;

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
        .attr("fill", SERIES_COLORS[0])
        .attr("stroke", "white")
        .attr("stroke-width", 1.5);

      const bisectDate = d3.bisector<{ date: Date; close: number }, Date>(
        (d) => d.date
      ).center;

      g.append("rect")
        .attr("fill", "transparent")
        .attr("pointer-events", "all")
        .attr("width", innerWidth)
        .attr("height", innerHeight)
        .on("mouseenter", () => {
          focusGroup.style("display", null);
        })
        .on("mouseleave", () => {
          focusGroup.style("display", "none");
          tooltipEl?.classList.add("hidden");
        })
        .on("mousemove", (event) => {
          if (!tooltipEl || !wrapperEl) return;
          const [mx] = d3.pointer(event, wrapperEl);
          const x0 = xScale.invert(mx - MARGIN.left);
          const idx = bisectDate(priceParsed, x0);
          const d = priceParsed[Math.max(0, Math.min(priceParsed.length - 1, idx))];
          const cx = xScale(d.date);
          const cy = yScalePrice(d.close);

          focusLineX.attr("x1", cx).attr("x2", cx);
          focusLineY.attr("y1", cy).attr("y2", cy);
          focusDot.attr("cx", cx).attr("cy", cy);

          const dateFormatter = w < 500 ? d3.timeFormat("%b %Y") : d3.timeFormat("%Y-%m-%d");
          const label = `${dateFormatter(d.date)} · $${d.close.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}`;
          tooltipEl.innerHTML = `<div class="font-medium">${label}</div>`;
          const [x, y] = d3.pointer(event, wrapperEl);
          const maxWidth = wrapperEl.getBoundingClientRect().width - 160;
          tooltipEl.style.left = `${Math.min(x + 10, maxWidth)}px`;
          tooltipEl.style.top = `${y - 16}px`;
          tooltipEl.classList.remove("hidden");
        });
    }

    if (trades && trades.length && wrapperRef.current && tooltipRef.current) {
      const points: {
        date: Date;
        price: number;
        side: "entry" | "exit";
        direction: string;
        trade: TradeMarker;
      }[] = [];

      // Helper: get close price at or nearest to a given date for fallback exit position
      const getPriceAtDate = (d: Date): number | null => {
        if (!priceParsed.length) return null;
        const t = d.getTime();
        let best = priceParsed[0];
        let bestDiff = Math.abs(priceParsed[0].date.getTime() - t);
        for (const p of priceParsed) {
          const diff = Math.abs(p.date.getTime() - t);
          if (diff < bestDiff) {
            bestDiff = diff;
            best = p;
          }
        }
        return best.close;
      };

      trades.forEach((t) => {
        points.push({
          date: new Date(t.entry_date),
          price: t.entry_price,
          side: "entry",
          direction: t.direction,
          trade: t,
        });
        // Always show exit marker for closed trades (exit_date present)
        if (t.exit_date) {
          const exitDate = new Date(t.exit_date);
          const exitPrice =
            t.exit_price != null
              ? t.exit_price
              : getPriceAtDate(exitDate);
          if (exitPrice != null) {
            points.push({
              date: exitDate,
              price: exitPrice,
              side: "exit",
              direction: t.direction,
              trade: t,
            });
          }
        }
      });

      const tooltipEl = tooltipRef.current;
      const wrapperEl = wrapperRef.current;

      const showTooltip = (
        event:
          | MouseEvent
          | d3.D3DragEvent<
              SVGCircleElement,
              (typeof points)[number],
              unknown
            >,
        d: (typeof points)[number]
      ) => {
        if (!tooltipEl || !wrapperEl) return;
        const [x, y] = d3.pointer(event, wrapperEl);
        tooltipEl.style.left = `${x + 12}px`;
        tooltipEl.style.top = `${y}px`;
        tooltipEl.classList.remove("hidden");
        const { trade, side } = d;
        const lines = [
          `${side === "entry" ? "Entry" : "Exit"} ${trade.direction.toUpperCase()} x${trade.size}`,
          `Price: ${d.price.toFixed(2)}`,
          trade.pnl !== undefined
            ? `PnL: ${trade.pnl.toFixed(2)}${trade.pnl_pct != null ? ` (${trade.pnl_pct.toFixed(2)}%)` : ""}`
            : "",
        ].filter(Boolean);
        tooltipEl.innerHTML = lines.join("<br/>");
      };

      const hideTooltip = () => {
        if (!tooltipEl) return;
        tooltipEl.classList.add("hidden");
      };

      const entries = points.filter((p) => p.side === "entry");
      const exits = points.filter((p) => p.side === "exit");

      g.selectAll("circle.trade-entry")
        .data(entries)
        .join("circle")
        .attr("class", "trade-entry")
        .attr("data-trade-id", (d) => d.trade.id)
        .attr("cx", (d) => xScale(d.date))
        .attr("cy", (d) => yScalePrice(d.price))
        .attr("r", (d) =>
          activeTradeId && d.trade.id === activeTradeId ? 6 : 4
        )
        .attr("fill", (d) =>
          d.direction === "short" ? "rgb(220 38 38)" : "rgb(5 150 105)"
        )
        .attr("fill-opacity", (d) =>
          activeTradeId && d.trade.id !== activeTradeId ? 0.3 : 0.9
        )
        .attr("stroke", "white")
        .attr("stroke-width", 1)
        .on("mouseenter", function (event, d) {
          showTooltip(event, d);
        })
        .on("mouseleave", hideTooltip)
        .on("click", function (_event, d) {
          if (onSelectTrade) onSelectTrade(d.trade.id);
        });

      g.selectAll("circle.trade-exit")
        .data(exits)
        .join("circle")
        .attr("class", "trade-exit")
        .attr("data-trade-id", (d) => d.trade.id)
        .attr("cx", (d) => xScale(d.date))
        .attr("cy", (d) => yScalePrice(d.price))
        .attr("r", (d) =>
          activeTradeId && d.trade.id === activeTradeId ? 6 : 4
        )
        .attr("fill", "rgb(220 38 38)")
        .attr("fill-opacity", (d) =>
          activeTradeId && d.trade.id !== activeTradeId ? 0.3 : 0.9
        )
        .attr("stroke", "white")
        .attr("stroke-width", 1)
        .on("mouseenter", function (event, d) {
          showTooltip(event, d);
        })
        .on("mouseleave", hideTooltip)
        .on("click", function (_event, d) {
          if (onSelectTrade) onSelectTrade(d.trade.id);
        });
    }

    if (highlightRange?.from != null && highlightRange?.to != null) {
      const fromX = xScale(new Date(highlightRange.from));
      const toX = xScale(new Date(highlightRange.to));
      const overlay = g.append("g").attr("class", "chart-highlight-overlay").attr("pointer-events", "none");
      if (fromX > 0) {
        overlay.append("rect").attr("x", 0).attr("y", 0).attr("width", fromX).attr("height", innerHeight).attr("fill", "currentColor").attr("fill-opacity", 0.45);
      }
      if (toX < innerWidth) {
        overlay.append("rect").attr("x", toX).attr("y", 0).attr("width", innerWidth - toX).attr("height", innerHeight).attr("fill", "currentColor").attr("fill-opacity", 0.45);
      }
    }
  }, [priceSeries, indicatorSeries, trades, activeTradeId, onSelectTrade, highlightRange, w, h, wrapperRef]);

  if (priceSeries.length === 0) return null;

  return (
    <div
      ref={wrapperRef}
      className="relative w-full min-w-0 overflow-visible min-h-[320px] sm:min-h-[280px] md:min-h-[260px] h-[80vmin] sm:h-[75vmin] md:h-[min(420px,48vw)]"
    >
      <svg
        ref={svgRef}
        className={`block w-full h-full ${className}`}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="Price and indicators"
      />
      <div
        ref={tooltipRef}
        className="pointer-events-none absolute z-10 hidden rounded-md bg-zinc-900 px-2 py-1 text-xs text-zinc-100 shadow-lg ring-1 ring-black/20"
      />
    </div>
  );
}
