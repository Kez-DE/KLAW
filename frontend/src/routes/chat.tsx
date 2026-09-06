import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * `/chat` từng là màn chào riêng rồi đẩy câu hỏi sang `/dung-thu?q=`. Màn chào
 * nay nằm trong `/dung-thu` (spec 2026-09-06 §4). Giữ route chỉ để link đã chia
 * sẻ không 404; `q` đi theo.
 */
export const Route = createFileRoute("/chat")({
  validateSearch: (tho: Record<string, unknown>): { q?: string } => {
    const q = tho["q"];
    return typeof q === "string" && q.trim() !== "" ? { q } : {};
  },
  beforeLoad: ({ search }) => {
    throw redirect({ to: "/dung-thu", search });
  },
});
