import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/soan-thao")({
  component: SoanThaoLayout,
  head: () => ({
    meta: [
      { title: "Soạn thảo hợp đồng & văn bản pháp lý | KLAW" },
      {
        name: "description",
        content:
          "Chọn mẫu hợp đồng, quyết định, đơn từ; điền biểu mẫu theo bước, xem trước khổ A4 và xuất Word/PDF ngay trên máy bạn.",
      },
      { property: "og:title", content: "Soạn thảo văn bản pháp lý cùng KLAW" },
      {
        property: "og:description",
        content:
          "Hơn 25 mẫu văn bản Việt Nam: điền thông tin các bên, chọn điều khoản, xem trước bản A4 và nhận cảnh báo rủi ro.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
});

function SoanThaoLayout() {
  return <Outlet />;
}
