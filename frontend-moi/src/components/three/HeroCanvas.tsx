import { Suspense, lazy, useEffect, useState } from "react";

// Loaded only in the browser, and only on >=768px — mobile never downloads three.js.
const HeroScene = lazy(() => import("./HeroScene"));

/** Static fallback — identical gradient to the mounted scene's backdrop, no layout shift. */
function HeroFallback() {
  return <div className="absolute inset-0 bg-gradient-parchment" aria-hidden />;
}

/** Mobile: animated CSS gradient + brass grain, zero WebGL. */
function HeroMobileArt() {
  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden>
      <div className="hero-mobile-gradient absolute inset-0" />
      <div className="hero-brass-grain absolute inset-0" />
    </div>
  );
}

export function HeroCanvas() {
  const [mode, setMode] = useState<"idle" | "mobile" | "canvas">("idle");

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const apply = () => setMode(mq.matches ? "canvas" : "mobile");
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  if (mode === "idle") return <HeroFallback />;
  if (mode === "mobile") return <HeroMobileArt />;

  return (
    <Suspense fallback={<HeroFallback />}>
      <HeroScene />
    </Suspense>
  );
}
