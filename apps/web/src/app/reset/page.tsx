/* Use case: The public password reset route.
What it does: Sets page metadata and renders the shared account form in reset mode. */

import type { Metadata } from "next";
import { AuthPage } from "../auth/auth-page";

export const metadata: Metadata = { title: "Reset password — Syntelio" };

export default function Page() {
  return <AuthPage mode="reset" />;
}
