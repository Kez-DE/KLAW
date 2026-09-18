"""Dòng chảy TRANG của `.docx` — `w:br w:type="page"` và ngắt phân đoạn.

Trước bản vá này, số trang của một `.docx` được quy đổi THUẦN theo số ký tự
(`KY_TU_MOI_TRANG`), nên BM.M05 — một biểu mẫu khai đúng một ngắt trang cứng —
ra 52 đơn vị cùng `trang=1`. Con số đó không dừng lại ở bộ đọc: nó đi thẳng vào
`neo_du_kien.xac_minh` và vào mọi `quan_sat` KLAW hiện ("tr. 1"), nên sản phẩm
nói sai chỗ một dòng chữ nằm trên trang 2.

Bốn điều file này khoá:

1. Ngắt tệp KHAI được tôn trọng — cứng (`w:br`) và phân đoạn (`w:sectPr/w:type`,
   kể cả khi `w:type` vắng mặt, vì mặc định OOXML là `nextPage`).
2. Chỗ ĐỨNG của ngắt đổi nghĩa: trước chữ thì đẩy chính đoạn ấy, sau chữ thì
   chỉ đẩy đoạn kế tiếp.
3. Tệp KHÔNG khai ngắt nào thì không có trang nào bị bịa ra — `trang` giữ
   nguyên 1, đúng luật "không suy diễn thêm ngoài những gì tệp nói".
4. `noi_dung`, `normalize`, `xac_minh` và `lam_sach_van_ban` KHÔNG đổi vì ngắt
   trang, trừ đúng hai trường `trang`/`offset_dau` — và chúng đổi về phía ĐÚNG.
"""

import zipfile
from io import BytesIO

from src.agents.nodes.hieu_tai_lieu import lam_sach_van_ban
from src.services.doc_tai_lieu import KY_TU_MOI_TRANG, doc
from src.services.neo_du_kien import LyDoNeo, normalize, xac_minh

_NGAT = '<w:r><w:br w:type="page"/></w:r>'


def _p(chu: str, truoc: str = "", sau: str = "", ppr: str = "") -> str:
    """Một `w:p`, có thể kèm ngắt trang TRƯỚC hoặc SAU chữ của nó."""
    return f"<w:p>{ppr}{truoc}<w:r><w:t>{chu}</w:t></w:r>{sau}</w:p>"


def _p_ngat() -> str:
    """Đoạn CHỈ chứa ngắt, không một ký tự nào — đúng cách Word ghi một
    Ctrl+Enter đứng riêng, và đúng hình dạng của BM.M05."""
    return f"<w:p>{_NGAT}</w:p>"


def _sect(kieu: str | None) -> str:
    """`w:sectPr` trong `w:pPr` — kết thúc một phân đoạn. `None` = không khai
    `w:type` (mặc định OOXML là `nextPage`)."""
    t = "" if kieu is None else f'<w:type w:val="{kieu}"/>'
    return f"<w:pPr><w:sectPr>{t}</w:sectPr></w:pPr>"


def _tc(chu: str, truoc: str = "", sau: str = "") -> str:
    return f"<w:tc>{_p(chu, truoc, sau)}</w:tc>"


def _tbl(*hang: str) -> str:
    return "<w:tbl>" + "".join(f"<w:tr>{h}</w:tr>" for h in hang) + "</w:tbl>"


def _docx(than: str, sect_cuoi: str = "") -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{than}{sect_cuoi}</w:body></w:document>"
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def _trang(than: str, sect_cuoi: str = "") -> list[int]:
    return [d.trang for d in doc("x.docx", _docx(than, sect_cuoi)).don_vi]


# ───────────────────────────────────────────────── ngắt trang CỨNG (`w:br`)


def test_MOT_NGAT_CUNG_day_moi_thu_sau_no_sang_trang_2():
    assert _trang(_p("Trang một") + _p_ngat() + _p("Trang hai")) == [1, 2]


def test_HAI_NGAT_CUNG_cho_ba_trang():
    than = _p("Một") + _p_ngat() + _p("Hai") + _p_ngat() + _p("Ba")
    assert _trang(than) == [1, 2, 3]


def test_NGAT_SAU_CHU_chi_day_doan_KE_TIEP_khong_day_chinh_no():
    """`w:br` là run CUỐI của một đoạn có chữ — cách Word ghi "xuống trang sau
    dòng này". Chính dòng ấy vẫn ở trang cũ."""
    assert _trang(_p("Còn ở trang một", sau=_NGAT) + _p("Trang hai")) == [1, 2]


def test_NGAT_TRUOC_CHU_day_CHINH_doan_do_sang_trang_moi():
    """`w:br` đứng trước run chữ đầu tiên: Word đặt chính dòng ấy lên trang
    mới, không phải dòng sau nó."""
    assert _trang(_p("Trang một") + _p("Trang hai", truoc=_NGAT)) == [1, 2]


def test_NGAT_TRONG_O_BANG_duoc_doc_theo_dung_thu_tu_o():
    """Ngắt nằm trong một ô bảng. Bộ đọc đọc nó ở mức Ô (ô LÀ đơn vị), nên ô
    mang ngắt trước chữ sang trang mới và mọi ô sau nó theo cùng.

    Trần đã ghi ở `doc_tai_lieu._SECT_SANG_TRANG`: Word bỏ qua ngắt cứng trong
    bảng ở một số ca. Ở đây tệp khai gì thì đọc nấy — đoán thay Word là suy
    diễn thêm ngoài những gì tệp nói."""
    than = _tbl(_tc("A") + _tc("B", truoc=_NGAT)) + _p("Sau bảng")
    assert _trang(than) == [1, 2, 2]


def test_KHONG_NGAT_NAO_thi_KHONG_TRANG_NAO_bi_bia_ra():
    """Luật trung tâm: tệp không khai ngắt thì bộ đọc không được đẻ ra trang
    thứ hai, dù tài liệu dài tới đâu. 7000 ký tự — quá `KY_TU_MOI_TRANG` hai
    lần — vẫn là MỘT trang KHAI."""
    than = "".join(_p("x" * 1000) for _ in range(7))
    assert KY_TU_MOI_TRANG == 3000
    assert _trang(than) == [1] * 7


def test_DO_DAY_van_lo_ra_o_so_trang_du_khong_ngat_nao():
    """Nửa còn lại của test trên: `so_trang` — thứ định tuyến FR-029/030 và cổng
    độ dài của `loc_don_vi` đọc — vẫn phải thấy tài liệu dày, bằng ước lượng
    theo ký tự. Nếu không, một hợp đồng 40 trang không ấn Ctrl+Enter lần nào sẽ
    đi thẳng vào prompt."""
    than = "".join(_p("x" * 1000) for _ in range(7))
    assert doc("x.docx", _docx(than)).so_trang == 3  # ceil(7000 / 3000)


# ────────────────────────────────────────────────────── ngắt PHÂN ĐOẠN


_SECT_CUOI = "<w:sectPr><w:pgSz w:w='11907' w:h='16839'/></w:sectPr>"


def test_NGAT_PHAN_DOAN_KHONG_KHAI_TYPE_la_mot_ngat_trang():
    """`w:type` vắng mặt = `nextPage` (mặc định OOXML). Đây là ngoại lệ có căn
    cứ của luật "vắng mặt nghĩa là không biết": ở riêng chỗ này, chuẩn nói rõ
    giá trị mặc định."""
    than = _p("Phân đoạn một") + _p("Đoạn kết", ppr=_sect(None)) + _p("Phân đoạn hai")
    assert _trang(than, _SECT_CUOI) == [1, 1, 2]


def test_NGAT_PHAN_DOAN_CONTINUOUS_KHONG_sang_trang():
    """`continuous` nói thẳng là phân đoạn sau chạy tiếp trên cùng trang — đọc
    nó thành một ngắt là vẽ thứ tệp phủ nhận."""
    than = _p("Một") + _p("Kết", ppr=_sect(None)) + _p("Hai")
    sect = '<w:sectPr><w:type w:val="continuous"/></w:sectPr>'
    assert _trang(than, sect) == [1, 1, 1]


def test_SECTPR_CUOI_THAN_khong_de_ra_ngat_nao():
    """`w:sectPr` con trực tiếp của `w:body` tả phân đoạn CUỐI. Sau nó không
    còn gì, nên nó không đẩy ai sang trang mới."""
    assert _trang(_p("Một") + _p("Hai"), _SECT_CUOI) == [1, 1]


# ────────────────────────────────────────────── hình dạng THẬT của BM.M05


def test_HINH_DANG_BM_M05_ngat_roi_con_noi_dung_dai_phia_sau():
    """Đúng hình dạng đo được trên tệp thật: một khối đầu, một đoạn CHỈ chứa
    ngắt, rồi một tiêu đề và một bảng danh sách. Mọi thứ sau ngắt phải ở trang
    2, kể cả ô bảng rỗng chữ."""
    than = (
        _p("GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP")
        + _p("(Ký và ghi rõ họ tên, chức vụ, đóng dấu)")
        + _p_ngat()
        + _p("DANH SÁCH SINH VIÊN/HỌC VIÊN THỰC HÀNH/THỰC TẬP TẠI …")
        + _tbl(_tc("STT") + _tc("Họ và tên"), _tc("") + _tc(""))
    )
    assert _trang(than) == [1, 1, 2, 2, 2, 2, 2]


def test_NEO_CUA_DON_VI_SAU_NGAT_bao_trang_2():
    """Điều người dùng thật sự thấy: `xac_minh` của một câu nằm sau ngắt phải
    trả về `trang=2`. Đây là chỗ con số cũ ("tr. 1") đi ra giao diện."""
    than = _p("Xác nhận của Cơ quan/Đơn vị") + _p_ngat() + _p("DANH SÁCH SINH VIÊN THỰC TẬP")
    don_vi = doc("x.docx", _docx(than)).don_vi
    neo = xac_minh("DANH SÁCH SINH VIÊN THỰC TẬP", don_vi)
    assert neo.ly_do is LyDoNeo.ok
    assert neo.trang == 2
    assert neo.offset_dau == 0, "offset đếm TRONG trang, nên nó khởi động lại ở trang mới"


# ───────────────────────────────────────── bất biến neo trích dẫn


_THAN_NGAT = _p("Mức lương: 20.000.000 đồng/tháng") + _p_ngat() + _p("Thưởng 5.000.000 đồng")
_THAN_TRAN = _p("Mức lương: 20.000.000 đồng/tháng") + _p("Thưởng 5.000.000 đồng")


def test_NOI_DUNG_va_LAM_SACH_y_HET_khi_bo_ngat_trang():
    """Cột mốc của bản vá, cùng phép đo `test_doc_tai_lieu_vien_le` đã dùng cho
    viền/lề: thêm một ngắt trang vào tệp KHÔNG được đổi một ký tự nào của
    `noi_dung`, cũng không đổi `normalize` hay kết quả `lam_sach_van_ban` (cả
    đầu ra lẫn BỘ ĐẾM).

    Hai trường CÓ đổi là `trang` và `offset_dau`, và đó chính là bản vá: một
    dòng nằm sau ngắt giờ báo trang 2 thay vì trang 1, và `offset_dau` —
    "ký tự TRONG TRANG" theo đúng định nghĩa của nó — đếm lại từ đầu trang mới.
    `chi_so` thì KHÔNG đổi: thứ tự đọc không phụ thuộc trang."""
    co = doc("x.docx", _docx(_THAN_NGAT)).don_vi
    khong = doc("x.docx", _docx(_THAN_TRAN)).don_vi

    assert [d.noi_dung for d in co] == [d.noi_dung for d in khong]
    assert [normalize(d.noi_dung) for d in co] == [normalize(d.noi_dung) for d in khong]
    assert [d.chi_so for d in co] == [d.chi_so for d in khong]

    trich = "Thưởng 5.000.000 đồng"
    neo_co, neo_khong = xac_minh(trich, co), xac_minh(trich, khong)
    assert neo_co.ly_do is neo_khong.ly_do is LyDoNeo.ok
    assert neo_co.chi_so_don_vi == neo_khong.chi_so_don_vi
    assert (neo_co.trang, neo_co.offset_dau) == (2, 0)
    assert (neo_khong.trang, neo_khong.offset_dau) == (1, len(khong[0].noi_dung) + 1)

    van_ban = {
        "muc": [
            {
                "ten": "Lương",
                "khoi": [{"noi_dung": "Mức lương: 20.000.000 đồng/tháng và thưởng 5.000.000 đồng"}],
            }
        ]
    }
    nguon = " ".join(d.noi_dung for d in co)
    ra_co, dem_co = lam_sach_van_ban(van_ban, nguon, [{"nhan": "A", "don_vi": co}])
    ra_khong, dem_khong = lam_sach_van_ban(van_ban, nguon, [{"nhan": "A", "don_vi": khong}])
    assert dem_co == dem_khong
    assert [[k["noi_dung"] for k in m["khoi"]] for m in ra_co["muc"]] == [
        [k["noi_dung"] for k in m["khoi"]] for m in ra_khong["muc"]
    ]
