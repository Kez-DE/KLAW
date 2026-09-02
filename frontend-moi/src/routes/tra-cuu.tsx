import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/tra-cuu")({
  component: () => <Outlet />,
});
