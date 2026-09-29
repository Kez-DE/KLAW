"""Trích dẫn đầy đủ (quyết định 2026-09-28) — hàm THUẦN, không DB, không LLM.

`cach_trich` là câu trích theo đúng cách chính văn bản luật viết ("khoản 1 Điều 3
Nghị định số 90/2019/NĐ-CP ngày 15/11/2019 của Chính phủ"); `khoi_can_cu` là khối
"Căn cứ" mở đầu bản thảo theo khuôn lời mở đầu của văn bản luật.
"""

from datetime import date

from src.services.effectivity import EffectivityVerdict as V
from src.services.trich_dan import (
    cach_trich,
    dong_can_cu,
    khoi_can_cu,
    lien_ket,
    link_ban_ky,
    truong_trich_dan,
)

BLLD = {
    "id": "139264",
    "so_ky_hieu": "45/2019/QH14",
    "loai_van_ban": "Bộ luật",
    "ten": "Bộ Luật lao động số 45/2019/QH14",
    "co_quan_ban_hanh": "Quốc hội",
    "ngay_ban_hanh": date(2019, 11, 20),
    "ngay_hieu_luc": date(2021, 1, 1),
}
ND90 = {
    "id": "139094",
    "so_ky_hieu": "90/2019/NĐ-CP",
    "loai_van_ban": "Nghị định",
    "ten": "Nghị định số 90/2019/NĐ-CP Quy định mức lương tối thiểu vùng đối với người lao động",
    "co_quan_ban_hanh": "Chính phủ",
    "ngay_ban_hanh": date(2019, 11, 15),
    "ngay_hieu_luc": date(2020, 1, 1),
}
ND293 = {
    "id": "183939",
    "so_ky_hieu": "293/2025/NĐ-CP",
    "loai_van_ban": "Nghị định",
    "ten": "Nghị định số 293/2025/NĐ-CP Quy định mức lương tối thiểu đối với người lao động.",
    "co_quan_ban_hanh": "Chính phủ",
    "ngay_ban_hanh": date(2025, 11, 10),
    "ngay_hieu_luc": date(2026, 1, 1),
}
TT10 = {
    "id": "146696",
    "so_ky_hieu": "10/2020/TT-BLĐTBXH",
    "loai_van_ban": "Thông tư",
    "ten": "Thông tư số 10/2020/TT-BLĐTBXH Quy định chi tiết một số điều của Bộ luật Lao động",
    "co_quan_ban_hanh": "Bộ Lao động - Thương binh và Xã hội",
    "ngay_ban_hanh": date(2020, 11, 12),
}


def _trich(duong_dan, v):
    return cach_trich(
        duong_dan,
        v.get("loai_van_ban"),
        v.get("so_ky_hieu"),
        v.get("ngay_ban_hanh"),
        v.get("co_quan_ban_hanh"),
        v.get("ten"),
    )


# ───────────────────────────────────────────────────────────── cach_trich


def test_nghi_dinh_khoan_dieu_dung_mau_cua_chinh_van_ban_luat():
    assert _trich("90/2019/NĐ-CP > Điều 3 > Khoản 1", ND90) == (
        "khoản 1 Điều 3 Nghị định số 90/2019/NĐ-CP ngày 15/11/2019 của Chính phủ"
    )


def test_bo_luat_goi_bang_TEN_viet_hoa_dung_quy_tac_va_cap_van_ban():
    """Tên trong DB là "Bộ Luật lao động số 45/2019/QH14" — câu trích dùng tên
    gọi chuẩn "Bộ luật Lao động", không chép nguyên chữ hoa/thường lệch."""
    assert _trich(None, BLLD) == "Bộ luật Lao động số 45/2019/QH14 ngày 20/11/2019 của Quốc hội"


def test_duong_dan_toi_DIEM_va_HANG_BANG_viet_thuong_theo_cach_luat_viet():
    assert _trich("45/2019/QH14 > Điều 21 > Khoản 1 > Điểm a", BLLD) == (
        "điểm a khoản 1 Điều 21 Bộ luật Lao động số 45/2019/QH14 ngày 20/11/2019 của Quốc hội"
    )
    nd38 = {**ND90, "so_ky_hieu": "38/2022/NĐ-CP", "ngay_ban_hanh": date(2022, 6, 12)}
    assert _trich("38/2022/NĐ-CP > Điều 3 > Khoản 1 > Vùng III", nd38) == (
        "vùng III khoản 1 Điều 3 Nghị định số 38/2022/NĐ-CP ngày 12/06/2022 của Chính phủ"
    )


def test_cap_tren_dieu_giu_viet_hoa_va_mo_dau_khong_phai_vi_tri():
    assert _trich(
        "91/2015/QH13 > Phần thứ ba > Chương XVI > Mục 5",
        {**BLLD, "ten": "Bộ luật Dân sự số 91/2015/QH13", "so_ky_hieu": "91/2015/QH13"},
    ).startswith("Mục 5 Chương XVI Phần thứ ba Bộ luật Dân sự số 91/2015/QH13")
    assert _trich("90/2019/NĐ-CP > Mở đầu", ND90) == "Nghị định số 90/2019/NĐ-CP ngày 15/11/2019 của Chính phủ"


def test_luat_thong_tu_quyet_dinh():
    luat = {
        "so_ky_hieu": "84/2015/QH13",
        "loai_van_ban": "Luật",
        "ten": "Luật An toàn, vệ sinh lao động số 84/2015/QH13",
        "co_quan_ban_hanh": "Quốc hội",
        "ngay_ban_hanh": date(2015, 6, 25),
    }
    assert _trich("84/2015/QH13 > Điều 7", luat) == (
        "Điều 7 Luật An toàn, vệ sinh lao động số 84/2015/QH13 ngày 25/06/2015 của Quốc hội"
    )
    assert _trich("10/2020/TT-BLĐTBXH > Điều 3 > Khoản 5 > Điểm c", TT10) == (
        "điểm c khoản 5 Điều 3 Thông tư số 10/2020/TT-BLĐTBXH ngày 12/11/2020 của Bộ Lao động - Thương binh và Xã hội"
    )
    # Tên DB không có chữ "số" — câu trích vẫn theo mẫu "Quyết định số …".
    qd = {
        "so_ky_hieu": "71/2026/QĐ-UBND",
        "loai_van_ban": "Quyết định",
        "ten": "Quyết định 71/2026/QĐ-UBND Quy định việc rà soát",
        "co_quan_ban_hanh": "UBND tỉnh Cà Mau",
        "ngay_ban_hanh": "2026-03-05",
    }
    assert _trich(None, qd) == "Quyết định số 71/2026/QĐ-UBND ngày 05/03/2026 của UBND tỉnh Cà Mau"


def test_ten_viet_HOA_chu_SO_khong_lap_lai_so():
    """Tên trong kho viết hoa cả chữ "SỐ" ("LUẬT DÂN SỐ SỐ 113/2025/QH15") — câu
    trích từng in "Luật Dân số số số 113/2025/QH15", đúng câu nút 'Sao chép trích
    dẫn' chép đi."""
    dan_so = {
        "so_ky_hieu": "113/2025/QH15",
        "loai_van_ban": "Luật",
        "ten": "LUẬT DÂN SỐ SỐ 113/2025/QH15",
        "co_quan_ban_hanh": "Quốc hội",
        "ngay_ban_hanh": date(2025, 12, 10),
    }
    assert _trich("113/2025/QH15 > Điều 5 > Khoản 1", dan_so) == (
        "khoản 1 Điều 5 Luật Dân số số 113/2025/QH15 ngày 10/12/2025 của Quốc hội"
    )
    assert dong_can_cu(dan_so) == "Căn cứ Luật Dân số số 113/2025/QH15 ngày 10 tháng 12 năm 2025"
    ma_tuy = {"so_ky_hieu": "120/2025/QH15", "loai_van_ban": "Luật", "ten": "LUẬT PHÒNG, CHỐNG MA TÚY SỐ 120/2025/QH15"}
    assert _trich(None, ma_tuy) == "Luật Phòng, chống ma túy số 120/2025/QH15"


def test_hien_phap_goi_bang_ten_vi_khong_co_so_hieu():
    """Hiến pháp 2013 không có số hiệu: kho lưu tiêu đề gateway ("Hiến pháp năm 2013")
    làm số hiệu. Câu trích từng in "Hiến pháp số Hiến pháp năm 2013"."""
    hien_phap = {
        "so_ky_hieu": "Hiến pháp năm 2013",
        "loai_van_ban": "Hiến pháp",
        "ten": "Hiến pháp năm 2013",
        "co_quan_ban_hanh": "Quốc hội",
        "ngay_ban_hanh": date(2013, 11, 28),
    }
    assert _trich("Hiến pháp năm 2013 > Điều 119 > Khoản 1", hien_phap) == (
        "khoản 1 Điều 119 Hiến pháp năm 2013 ngày 28/11/2013 của Quốc hội"
    )
    assert truong_trich_dan(hien_phap)["ten_van_ban"] == "Hiến pháp năm 2013"


def test_thieu_phan_nao_thi_BO_phan_do_khong_dien_cho_trong():
    assert _trich("90/2019/NĐ-CP > Điều 3", {**ND90, "co_quan_ban_hanh": None}) == (
        "Điều 3 Nghị định số 90/2019/NĐ-CP ngày 15/11/2019"
    )
    assert _trich(None, {**ND90, "ngay_ban_hanh": None}) == "Nghị định số 90/2019/NĐ-CP của Chính phủ"
    # Luật không có tên riêng trong DB ("Thủ đô") vẫn gọi được bằng loại + tên.
    assert _trich(None, {"so_ky_hieu": "25/2012/QH13", "loai_van_ban": "Luật", "ten": "Thủ đô"}) == (
        "Luật Thủ đô số 25/2012/QH13"
    )
    # 'Không số' không phải một số hiệu — không in "số Không số".
    khong_so = {
        "so_ky_hieu": "Không số",
        "loai_van_ban": "Luật",
        "ten": "Luật Phá sản doanh nghiệp số Không số",
        "ngay_ban_hanh": date(1993, 12, 30),
    }
    assert _trich(None, khong_so) == "Luật Phá sản doanh nghiệp ngày 30/12/1993"
    assert _trich(None, {}) is None


# ───────────────────────────────────────────────────────────── lien_ket


def test_lien_ket_vbpl_truoc_chinhphu_chi_https_dung_mau():
    vbpl = "https://vbpl.vn/van-ban/chi-tiet/139264"
    cp = "https://vanban.chinhphu.vn/?pageid=27160&docid=198540"
    assert lien_ket(vbpl, cp) == vbpl
    assert lien_ket(None, cp) == cp
    assert lien_ket(None, None) is None
    # Mẫu cũ `vbpq-toanvan.aspx?ItemID=` chuyển hướng về TRANG CHỦ — không phải link.
    assert lien_ket("https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=139264", None) is None
    assert lien_ket("http://vbpl.vn/van-ban/chi-tiet/139264", cp) == cp, "chỉ https"
    assert lien_ket("https://evil.example/van-ban/chi-tiet/1", None) is None
    assert lien_ket(None, "javascript:alert(1)") is None


def test_link_ban_ky_chi_pdf_https_tren_datafiles_chinhphu():
    """Quyết định 2026-09-28 mục 9: nút "Bản gốc có chữ ký (PDF)" mở ra dưới tên
    Cổng TTĐT Chính phủ, nên chỉ một tệp PDF trên đúng máy chủ tệp của cổng."""
    pdf = "https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/12/145.signed.pdf"
    assert link_ban_ky(pdf) == pdf
    assert link_ban_ky("https://datafiles.chinhphu.vn/cpp/files/vbpq/2013/05/44-ND.PDF")
    for sai in (
        None,
        "",
        "http://datafiles.chinhphu.vn/cpp/files/vbpq/2020/12/145.signed.pdf",
        "https://datafiles.chinhphu.vn.evil.example/145.signed.pdf",
        "https://evil.example/https://datafiles.chinhphu.vn/145.pdf",
        "https://user@datafiles.chinhphu.vn/cpp/145.pdf",
        "https://datafiles.chinhphu.vn:8443/cpp/145.pdf",
        "https://datafiles.chinhphu.vn:abc/cpp/145.pdf",
        "https://datafiles.chinhphu.vn/cpp/1/Logo/quoc-huy.png",
        "https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/12/145.doc",
        "https://vanban.chinhphu.vn/?pageid=27160&docid=198540",
    ):
        assert link_ban_ky(sai) is None, sai


def test_truong_trich_dan_ngay_ISO_va_NULL_di_nguyen():
    t = truong_trich_dan({**BLLD, "link_vbpl": None, "link_chinhphu": None}, "45/2019/QH14 > Điều 21")
    assert t == {
        "ten_van_ban": "Bộ Luật lao động số 45/2019/QH14",
        "loai_van_ban": "Bộ luật",
        "co_quan_ban_hanh": "Quốc hội",
        "ngay_ban_hanh": "2019-11-20",
        "ngay_hieu_luc": "2021-01-01",
        "lien_ket": None,
        "cach_trich": "Điều 21 Bộ luật Lao động số 45/2019/QH14 ngày 20/11/2019 của Quốc hội",
    }
    rong = truong_trich_dan({"so_ky_hieu": "x", "ten": ""})
    assert rong["co_quan_ban_hanh"] is None and rong["ngay_ban_hanh"] is None and rong["lien_ket"] is None


# ───────────────────────────────────────────────────────────── khối "Căn cứ"


def test_dong_can_cu_theo_khuon_loi_mo_dau():
    assert dong_can_cu(BLLD) == "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019"
    assert dong_can_cu(ND293) == (
        "Căn cứ Nghị định số 293/2025/NĐ-CP ngày 10 tháng 11 năm 2025 của Chính phủ"
        " quy định mức lương tối thiểu đối với người lao động"
    )
    # Ngày dưới 10 và tháng 1, 2 ghi thêm số 0 — như chính lời mở đầu trong kho
    # ("ngày 17 tháng 02 năm 2017", "ngày 08 tháng 12").
    assert "ngày 05 tháng 02 năm 2020" in dong_can_cu({**ND90, "ngay_ban_hanh": date(2020, 2, 5)})
    assert "ngày 20 tháng 6 năm 2020" in dong_can_cu({**ND90, "ngay_ban_hanh": date(2020, 6, 20)})


def test_khoi_can_cu_xep_theo_thu_bac_khu_trung_bo_van_ban_het_hieu_luc():
    verdict = {
        "139264": V.mot_phan_khong_xac_dinh,
        "183939": V.con_hieu_luc,
        "146696": V.bi_sua_doi,
        "139094": V.bi_thay_the,
    }
    khoi = khoi_can_cu([TT10, ND90, BLLD, ND293, BLLD], verdict.__getitem__)
    assert khoi == [
        "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019;",
        "Căn cứ Nghị định số 293/2025/NĐ-CP ngày 10 tháng 11 năm 2025 của Chính phủ"
        " quy định mức lương tối thiểu đối với người lao động;",
        "Căn cứ Thông tư số 10/2020/TT-BLĐTBXH ngày 12 tháng 11 năm 2020 của Bộ Lao động - Thương binh"
        " và Xã hội quy định chi tiết một số điều của Bộ luật Lao động.",
    ]
    assert not any("90/2019" in d for d in khoi), "văn bản đã bị thay thế không được làm căn cứ"
    assert not any("hiệu lực" in d for d in khoi), "khối Căn cứ không phán về hiệu lực"


def test_khoi_can_cu_KHONG_dan_nghi_dinh_the_thuc_van_thu():
    """NĐ 30/2020 (công tác văn thư) chỉ quy định THỂ THỨC — checklist dẫn nó cho
    quốc hiệu, số ký hiệu, nơi nhận — nên không phải căn cứ ban hành của văn bản
    người dùng đem đi ký, kể cả khi còn hiệu lực."""
    ldn = {
        "id": "1",
        "so_ky_hieu": "59/2020/QH14",
        "loai_van_ban": "Luật",
        "ten": "Luật Doanh nghiệp số 59/2020/QH14",
        "ngay_ban_hanh": date(2020, 6, 17),
    }
    nd30 = {
        "id": "2",
        "so_ky_hieu": "30/2020/NĐ-CP",
        "loai_van_ban": "Nghị định",
        "ten": "Nghị định số 30/2020/NĐ-CP về công tác văn thư",
        "co_quan_ban_hanh": "Chính phủ",
        "ngay_ban_hanh": date(2020, 3, 5),
    }
    luon_con = lambda _i: V.con_hieu_luc  # noqa: E731
    assert khoi_can_cu([ldn, nd30], luon_con) == ["Căn cứ Luật Doanh nghiệp số 59/2020/QH14 ngày 17 tháng 6 năm 2020."]
    assert khoi_can_cu([nd30], luon_con) == [], "chỉ có nguồn thể thức thì không có khối"


def test_khoi_can_cu_chi_nhan_van_ban_CON_hieu_luc():
    for v in (V.het_hieu_luc, V.bi_thay_the, V.chua_hieu_luc, V.chua_xac_dinh, V.can_doi_chieu_tay):
        assert khoi_can_cu([BLLD], lambda _i, v=v: v) == [], v
    assert khoi_can_cu([], lambda _i: V.con_hieu_luc) == []
