"""Dựng lại các tệp .docx của tập mẫu từ nhãn trong manifest.

Chạy: `python eval/datasets/tai_lieu_mau/dung_mau.py`

Vì sao sinh bằng script thay vì chép tệp nhị phân vào kho mã: tài liệu đọc được
dưới dạng chữ trong lịch sử git, sửa được bằng một dòng, và mọi người dựng lại
được y hệt. Tệp .docx sinh ra KHÔNG được commit — chúng là đầu ra.

Tài liệu ở đây là TỰ DỰNG, không phải giấy tờ thật của người dùng: giấy tờ thật
chứa thông tin cá nhân của bên thứ ba chưa đồng ý gì cả.
"""

import zipfile
from pathlib import Path

import yaml

GOC = Path(__file__).parent
_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body>{than}</w:body></w:document>"
)


def _docx(duong: list[str]) -> bytes:
    than = "".join(
        f"<w:p><w:r><w:t>{d.replace('&', '&amp;').replace('<', '&lt;')}</w:t></w:r></w:p>" for d in duong
    )
    from io import BytesIO

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", _XML.format(than=than))
    return buf.getvalue()


_NHOM = {
    "cao_dang_tro_len": "đã qua đào tạo từ trình độ cao đẳng trở lên",
    "trung_cap_cnkt_nghiep_vu": "trình độ trung cấp, công nhân kỹ thuật, nghiệp vụ",
    "quan_ly_doanh_nghiep": "chức danh quản lý doanh nghiệp",
    "cong_viec_khac": "công việc khác",
}


def _than(m: dict) -> list[str]:
    n = m["nhan"]
    d = [f"HỢP ĐỒNG LAO ĐỘNG số {m['id'].upper()}", "Căn cứ Bộ luật Lao động số 45/2019/QH14."]
    if "nhom_chuc_danh" in n:
        d.append(f"Nhóm chức danh: {_NHOM[n['nhom_chuc_danh']]}")
    if "thoi_gian_thu_viec_ngay" in n:
        d.append(f"Thời gian thử việc: {n['thoi_gian_thu_viec_ngay']} ngày")
    if "luong_thu_viec" in n:
        d.append(f"Lương thử việc: {int(n['luong_thu_viec']):,} đồng/tháng".replace(",", "."))
    if "luong_chinh_thuc" in n:
        so = f"{int(n['luong_chinh_thuc']):,}".replace(",", ".")
        chu = " (bằng chữ: xem phụ lục)" if m["id"] == "hdld-so-viet-bang-chu" else ""
        d.append(f"Lương chính thức: {so} đồng/tháng{chu}")
    if "luong_thang" in n:
        d.append(f"Lương tháng: {int(n['luong_thang']):,} đồng/tháng".replace(",", "."))
    if "vung" in n:
        d.append(f"Địa điểm làm việc thuộc vùng {n['vung']} theo quy định về lương tối thiểu.")
    if n.get("co_dieu_khoan_phat_tien") == "true":
        d.append("Người lao động vi phạm nội quy bị phạt tiền 500.000 đồng mỗi lần.")
    if n.get("co_dieu_khoan_giu_giay_to") == "true":
        d.append("Người sử dụng lao động giữ bản chính bằng tốt nghiệp trong thời gian làm việc.")
    d.append("Hợp đồng lập thành 02 bản, mỗi bên giữ 01 bản.")
    return d


def main() -> None:
    bo = yaml.safe_load((GOC / "manifest_candidates.yaml").read_text(encoding="utf-8"))
    for m in bo["items"]:
        (GOC / m["tep"]).write_bytes(_docx(_than(m)))
        print("dựng", m["tep"])


if __name__ == "__main__":
    main()
