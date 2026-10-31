/* Use case: Pure rules for the get-to-know-you questionnaire, shared by the flow and its tests.
What it does: Decides when the flow must show, toggles choices and builds the exact save payload. */

export type Answer = string | string[];
export type Question = { id: string; prompt: string; kind: "text" | "single" | "multi"; options: string[]; hint: string };
export type ProfileView = {
  user_id: string;
  version: number;
  preferred_name: string;
  answers: Record<string, Answer>;
  completed_at: string | null;
  skipped_at: string | null;
  status: "pending" | "completed" | "skipped";
  questionnaire: Question[];
};

export function profileNeeded(profile: Pick<ProfileView, "status"> | null, accountKind: string): boolean {
  return profile !== null && profile.status === "pending" && accountKind !== "operator";
}

export function toggleChoice(current: Answer | undefined, option: string): string[] {
  const list = Array.isArray(current) ? current : [];
  return list.includes(option) ? list.filter(value => value !== option) : [...list, option];
}

export function hasAnswer(value: Answer | undefined): boolean {
  return Array.isArray(value) ? value.length > 0 : Boolean(value && value.trim());
}

export function profilePayload(version: number, name: string, answers: Record<string, Answer>, status: "completed" | "skipped") {
  const kept: Record<string, Answer> = {};
  for (const [id, value] of Object.entries(answers)) {
    if (id === "preferred_name" || !hasAnswer(value)) continue;
    kept[id] = Array.isArray(value) ? value : value.trim();
  }
  return { expected_version: version, preferred_name: name.trim().slice(0, 120), answers: kept, status };
}

export function progressLabel(index: number, total: number): string {
  return `${index + 1} of ${total}`;
}
