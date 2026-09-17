"""`.doc` cũ (OLE2) — chuyển bằng LibreOffice rồi tái dùng đường đọc DOCX
KHÔNG ĐỔI GÌ (`.sdd/phase-13-brief.md`, Phase 13).

Ba điều file này khoá:

1. Vòng .doc -> .docx không đánh mất cấu trúc: số đoạn, số bảng, tỉ lệ cột
   phải giống hệt bản .docx gốc — đo trên BM.M05 thật, cùng tệp và cùng cách
   brief đã đo tay (`MS Word 97` rồi ngược lại). Không viết một bộ đọc .doc
   riêng: `doc()` phải tái dùng ĐÚNG `_doc_docx`.
2. `.doc` là một CHỮ KÝ byte (OLE2/CFB), không phải một đuôi tên tệp — dữ liệu
   không phải OLE2 (ví dụ một .docx bị đổi tên nhầm) phải bị chặn TRƯỚC khi
   chạm bộ chuyển đổi, không phải sau khi soffice báo lỗi.
3. Bộ chuyển đổi là một tiến trình con nhận dữ liệu KHÔNG ĐÁNG TIN: treo phải
   bị cắt sạch trong một hạn định, và thư mục tạm (đầu vào, đầu ra, hồ sơ
   soffice) không được sống sót qua lần gọi dù việc chuyển đổi thành hay bại.
"""

import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.doc_tai_lieu import ChuyenDoiKhongSanSang, KhongDocDuoc, LoaiHong, doc

_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_CO_SOFFICE = shutil.which("soffice") is not None

# Cùng kho mẫu ngoài repo mà `test_doc_tai_lieu.py`/`test_ban_thao_tong_quat.py`
# đã dùng cho Phase 9/11 — đây chính là tệp brief đã đo tay cho quyết định
# "chuyển đổi, không viết bộ đọc riêng".
_KHO_MAU = Path.home() / "giấy tờ thực tập"
_BM_M05 = _KHO_MAU / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx"


def _docx_sang_doc_that(docx_bytes: bytes, tmp_path: Path) -> bytes:
    """Dùng CHÍNH soffice để dựng một .doc THẬT từ .docx — cùng bộ lọc
    `MS Word 97` brief đã đo tay. Đây là SETUP của test: sản phẩm chỉ đi một
    chiều .doc -> .docx, chiều ngược lại chỉ tồn tại để có dữ liệu thử."""
    vao = tmp_path / "goc.docx"
    vao.write_bytes(docx_bytes)
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "doc:MS Word 97", "--outdir", str(tmp_path), str(vao)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return (tmp_path / "goc.doc").read_bytes()


def _tom_tat(t):
    """(số đoạn ngoài bảng, số bảng, tỉ lệ cột từng bảng) — so trực tiếp hai vế
    thay vì ghim lại con số brief đã đo, để một cách đếm khác đi ở tương lai
    vẫn giữ được phép so sánh này đúng."""
    doan = [d.noi_dung for d in t.don_vi if d.bang is None]
    id_bang = sorted({d.bang[0] for d in t.don_vi if d.bang is not None})
    grid = [next(d.bang_ti_le for d in t.don_vi if d.bang is not None and d.bang[0] == b) for b in id_bang]
    return len(doan), len(id_bang), grid


@pytest.mark.skipif(not _CO_SOFFICE, reason="cần LibreOffice để chuyển đổi .doc")
@pytest.mark.skipif(not _BM_M05.exists(), reason="kho mẫu ngoài repo (BM.M05) không có trên máy này")
def test_DOC_giu_dung_cau_truc_nhu_DOCX_goc(tmp_path):
    docx_goc = _BM_M05.read_bytes()
    t_docx = doc(_BM_M05.name, docx_goc)

    doc_that = _docx_sang_doc_that(docx_goc, tmp_path)
    t_doc = doc("giay-tiep-nhan.doc", doc_that)

    assert _tom_tat(t_doc) == _tom_tat(t_docx)


def test_DOC_khong_bi_tu_choi_vi_DINH_DANG():
    """.doc giờ được NHẬN — không còn rơi vào `dinh_dang_khong_ho_tro`, bất kể
    LibreOffice có mặt hay không (vắng mặt thì ném `ChuyenDoiKhongSanSang` —
    fix round 2, không còn `KhongDocDuoc`; có mặt mà nội dung rác thì rơi vào
    `tep_hong`)."""
    try:
        doc("hd.doc", _OLE2_MAGIC + b"\x00" * 100)
    except KhongDocDuoc as e:
        assert e.ly_do is not LoaiHong.dinh_dang_khong_ho_tro
    except ChuyenDoiKhongSanSang:
        pass  # máy không có LibreOffice — vẫn KHÔNG phải "định dạng không hỗ trợ"


def test_DOC_gia_mao_KHONG_phai_OLE2_bi_chan_TRUOC_bo_chuyen_doi():
    """Một .docx (chữ ký zip `PK`) bị đổi tên nhầm thành .doc — lỗi người dùng
    thường gặp. Đuôi tên tệp nói .doc nhưng byte nói khác; phải tin byte, và
    phải chặn TRƯỚC khi gọi soffice, không đợi soffice từ chối."""
    with patch("src.services.doc_tai_lieu._duong_soffice") as gia_bo_chuyen_doi:
        with pytest.raises(KhongDocDuoc) as e:
            doc("nham-duoi.doc", b"PK\x03\x04" + b"\x00" * 100)
    assert e.value.ly_do is LoaiHong.tep_hong
    gia_bo_chuyen_doi.assert_not_called()


def test_DOC_khong_co_soffice_bao_loi_ro_khong_phai_500(monkeypatch, caplog):
    """LibreOffice vắng mặt lúc chạy phải ra lỗi CỤ THỂ — không phải 500,
    không phải một `hong` câm lặng không rõ lý do, và không đổ lỗi cho tài
    liệu (fix round 2, Minor #4): đây là `ChuyenDoiKhongSanSang`, KHÔNG còn
    `KhongDocDuoc(khong_co_lop_chu, ...)` như round 1 — một máy chủ thiếu
    LibreOffice không phải "ảnh chụp mờ". Phải LOUD với người vận hành: log
    ở mức ERROR, không log câm lặng."""
    monkeypatch.setattr("src.services.doc_tai_lieu._duong_soffice", lambda: None)
    with caplog.at_level("ERROR", logger="src.services.doc_tai_lieu"):
        with pytest.raises(ChuyenDoiKhongSanSang) as e:
            doc("hd.doc", _OLE2_MAGIC + b"\x00" * 100)
    assert e.value.ly_do == "khong_co_cong_cu"
    assert any(r.levelname == "ERROR" and "LibreOffice" in r.message for r in caplog.records), (
        "thiếu LibreOffice phải log ở mức ERROR để người vận hành thấy được"
    )


def test_DOC_qua_tai_KHONG_xep_hang_im_lang(monkeypatch):
    """Không giành được suất chuyển đổi trong thời gian chờ phải báo NGAY
    (`ChuyenDoiKhongSanSang("qua_tai", ...)`), không treo request vô thời hạn
    — "hàng đợi im lặng" tự nó là một lỗi (task review, Important)."""
    monkeypatch.setattr("src.services.doc_tai_lieu._duong_soffice", lambda: "/usr/bin/soffice")
    # Suất RỖNG: chiếm hết toàn bộ suất thật trước khi gọi, để lần gọi dưới
    # đây chắc chắn không giành được gì — không cần đợi hết hạn thật
    # (`_HAN_CHO_SUAT_GIAY`) nên cũng hạ xuống cho bài kiểm chạy nhanh.
    monkeypatch.setattr("src.services.doc_tai_lieu._HAN_CHO_SUAT_GIAY", 0.2)
    suat = threading.Semaphore(1)
    suat.acquire()
    monkeypatch.setattr("src.services.doc_tai_lieu._suat_chuyen_doi", suat)

    with pytest.raises(ChuyenDoiKhongSanSang) as e:
        doc("hd.doc", _OLE2_MAGIC + b"\x00" * 100)
    assert e.value.ly_do == "qua_tai"


def test_DOC_loi_chuyen_doi_KHONG_ghi_stderr_cua_soffice_vao_log(monkeypatch, caplog):
    """FR-027 + quyết định 2026-09-16: nội dung tài liệu không bao giờ vào
    log. `stderr` của soffice bắt nguồn từ CHÍNH tài liệu người dùng (tên
    tệp, đôi khi trích lại nội dung không phân tích được) — chỉ mã thoát
    được phép vào log, không phải chuỗi đó (task review, Minor #3)."""
    monkeypatch.setattr("src.services.doc_tai_lieu._duong_soffice", lambda: "/usr/bin/soffice")

    chuoi_bi_mat = "BI-MAT-KHONG-DUOC-VAO-LOG-tu-tai-lieu-cua-nguoi-dung"

    class _TienTrinhHong:
        pid = 2**30
        returncode = 1

        def communicate(self, timeout=None):
            return b"", chuoi_bi_mat.encode()

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _TienTrinhHong())

    with caplog.at_level("WARNING", logger="src.services.doc_tai_lieu"):
        with pytest.raises(KhongDocDuoc):
            doc("hd.doc", _OLE2_MAGIC + b"\x00" * 100)

    toan_bo_log = "\n".join(r.message for r in caplog.records)
    assert chuoi_bi_mat not in toan_bo_log, "stderr của soffice (bắt nguồn từ tài liệu) không được vào log"
    assert any("mã thoát" in r.message or "1" in r.message for r in caplog.records), (
        "vẫn phải log ĐƯỢC sự kiện hỏng và mã thoát, chỉ không log nội dung"
    )


def test_DOC_qua_han_treo_hong_sach_khong_treo_ca_request(monkeypatch):
    """Một .doc cố ý làm treo bộ phân tích OLE2 phải hỏng việc đọc trong hạn
    định, không được treo cả request (R3). Mock ở tầng `Popen` (fix round 1:
    hàm chuyển đổi giờ dùng `Popen`, không còn `subprocess.run`) — bài kiểm
    RIÊNG bên dưới (`test_DOC_qua_han_treo_GIET_CA_NHOM...`) mới là bài chứng
    minh việc diệt CẢ NHÓM tiến trình bằng tiến trình thật."""
    monkeypatch.setattr("src.services.doc_tai_lieu._duong_soffice", lambda: "/usr/bin/soffice")

    class _TienTrinhTreo:
        # Ngoài dải PID thật trên mọi hệ điều hành hiện hành — `os.killpg`
        # trên nó phải luôn ném `ProcessLookupError`, đúng hành vi khi tiến
        # trình (giả) đã không còn tồn tại.
        pid = 2**30
        returncode = None
        _lan_goi = 0

        def communicate(self, timeout=None):
            self._lan_goi += 1
            if self._lan_goi == 1:
                raise subprocess.TimeoutExpired(cmd="soffice", timeout=timeout or 60)
            return b"", b""  # lần gọi lại của `_giet_sach_nhom` sau khi diệt

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _TienTrinhTreo())
    with pytest.raises(KhongDocDuoc) as e:
        doc("hd.doc", _OLE2_MAGIC + b"\x00" * 100)
    assert e.value.ly_do is LoaiHong.tep_hong


def test_DOC_tep_tam_khong_song_sot_qua_lan_goi_khi_chuyen_doi_hong(monkeypatch):
    """Thư mục tạm (đầu vào .doc, đầu ra .docx, hồ sơ soffice riêng) phải bị
    xoá kể cả khi bộ chuyển đổi báo lỗi — không nhánh nào để lại tệp của người
    dùng trên đĩa (FR-022 áp dụng cho cả bản chuyển đổi)."""
    monkeypatch.setattr("src.services.doc_tai_lieu._duong_soffice", lambda: "/usr/bin/soffice")

    duong_da_dung: list[str] = []
    goc_tao = tempfile.TemporaryDirectory

    class _ThuMucGiamSat(goc_tao):
        def __enter__(self):
            p = super().__enter__()
            duong_da_dung.append(p)
            return p

    monkeypatch.setattr("src.services.doc_tai_lieu.tempfile.TemporaryDirectory", _ThuMucGiamSat)

    class _TienTrinhHong:
        pid = 2**30
        returncode = 1

        def communicate(self, timeout=None):
            return b"", b"loi gia lap"

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _TienTrinhHong())

    with pytest.raises(KhongDocDuoc) as e:
        doc("hd.doc", _OLE2_MAGIC + b"\x00" * 100)

    assert e.value.ly_do is LoaiHong.tep_hong
    assert duong_da_dung, "phải có ít nhất một thư mục tạm được dựng lên"
    assert not Path(duong_da_dung[0]).exists(), "thư mục tạm phải bị xoá sau khi hàm kết thúc"


def test_DOC_qua_han_treo_GIET_CA_NHOM_khong_chi_con_truc_tiep(tmp_path, monkeypatch):
    """Fix round 1 (Critical) — proof bằng tiến trình THẬT, không mock.

    `soffice` thật là một wrapper thực thi `soffice.bin`, và bản thân
    LibreOffice có thể tự sinh thêm tiến trình của riêng nó — PID mà `Popen`
    giữ không chắc là PID của tiến trình đang THẬT SỰ làm việc. `soffice` GIẢ
    dưới đây tự sinh một tiến trình CHÁU rồi treo cả hai (mô phỏng đúng hình
    dạng đó), và bài kiểm xác nhận: (1) tiến trình CHÁU — không chỉ con trực
    tiếp `Popen` biết tới — cũng bị dọn khi hết hạn, và (2) thư mục tạm bị xoá
    trên CHÍNH đường hết hạn (trước chỉ có bài kiểm cho đường chuyển đổi
    hỏng, không phải đường hết hạn)."""
    pid_chau_path = tmp_path / "chau.pid"
    soffice_gia = tmp_path / "soffice_gia.py"
    soffice_gia.write_text(
        "#!/usr/bin/env python3\n"
        "import subprocess, time\n"
        "p = subprocess.Popen(['sleep', '50'])\n"
        f"open({str(pid_chau_path)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(50)\n"
    )
    soffice_gia.chmod(0o755)

    monkeypatch.setattr("src.services.doc_tai_lieu._duong_soffice", lambda: str(soffice_gia))
    # Hạn thật (60s) làm bài kiểm chậm không cần thiết — hạ xuống để proof vẫn
    # đi qua ĐÚNG đường code (Popen -> TimeoutExpired -> _giet_sach_nhom).
    monkeypatch.setattr("src.services.doc_tai_lieu._HAN_CHUYEN_DOI_GIAY", 2)

    duong_da_dung: list[str] = []
    goc_tao = tempfile.TemporaryDirectory

    class _ThuMucGiamSat(goc_tao):
        def __enter__(self):
            p = super().__enter__()
            duong_da_dung.append(p)
            return p

    monkeypatch.setattr("src.services.doc_tai_lieu.tempfile.TemporaryDirectory", _ThuMucGiamSat)

    with pytest.raises(KhongDocDuoc) as e:
        doc("hd.doc", _OLE2_MAGIC + b"\x00" * 100)
    assert e.value.ly_do is LoaiHong.tep_hong

    for _ in range(50):
        if pid_chau_path.exists():
            break
        time.sleep(0.1)
    assert pid_chau_path.exists(), "soffice giả không kịp sinh tiến trình cháu trước khi bị diệt"
    pid_chau = int(pid_chau_path.read_text())

    for _ in range(50):
        try:
            os.kill(pid_chau, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"tiến trình cháu {pid_chau} vẫn sống sau khi hết hạn — killpg không tới được nó")

    assert duong_da_dung, "phải có ít nhất một thư mục tạm được dựng lên"
    assert not Path(duong_da_dung[0]).exists(), (
        "thư mục tạm phải bị xoá cả trên đường hết hạn, không chỉ đường chuyển đổi hỏng"
    )


def _csv_sang_xls_that(tmp_path: Path) -> bytes:
    """Dựng một .xls THẬT (không phải .doc) bằng CHÍNH soffice — mô phỏng ca
    thật: một bảng tính bị đổi tên nhầm/cố ý thành .doc."""
    csv = tmp_path / "mini.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "xls:MS Excel 97", "--outdir", str(tmp_path), str(csv)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return (tmp_path / "mini.xls").read_bytes()


@pytest.mark.skipif(not _CO_SOFFICE, reason="cần LibreOffice để dựng .xls thử và để tự chuyển đổi thất bại")
def test_DOC_gia_dang_XLS_that_bai_o_buoc_chuyen_doi_khong_phai_o_cong_OLE2(tmp_path):
    """Fix round 1 (Important) — đo THẬT, không chỉ suy luận từ docstring.

    .xls dùng CHUNG chữ ký OLE2 với .doc (`_la_ole2` không phân biệt sâu hơn —
    xem docstring của nó). Một .xls THẬT bị đổi tên thành .doc phải QUA được
    cổng OLE2 rồi THẤT BẠI ở bước chuyển đổi — soffice mở nó bằng Calc, không
    xuất được sang khuôn Writer .docx (`SfxBaseModel::impl_store` báo lỗi,
    không tệp .docx nào được sinh ra) — và việc đó rơi đúng vào `tep_hong`."""
    xls_that = _csv_sang_xls_that(tmp_path)
    assert xls_that[:8] == _OLE2_MAGIC, "phải là OLE2 thật để test đúng cổng đang khoá"

    with pytest.raises(KhongDocDuoc) as e:
        doc("bang-tinh-doi-ten.doc", xls_that)
    assert e.value.ly_do is LoaiHong.tep_hong
