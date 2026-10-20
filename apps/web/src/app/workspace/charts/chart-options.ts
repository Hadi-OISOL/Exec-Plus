/* Use case: Turns an exact chart specification into a themed, animated Apache ECharts option.
What it does: Builds donut, bar, line/area, histogram, scatter, heatmap, box plot, treemap, flow and tree options whose geometry is approximate and whose labels and tooltips show the returned strings. */

import type { EChartsCoreOption } from "echarts/core";
import { displayMetric, plotNumber } from "../visualization-values";
import { addExact, bucketSlices, readableMetric, shareText } from "./chart-values";
import type { ChartSpec, TreeNode } from "./chart-values";
import type { ChartTokens } from "./chart-tokens";

export type KitContext = { reducedMotion: boolean; width: number };

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]!);
}

function tip(title: string, lines: [string, string][]): string {
  return `<strong>${escapeHtml(title)}</strong>${lines.map(([name, value]) => `<br/><span style="opacity:.72">${escapeHtml(name)}</span> ${escapeHtml(value)}`).join("")}`;
}

function base(tokens: ChartTokens, context: KitContext): EChartsCoreOption {
  return {
    animation: !context.reducedMotion,
    animationDuration: context.reducedMotion ? 0 : 600,
    animationEasing: "cubicOut",
    animationDurationUpdate: context.reducedMotion ? 0 : 300,
    color: tokens.series,
    textStyle: { fontFamily: tokens.font, color: tokens.ink },
    tooltip: {
      trigger: "item", confine: true, backgroundColor: tokens.surface, borderColor: tokens.grid, borderWidth: 1, padding: [10, 12],
      textStyle: { color: tokens.ink, fontFamily: tokens.font, fontSize: 13 }, extraCssText: "border-radius:8px;box-shadow:0 4px 8px -2px rgba(16,24,40,.08),0 2px 4px -2px rgba(16,24,40,.06);font-variant-numeric:tabular-nums;",
    },
  };
}

function axes(tokens: ChartTokens) {
  return {
    category: { axisLine: { lineStyle: { color: tokens.grid } }, axisTick: { show: false }, axisLabel: { color: tokens.muted, fontSize: 12, hideOverlap: true } },
    value: { splitLine: { lineStyle: { color: tokens.grid, type: [3, 3] } }, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: tokens.muted, fontSize: 11, hideOverlap: true } },
  };
}

function stagger(context: KitContext) {
  return context.reducedMotion ? 0 : (index: number) => Math.min(index, 12) * 40;
}

function treeData(node: TreeNode): object {
  return { id: node.id, name: node.name, value: plotNumber(node.value) ?? undefined, exact: node.value, children: node.children?.map(treeData) };
}

export function sliceColor(slice: { members?: unknown[] }, index: number, tokens: ChartTokens): string {
  return slice.members || index >= tokens.series.length ? tokens.other : tokens.series[index];
}

export function kitItemCount(spec: ChartSpec): number {
  switch (spec.kind) {
    case "donut": return bucketSlices(spec.slices, spec.maxSlices).length;
    case "bar": return spec.categories.length;
    case "line": return spec.x.length;
    case "histogram": return spec.bins.length;
    case "scatter": return spec.points.length;
    case "heatmap": return spec.cells.length;
    case "boxplot": return spec.groups.length;
    case "treemap": return spec.nodes.length;
    case "sankey": return spec.nodes.length;
    case "tree": return 0;
  }
}

export function makeKitOption(spec: ChartSpec, tokens: ChartTokens, context: KitContext): EChartsCoreOption {
  const option = base(tokens, context);
  const axis = axes(tokens);
  const unit = spec.unit ? ` ${spec.unit}` : "";
  const narrow = context.width < 480;
  switch (spec.kind) {
    case "donut": {
      const slices = bucketSlices(spec.slices, spec.maxSlices);
      const total = spec.total ?? addExact(spec.slices.map(slice => slice.value));
      return { ...option, series: [{
        type: "pie", radius: ["62%", "85%"], center: ["50%", "50%"], startAngle: 90, minAngle: 2, avoidLabelOverlap: true,
        itemStyle: { borderRadius: 4, borderColor: tokens.surface, borderWidth: 2 }, label: { show: false }, labelLine: { show: false },
        emphasis: { scale: true, scaleSize: 4, itemStyle: { shadowBlur: 12, shadowColor: "rgba(0,0,0,.18)" } },
        animationType: "expansion", animationEasing: "cubicOut",
        tooltip: { formatter: (item: { dataIndex: number }) => { const slice = slices[item.dataIndex]; return slice ? tip(slice.label, [["Value", `${displayMetric(slice.value)}${unit}`], ["Share", shareText(slice.value, total)]]) : ""; } },
        data: slices.map((slice, index) => ({ name: slice.label, value: plotNumber(slice.value) ?? 0, itemStyle: { color: sliceColor(slice, index, tokens) } })),
      }] };
    }
    case "bar": {
      const horizontal = spec.horizontal ?? spec.series.length === 1;
      const category = { type: "category" as const, data: spec.categories, ...axis.category, ...(horizontal ? { inverse: true, axisLabel: { ...axis.category.axisLabel, width: narrow ? 90 : 140, overflow: "truncate" as const } } : {}) };
      const value = { type: "value" as const, ...axis.value };
      const single = spec.series.length === 1;
      return { ...option,
        legend: single ? undefined : { top: 0, right: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: tokens.ink, fontSize: 12 } },
        grid: { left: 8, right: horizontal && single && !narrow ? 72 : 16, top: single ? 8 : 36, bottom: 8, containLabel: true },
        xAxis: horizontal ? value : category, yAxis: horizontal ? category : value,
        series: spec.series.map((series, index) => ({
          type: "bar", name: series.name, barMaxWidth: horizontal ? 20 : 32, barGap: "20%", animationDelay: stagger(context),
          itemStyle: { color: tokens.series[index % tokens.series.length], borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
          emphasis: { focus: "series" },
          label: { show: horizontal && single && !narrow && spec.categories.length <= 16, position: "right", color: tokens.ink, fontSize: 12, formatter: (item: { dataIndex: number }) => readableMetric(series.values[item.dataIndex]) },
          tooltip: { formatter: (item: { dataIndex: number }) => tip(spec.categories[item.dataIndex] ?? "", [[series.name, `${displayMetric(series.values[item.dataIndex])}${unit}`]]) },
          data: series.values.map(plotNumber),
        })),
      };
    }
    case "line": return { ...option,
      legend: spec.series.length > 1 ? { top: 0, right: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: tokens.ink, fontSize: 12 } } : undefined,
      tooltip: { ...(option.tooltip as object), trigger: "axis", axisPointer: { type: "line", lineStyle: { color: tokens.muted, type: "dashed" } },
        formatter: (items: { dataIndex: number; seriesIndex: number }[]) => items.length ? tip(spec.x[items[0].dataIndex] ?? "", items.map(item => [spec.series[item.seriesIndex].name, `${displayMetric(spec.series[item.seriesIndex].values[item.dataIndex])}${unit}`])) : "" },
      grid: { left: 8, right: 16, top: spec.series.length > 1 ? 36 : 12, bottom: 8, containLabel: true },
      xAxis: { type: "category", boundaryGap: false, data: spec.x, ...axis.category },
      yAxis: { type: "value", scale: true, ...axis.value },
      series: spec.series.map((series, index) => ({
        type: "line", name: series.name, smooth: false, connectNulls: false, symbol: "circle", symbolSize: 8, showSymbol: false,
        lineStyle: { width: 2 }, itemStyle: { color: tokens.series[index % tokens.series.length], borderColor: tokens.surface, borderWidth: 2 },
        areaStyle: spec.area ? { opacity: 0.16 } : undefined, emphasis: { focus: "series" }, data: series.values.map(plotNumber),
      })),
    };
    case "histogram": return { ...option,
      grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
      xAxis: { type: "category", data: spec.bins.map(bin => bin.label), ...axis.category },
      yAxis: { type: "value", ...axis.value, minInterval: 1 },
      series: [{ type: "bar", barCategoryGap: 1, animationDelay: stagger(context), itemStyle: { color: tokens.series[0], borderRadius: [4, 4, 0, 0] },
        tooltip: { formatter: (item: { dataIndex: number }) => tip(spec.bins[item.dataIndex]?.label ?? "", [["Count", displayMetric(spec.bins[item.dataIndex]?.count)]]) },
        data: spec.bins.map(bin => plotNumber(bin.count)) }],
    };
    case "scatter": return { ...option,
      grid: { left: 8, right: 20, top: 28, bottom: 28, containLabel: true },
      xAxis: { type: "value", scale: true, name: spec.xName, nameLocation: "middle", nameGap: 28, nameTextStyle: { color: tokens.muted }, ...axis.value },
      yAxis: { type: "value", scale: true, name: spec.yName, nameTextStyle: { color: tokens.muted, align: "left" }, ...axis.value },
      series: [{ type: "scatter", symbolSize: 9, itemStyle: { color: tokens.series[0], opacity: 0.78, borderColor: tokens.surface, borderWidth: 1 }, emphasis: { scale: 1.6 },
        tooltip: { formatter: (item: { dataIndex: number }) => { const point = spec.points[item.dataIndex]; return point ? tip(point.label ?? `Point ${item.dataIndex + 1}`, [[spec.xName, point.x], [spec.yName, point.y]]) : ""; } },
        data: spec.points.map(point => [plotNumber(point.x), plotNumber(point.y)]) }],
    };
    case "heatmap": {
      const data = spec.cells.map(cell => [spec.x.indexOf(cell.x), spec.y.indexOf(cell.y), plotNumber(cell.value)]);
      return { ...option,
        grid: { left: 8, right: 8, top: 8, bottom: 48, containLabel: true },
        xAxis: { type: "category", data: spec.x, ...axis.category, axisLabel: { ...axis.category.axisLabel, rotate: spec.x.length > 4 ? 35 : 0, width: 90, overflow: "truncate" }, splitArea: { show: false } },
        yAxis: { type: "category", data: spec.y, ...axis.category, axisLabel: { ...axis.category.axisLabel, width: narrow ? 70 : 120, overflow: "truncate" } },
        visualMap: { show: true, min: -1, max: 1, calculable: false, orient: "horizontal", left: "center", bottom: 0, itemWidth: 10, itemHeight: narrow ? 140 : 200, text: ["+1", "−1"], textStyle: { color: tokens.muted, fontSize: 11 }, inRange: { color: tokens.diverging } },
        series: [{ type: "heatmap", data, itemStyle: { borderColor: tokens.surface, borderWidth: 2, borderRadius: 4 },
          label: { show: spec.cells.length <= 64 && !narrow, color: tokens.ink, fontSize: 11, fontWeight: 600, rich: { strong: { color: "#ffffff", fontSize: 11, fontWeight: 600 } }, formatter: (item: { dataIndex: number }) => { const value = spec.cells[item.dataIndex]?.value ?? null; return Math.abs(plotNumber(value) ?? 0) >= 0.6 ? `{strong|${readableMetric(value)}}` : readableMetric(value); } },
          tooltip: { formatter: (item: { dataIndex: number }) => { const cell = spec.cells[item.dataIndex]; return cell ? tip(`${cell.y} × ${cell.x}`, [["Value", displayMetric(cell.value)]]) : ""; } } }],
      };
    }
    case "boxplot": return { ...option,
      grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
      xAxis: { type: "category", data: spec.groups.map(group => group.label), ...axis.category },
      yAxis: { type: "value", scale: true, ...axis.value },
      series: [{ type: "boxplot", itemStyle: { color: tokens.surface, borderColor: tokens.series[0], borderWidth: 1.5 }, boxWidth: [8, 36],
        tooltip: { formatter: (item: { dataIndex: number }) => { const group = spec.groups[item.dataIndex]; return group ? tip(group.label, [["Highest", group.max], ["Upper quartile", group.q3], ["Median", group.median], ["Lower quartile", group.q1], ["Lowest", group.min]]) : ""; } },
        data: spec.groups.map(group => [group.min, group.q1, group.median, group.q3, group.max].map(value => plotNumber(value))) },
      ...(spec.outliers?.length ? [{ type: "scatter", symbolSize: 8, itemStyle: { color: tokens.series[1], borderColor: tokens.surface, borderWidth: 1 },
        tooltip: { formatter: (item: { dataIndex: number }) => { const point = spec.outliers![item.dataIndex]; return point ? tip("Unusual value", [["Value", `${displayMetric(point.value)}${unit}`], ...(point.count ? [["Rows", point.count] as [string, string]] : [])]) : ""; } },
        data: spec.outliers.map(point => [Math.max(0, spec.groups.findIndex(group => group.label === point.group)), plotNumber(point.value)]) }] : [])],
    };
    case "treemap": return { ...option,
      series: [{ type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false }, width: "100%", height: "100%", top: 0, left: 0,
        itemStyle: { borderColor: tokens.surface, borderWidth: 2, gapWidth: 2, borderRadius: 6 },
        label: { color: "#ffffff", fontSize: 12, fontWeight: 600, overflow: "truncate", formatter: (item: { name: string; data: { exact?: string } }) => `${item.name}\n${readableMetric(item.data.exact)}` },
        levels: [{ colorMappingBy: "index", color: tokens.series }],
        tooltip: { formatter: (item: { name: string; data: { exact?: string } }) => tip(item.name, [["Value", `${displayMetric(item.data.exact)}${unit}`]]) },
        data: spec.nodes.map(treeData) }],
    };
    case "sankey": return { ...option,
      series: [{ type: "sankey", left: 8, right: narrow ? 90 : 140, top: 8, bottom: 8, nodeGap: 12, nodeWidth: 12, nodeAlign: "justify", draggable: false,
        emphasis: { focus: "adjacency" }, lineStyle: { color: "gradient", opacity: 0.32, curveness: 0.5 }, itemStyle: { borderWidth: 0, borderRadius: 3 },
        label: { color: tokens.ink, fontSize: 12, width: narrow ? 84 : 130, overflow: "truncate" },
        tooltip: { formatter: (item: { dataType: string; dataIndex: number; name: string }) => { const link = spec.links[item.dataIndex]; return item.dataType === "edge" && link ? tip(`${link.source} → ${link.target}`, [["Value", `${displayMetric(link.value)}${unit}`]]) : tip(item.name, []); } },
        data: spec.nodes.map((name, index) => ({ name, itemStyle: { color: tokens.series[index % tokens.series.length] } })),
        links: spec.links.map(link => ({ source: link.source, target: link.target, value: plotNumber(link.value) ?? 0 })) }],
    };
    case "tree": return { ...option,
      series: [{ type: "tree", data: [treeData(spec.root)], orient: "LR", top: 16, bottom: 16, left: narrow ? 20 : 60, right: narrow ? 110 : 180,
        symbol: "circle", symbolSize: 11, edgeShape: "curve", initialTreeDepth: -1, expandAndCollapse: false, roam: false,
        itemStyle: { color: tokens.series[0], borderColor: tokens.surface, borderWidth: 2 }, lineStyle: { color: tokens.grid, width: 1.5, curveness: 0.5 },
        label: { position: "left", verticalAlign: "middle", align: "right", color: tokens.ink, fontSize: 12 },
        leaves: { label: { position: "right", align: "left", width: narrow ? 100 : 160, overflow: "truncate" } },
        emphasis: { focus: "ancestor" } }],
    };
  }
}
