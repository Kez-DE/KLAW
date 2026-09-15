"""So hai prompt trả lời trên bộ 77 câu vàng (spec 2026-09-15f).

Chạy: `python -m eval.run_cau_tra_loi --prompt prompts/assemble.v4.md [--so 15]`

**Chỉ đo thứ đo được.** Không chấm "câu trả lời hay không" bằng một mô hình khác
— đó là đúng cái sai mà khoá luận này tồn tại để chống: nhờ LLM tự kiểm chính nó.
Sáu cột dưới đây đều tất định, tính bằng Python, lặp lại được:

* **trung_dan**  — câu trả lời có dẫn ĐÚNG điều luật mà người duyệt đã ghi ở
  `duong_dan` không. Đây là cột quan trọng nhất: nó trả lời "trả lời đúng câu
  hỏi của khách hàng" bằng một phép tra bảng chứ không bằng cảm nhận.
* **trich_dan_dung** — `citation_precision` của tầng 1, 0 token.
* **result_type**  — phân bố answer / partial_coverage / abstain / out_of_scope.
  Abstain KHÔNG phải cột xấu: trên câu vàng thì abstain nhiều là dở, nhưng nó
  phải được đọc cùng `trung_dan` chứ không một mình.
* **co_tang_4 / co_tang_5** — hai tầng mới của v4 có xuất hiện không, và có
  xuất hiện ĐÚNG LÚC không (bỏ được khi không cần).
* **do_dai**     — số ký tự. Bức tường chữ là cách một câu trả lời đúng vẫn hỏng.
* **chi_phi**    — USD thật từ `traces`.

Một câu lỗi KHÔNG làm mất cả lượt chạy — cùng lý do `run_trap.chay` đã ghi:
một lượt 45 câu từng mất trắng vì đúng một câu ăn HTTP 429.
"""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import yaml

from src.agents.graph_tra_cuu import build_graph_tra_cuu
from src.agents.nodes.verify_tier1 import citation_precision

BO_CAU = Path("eval/datasets/golden_qa.yaml")
CUM_TANG_4 = "Kết luận này đổi nếu"
CUM_TANG_5 = "Bạn có thể làm ngay:"


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "khong-ro"


def _duong_dan_da_dan(st: dict) -> set[str]:
    """`duong_dan` của mọi trích dẫn đã qua kiểm chứng trong câu trả lời."""
    ra = set()
    for c in st.get("citations") or []:
        dd = c.get("duong_dan") if isinstance(c, dict) else getattr(c, "duong_dan", None)
        if dd:
            ra.add(str(dd).strip())
    return ra


def _trung(mong_doi, da_dan: set[str]) -> bool:
    """Có dẫn đúng điều luật người duyệt đã ghi không.

    `duong_dan` của bộ vàng là một DANH SÁCH: một câu hỏi có thể có nhiều điều
    luật cùng đúng. Dẫn được MỘT trong số đó là trúng — đòi đủ cả danh sách sẽ
    chấm trượt một câu trả lời đúng chỉ vì nó gọn hơn nhãn.

    So theo TIỀN TỐ hai chiều: người duyệt ghi tới cấp Điều, còn hệ thống có thể
    dẫn tới cấp Khoản của chính Điều đó — và ngược lại. Đòi khớp tuyệt đối sẽ
    chấm trượt một câu trả lời chính xác hơn cả nhãn.
    """
    ds = mong_doi if isinstance(mong_doi, list) else [mong_doi]
    for m in (str(x).strip() for x in ds if x):
        if any(d == m or d.startswith(m + " >") or m.startswith(d + " >") for d in da_dan):
            return True
    return False


async def chay(items: list[dict], prompt: str) -> dict:
    g = build_graph_tra_cuu()
    hang = []
    for it in items:
        try:
            st = await g.ainvoke({"query": it["cau_hoi"], "lich_su": []})
        except Exception as e:  # noqa: BLE001 — một câu lỗi không được làm mất cả lượt
            print(f"[{it['id']}] LỖI {type(e).__name__}: {e}", file=sys.stderr)
            hang.append({"id": it["id"], "loi": f"{type(e).__name__}: {e}"})
            continue

        rt = st["result_type"]
        rt = rt.value if hasattr(rt, "value") else str(rt)
        tra = st.get("answer") or ""
        da_dan = _duong_dan_da_dan(st)
        tr = st.get("traces") or {}
        hang.append(
            {
                "id": it["id"],
                "result_type": rt,
                "trung_dan": _trung(it.get("duong_dan", ""), da_dan),
                "so_trich_dan": len(da_dan),
                # Tính THẲNG từ `st["tier1"]`, không đọc traces: `citation_precision`
                # là hàm thuần 0 token, và đọc lại từ traces thêm một chỗ có thể lệch.
                "trich_dan_dung": citation_precision(st.get("tier1") or []),
                "co_tang_4": CUM_TANG_4 in tra,
                "co_tang_5": CUM_TANG_5 in tra,
                "do_dai": len(tra),
                "chi_phi": float(tr.get("cost_usd") or 0.0),
            }
        )

    ok = [h for h in hang if "loi" not in h]
    n = len(ok) or 1
    return {
        "commit_hash": _commit(),
        "prompt": prompt,
        "so_cau": len(items),
        "so_chay_duoc": len(ok),
        "so_loi": len(hang) - len(ok),
        "trung_dan": sum(h["trung_dan"] for h in ok) / n,
        "trich_dan_dung": sum(h["trich_dan_dung"] or 0 for h in ok) / n,
        "abstain": sum(h["result_type"] == "abstain" for h in ok) / n,
        "answer": sum(h["result_type"] == "answer" for h in ok) / n,
        "co_tang_4": sum(h["co_tang_4"] for h in ok) / n,
        "co_tang_5": sum(h["co_tang_5"] for h in ok) / n,
        "do_dai_tb": sum(h["do_dai"] for h in ok) / n,
        "chi_phi_tong": sum(h["chi_phi"] for h in ok),
        "hang": hang,
    }


def _in(kq: dict) -> None:
    print(f"\n── {kq['prompt']} · commit {kq['commit_hash']} ──")
    print(f"chạy được        {kq['so_chay_duoc']}/{kq['so_cau']}  (lỗi {kq['so_loi']})")
    print(f"TRÚNG DẪN        {kq['trung_dan']:.1%}   ← dẫn đúng điều luật người duyệt ghi")
    print(f"trích dẫn đúng   {kq['trich_dan_dung']:.1%}")
    print(f"answer / abstain {kq['answer']:.1%} / {kq['abstain']:.1%}")
    print(f"có tầng 4 / 5    {kq['co_tang_4']:.1%} / {kq['co_tang_5']:.1%}")
    print(f"độ dài trung bình {kq['do_dai_tb']:.0f} ký tự")
    print(f"chi phí          ${kq['chi_phi_tong']:.4f}")


def _so_sanh(a: dict, b: dict) -> None:
    """Bảng delta giữa hai lượt chạy.

    In cả hai cột gốc chứ không chỉ delta: một delta +2% trên nền 40% và trên nền
    95% là hai câu chuyện khác nhau, và người đọc bảng phải thấy được nền.

    Không tô màu "tốt/xấu" cho `abstain` và `do_dai_tb`: abstain nhiều trên bộ
    câu vàng là dở, nhưng abstain là hành vi ĐÚNG ở chỗ khác, nên gắn nhãn xấu
    cố định cho nó là dạy sai người đọc bảng.
    """
    cot = [
        ("TRÚNG DẪN", "trung_dan", True),
        ("trích dẫn đúng", "trich_dan_dung", True),
        ("answer", "answer", True),
        ("abstain", "abstain", None),
        ("có tầng 4", "co_tang_4", None),
        ("có tầng 5", "co_tang_5", None),
    ]
    print(f"\n{'':<18}{Path(a['prompt']).stem:>12}{Path(b['prompt']).stem:>12}{'delta':>10}")
    for nhan, khoa, cao_la_tot in cot:
        va, vb = a[khoa], b[khoa]
        d = vb - va
        dau = "" if cao_la_tot is None else ("  ↑" if d > 0.001 else "  ↓" if d < -0.001 else "  =")
        print(f"{nhan:<18}{va:>11.1%}{vb:>12.1%}{d:>+9.1%}{dau}")
    print(f"{'độ dài tb':<18}{a['do_dai_tb']:>11.0f}{b['do_dai_tb']:>12.0f}{b['do_dai_tb'] - a['do_dai_tb']:>+9.0f}")
    print(f"{'chi phí':<18}{a['chi_phi_tong']:>11.4f}{b['chi_phi_tong']:>12.4f}{b['chi_phi_tong'] - a['chi_phi_tong']:>+9.4f}")
    print(f"{'lỗi':<18}{a['so_loi']:>11}{b['so_loi']:>12}")

    # Câu nào ĐỔI kết quả — đây mới là chỗ đọc để hiểu vì sao delta như vậy.
    ta = {h["id"]: h.get("trung_dan") for h in a["hang"] if "loi" not in h}
    tb = {h["id"]: h.get("trung_dan") for h in b["hang"] if "loi" not in h}
    mat = sorted(i for i in ta if ta[i] and not tb.get(i, False))
    them = sorted(i for i in tb if tb[i] and not ta.get(i, False))
    if them:
        print(f"\nTrúng THÊM ({len(them)}): {', '.join(them[:8])}")
    if mat:
        print(f"MẤT trúng ({len(mat)}): {', '.join(mat[:8])}")
    if not them and not mat:
        print("\nKhông câu nào đổi kết quả trúng dẫn.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompt", default=None, help="đường dẫn prompt assemble; bỏ trống = mặc định")
    p.add_argument("--so", type=int, default=0, help="chỉ chạy N câu đầu (0 = tất cả)")
    p.add_argument("--json", type=Path, help="ghi kết quả ra tệp")
    p.add_argument("--so-sanh", nargs=2, type=Path, metavar=("GOC", "MOI"), help="so hai tệp kết quả")
    a = p.parse_args()

    if a.so_sanh:
        _so_sanh(*(json.loads(t.read_text(encoding="utf-8")) for t in a.so_sanh))
        return

    if a.prompt:
        # `get_settings` là `lru_cache`, nên phải đặt TRƯỚC khi graph đọc nó.
        import os

        os.environ["KLAW_ASSEMBLE_PROMPT"] = a.prompt
        from src.config import get_settings

        get_settings.cache_clear()

    from src.config import get_settings

    items = yaml.safe_load(BO_CAU.read_text(encoding="utf-8"))
    items = items if isinstance(items, list) else items.get("items")
    if a.so:
        items = items[: a.so]

    kq = asyncio.run(chay(items, get_settings().assemble_prompt))
    _in(kq)
    if a.json:
        a.json.write_text(json.dumps(kq, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {a.json}")


if __name__ == "__main__":
    main()
