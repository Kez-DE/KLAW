"""Nạp bản đồ sửa đổi cấp điều khoản từ một văn bản hợp nhất của Công báo.

    python -m scripts.nap_sua_doi_vbhn \
        --url https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-18-vbhn-vpqh-468971.htm \
        --van-ban 45/2019/QH14 --vbhn 18/VBHN-VPQH

`--van-ban` là BẮT BUỘC và không suy ra từ file: metadata loại văn bản của
congbao đã đo được là sai (trang Bộ luật Lao động 2019 mang `<title>Nghị quyết
số 45/2019/QH14…`). Nói thẳng VBHN này hợp nhất văn bản nào rẻ hơn nhiều so với
một bộ suy luận có thể trỏ nhầm cả một bản đồ sửa đổi sang văn bản khác.

Idempotent: `ON CONFLICT` trên `ux_sua_doi_neo(provision_id, nguon, vi_tri)`.
Chạy hai lần cho cùng kết quả, kể cả khi VBHN được tái bản với footnote mới.

Ghi nguồn: mỗi dòng mang `nguon = "congbao.chinhphu.vn — <số hiệu VBHN>"`, và
`effectivity.py` đưa chuỗi đó thẳng ra `ly_do` của câu trả lời.
"""

import argparse
from pathlib import Path

from sqlalchemy import text

from src.services.congbao_client import CongBaoClient
from src.services.db import get_engine, run_migrations
from src.services.vbhn_parser import SuaDoi, doc_sua_doi

# Điều khoản bị sửa nằm ở `duong_dan` sâu nhất khớp được. Khoản MỚI do luật sửa
# chèn vào ("8a" ở Điều 154) KHÔNG có trong văn bản gốc, nên nó lùi về Điều cha
# — và `vi_tri` giữ nguyên chữ VBHN nêu để không mất thông tin đó.
_SQL_NEO = text("SELECT id FROM provisions WHERE duong_dan = :dd")

_SQL_GHI = text(
    "INSERT INTO sua_doi_dieu_khoan"
    " (provision_id, vi_tri, sua_boi_so_ky_hieu, sua_boi_duong_dan, tu_ngay, nguon,"
    "  do_tin_cay, ghi_chu)"
    " VALUES (:pid, :vi_tri, :sk, :dd, :tu_ngay, :nguon, :tc, :ghi_chu)"
    " ON CONFLICT (provision_id, nguon, vi_tri) DO UPDATE SET"
    "   sua_boi_so_ky_hieu = EXCLUDED.sua_boi_so_ky_hieu,"
    "   sua_boi_duong_dan  = EXCLUDED.sua_boi_duong_dan,"
    "   tu_ngay            = EXCLUDED.tu_ngay,"
    "   do_tin_cay         = EXCLUDED.do_tin_cay,"
    "   ghi_chu            = EXCLUDED.ghi_chu"
)


def _phan_giai(conn, van_ban: str, vi_tri: str) -> tuple[int, str] | None:
    """`"Điều 139 > Khoản 1"` → `provisions.id`, lùi dần về tổ tiên nếu cần."""
    phan = vi_tri.split(" > ")
    for i in range(len(phan), 0, -1):
        dd = " > ".join([van_ban, *phan[:i]])
        if (pid := conn.execute(_SQL_NEO, {"dd": dd}).scalar()) is not None:
            return pid, dd
    return None


def nap(docx: bytes, van_ban: str, vbhn: str) -> dict[str, int]:
    """Trả về số đếm để người chạy đối chiếu, không chỉ in ra rồi quên."""
    sua_doi = doc_sua_doi(docx)
    nguon = f"congbao.chinhphu.vn — {vbhn}"
    dem = {"giai_duoc": 0, "can_doi_chieu_tay": 0, "khong_phan_giai_duoc": 0, "lui_ve_cha": 0}
    engine = get_engine()
    with engine.begin() as conn:
        # Đối chiếu chéo số hiệu văn bản ĐI SỬA với corpus. ĐO ĐƯỢC: 2/3 văn bản
        # sửa Bộ luật Lao động (113/2025/QH15, 124/2025/QH15) NẰM NGOÀI corpus 57
        # văn bản. Nên đây là TÍN HIỆU TIN CẬY, không phải bộ lọc — lọc bằng nó
        # sẽ vứt đúng ca Điều 139, ca trung tâm của cả việc này.
        trong_corpus = {r[0] for r in conn.execute(text("SELECT so_ky_hieu FROM documents"))}
        for s in sua_doi:
            neo = _phan_giai(conn, van_ban, s.vi_tri)
            if neo is None:
                dem["khong_phan_giai_duoc"] += 1
                print(f"[bỏ] {s.vi_tri}: không có điều khoản nào khớp trong {van_ban}")
                continue
            pid, dd = neo
            if not dd.endswith(s.vi_tri):
                dem["lui_ve_cha"] += 1
                print(f"[lùi] {s.vi_tri} → {dd} (điều khoản mới, chưa có trong bản gốc)")
            tc = s.do_tin_cay
            if tc != "can_doi_chieu_tay":
                tc = "cao" if s.sua_boi_so_ky_hieu in trong_corpus else "trung_binh"
                dem["giai_duoc"] += 1
            else:
                dem["can_doi_chieu_tay"] += 1
            conn.execute(_SQL_GHI, {
                "pid": pid, "vi_tri": s.vi_tri, "sk": s.sua_boi_so_ky_hieu,
                "dd": s.sua_boi_duong_dan, "tu_ngay": s.tu_ngay, "nguon": nguon,
                "tc": tc, "ghi_chu": s.ghi_chu})
            print(f"[ok] {dd}  ←  {s.sua_boi_so_ky_hieu or '?'} từ {s.tu_ngay or '?'}  [{tc}]")
    return dem


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", help="trang chi tiết congbao của VBHN")
    ap.add_argument("--tep", type=Path, help="dùng .docx đã tải sẵn thay vì gọi mạng")
    ap.add_argument("--van-ban", required=True, help="số ký hiệu văn bản GỐC, vd 45/2019/QH14")
    ap.add_argument("--vbhn", required=True, help="số ký hiệu VBHN, vd 18/VBHN-VPQH")
    a = ap.parse_args()
    if not (a.url or a.tep):
        ap.error("cần --url hoặc --tep")

    run_migrations("014")   # chỉ bảng của script này; xem `db.run_migrations`
    docx = a.tep.read_bytes() if a.tep else CongBaoClient().tai_vbhn(a.url)
    dem = nap(docx, a.van_ban, a.vbhn)
    print(f"\n{dem}")


if __name__ == "__main__":
    main()


__all__ = ["SuaDoi", "nap"]
