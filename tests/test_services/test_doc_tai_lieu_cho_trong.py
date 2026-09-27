"""Địa chỉ OOXML và chỗ trống của từng đơn vị DOCX — kế hoạch
`docs/plans/completed/khuon-goc-dien-tai-cho.md`, hợp đồng "Đơn vị văn bản
additions" (P2b).

Bộ áp phép sửa (P3a) sẽ đi THẲNG tới `dia_chi` trên bytes khuôn gốc đã lưu, và
thay đúng các ký tự `[dau:cuoi]` của một chỗ trống. Nên mọi con số ở đây phải
đúng trên part XML THÔ như nằm trong tệp — không phải trên cây bộ đọc đã bỏ
`mc:Fallback`. Năm điều file này khoá:

1. `chi_muc` đếm MỌI con phần tử ở từng cấp (`w:tblPr`, `w:tblGrid`, `w:trPr`
   cũng được đếm), từ `w:body` (hoặc gốc `w:hdr`/`w:ftr`) xuống vật chứa.
2. `doan` và `dau`/`cuoi` đo trên thứ tự THÔ: một hộp chữ có `mc:Fallback`
   đứng trước làm lệch mọi chỉ số nếu đo trên cây đã gỡ.
3. Chỗ trống `cham` là dãy `.`/`…` mà `RE_CHO_DIEN` (định nghĩa dùng chung với
   `hieu_tai_lieu.vung_trong`) nhận; `tab` là `w:tab` rơi vào mốc có đường dẫn
   `dot` khai TRỰC TIẾP ở đoạn.
4. Fail closed: đường lùi duyệt phẳng của thân bài, đoạn chứa hộp chữ và mọi
   thứ trong `mc:AlternateContent` không có chỗ trống (thân bài lùi thì không
   có cả `dia_chi`).
5. `noi_dung`, `chi_so`, neo và bộ đếm `lam_sach_van_ban` không đổi một byte.
"""

import time
import zipfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest

from src.agents.nodes.hieu_tai_lieu import lam_sach_van_ban, vung_trong
from src.services.doc_tai_lieu import ChoTrong, DiaChi, DonViVanBan, doc, nhan_sach
from src.services.neo_du_kien import LyDoNeo, normalize, xac_minh
from src.services.tai_lieu import _cho_trong_tu_hang, _dia_chi_tu_hang, _hang_don_vi, _hop_tu_hang

_NSW = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NSMC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_KHAI_NS = f'xmlns:w="{_NSW}" xmlns:mc="{_NSMC}" xmlns:wps="urn:wps" xmlns:v="urn:v"'
_DOC = f'<?xml version="1.0" encoding="UTF-8"?><w:document {_KHAI_NS}><w:body>{{than}}</w:body></w:document>'


def _docx(than: str, phan: dict[str, str] | None = None) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", _DOC.format(than=than))
        for ten, xml in (phan or {}).items():
            z.writestr(ten, xml)
    return buf.getvalue()


def _r(chu: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{chu}</w:t></w:r>'


def _p(*run: str, ppr: str = "") -> str:
    return f"<w:p>{ppr}{''.join(run)}</w:p>"


_KHO_MAU = Path.home() / "giấy tờ thực tập"
_TAB = "<w:r><w:tab/></w:r>"
_MOC_CHAM = '<w:pPr><w:tabs><w:tab w:val="right" w:pos="9000" w:leader="dot"/></w:tabs></w:pPr>'


def _hop_chu(chu: str) -> str:
    """Một run chứa hộp chữ HAI lần — `Choice` cho Word mới, `Fallback` cho Word
    cũ — đúng hình dạng của BM.ĐT.18.05 ("Phụ lục 4Phụ lục 4" trên cây thô)."""
    return (
        "<w:r><mc:AlternateContent>"
        f'<mc:Choice Requires="wps"><w:drawing><wps:txbx><w:txbxContent>{_p(_r(chu))}'
        "</w:txbxContent></wps:txbx></w:drawing></mc:Choice>"
        f"<mc:Fallback><w:pict><v:textbox><w:txbxContent>{_p(_r(chu))}"
        "</w:txbxContent></v:textbox></w:pict></mc:Fallback>"
        "</mc:AlternateContent></w:r>"
    )


def _mot(than: str, phan: dict[str, str] | None = None) -> list[DonViVanBan]:
    return doc("x.docx", _docx(than, phan)).don_vi


def _theo_chu(don_vi: list[DonViVanBan], dau: str) -> DonViVanBan:
    return next(d for d in don_vi if d.noi_dung.startswith(dau))


# ───────────────────────────────────────────────────────────── dia_chi


def test_doan_than_bai_co_dia_chi_la_chi_so_con_cua_w_body():
    """Chỉ số đếm MỌI con của `w:body`, kể cả thứ bộ đọc không lấy chữ
    (`w:bookmarkStart` đứng trước) và đoạn rỗng không đẻ ra đơn vị."""
    than = '<w:bookmarkStart w:id="0" w:name="a"/>' + _p() + _p(_r("Họ tên: ……"))
    d = _theo_chu(_mot(than), "Họ tên")
    assert d.dia_chi == DiaChi(phan="word/document.xml", chi_muc=(2,))


def test_o_bang_co_dia_chi_dem_ca_tblPr_tblGrid_trPr_tcPr():
    o = "<w:tc><w:tcPr/>" + _p(_r("Số: ……")) + "</w:tc>"
    bang = (
        "<w:tbl><w:tblPr/><w:tblGrid/>"
        f"<w:tr>{'<w:tc>' + _p(_r('A')) + '</w:tc>'}</w:tr>"
        f"<w:tr><w:trPr/>{'<w:tc>' + _p(_r('B')) + '</w:tc>'}{o}</w:tr>"
        "</w:tbl>"
    )
    d = _theo_chu(_mot(_p(_r("Tiêu đề")) + bang), "Số")
    assert d.bang == (0, 1, 1)
    assert d.dia_chi == DiaChi(phan="word/document.xml", chi_muc=(1, 3, 2))


def test_dau_trang_co_dia_chi_tu_goc_w_hdr_ke_ca_doan_trong_bang():
    hdr = (
        f'<?xml version="1.0"?><w:hdr {_KHAI_NS}>{_p(_r("Mẫu số: ……"))}'
        f"<w:tbl><w:tblPr/><w:tr><w:tc>{_p(_r('Số hiệu: ……'))}</w:tc></w:tr></w:tbl></w:hdr>"
    )
    don_vi = _mot(_p(_r("Thân")), {"word/header1.xml": hdr})
    assert _theo_chu(don_vi, "Mẫu số").dia_chi == DiaChi("word/header1.xml", (0,))
    d = _theo_chu(don_vi, "Số hiệu")
    assert d.dia_chi == DiaChi("word/header1.xml", (1, 1, 0, 0))
    assert [(c.kieu, c.doan) for c in d.cho_trong] == [("cham", 0)]


def test_doan_trong_hop_chu_o_dau_trang_KHONG_co_dia_chi():
    """Duyệt phẳng đầu trang đi vào cả hộp chữ; đoạn trong đó không có địa chỉ
    đáng tin (hai bản Choice/Fallback), nên fail closed."""
    hdr = f'<?xml version="1.0"?><w:hdr {_KHAI_NS}>{_p(_r("Nhãn"), _hop_chu("Trong hộp: ……"))}</w:hdr>'
    don_vi = _mot(_p(_r("Thân")), {"word/header1.xml": hdr})
    assert [d.dia_chi for d in don_vi if d.noi_dung.startswith("Trong hộp")] == [None, None]
    ngoai = _theo_chu(don_vi, "Nhãn")
    assert ngoai.dia_chi == DiaChi("word/header1.xml", (0,))
    assert ngoai.cho_trong == ()


def test_than_bai_LUI_VE_duyet_phang_thi_KHONG_co_dia_chi_hay_cho_trong():
    """Chữ nằm trong `w:sdt` cấp thân: cấu trúc đọc ít chữ hơn → lùi về duyệt
    phẳng, nơi không còn chỉ số con nào đáng tin."""
    than = f"<w:sdt><w:sdtContent>{_p(_r('Họ tên: ………… và rất nhiều chữ nữa ở đây'))}</w:sdtContent></w:sdt>"
    than += _p(_r("Ngắn: ……"))
    don_vi = _mot(than)
    assert len(don_vi) == 2
    assert all(d.dia_chi is None and d.cho_trong == () for d in don_vi)


# ─────────────────────────────────────────────────────────── cho_trong


def test_nhieu_cho_trong_mot_doan_offset_tren_chuoi_THO_truoc_strip():
    """`dau`/`cuoi` đo trên chuỗi `w:t` nối THÔ — khoảng trắng đầu dòng vẫn
    được đếm, dù `noi_dung` đã cắt nó."""
    d = _theo_chu(_mot(_p(_r("  Điện thoại: ………. Fax: …………"))), "Điện thoại")
    tho = "  Điện thoại: ………. Fax: …………"
    assert d.noi_dung == tho.strip()
    assert [(c.so, c.kieu, c.doan, c.nhan) for c in d.cho_trong] == [
        (0, "cham", 0, "Điện thoại"),
        (1, "cham", 0, "Fax"),
    ]
    assert [tho[c.dau : c.cuoi] for c in d.cho_trong] == ["……….", "…………"]


def test_cho_trong_VAT_qua_nhieu_run_la_MOT_cho():
    run = ["Địa chỉ: ……", "…", "….."]
    d = _theo_chu(_mot(_p(*map(_r, run))), "Địa chỉ")
    assert [(c.dau, c.cuoi) for c in d.cho_trong] == [(len("Địa chỉ: "), len("".join(run)))]


@pytest.mark.parametrize(
    "doan",
    [
        _p(_r("Tên: ……"), "<w:r><w:tab/></w:r>", _r("……")),
        _p(_r("Tên: ……"), "<w:r><w:br/></w:r>", _r("……")),
        _p(_r("Tên: ……"), "<w:r><w:cr/></w:r>", _r("……")),
        _p("<w:r><w:t>Tên: ……</w:t><w:tab/><w:t>……</w:t></w:r>"),
    ],
    ids=["tab", "br", "cr", "cung_run"],
)
def test_day_cham_bi_TAB_hoac_NGAT_DONG_chen_giua_la_HAI_cho_trong(doan):
    """`w:tab`/`w:br` không góp ký tự nào vào chuỗi `w:t` thô, nên "……<tab>……"
    nối ra MỘT dãy chấm liền. Điền dãy ấy là xoá chấm vắt qua tab hay ngắt dòng
    (P2b review) — mỗi phía của chỗ ngắt là một chỗ trống riêng."""
    d = _theo_chu(_mot(doan), "Tên")
    dau = len("Tên: ")
    assert [(c.kieu, c.dau, c.cuoi) for c in d.cho_trong] == [("cham", dau, dau + 2), ("cham", dau + 2, dau + 4)]


def test_manh_cham_con_lai_sau_khi_cat_QUA_NGAN_thi_KHONG_la_cho_trong():
    d = _theo_chu(_mot(_p(_r("Số: .."), _TAB, _r("...."))), "Số")
    dau = len("Số: ..")
    assert [(c.kieu, c.dau, c.cuoi) for c in d.cho_trong] == [("cham", dau, dau + 4)]


def test_ngay_thang_nam_moi_dau_lung_la_mot_cho_trong_so_nghin_thi_KHONG():
    d = _theo_chu(_mot(_p(_r("Lương 20.000.000 đồng, ngày … tháng … năm …… hết."))), "Lương")
    assert [c.nhan for c in d.cho_trong] == ["Lương 20.000.000 đồng, ngày", "tháng", "năm"]


def test_moi_cho_trong_cham_deu_la_vung_trong_theo_dinh_nghia_dung_chung():
    """Hai nơi cùng nói "chỗ này để điền": bộ đọc và `vung_trong`. Chúng phải
    đồng ý — một chỗ trống bộ đọc ghi nhận mà `vung_trong` coi là giá trị thật
    thì mô hình sẽ chép dãy chấm vào bảng dữ kiện."""
    tho = "Số …./…. ngày ... tháng .. năm 2026, mã 1.2.3"
    d = _theo_chu(_mot(_p(_r(tho))), "Số")
    assert [tho[c.dau : c.cuoi] for c in d.cho_trong] == ["….", "….", "..."]
    assert all(vung_trong(tho[c.dau : c.cuoi]) for c in d.cho_trong)


def test_tab_co_moc_dan_cham_TRUC_TIEP_la_cho_trong_tab():
    tho = "Company name:"
    d = _theo_chu(_mot(_p(_r(tho), _TAB, _r(" "), ppr=_MOC_CHAM)), "Company")
    assert [(c.kieu, c.dau, c.cuoi, c.nhan) for c in d.cho_trong] == [("tab", 13, 13, "Company name")]


def test_tab_KHONG_dan_cham_hoac_moc_tu_KIEU_thi_khong_phai_cho_trong():
    """Mốc thừa kế từ `w:pStyle` là trần có ghi: chỉ đọc mốc khai trực tiếp."""
    khong_dan = '<w:pPr><w:tabs><w:tab w:val="left" w:pos="3000"/></w:tabs></w:pPr>'
    theo_kieu = '<w:pPr><w:pStyle w:val="Dien"/></w:pPr>'
    styles = (
        f'<?xml version="1.0"?><w:styles {_KHAI_NS}><w:style w:styleId="Dien"><w:pPr><w:tabs>'
        '<w:tab w:val="right" w:pos="9000" w:leader="dot"/></w:tabs></w:pPr></w:style></w:styles>'
    )
    don_vi = _mot(
        _p(_r("Tên:"), _TAB, ppr=khong_dan) + _p(_r("Lớp:"), _TAB, ppr=theo_kieu),
        {"word/styles.xml": styles},
    )
    assert [d.cho_trong for d in don_vi] == [(), ()]


def test_tab_thu_n_di_toi_moc_thu_n_chi_moc_dan_cham_la_cho_trong():
    moc = (
        '<w:pPr><w:tabs><w:tab w:val="left" w:pos="2000"/>'
        '<w:tab w:val="right" w:pos="9000" w:leader="dot"/></w:tabs></w:pPr>'
    )
    d = _theo_chu(_mot(_p(_r("STT"), _TAB, _r("Họ tên"), _TAB, ppr=moc)), "STT")
    # `w:tab` không góp ký tự vào chuỗi thô, nhưng trong NHÃN nó là một chỗ ngắt.
    assert [(c.kieu, c.dau, c.nhan) for c in d.cho_trong] == [("tab", len("STTHọ tên"), "STT Họ tên")]


def test_o_bang_nhieu_doan_doan_la_chi_so_THO_ke_ca_hop_chu_co_fallback():
    """Đoạn 0 của ô chứa hộp chữ (Choice + Fallback). Trên cây THÔ `tc.iter(w:p)`
    là [p0, p-choice, p-fallback, p1] nên chỗ trống của p1 là `doan` 3 — trên
    cây đã gỡ Fallback nó sẽ là 2, và bộ áp sẽ sửa nhầm đoạn."""
    o = "<w:tc>" + _p(_r("Tiêu đề"), _hop_chu("Hộp: ……")) + _p(_r("Số: ………")) + "</w:tc>"
    d = _theo_chu(_mot(f"<w:tbl><w:tr>{o}</w:tr></w:tbl>"), "Tiêu đề")
    assert [(c.doan, c.dau, c.cuoi, c.nhan) for c in d.cho_trong] == [(3, len("Số: "), len("Số: ………"), "Số")]


def test_doan_than_bai_chua_hop_chu_co_dia_chi_nhung_KHONG_co_cho_trong():
    d = _theo_chu(_mot(_p(_r("Phụ lục 4"), _hop_chu("Điền: ……"))), "Phụ lục")
    assert d.dia_chi == DiaChi("word/document.xml", (0,))
    assert d.cho_trong == ()


def test_so_danh_lien_tuc_qua_cac_doan_cua_mot_o():
    o = "<w:tc>" + _p(_r("Họ: ……")) + _p(_r("Tên: ……"), _TAB, ppr=_MOC_CHAM) + "</w:tc>"
    d = _theo_chu(_mot(f"<w:tbl><w:tr>{o}</w:tr></w:tbl>"), "Họ")
    assert [(c.so, c.kieu, c.doan) for c in d.cho_trong] == [(0, "cham", 0), (1, "cham", 1), (2, "tab", 1)]


def test_nhan_la_DUOI_60_ky_tu_bo_tu_bi_cat_do():
    """Nhãn là 60 ký tự CUỐI trước chỗ trống (sát chỗ trống mới là nhãn), rồi
    `nhan_sach`: cắt giữa một từ thì bỏ mẩu từ đó, bỏ dấu `:` cuối."""
    dai = "x" * 70 + " Họ và tên người đại diện:"
    d = _theo_chu(_mot(_p(_r(dai + " ……"))), "xxx")
    assert d.cho_trong[0].nhan == "Họ và tên người đại diện"


# Nhãn thô của BM.M05 đúng như bộ đọc cắt ra (60 ký tự cuối, đo 2026-09-27 trên
# tệp của chủ dự án) → nhãn hiển thị. `truoc`: nhãn SẠCH của chỗ trống liền trước.
@pytest.mark.parametrize(
    ("tho", "truoc", "sach"),
    [
        ("Cơ quan/Đơn vị tiếp nhận:", "", "Cơ quan/Đơn vị tiếp nhận"),
        ("o) là sinh viên/học viên Trường Đại học Phenikaa, thuộc Khoa", "Fax", "thuộc Khoa"),
        ("Số", "", "Số"),
        ("/", "Số", "Số (sau /)"),
        ("/20", "Thời gian thực tập: từ ngày (sau /)", "Thời gian thực tập: từ ngày (sau /20)"),
        ("=", "", ""),
        ("Thời gian: từ ngày", "", "Thời gian: từ ngày"),
        ("tháng", "Thời gian: từ ngày", "tháng"),
        ("năm", "tháng", "năm"),
        (", ngày", "năm", "ngày"),
        ("(Kèm theo Giấy tiếp nhận thực hành/thực tập số", "", "Kèm theo Giấy tiếp nhận thực hành/thực tập số"),
        ("What are his/her contributions (đóng góp đó là gì)?:", "", "đóng góp đó là gì"),
        ("gì, hoàn thành mục tiêu gì, sẽ tiếp tục thực hiện nhưng gì?", "", "sẽ tiếp tục thực hiện nhưng gì?"),
        (
            "DANH SÁCH SINH VIÊN/HỌC VIÊN THỰC HÀNH/THỰC TẬP TẠI",
            "",
            "DANH SÁCH SINH VIÊN/HỌC VIÊN THỰC HÀNH/THỰC TẬP TẠI",
        ),
        ("  Họ   và tên:  ", "", "Họ và tên"),
        ("x" * 58 + ": 1", "", "x" * 58),  # cắt 60 ký tự mà mẩu có chữ không có dấu cách
        ("", "Số", ""),
        # Chú thích ngoặc CUỐI nhãn dài ("(nếu có)", "(ghi rõ …)") không phải tên ô.
        ("Họ và tên người đại diện theo pháp luật (nếu có):", "", "Họ và tên người đại diện theo pháp luật"),
        ("Số điện thoại liên hệ của người hướng dẫn (nếu có)", "", "Số điện thoại liên hệ của người hướng dẫn"),
        ("Địa chỉ nơi ở hiện tại (ghi rõ số nhà, đường, phường):", "", "Địa chỉ nơi ở hiện tại"),
        ("Người đại diện (ký, ghi rõ họ tên và đóng dấu)", "", "Người đại diện"),
        ("Họ tên (nếu có):", "", "Họ tên (nếu có)"),  # nhãn ngắn giữ nguyên
        # 60 ký tự cuối cắt "của" còn "a", rồi chú thích ngoặc: bỏ cả hai.
        ("a người hướng dẫn tại cơ sở (ký, ghi rõ họ tên và đóng dấu):", "", "người hướng dẫn tại cơ sở"),
        ("(ghi rõ số nhà, đường, phường, quận, thành phố nơi cư trú):", "", "thành phố nơi cư trú"),
    ],
)
def test_nhan_sach(tho, truoc, sach):
    assert nhan_sach(tho, truoc) == sach
    assert nhan_sach(sach, truoc) == sach, "lũy đẳng: nhãn đã lưu sạch đọc lại không đổi"


@pytest.mark.skipif(not (_KHO_MAU / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx").exists(), reason="kho mẫu")
def test_nhan_that_cua_BM_M05_da_sach_ngay_luc_doc():
    tep = _KHO_MAU / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx"
    nhan = {(d.chi_so, c.so): c.nhan for d in doc(tep.name, tep.read_bytes()).don_vi for c in d.cho_trong}
    assert [nhan[3, 0], nhan[3, 1], nhan[6, 0], nhan[9, 0], nhan[14, 0]] == [
        "Số",
        "Số (sau /)",
        "Cơ quan/Đơn vị tiếp nhận",
        "thuộc Khoa",
        "ngày",
    ]
    assert [nhan[13, i] for i in range(6)] == ["Thời gian: từ ngày", "tháng", "năm", "đến ngày", "tháng", "năm"]
    assert [nhan[20, i] for i in range(3)] == ["Thời gian: từ", "Thời gian: từ (sau /)", "Thời gian: từ (sau /)"]


# ─────────────────────────────────────────── chi phí tuyến tính theo tệp
# Bộ đọc chạy trên MỌI tệp tải lên, trong threadpool, không hạn giờ. Vài KB
# lồng sâu hay lặp dày mà tốn bậc hai là giữ một worker hàng giờ (đo 2026-09-26:
# 32.000 tầng `mc:AlternateContent` mất 30 s trước khi sửa, 0,03 s trên main).


def _giay(than: str, phan: dict[str, str] | None = None) -> tuple[float, list[DonViVanBan]]:
    du_lieu = _docx(than, phan)
    t = time.perf_counter()
    don_vi = doc("x.docx", du_lieu).don_vi
    return time.perf_counter() - t, don_vi


def test_mc_AlternateContent_LONG_SAU_doc_trong_thoi_gian_tuyen_tinh():
    n = 16_000
    ac = '<mc:AlternateContent><mc:Choice Requires="wps">' * n + "</mc:Choice></mc:AlternateContent>" * n
    giay, don_vi = _giay(_p(_r("Họ tên: ……"), f"<w:r>{ac}</w:r>"))
    assert giay < 2, giay
    d = _theo_chu(don_vi, "Họ tên")
    assert d.dia_chi == DiaChi("word/document.xml", (0,))
    assert d.cho_trong == (), "đoạn chứa mc:AlternateContent vẫn fail closed"


def test_dau_trang_LONG_SAU_khong_co_dia_chi_va_doc_nhanh():
    """`chi_muc` dài đúng bằng độ sâu: 32.000 tầng `w:sdt` là 32.000 số lưu vào
    DB cho MỘT đơn vị và một lần chép đường mỗi tầng. Sâu quá trần thì không có
    địa chỉ (fail closed); nông thì như cũ."""
    n = 32_000
    sdt = "<w:sdt><w:sdtContent>{}</w:sdtContent></w:sdt>"
    hdr = (
        f'<?xml version="1.0"?><w:hdr {_KHAI_NS}>{sdt.format(_p(_r("Nông: ……")))}'
        + "<w:sdt><w:sdtContent>" * n
        + _p(_r("Sâu: ……"))
        + "</w:sdtContent></w:sdt>" * n
        + "</w:hdr>"
    )
    giay, don_vi = _giay(_p(_r("Thân")), {"word/header1.xml": hdr})
    assert giay < 2, giay
    nong = _theo_chu(don_vi, "Nông")
    assert nong.dia_chi == DiaChi("word/header1.xml", (0, 0, 0)) and len(nong.cho_trong) == 1
    sau = _theo_chu(don_vi, "Sâu")
    assert sau.dia_chi is None and sau.cho_trong == ()


def test_doan_NHIEU_cho_trong_va_tab_doc_trong_thoi_gian_tuyen_tinh():
    n = 30_000
    giay, don_vi = _giay(_p(*["<w:r><w:t>a…</w:t><w:tab/></w:r>"] * n))
    assert giay < 2, giay
    (d,) = don_vi
    assert len(d.cho_trong) == n
    assert d.cho_trong[1].nhan == "a"


# ───────────────────────────────────────────────── bất biến neo trích dẫn


_THAN_MAU = (
    _p(_r("Mức lương: 20.000.000 đồng/tháng, ngày … tháng … năm ……"))
    + _p(_r("Company name:"), _TAB, ppr=_MOC_CHAM)
    + f"<w:tbl><w:tblPr/><w:tr><w:tc>{_p(_r('Số: ……'))}</w:tc><w:tc>{_p(_r('Thưởng 5.000.000 đồng'))}</w:tc></w:tr></w:tbl>"
)


def test_NOI_DUNG_NEO_va_LAM_SACH_y_HET_khi_bo_truong_moi():
    """Cùng phép đo `test_doc_tai_lieu_trang` dùng cho ngắt trang: hai trường
    mới đi CẠNH chuỗi, không chạm nó — gỡ chúng ra thì mọi thứ phía sau neo
    trích dẫn cho đúng kết quả cũ, kể cả bộ đếm."""
    co = _mot(_THAN_MAU)
    assert any(d.dia_chi for d in co) and any(d.cho_trong for d in co) and any(d.doan_chu for d in co)
    khong = [replace(d, dia_chi=None, cho_trong=(), hop=None, doan_chu=()) for d in co]

    assert [d.noi_dung for d in co] == [d.noi_dung for d in khong]
    assert [normalize(d.noi_dung) for d in co] == [normalize(d.noi_dung) for d in khong]
    assert [d.chi_so for d in co] == [d.chi_so for d in khong]

    for trich in ("Thưởng 5.000.000 đồng", "Mức lương: 20.000.000 đồng/tháng"):
        a, b = xac_minh(trich, co), xac_minh(trich, khong)
        assert a.ly_do is b.ly_do is LyDoNeo.ok
        assert (a.chi_so_don_vi, a.trang, a.offset_dau) == (b.chi_so_don_vi, b.trang, b.offset_dau)

    van_ban = {"muc": [{"ten": "Lương", "khoi": [{"noi_dung": "Mức lương: 20.000.000 đồng/tháng"}]}]}
    nguon = " ".join(d.noi_dung for d in co)
    ra_co, dem_co = lam_sach_van_ban(van_ban, nguon, [{"nhan": "A", "don_vi": co}])
    ra_khong, dem_khong = lam_sach_van_ban(van_ban, nguon, [{"nhan": "A", "don_vi": khong}])
    assert dem_co == dem_khong
    assert ra_co == ra_khong


# ─────────────────────────────── ô trống của bảng dữ liệu (`kieu` "o", G5)
# Bảng danh sách của BM.M05 trang 2: hàng tiêu đề có chữ, các hàng dưới là ô RỖNG
# — không dãy chấm nào. Mỗi ô rỗng của một bảng CÓ VIỀN, dưới một cột có tên, là
# một chỗ trống `o`: điền vào đoạn đầu của ô, không có offset nào để trỏ.

_VIEN = '<w:tblPr><w:tblBorders><w:insideH w:val="single" w:sz="4"/></w:tblBorders></w:tblPr>'


def _tc(chu: str = "", tcpr: str = "", noi: str = "") -> str:
    return f"<w:tc>{tcpr}{_p(_r(chu)) if chu else _p(noi)}</w:tc>"


def _bang(*hang: list[str], tblpr: str = _VIEN) -> str:
    return f"<w:tbl>{tblpr}" + "".join(f"<w:tr>{''.join(h)}</w:tr>" for h in hang) + "</w:tbl>"


def _o(don_vi: list[DonViVanBan]) -> list[tuple[tuple[int, int, int], str, int, int, int]]:
    return [(d.bang, c.nhan, c.doan, c.dau, c.cuoi) for d in don_vi for c in d.cho_trong if c.kieu == "o"]


def test_o_rong_cua_bang_co_vien_duoi_cot_co_ten_la_cho_trong_o():
    bang = _bang(
        [_tc("STT"), _tc("Mã sinh viên/ học viên"), _tc("Họ và tên")],
        [_tc(), _tc(), _tc()],
        [_tc("2"), _tc(), _tc("Đã có tên")],
    )
    don_vi = _mot(_p(_r("DANH SÁCH")) + bang)
    assert _o(don_vi) == [
        ((0, 1, 0), "STT (dòng 1)", 0, 0, 0),
        ((0, 1, 1), "Mã sinh viên/ học viên (dòng 1)", 0, 0, 0),
        ((0, 1, 2), "Họ và tên (dòng 1)", 0, 0, 0),
        ((0, 2, 1), "Mã sinh viên/ học viên (dòng 2)", 0, 0, 0),
    ]
    o = next(d for d in don_vi if d.bang == (0, 1, 2))
    assert (o.noi_dung, o.doan_chu, o.dia_chi) == ("", ("",), DiaChi("word/document.xml", (1, 2, 2)))
    assert [c.so for c in o.cho_trong] == [0]


def test_bang_KHONG_vien_o_khong_ten_cot_hang_tieu_de_va_o_khong_an_toan_KHONG_co_cho_trong_o():
    """Bảng không viền là bảng xếp chỗ (tiêu đề thư, cặp chữ ký), không phải bảng dữ
    liệu. Ô không có tên cột, ô của chính hàng tiêu đề, ô gộp dọc nối tiếp, ô mang
    hình hay bảng lồng: không có chỗ `o` nào (fail closed)."""
    tieu_de = [_tc("Họ và tên"), _tc(), _tc("Ghi chú"), _tc("Ảnh"), _tc("Lồng")]
    hinh = "<w:r><w:drawing/></w:r>"
    long = _bang([_tc()], tblpr="<w:tblPr/>")
    hang = [
        _tc(tcpr='<w:tcPr><w:vMerge w:val="restart"/></w:tcPr>'),
        _tc(),
        _tc(),
        _tc(noi=hinh),
        f"<w:tc>{long}{_p()}</w:tc>",
    ]
    noi_tiep = [_tc(tcpr="<w:tcPr><w:vMerge/></w:tcPr>"), _tc(), _tc()]
    assert _o(_mot(_bang(tieu_de, hang, tblpr="<w:tblPr/>"))) == []
    assert _o(_mot(_bang(tieu_de, hang, noi_tiep))) == [
        ((0, 1, 0), "Họ và tên (dòng 1)", 0, 0, 0),
        ((0, 1, 2), "Ghi chú (dòng 1)", 0, 0, 0),
        ((0, 2, 2), "Ghi chú (dòng 2)", 0, 0, 0),
    ]


def test_ten_cot_la_hang_tieu_de_CUOI_co_chu_va_dong_dem_tu_hang_du_lieu_dau():
    """Hàng đánh số cột "(1) (2)" dưới tiêu đề không phải tên cột và không phải hàng
    dữ liệu; tiêu đề hai tầng lấy tên ở tầng dưới."""
    bang = _bang(
        [_tc("Họ tên"), _tc("Điểm", tcpr='<w:tcPr><w:gridSpan w:val="2"/></w:tcPr>')],
        [_tc("(1)"), _tc("Tối đa"), _tc("Đánh giá")],
        [_tc("Nguyễn Văn A"), _tc("10"), _tc()],
    )
    assert _o(_mot(bang)) == [((0, 2, 2), "Đánh giá (dòng 1)", 0, 0, 0)]


def test_nhan_o_dai_giu_so_dong_qua_nhan_sach_luy_dang():
    dai = "Kết quả thực hiện nhiệm vụ được giao của sinh viên thực tập (tự đánh giá)"
    (c,) = [c for d in _mot(_bang([_tc(dai)], [_tc()])) for c in d.cho_trong]
    assert c.nhan.endswith(" (dòng 1)") and "(tự đánh giá)" not in c.nhan
    assert nhan_sach(c.nhan, "Số") == c.nhan


def test_o_rong_NOI_DUNG_NEO_va_LAM_SACH_y_HET_bang_khong_vien():
    """Cùng phép đo equivalence: chỗ `o` đi CẠNH chuỗi — cùng bảng có viền hay không
    thì `noi_dung`, `chi_so`, neo và bộ đếm `lam_sach_van_ban` y hệt."""
    hang = ([_tc("Họ và tên"), _tc("Thưởng 5.000.000 đồng")], [_tc(), _tc()])
    co, khong = _mot(_bang(*hang)), _mot(_bang(*hang, tblpr="<w:tblPr/>"))
    assert _o(co) and not _o(khong)
    assert [d.noi_dung for d in co] == [d.noi_dung for d in khong]
    assert [d.chi_so for d in co] == [d.chi_so for d in khong]
    a, b = xac_minh("Thưởng 5.000.000 đồng", co), xac_minh("Thưởng 5.000.000 đồng", khong)
    assert a.ly_do is b.ly_do is LyDoNeo.ok and a.chi_so_don_vi == b.chi_so_don_vi
    van_ban = {"muc": [{"ten": "A", "khoi": [{"noi_dung": "Thưởng 5.000.000 đồng"}]}]}
    nguon = " ".join(d.noi_dung for d in co)
    assert lam_sach_van_ban(van_ban, nguon, [{"nhan": "A", "don_vi": co}]) == lam_sach_van_ban(
        van_ban, nguon, [{"nhan": "A", "don_vi": khong}]
    )


def test_o_di_va_ve_qua_hang_va_o_hong_bi_bo():
    d = next(d for d in _mot(_bang([_tc("Họ và tên")], [_tc()])) if d.cho_trong)
    hang = _hang_don_vi(d)
    assert hang["cho_trong"] == [{"so": 0, "kieu": "o", "doan": 0, "dau": 0, "cuoi": 0, "nhan": "Họ và tên (dòng 1)"}]
    assert _cho_trong_tu_hang(hang["cho_trong"]) == d.cho_trong
    assert _cho_trong_tu_hang([{"so": 0, "kieu": "o", "doan": 0, "dau": 0, "cuoi": 1}]) == ()


@pytest.mark.skipif(not (_KHO_MAU / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx").exists(), reason="kho mẫu")
def test_bang_danh_sach_that_cua_BM_M05_co_24_o_cot_hang_dung_ten():
    tep = _KHO_MAU / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx"
    don_vi = doc(tep.name, tep.read_bytes()).don_vi
    o = {d.chi_so: c.nhan for d in don_vi for c in d.cho_trong if c.kieu == "o"}
    assert len(o) == 24 and sorted(o) == list(range(27, 51))
    assert [o[27], o[28], o[29], o[30], o[31], o[32], o[50]] == [
        "STT (dòng 1)",
        "Lớp quản lý (dòng 1)",
        "Mã sinh viên/ học viên (dòng 1)",
        "Họ và tên (dòng 1)",
        "Ngày sinh (dòng 1)",
        "Ghi chú (dòng 1)",
        "Ghi chú (dòng 4)",
    ]
    assert sum(1 for d in don_vi for c in d.cho_trong if c.kieu != "o") == 32, "chỗ trống cũ không đổi"
    assert not [c for d in don_vi if d.bang and d.bang[0] == 0 for c in d.cho_trong if c.kieu == "o"], "tiêu đề thư"


# ──────────────────────────────────────────────────────── lưu / đọc lại


def test_khoa_moi_CHI_co_mat_khi_nguon_khai():
    """Luật `**({"k": v} if v else {})` của hợp đồng: đơn vị không có địa chỉ
    thì dòng lưu không có khoá, không phải khoá mang `null`."""
    hang = _hang_don_vi(DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="x"))
    assert not {"dia_chi", "cho_trong", "hop", "doan_chu"} & hang.keys()


# ───────────────────────────────────────────── chữ thô từng đoạn (`doan_chu`)
# Prompt khuôn gốc đặt dấu chỗ trống NGAY TẠI chỗ của nó trong câu, và `thay`
# theo `doan` so chữ mới với chữ cũ của ĐÚNG đoạn ấy — cả hai cần chuỗi thô mà
# `doan`/`dau`/`cuoi` trỏ vào, thứ `noi_dung` (đã `strip`, các đoạn nối bằng dấu
# cách) không giữ lại được.


def test_doan_chu_la_chu_THO_tung_doan_theo_iter_w_p_cua_vat_chua():
    o = "<w:tc>" + _p(_r("TÊN CƠ QUAN")) + _p() + _p(_r(" Số …./…. ")) + "</w:tc>"
    d = _theo_chu(_mot(f"<w:tbl><w:tr>{o}</w:tr></w:tbl>"), "TÊN")
    assert d.doan_chu == ("TÊN CƠ QUAN", "", " Số …./…. ")
    assert [d.doan_chu[c.doan][c.dau : c.cuoi] for c in d.cho_trong] == ["….", "…."]


def test_doan_chu_CHI_co_khi_don_vi_co_cho_trong_hoac_nhieu_doan():
    o = "<w:tc>" + _p(_r("A")) + _p(_r("B")) + "</w:tc><w:tc>" + _p(_r("C")) + "</w:tc>"
    don_vi = _mot(_p(_r("Tiêu đề")) + _p(_r("Họ tên: ……")) + f"<w:tbl><w:tr>{o}</w:tr></w:tbl>")
    assert [(d.noi_dung, d.doan_chu) for d in don_vi] == [
        ("Tiêu đề", ()),
        ("Họ tên: ……", ("Họ tên: ……",)),
        ("A B", ("A", "B")),
        ("C", ()),
    ]


def test_doan_chu_di_va_ve_qua_hang_va_hang_hong_doc_ra_rong():
    from src.services.tai_lieu import _doan_chu_tu_hang

    d = _theo_chu(_mot(_p(_r("Họ tên: ……"))), "Họ tên")
    hang = _hang_don_vi(d)
    assert hang["doan_chu"] == ["Họ tên: ……"]
    assert _doan_chu_tu_hang(hang["doan_chu"]) == d.doan_chu
    for hong in (None, "Họ tên", [1], ["a", None], {}):
        assert _doan_chu_tu_hang(hong) == ()


def test_docx_di_va_ve_qua_hang_nguyen_ven():
    d = _theo_chu(_mot(_p(_r("Điện thoại: ………. Fax: …………"))), "Điện thoại")
    hang = _hang_don_vi(d)
    assert hang["dia_chi"] == {"phan": "word/document.xml", "chi_muc": [0]}
    dau = len("Điện thoại: ")
    assert hang["cho_trong"][0] == {
        "so": 0,
        "kieu": "cham",
        "doan": 0,
        "dau": dau,
        "cuoi": dau + len("………."),
        "nhan": "Điện thoại",
    }
    assert _dia_chi_tu_hang(hang["dia_chi"]) == d.dia_chi
    assert _cho_trong_tu_hang(hang["cho_trong"]) == d.cho_trong


def test_pdf_di_va_ve_qua_hang_nguyen_ven():
    c = ChoTrong(so=0, kieu="cham", nhan="Họ tên:", hop=(10.0, 20.5, 90.25, 33.0), co_chu=12.5)
    d = DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Họ tên: ……", hop=(5.0, 20.0, 95.0, 33.5), cho_trong=(c,))
    hang = _hang_don_vi(d)
    assert hang["cho_trong"] == [
        {"so": 0, "kieu": "cham", "hop": [10.0, 20.5, 90.25, 33.0], "co_chu": 12.5, "nhan": "Họ tên:"}
    ]
    assert _hop_tu_hang(hang["hop"]) == d.hop
    assert _cho_trong_tu_hang(hang["cho_trong"]) == d.cho_trong


@pytest.mark.parametrize(
    "tho",
    [
        None,
        "hỏng",
        {},
        {"phan": "", "chi_muc": [0]},
        {"phan": "word/document.xml", "chi_muc": []},
        {"phan": "word/document.xml", "chi_muc": [0, -1]},
        {"phan": "word/document.xml", "chi_muc": [True]},
        {"phan": "word/document.xml", "chi_muc": ["0"]},
    ],
)
def test_dia_chi_hong_hinh_dang_doc_ra_VANG(tho):
    assert _dia_chi_tu_hang(tho) is None


def test_cho_trong_hong_hinh_dang_bo_RIENG_phan_tu_do():
    tot = {"so": 1, "kieu": "tab", "doan": 0, "dau": 4, "cuoi": 4, "nhan": "Tên:"}
    hong = [
        "x",
        {"so": 0, "kieu": "gach", "doan": 0, "dau": 0, "cuoi": 3},
        {"so": 0, "kieu": "cham", "doan": 0, "dau": 5, "cuoi": 3},
        {"so": 0, "kieu": "cham", "doan": 0, "dau": 2, "cuoi": 2},
        {"so": 0, "kieu": "tab", "doan": 0, "dau": 1, "cuoi": 2},
        {"so": "0", "kieu": "cham", "doan": 0, "dau": 0, "cuoi": 3},
        {"so": 0, "kieu": "cham", "hop": [1, 2, 3], "co_chu": 10},
        {"so": 0, "kieu": "cham", "hop": [5, 2, 3, 4], "co_chu": 10},
        {"so": 0, "kieu": "cham", "hop": [1, 2, 3, 4], "co_chu": 0},
    ]
    assert _cho_trong_tu_hang([*hong, tot]) == (ChoTrong(so=1, kieu="tab", nhan="Tên:", dau=4, cuoi=4),)
    assert _cho_trong_tu_hang(None) == ()
    assert _hop_tu_hang([1, 2]) is None
    assert _hop_tu_hang([3, 0, 1, 4]) is None


# ───────────────────────────────────────── tám biểu mẫu thật của chủ dự án

_MAU = sorted(_KHO_MAU.glob("*.docx")) if _KHO_MAU.exists() else []
_W = f"{{{_NSW}}}"


def _con(nut):
    """Con PHẦN TỬ của một nút lxml — lxml giữ cả comment/PI làm con, ET thì
    không; `chi_muc` đếm phần tử, nên bộ áp (P3a) phải lọc đúng như vậy."""
    return [c for c in nut if isinstance(c.tag, str)]


def _giai(z: zipfile.ZipFile, dia_chi: DiaChi):
    from lxml import etree

    goc = etree.fromstring(z.read(dia_chi.phan))
    nut = goc.find(f"{_W}body") if goc.tag == f"{_W}document" else goc
    for i in dia_chi.chi_muc:
        nut = _con(nut)[i]
    return nut


def _tho_va_tab(p) -> tuple[str, list[int]]:
    """Chuỗi `w:t` nối THÔ của `p` và offset từng `w:tab` trong run (bỏ `w:pPr`)."""
    phan, tab, n = [], [], 0
    for con in p:
        if con.tag == f"{_W}pPr":
            continue
        for e in con.iter():
            if e.tag == f"{_W}t":
                phan.append(e.text or "")
                n += len(e.text or "")
            elif e.tag == f"{_W}tab":
                tab.append(n)
    return "".join(phan), tab


@pytest.mark.skipif(not _MAU, reason="kho mẫu ngoài repo không có trên máy này")
@pytest.mark.parametrize("tep", _MAU, ids=lambda p: p.stem[:24])
def test_moi_dia_chi_va_cho_trong_GIAI_DUNG_tren_bytes_tho_cua_tep_that(tep):
    """Bằng chứng P2b: đi lại bằng lxml trên CHÍNH bytes của tệp — không qua bộ
    đọc — thì mỗi `dia_chi` ra đúng `w:p`/`w:tc` mang chữ của đơn vị, mỗi chỗ
    trống `cham` là một lát toàn dấu chấm, mỗi chỗ trống `tab` đứng đúng ở một
    `w:tab` có mốc dẫn chấm."""
    du_lieu = tep.read_bytes()
    t = doc(tep.name, du_lieu)
    z = zipfile.ZipFile(BytesIO(du_lieu))
    for d in t.don_vi:
        if d.dia_chi is None:
            assert d.cho_trong == ()
            continue
        nut = _giai(z, d.dia_chi)
        assert nut.tag == (f"{_W}tc" if d.bang else f"{_W}p")
        # Chữ của vật chứa như bộ đọc thấy: bỏ bản `mc:Fallback` đôi.
        chu_nut = "".join(
            t.text or "" for t in nut.iter(f"{_W}t") if next(t.iterancestors(f"{{{_NSMC}}}Fallback"), None) is None
        )
        assert "".join(d.noi_dung.split())[:12] in "".join(chu_nut.split())
        doan = list(nut.iter(f"{_W}p"))
        if d.doan_chu:
            assert d.doan_chu == tuple(_tho_va_tab(p)[0] for p in doan), "doan_chu là chữ THÔ, cùng thứ tự bộ áp"
        for c in d.cho_trong:
            tho, tab = _tho_va_tab(doan[c.doan])
            assert tho == d.doan_chu[c.doan]
            if c.kieu == "cham":
                lat = tho[c.dau : c.cuoi]
                assert lat and set(lat) <= {".", "…"}, (d.noi_dung, c)
            elif c.kieu == "o":
                assert nut.tag == f"{_W}tc" and (c.doan, c.dau, c.cuoi) == (0, 0, 0) and not "".join(d.doan_chu).strip()
            else:
                assert c.kieu == "tab" and c.dau == c.cuoi and c.dau in tab
                moc = doan[c.doan].find(f"{_W}pPr/{_W}tabs")
                assert moc is not None and any(m.get(f"{_W}leader") == "dot" for m in moc)
    if tep.stem == "Evaluation Form":
        # 45 đoạn có tab dẫn chấm: 12 đoạn có nhãn ("Company name:<tab>") và 33
        # dòng chấm nối tiếp KHÔNG có chữ nào. Đoạn không chữ không phải đơn vị
        # văn bản (chuỗi đơn vị phải giữ nguyên từng byte), nên chỗ trống của nó
        # không có đơn vị nào để treo — đo, không phải lỗi sót.
        assert sum(c.kieu == "tab" for d in t.don_vi for c in d.cho_trong) == 12
