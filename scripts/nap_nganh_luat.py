"""Xếp mọi văn bản trong CSDL vào 12 ngành luật VÀ 27 lĩnh vực (spec 2026-09-15d).

Chạy: `python -m scripts.nap_nganh_luat [--that]`

Mặc định là CHẠY THỬ: in bảng phân bố rồi dừng, không ghi gì. `--that` mới ghi.
Một phép xếp loại chạy trên 1634 văn bản mà không xem trước là cách nhanh nhất
để phát hiện bộ từ khoá sai sau khi đã ghi đè xong.

Chạy lại được nhiều lần: nó tính lại từ `ten`, `linh_vuc` nguồn và
`co_quan_ban_hanh`, vốn không bị nó đụng tới. Sửa `config/linh_vuc.yaml` rồi
chạy lại là đủ.
"""

import argparse
from collections import Counter

from sqlalchemy import text

from src.services.db import get_engine
from src.services.phan_linh_vuc import LINH_VUC, NGANH_LUAT, phan_linh_vuc, phan_nganh_luat


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--that", action="store_true", help="ghi thật, thay vì chỉ in bảng")
    a = p.parse_args()

    engine = get_engine()
    with engine.connect() as c:
        hang = c.execute(
            text("SELECT id, ten, linh_vuc, co_quan_ban_hanh FROM documents")
        ).mappings().all()

    def _chay_mot_truc(ham, bang, nhan):
        xep, vi_du, khong_ra = {}, {}, []
        for r in hang:
            kq = ham(
                ten=r["ten"] or "",
                linh_vuc_nguon=r["linh_vuc"] or "",
                co_quan=r["co_quan_ban_hanh"] or "",
            )
            if kq is None:
                khong_ra.append((r["ten"] or r["id"])[:70])
                continue
            xep[r["id"]] = kq.linh_vuc
            vi_du.setdefault(kq.linh_vuc, f'{(r["ten"] or "")[:52]}  ← "{kq.tu_khoa}"')

        dem = Counter(xep.values())
        phu = len(xep) / len(hang) * 100 if hang else 0
        print(f"\n══ {nhan} — {len(xep)}/{len(hang)} ({phu:.1f}%) ══")
        print(f"{'nhóm':<24} {'số':>5}  ví dụ")
        for slug, lv in sorted(bang.items(), key=lambda kv: kv[1].uu_tien):
            print(f"{slug:<24} {dem.get(slug, 0):>5}  {vi_du.get(slug, '—')}")
        if khong_ra:
            print(f"  không xếp được: {len(khong_ra)} — ví dụ: {khong_ra[0]}")
        return xep

    nganh = _chay_mot_truc(phan_nganh_luat, NGANH_LUAT, "12 NGÀNH LUẬT")
    linh = _chay_mot_truc(phan_linh_vuc, LINH_VUC, "27 LĨNH VỰC")

    if not a.that:
        print("\nCHẠY THỬ — chưa ghi gì. Thêm `--that` để ghi.")
        return

    with engine.begin() as c:
        if nganh:
            c.execute(
                text("UPDATE documents SET nganh_luat = :n WHERE id = :i"),
                [{"i": i, "n": n} for i, n in nganh.items()],
            )
        if linh:
            c.execute(
                text("UPDATE documents SET linh_vuc_chuan = :n WHERE id = :i"),
                [{"i": i, "n": n} for i, n in linh.items()],
            )
    print(f"\nĐã ghi: nganh_luat {len(nganh)} dòng · linh_vuc_chuan {len(linh)} dòng.")


if __name__ == "__main__":
    main()
