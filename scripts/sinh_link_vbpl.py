"""Sinh `link_vbpl` cho mọi văn bản lấy từ MOJ, vào một seed RIÊNG (spec 2026-09-15g).

    python -m scripts.sinh_link_vbpl            # chạy thử, in bảng rồi dừng
    python -m scripts.sinh_link_vbpl --that     # ghi data/seed/link_vbpl_suy_ra.yaml

Vì sao suy ra được chứ không phải đoán: `documents.id` của văn bản lấy từ MOJ
CHÍNH LÀ `ItemID` của vbpl.vn. Chứng cứ trong chính CSDL — `documents.nguon_url`
ghi `vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{id}`, cùng một id.

Vì sao KHÔNG kiểm sống được: `vbpl.vn` trả 403 cho mọi bot, kể cả Firecrawl với
proxy stealth (`document_antibot`, đo 2026-09-15). Trang, tệp PDF và tệp DOC đều
403. Không có công cụ nào vượt được, nên không có cách nào xác nhận bằng máy.

Vì sao GHI RA TỆP KHÁC: `data/seed/link_cong_luat.yaml` chứa link NGƯỜI đã mở
bằng trình duyệt thật và ký tên. Trộn link máy suy ra vào đó là xoá mất sự khác
nhau giữa hai loại bằng chứng — đúng lỗi mà cả dự án này tồn tại để chống. Hai
tệp, hai mức tin cậy, `kiem_boi` nói thẳng loại nào.
"""

import argparse
from datetime import date
from pathlib import Path

from sqlalchemy import text

from src.services.db import get_engine

RA = Path("data/seed/link_vbpl_suy_ra.yaml")
MAU = "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID={id}"
KIEM_BOI = "may-suy-ra-chua-nguoi-mo"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--that", action="store_true", help="ghi tệp, thay vì chỉ in")
    a = p.parse_args()

    with get_engine().connect() as c:
        hang = c.execute(
            text(
                "SELECT id, so_ky_hieu, ten FROM documents "
                "WHERE id ~ '^[0-9]+$' AND (link_vbpl IS NULL OR link_vbpl = '') "
                "ORDER BY id"
            )
        ).mappings().all()
        tong = c.execute(text("SELECT count(*) FROM documents")).scalar_one()
        khong_so = c.execute(text("SELECT count(*) FROM documents WHERE id !~ '^[0-9]+$'")).scalar_one()

    print(f"\n{tong} văn bản · suy ra được {len(hang)} · id không phải số {khong_so} (không suy ra)")
    print("\n3 dòng đầu, mở thử bằng trình duyệt trước khi nạp:")
    for r in hang[:3]:
        print(f"  {r['so_ky_hieu']:<20} {MAU.format(id=r['id'])}")
        print(f"  {'':<20} {(r['ten'] or '')[:72]}")

    if not a.that:
        print("\nCHẠY THỬ — chưa ghi gì. Thêm `--that` để ghi.")
        return

    dong = [
        "# Link vbpl.vn SUY RA từ `documents.id` (= ItemID của vbpl.vn).",
        "#",
        "# CHƯA CÓ NGƯỜI MỞ THỬ. `vbpl.vn` trả 403 cho mọi bot kể cả Firecrawl proxy",
        "# stealth, nên không xác minh bằng máy được. Mở vài dòng bằng trình duyệt",
        "# thật rồi đổi `kiem_boi` sang tên bạn và chuyển sang `link_cong_luat.yaml`.",
        "#",
        "# Tệp này TÁCH khỏi `link_cong_luat.yaml` có chủ ý: trộn link máy suy ra vào",
        "# link người đã ký là xoá mất sự khác nhau giữa hai mức bằng chứng.",
        f"# Sinh bằng `python -m scripts.sinh_link_vbpl --that` ngày {date.today()}.",
        "",
    ]
    for r in hang:
        dong += [
            f'"{r["id"]}":',
            f"  vbpl: {MAU.format(id=r['id'])}",
            "  chinhphu: null",
            "  tvpl: null",
            f"  kiem_luc: {date.today()}",
            f"  kiem_boi: {KIEM_BOI}",
        ]
    RA.parent.mkdir(parents=True, exist_ok=True)
    RA.write_text("\n".join(dong) + "\n", encoding="utf-8")
    print(f"\nĐã ghi {len(hang)} dòng → {RA}")
    print("CHƯA nạp vào CSDL. Nạp bằng:")
    print(f"  python -c \"from pathlib import Path; from scripts.nap_link_cong_luat import nap;"
          f" from src.services.db import get_engine; print(nap(Path('{RA}'), get_engine()))\"")


if __name__ == "__main__":
    main()
