/* Use case: Starts the print and reveal motion once an element enters the viewport.
What it does: On the client, marks data-print and data-reveal elements as waiting, then flips each to "in" once when it intersects; without scripts, an observer or with reduced motion everything stays printed and visible. */

"use client";

import { useEffect } from "react";

export function PrintReveal() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) return;
    const targets = Array.from(document.querySelectorAll<HTMLElement>("[data-print], [data-reveal]"));
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const target = entry.target as HTMLElement;
        if ("print" in target.dataset) target.dataset.print = "in";
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
