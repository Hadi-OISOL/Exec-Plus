/* Use case: The public sign-up route.
What it does: Sets page metadata and renders the shared account form in register mode. */

import type { Metadata } from "next";
import { AuthPage } from "../auth/auth-page";

export const metadata: Metadata = { title: "Create account — Osalytix" };

export default function Page() {
  return <AuthPage mode="register" />;
}
