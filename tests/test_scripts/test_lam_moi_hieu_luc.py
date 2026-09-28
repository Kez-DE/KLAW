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


@pytest.mark.parametrize("status, cache", [(503, False), (429, False), (200, True), (404, True)])
def test_vbpl_chi_cache_ket_qua_ben_khong_cache_loi_tam(tmp_path, monkeypatch, status, cache):
    """Chạy lại được: 429/5xx còn sau hết lượt thử là lỗi TẠM — lần sau phải tải
    lại, không đọc 'trượt' từ cache. 200/404 là kết quả bền thì giữ."""
    import httpx

    from scripts import lam_moi_hieu_luc as m

    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, text="<head></head>")))
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
