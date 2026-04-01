import * as d3 from "d3";

export type ChartMargin = {
  top: number;
  right: number;
  bottom: number;
  left: number;
};

export type ChartHighlightRange = { from: string; to: string };

/**
 * Clears the SVG, sets viewBox and aspect ratio, and returns a root group
 * translated by margin plus inner width/height for drawing.
 */
export function clearSvgAndCreateRoot(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  w: number,
  h: number,
  margin: ChartMargin
): {
  root: d3.Selection<SVGGElement, unknown, null, undefined>;
  innerWidth: number;
  innerHeight: number;
} {
  svg.selectAll("*").remove();
  svg
    .attr("viewBox", `0 0 ${w} ${h}`)
    .attr("preserveAspectRatio", "xMidYMid meet")
    .attr("class", "overflow-visible");
  const root = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);
  const innerWidth = w - margin.left - margin.right;
  const innerHeight = h - margin.top - margin.bottom;
  return { root, innerWidth, innerHeight };
}
