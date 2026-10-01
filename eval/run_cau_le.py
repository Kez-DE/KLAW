"""Câu lẻ qua toàn đồ thị: câu tranh chấp nhà đất và bộ live thông tin nội bộ
(`eval/datasets/cau_le.yaml`). TỐN PHÍ: mô hình định tuyến, sinh, thẩm định thật.

    python -m eval.run_cau_le --bo dat|live --out PATH

Mỗi lượt một trạng thái mới qua `build_graph_tra_cuu` — không cache, không ghi traces,
như `eval/run_trap.py`. Ghi cho từng lượt đúng phản hồi người dùng nhận
(`routes._payload_cache` → `routes.tra_cuu_response`, hình dạng duy nhất `/tra-cuu` trả)
và, tách riêng, sổ sách nội bộ không bao giờ hiện cho người dùng: ý định, truy vấn viết
lại, token và chi phí từ traces, số lượt gọi mô hình và số lượt gọi API nhúng đếm được.
Một lượt lỗi không làm mất cả bộ. Điều kiện chạy (mô hình, mốc hiệu lực, cache, nhánh từ
vựng) đặt bằng biến môi trường như `eval/run_cau_tra_loi.py` và được ghi ở `moi_truong`.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

from eval.run_cau_tra_loi import _commit, _moi_truong
from src.agents.graph_tra_cuu import build_graph_tra_cuu
from src.api import routes
from src.services import embedding, llm
from src.services.hoi_thoai import _luot_thanh_lich_su
from src.services.traces import _tong_hop_traces

DATA = Path(__file__).resolve().parent / "datasets" / "cau_le.yaml"
DEM = {"chat": 0, "embed_http": 0}


def doc_bo(ten: str) -> list[dict]:
    """Một bộ của `cau_le.yaml`: danh sách `{nhom, cau_hoi}`; `cau_hoi` là danh sách = một hội thoại."""
    return yaml.safe_load(DATA.read_text(encoding="utf-8"))[ten]


def _dem(cls: type, ten: str, khoa: str) -> None:
    goc = getattr(cls, ten)

    def boc(self, *a, **k):
        DEM[khoa] += 1
        return goc(self, *a, **k)

    setattr(cls, ten, boc)


async def mot(g, nhom: str, cau: str, lich_su: list[dict]) -> tuple[dict, dict | None]:
    DEM.update(chat=0, embed_http=0)
    t0 = time.perf_counter()
    try:
        st = await g.ainvoke({"query": cau, "lich_su": lich_su})
    except Exception as e:  # noqa: BLE001 — một lượt lỗi không được làm mất cả bộ đã tốn phí
        print(f"[cau_le] LỖI {cau!r}: {type(e).__name__}: {e}", file=sys.stderr)
        return {"nhom": nhom, "cau_hoi": cau, "lich_su": lich_su, "error_type": type(e).__name__, "error": str(e)}, None
    rt = st.get("result_type")
    rt = rt.value if hasattr(rt, "value") else str(rt)
    payload = routes._payload_cache(st, rt)
    tr = _tong_hop_traces(st.get("traces") or {})
    return {
        "nhom": nhom,
        "cau_hoi": cau,
        "lich_su": lich_su,
        "result_type": rt,
        "nguoi_dung_thay": routes.tra_cuu_response(payload, "cau-le", "default").model_dump(mode="json"),
        "noi_bo": {
            "intent": str(st.get("intent")),
            "queries": st.get("queries"),
            "token_in": tr["token_in"],
            "token_out": tr["token_out"],
            "cost_usd": tr["cost_usd"],
            "goi_chat": DEM["chat"],
            "goi_embedding_http": DEM["embed_http"],
            "latency_s": round(time.perf_counter() - t0, 2),
        },
    }, payload


async def chay(g, bo: list[dict]) -> list[dict]:
    ra: list[dict] = []
    for muc in bo:
        cau = muc["cau_hoi"]
        if isinstance(cau, str):
            ra.append((await mot(g, muc["nhom"], cau, []))[0])
            continue
        lich_su: list[dict] = []
        for k, c in enumerate(cau, 1):
            h, payload = await mot(g, f"{muc['nhom']}_{k}", c, lich_su)
            ra.append(h)
            if payload is not None:
                lich_su = [*lich_su, _luot_thanh_lich_su(c, payload)]
    return ra


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bo", choices=("dat", "live"), required=True)
    ap.add_argument("--out", type=Path, required=True, help="tệp kết quả (lượt tốn phí: luôn ghi)")
    a = ap.parse_args()
    _dem(llm.LlmClient, "chat", "chat")
    _dem(embedding.EmbeddingClient, "_post_with_retry", "embed_http")
    hang = asyncio.run(chay(build_graph_tra_cuu(), doc_bo(a.bo)))
    kq = {
        "bo": a.bo,
        "commit_hash": _commit(),
        "chay_luc": datetime.now(UTC).isoformat(),
        "moi_truong": _moi_truong(),
        "so_loi": sum("error" in h for h in hang),
        "hang": hang,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(kq, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for h in hang:
        nb = h.get("noi_bo") or {}
        print(h["nhom"], h.get("result_type", "LOI"), nb.get("goi_chat"), nb.get("cost_usd"), "|", h["cau_hoi"][:50])
    print(f"{len(hang)} lượt, {kq['so_loi']} lỗi — {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
