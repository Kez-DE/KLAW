import { createFileRoute } from "@tanstack/react-router";
import { KhongGianSoanThao } from "@/components/soan-thao/KhongGianSoanThao";
import { MAU } from "@/lib/mau-van-ban";
import { SITE_ORIGIN } from "./__root";

export const Route = createFileRoute("/soan-thao/$loaiVanBan")({
  head: ({ params }) => {
    const m = MAU.find((x) => x.id === params.loaiVanBan);
    const ten = m?.ten ?? "Văn bản pháp lý";
    return {
      meta: [
        { title: `Soạn thảo ${ten} — KLAW` },
        {
          name: "description",
          content:
            m?.moTa ??
            "Soạn thảo văn bản pháp lý theo thể thức Việt Nam với biểu mẫu thông minh, xem trước A4 và rà soát rủi ro.",
        },
        { property: "og:title", content: `Soạn thảo ${ten} — KLAW` },
        {
          property: "og:description",
          content:
            m?.moTa ?? "Điền thông tin các bên, chọn điều khoản và xuất bản thảo hoàn chỉnh.",
        },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
      links: [
        {
          rel: "canonical",
          href: `${SITE_ORIGIN}/soan-thao/${encodeURIComponent(params.loaiVanBan)}`,
        },
      ],
    };
  },
  component: TrangSoanThao,
});

function TrangSoanThao() {
  const { loaiVanBan } = Route.useParams();
  return <KhongGianSoanThao loaiVanBan={loaiVanBan} />;
}
