import { createFileRoute } from "@tanstack/react-router";
import { streamText } from "ai";
import { createLovableAiGatewayProvider } from "@/lib/ai-gateway.server";

const SYSTEM_PROMPT = `Bạn là KLAW — công cụ tra cứu pháp luật Việt Nam theo điều, khoản, điểm, nghị quyết, nghị định, thông tư.

Yêu cầu bắt buộc:
- Trả lời bằng tiếng Việt, chính xác, súc tích, có cấu trúc markdown.
- Hiểu truy vấn tiếng Việt tự nhiên (có hoặc không dấu), ví dụ "dieu 385 bo luat dan su", "khoản 2 điều 5 nghị định 15/2020".
- Bố cục trả lời:
  ## Kết quả tra cứu
  **Căn cứ pháp lý:** <Tên văn bản đầy đủ, số hiệu, năm, cơ quan ban hành>
  ### Trích dẫn nguyên văn
  > trích dẫn nội dung điều/khoản/điểm liên quan (nêu rõ Điều … Khoản … Điểm …)
  ### Giải thích
  - diễn giải ngắn gọn, dễ hiểu
  ### Văn bản liên quan
  - liệt kê văn bản sửa đổi, bổ sung, hướng dẫn, hoặc bãi bỏ (nếu có)
- Nếu không chắc chắn về nguyên văn, nói rõ "Cần đối chiếu với văn bản gốc" thay vì bịa nội dung.
- Kết thúc bằng: "⚖️ Thông tin chỉ mang tính tham khảo, cần đối chiếu văn bản pháp luật hiện hành."`;

export const Route = createFileRoute("/api/lookup")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const apiKey = process.env["LOVABLE_API_KEY"];
        if (!apiKey) {
          return Response.json(
            { error: "Thiếu cấu hình khóa AI trên máy chủ." },
            { status: 500 },
          );
        }

        const { query, scope } = (await request.json()) as {
          query?: string;
          scope?: string;
        };
        if (!query || !query.trim()) {
          return Response.json({ error: "Thiếu nội dung tra cứu." }, { status: 400 });
        }

        const gateway = createLovableAiGatewayProvider(apiKey);
        const result = streamText({
          model: gateway("google/gemini-3.7-flash"),
          system: SYSTEM_PROMPT,
          prompt: `Phạm vi tra cứu: ${scope || "Tất cả loại văn bản"}\nTruy vấn: ${query}`,
        });

        return result.toTextStreamResponse();
      },
    },
  },
});
