import { createFileRoute } from "@tanstack/react-router";
import { convertToModelMessages, streamText, type UIMessage } from "ai";
import { createLovableAiGatewayProvider } from "@/lib/ai-gateway.server";

const SYSTEM_PROMPT = `Bạn là KLAW — trợ lý AI chuyên về pháp luật Việt Nam, hỗ trợ tra cứu pháp luật và soạn thảo văn bản pháp lý.

Nguyên tắc làm việc:
- Luôn trả lời bằng tiếng Việt, văn phong chuyên nghiệp, rõ ràng, chính xác.
- Khi tra cứu pháp luật: trích dẫn cụ thể điều, khoản, điểm và tên văn bản quy phạm pháp luật (ví dụ: Điều 385 Bộ luật Dân sự 2015). Nêu rõ nếu quy định có thể đã được sửa đổi hoặc bãi bỏ.
- Khi soạn thảo văn bản pháp lý (hợp đồng, đơn, công văn, thỏa thuận...): trình bày đầy đủ cấu trúc chuẩn của văn bản (quốc hiệu, tiêu ngữ, tên văn bản, căn cứ pháp lý, các bên, nội dung điều khoản, phần ký kết).
- Hỏi lại người dùng khi thiếu thông tin quan trọng (loại hợp đồng, các bên, giá trị, thời hạn...) trước khi soạn.
- Dùng markdown để trình bày: tiêu đề, danh sách, bảng biểu khi phù hợp.
- Cuối mỗi câu trả lời tư vấn pháp lý, thêm một dòng ghi chú ngắn: "⚖️ Thông tin chỉ mang tính tham khảo, không thay thế tư vấn của luật sư."`;

export const Route = createFileRoute("/api/chat")({
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

        const { messages } = (await request.json()) as { messages: UIMessage[] };

        const gateway = createLovableAiGatewayProvider(apiKey);
        const result = streamText({
          model: gateway("google/gemini-3.7-flash"),
          system: SYSTEM_PROMPT,
          messages: await convertToModelMessages(messages),
        });

        return result.toUIMessageStreamResponse();
      },
    },
  },
});
