"""Đo lượng mất mát khi `hieu_tai_lieu` dựng lại một biểu mẫu nguồn thành
`van_ban.muc` (Phase 8 R5, `.sdd/phase-8-brief.md`).

Gọi model THẬT qua OpenRouter (~0,001 USD/tệp) — KHÔNG chạy trong CI, KHÔNG
chạy tự động sau mỗi lần sửa (cùng lý do các tệp bị cấm chạy của backend gate:
`test_route.py`, `test_tra_cuu.py`, …). Chạy TAY khi cần đo trước/sau một thay
đổi:

    PYTHONPATH="$PWD" .venv/bin/python scripts/kiem_tai_lieu_tong_quat.py

Đọc được CẢ HAI hình dạng `van_ban.muc[]` — `khoi` (Phase 8) và `noi_dung`/
`bang` (Phase 7 trở về trước, hàm `_khoi` dưới đây quy về cùng một dạng đếm
được) — nên CÙNG một script đo được cả "trước" lẫn "sau" bản vá, không phải
viết lại lần thứ hai.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.agents.nodes.hieu_tai_lieu import hieu_tai_lieu
from src.services import doc_tai_lieu
from src.services.llm import from_settings, generate_model

# Tối thiểu theo brief (R5) cộng ca chịu áp lực `Evaluation Form.docx`.
MAC_DINH = [
    "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx",
    "BM.ĐT.18.03. Đơn đăng ký đi thực tập tốt nghiệp Ver 02.docx",
    "BM.ĐT.18.05. Kế hoạch thực tập tại cơ sở Ver 02.docx",
    "BM.ĐT.18.11. Phiếu đánh giá quá trình thực tập tốt nghiệp của sinh viên tại cơ sở thực tập Ver 02 (1).docx",
    "phiếu đánh giá thực tập công nghiệp.docx",
    "Evaluation Form.docx",
]

CAU_HOI = (
    "Hãy dựng lại nguyên văn biểu mẫu này thành một văn bản đầy đủ mọi mục, "
    "mọi trường, mọi bảng, đầu trang và chân trang của nó."
)


def _khoi(m: dict) -> list[dict]:
    """Một mục → danh sách khối, đọc được CẢ hình dạng `khoi` (Phase 8) LẪN
    `noi_dung`/`bang` rời (Phase 7 trở về trước) — script không đổi giữa hai
    lần chạy trước/sau bản vá."""
    if isinstance(m.get("khoi"), list):
        return m["khoi"]
    ra = []
    if m.get("noi_dung"):
        ra.append({"noi_dung": m["noi_dung"], "bang": []})
    if m.get("bang"):
        ra.append({"noi_dung": "", "bang": m["bang"]})
    return ra


def do_mot_tep(duong_dan: Path) -> None:
    du_lieu = duong_dan.read_bytes()
    tl = doc_tai_lieu.doc(duong_dan.name, du_lieu)
    so_bang_vao = len({d.bang[0] for d in tl.don_vi if d.bang})
    so_dau_trang = sum(1 for d in tl.don_vi if d.vung == "dau_trang")
    so_chan_trang = sum(1 for d in tl.don_vi if d.vung == "chan_trang")
    chan_trang_chu = next((d.noi_dung for d in tl.don_vi if d.vung == "chan_trang"), None)

    llm = from_settings()
    tai_lieu = [{"id": "x", "ten_tep": duong_dan.name, "don_vi": tl.don_vi}]
    ra = hieu_tai_lieu({"query": CAU_HOI}, tai_lieu, llm, generate_model())

    van_ban = ra.get("van_ban_tong_quat")
    muc = (van_ban or {}).get("muc") or []
    khoi_ra = [_khoi(m) for m in muc]
    so_khoi = sum(len(k) for k in khoi_ra)
    so_bang_ra = sum(1 for k in khoi_ra for b in k if b.get("bang"))
    so_vung: dict[str, int] = {}
    for m in muc:
        v = m.get("vung") or "than"
        so_vung[v] = so_vung.get(v, 0) + 1
    # Chân trang có "sống sót" không — chép nguyên văn ở đâu đó trong văn bản
    # ra (mục văn xuôi hoặc một ô bảng), không cần đúng mục.
    chan_trang_song = None
    if chan_trang_chu:
        chu_ra = " ".join(
            b.get("noi_dung", "") or " ".join(o for hang in b.get("bang", []) for o in hang)
            for k in khoi_ra
            for b in k
        )
        chan_trang_song = chan_trang_chu.strip() in chu_ra

    print(f"\n== {duong_dan.name}")
    print(f"   muc_dich={ra.get('muc_dich_tai_lieu')}  chi_phi=${ra['traces'].get('hieu_tai_lieu_cost_usd', 0):.5f}")
    print(f"   don_vi_vao={len(tl.don_vi)}  bang_vao={so_bang_vao}  dau_trang_vao={so_dau_trang}  chan_trang_vao={so_chan_trang}")
    if van_ban is None:
        print(f"   KHÔNG soạn được văn bản nào (van_ban_tong_quat=None, muc_dich={ra.get('muc_dich_tai_lieu')})")
        return
    print(f"   muc_ra={len(muc)}  khoi_ra={so_khoi}  bang_ra={so_bang_ra}  vung_ra={so_vung}")
    if chan_trang_chu:
        print(f"   chan_trang_vao={chan_trang_chu!r}  song_sot={chan_trang_song}")


def main(argv: list[str]) -> None:
    corpus = Path.home() / "giấy tờ thực tập"
    ten_tep = argv or MAC_DINH
    for ten in ten_tep:
        duong_dan = corpus / ten
        if not duong_dan.exists():
            print(f"BỎ QUA {ten}: không thấy tại {duong_dan}")
            continue
        do_mot_tep(duong_dan)


if __name__ == "__main__":
    main(sys.argv[1:])
