/* Use case: The public log-in route.
What it does: Sets page metadata and renders the shared account form in login mode. */

import type { Metadata } from "next";
import { AuthPage } from "../auth/auth-page";

export const metadata: Metadata = { title: "Log in — Osalytix" };

export default function Page() {
  return <AuthPage mode="login" />;
}
