"""Dựng các tệp .docx của tập mẫu ĐƯỜNG TỔNG QUÁT từ chính manifest.

Chạy: `python eval/datasets/tai_lieu_tong_quat/dung_mau.py`

Khác `tai_lieu_mau/` bên cạnh: tập kia đo đường CHECKLIST (rút đúng bộ trường
của một trong 29 loại). Tập này đo đường tổng quát — tài liệu KHÔNG thuộc loại
nào: neo có đúng không, phép tính có chạy bằng mã không, biểu mẫu trắng có bị
chép thành dữ kiện không, và một câu lệnh giấu trong tài liệu có bị làm theo
không.

Cùng hai lý do của tập kia: tệp .docx là ĐẦU RA, không commit; tài liệu tự dựng
chứ không phải giấy tờ thật, vì giấy tờ thật mang dữ liệu cá nhân của bên thứ ba
chưa đồng ý gì cả.

Bốn thứ tập này cố ý có mà tập kia không có: bảng thật (`w:tbl`, để neo chỉ được
vào ô), chân trang (`w:ftr`, một vùng riêng), vùng chờ điền (dãy chấm), và một
câu tiêm lệnh.
"""

import zipfile
from io import BytesIO
from pathlib import Path

import yaml

GOC = Path(__file__).parent
_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_DOC = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{_NS}"><w:body>{{than}}</w:body></w:document>'
_FTR = f'<?xml version="1.0" encoding="UTF-8"?><w:ftr xmlns:w="{_NS}">{{than}}</w:ftr>'


def _thoat(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _p(chu: str) -> str:
    return f'<w:p><w:r><w:t xml:space="preserve">{_thoat(chu)}</w:t></w:r></w:p>'


def _bang(hang: list[list[str]]) -> str:
    """`w:tbl` thật: mỗi ô là một đơn vị văn bản riêng, nên một neo chỉ được vào
    đúng ô chứ không vào cả đoạn."""
    o = "".join("<w:tr>" + "".join(f"<w:tc>{_p(c)}</w:tc>" for c in h) + "</w:tr>" for h in hang)
    return f"<w:tbl>{o}</w:tbl>"


def _khoi(k: dict) -> str:
    """Một khối trong `noi_dung` của manifest: đoạn văn hoặc bảng."""
    return _bang(k["bang"]) if "bang" in k else _p(k["doan"])


def dung(m: dict) -> bytes:
    than = "".join(_khoi(k) for k in m["noi_dung"])
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        z.writestr("word/document.xml", _DOC.format(than=than))
        if m.get("chan_trang"):
            z.writestr("word/footer1.xml", _FTR.format(than=_p(m["chan_trang"])))
    return buf.getvalue()


def main() -> None:
    bo = yaml.safe_load((GOC / "manifest_candidates.yaml").read_text(encoding="utf-8"))
    for m in bo["tai_lieu"]:
        (GOC / m["tep"]).write_bytes(dung(m))
        print("dựng", m["tep"])


if __name__ == "__main__":
    main()
