"""Bộ dựng khuôn mẫu `khuon_mau.dung_docx` — thiết kế `khuon-mau-thiet-ke.md` §1, §2, §8.

Hàm thuần: không DB, không mô hình, không LibreOffice (trang thật ở
`test_khuon_mau_trang.py`). Khoá bốn lời hứa:

1. Thể thức đúng Phụ lục I NĐ 30/2020: A4, lề, chuỗi quốc hiệu/tiêu ngữ chính
   thức, số trang ở lề trên trừ trang 1.
2. Không dấu giữ chỗ nào trong tệp: không `{`, `⟦`, `¶`, `[…]`, `<…>`.
3. Bộ đọc của khuôn gốc (`doc_tai_lieu.doc`) thấy đúng mọi chỗ trống bộ dựng viết,
   đúng loại, đúng nhãn — và bộ áp (`dien_khuon.ap_dung_docx`) điền được tất cả.
4. Cùng spec ra cùng bytes.
"""

import io
import re
import zipfile

import pytest
from lxml import etree

from src.services import khuon_mau as km
from src.services.dien_khuon import ap_dung_docx
from src.services.doc_tai_lieu import doc
from src.services.tai_lieu import _hang_don_vi

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CAN_CU = [
    {"dong": "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019;", "doc_id": "139264"},
    {"dong": "Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11 năm 2015.", "doc_id": "95942"},
]
DIEU = [
    {"key": "cong_viec", "ten": "Công việc và địa điểm làm việc", "doan": ["Địa điểm làm việc: ……"]},
    {"key": "luong", "ten": "Mức lương", "doan": ["Mức lương: …… đồng/tháng.", "Trả lương vào ngày …… hằng tháng."]},
]


def _spec(loai: str, dieu=DIEU, **kw) -> dict:
    return km.spec_tu(km.nap(loai), tieu_de=None, trich_yeu=kw.get("trich_yeu"), can_cu=CAN_CU, dieu=dieu)


def _tong_quat(bo_cuc: str = "hop_dong") -> dict:
    ben = [
        {"khoa": "ben_a", "vai": "Bên cho thuê", "loai": "ca_nhan"},
        {"khoa": "ben_b", "vai": "Bên thuê", "loai": "to_chuc"},
    ]
    return km.spec_tu(
        {**km.khung_tong_quat(bo_cuc, ben), "loai": None},
        tieu_de="Hợp đồng thuê tài sản",
        trich_yeu=None,
        can_cu=CAN_CU,
        dieu=DIEU,
    )


def _part(docx: bytes, ten: str):
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        return etree.fromstring(z.read(ten))


def _don_vi(docx: bytes) -> list[dict]:
    return [_hang_don_vi(d) for d in doc("k.docx", docx).don_vi]


DIEU_DON = [{"key": "yeu_cau", "ten": "", "doan": ["Buộc bị đơn trả …… đồng.", "Buộc bị đơn trả lại nhà."]}]
DIEU_CV = [{"key": "noi_dung", "ten": "", "doan": ["Đề nghị Quý cơ quan hướng dẫn trước ngày …….", "Liên hệ: ……"]}]
TAT_CA = [
    _spec("hdld"),
    _spec("don_khoi_kien", DIEU_DON),
    _spec("cong_van", DIEU_CV, trich_yeu="đề nghị bổ sung"),
    _tong_quat("hop_dong"),
    _tong_quat("don"),
    _tong_quat("hanh_chinh"),
]
TEN = ["hdld", "don_khoi_kien", "cong_van", "tq_hop_dong", "tq_don", "tq_hanh_chinh"]


@pytest.mark.parametrize("spec", TAT_CA, ids=TEN)
def test_trang_A4_le_phu_luc_I_va_so_trang_tru_trang_dau(spec):
    docx, _ = km.dung_docx(spec)
    goc = _part(docx, "word/document.xml")
    sect = goc.find(f"{_W}body/{_W}sectPr")
    assert (sect.find(f"{_W}pgSz").get(f"{_W}w"), sect.find(f"{_W}pgSz").get(f"{_W}h")) == ("11906", "16838")
    le = sect.find(f"{_W}pgMar")
    mm = {k: round(int(le.get(f"{_W}{k}")) * 25.4 / 1440) for k in ("top", "bottom", "left", "right")}
    assert 20 <= mm["top"] <= 25 and 20 <= mm["bottom"] <= 25 and 30 <= mm["left"] <= 35 and 15 <= mm["right"] <= 20
    assert sect.find(f"{_W}titlePg") is not None
    refs = sect.findall(f"{_W}headerReference")
    assert [r.get(f"{_W}type") for r in refs] == ["default"], "không có đầu trang riêng cho trang 1"
    hdr = _part(docx, "word/header1.xml")
    assert [f.get(f"{_W}instr").strip() for f in hdr.iter(f"{_W}fldSimple")] == ["PAGE"]


@pytest.mark.parametrize("spec", TAT_CA, ids=TEN)
def test_quoc_hieu_tieu_ngu_dung_chuoi_chinh_thuc_va_dam(spec):
    docx, _ = km.dung_docx(spec)
    run = {t.text: t.getparent() for t in _part(docx, "word/document.xml").iter(f"{_W}t")}
    assert "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" in run and "Độc lập - Tự do - Hạnh phúc" in run
    for chu in ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "Độc lập - Tự do - Hạnh phúc"):
        assert run[chu].find(f"{_W}rPr/{_W}b") is not None


@pytest.mark.parametrize("spec", TAT_CA, ids=TEN)
def test_khong_dau_giu_cho_nao_trong_moi_part(spec):
    docx, _ = km.dung_docx(spec)
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        for ten in z.namelist():
            goc = etree.fromstring(z.read(ten))
            chu = "".join(t.text or "" for t in goc.iter(f"{_W}t"))
            assert not re.search(r"[{}⟦⟧¶]|\[[^\]]*\]|<[^>]*>", chu), (ten, chu[:200])


def test_cung_spec_cung_bytes():
    assert km.dung_docx(_spec("hdld"))[0] == km.dung_docx(_spec("hdld"))[0]


@pytest.mark.parametrize("spec", TAT_CA, ids=TEN)
def test_ban_do_khop_cho_trong_bo_doc_thay(spec):
    """Mỗi đơn vị trong bản đồ có đúng số chỗ trống bộ đọc thấy; không đơn vị nào có
    chỗ trống ngoài bản đồ — không có chỗ trống lạc."""
    docx, ban_do = km.dung_docx(spec)
    dv = _don_vi(docx)
    theo = {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d for d in dv if d.get("dia_chi")}
    for k, ds in ban_do.items():
        assert len(theo[k].get("cho_trong") or []) == len(ds), theo[k]["noi_dung"]
    co_cho = {k for k, d in theo.items() if d.get("cho_trong")}
    assert co_cho == set(ban_do)


def test_moi_truong_cua_cac_ben_la_mot_cho_tab_dung_nhan():
    docx, ban_do = km.dung_docx(_spec("hdld"))
    dv = {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d for d in _don_vi(docx) if d.get("dia_chi")}
    nhan = {}
    for k, ds in ban_do.items():
        for so, khoa in enumerate(ds):
            c = dv[k]["cho_trong"][so]
            if khoa and khoa[0] in ("nld", "nsdld") and c["kieu"] == "tab":
                assert khoa not in nhan, "mỗi trường một dòng"
                nhan[khoa] = (c["kieu"], c["nhan"])
    assert nhan[("nld", "ho_ten")] == ("tab", "Họ và tên")
    assert nhan[("nld", "so_dinh_danh")] == ("tab", "Số định danh cá nhân")
    assert nhan[("nsdld", "ten_to_chuc")] == ("tab", "Tên người sử dụng lao động")
    # Tên ở khối ký là chỗ trống "……" (không phải tab) của cùng trường.
    ky = [k for k, ds in ban_do.items() if ds == [("nld", "ho_ten")] and len(k[1]) == 3]
    assert ky, "chỗ họ tên dưới khối ký của người lao động"


def test_dong_ngay_cho_trong_ngay_thang_nam():
    docx, ban_do = km.dung_docx(_tong_quat("hanh_chinh"))
    dv = _don_vi(docx)
    nhan = [c["nhan"] for d in dv for c in d.get("cho_trong") or [] if "ngày" in d["noi_dung"]]
    assert {"ngày", "tháng", "năm"} <= set(nhan)


@pytest.mark.parametrize("spec", TAT_CA, ids=TEN)
def test_bang_dau_trang_va_khoi_ky_khong_vien_khong_o(spec):
    docx, _ = km.dung_docx(spec)
    for d in _don_vi(docx):
        if d.get("bang"):
            assert d["bang_vien"] is False
            assert all(c["kieu"] != "o" for c in d.get("cho_trong") or [])


@pytest.mark.parametrize("spec", TAT_CA, ids=TEN)
def test_cho_cham_trong_dieu_khoan_dung_bang_so_dau_cho_cua_spec(spec):
    """Đoạn điều khoản có đúng số chỗ trống bằng số "……" mô hình viết: dấu câu, số,
    "./." không mọc thêm chỗ trống nào."""
    docx, _ = km.dung_docx(spec)
    doan = {x.rstrip(".") for d in spec["dieu"] for x in d["doan"]}
    for d in _don_vi(docx):
        if d["noi_dung"].rstrip("./ ") in doan or d["noi_dung"].rstrip(".") in doan:
            assert len(d.get("cho_trong") or []) == d["noi_dung"].count(km.CHO), d["noi_dung"]


def _vi_tri_dong_ngay(docx: bytes) -> str:
    """ "than" (đoạn thân), "bang" (ô bảng) hay "khong" — chỗ dòng địa danh-ngày đứng."""
    for d in _don_vi(docx):
        if re.search(r"ngày …… tháng …… năm", d["noi_dung"]):
            return ("bang" if d.get("bang") else "than") + ":" + d["can_le"]
    return "khong"


@pytest.mark.parametrize(("ngay", "mong"), [("dau", "than:giua"), ("cuoi", "than:phai"), ("khong", "khong")])
def test_vi_tri_dong_ngay_theo_the_thuc(ngay, mong):
    d = km.nap("don_khoi_kien")
    spec = km.spec_tu(
        {**d, "the_thuc": {**d["the_thuc"], "ngay": ngay}}, tieu_de=None, trich_yeu=None, can_cu=[], dieu=[]
    )
    assert _vi_tri_dong_ngay(km.dung_docx(spec)[0]) == mong


def test_ngay_cot_phai_nam_trong_bang_dau_trang():
    assert _vi_tri_dong_ngay(km.dung_docx(_spec("cong_van"))[0]) == "bang:giua"


def test_kinh_gui_thut_30_mm():
    docx, _ = km.dung_docx(_spec("don_khoi_kien"))
    for p in _part(docx, "word/document.xml").iter(f"{_W}p"):
        chu = "".join(t.text or "" for t in p.iter(f"{_W}t"))
        if chu.startswith("Kính gửi"):
            trai = int(p.find(f"{_W}pPr/{_W}ind").get(f"{_W}left"))
            assert round(trai * 25.4 / 1440) == 30
            return
    raise AssertionError("không thấy dòng Kính gửi")


def test_dieu_danh_so_1_den_n_ten_da_bo_so():
    docx, _ = km.dung_docx(_tong_quat())
    chu = [d["noi_dung"] for d in _don_vi(docx)]
    tieu_de = [c for c in chu if c.startswith("Điều ")]
    assert tieu_de == ["Điều 1. Công việc và địa điểm làm việc", "Điều 2. Mức lương"]


@pytest.mark.parametrize("spec", TAT_CA, ids=TEN)
def test_bo_ap_dien_duoc_moi_cho_trong(spec):
    docx, _ = km.dung_docx(spec)
    dv = _don_vi(docx)
    phep = [
        {"loai": "dien", "don_vi": d["chi_so"], "cho_trong": c["so"], "gia_tri": f"GT{d['chi_so']}-{c['so']}"}
        for d in dv
        for c in d.get("cho_trong") or []
    ]
    assert phep
    ban, bao_cao = ap_dung_docx(docx, dv, phep)
    assert bao_cao["bo_qua"] == [] and len(bao_cao["da_ap"]) == len(phep)
    chu = "\n".join(d.noi_dung for d in doc("k.docx", ban).don_vi)
    assert all(p["gia_tri"] in chu for p in phep)


def test_ban_do_giai_moi_truong_cua_ben_ra_cho_trong():
    docx, ban_do = km.dung_docx(_tong_quat())
    khoa = {k for ds in ban_do.values() for k in ds if k}
    for b in ("ben_a", "ben_b"):
        truong = km.khung_tong_quat("hop_dong", [{"khoa": b, "loai": "ca_nhan" if b == "ben_a" else "to_chuc"}])
        for t in truong["ben"][0]["truong"]:
            assert (b, t) in khoa, (b, t)


def test_them_dieu_bat_buoc_chen_dung_vi_tri_voi_cho_trong_khi_tao():
    dieu, kq = km.them_dieu_bat_buoc(DIEU, "hdld")
    khoa = [d["key"] for d in dieu]
    # nsdld/nld là khung (khối các bên): không đòi thành điều khoản.
    assert "nsdld" not in khoa and "nld" not in khoa
    assert khoa.index("cong_viec") < khoa.index("thoi_han") < khoa.index("luong") < khoa.index("nang_luong")
    chen = [d for d in dieu if d.get("chen")]
    assert {d["key"] for d in chen} == set(kq["thieu"])
    # Hợp đồng: điều chèn không bao giờ trống — câu trung tính chừa chỗ điền, hay nội dung
    # chuẩn (`mau`) khi người gọi có.
    assert all(
        d["doan"] == [f"Các bên thỏa thuận về {d['ten'][:1].lower()}{d['ten'][1:]} như sau: {km.CHO}"] for d in chen
    )
    co_mau, _ = km.them_dieu_bat_buoc(DIEU, "hdld", mau={"thoi_han": "Hai bên phải thỏa thuận thời hạn."})
    assert next(d for d in co_mau if d["key"] == "thoi_han")["doan"] == ["Hai bên phải thỏa thuận thời hạn."]
    sua, kq2 = km.them_dieu_bat_buoc(DIEU, "hdld", tao=False)
    assert sua == DIEU and kq2["thieu"] == kq["thieu"]


def test_them_dieu_bat_buoc_don_tinh_khung_la_da_co():
    _, kq = km.them_dieu_bat_buoc([{"key": "yeu_cau", "ten": "", "doan": ["x"]}], "don_khoi_kien")
    assert kq["thieu"] == ["tai_lieu"], "ngày, Tòa án, các bên do khung dựng"


def test_loai_khong_checklist_khong_doi_gi():
    assert km.them_dieu_bat_buoc(DIEU, None) == (DIEU, {"thieu": [], "completeness": None})


def test_khuon_goc_tai_len_van_dung_tung_byte_va_khong_mang_can_cu():
    """Owner: dựng lại một khuôn gốc tải lên vẫn đúng 100%. Không phép nào → CHÍNH bytes
    vào; một dòng khuôn gốc lưu trước migration 041 (không `nguon`) là tệp tải lên."""
    from src.services import ban_thao

    goc, _ = km.dung_docx(_spec("don_khoi_kien", DIEU_DON))
    dv = _don_vi(goc)
    ban, bao_cao = ban_thao.ap_phep_sua("docx", goc, dv, [])
    assert ban is goc and bao_cao == {"da_ap": [], "bo_qua": []}
    k = {"dinh_dang": "docx", "so_trang": 1, "don_vi": dv}
    assert ban_thao._khuon_tu(k, "v", [])["nguon"] == "tai_len" and "can_cu" not in ban_thao._khuon_tu(k, "v", [])
    k_mau = {**k, "nguon": "khuon_mau"}
    assert ban_thao._khuon_tu(k_mau, "v", [], {"audit": {}, "clauses": []})["can_cu"] == []
