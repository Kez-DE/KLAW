"""Khuôn mẫu nhóm HỢP ĐỒNG — mọi checklist `la_hop_dong` và các hợp đồng mới (quyết định
2026-09-29 mục 3, 5–8; thiết kế `khuon-mau-thiet-ke.md` §1, §2, §7).

Không DB, không mô hình, không LibreOffice (trang thật: `test_khuon_mau_trang.py` phủ
mọi mục registry), trừ MỘT test `integration` CHỈ ĐỌC: căn cứ của mỗi hợp đồng phân giải
được thành văn bản đang HIỆN và còn hiệu lực, in đủ số và ngày.

Khoá năm điều cho mỗi loại hợp đồng:

1. Có mục registry, bố cục `hop_dong`, nguồn là mẫu Chính phủ ghi URL + SHA-256.
2. Mọi chỗ trống bộ dựng viết là chỗ trống bộ đọc thấy, và bộ áp điền được hết.
3. Mọi trường của các bên là một chỗ `tab` có nhãn; tên ở khối ký lấy từ trường tên.
4. Bản dựng lúc TẠO có đủ mọi Điều luật đòi (`them_dieu_bat_buoc`), theo đúng tên mục.
5. Hình thức luật đòi (công chứng, chứng thực, đăng ký) là một MỤC bắt buộc mang căn cứ.
"""

import io
import re
import zipfile

import pytest
from lxml import etree

from src.agents.graph_soan_thao import cac_loai as cac_checklist
from src.agents.graph_soan_thao import load_checklist_cached
from src.services import khuon_mau as km
from src.services.dien_khuon import ap_dung_docx
from src.services.doc_tai_lieu import doc
from src.services.tai_lieu import _hang_don_vi

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HOP_DONG = sorted(lo for lo in cac_checklist() if load_checklist_cached(lo).la_hop_dong)
# Hợp đồng mới của đợt này (quyết định 2026-09-29 mục 8; nghiên cứu `hop-dong.md` §2).
MOI = {
    "hop_dong_dat_coc",
    "hop_dong_van_chuyen_tai_san",
    "hop_dong_van_chuyen_hanh_khach",
    "hop_dong_tang_cho_tai_san",
    "hop_dong_tang_cho_quyen_su_dung_dat",
    "hop_dong_chuyen_nhuong_quyen_su_dung_dat",
    "hop_dong_thue_quyen_su_dung_dat",
    "hop_dong_dich_vu_bat_dong_san",
}
# Tệp mẫu Chính phủ D2 đã tải và băm (scratchpad `tt/mau-that/index.json`).
MAU_CHINH_PHU = {
    "goc/nd96-2024_congbao-939-940.pdf": "5b41a37fec6af317480a600f70cb4233ae852d6b297613ebe32222f531322174",
    "goc/nd96-2024_congbao-937-938.pdf": "3e6c0225bf008058b39aa82b3a0b0d22e01cd90ba2ee06c5335c870762fcff1f",
    "goc/nd145-2020_congbao-1205-1206.pdf": "38de13854df47d0e27ee497b86272f874742cea7e68f1be26d81587ff95f170b",
}


def _spec(loai: str) -> dict:
    """Bản TẠO của `loai`: khung registry + mọi Điều luật đòi (mỗi Điều một "……")."""
    dieu, _ = km.them_dieu_bat_buoc([], loai)
    return km.spec_tu(km.nap(loai), tieu_de=None, trich_yeu=None, can_cu=[], dieu=dieu)


def _dung(loai: str):
    docx, ban_do = km.dung_docx(_spec(loai))
    dv = [_hang_don_vi(d) for d in doc("k.docx", docx).don_vi]
    theo = {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d for d in dv if d.get("dia_chi")}
    return docx, ban_do, dv, theo


def _doan(docx: bytes):
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        return list(etree.fromstring(z.read("word/document.xml")).iter(f"{_W}p"))


def test_danh_sach_hop_dong_du_va_co_hop_dong_moi():
    assert len(HOP_DONG) == 21 and MOI <= set(HOP_DONG)


@pytest.mark.parametrize("loai", HOP_DONG)
def test_moi_hop_dong_co_khuon_mau_bo_cuc_hop_dong_nguon_mau_chinh_phu(loai):
    d = km.nap(loai)
    assert d["bo_cuc"] == "hop_dong" and d["tieu_de"] == load_checklist_cached(loai).tieu_de
    ng = d["nguon"]
    assert ng["loai"] == "tuong_tu" and ng["ghi_chu"]
    assert MAU_CHINH_PHU[ng["tep_d2"]] == ng["sha256"]
    assert ng["url"].startswith("https://congbaocdn.chinhphu.vn/")


@pytest.mark.parametrize("loai", HOP_DONG)
def test_moi_cho_trong_bo_doc_thay_va_bo_ap_dien_het(loai):
    docx, ban_do, dv, theo = _dung(loai)
    for k, ds in ban_do.items():
        assert len(theo[k].get("cho_trong") or []) == len(ds), theo[k]["noi_dung"]
    assert {k for k, d in theo.items() if d.get("cho_trong")} == set(ban_do), "chỗ trống lạc ngoài bản đồ"
    phep = [
        {"loai": "dien", "don_vi": d["chi_so"], "cho_trong": c["so"], "gia_tri": f" x{i}"}
        for i, d in enumerate(dv)
        for c in d.get("cho_trong") or []
    ]
    _, bao_cao = ap_dung_docx(docx, dv, phep)
    assert phep and not bao_cao["bo_qua"]


@pytest.mark.parametrize("loai", HOP_DONG)
def test_truong_cac_ben_la_cho_tab_co_nhan_va_ten_o_khoi_ky(loai):
    _, ban_do, _, theo = _dung(loai)
    d = km.nap(loai)
    tab, ky = {}, set()
    for k, ds in ban_do.items():
        for so, khoa in enumerate(ds):
            if not khoa or khoa[0] == km.BEN_VAN_BAN:
                continue
            c = theo[k]["cho_trong"][so]
            if c["kieu"] == "tab":
                assert c["nhan"], (khoa, theo[k]["noi_dung"])
                tab[khoa] = c["nhan"]
            else:
                ky.add(khoa)
    for b in d["ben"]:
        truong = b.get("truong") or [o for x in b.get("dong") or [] for o in km._cac_o(km._chuoi_cua_dong(x))]
        assert {(b["khoa"], t) for t in truong} <= set(tab), b["khoa"]
    assert ky == {(o["khoa"], o["ho_ten_tu"]) for o in d["ky"]["o"]}, "tên dưới chữ ký = trường tên của bên"
    assert [o["khoa"] for o in d["ky"]["o"]] == d["ky"]["thu_tu"]


@pytest.mark.parametrize("loai", HOP_DONG)
def test_nhan_dong_truong_khong_ket_bang_dau_cach(loai):
    """Bộ áp thêm MỘT dấu cách trước giá trị chỗ `tab`; nhãn kết bằng dấu cách thì trang
    ra "Họ và tên:  An" (hai dấu cách). Nhãn in sát dấu hai chấm như mẫu Chính phủ."""
    for p in _doan(km.dung_docx(_spec(loai))[0]):
        if p.find(f"{_W}r/{_W}tab") is None:
            continue
        truoc = "".join(t.text or "" for t in p.iter(f"{_W}t"))
        assert not truoc.endswith(" "), truoc


@pytest.mark.parametrize("loai", sorted(MOI | {"hop_dong_thue_tai_san", "hop_dong_vay", "hop_dong_mua_ban"}))
def test_khoi_cac_ben_thut_bang_le_chu_than_bai_nd96(loai):
    """NĐ 96/2024 Phụ lục II: "I. BÊN …" và các dòng "- …" thẳng lùi đầu dòng của thân
    bài; đoạn Điều khoản vẫn chỉ lùi DÒNG ĐẦU."""
    thut = round(12.7 * km._MM)
    doan = _doan(km.dung_docx(_spec(loai))[0])
    ben = [p for p in doan if "".join(t.text or "" for t in p.iter(f"{_W}t")).startswith(("I. BÊN", "II. BÊN", "- "))]
    assert ben and all(int(p.find(f"{_W}pPr/{_W}ind").get(f"{_W}left")) == thut for p in ben)
    # Đoạn thân Điều (canh đều) — không phải dòng tên dưới chữ ký (canh giữa).
    dieu = [
        p
        for p in doan
        if "".join(t.text or "" for t in p.iter(f"{_W}t")) == km.CHO
        and p.find(f"{_W}pPr/{_W}jc").get(f"{_W}val") == "both"
    ]
    assert dieu and all(p.find(f"{_W}pPr/{_W}ind").get(f"{_W}left") == "0" for p in dieu)


@pytest.mark.parametrize("loai", HOP_DONG)
def test_ban_tao_du_moi_dieu_luat_doi_dung_ten_muc(loai):
    cl = load_checklist_cached(loai)
    khong = set(cl.khong_bat_buoc.get("keys") or []) | km.khoa_khung(km.nap(loai))
    bat_buoc = [m for m in cl.muc if m["key"] not in khong]
    chu = [
        " ".join("".join(t.text or "" for t in p.iter(f"{_W}t")).split()) for p in _doan(km.dung_docx(_spec(loai))[0])
    ]
    tieu_de = [c for c in chu if re.match(r"Điều \d+\. ", c)]
    assert tieu_de == [f"Điều {n}. {m['ten']}" for n, m in enumerate(bat_buoc, 1)]
    _, info = km.them_dieu_bat_buoc([{"key": m["key"]} for m in bat_buoc], loai)
    assert info["thieu"] == [] and info["completeness"] == 1.0


@pytest.mark.parametrize(
    ("loai", "khoa", "can_cu"),
    [
        ("hop_dong_chuyen_nhuong_quyen_su_dung_dat", "cong_chung", "31/2024/QH15 > Điều 27 > Khoản 3 > Điểm a"),
        ("hop_dong_chuyen_nhuong_quyen_su_dung_dat", "dang_ky", "91/2015/QH13 > Điều 503"),
        ("hop_dong_tang_cho_quyen_su_dung_dat", "cong_chung", "31/2024/QH15 > Điều 27 > Khoản 3 > Điểm a"),
        ("hop_dong_tang_cho_quyen_su_dung_dat", "dang_ky", "91/2015/QH13 > Điều 503"),
    ],
)
def test_hinh_thuc_luat_doi_la_muc_bat_buoc_mang_can_cu(loai, khoa, can_cu):
    cl = load_checklist_cached(loai)
    muc = {m["key"]: m for m in cl.muc}
    assert muc[khoa]["can_cu"] == can_cu and khoa not in (cl.khong_bat_buoc.get("keys") or [])


@pytest.mark.parametrize(
    ("loai", "khoa", "can_cu"),
    [
        ("hop_dong_thue_quyen_su_dung_dat", "cong_chung", "31/2024/QH15 > Điều 27 > Khoản 3 > Điểm b"),
        ("hop_dong_tang_cho_tai_san", "bat_dong_san", "91/2015/QH13 > Điều 459 > Khoản 1"),
        ("hop_dong_van_chuyen_tai_san", "giay_van_tai", "35/2024/QH15 > Điều 61 > Khoản 1"),
    ],
)
def test_hinh_thuc_theo_yeu_cau_la_muc_tuy_chon_mang_can_cu(loai, khoa, can_cu):
    cl = load_checklist_cached(loai)
    assert {m["key"]: m["can_cu"] for m in cl.muc}[khoa] == can_cu
    assert khoa in cl.khong_bat_buoc["keys"]


@pytest.mark.integration
@pytest.mark.parametrize("loai", HOP_DONG)
def test_can_cu_cua_hop_dong_la_van_ban_dang_hien_du_so_va_ngay(loai):
    """CHỈ ĐỌC DB. Mọi `can_cu` của checklist là một điều khoản thật của văn bản đang
    HIỆN; khối căn cứ in một dòng cho mỗi văn bản đó, đủ số hiệu và ngày."""
    from src.agents import graph_soan_thao as gst
    from src.config import as_of_hieu_luc
    from src.services.checklist import cac_can_cu
    from src.services.db import get_engine
    from src.services.hien_thi import hien_thi_luc

    e, as_of = get_engine(), as_of_hieu_luc(None)
    _, cl, db = gst.requirements(loai)
    hien = gst.chi_van_ban_hien(db, hien_thi_luc(e, as_of))
    assert cac_can_cu(cl) <= {r["duong_dan"] for r in hien.values()}
    dong = gst.can_cu_van_ban_co_id(e, hien, as_of)
    assert {x["doc_id"] for x in dong} == {r["document_id"] for r in hien.values()}
    for x in dong:
        assert x["dong"].startswith("Căn cứ ") and x["dong"][-1] in ";.", x["dong"]
        assert re.search(r" số \S+/\S+ ngày \d{1,2} tháng \d{1,2} năm \d{4}", x["dong"]), x["dong"]


@pytest.mark.parametrize("loai", HOP_DONG)
def test_ten_duoi_chu_ky_thang_hang_giua_cac_cot(loai):
    """Khối ký nhiều cột: dòng tên (chỗ trống "……") của mọi cột nằm ở CÙNG thứ tự đoạn
    trong ô, dù nhãn vai hay ghi chú của mỗi bên dài ngắn khác nhau — căn chỗ ký thẳng
    hàng (chủ dự án 2026-09-29: "phải căn lề chuẩn chỗ kí")."""
    with zipfile.ZipFile(io.BytesIO(km.dung_docx(_spec(loai))[0])) as z:
        body = etree.fromstring(z.read("word/document.xml")).find(f"{_W}body")
    bang_ky = body.findall(f"{_W}tbl")[-1]
    vi_tri = [
        [i for i, p in enumerate(tc.findall(f"{_W}p")) if "".join(t.text or "" for t in p.iter(f"{_W}t")) == km.CHO]
        for tc in bang_ky.iter(f"{_W}tc")
    ]
    assert len(vi_tri) >= 2 and all(len(v) == 1 for v in vi_tri) and len({v[0] for v in vi_tri}) == 1, vi_tri
