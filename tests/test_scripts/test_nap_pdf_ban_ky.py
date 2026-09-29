"""`scripts.nap_pdf_ban_ky` — hai phép đọc HTML của vanban.chinhphu.vn, $0, không mạng.

HTML mẫu cắt từ trang thật (tìm "145/2020/NĐ-CP", 2026-09-29): một dòng kết quả mang
`span.code` (số hiệu), `span.issued-date` (ngày ban hành) và link trang chi tiết.
"""

from datetime import date

from scripts.nap_pdf_ban_ky import docid_tim_duoc, link_ky


def _dong(docid: str, so: str, ngay: str) -> str:
    return (
        f"<tr><td><a href='/?pageid=27160&docid={docid}&classid=1'> <span class=\"code\">{so}</span>"
        f' <span class="issue-v2">{ngay}</span> </a></td><td> <span class="issued-date">{ngay}</span> </td>'
        "<td>trích yếu</td></tr>"
    )


def test_nhan_dung_dong_trung_ca_so_hieu_lan_ngay_ban_hanh():
    html = _dong("111", "145/2020/NĐ-CP", "01/01/2020") + _dong("201967", "145/2020/NĐ-CP", "14/12/2020")
    assert docid_tim_duoc(html, "145/2020/NĐ-CP", date(2020, 12, 14)) == ("201967", None)


def test_khong_dong_nao_khop_thi_khong_docid_va_neu_ly_do():
    html = _dong("219495", "45/2020/NĐ-CP", "14/12/2020")
    docid, ly_do = docid_tim_duoc(html, "145/2020/NĐ-CP", date(2020, 12, 14))
    assert docid is None and ly_do


def test_hai_docid_cung_khop_la_mo_ho_khong_chon():
    html = _dong("1", "01/2020/QĐ-UBND", "02/01/2020") + _dong("2", "01/2020/QĐ-UBND", "02/01/2020")
    docid, ly_do = docid_tim_duoc(html, "01/2020/QĐ-UBND", date(2020, 1, 2))
    assert docid is None and "2 docid" in ly_do


def test_link_ky_chi_lay_tep_signed_pdf_cua_datafiles():
    trang = (
        '<a href="https://datafiles.chinhphu.vn/cpp/files/vbpq/2016/01/91_.pdf">x</a>'
        '<a href="https://datafiles.chinhphu.vn/cpp/files/vbpq/2016/01/91.signed.pdf">y</a>'
        '<a href="https://example.com/a.signed.pdf">z</a>'
    )
    assert link_ky(trang) == "https://datafiles.chinhphu.vn/cpp/files/vbpq/2016/01/91.signed.pdf"
    assert link_ky('<a href="https://datafiles.chinhphu.vn/cpp/files/vbpq/2016/01/91_.pdf">x</a>') is None
