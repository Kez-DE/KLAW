"""Đo bộ nhớ phiên qua graph thật + dịch vụ bộ nhớ thật (spec 2026-09-09 §6.7).
    python -m eval.run_hoi_thoai [--limit N] [--out PATH]
Mỗi hội thoại: tạo phiên cho một user đo riêng, chạy từng lượt qua `chay_tra_cuu`
với bộ nhớ nạp như production, gọi `bo_nho.cap_nhat_phien` ĐỒNG BỘ sau mỗi lượt
(không chạy nền, để lượt sau thấy hồ sơ), rồi chấm lượt cuối."""

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
from src.services import bao_ve, bo_nho, hoi_thoai

DATA = Path(__file__).resolve().parent / "datasets" / "hoi_thoai_nhieu_luot.yaml"
KET_QUA = Path(__file__).resolve().parent / "results"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def dung_du_kien(ky_vong: dict, ho_so_da_dung: list[dict], answer: str) -> bool:
    """So khớp NGUYÊN VĂN đã chuẩn hoá (gộp khoảng trắng, hạ chữ thường) — KHÔNG substring.

    Review round 1 (Important): `substring in` từng khớp `"xác định thời hạn"` vào CẢ
    `"không xác định thời hạn"` — hai loại hợp đồng ĐỐI LẬP, cả hai đều là output thật
    của prompt trích xuất (`prompts/bo_nho.v1.md`). Một scorer báo ĐÚNG trên đúng phân
    biệt mà cả giai đoạn này tồn tại để chứng minh bộ nhớ giữ được là một công cụ đo tệ
    hơn không có công cụ nào. Chưa hội thoại nào trong bộ dữ liệu cần so lỏng theo cụm
    từ con, nên so ĐÚNG TOÀN BỘ trên MỌI khoá — nới lỏng cho khoá tự do cụ thể khi có
    nhu cầu thật, không phải trước.
    """
    da = {d["khoa"]: " ".join(str(d.get("gia_tri") or "").split()).lower() for d in ho_so_da_dung}
    for khoa, gia_tri in (ky_vong.get("ho_so") or {}).items():
        if khoa not in da or " ".join(str(gia_tri).split()).lower() != da[khoa]:
            return False
    return all(cum.lower() in (answer or "").lower() for cum in ky_vong.get("answer_co") or [])


def commit_hash() -> str:
    """Cùng khuôn `eval/run_trap.py::commit_hash` — fallback "unknown" khi git không
    chạy được, để thiếu git không làm crash cả lượt chạy đã tốn tiền."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True, cwd=_REPO_ROOT
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


async def chay_mot(ht: dict, sub: str) -> dict:
    pid: str | None = None
    payload: dict = {}
    for cau in ht["luot"]:
        req = TraCuuRequest(query=cau, **({"hoi_thoai_id": pid} if pid else {}))
        req, pid, bn = await routes._chuan_bi_phien(req, sub)
        payload, _ = await routes.chay_tra_cuu(req, sub, str(uuid.uuid4()), bo_nho=bn)
        hoi_thoai.ghi_luot(pid, cau, payload, None)
        bo_nho.cap_nhat_phien(pid, sub)
    return {
        "id": ht["id"],
        "dung": dung_du_kien(ht["ky_vong"], payload.get("ho_so_da_dung") or [], payload.get("answer") or ""),
        "ho_so_da_dung": payload.get("ho_so_da_dung") or [],
        "result_type": payload.get("result_type"),
    }


async def main(limit: int | None, out: Path | None) -> int:
    ds = yaml.safe_load(DATA.read_text(encoding="utf-8"))["hoi_thoai"][:limit]
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    ket: list[dict] = []
    for ht in ds:
        try:
            ket.append(await chay_mot(ht, sub))
        except Exception as e:  # noqa: BLE001 - cố ý bắt rộng để MỘT hội thoại lỗi không làm mất
            # cả lượt chạy đã tốn tiền — cùng lý do `eval/run_trap.py::chay` (đo được: một câu
            # ăn HTTP 429 từng cuốn theo ~5 phút chi phí LLM và toàn bộ dữ liệu chưa ghi).
            print(f"[hoi_thoai] LỖI hội thoại {ht['id']!r}: {type(e).__name__}: {e}", file=sys.stderr)
            ket.append({"id": ht["id"], "dung": False, "error_type": type(e).__name__, "error": str(e)})
    dung = sum(1 for k in ket if k["dung"])
    commit = commit_hash()
    bao_cao = {
        "commit_hash": commit,
        "chay_luc": datetime.now(UTC).isoformat(),
        "so_hoi_thoai": len(ket),
        "dung": dung,
        "ty_le_dung_du_kien": round(dung / len(ket), 3) if ket else 0.0,
        "chi_tiet": ket,
    }
    duong = out or KET_QUA / f"hoi_thoai_nhieu_luot-{commit}.json"
    duong.parent.mkdir(parents=True, exist_ok=True)
    duong.write_text(json.dumps(bao_cao, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{dung}/{len(ket)} hội thoại dùng đúng dữ kiện — {duong}")
    loi = [c for c in ket if "error" in c]
    if loi:
        print(
            f"LỖI: {len(loi)}/{len(ket)} hội thoại không chạy được (KHÔNG tính vào cột đúng) — "
            + ", ".join(f"{c['id']}({c['error_type']})" for c in loi)
        )
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.limit, a.out)))
