/* Use case: Displays returned answer values with Lieflat's G10 diverging-bar template.
What it does: Adapts the original signed bars, zero baseline and stagger to exact-row inspection, responsive layout and bounded geometry.
Source: larashero3-dotcom/lieflat-charts, ed436ba56b3cbeee20b9b9966b38a9a9689e239c,
templates/glance-gallery.html, G10 card lines 103–108 and renderer lines 502–534.
Copyright: 躺在废墟里. License: PolyForm Noncommercial 1.0.0; see THIRD_PARTY_NOTICES.md.
Changes: Replace demo rows/copy with governed results; use ExecPlus colors/font; normalize only geometry;
retain nulls and row order; cap automatic bar width at the original 16px and hide overlapping labels;
add bounded navigation, exact native inspection and reduced-motion handling. */

import type { EChartsCoreOption } from "echarts/core";
import type { PlotPoint } from "./visualization-values";

type BarOptionInput = {
  points: PlotPoint[];
  start: number;
  end: number;
  reducedMotion: boolean;
  width: number;
};

export function makeLieflatBarOption({
  points,
  start,
  end,
  reducedMotion,
  width,
}: BarOptionInput): EChartsCoreOption {
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
  const showValues =
    width >= 640 &&
    last - first < 16 &&
    points.every((point) => String(point.raw ?? "").length <= 16);

  return {
    animation: !reducedMotion,
    animationDuration: 900,
    animationDurationUpdate: reducedMotion ? 0 : 240,
    animationEasing: "quarticOut",
    animationDelay: (index: number) =>
      reducedMotion ? 0 : Math.min(8, Math.max(0, index - first)) * 80,
    tooltip: { show: false, trigger: "item" },
    grid: {
      left: width < 480 ? 88 : 116,
      right: showValues ? 136 : 24,
      top: 8,
      bottom: 8,
    },
    xAxis: {
      type: "value",
      min: minimum,
      max: maximum || (minimum === 0 ? 1 : 0),
      splitLine: { lineStyle: { color: "#deddd6" } },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    yAxis: {
      type: "category",
      data: points.map((point) => point.label),
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#53625f",
        fontFamily: "Manrope, sans-serif",
        fontSize: 11,
        fontWeight: 600,
        width: width < 480 ? 76 : 104,
        overflow: "truncate",
        interval: "auto",
        hideOverlap: true,
      },
    },
    dataZoom: [
      {
        type: "inside",
        disabled: true,
        filterMode: "none",
        yAxisIndex: 0,
        startValue: first,
        endValue: last,
      },
    ],
    series: [
      {
        type: "bar",
        barMaxWidth: 16,
        barCategoryGap: "35%",
        data: points.map((point, index) => ({
          name: point.label,
          value: values[index],
          itemStyle: {
            color: (point.value ?? 0) >= 0 ? "#176c64" : "#929e99",
            borderRadius:
              (point.value ?? 0) >= 0 ? [0, 9, 9, 0] : [9, 0, 0, 9],
          },
        })),
        label: {
          show: showValues,
          fontFamily: "Manrope, sans-serif",
          fontSize: 11,
          fontWeight: 700,
          position: "outside",
          formatter: (parameter: { dataIndex: number }) => {
            const raw = points[parameter.dataIndex]?.raw;
            return raw === null || raw === undefined ? "" : String(raw);
          },
          color: "#173e3b",
        },
        markLine: {
          symbol: "none",
          silent: true,
          label: { show: false },
          lineStyle: { color: "#8f8e88", width: 1.5 },
          data: [{ xAxis: 0 }],
        },
      },
    ],
  };
}
