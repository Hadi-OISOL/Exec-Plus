/* Use case: Holds the Osalytix phone app's colours, type and spacing in one place.
What it does: Defines the receipt palette (field green, paper, saffron, ink) shared by every screen. */

import { Platform } from "react-native";

export const color = {
  field: "#0f3b2e",
  fieldSoft: "#1b5141",
  paper: "#f4ecd8",
  card: "#fffaf0",
  line: "#e2d6bb",
  ink: "#1d1a14",
  muted: "#6b6253",
  saffron: "#ff9f1c",
  saffronInk: "#8a4600",
  mint: "#a7dcc0",
  danger: "#a3361f",
  white: "#ffffff",
};

export const font = {
  serif: Platform.select({ ios: "Georgia", default: "serif" }),
  mono: Platform.select({ ios: "Menlo", default: "monospace" }),
};

export const space = (n: number) => n * 4;
