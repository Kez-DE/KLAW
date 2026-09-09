"""Đo QT-5 trên câu mơ hồ: trả lời kèm giả định thay vì abstain oan (spec 2026-09-09 §7.7).
python -m eval.run_mo_ho [--limit N] [--out PATH]"""

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


def dung(it: dict, payload: dict) -> bool:
    kv = it["ky_vong"]
    rt = payload.get("result_type")
    rt = rt.value if hasattr(rt, "value") else rt
    if kv.get("khong_abstain") and rt not in ("answer", "partial_coverage"):
        return False
    da = {d["khoa"]: d for d in payload.get("ho_so_da_dung") or []}
    ct = da.get("chu_the")
    return bool(ct) and kv["chu_the"] in str(ct.get("gia_tri")).lower()


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
