"""Tách ẢNH khỏi biểu mẫu tải lên — quyết định 2026-09-18
(`docs/decisions/2026-09-18-trung-thuc-bieu-mau-va-media.md`, mục "media đã
tách").

Hai nhóm khẳng định, và nhóm thứ hai mới là nhóm đắt:

1. Bộ đọc giải đúng `a:blip@r:embed` và `v:imagedata@r:id` qua `.rels` về một
   part dưới `word/media/`, giữ cỡ khai (`wp:extent`, EMU) và vùng (thân bài,
   đầu trang, chân trang); và FAIL CLOSED ở mọi cửa — rel gãy, kiểu lạ, quá
   trần — mà phần còn lại của tài liệu vẫn dựng đủ.
2. Một tấm ảnh KHÔNG dịch một ký tự nào. `noi_dung`, `normalize`, neo trích
   dẫn (`neo_du_kien.xac_minh`) và cả ĐẦU RA lẫn BỘ ĐẾM của
   `hieu_tai_lieu.lam_sach_van_ban` phải y hệt giữa hai tệp chỉ khác nhau ở
   chỗ có ảnh hay không. Bốn phase trước đã trả giá đúng ở chỗ này: một trường
   mới chen vào `noi_dung` là mọi bằng chứng trích dẫn của sản phẩm lệch cùng
   lúc, và đó là thứ KLAW bán.

Ảnh trong tệp mẫu là PNG 1×1 SINH RA TẠI CHỖ (`_PNG`), không phải ảnh thật:
một con dấu hay chữ ký quét là dữ liệu cá nhân của bên thứ ba, và commit nó
vào kho mã là đúng thứ quyết định trên cấm.
"""

import zipfile
from io import BytesIO

import pytest

from src.agents.nodes.hieu_tai_lieu import lam_sach_van_ban
from src.agents.nodes.verify_tier1 import normalize
from src.services.doc_tai_lieu import TRAN_ANH_BYTE, TRAN_ANH_TONG_BYTE, doc
from src.services.neo_du_kien import xac_minh

_NS = " ".join(
    (
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"',
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"',
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"',
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"',
        'xmlns:v="urn:schemas-microsoft-com:vml"',
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"',
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"',
    )
)

# PNG 1×1 hợp lệ, dựng bằng chính `zlib` — không nhúng một ảnh thật nào vào kho
# mã (xem docstring module). Nhỏ nhưng ĐÚNG tám byte chữ ký, đúng thứ
# `_kieu_anh` nhận dạng.
_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IENDaE\x82"
)

_RELS = (
    '<?xml version="1.0"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/image" Target="media/logo.png"/></Relationships>'
)

_DOAN_CHU = "<w:p><w:r><w:t>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</w:t></w:r></w:p>"
_DOAN_CHU_2 = "<w:p><w:r><w:t>Số: 18/QĐ-ĐHCN ngày 18 tháng 9 năm 2026</w:t></w:r></w:p>"


def _anh_drawing(rid: str = "rId1", cx: str = "1733550", cy: str = "537039") -> str:
    """Một `w:p` chỉ chứa ẢNH, không một ký tự nào — đúng hình dạng một đoạn
    letterhead thật, và là lý do ảnh KHÔNG treo lên được một đơn vị văn bản."""
    return (
        f'<w:p><w:r><w:drawing><wp:inline><wp:extent cx="{cx}" cy="{cy}"/>'
        "<a:graphic><a:graphicData><pic:pic><pic:blipFill>"
        f'<a:blip r:embed="{rid}"/></pic:blipFill></pic:pic></a:graphicData></a:graphic>'
        "</wp:inline></w:drawing></w:r></w:p>"
    )


_ANH_VML = (
    '<w:p><w:r><w:pict><v:shape style="width:136.5pt;height:42.3pt">'
    '<v:imagedata r:id="rId1"/></v:shape></w:pict></w:r></w:p>'
)


def _docx(
    than: str,
    *,
    rels: str | None = _RELS,
    media: bytes | None = _PNG,
    ten_media: str = "word/media/logo.png",
    dau_trang: str = "",
) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", f"<w:document {_NS}><w:body>{than}</w:body></w:document>")
        if rels is not None:
            z.writestr("word/_rels/document.xml.rels", rels)
        if dau_trang:
            z.writestr("word/header1.xml", f"<w:hdr {_NS}>{dau_trang}</w:hdr>")
            z.writestr("word/_rels/header1.xml.rels", _RELS)
        if media is not None:
            z.writestr(ten_media, media)
    return buf.getvalue()


def _anh(du_lieu: bytes):
    """Mô tả ảnh của một tài liệu — chép trên MỌI đơn vị, nên đọc đơn vị đầu."""
    tl = doc("bieu-mau.docx", du_lieu)
    return tl.don_vi[0].anh, tl.anh_byte


# ═══ Tách được ═══════════════════════════════════════════════════════════════


def test_anh_NOI_TUYEN_giai_qua_rels_ve_part_media_kem_co_khai():
    anh, byte = _anh(_docx(_DOAN_CHU + _anh_drawing()))

    assert len(anh) == 1
    assert (anh[0].phan, anh[0].kieu) == ("word/media/logo.png", "image/png")
    # Cỡ giữ NGUYÊN EMU, không quy đổi ở bộ đọc — `.docx` tải về ghi lại chính
    # đơn vị này (xem `AnhTaiLieu.rong`).
    assert (anh[0].rong, anh[0].cao) == (1733550, 537039)
    assert (anh[0].vung, anh[0].thu_tu) == ("than", 0)
    assert byte == {"word/media/logo.png": ("image/png", _PNG)}


def test_anh_trong_DAU_TRANG_doc_duoc_qua_rels_RIENG_cua_no():
    """Logo letterhead gần như luôn nằm ở `word/headerN.xml`, và phần ấy có
    bảng `.rels` RIÊNG. Tra nhầm bảng thì logo biến mất đúng ở tệp có logo."""
    anh, byte = _anh(_docx(_DOAN_CHU, dau_trang=_anh_drawing()))

    assert len(anh) == 1
    assert (anh[0].phan, anh[0].vung, anh[0].thu_tu) == ("word/media/logo.png", "dau_trang", 0)
    assert byte["word/media/logo.png"] == ("image/png", _PNG)


def test_anh_VML_doc_duoc_va_co_quy_tu_style_CSS_sang_EMU():
    """Biểu mẫu cũ dùng `v:imagedata` thay `a:blip`, và khai cỡ bằng CSS trên
    `v:shape` chứ không bằng `wp:extent`."""
    anh, byte = _anh(_docx(_DOAN_CHU + _ANH_VML))

    assert len(anh) == 1
    assert anh[0].phan == "word/media/logo.png"
    # 136.5pt × 12700 = 1733550 EMU; 42.3pt × 12700 = 537210.
    assert (anh[0].rong, anh[0].cao) == (1733550, 537210)
    assert byte["word/media/logo.png"] == ("image/png", _PNG)


def test_mc_AlternateContent_KHONG_tach_cung_mot_logo_HAI_lan():
    """`mc:Choice` (DrawingML) và `mc:Fallback` (VML) chở CÙNG một hình. Không
    bỏ Fallback thì mọi logo của Word hiện đại đếm và tách hai lần."""
    doi = (
        "<w:p><w:r><mc:AlternateContent>"
        f"<mc:Choice Requires=\"wps\">{_anh_drawing()}</mc:Choice>"
        f"<mc:Fallback>{_ANH_VML}</mc:Fallback>"
        "</mc:AlternateContent></w:r></w:p>"
    )
    anh, byte = _anh(_docx(_DOAN_CHU + doi))

    assert len(anh) == 1
    assert len(byte) == 1


def test_mot_logo_dung_HAI_CHO_ra_HAI_mo_ta_nhung_MOT_khoi_bytes():
    anh, byte = _anh(_docx(_DOAN_CHU + _anh_drawing() + _DOAN_CHU_2 + _anh_drawing()))

    assert [a.thu_tu for a in anh] == [0, 1]
    assert {a.phan for a in anh} == {"word/media/logo.png"}
    assert len(byte) == 1


# ═══ Fail closed ═════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    # `ids` từ chính tên ca: không có nó, pytest dựng id từ BYTES của tệp .docx
    # và một dòng kết quả dài vài nghìn ký tự che mất ca nào đỏ.
    ("ten", "du_lieu"),
    ids=lambda x: x if isinstance(x, str) else "",
    argvalues=[
        # rId2 không có trong `.rels` — một tệp Word hỏng nửa chừng.
        ("rel gãy", _docx(_DOAN_CHU + _anh_drawing(rid="rId2"))),
        # Không có `.rels` nào cả.
        ("thiếu rels", _docx(_DOAN_CHU + _anh_drawing(), rels=None)),
        # `.rels` trỏ tới một part không tồn tại trong zip.
        ("thiếu part", _docx(_DOAN_CHU + _anh_drawing(), media=None)),
        # EMF: trình duyệt không vẽ được, `docx.ImageRun` không nhận, jsPDF
        # không dựng — giữ bytes cho nó là lưu dữ liệu cá nhân không đổi lại gì.
        ("kiểu lạ", _docx(_DOAN_CHU + _anh_drawing(), media=b"\x01\x00\x00\x00 EMF")),
        # SVG: trình duyệt VẼ được, nhưng nó là XML chạy được script — loại CÓ
        # CHỦ Ý, không phải quên.
        ("svg", _docx(_DOAN_CHU + _anh_drawing(), media=b"<svg onload='alert(1)'/>")),
        # Quá trần MỘT ảnh.
        ("quá trần ảnh", _docx(_DOAN_CHU + _anh_drawing(), media=_PNG + b"\x00" * TRAN_ANH_BYTE)),
    ],
)
def test_anh_KHONG_DUNG_DUOC_bi_bo_ma_ca_tai_lieu_van_doc_duoc(ten, du_lieu):
    anh, byte = _anh(du_lieu)

    assert anh == () and byte == {}, ten
    # Cả tờ giấy vẫn đọc được — đó là điều kiện của "fail closed".
    assert doc("x.docx", du_lieu).don_vi[0].noi_dung == "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM"


def test_TRAN_CA_TAI_LIEU_giu_anh_dau_va_bo_anh_lam_TRAN_vo(monkeypatch):
    """Trăm ảnh nhỏ cộng lại vẫn đầy một dòng Postgres, nên trần mỗi ảnh không
    thay được trần cả tài liệu.

    Hạ CẢ HAI trần thay vì dựng 8 MB số 0 trong bộ nhớ: phép đo ở đây là LUẬT
    cộng dồn, không phải con số cụ thể — và một tệp mẫu 8 MB làm chậm cả lượt
    kiểm để chứng minh đúng điều mà hai trần nhỏ cũng chứng minh được.
    """
    monkeypatch.setattr("src.services.doc_tai_lieu.TRAN_ANH_BYTE", 2048)
    monkeypatch.setattr("src.services.doc_tai_lieu.TRAN_ANH_TONG_BYTE", 2048)
    # Đúng 1024 byte mỗi tấm: hai tấm vừa KHÍT trần cả tài liệu, tấm thứ ba
    # làm vỡ. Mỗi tấm dưới trần MỖI ảnh, nên chỉ trần cộng dồn mới chặn được.
    nho = _PNG + b"\x00" * (1024 - len(_PNG))
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr(
            "word/document.xml",
            f"<w:document {_NS}><w:body>{_DOAN_CHU}"
            f'{_anh_drawing(rid="rId1")}{_anh_drawing(rid="rId2")}{_anh_drawing(rid="rId3")}'
            "</w:body></w:document>",
        )
        z.writestr(
            "word/_rels/document.xml.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/'
                f'officeDocument/2006/relationships/image" Target="media/a{i}.png"/>'
                for i in (1, 2, 3)
            )
            + "</Relationships>",
        )
        for i in (1, 2, 3):
            z.writestr(f"word/media/a{i}.png", nho)
    anh, byte = _anh(buf.getvalue())

    # Hai tấm đầu vừa trần (mỗi tấm nửa trần), tấm thứ ba làm vỡ và bị bỏ.
    assert [a.phan for a in anh] == ["word/media/a1.png", "word/media/a2.png"]
    assert set(byte) == {"word/media/a1.png", "word/media/a2.png"}
    assert sum(len(v[1]) for v in byte.values()) <= TRAN_ANH_TONG_BYTE


def test_rel_TRO_RA_NGOAI_word_media_bi_tu_choi():
    """Một `r:embed` trỏ tới một part bất kỳ của zip là đường đọc trộm nội dung
    tệp người lạ, không phải một tấm ảnh."""
    anh, byte = _anh(
        _docx(
            _DOAN_CHU + _anh_drawing(),
            rels=(
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
                '2006/relationships/image" Target="../[Content_Types].xml"/></Relationships>'
            ),
        )
    )

    assert anh == () and byte == {}


def test_anh_LIEN_KET_NGOAI_khong_goi_ra_mang():
    """`TargetMode="External"` không có bytes trong tệp. Đi lấy nó là để tài
    liệu của khách điều khiển máy chủ gọi ra một địa chỉ bất kỳ (SSRF)."""
    anh, byte = _anh(
        _docx(
            _DOAN_CHU + _anh_drawing(),
            rels=(
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" TargetMode="External" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                'Target="http://169.254.169.254/latest/meta-data/"/></Relationships>'
            ),
        )
    )

    assert anh == () and byte == {}


# ═══ Tương đương: ảnh KHÔNG dịch một ký tự nào ═══════════════════════════════


_CO_ANH = _docx(_DOAN_CHU + _anh_drawing() + _DOAN_CHU_2)
_KHONG_ANH = _docx(_DOAN_CHU + _DOAN_CHU_2, media=None, rels=None)

_TRICH = "Số: 18/QĐ-ĐHCN ngày 18 tháng 9 năm 2026"


def test_anh_khong_doi_noi_dung_hay_neo():
    """Hợp đồng của bốn phase trước, nguyên văn: `noi_dung` y hệt từng byte,
    `normalize` y hệt, và neo trích dẫn trỏ vào ĐÚNG một đơn vị/trang/offset.

    Đây là chỗ đắt nhất của cả bản vá. `neo_du_kien.xac_minh` là bằng chứng
    của cả sản phẩm; một ảnh chen vào làm lệch `chi_so`/`offset_dau` sẽ khiến
    mọi trích dẫn đã lưu trỏ sang chỗ khác mà giao diện trông y hệt.
    """
    co = doc("co-anh.docx", _CO_ANH)
    khong = doc("khong-anh.docx", _KHONG_ANH)

    assert [d.noi_dung for d in co.don_vi] == [d.noi_dung for d in khong.don_vi]
    assert [normalize(d.noi_dung) for d in co.don_vi] == [
        normalize(d.noi_dung) for d in khong.don_vi
    ]
    assert [(d.chi_so, d.trang, d.offset_dau) for d in co.don_vi] == [
        (d.chi_so, d.trang, d.offset_dau) for d in khong.don_vi
    ]
    assert (co.so_ky_tu, co.so_trang) == (khong.so_ky_tu, khong.so_trang)

    neo_co = xac_minh(_TRICH, co.don_vi)
    neo_khong = xac_minh(_TRICH, khong.don_vi)
    assert neo_co.ly_do is neo_khong.ly_do
    assert (neo_co.chi_so_don_vi, neo_co.trang, neo_co.offset_dau) == (
        neo_khong.chi_so_don_vi,
        neo_khong.trang,
        neo_khong.offset_dau,
    )
    # Ảnh CÓ được đọc ra — nếu không thì hai vế trên bằng nhau một cách tầm
    # thường và test này không chứng minh gì cả.
    assert len(co.don_vi[0].anh) == 1 and khong.don_vi[0].anh == ()


def test_anh_khong_doi_dau_ra_VA_BO_DEM_cua_lam_sach_van_ban():
    """`lam_sach_van_ban` gỡ khỏi bản thảo mọi giá trị không có trong nguồn.
    Bộ đếm của nó đi thẳng vào traces, nên một con số lệch là một phép đo lệch
    — chốt CẢ đầu ra lẫn bộ đếm, không chỉ đầu ra."""
    co = doc("co-anh.docx", _CO_ANH)
    khong = doc("khong-anh.docx", _KHONG_ANH)
    van_ban = {
        "tieu_de": "QUYẾT ĐỊNH",
        "muc": [
            {
                "ten": "Căn cứ",
                "khoi": [{"noi_dung": f"{_TRICH} và số 99/QĐ-BỊA không có trong nguồn"}],
            }
        ],
    }
    nguon = "\n".join(d.noi_dung for d in co.don_vi)
    goi_co = [{"id": "v1", "ten_tep": "x.docx", "don_vi": co.don_vi}]
    goi_khong = [{"id": "v1", "ten_tep": "x.docx", "don_vi": khong.don_vi}]

    ra_co, dem_co = lam_sach_van_ban(van_ban, nguon, goi_co)
    ra_khong, dem_khong = lam_sach_van_ban(van_ban, nguon, goi_khong)

    # CHỮ y hệt, kể cả chỗ bị gỡ và chỗ giữ lại. `anh` là khoá MỚI đứng CẠNH
    # chữ (cùng khuôn `le_trang` của phase trước), không nằm trong nó — nên nó
    # bị loại khỏi phép so này và được chốt riêng ở hai test dưới.
    def _khong_anh(ra: dict) -> dict:
        return {
            **ra,
            "muc": [{k: v for k, v in m.items() if k != "anh"} for m in ra["muc"]],
        }

    assert _khong_anh(ra_co) == _khong_anh(ra_khong)
    # Bộ đếm đi thẳng vào traces: một con số lệch là một phép đo lệch.
    assert dem_co == dem_khong
    # Và ảnh THẬT SỰ có mặt ở vế trái — nếu không, phép so trên bằng nhau một
    # cách tầm thường.
    assert ra_co["muc"][0]["anh"] != []
    assert "anh" not in ra_khong["muc"][0]


def test_LAM_SACH_VAN_BAN_mang_ANH_sang_TUNG_MUC_kem_duong_dan_co_viec_id():
    co = doc("co-anh.docx", _CO_ANH)
    ra, _ = lam_sach_van_ban(
        {"muc": [{"ten": "A", "khoi": [{"noi_dung": _TRICH}]}]},
        _TRICH,
        [{"id": "v1", "ten_tep": "x.docx", "don_vi": co.don_vi}],
    )

    assert ra["muc"][0]["anh"] == [
        {
            "url": "/tai-lieu/v1/anh/logo.png",
            "rong": 1733550,
            "cao": 537039,
            "vung": "than",
            "thu_tu": 0,
        }
    ]


def test_LAM_SACH_VAN_BAN_KHONG_them_khoa_anh_khi_nguon_khong_co_anh():
    khong = doc("khong-anh.docx", _KHONG_ANH)
    ra, _ = lam_sach_van_ban(
        {"muc": [{"ten": "A", "khoi": [{"noi_dung": _TRICH}]}]},
        _TRICH,
        [{"id": "v1", "ten_tep": "x.docx", "don_vi": khong.don_vi}],
    )

    assert "anh" not in ra["muc"][0]
