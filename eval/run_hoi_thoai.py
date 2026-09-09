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


def dung_du_kien(ky_vong: dict, ho_so_da_dung: list[dict], answer: str) -> bool:
    da = {d["khoa"]: str(d.get("gia_tri") or "").lower() for d in ho_so_da_dung}
    for khoa, gia_tri in (ky_vong.get("ho_so") or {}).items():
        if khoa not in da or str(gia_tri).lower() not in da[khoa]:
            return False
    return all(cum.lower() in (answer or "").lower() for cum in ky_vong.get("answer_co") or [])


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
    ket = [await chay_mot(ht, sub) for ht in ds]
    dung = sum(1 for k in ket if k["dung"])
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    bao_cao = {
        "commit_hash": commit,
        "chay_luc": datetime.now(UTC).isoformat(),
        "so_hoi_thoai": len(ket),
        "dung": dung,
        "ty_le_dung_du_kien": round(dung / len(ket), 3) if ket else 0.0,
        "chi_tiet": ket,
    }
    duong = out or KET_QUA / f"hoi_thoai_nhieu_luot-{commit}.json"
    duong.write_text(json.dumps(bao_cao, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{dung}/{len(ket)} hội thoại dùng đúng dữ kiện — {duong}")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.limit, a.out)))
