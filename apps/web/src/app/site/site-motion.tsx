/* Use case: The scroll-entrance layer of the public website.
What it does: Marks each data-reveal element as waiting, then lets it in once when it enters the viewport; everything stays visible when scripts or the observer are unavailable or motion is reduced. */

"use client";

import { useEffect } from "react";

export function SiteMotion() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) return;
    const targets = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        (entry.target as HTMLElement).dataset.reveal = "in";
        observer.unobserve(entry.target);
      }
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.1 });
    for (const target of targets) {
      if (target.getBoundingClientRect().top > window.innerHeight * 0.9) target.dataset.reveal = "wait";
      observer.observe(target);
    }
    return () => observer.disconnect();
  }, []);
  return null;
}
