import { useEffect } from "react";

const MAX_DEG = 12;

/**
 * Mouse-tracked 3D tilt (CSS transforms only) for every element marked
 * with `data-tilt` inside the document. No WebGL, no per-frame React state.
 */
export function useMouseTilt() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (window.matchMedia("(hover: none)").matches) return;

    const cards = Array.from(document.querySelectorAll<HTMLElement>("[data-tilt]"));
    const cleanups: (() => void)[] = [];

    cards.forEach((el) => {
      let raf = 0;
      const onMove = (e: PointerEvent) => {
        if (raf) return;
        raf = requestAnimationFrame(() => {
          raf = 0;
          const r = el.getBoundingClientRect();
          const px = (e.clientX - r.left) / r.width;
          const py = (e.clientY - r.top) / r.height;
          el.style.setProperty("--ty", `${(px - 0.5) * 2 * MAX_DEG}deg`);
          el.style.setProperty("--tx", `${-(py - 0.5) * 2 * MAX_DEG}deg`);
          el.style.setProperty("--mx", `${px * 100}%`);
          el.style.setProperty("--my", `${py * 100}%`);
        });
      };
      const onEnter = () => el.classList.add("is-tilting");
      const onLeave = () => {
        el.classList.remove("is-tilting");
        el.style.setProperty("--tx", "0deg");
        el.style.setProperty("--ty", "0deg");
      };
      el.addEventListener("pointermove", onMove);
      el.addEventListener("pointerenter", onEnter);
      el.addEventListener("pointerleave", onLeave);
      cleanups.push(() => {
        if (raf) cancelAnimationFrame(raf);
        el.removeEventListener("pointermove", onMove);
        el.removeEventListener("pointerenter", onEnter);
        el.removeEventListener("pointerleave", onLeave);
      });
    });

    return () => cleanups.forEach((c) => c());
  }, []);
}
