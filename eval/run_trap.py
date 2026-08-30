"""Chạy `eval/datasets/trap.yaml` qua graph thật, in bảng theo nhóm, ghi kết
quả kèm `commit_hash` (M6, silent-failure review round 2 — không có runner
trong repo thì con số 39/40 (nay 44/45) không tái lập được và không gác
regression cho chuỗi bảy phép kiểm).

    python -m eval.run_trap [--limit N] [--out PATH]
"""

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

import yaml

from src.agents.graph_tra_cuu import build_graph_tra_cuu

TRAP_PATH = Path(__file__).resolve().parent / "datasets" / "trap.yaml"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def dung(it: dict, st: dict) -> bool:
    """`ky_vong` → hành vi đúng. Cùng quy tắc chấm điểm đã dùng suốt Task 10
    (out_of_scope/abstain khớp thẳng; warning_* cần answer + có cảnh báo)."""
    rt = st["result_type"].value if hasattr(st["result_type"], "value") else st["result_type"]
    kv = it["ky_vong"]
    if kv == "out_of_scope":
        return rt == "out_of_scope"
    if kv == "abstain":
        return rt == "abstain"
    if kv.startswith("warning_"):
        return rt == "answer" and bool(st.get("warnings"))
    return False


def commit_hash() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=_REPO_ROOT
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


async def chay(items: list[dict]) -> dict:
    g = build_graph_tra_cuu()
    theo_nhom: dict[str, list[int]] = {}
    chi_tiet = []
    for it in items:
        st = await g.ainvoke({"query": it["cau_hoi"]})
        rt = st["result_type"].value if hasattr(st["result_type"], "value") else st["result_type"]
        d = dung(it, st)
        cap = theo_nhom.setdefault(it["nhom"], [0, 0])
        cap[0] += int(d)
        cap[1] += 1
        chi_tiet.append({"id": it["id"], "nhom": it["nhom"], "dung": d, "result_type": rt})
    return {"commit_hash": commit_hash(), "theo_nhom": theo_nhom, "chi_tiet": chi_tiet}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="chỉ chạy N câu đầu (vd. để tiết kiệm ngân sách API)")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results" / "trap_run.json")
    args = ap.parse_args()

    items = yaml.safe_load(TRAP_PATH.read_text(encoding="utf-8"))["items"]
    if args.limit:
        items = items[: args.limit]

    ket = asyncio.run(chay(items))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"commit_hash={ket['commit_hash']}")
    tong_dung = tong_cau = 0
    for nhom, (d, tong) in sorted(ket["theo_nhom"].items()):
        print(f"  {nhom}: {d}/{tong} = {d / tong:.0%}")
        tong_dung += d
        tong_cau += tong
    if tong_cau:
        print(f"TỔNG: {tong_dung}/{tong_cau} = {tong_dung / tong_cau:.0%}")


if __name__ == "__main__":
    main()
