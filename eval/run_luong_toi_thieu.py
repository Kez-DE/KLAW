"""Ca lương tối thiểu, chạy N lần — ca chứng minh CẢ HAI bản vá tầng dữ liệu.

Vì sao cần một runner riêng thay vì một dòng trong `trap.yaml`: `run_trap.dung()`
chỉ chấm `result_type`, còn ca này phải kiểm ba thứ mà `result_type` không nói
được — con số trong câu trả lời có khớp bảng lương không, trích dẫn có trỏ đúng
điều khoản CHỨA bảng không, và bốn nghị định đã chết có được cảnh báo không.

Vì sao N lần chứ không một lần: đo được (2026-09-01) rằng cùng một truy vấn cho
lúc `answer` lúc `abstain`. Một lần chạy vì thế KHÔNG phải một phép đo, nó là một
mẫu; con số trích dẫn được là TỈ LỆ trên N.

    python -m eval.run_luong_toi_thieu [--n 10] [--out PATH]
"""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from src.agents.graph_tra_cuu import build_graph_tra_cuu

CAU_HOI = "lương tối thiểu vùng I là bao nhiêu"
SO_DUNG = "5.310.000"                       # Vùng I, bảng tại 293/2025 Điều 3 Khoản 1
NEO_BANG = "293/2025/NĐ-CP > Điều 3"        # tiền tố: Điều 3 hoặc Khoản/Điểm con của nó
DA_CHET = ("122/2015/NĐ-CP", "141/2017/NĐ-CP", "157/2018/NĐ-CP", "90/2019/NĐ-CP", "74/2024/NĐ-CP")
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True, cwd=_REPO_ROOT).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def cham(st: dict) -> dict:
    """Ba phép kiểm của đề bài + result_type. Mỗi cái ĐỘC LẬP: một câu trả lời có
    thể đúng số mà sai trích dẫn, và gộp chúng lại là giấu mất chế độ hỏng đó."""
    rt = st["result_type"]
    rt = getattr(rt, "value", rt)
    answer = st.get("answer") or ""
    cits = st.get("citations") or []
    neo = [c.get("duong_dan", "") if isinstance(c, dict) else getattr(c, "duong_dan", "") for c in cits]
    canh_bao = " ".join(st.get("warnings") or [])
    return {
        "result_type": rt,
        "co_so_dung": SO_DUNG in answer,
        "trich_dan_dung_bang": any(n.startswith(NEO_BANG) for n in neo),
        "canh_bao_van_ban_chet": sorted(d for d in DA_CHET if d in canh_bao),
        "n_citations": len(cits),
        "neo": neo[:6],
    }


async def chay(n: int) -> dict:
    """N lượt, MỘT lượt lỗi KHÔNG được làm mất cả phép đo.

    Cùng khuôn `eval.run_trap.chay` và vì cùng lý do đã đo được ở đó
    ("HAI lượt chạy 45 câu mất trắng vì đúng một câu ăn HTTP 429") — bài học ấy
    chỉ được áp ở `run_trap.py` mà không áp sang đây, nên khi OpenRouter siết
    hạn mức (2026-09-02, mọi lượt gọi ăn 429 ít nhất một lần) một 429 duy nhất
    giết cả 10 lượt và không ghi ra file nào. Cổng đo mất trắng đúng lúc cần nó
    nhất.

    Lỗi hạ tầng ghi RIÊNG (`n_loi`), KHÔNG cộng vào `abstain` — một lượt crash
    không phải một lượt hệ thống chọn im lặng, và gộp hai thứ đó lại sẽ làm con
    số abstain (đóng góp trung tâm của khoá luận) trông tệ hơn sự thật.

    Mọi tỉ lệ tính trên `n_do_duoc`, không trên `n`: chia cho số lượt ĐÃ CHẠY,
    không cho số lượt ĐÃ ĐỊNH chạy.
    """
    g = build_graph_tra_cuu()
    lan: list[dict] = []
    loi: list[dict] = []
    for i in range(n):
        try:
            st = await g.ainvoke({"query": CAU_HOI})
        except Exception as e:  # noqa: BLE001 - cố ý bắt rộng, xem docstring
            print(f"[luong] LỖI lượt {i + 1}/{n}: {type(e).__name__}: {e}", file=sys.stderr)
            loi.append({"lan": i + 1, "error_type": type(e).__name__, "error": str(e)})
            continue
        lan.append(cham(st))
    tong = {
        "n": n,
        "n_do_duoc": len(lan),
        "n_loi": len(loi),
        "answer": sum(r["result_type"] == "answer" for r in lan),
        "abstain": sum(r["result_type"] == "abstain" for r in lan),
        "co_so_dung": sum(r["co_so_dung"] for r in lan),
        "trich_dan_dung_bang": sum(r["trich_dan_dung_bang"] for r in lan),
        "co_it_nhat_mot_canh_bao": sum(bool(r["canh_bao_van_ban_chet"]) for r in lan),
    }
    return {"cau_hoi": CAU_HOI, "commit_hash": _commit(), "tong_hop": tong,
            "tung_lan": lan, "loi": loi}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parent / "results" / "luong_toi_thieu.json")
    a = ap.parse_args()
    ket = asyncio.run(chay(a.n))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(ket, ensure_ascii=False, indent=2), encoding="utf-8")
    t = ket["tong_hop"]
    print(f"commit={ket['commit_hash']}  n={t['n']}")
    for k in ("answer", "abstain", "co_so_dung", "trich_dan_dung_bang", "co_it_nhat_mot_canh_bao"):
        print(f"  {k:26s} {t[k]}/{t['n']} = {t[k] / t['n']:.0%}")


if __name__ == "__main__":
    main()
