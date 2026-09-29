"""Khuôn mẫu nhóm hôn nhân và gia đình — ba loại KHÔNG checklist (thiết kế
`khuon-mau-thiet-ke.md` §7 "New types"): đơn yêu cầu công nhận thuận tình ly hôn (Mẫu
01-VDS NQ 04/2018/NQ-HĐTP), văn bản thỏa thuận phân chia tài sản chung của vợ chồng,
văn bản thỏa thuận nuôi con sau khi ly hôn.

Không DB, không mô hình, không LibreOffice (trang thật ở `test_khuon_mau_trang.py`,
căn cứ trên kho thật ở `test_khuon_mau_hon_nhan_kho.py`). Khoá bốn lời hứa:

1. Mục registry nạp được, không checklist, nguồn ghi rõ.
2. Mọi chỗ trống bộ dựng viết, bộ đọc của khuôn gốc thấy đúng và bộ áp điền được; mỗi
   trường của các bên là MỘT chỗ tab đúng nhãn, tên dưới chữ ký là chỗ của cùng trường.
3. Điều luật đòi luôn có: tạo bản thảo mà mô hình không viết điều nào vẫn đủ các điều
   (mục) bắt buộc, để trống "……" — không bịa.
4. Căn cứ chỉ từ văn bản được HIỆN, qua đúng bộ lọc của checklist; không có văn bản
   nào thì không in dòng nào — không bao giờ "……" thay chỗ một dòng căn cứ.
"""

import pytest

from src.agents import graph_tra_cuu as g
from src.agents.graph_soan_thao import cac_loai as cac_checklist
from src.services import khuon_mau as km
from src.services.dien_khuon import ap_dung_docx
from src.services.doc_tai_lieu import doc
from src.services.tai_lieu import _hang_don_vi

LOAI = ["don_thuan_tinh_ly_hon", "thoa_thuan_chia_tai_san_chung", "thoa_thuan_nuoi_con"]
BAT_BUOC = {
    "don_thuan_tinh_ly_hon": ["yeu_cau", "ly_do", "tai_lieu"],
    "thoa_thuan_chia_tai_san_chung": ["tai_san_chung", "phan_chong", "phan_vo"],
    "thoa_thuan_nuoi_con": [
        "nguoi_truc_tiep_nuoi",
        "cap_duong",
        "phuong_thuc_cap_duong",
        "quyen_ben_khong_nuoi",
        "quyen_ben_nuoi",
    ],
}
CAN_CU = [
    {"dong": "Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11 năm 2015;", "doc_id": "95942"},
    {"dong": "Căn cứ Luật Hôn nhân và gia đình số 52/2014/QH13 ngày 19 tháng 6 năm 2014.", "doc_id": "36870"},
]


def _spec(loai: str, dieu: list[dict] | None = None, can_cu: list[dict] = CAN_CU) -> dict:
    if dieu is None:
        dieu, _ = km.them_dieu_bat_buoc([], loai)
    return km.spec_tu(km.nap(loai), tieu_de=None, trich_yeu=None, can_cu=can_cu, dieu=dieu)


def _don_vi(docx: bytes) -> list[dict]:
    return [_hang_don_vi(d) for d in doc("k.docx", docx).don_vi]


def _chu(docx: bytes) -> list[str]:
    return [d["noi_dung"] for d in _don_vi(docx)]


@pytest.mark.parametrize("loai", LOAI)
def test_nap_duoc_khong_checklist_va_moi_muc_bat_buoc_co_dieu_luat(loai):
    d = km.nap(loai)
    assert loai not in cac_checklist(), "loại registry thuần: đường chat v3, không phiên checklist"
    muc = d["muc"]
    assert [m["key"] for m in muc if m.get("bat_buoc", True)] == BAT_BUOC[loai]
    assert all(m.get("can_cu") for m in muc if m.get("bat_buoc", True)), "điều bắt buộc mở được điều luật của nó"
    goc = {x.split(" > ")[0] for x in [*(d.get("can_cu") or []), *(m["can_cu"] for m in muc if m.get("can_cu"))]}
    assert goc <= {"52/2014/QH13", "92/2015/QH13", "91/2015/QH13"}


@pytest.mark.parametrize("loai", LOAI)
@pytest.mark.parametrize("co_dieu", [False, True], ids=["chi_bat_buoc", "co_dieu_mo_hinh"])
def test_ban_do_khop_bo_doc_va_bo_ap_dien_het(loai, co_dieu):
    dieu = None
    if co_dieu:
        dieu, _ = km.them_dieu_bat_buoc(
            [{"key": BAT_BUOC[loai][0], "ten": "Nội dung", "doan": ["Hai bên thống nhất: ……", "Mỗi bên giữ ……."]}], loai
        )
    docx, ban_do = km.dung_docx(_spec(loai, dieu))
    dv = _don_vi(docx)
    theo = {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d for d in dv if d.get("dia_chi")}
    for k, ds in ban_do.items():
        assert len(theo[k].get("cho_trong") or []) == len(ds), theo[k]["noi_dung"]
    assert {k for k, d in theo.items() if d.get("cho_trong")} == set(ban_do), "không chỗ trống lạc"
    phep = [
        {"loai": "dien", "don_vi": d["chi_so"], "cho_trong": c["so"], "gia_tri": f"GT{d['chi_so']}-{c['so']}"}
        for d in dv
        for c in d.get("cho_trong") or []
    ]
    ban, bao_cao = ap_dung_docx(docx, dv, phep)
    assert bao_cao["bo_qua"] == [] and len(bao_cao["da_ap"]) == len(phep)
    chu = "\n".join(x.noi_dung for x in doc("k.docx", ban).don_vi)
    assert all(p["gia_tri"] in chu for p in phep)
    assert not any(c in chu for c in "{}[]⟦⟧¶<>")


NHAN = {
    "don_thuan_tinh_ly_hon": {
        ("chong", "ho_ten"): "1. Người yêu cầu giải quyết việc dân sự (chồng):",
        ("vo", "ho_ten"): "2. Người yêu cầu giải quyết việc dân sự (vợ):",
        ("vo", "so_dinh_danh"): "Số định danh cá nhân:",
        ("vo", "dien_thoai"): "Số điện thoại (nếu có):",
        ("vo", "fax"): "; Fax (nếu có):",
        ("chong", "thu_dien_tu"): "Địa chỉ thư điện tử (nếu có):",
    },
    "thoa_thuan_chia_tai_san_chung": {
        ("chong", "ho_ten"): "- Họ và tên:",
        ("vo", "so_dinh_danh"): "- Số định danh cá nhân:",
        ("vo", "noi_cu_tru"): "- Nơi cư trú:",
    },
    "thoa_thuan_nuoi_con": {
        ("chong", "ho_ten"): "- Họ và tên:",
        ("con_thu_nhat", "ho_ten"): "- Họ và tên con thứ nhất:",
        ("con_thu_hai", "ngay_sinh"): "- Ngày sinh:",
    },
}


def _nhan_gan(nhan: str) -> str:
    return " ".join(nhan.split())


@pytest.mark.parametrize("loai", LOAI)
def test_truong_cac_ben_la_mot_tab_dung_nhan_va_ten_duoi_chu_ky(loai):
    docx, ban_do = km.dung_docx(_spec(loai))
    dv = {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d for d in _don_vi(docx) if d.get("dia_chi")}
    tab, cham = {}, []
    for k, ds in ban_do.items():
        for so, khoa in enumerate(ds):
            if not khoa:
                continue
            c = dv[k]["cho_trong"][so]
            if c["kieu"] == "tab":
                assert khoa not in tab, f"{khoa}: mỗi trường một dòng"
                tab[khoa] = dv[k]["noi_dung"][: c["dau"]]
            else:
                cham.append(khoa)
    for khoa, nhan in NHAN[loai].items():
        assert _nhan_gan(tab[khoa]).endswith(_nhan_gan(nhan)), (khoa, tab[khoa])
    # Tên dưới chữ ký của MỖI người ký là chỗ trống "……" của chính trường họ tên.
    ky = km.nap(loai)["ky"]
    assert {(k, "ho_ten") for k in ky["thu_tu"]} <= set(cham)


@pytest.mark.parametrize("loai", LOAI)
def test_dieu_bat_buoc_luon_co_khi_tao_va_chi_la_phat_hien_khi_sua(loai):
    dieu, kq = km.them_dieu_bat_buoc([], loai)
    assert [d["key"] for d in dieu] == BAT_BUOC[loai] == kq["thieu"]
    assert all(d["doan"] == [km.CHO] and d.get("chen") for d in dieu)
    sua, kq2 = km.them_dieu_bat_buoc([], loai, tao=False)
    assert sua == [] and kq2["thieu"] == BAT_BUOC[loai]
    # Một điều mô hình viết (không bắt buộc, có khoá) giữ chỗ; điều thiếu chèn đúng thứ tự.
    ten = {m["key"]: m["ten"] for m in km.nap(loai)["muc"]}
    chu = _chu(km.dung_docx(_spec(loai, dieu))[0])
    if km.nap(loai)["bo_cuc"] == "hop_dong":
        assert [c for c in chu if c.startswith("Điều ")] == [
            f"Điều {n}. {ten[k]}" for n, k in enumerate(BAT_BUOC[loai], 1)
        ]
    else:
        nhan = {m["muc"]: m["nhan"] for m in km.nap(loai)["than"] if "muc" in m}
        for k in BAT_BUOC[loai]:
            assert any(c.startswith(nhan[k]) for c in chu), nhan[k]


def test_dieu_mo_hinh_giu_vi_tri_dieu_thieu_chen_theo_thu_tu_muc():
    viet = [{"key": "cap_duong", "ten": "Cấp dưỡng", "doan": ["Mức cấp dưỡng là …… đồng mỗi tháng."]}]
    dieu, kq = km.them_dieu_bat_buoc(viet, "thoa_thuan_nuoi_con")
    assert [d["key"] for d in dieu] == BAT_BUOC["thoa_thuan_nuoi_con"]
    assert dieu[1] == viet[0] and "cap_duong" not in kq["thieu"]


@pytest.mark.parametrize("loai", ["thoa_thuan_chia_tai_san_chung", "thoa_thuan_nuoi_con"])
def test_thoa_thuan_in_can_cu_khi_co_va_bo_han_khi_khong(loai):
    co = _chu(km.dung_docx(_spec(loai))[0])
    assert [c for c in co if c.startswith("Căn cứ")] == [x["dong"] for x in CAN_CU]
    khong = _chu(km.dung_docx(_spec(loai, can_cu=[]))[0])
    assert not [c for c in khong if c.startswith("Căn cứ")]
    # Chỗ dòng căn cứ không thành một dòng trống: sau tên loại là ngay câu "gồm".
    i = khong.index(km.nap(loai)["the_thuc"]["ten_loai"][-1])
    assert khong[i + 1] == "Hai bên chúng tôi gồm:"


def test_don_theo_mau_01_vds_khong_in_can_cu_ngay_o_cuoi_hai_nguoi_ky():
    docx, _ = km.dung_docx(_spec("don_thuan_tinh_ly_hon"))
    dv = _don_vi(docx)
    chu = [d["noi_dung"] for d in dv]
    assert not [c for c in chu if c.startswith("Căn cứ")], "Mẫu 01-VDS không có khối căn cứ"
    assert chu[2:5] == [
        "ĐƠN YÊU CẦU",
        "GIẢI QUYẾT VIỆC DÂN SỰ",
        "(V/v: Yêu cầu công nhận thuận tình ly hôn, thỏa thuận nuôi con, chia tài sản khi ly hôn)",
    ]
    kinh_gui = next(d for d in dv if d["noi_dung"].startswith("Kính gửi"))
    assert kinh_gui["can_le"] == "giua"
    ngay = next(i for i, c in enumerate(chu) if "ngày …… tháng …… năm" in c)
    assert dv[ngay]["can_le"] == "phai" and chu[ngay - 1].startswith("Tôi (chúng tôi) cam kết")
    ky = [d for d in dv[ngay + 1 :] if d.get("bang")]
    assert sum(c.startswith("NGƯỜI YÊU CẦU") for d in ky for c in [d["noi_dung"]]) == 2
    # Danh mục tài liệu đánh số "1." "2." "3." như mẫu, mỗi dòng một chỗ dẫn chấm.
    so = [d for d in dv if d["noi_dung"] in ("1.", "2.", "3.")]
    assert [d["noi_dung"] for d in so] == ["1.", "2.", "3."]
    assert all([c["kieu"] for c in d["cho_trong"]] == ["tab"] for d in so)


def _db_gia(loai: str) -> dict[int, dict]:
    d = km.nap(loai)
    duong = sorted({*(d.get("can_cu") or []), *(m["can_cu"] for m in d["muc"] if m.get("can_cu"))})
    doc_id = {"52/2014/QH13": "36870", "91/2015/QH13": "95942", "92/2015/QH13": "96115"}
    return {
        i: {"id": i, "document_id": doc_id[x.split(" > ")[0]], "duong_dan": x, "noi_dung": f"Nội dung {x}"}
        for i, x in enumerate(duong, 1)
    }


@pytest.mark.parametrize("loai", LOAI)
def test_nap_khuon_mau_can_cu_chi_tu_van_ban_hien(monkeypatch, loai):
    """Loại registry thuần đi CÙNG bộ lọc của checklist: điều luật của văn bản ẩn không
    thành căn cứ; dòng căn cứ khung chỉ dựng khi mẫu in khối căn cứ."""
    db = _db_gia(loai)
    nhan: dict = {}
    monkeypatch.setattr(g.gst, "provisions_theo_duong_dan", lambda dd: {k: v for k, v in db.items()})
    # BLDS ẩn: chỉ Luật HNGĐ và BLTTDS được hiện.
    monkeypatch.setattr(g, "hien_thi_luc", lambda engine, as_of: frozenset({"36870", "96115"}))

    def _dong(engine, hien, as_of):
        nhan["hien"] = hien
        return [{"dong": f"Căn cứ {i}.", "doc_id": i} for i in sorted({r["document_id"] for r in hien.values()})]

    monkeypatch.setattr(g.gst, "can_cu_van_ban_co_id", _dong)
    ng = g._nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": loai}})["khuon_mau_ngu_canh"]
    d = km.nap(loai)
    assert ng["loai"] == loai and ng["bat_buoc"] == BAT_BUOC[loai]
    assert set(ng["khoa"]) == {m["key"] for m in d["muc"]}
    for m in ng["muc"]:
        dd = next(x["can_cu"] for x in d["muc"] if x["key"] == m["key"])
        if dd.startswith("91/2015/QH13"):
            assert m.get("can_cu") is None and m["trich"] == "", "văn bản ẩn không thành căn cứ"
        else:
            assert m["can_cu"]["duong_dan"] == dd and m["trich"] == f"Nội dung {dd}"
    if d["the_thuc"].get("can_cu"):
        assert {r["document_id"] for r in nhan["hien"].values()} <= {"36870", "96115"}
        assert ng["can_cu"] and all(x["doc_id"] in {"36870", "96115"} for x in ng["can_cu"])
    else:
        assert ng["can_cu"] == []
