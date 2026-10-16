/* Use case: Displays eligible time-series answers using an attributed documd ECharts template.
What it does: Adapts the existing category/value-axis line option to all returned rows, raw-value inspection and explicit null gaps.
Source: markdown-viewer/skills, 2672b6920f6c055caf72a916b414ede62ecbfc2e,
documd-visuals/examples/ops-monitoring/trend-line-multi-series.md. License: CC-BY-4.0; see THIRD_PARTY_NOTICES.md.
Changes: Remove all demo rows/text, second measure/axis and target; use ExecPlus theme, responsive grid,
unsmoothed single-series geometry, no missing-value connections, bounded navigation and reduced motion.
This option is separate from the Lieflat bar template; no documd exporter is included. */

import type { EChartsCoreOption } from "echarts/core";
import type { PlotPoint } from "./visualization-values";

type LineOptionInput = {
  points: PlotPoint[];
  start: number;
  end: number;
  reducedMotion: boolean;
  width: number;
  connectLinePoints?: boolean;
};

export function makeDocumdLineOption({
  points,
  start,
  end,
  reducedMotion,
  width,
  connectLinePoints = true,
}: LineOptionInput): EChartsCoreOption {
  const magnitude = points.reduce(
    (maximum, point) => Math.max(maximum, Math.abs(point.value ?? 0)),
    Number.MIN_VALUE,
  );
  const values = points.map((point) =>
    point.value === null ? null : point.value / magnitude,
  );
  const minimum = values.reduce<number>(
    (current, value) => Math.min(current, value ?? 0),
    0,
  );
  const maximum = values.reduce<number>(
    (current, value) => Math.max(current, value ?? 0),
    0,
  );
  const first = Math.max(0, Math.min(points.length - 1, Math.floor(start)));
  const last = Math.max(first, Math.min(points.length - 1, Math.floor(end)));

  return {
    color: ["#176c64"],
    animation: !reducedMotion,
    animationDuration: reducedMotion ? 0 : 600,
    animationDurationUpdate: reducedMotion ? 0 : 240,
    tooltip: { show: false, trigger: "axis" },
    grid: {
      left: width < 480 ? 20 : 64,
      right: width < 480 ? 20 : 64,
      top: 24,
      bottom: 40,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => point.label),
      axisLine: { lineStyle: { color: "#929e99" } },
      axisTick: { show: false },
      axisLabel: {
        color: "#53625f",
        fontFamily: "Manrope, sans-serif",
        fontSize: 11,
        width: width < 480 ? 64 : 100,
        overflow: "truncate",
        hideOverlap: true,
      },
    },
    yAxis: [
      {
        type: "value",
        nameLocation: "end",
        nameGap: 10,
        min: minimum,
        max: maximum || (minimum === 0 ? 1 : 0),
        axisLabel: { show: false },
        splitLine: { lineStyle: { color: "#deddd6" } },
        axisLine: { show: false },
        axisTick: { show: false },
      },
    ],
    dataZoom: [
      {
        type: "inside",
        disabled: true,
        filterMode: "none",
        xAxisIndex: 0,
        startValue: first,
        endValue: last,
      },
    ],
    series: [
      {
        type: "line",
        smooth: false,
        connectNulls: false,
        symbolSize: 6,
        showSymbol: true,
        lineStyle: { width: connectLinePoints ? 2 : 0 },
        data: values,
      },
    ],
  };
}
