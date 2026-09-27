"""Microsoft Word có mở được bản đã điền không — thước đo P3a của kế hoạch
`docs/plans/active/khuon-goc-dien-tai-cho.md` (mục Risks: "only Word proves the
file").

LibreOffice dung thứ khai báo markup-compatibility hỏng mà Word từ chối, nên bằng
chứng cuối là chính Word trên máy chủ dự án. Với MỖI biểu mẫu `.docx` trong kho
mẫu: điền MỌI chỗ trống có địa chỉ bằng giá trị mẫu tiếng Việt
(`dien_khuon.ap_dung_docx`), đếm trang LibreOffice dựng trước/sau, rồi nhờ Word
(qua `osascript`, một lần mỗi tệp, trần 90 s) mở tệp, lưu ra PDF, đóng không lưu.
Đạt = PDF có mặt và cùng số trang LibreOffice dựng cho bản đã điền.

KHÔNG phải test pytest, không chạy trong CI: cần Word và quyền Automation. Một
lần gọi hỏng hay treo (macOS hỏi quyền, Word hiện hộp thoại) thì dừng phần Word,
in lỗi nguyên văn — không giết tiến trình nào của người dùng. Tệp tạm nằm trong
hộp cát của chính Word (`~/Library/Containers/com.microsoft.Word/Data/tmp`) để
Word không phải hỏi quyền truy cập tệp, và bị xoá khi xong.

Chạy:

    PYTHONPATH="$PWD" .venv/bin/python scripts/kiem_mo_bang_word.py
    PYTHONPATH="$PWD" .venv/bin/python scripts/kiem_mo_bang_word.py --khong-word   # chỉ LibreOffice

Các hàm dựng/so trang dưới đây cũng là công cụ của test trên tệp thật trong
`tests/test_services/test_dien_khuon.py`. ponytail: chuyển sang
`src/services/dung_trang.py` khi P2a về main.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from io import BytesIO
from pathlib import Path

import numpy as np
from pypdf import PdfReader

from src.services.dien_khuon import ap_dung_docx
from src.services.doc_tai_lieu import _cac_trang_pgm, _chay_cong_cu, _duong_soffice, doc
from src.services.tai_lieu import _hang_don_vi

GIA_TRI_MAU = ("Nguyễn Văn Ánh", "0912 345 678", "01/10/2026")
_KHO_MAC_DINH = Path.home() / "giấy tờ thực tập"
_THU_MUC_WORD = Path.home() / "Library/Containers/com.microsoft.Word/Data/tmp"
_HAN_WORD_GIAY = 90
_HAN_SOFFICE_GIAY = 120

_KICH_BAN = """on run argv
    set vao to POSIX file (item 1 of argv)
    set ra to item 2 of argv
    with timeout of 85 seconds
        tell application "Microsoft Word"
            open vao
            set d to active document
            save as d file name ra file format format PDF
            close d saving no
        end tell
    end timeout
end run"""


def hang_don_vi(ten: str, du_lieu: bytes) -> list[dict]:
    """Đúng mảng `tai_lieu.luu_don_vi` ghi và `don_vi_cua` đọc lại."""
    return json.loads(json.dumps([_hang_don_vi(d) for d in doc(ten, du_lieu).don_vi], ensure_ascii=False))


def phep_dien_het(hang: list[dict]) -> list[dict]:
    """Một phép `dien` cho MỖI chỗ trống chấm/tab có địa chỉ, giá trị xoay vòng
    `GIA_TRI_MAU`. Chỗ `o` (ô rỗng của bảng, G5) đo riêng (`eval.run_khuon_goc`): ô
    hẹp ngắt giá trị dài thành nhiều dòng, và `pdftotext` đọc bảng theo dòng."""
    cho = [(h["chi_so"], c["so"]) for h in hang if "dia_chi" in h for c in h.get("cho_trong", []) if c["kieu"] != "o"]
    return [
        {"loai": "dien", "don_vi": d, "cho_trong": so, "gia_tri": GIA_TRI_MAU[i % len(GIA_TRI_MAU)]}
        for i, (d, so) in enumerate(cho)
    ]


def dung_pdf(docx: bytes) -> bytes:
    """`.docx` → PDF bằng LibreOffice, hồ sơ người dùng riêng trong thư mục tạm."""
    with tempfile.TemporaryDirectory() as tmp:
        vao = Path(tmp) / "vao.docx"
        vao.write_bytes(docx)
        subprocess.run(
            [
                _duong_soffice() or "soffice",
                "--headless",
                "--norestore",
                f"-env:UserInstallation=file://{tmp}/ho_so",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp,
                str(vao),
            ],
            check=True,
            capture_output=True,
            timeout=_HAN_SOFFICE_GIAY,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp},
        )
        return (Path(tmp) / "vao.pdf").read_bytes()


def anh_xam(pdf: bytes, dpi: int = 60) -> list[np.ndarray]:
    """Ảnh xám 8-bit của từng trang (`pdftoppm -gray`, đọc PGM bằng numpy)."""
    return _cac_trang_pgm(_chay_cong_cu(["pdftoppm", "-r", str(dpi), "-gray", "-"], pdf) or b"")


def chu_trang(pdf: bytes) -> list[str]:
    """Chữ `pdftotext` của từng trang, NFC, khoảng trắng gộp một."""
    ra = (_chay_cong_cu(["pdftotext", "-", "-"], pdf) or b"").decode("utf-8", "replace")
    return [" ".join(unicodedata.normalize("NFC", t).split()) for t in ra.split("\f")[: so_trang(pdf)]]


def so_trang(pdf: bytes) -> int:
    return len(PdfReader(BytesIO(pdf)).pages)


def mo_bang_word(docx: Path, pdf: Path) -> str | None:
    """`None` khi Word mở và lưu được PDF; ngược lại là lỗi nguyên văn."""
    try:
        r = subprocess.run(
            ["osascript", "-e", _KICH_BAN, str(docx), str(pdf)],
            capture_output=True,
            text=True,
            timeout=_HAN_WORD_GIAY,
        )
    except subprocess.TimeoutExpired:
        return f"osascript treo quá {_HAN_WORD_GIAY} s (hộp thoại quyền Automation hoặc hộp thoại của Word?)"
    if r.returncode != 0:
        return r.stderr.strip() or f"osascript thoát mã {r.returncode}"
    return None if pdf.exists() else "Word chạy xong nhưng không có PDF"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kho", type=Path, default=_KHO_MAC_DINH, help="thư mục các biểu mẫu .docx")
    ap.add_argument("--ra", type=Path, help="thư mục tạm cho Word (mặc định: hộp cát của Word, xoá khi xong)")
    ap.add_argument("--khong-word", action="store_true", help="chỉ đếm trang LibreOffice, không gọi Word")
    a = ap.parse_args()
    # pypdf cảnh báo từng đối tượng lệch offset trong PDF của Word — tiếng ồn, không phải lỗi.
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    ra = a.ra or (_THU_MUC_WORD / "klaw-kiem-word" if _THU_MUC_WORD.exists() else Path(tempfile.mkdtemp()))
    ra.mkdir(parents=True, exist_ok=True)
    chan: str | None = None
    hong = 0
    print(f"{'tệp':42} {'phép':>5} {'áp':>5} {'bỏ':>4} {'LO trước':>9} {'LO sau':>7} {'Word':>6}")
    try:
        for k, tep in enumerate(sorted(a.kho.glob("*.docx")), start=1):
            du_lieu = tep.read_bytes()
            hang = hang_don_vi(tep.name, du_lieu)
            phep = phep_dien_het(hang)
            moi, bao_cao = ap_dung_docx(du_lieu, hang, phep)
            lo_truoc, lo_sau = so_trang(dung_pdf(du_lieu)), so_trang(dung_pdf(moi))
            word = "-"
            if not a.khong_word and chan is None:
                vao, pdf = ra / f"dien_{k}.docx", ra / f"dien_{k}.pdf"
                vao.write_bytes(moi)
                pdf.unlink(missing_ok=True)
                chan = mo_bang_word(vao, pdf)
                word = "CHẶN" if chan else str(so_trang(pdf.read_bytes()))
            dat = not bao_cao["bo_qua"] and (word in ("-", str(lo_sau)))
            hong += not dat
            print(
                f"{tep.stem[:42]:42} {len(phep):>5} {len(bao_cao['da_ap']):>5} {len(bao_cao['bo_qua']):>4} "
                f"{lo_truoc:>9} {lo_sau:>7} {word:>6}{'' if dat else '  <-- LỆCH'}"
            )
    finally:
        if a.ra is None:
            shutil.rmtree(ra, ignore_errors=True)
    if chan:
        print(f"Word check blocked: {chan}")
    return 1 if hong or chan else 0


if __name__ == "__main__":
    sys.exit(main())
