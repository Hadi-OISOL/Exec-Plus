/* Use case: Defines the shared document shell for every ExecPlus page.
What it does: Applies global styling, metadata, and the root HTML structure. */

import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import "./globals.css";

const inter = localFont({
  src: "./fonts/InterVariable.woff2",
  variable: "--font-sans",
  weight: "100 900",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Syntelio",
  description: "Synthesized Enterprise Intelligence: verified conversational analytics for structured business data",
};

type RootLayoutProps = Readonly<{
  children: ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body><script dangerouslySetInnerHTML={{ __html: `try{var t=localStorage.getItem("execplus-appearance");document.documentElement.dataset.theme=t==="dark"||t==="light"?t:"system"}catch{}` }} />{children}</body>
    </html>
  );
}

