/* Use case: Shared building blocks for the Osalytix phone app screens.
What it does: Provides the screen frame, buttons, inputs, receipt cards, chips, exact tables and simple bar charts in the receipt style. */

import { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
  ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { color, font, space } from "./theme";

export function Screen({
  title,
  kicker,
  onBack,
  right,
  children,
  scroll = true,
}: {
  title: string;
  kicker?: string;
  onBack?: () => void;
  right?: ReactNode;
  children: ReactNode;
  scroll?: boolean;
}) {
  const body = scroll ? (
    <ScrollView contentContainerStyle={s.body} keyboardShouldPersistTaps="handled">
      {children}
    </ScrollView>
  ) : (
    <View style={[s.body, { flex: 1 }]}>{children}</View>
  );
  return (
    <SafeAreaView style={s.safe} edges={["top"]}>
      <View style={s.header}>
        <View style={s.headerRow}>
          {onBack ? (
            <Pressable onPress={onBack} hitSlop={12} accessibilityRole="button" accessibilityLabel="Back">
              <Text style={s.back}>‹ Back</Text>
            </Pressable>
          ) : (
            <Text style={s.brand}>
              <Text style={s.brandMark}>O</Text> Osalytix
            </Text>
          )}
          {right}
        </View>
        {kicker ? <Text style={s.kicker}>{kicker.toUpperCase()}</Text> : null}
        <Text style={s.title} numberOfLines={2}>
          {title}
        </Text>
      </View>
      <View style={s.paper}>{body}</View>
    </SafeAreaView>
  );
}

export function Button({
  label,
  onPress,
  kind = "primary",
  busy,
  disabled,
  style,
}: {
  label: string;
  onPress: () => void;
  kind?: "primary" | "secondary" | "ghost";
  busy?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
}) {
  const off = disabled || busy;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!off, busy: !!busy }}
      onPress={off ? undefined : onPress}
      style={({ pressed }) => [
        s.button,
        kind === "primary" && s.primary,
        kind === "secondary" && s.secondary,
        kind === "ghost" && s.ghost,
        pressed && !off && { transform: [{ translateY: 1 }], opacity: 0.9 },
        off && { opacity: 0.5 },
        style,
      ]}
    >
      {busy ? (
        <ActivityIndicator color={color.ink} />
      ) : (
        <Text style={[s.buttonText, kind === "secondary" && { color: color.field }, kind === "ghost" && { color: color.saffronInk }]}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}

export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={{ marginBottom: space(3) }}>
      <Text style={s.label}>{label}</Text>
      <TextInput placeholderTextColor={color.muted} style={s.input} accessibilityLabel={label} {...props} />
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[s.card, style]}>{children}</View>;
}

export function Receipt({ title, children, stamp }: { title: string; children: ReactNode; stamp?: string }) {
  return (
    <View style={s.receipt}>
      <View style={s.receiptHead}>
        <Text style={s.receiptTitle}>{title}</Text>
        {stamp ? <Text style={s.stamp}>{stamp}</Text> : null}
      </View>
      <View style={s.dash} />
      {children}
    </View>
  );
}

export function Chip({ label, onPress, active }: { label: string; onPress?: () => void; active?: boolean }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={[s.chip, active && s.chipActive]}>
      <Text style={[s.chipText, active && { color: color.paper }]}>{label}</Text>
    </Pressable>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <View style={{ paddingVertical: space(10), alignItems: "center", gap: space(3) }}>
      <ActivityIndicator color={color.field} size="large" />
      <Text style={s.muted}>{label}</Text>
    </View>
  );
}

export function ErrorText({ text }: { text: string }) {
  return text ? <Text style={s.error}>{text}</Text> : null;
}

export function H({ children }: { children: ReactNode }) {
  return <Text style={s.h}>{children}</Text>;
}

export function P({ children, muted }: { children: ReactNode; muted?: boolean }) {
  return <Text style={muted ? s.muted : s.p}>{children}</Text>;
}

export function exact(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  const text = String(value);
  if (!/^-?\d+(\.\d+)?$/.test(text)) return text;
  const [whole, part] = text.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const trimmed = part ? part.replace(/0+$/, "") : "";
  return trimmed ? `${grouped}.${trimmed}` : grouped;
}

export function short(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value ?? "—");
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function Bars({ rows, unit }: { rows: { label: string; value: unknown }[]; unit?: string | null }) {
  const values = rows.map((r) => Number(r.value)).filter(Number.isFinite);
  const max = Math.max(...values.map(Math.abs), 0) || 1;
  return (
    <View style={{ gap: space(2), marginTop: space(2) }}>
      {rows.slice(0, 12).map((row, i) => {
        const v = Number(row.value);
        const width = Number.isFinite(v) ? `${Math.max(2, (Math.abs(v) / max) * 100)}%` : "0%";
        return (
          <View key={`${row.label}-${i}`}>
            <View style={s.barLabelRow}>
              <Text style={s.barLabel} numberOfLines={1}>
                {row.label}
              </Text>
              <Text style={s.barValue}>
                {short(row.value)}
                {unit ? ` ${unit}` : ""}
              </Text>
            </View>
            <View style={s.barTrack}>
              <View style={[s.barFill, { width: width as any }, i === 0 && { backgroundColor: color.saffron }]} />
            </View>
          </View>
        );
      })}
    </View>
  );
}

export function Table({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: space(3) }}>
      <View>
        <View style={[s.tr, { borderBottomColor: color.ink }]}>
          {columns.map((c) => (
            <Text key={c} style={[s.td, s.th]} numberOfLines={1}>
              {c}
            </Text>
          ))}
        </View>
        {rows.slice(0, 50).map((row, i) => (
          <View key={i} style={s.tr}>
            {row.map((cell, j) => (
              <Text key={j} style={s.td} numberOfLines={1}>
                {exact(cell)}
              </Text>
            ))}
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

export const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: color.field },
  header: { paddingHorizontal: space(5), paddingTop: space(2), paddingBottom: space(5) },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", minHeight: 32 },
  brand: { color: color.paper, fontSize: 16, fontWeight: "700", letterSpacing: 0.3 },
  brandMark: { color: color.saffron, fontFamily: font.serif, fontSize: 20 },
  back: { color: color.mint, fontSize: 16, fontWeight: "600" },
  kicker: { color: color.mint, fontSize: 11, fontWeight: "700", letterSpacing: 1.6, marginTop: space(4) },
  title: { color: color.paper, fontFamily: font.serif, fontSize: 28, lineHeight: 34, marginTop: space(1) },
  paper: { flex: 1, backgroundColor: color.paper, borderTopLeftRadius: 22, borderTopRightRadius: 22, overflow: "hidden" },
  body: { padding: space(5), paddingBottom: space(16), gap: space(4) },
  button: { minHeight: 50, borderRadius: 14, paddingHorizontal: space(5), alignItems: "center", justifyContent: "center" },
  primary: { backgroundColor: color.saffron, borderBottomWidth: 3, borderBottomColor: "#d97e00" },
  secondary: { backgroundColor: color.card, borderWidth: 1.5, borderColor: color.field },
  ghost: { backgroundColor: "transparent", minHeight: 40 },
  buttonText: { color: color.ink, fontSize: 16, fontWeight: "700" },
  label: { color: color.ink, fontWeight: "600", marginBottom: space(1.5), fontSize: 14 },
  input: {
    backgroundColor: color.card,
    borderWidth: 1.5,
    borderColor: color.line,
    borderRadius: 12,
    paddingHorizontal: space(4),
    paddingVertical: space(3),
    fontSize: 16,
    color: color.ink,
  },
  card: { backgroundColor: color.card, borderRadius: 16, padding: space(4), borderWidth: 1, borderColor: color.line },
  receipt: {
    backgroundColor: color.card,
    borderRadius: 6,
    padding: space(4),
    borderWidth: 1,
    borderColor: color.line,
    shadowColor: "#3a2e10",
    shadowOpacity: 0.08,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  receiptHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: space(2) },
  receiptTitle: { flex: 1, fontFamily: font.serif, fontSize: 18, color: color.ink, lineHeight: 23 },
  stamp: {
    color: color.field,
    borderWidth: 1.5,
    borderColor: color.field,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 1,
    transform: [{ rotate: "-4deg" }],
  },
  dash: { borderBottomWidth: 1, borderStyle: "dashed", borderColor: color.muted, marginVertical: space(3), opacity: 0.5 },
  chip: {
    paddingHorizontal: space(3.5),
    paddingVertical: space(2),
    borderRadius: 999,
    borderWidth: 1.5,
    borderColor: color.field,
    backgroundColor: color.card,
  },
  chipActive: { backgroundColor: color.field },
  chipText: { color: color.field, fontWeight: "600", fontSize: 14 },
  muted: { color: color.muted, fontSize: 14, lineHeight: 20 },
  p: { color: color.ink, fontSize: 15, lineHeight: 22 },
  h: { fontFamily: font.serif, fontSize: 21, color: color.ink, marginTop: space(2) },
  error: { color: color.danger, fontWeight: "600", fontSize: 14 },
  barLabelRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 3, gap: space(2) },
  barLabel: { flex: 1, color: color.ink, fontSize: 13 },
  barValue: { fontFamily: font.mono, color: color.ink, fontSize: 13 },
  barTrack: { height: 10, backgroundColor: "#ebe1c8", borderRadius: 5, overflow: "hidden" },
  barFill: { height: 10, backgroundColor: color.field, borderRadius: 5 },
  tr: { flexDirection: "row", borderBottomWidth: 1, borderBottomColor: color.line },
  td: { width: 120, paddingVertical: space(2), paddingRight: space(2), fontFamily: font.mono, fontSize: 12, color: color.ink },
  th: { fontFamily: undefined, fontWeight: "700" },
  row: { flexDirection: "row", flexWrap: "wrap", gap: space(2) },
});
