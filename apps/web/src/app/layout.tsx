/* Use case: Defines the shared document shell for every ExecPlus page.
What it does: Applies global styling, metadata, and the root HTML structure. */

import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import "./globals.css";

const manrope = localFont({
  src: "./fonts/Manrope-Variable.ttf",
  variable: "--font-product",
  weight: "200 800",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ExecPlus",
  description: "Verified conversational analytics for structured business data",
};

type RootLayoutProps = Readonly<{
  children: ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className={manrope.variable}>
      <body>{children}</body>
    </html>
  );
}

