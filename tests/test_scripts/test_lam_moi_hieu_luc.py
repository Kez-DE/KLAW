"""Hai phép thuần của `scripts/lam_moi_hieu_luc.py`: đọc cột hiệu lực từ một
response gateway, và phép kiểm máy một trang vbpl.vn (quyết định 2026-09-28 mục 2:
HTTP 200, tiêu đề chứa đúng số hiệu, ngày ban hành trên trang = ngày trong kho)."""

from datetime import date

import pytest

from scripts.lam_moi_hieu_luc import cot_tu_gateway, kiem_trang_vbpl

# Đầu trang thật của vbpl.vn (scratchpad kiểm kho 2026-09-28, 139264), rút gọn.
DAU_BLLD = (
    "<html><head><title>Bộ luật 45/2019/QH14 của Quốc hội | CSDL quốc gia về pháp luật</title>"
    '<link rel="canonical" href="https://vbpl.vn/van-ban/chi-tiet/bo-luat-lao-dong-so-45-2019-qh14--139264"/>'
    '<meta property="article:published_time" content="2019-11-19T17:00:00.000Z"/>'
)
CANON = "https://vbpl.vn/van-ban/chi-tiet/bo-luat-lao-dong-so-45-2019-qh14--139264"
URL = "https://vbpl.vn/van-ban/chi-tiet/139264"


def test_cot_tu_gateway_doc_ma_ngay_co_quan():
    d = {
        "docNum": "45/2019/QH14",
        "effStatus": {"code": "HHL1P", "name": "Hết hiệu lực một phần"},
        "effFrom": "2021-01-01T00:00:00",
        "effTo": None,
        "issueDate": "2019-11-20T00:00:00",
        "agencyName": " Quốc hội ",
    }
    assert cot_tu_gateway(d) == {
        "so_ky_hieu": "45/2019/QH14",
        "tinh_trang": "HHL1P",
        "ngay_hieu_luc": date(2021, 1, 1),
        "ngay_het_hieu_luc": None,
        "ngay_ban_hanh": date(2019, 11, 20),
        "co_quan": "Quốc hội",
    }


def test_CCHL_la_chua_hieu_luc_khong_phai_chua_ro():
    """Gateway có mã thứ tư: 'CCHL' = 'Chưa có hiệu lực' (04/2026/QH16, effFrom
    2027-01-01, đo 2026-09-28). Tình trạng ĐÃ BIẾT — không được rơi về 'chưa rõ'."""
    assert cot_tu_gateway({"effStatus": {"code": "CCHL", "name": "Chưa có hiệu lực"}})["tinh_trang"] == "chua_hieu_luc"


@pytest.mark.parametrize("eff", [None, {}, {"code": "XYZ"}])
def test_ma_la_hoac_thieu_thanh_chua_xac_dinh(eff):
    """Không đoán: một mã gateway chưa biết là 'chưa rõ tình trạng' (bị ẩn), không phải CHL."""
    assert cot_tu_gateway({"effStatus": eff})["tinh_trang"] == "chua_xac_dinh"


def test_trang_dat_ca_ba_phep_kiem():
    assert kiem_trang_vbpl("45/2019/QH14", date(2019, 11, 20), "139264", 200, URL, DAU_BLLD) == (CANON, None)


def test_Eth_va_gach_en_trong_kho_van_khop_tieu_de():
    dau = (
        "<title>Quyết định 110/2002/QĐ-BTC của Bộ Tài chính | CSDL</title>"
        '<link rel="canonical" href="https://vbpl.vn/van-ban/chi-tiet/qd--109937"/>'
        '<meta property="article:published_time" content="2002-09-17T17:00:00.000Z"/>'
    )
    _, ly_do = kiem_trang_vbpl("110/2002/QÐ-BTC", date(2002, 9, 18), "109937", 200, "x", dau)
    assert ly_do is None


@pytest.mark.parametrize(
    "tham_so, manh",
    [
        # Mẫu cũ chuyển hướng về trang chủ: 200, nhưng không phải trang văn bản.
        (
            (
                "45/2019/QH14",
                date(2019, 11, 20),
                "139264",
                200,
                "https://vbpl.vn/",
                '<title>Trang chủ | CSDL quốc gia về pháp luật</title><link rel="canonical" href="https://vbpl.vn"/>',
            ),
            "canonical",
        ),
        (("45/2019/QH14", date(2019, 11, 20), "139264", 404, URL, ""), "HTTP 404"),
        # Ranh giới số: 45/2019/QH14 KHÔNG được khớp trong 145/2019/QH14.
        (
            (
                "45/2019/QH14",
                date(2019, 11, 20),
                "139264",
                200,
                URL,
                DAU_BLLD.replace("45/2019/QH14 của", "145/2019/QH14 của"),
            ),
            "tiêu đề",
        ),
        (("45/2019/QH14", date(2019, 11, 21), "139264", 200, URL, DAU_BLLD), "ngày ban hành"),
        (("45/2019/QH14", None, "139264", 200, URL, DAU_BLLD), "ngày ban hành"),
        (
            (
                "45/2019/QH14",
                date(2019, 11, 20),
                "139264",
                200,
                URL,
                DAU_BLLD.replace('<meta property="article:published_time" content="2019-11-19T17:00:00.000Z"/>', ""),
            ),
            "published_time",
        ),
    ],
)
def test_trang_truot_neu_ly_do(tham_so, manh):
    canonical, ly_do = kiem_trang_vbpl(*tham_so)
    assert ly_do is not None and manh in ly_do


def test_so_hieu_kho_mang_tien_to_so_van_cung_so_voi_gateway():
    """3 dòng parquet lưu 'Luật số 51/2024/QH15', 'số: 34/2024/QH15'; gateway và
    vbpl.vn ghi '51/2024/QH15'. Phần đuôi nguyên văn nguồn ('(1)', 'TT- BTC') thì
    gateway cũng ghi y như kho, nên không nới."""
    from scripts.lam_moi_hieu_luc import cung_so

    assert cung_so("Luật số 51/2024/QH15", "51/2024/QH15")
    assert cung_so("số: 34/2024/QH15", "34/2024/QH15")
    assert cung_so("110/2002/QÐ-BTC", "110/2002/QĐ-BTC")
    assert cung_so("Không số", "Không số")
    assert not cung_so("45/2019/QH14", "145/2019/QH14")
    assert not cung_so("22/2023/NĐ-CP (1)", "22/2023/NĐ-CP")
    dau = DAU_BLLD.replace("Bộ luật 45/2019/QH14", "Luật 51/2024/QH15")
    assert kiem_trang_vbpl("Luật số 51/2024/QH15", date(2019, 11, 20), "139264", 200, URL, dau)[1] is None


def test_trang_chung_cua_vbpl_neu_ro_tieu_de_trong_ly_do():
    dau = (
        '<title>Văn bản pháp luật | CSDL</title><link rel="canonical" href="https://vbpl.vn/van-ban/chi-tiet/121053"/>'
    )
    _, ly_do = kiem_trang_vbpl("28/2017/TT-BTC", date(2017, 4, 12), "121053", 200, URL, dau)
    assert "Văn bản pháp luật" in ly_do and "canonical" in ly_do


# Trang chung vbpl.vn trả với HTTP 200 khi không phục vụ trang chi tiết: canonical
# không có slug, không published_time (đo 2026-09-28 17:02–17:21 UTC, 23/23 id).
DAU_CHUNG = (
    "<title>Văn bản pháp luật | CSDL quốc gia về pháp luật</title>"
    '<link rel="canonical" href="https://vbpl.vn/van-ban/chi-tiet/139264"/>'
)


@pytest.mark.parametrize(
    "status, dau, cache",
    [
        (503, "", False),
        (429, "", False),
        (403, "", False),
        (200, DAU_CHUNG, False),
        (200, DAU_BLLD, True),
        (404, "", True),
    ],
)
def test_vbpl_chi_cache_ket_qua_ben_khong_cache_loi_tam(tmp_path, monkeypatch, status, dau, cache):
    """Chạy lại được: 429/5xx còn sau hết lượt thử, 403 và trang chung là vbpl.vn
    đang không phục vụ — lần sau phải tải lại, không đọc 'trượt' từ cache. Trang
    chi tiết thật và 404 là kết quả bền thì giữ."""
    import httpx

    from scripts import lam_moi_hieu_luc as m

    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, text=f"<head>{dau}</head>")))
    assert m._lay_vbpl(http, "139264", tmp_path)["status"] == status
    assert (tmp_path / "139264.json").exists() is cache


# Trang vanban.chinhphu.vn thật (scratchpad kiểm kho 2026-09-28, docid=162374), rút gọn.
TRANG_CP = (
    "<title>\n\tLuật số 02/2011/QH13 của Quốc hội: LUẬT KHIẾU NẠI\n</title>"
    '<table><tr><td class="col1" style="width: 135px">Số ký hiệu</td><td>\n    02/2011/QH13</td></tr>'
    '<tr><td class="col1">Ngày ban hành</td><td>\n                    11-11-2011</td></tr></table>'
)


def test_du_phong_chinhphu_dat_khi_tieu_de_va_ngay_khop():
    """Owner rule 2026-09-28 (b): vbpl.vn trượt → thử vanban.chinhphu.vn khi đã biết docid."""
    from scripts.lam_moi_hieu_luc import kiem_trang_chinhphu

    assert kiem_trang_chinhphu("02/2011/QH13", date(2011, 11, 11), 200, TRANG_CP) is None


@pytest.mark.parametrize(
    "so, ngay, status, trang, manh",
    [
        ("02/2011/QH13", date(2011, 11, 11), 404, "", "HTTP 404"),
        ("12/2011/QH13", date(2011, 11, 11), 200, TRANG_CP, "tiêu đề"),
        ("02/2011/QH13", date(2011, 11, 12), 200, TRANG_CP, "ngày ban hành"),
        ("02/2011/QH13", date(2011, 11, 11), 200, TRANG_CP.split("<table>")[0], "ngày ban hành"),
    ],
)
def test_du_phong_chinhphu_truot_neu_ly_do(so, ngay, status, trang, manh):
    from scripts.lam_moi_hieu_luc import kiem_trang_chinhphu

    ly_do = kiem_trang_chinhphu(so, ngay, status, trang)
    assert ly_do is not None and manh in ly_do


# ── Vòng xem xét K2 (2026-09-29): nguồn sập không xoá link, cầu dao, ghi đè có bằng chứng ──
from datetime import UTC, datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from scripts.lam_moi_hieu_luc import (  # noqa: E402
    NGAT_SAU,
    SEED_GHI_DE,
    SEED_HIEU_LUC,
    doc_bang_chung,
    doc_ghi_de,
    doi_chieu_link,
    hang_bang_chung,
    ket_luan_duoc,
    kiem_ghi_de,
    lan_luot,
    ngat_ghi,
    tinh_cot,
)

GOC = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "status, canonical, ket_luan",
    [
        (404, None, True),
        (410, None, True),
        (200, CANON, True),
        (200, "https://vbpl.vn/van-ban/chi-tiet/luat-khac--139265", True),  # trang thật của id khác
        (200, "https://vbpl.vn/van-ban/chi-tiet/139264", False),  # trang chung, không slug
        (200, "https://vbpl.vn", False),
        (200, None, False),
        (403, CANON, False),
        (429, None, False),
        (503, None, False),
        (None, None, False),  # lỗi mạng
    ],
)
def test_chi_404_hay_trang_chi_tiet_that_moi_ket_luan_duoc(status, canonical, ket_luan):
    assert ket_luan_duoc(status, canonical) is ket_luan


DOC = {"id": "139264", "so_ky_hieu": "45/2019/QH14", "ngay_ban_hanh": date(2019, 11, 20), "link_chinhphu": None}
CU_DAT = {
    "139264": {
        "so_ky_hieu": "45/2019/QH14",
        "url": URL,
        "canonical": CANON,
        "kiem_boi": "may-doi-chieu-tieu-de",
        "kiem_luc": datetime(2026, 9, 28, 5, tzinfo=UTC),
    }
}
LUC = "2026-09-29T01:00:00+00:00"


@pytest.mark.parametrize(
    "trang",
    [
        {"status": 200, "url": URL, "dau": DAU_CHUNG, "luc": LUC},
        {"status": 403, "url": URL, "dau": "", "luc": LUC},
        {"status": 503, "url": URL, "dau": ""},
        {"status": None, "url": URL, "dau": "", "loi": "ConnectError"},
        None,  # cầu dao đã ngắt vòng vbpl.vn trước id này
    ],
)
def test_vbpl_khong_phuc_vu_thi_giu_link_va_bang_chung_cu(trang):
    """Reviewer K2: trang chung/403/5xx/lỗi mạng mà xoá link thì một lượt chạy lúc
    vbpl.vn sập ẩn gần hết kho (K7 chỉ hiện văn bản có link đã kiểm)."""
    seed, bao = doi_chieu_link([DOC], {} if trang is None else {"139264": trang}, CU_DAT)
    assert seed["139264"] == CU_DAT["139264"]
    assert bao["mat_link"] == 0 and len(bao["giu_dong_cu_vi_khong_ket_luan"]) == 1


@pytest.mark.parametrize(
    "trang, manh",
    [
        ({"status": 200, "url": URL, "dau": DAU_BLLD.replace("2019-11-19T17", "2019-11-20T17"), "luc": LUC}, "ngày"),
        ({"status": 404, "url": URL, "dau": "", "luc": LUC}, "HTTP 404"),
    ],
)
def test_truot_ve_noi_dung_thi_xoa_link_va_dem_mat(trang, manh):
    seed, bao = doi_chieu_link([DOC], {"139264": trang}, CU_DAT)
    assert manh in seed["139264"]["ly_do"] and bao["mat_link"] == 1


def test_trang_dat_ghi_bang_chung_moi():
    seed, bao = doi_chieu_link([DOC], {"139264": {"status": 200, "url": URL, "dau": DAU_BLLD, "luc": LUC}}, {})
    assert seed["139264"]["canonical"] == CANON and "ly_do" not in seed["139264"]
    assert seed["139264"]["kiem_luc"] == datetime.fromisoformat(LUC) and bao["dat"] == 1


def test_nguon_sap_thi_thoi_goi_sau_NGAT_SAU_loi_lien_tiep():
    goi = []
    ra = lan_luot("x", [str(i) for i in range(50)], lambda g: goi.append(g) or "loi", lambda r: r == "loi")
    assert len(goi) == NGAT_SAU and list(ra) == goi


def test_loi_xen_ke_nhu_K2_that_khong_ngat():
    """K2 thật: 10 id gateway lỗi trên 1.822, nhiều nhất 2 id liền nhau."""
    kq = {str(i): "loi" if i % 3 == 0 else "ok" for i in range(30)}
    assert len(lan_luot("x", list(kq), kq.get, lambda r: r == "loi")) == 30


@pytest.mark.parametrize("mat, tong, ngat", [(0, 1822, False), (91, 1822, False), (92, 1822, True), (4, 78, True)])
def test_cau_dao_ghi_ngat_khi_mat_hon_5_phan_tram(mat, tong, ngat):
    assert (ngat_ghi(mat, tong) is not None) is ngat


# Dòng DB 49/2013/NĐ-CP: gateway còn ghi HHL1P, 145/2020/NĐ-CP Điều 114 khoản 2 bãi bỏ
# toàn bộ từ 2021-02-01 (scratchpad K8 ke-hoach-nap.md B-R1, B-R4).
DONG = {
    "id": "30466",
    "so_ky_hieu": "49/2013/NĐ-CP",
    "depth": "shallow",
    "tinh_trang": "HHL",
    "ngay_hieu_luc": date(2013, 7, 1),
    "ngay_het_hieu_luc": date(2021, 2, 1),
    "co_quan_ban_hanh": "Chính phủ",
    "hieu_luc_kiem_luc": datetime(2026, 9, 28, 5, tzinfo=UTC),
}
GATEWAY = {
    "docNum": "49/2013/NĐ-CP",
    "effStatus": {"code": "HHL1P", "name": "Hết hiệu lực một phần"},
    "effFrom": "2013-07-01T00:00:00",
    "effTo": None,
    "agencyName": "Chính phủ",
}
GHI_DE = {
    "so_ky_hieu": "49/2013/NĐ-CP",
    "tinh_trang": "HHL",
    "ngay_het_hieu_luc": date(2021, 2, 1),
    "dieu_khoan": "145/2020/NĐ-CP Điều 114 khoản 2: bãi bỏ Nghị định số 49/2013/NĐ-CP",
    "url": "https://congbao.chinhphu.vn/noi-dung-van-ban-so-145-2020-nd-cp-32043",
    "lay_luc": datetime(2026, 9, 28, 10, tzinfo=UTC),
}


def _bang(gw=GATEWAY):
    return {"30466": hang_bang_chung("30466", gw, datetime.fromisoformat(LUC))}


def test_hang_bang_chung_giu_du_truong_ma_cot_tu_gateway_doc():
    h = _bang()["30466"]
    assert cot_tu_gateway(h) == {**cot_tu_gateway(GATEWAY), "ngay_ban_hanh": None}
    assert h["url"].endswith("/doc/30466") and h["luc"] == LUC
    assert hang_bang_chung("cp-162374", GATEWAY, datetime.fromisoformat(LUC))["url"].endswith("/doc/27325")


@pytest.mark.parametrize("tinh_trang_db", ["HHL", "HHL1P"])
def test_ghi_de_thang_gateway_va_bao_cho_gateway_noi_khac(tinh_trang_db):
    """Quyết định mục 12: lượt làm mới KHÔNG được ghi ngược lại một ghi đè có bằng chứng."""
    cap_nhat, bao = tinh_cot([{**DONG, "tinh_trang": tinh_trang_db}], _bang(), {"30466": GHI_DE})
    assert cap_nhat[0]["tinh_trang"] == "HHL" and cap_nhat[0]["ngay_het_hieu_luc"] == date(2021, 2, 1)
    assert [x for x in bao["ghi_de"]["gateway_noi_khac"] if "HHL1P" in x and "145/2020" in x]
    assert bao["tinh_trang_doi_tang_nong_metadata"] == ({} if tinh_trang_db == "HHL" else {"HHL1P → HHL": 1})


def test_khong_ghi_de_thi_gateway_thang_ngay_trong_giu_ngay_kho():
    cap_nhat, bao = tinh_cot([DONG], _bang(), {})
    assert cap_nhat[0]["tinh_trang"] == "HHL1P"
    assert cap_nhat[0]["ngay_het_hieu_luc"] == date(2021, 2, 1)  # gateway effTo null: giữ ngày đang có
    assert cap_nhat[0]["hieu_luc_kiem_luc"] == datetime.fromisoformat(LUC)


def test_nap_lai_cung_bang_chung_la_khong_doi_gi():
    """Dựng lại kho rồi nạp seed: DB đã đúng seed thì 0 dòng cập nhật (idempotent)."""
    dong = {**DONG, "tinh_trang": "HHL1P", "hieu_luc_kiem_luc": datetime.fromisoformat(LUC)}
    assert tinh_cot([dong], _bang(), {})[0] == []


def test_ma_la_lam_van_ban_da_biet_roi_ve_chua_ro_bi_dem_cho_cau_dao():
    _, bao = tinh_cot([DONG], _bang({**GATEWAY, "effStatus": None}), {})
    assert bao["mat_tinh_trang"] == 1


def test_so_ky_hieu_lech_thi_khong_ap_bang_chung():
    cap_nhat, bao = tinh_cot([DONG], _bang({**GATEWAY, "docNum": "149/2013/NĐ-CP"}), {})
    assert cap_nhat == [] and len(bao["lech_so_ky_hieu"]) == 1


def test_ghi_de_lech_so_ky_hieu_hay_id_khong_co_trong_db_la_loi():
    with pytest.raises(ValueError, match="so_ky_hieu"):
        tinh_cot([DONG], {}, {"30466": {**GHI_DE, "so_ky_hieu": "50/2013/NĐ-CP"}})
    with pytest.raises(ValueError, match="không có trong documents"):
        tinh_cot([DONG], {}, {"99999": GHI_DE})


BAY_GIO = datetime(2026, 9, 29, tzinfo=UTC)


def test_kiem_ghi_de_nhan_dong_du_bang_chung():
    assert kiem_ghi_de("30466", GHI_DE, BAY_GIO) == GHI_DE
    assert kiem_ghi_de("30466", {**GHI_DE, "ngay_het_hieu_luc": None}, BAY_GIO)  # null = xoá ngày gateway ghi sai


@pytest.mark.parametrize(
    "sua, loi",
    [
        ({"dieu_khoan": " "}, "dieu_khoan"),
        ({"url": "https://thuvienphapluat.vn/van-ban/x"}, "nguồn nhà nước"),  # trang thương mại
        ({"url": "http://congbao.chinhphu.vn/x"}, "nguồn nhà nước"),
        ({"tinh_trang": "chua_xac_dinh"}, "tinh_trang"),
        ({"ngay_het_hieu_luc": "2021-02-01"}, "ngay_het_hieu_luc"),
        ({"lay_luc": datetime(2026, 9, 30, tzinfo=UTC)}, "lay_luc"),
        ({"lay_luc": datetime(2026, 9, 28)}, "lay_luc"),  # không múi giờ
        ({"so_ky_hieu": None}, "so_ky_hieu"),
        ({"ghi_chu": "x"}, "khoá lạ"),
    ],
)
def test_kiem_ghi_de_tu_choi(sua, loi):
    with pytest.raises(ValueError, match=loi):
        kiem_ghi_de("30466", {**GHI_DE, **sua}, BAY_GIO)


def test_kiem_ghi_de_tu_choi_dong_khong_ghi_de_cot_nao():
    with pytest.raises(ValueError, match="không ghi đè cột nào"):
        kiem_ghi_de("30466", {k: v for k, v in GHI_DE.items() if k not in ("tinh_trang", "ngay_het_hieu_luc")}, BAY_GIO)


def test_seed_bang_chung_tu_choi_url_khong_phai_gateway(tmp_path):
    import json

    p = tmp_path / "hl.jsonl"
    p.write_text(json.dumps({**_bang()["30466"], "url": "https://vbpl.vn/doc/30466"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="url"):
        doc_bang_chung(p)


def test_hai_seed_commit_doc_duoc_va_hop_le():
    bang = doc_bang_chung(GOC / SEED_HIEU_LUC)
    assert len(bang) >= 1812
    doc_ghi_de(GOC / SEED_GHI_DE)
