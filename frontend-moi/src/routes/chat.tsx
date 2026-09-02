import { createFileRoute } from "@tanstack/react-router";
import { KlawChat } from "@/components/KlawChat";

export const Route = createFileRoute("/chat")({
  head: () => ({
    meta: [
      { title: "Trò chuyện với KLAW — Trợ lý AI Pháp luật" },
      {
        name: "description",
        content:
          "Đặt câu hỏi pháp luật Việt Nam và yêu cầu KLAW soạn thảo hợp đồng, đơn từ, công văn ngay trong cuộc trò chuyện.",
      },
      { property: "og:title", content: "Trò chuyện với KLAW — Trợ lý AI Pháp luật" },
      {
        property: "og:description",
        content:
          "Tra cứu điều luật và soạn thảo văn bản pháp lý theo thể thức chuẩn cùng trợ lý AI KLAW.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: KlawChat,
});
