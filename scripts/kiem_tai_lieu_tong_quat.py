"""Đo lượng mất mát khi `hieu_tai_lieu` dựng lại một biểu mẫu nguồn thành
`van_ban.muc` (Phase 8 R5, `.sdd/phase-8-brief.md`; Phase 11 R1, `.sdd/phase-11-brief.md`).

Hai phần, tách chi phí RÕ RÀNG:

1. `kiem_ti_le_doc()` — 0 token, THUẦN `doc_tai_lieu.doc()`. So tỉ lệ cột đo
   được BÂY GIỜ với một mốc đã ghim (đo trực tiếp từ `word/document.xml` khi
   viết Phase 11) cho CẢ SÁU form của kho mẫu — không chỉ BM.ĐT.18.05 brief
   nêu tên. Đây là phép kiểm THẤT BẠI ĐƯỢC nếu `doc_tai_lieu._ti_le_luoi`/
   `_nhip_o` hỏng ở một bản vá sau này — không cần gọi model, chạy được
   trong `pytest` (xem `tests/test_services/test_doc_tai_lieu.py`) LẪN chạy
   tay ở đây để xem báo cáo đầy đủ.

2. `do_mot_tep()` — gọi model THẬT qua OpenRouter (~0,001 USD/tệp). KHÔNG chạy
   trong CI, KHÔNG chạy tự động sau mỗi lần sửa (cùng lý do các tệp bị cấm
   chạy của backend gate). Báo cáo bảng VÀO (đọc thẳng, 0 token) đối chiếu
   bảng RA (sau khi model soạn + `_khop_bang` khớp lại) — bao gồm tỉ lệ cột
   RA có khớp với tỉ lệ cột VÀO của CHÍNH bảng đó không (một khớp SAI ti_le
   là dấu hiệu `_khop_bang` gán nhầm bảng, một lỗi thật). Số bảng RA giảm so
   với số bảng VÀO không tự nó là lỗi (model có thể bỏ sót một bảng, đã
   disclose từ Phase 8) — script chỉ CẢNH BÁO, không chặn — nhưng NẾU bảng RA
   có ti_le mà không khớp NGUYÊN VĂN một bảng VÀO, đó luôn luôn là lỗi và
   script THOÁT MÃ KHÁC 0.

3. `so_sanh_docx()` — 0 token, THUẦN OOXML (stdlib `xml.etree.ElementTree`,
   không `python-docx`). Phase 11 R8: so một `.docx` NGUỒN với một `.docx`
   KLAW ĐÃ XUẤT (tải từ trình duyệt) — số đoạn văn, số bảng, tỉ lệ cột từng
   bảng, phân bố căn lề (`w:jc`) và phân bố đậm (`w:b`), cạnh nhau. Đây chính
   là phép so đã bắt được cả năm điểm đo trong R8 (bảng biến mất, tỉ lệ cột
   giả `[100,100,100]`, "cả tệp căn đều") mà không cần đoán bằng mắt lần sau.

Chạy:

    PYTHONPATH="$PWD" .venv/bin/python scripts/kiem_tai_lieu_tong_quat.py            # phần 1+2
    PYTHONPATH="$PWD" .venv/bin/python scripts/kiem_tai_lieu_tong_quat.py --ti-le    # chỉ phần 1, 0 token
    PYTHONPATH="$PWD" .venv/bin/python scripts/kiem_tai_lieu_tong_quat.py --so-sanh nguon.docx xuat.docx

Đọc được CẢ HAI hình dạng `van_ban.muc[]` — `khoi` (Phase 8) và `noi_dung`/
`bang` (Phase 7 trở về trước, hàm `_khoi` dưới đây quy về cùng một dạng đếm
được) — nên CÙNG một script đo được cả "trước" lẫn "sau" bản vá, không phải
viết lại lần thứ hai.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
import zipfile
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

# Mốc ghim (Phase 11 R1) — đo TRỰC TIẾP `word/document.xml` từng tệp, 2026-09-17.
# `doc_tai_lieu.doc()` là hàm THUẦN nên giá trị này KHÔNG được đổi trừ khi bản
# thân tài liệu nguồn đổi — một bản vá sau làm lệch số này là một hồi quy thật.
TI_LE_MOC = {
    "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx": {
        0: (43, 57),
        1: (7, 19, 18, 25, 15, 15),
    },
    "BM.ĐT.18.03. Đơn đăng ký đi thực tập tốt nghiệp Ver 02.docx": {
        0: (45, 55),
        1: (34, 34, 32),
    },
    "BM.ĐT.18.05. Kế hoạch thực tập tại cơ sở Ver 02.docx": {
        0: (45, 55),
        1: (7, 15, 30, 34, 15),
        2: (47, 53),
    },
    "BM.ĐT.18.11. Phiếu đánh giá quá trình thực tập tốt nghiệp của sinh viên tại cơ sở thực tập Ver 02 (1).docx": {
        0: (6, 64, 15, 15),
        1: (50, 50),
    },
    "phiếu đánh giá thực tập công nghiệp.docx": {
        0: (6, 64, 15, 15),
        1: (50, 50),
    },
    "Evaluation Form.docx": {
        0: (14, 6, 11, 6, 20, 6, 9, 6, 14, 6),
        1: (14, 6, 11, 6, 20, 6, 9, 6, 14, 6),
        2: (14, 6, 11, 6, 20, 6, 9, 6, 14, 6),
        3: (14, 6, 11, 6, 20, 6, 9, 6, 14, 6),
        4: (14, 6, 11, 6, 20, 6, 9, 6, 14, 6),
        5: (14, 6, 11, 6, 20, 6, 9, 6, 14, 6),
        6: (14, 6, 11, 6, 20, 6, 9, 6, 14, 6),
        7: (14, 6, 11, 6, 20, 6, 9, 6, 14, 6),
        8: (14, 6, 11, 6, 20, 6, 9, 6, 14, 6),
        9: (17, 7, 13, 7, 21, 7, 20, 7),
    },
}

CAU_HOI = (
    "Hãy dựng lại nguyên văn biểu mẫu này thành một văn bản đầy đủ mọi mục, "
    "mọi trường, mọi bảng, đầu trang và chân trang của nó."
)


def _ti_le_vao(tl: doc_tai_lieu.TaiLieuDaDoc) -> dict[int, tuple[int, ...]]:
    ra: dict[int, tuple[int, ...]] = {}
    for d in tl.don_vi:
        if d.bang is not None:
            ra.setdefault(d.bang[0], d.bang_ti_le)
    return ra


def kiem_ti_le_doc(ten_tep: list[str]) -> bool:
    """Phần 1 — 0 token. Trả `True` khi mọi tệp khớp mốc đã ghim."""
    corpus = Path.home() / "giấy tờ thực tập"
    dat = True
    for ten in ten_tep:
        duong_dan = corpus / ten
        if not duong_dan.exists():
            print(f"BỎ QUA {ten}: không thấy tại {duong_dan}")
            continue
        tl = doc_tai_lieu.doc(duong_dan.name, duong_dan.read_bytes())
        vao = _ti_le_vao(tl)
        moc = TI_LE_MOC.get(ten, {})
        print(f"\n== {ten} (tỉ lệ cột, 0 token)")
        for b in sorted(set(vao) | set(moc)):
            khop = vao.get(b) == moc.get(b)
            dat &= khop
            danh_dau = "✓" if khop else "✗ HỒI QUY"
            print(f"   bảng {b}: đo được {vao.get(b)}  mốc {moc.get(b)}  {danh_dau}")
    return dat


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


def do_mot_tep(duong_dan: Path) -> bool:
    """Phần 2 — gọi model thật. Trả `False` khi một bảng RA mang `ti_le`
    không khớp NGUYÊN VĂN bảng VÀO nào (dấu hiệu `_khop_bang` gán nhầm bảng)."""
    du_lieu = duong_dan.read_bytes()
    tl = doc_tai_lieu.doc(duong_dan.name, du_lieu)
    ti_le_vao = _ti_le_vao(tl)
    so_bang_vao = len(ti_le_vao)
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
    bang_ra = [k for kk in khoi_ra for k in kk if k.get("bang")]
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
        return True
    print(f"   muc_ra={len(muc)}  khoi_ra={so_khoi}  bang_ra={len(bang_ra)}  vung_ra={so_vung}")
    if chan_trang_chu:
        print(f"   chan_trang_vao={chan_trang_chu!r}  song_sot={chan_trang_song}")
    if so_bang_vao and len(bang_ra) < so_bang_vao:
        print(f"   CẢNH BÁO: {so_bang_vao} bảng vào, chỉ {len(bang_ra)} bảng ra (model có thể bỏ sót — không chặn)")

    # Tỉ lệ cột RA (Phase 11 R1) — mỗi bảng RA mang `ti_le` phải khớp NGUYÊN
    # VĂN tỉ lệ của MỘT bảng VÀO nào đó (bảng thật đã được `_khop_bang` thay
    # vào) — khớp SAI là dấu hiệu gán nhầm bảng, LUÔN LÀ LỖI, không phải
    # "model có thể bỏ sót" như số lượng ở trên.
    dat = True
    cac_ti_le_vao = set(ti_le_vao.values())
    for i, b in enumerate(bang_ra):
        ti_le = tuple(b.get("ti_le") or ())
        if not ti_le:
            continue  # bảng không khớp lưới nguồn nào (model tự soạn) — không có gì để đối chiếu
        khop = ti_le in cac_ti_le_vao
        dat &= khop
        danh_dau = "✓" if khop else "✗ GÁN NHẦM BẢNG"
        print(f"   bảng ra #{i}: ti_le={ti_le}  {danh_dau}")
    return dat


# ─────────────────────────── Phase 11 R8 — so nguồn với tệp KLAW đã xuất ────
#
# Thuần OOXML, `xml.etree.ElementTree` (như `doc_tai_lieu.py`) — không
# `python-docx`, không mở tệp qua Word. Đọc trực tiếp `word/document.xml`.

_NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _doc_xml(duong_dan: Path) -> ET.Element:
    with zipfile.ZipFile(duong_dan) as z:
        return ET.fromstring(z.read("word/document.xml"))


def _chu_chay(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.iter(f"{_NS_W}t"))


def _dam(p: ET.Element) -> bool | None:
    """Đoạn này có chạy nào IN ĐẬM không — `None` khi đoạn không có chữ (đầu
    mục/dòng trống), để không tính lẫn vào phân bố. `<w:b w:val="false"/>`
    KHÔNG phải đậm — đây chính là chỗ một phép đếm ẩu (chỉ xem `<w:b` có mặt
    hay không) từng báo nhầm "mọi đoạn đều đậm" trong khi giá trị THẬT nói
    ngược lại (R8's bold-defect measurement, không tái hiện được trên mã hiện
    tại khi soát lại đúng thuộc tính `w:val`)."""
    if not _chu_chay(p).strip():
        return None
    for r in p.iter(f"{_NS_W}r"):
        b = r.find(f"{_NS_W}rPr/{_NS_W}b")
        if b is not None and b.get(f"{_NS_W}val") not in ("0", "false"):
            return True
    return False


def _can_le(p: ET.Element) -> str | None:
    jc = p.find(f"{_NS_W}pPr/{_NS_W}jc")
    return jc.get(f"{_NS_W}val") if jc is not None else None


def _bao_cao_mot_tep(duong_dan: Path) -> dict:
    goc = _doc_xml(duong_dan)
    than = goc.find(f"{_NS_W}body")
    doan = [c for c in than if c.tag == f"{_NS_W}p"]
    bang = [c for c in than if c.tag == f"{_NS_W}tbl"]
    ti_le: list[tuple[int, ...]] = []
    for tbl in bang:
        grid = tbl.find(f"{_NS_W}tblGrid")
        rong = (
            [int(v) for g in grid.findall(f"{_NS_W}gridCol") if (v := g.get(f"{_NS_W}w"))]
            if grid is not None
            else []
        )
        tong = sum(rong)
        ti_le.append(tuple(round(w * 100 / tong) for w in rong) if tong else ())
    can_le = [c for p in doan if (c := _can_le(p)) is not None or _chu_chay(p).strip()]
    can_le_dem: dict[str, int] = {}
    for c in can_le:
        khoa = c or "(vắng — thừa kế)"
        can_le_dem[khoa] = can_le_dem.get(khoa, 0) + 1
    dam_dem = {"dam": 0, "khong_dam": 0}
    for p in doan:
        d = _dam(p)
        if d is True:
            dam_dem["dam"] += 1
        elif d is False:
            dam_dem["khong_dam"] += 1
    return {
        "so_doan": len(doan),
        "so_bang": len(bang),
        "ti_le": ti_le,
        "can_le": can_le_dem,
        "dam": dam_dem,
    }


def so_sanh_docx(nguon: Path, xuat: Path) -> None:
    a, b = _bao_cao_mot_tep(nguon), _bao_cao_mot_tep(xuat)
    print(f"\n== So sánh {nguon.name}  vs  {xuat.name}")
    print(f"   đoạn văn:  nguồn={a['so_doan']}  xuất={b['so_doan']}")
    print(f"   bảng:      nguồn={a['so_bang']}  xuất={b['so_bang']}")
    print("   tỉ lệ cột (từng bảng, theo thứ tự):")
    print(f"      nguồn: {a['ti_le']}")
    print(f"      xuất:  {b['ti_le']}")
    print(f"   căn lề:    nguồn={a['can_le']}  xuất={b['can_le']}")
    print(f"   đậm:       nguồn={a['dam']}  xuất={b['dam']}")


def main(argv: list[str]) -> None:
    if "--so-sanh" in argv:
        i = argv.index("--so-sanh")
        so_sanh_docx(Path(argv[i + 1]), Path(argv[i + 2]))
        return

    chi_ti_le = "--ti-le" in argv
    ten_tep = [a for a in argv if not a.startswith("--")] or MAC_DINH

    dat = kiem_ti_le_doc(ten_tep)
    if not chi_ti_le:
        corpus = Path.home() / "giấy tờ thực tập"
        for ten in ten_tep:
            duong_dan = corpus / ten
            if not duong_dan.exists():
                print(f"BỎ QUA {ten}: không thấy tại {duong_dan}")
                continue
            dat &= do_mot_tep(duong_dan)

    if not dat:
        print("\nTHẤT BẠI — có hồi quy hoặc gán nhầm bảng, xem ✗ ở trên.")
        sys.exit(1)
    print("\nĐẠT — không hồi quy, không gán nhầm bảng.")


if __name__ == "__main__":
    main(sys.argv[1:])
