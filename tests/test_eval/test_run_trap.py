"""M6 (silent-failure review round 2): `eval/run_trap.py` phải thật sự chạy
được qua graph thật, không chỉ tồn tại như file — nếu không, 44/45 (hay bất
kỳ con số nào sau này) không tái lập được và không gác regression."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_run_trap_chay_duoc_tren_1_cau_va_ghi_commit_hash(tmp_path):
    """`--limit 1` để không tốn ngân sách API — chỉ cần chứng minh runner THẬT
    SỰ gọi được graph, không phải suy luận trên chữ ký hàm."""
    out = tmp_path / "trap_run.json"
    subprocess.run(
        [sys.executable, "-m", "eval.run_trap", "--limit", "1", "--out", str(out)],
        check=True, cwd=_REPO_ROOT,
    )
    ket = json.loads(out.read_text(encoding="utf-8"))
    assert ket["commit_hash"] and ket["commit_hash"] != "unknown"
    assert sum(tong for _, tong in ket["theo_nhom"].values()) == 1
    assert len(ket["chi_tiet"]) == 1
