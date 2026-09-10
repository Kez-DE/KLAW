"""Đo QT-5 trên câu mơ hồ: trả lời kèm giả định thay vì abstain oan (spec 2026-09-09 §7.7).
python -m eval.run_mo_ho [--limit N] [--out PATH]

Review round 1 (Important): `suy_dien` (zero-token) chạy TRƯỚC hành văn và quyết
định luôn giá trị `chu_the` trong `ho_so_da_dung` — nên với bộ 20 câu này (mọi câu
đều khớp `suy_vai`), "không abstain + đúng vai trong hồ sơ" đúng KHÔNG PHỤ THUỘC
`assemble.v3` có được dùng hay không. Một mô hình bỏ qua prompt mới, lặp lại
nguyên câu hỏi và không bao giờ nêu dòng giả định vẫn qua được phép kiểm cũ.
`tra_loi_dat_chuan` dưới đây là nửa còn lại, đọc thẳng `answer` — heuristic văn
bản (substring), KHÔNG PHẢI judge ngữ nghĩa: bắt được lặp NGUYÊN VĂN câu hỏi và
thiếu ĐÚNG cụm "Tôi hiểu bạn là" mà prompt yêu cầu, bỏ lọt paraphrase (mô hình
diễn đạt lại ý câu hỏi, hoặc nêu giả định bằng cách khác). Chấp nhận được cho
một benchmark đo xu hướng qua 20 câu, không phải chấm điểm ngữ nghĩa từng câu.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from src.api import routes
from src.models.schemas import TraCuuRequest

DATA = Path(__file__).resolve().parent / "datasets" / "mo_ho.yaml"
KET_QUA = Path(__file__).resolve().parent / "results"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _chuan_hoa(s: str) -> str:
    return " ".join((s or "").split()).lower()


# Đủ dài để không dương tính giả trên vài chữ trùng ngẫu nhiên ("được gì", "phải
# làm sao"), đủ ngắn để bắt được lặp lại dù answer đổi vài chữ cuối câu hỏi.
_DO_DAI_DOAN_TOI_THIEU = 20
_DO_DAI_DOAN_SO_KHOP = 40
# "Mở đầu" = vài câu đầu answer, không phải toàn bộ — đúng hành vi lỗi mô tả
# trong review (lặp câu hỏi rồi mới từ chối), không phạt một answer nhắc lại
# một cụm ngắn của câu hỏi ở tận cuối tầng 3.
_DO_DAI_MO_DAU = 200


def lap_lai_cau_hoi(answer: str, cau_hoi: str) -> bool:
    """`answer` có MỞ ĐẦU bằng cách lặp lại câu hỏi không — so một đoạn ĐẦU của
    câu hỏi (đã chuẩn hoá: hạ chữ thường, gộp khoảng trắng) với phần mở đầu của
    answer. Câu hỏi quá ngắn (dưới `_DO_DAI_DOAN_TOI_THIEU`) thì bỏ qua — không
    đủ đặc trưng để so mà không dương tính giả."""
    doan = _chuan_hoa(cau_hoi)[:_DO_DAI_DOAN_SO_KHOP]
    if len(doan) < _DO_DAI_DOAN_TOI_THIEU:
        return False
    return doan in _chuan_hoa(answer)[:_DO_DAI_MO_DAU]


def tra_loi_dat_chuan(answer: str, cau_hoi: str, can_neu_gia_dinh: bool) -> bool:
    """Nửa thứ hai của phép kiểm — đọc thẳng `answer`, độc lập với việc `chu_the`
    đã đúng trong `ho_so_da_dung` hay chưa (xem docstring module). Sai một trong
    hai là answer chưa theo đúng TẦNG 1 của `assemble.v3`:

    1. Không được mở đầu bằng cách lặp lại câu hỏi (`lap_lai_cau_hoi`).
    2. Khi vai tới từ suy diễn (`can_neu_gia_dinh`), answer phải nêu dòng giả
       định đúng mẫu TẦNG 1 ("Tôi hiểu bạn là ..."). `can_neu_gia_dinh=False`
       (vai người nói tự khai, không phải giả định) thì không đòi dòng này.

    Phép so KHỚP NGUYÊN VĂN ở đây hợp lệ vì `prompts/assemble.v3.md` BẮT BUỘC
    đúng cụm đó ("viết ĐÚNG mẫu ... nguyên cụm đó, không diễn đạt lại"), chứ
    không nêu nó như một ví dụ — trước bản đó, benchmark này chấm trượt một hình
    dạng câu trả lời mà không prompt nào cấm.
    """
    if lap_lai_cau_hoi(answer, cau_hoi):
        return False
    return not can_neu_gia_dinh or "tôi hiểu bạn là" in _chuan_hoa(answer)


def dung(it: dict, payload: dict) -> bool:
    kv = it["ky_vong"]
    rt = payload.get("result_type")
    rt = rt.value if hasattr(rt, "value") else rt
    if kv.get("khong_abstain") and rt not in ("answer", "partial_coverage"):
        return False
    da = {d["khoa"]: d for d in payload.get("ho_so_da_dung") or []}
    ct = da.get("chu_the")
    if not (ct and kv["chu_the"] in str(ct.get("gia_tri")).lower()):
        return False
    return tra_loi_dat_chuan(payload.get("answer") or "", it.get("cau_hoi") or "", ct.get("gia_dinh") is True)


def tom_tat(ket: list[dict]) -> dict:
    """Đếm đúng/tổng/abstain oan từ `chi_tiet` — hàm THUẦN, không cần graph/mạng.

    Cùng cam kết `eval/run_trap.py::chay` và `eval/run_hoi_thoai.py::tom_tat_diem`:
    một câu lỗi hạ tầng không có khoá `dung`/`result_type` (chỉ có `error`/
    `error_type`) và không được tính vào CẢ tử số lẫn mẫu số của tỉ lệ đúng —
    loại riêng ra `so_loi`, không phải một câu trả lời sai.
    """
    loi = [k for k in ket if "error" in k]
    cham = [k for k in ket if "error" not in k]
    so_dung = sum(1 for k in cham if k["dung"])
    abstain_oan = sum(1 for k in cham if k["result_type"].endswith("abstain"))
    return {
        "so_cham": len(cham),
        "dung": so_dung,
        "so_loi": len(loi),
        "abstain_oan": abstain_oan,
        "ty_le_dung": round(so_dung / len(cham), 3) if cham else 0.0,
    }


def commit_hash() -> str:
    """Cùng khuôn `eval/run_trap.py::commit_hash` — fallback "unknown" khi git không
    chạy được, để thiếu git không làm crash cả lượt chạy đã tốn tiền."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True, cwd=_REPO_ROOT
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


async def main(limit: int | None, out: Path | None) -> int:
    ds = yaml.safe_load(DATA.read_text(encoding="utf-8"))["items"][:limit]
    ket: list[dict] = []
    for it in ds:
        try:
            payload, _ = await routes.chay_tra_cuu(TraCuuRequest(query=it["cau_hoi"]), None, str(uuid.uuid4()))
        except Exception as e:  # noqa: BLE001 - cố ý bắt rộng để MỘT câu lỗi hạ tầng không cuốn theo
            # cả lượt chạy đã tốn tiền — cùng lý do `eval/run_trap.py::chay` và
            # `eval/run_hoi_thoai.py::chay_mot` (đo được: một câu ăn HTTP 429 từng
            # cuốn theo ~5 phút chi phí LLM và toàn bộ dữ liệu chưa ghi).
            print(f"[mo_ho] LỖI câu {it['id']!r}: {type(e).__name__}: {e}", file=sys.stderr)
            ket.append({"id": it["id"], "error_type": type(e).__name__, "error": str(e)})
            continue
        ket.append(
            {
                "id": it["id"],
                "dung": dung(it, payload),
                "result_type": str(payload.get("result_type")),
                "ho_so_da_dung": payload.get("ho_so_da_dung") or [],
            }
        )
    tt = tom_tat(ket)
    commit = commit_hash()
    bao_cao = {
        "commit_hash": commit,
        "chay_luc": datetime.now(UTC).isoformat(),
        "so_cau": len(ket),
        **tt,
        "chi_tiet": ket,
    }
    duong = out or KET_QUA / f"mo_ho-{commit}.json"
    duong.parent.mkdir(parents=True, exist_ok=True)
    duong.write_text(json.dumps(bao_cao, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"{tt['dung']}/{tt['so_cham']} câu trả lời kèm giả định đúng; abstain oan {tt['abstain_oan']}, "
        f"{tt['so_loi']} câu lỗi không tính vào tỉ lệ — {duong}"
    )
    if tt["so_loi"]:
        loi = [c for c in ket if "error" in c]
        print("LỖI: " + ", ".join(f"{c['id']}({c['error_type']})" for c in loi), file=sys.stderr)
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.limit, a.out)))
