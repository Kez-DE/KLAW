import subprocess

import httpx
import pytest

from scripts import download_data
from scripts.download_data import FILES


def test_khong_bao_gio_tai_content_parquet_784mb():
    assert "content" not in FILES, (
        "content.parquet là 784 MB và không cần: toàn văn lấy từ API MOJ (spec 4b.3)"
    )


def test_chi_tai_dung_hai_file_can_thiet():
    assert set(FILES) == {"metadata", "relationships"}


def test_khong_tai_thu_muc_legacy_3_5gb():
    assert all("legacy" not in u for u in FILES.values())


def test_data_seed_KHONG_bi_gitignore():
    """Task 8 phải commit được data/seed/*.jsonl — nếu bị ignore, git add thêm số không."""
    r = subprocess.run(["git", "check-ignore", "-q", "data/seed/documents.jsonl"],
                       capture_output=True)
    assert r.returncode != 0, "data/seed bị gitignore — Task 8 sẽ commit rỗng mà không báo lỗi"


def test_data_raw_VAN_bi_gitignore():
    """parquet 25 MB không được vào repo."""
    r = subprocess.run(["git", "check-ignore", "-q", "data/raw/metadata.parquet"],
                       capture_output=True)
    assert r.returncode == 0, "data/raw không bị ignore — parquet sẽ lọt vào repo"


def test_tai_that_bai_giua_duong_KHONG_de_lai_file_do(tmp_path, monkeypatch):
    """File dở + skip-if-exists = file hỏng vĩnh viễn, và lỗi chỉ lộ ở Task 8."""

    class BoomStream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_bytes(self, n):
            yield b"x" * 1024
            raise httpx.ReadError("mất mạng giữa đường")

    monkeypatch.setattr(download_data.httpx, "stream", lambda *a, **k: BoomStream())

    with pytest.raises(httpx.ReadError):
        download_data.download(tmp_path, only=["metadata"])

    assert not (tmp_path / "metadata.parquet").exists(), (
        "để lại file dở → lần sau skip-if-exists giữ file hỏng vĩnh viễn"
    )
    assert not list(tmp_path.glob("*.tmp")), "để lại file .tmp"
