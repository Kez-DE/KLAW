"""M6 (silent-failure review round 2): `eval/run_trap.py` phải thật sự chạy
được qua graph thật, không chỉ tồn tại như file — nếu không, 44/45 (hay bất
kỳ con số nào sau này) không tái lập được và không gác regression."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval.run_trap import dung, token_in_cua

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


# ── `dung()` cho sáu `ky_vong` mới (spec 2026-09-06 §8.3) — trên state giả,
#    không chạy graph ──

CIT = [{"k": 1, "doc_id": "139264", "duong_dan": "45/2019/QH14 > Điều 26"}]
DOCS = [{"doc_id": "139264"}]


def _st(answer, rt="answer", **kw):
    return {"result_type": rt, "answer": answer, "citations": CIT, "documents": DOCS, **kw}


def test_khong_url():
    assert dung({"ky_vong": "khong_url"}, _st("Bạn được 85% [Điều 26](cite:1)."))
    assert not dung({"ky_vong": "khong_url"}, _st("Xem vbpl.vn"))


def test_the_hop_le():
    assert dung({"ky_vong": "the_hop_le"}, _st("[BLLĐ](doc:139264) 85% [Điều 26](cite:1)."))
    assert not dung({"ky_vong": "the_hop_le"}, _st("[Điều 99](cite:1)."))
    assert not dung({"ky_vong": "the_hop_le"}, _st("x", rt="abstain")), "abstain vì thẻ sai phải tính là hỏng"


def test_khong_mien_tru():
    assert dung({"ky_vong": "khong_mien_tru"}, _st("Bạn được 85%."))
    assert not dung({"ky_vong": "khong_mien_tru"}, _st("Thông tin chỉ mang tính tham khảo."))
    assert not dung({"ky_vong": "khong_mien_tru"}, _st("Bạn nên hỏi luật sư."))


def test_co_chao_va_khong_chao():
    assert dung({"ky_vong": "co_chao"}, _st("Chào bạn, công ty chỉ được…"))
    assert not dung({"ky_vong": "co_chao"}, _st("Công ty chỉ được…"))
    assert dung({"ky_vong": "khong_chao"}, _st("Công ty chỉ được…"))
    assert not dung({"ky_vong": "khong_chao"}, _st("Chào bạn, công ty…"))


def test_van_ban_ngoai_kho():
    it = {"ky_vong": "van_ban_ngoai_kho", "cam_nhac": ["126/2014", "01/2016"]}
    assert dung(it, _st("Theo Luật HN&GĐ…"))
    assert dung(it, _st(None, rt="abstain"))
    assert not dung(it, _st("Xem Nghị định 126/2014/NĐ-CP"))


def test_token_in_cua_cong_bay_khoa_bo_qua_khoa_thieu():
    assert token_in_cua({"traces": {"route_token_in": 10, "assemble_token_in": 5}}) == 15
    assert token_in_cua({}) == 0
