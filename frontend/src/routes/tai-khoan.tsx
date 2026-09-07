import { Outlet, createFileRoute, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";
import { AppShell } from "@/components/app/AppShell";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { dichQuayLaiTu } from "@/lib/quay-lai";

export const Route = createFileRoute("/tai-khoan")({
  component: TaiKhoanLayout,
  head: () => ({ meta: [{ title: "Tài khoản — KLAW" }] }),
});

function TaiKhoanLayout() {
  const { laKhach, dangKiemPhien } = useTaiKhoan();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  useEffect(() => {
    if (!dangKiemPhien && laKhach)
      void navigate({ to: "/dang-nhap", search: { next: dichQuayLaiTu(pathname) } });
  }, [laKhach, dangKiemPhien, navigate, pathname]);
  return (
    <AppShell active="/tai-khoan">
      <Outlet />
    </AppShell>
  );
}
