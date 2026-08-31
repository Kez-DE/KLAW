import { createFileRoute } from "@tanstack/react-router";
import { streamText } from "ai";
import { createLovableAiGatewayProvider } from "@/lib/ai-gateway.server";

const SYSTEM_PROMPT = `Bạn là KLAW — trợ lý soạn thảo văn bản pháp lý theo pháp luật Việt Nam.

Yêu cầu bắt buộc:
- Soạn văn bản hoàn chỉnh bằng tiếng Việt, đúng thể thức: quốc hiệu – tiêu ngữ, tên văn bản, số hiệu (nếu có), căn cứ pháp lý (viện dẫn đúng luật/nghị định hiện hành), thông tin các bên, các điều khoản được đánh số (Điều 1, Điều 2, …), điều khoản giải quyết tranh chấp, hiệu lực, phần ký kết.
- Sử dụng đúng thông tin người dùng cung cấp; với thông tin còn thiếu, để chỗ trống dạng […] và liệt kê ở cuối phần "Thông tin cần bổ sung".
- Trình bày bằng markdown, dùng tiêu đề và danh sách rõ ràng, không thêm lời dẫn ngoài văn bản.
- Kết thúc bằng: "⚖️ Bản thảo mang tính tham khảo, nên được luật sư rà soát trước khi ký kết."`;

export const Route = createFileRoute("/api/draft")({
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

        const body = (await request.json()) as {
          docType?: string;
          fields?: Record<string, string>;
          notes?: string;
        };
        if (!body.docType) {
          return Response.json(
            { error: "Chưa chọn loại văn bản." },
            { status: 400 },
          );
        }

        const filled = Object.entries(body.fields ?? {})
          .filter(([, v]) => v && v.trim())
          .map(([k, v]) => `- ${k}: ${v}`)
          .join("\n");

        const gateway = createLovableAiGatewayProvider(apiKey);
        const result = streamText({
          model: gateway("google/gemini-3.7-flash"),
          system: SYSTEM_PROMPT,
          prompt: `Loại văn bản cần soạn: ${body.docType}

Thông tin đã có:
${filled || "(chưa cung cấp)"}

Yêu cầu bổ sung của người dùng: ${body.notes?.trim() || "(không có)"}

Hãy soạn văn bản hoàn chỉnh.`,
        });

        return result.toTextStreamResponse();
      },
    },
  },
});
