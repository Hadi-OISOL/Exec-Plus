/* Use case: Starts the print and reveal motion once an element enters the viewport.
What it does: On the client, marks data-print and data-reveal elements as waiting, then flips each to "in" once when it intersects and rolls any data-count figure inside up to its exact server-rendered text; without scripts, an observer or with reduced motion everything stays printed and visible. */

"use client";

import { useEffect } from "react";

function rollUp(element: HTMLElement, delay: number) {
  const final = element.textContent ?? "";
  const decimals = final.includes(".") ? final.length - final.indexOf(".") - 1 : 0;
  const target = Number(final.replace(/,/g, ""));
  if (!Number.isFinite(target)) return;
  const format = (value: number) => final.includes(",") ? value.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : value.toFixed(decimals);
  const start = performance.now() + delay;
  const duration = 1100;
  const frame = (now: number) => {
    const progress = Math.min(1, Math.max(0, (now - start) / duration));
    element.textContent = progress >= 1 ? final : format(target * (1 - (1 - progress) ** 4));
    if (progress < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

export function PrintReveal() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) return;
    const targets = Array.from(document.querySelectorAll<HTMLElement>("[data-print], [data-reveal]"));
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const target = entry.target as HTMLElement;
        if ("print" in target.dataset) {
          target.dataset.print = "in";
          for (const figure of target.querySelectorAll<HTMLElement>("[data-count]")) rollUp(figure, 500);
        }
        if ("reveal" in target.dataset) target.dataset.reveal = "in";
        observer.unobserve(target);
      }
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.15 });
    for (const target of targets) {
      if ("print" in target.dataset && target.dataset.print !== "in") target.dataset.print = "wait";
      if ("reveal" in target.dataset && target.dataset.reveal !== "in") target.dataset.reveal = "wait";
      observer.observe(target);
    }
    return () => observer.disconnect();
  }, []);
  return null;
}
