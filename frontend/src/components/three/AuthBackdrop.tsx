import { Suspense, lazy, useEffect, useState } from "react";

const AuthScene = lazy(() => import("./AuthScene"));

/** Nền gradient sáng — dùng cho SSR, mobile và khi scene đang tải. */
function LightWash() {
  return (
    <div className="auth-wash absolute inset-0" aria-hidden>
      <div className="auth-orb auth-orb-a" />
      <div className="auth-orb auth-orb-b" />
      <div className="auth-orb auth-orb-c" />
    </div>
  );
}

/** 3D chỉ tải trên màn hình >=768px; mobile dùng gradient động thuần CSS. */
export function AuthBackdrop() {
  const [mode, setMode] = useState<"idle" | "css" | "canvas">("idle");

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const apply = () => setMode(mq.matches ? "canvas" : "css");
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <LightWash />
      {mode === "canvas" ? (
        <Suspense fallback={null}>
          <div className="absolute inset-0 opacity-60">
            <AuthScene />
          </div>
        </Suspense>
      ) : null}
    </div>
  );
}
