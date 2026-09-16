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
import math
import subprocess
import sys
import time
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


def _dem_corpus() -> dict:
    """Dấu vân tay corpus: số hàng ba bảng. Rẻ, tất định, đủ để phát hiện hai
    lượt chạy trên hai kho khác nhau. DB hỏng KHÔNG làm hỏng lượt đo — trả `{}`
    và để `so_loi` của chính lượt đó nói phần còn lại."""
    try:
        from sqlalchemy import text

        from src.services.db import get_engine

        with get_engine().connect() as c:
            return {
                b: int(c.execute(text(f"select count(*) from {b}")).scalar() or 0)
                for b in ("documents", "provisions", "chunks")
            }
    except Exception:  # noqa: BLE001 — metadata thiếu còn hơn lượt đo mất trắng
        return {}


def _moi_truong(dem: dict | None = None) -> dict:
    """Mọi thứ phải trùng nhau thì hai lượt mới so được: model TỪNG VAI, corpus,
    `as_of_date`, trạng thái cache.

    `glm/v3.json` (`trung_dan=0.364`) và `soul-v4/v3-77.json` (`0.662`) cùng chạy
    `assemble.v3` mà lệch 30 điểm vì khác model — và không tệp nào ghi lại model,
    nên giờ không đối chiếu được nữa. KHÔNG ghi khoá API: tệp kết quả được commit.
    """
    from src.config import as_of_hieu_luc, get_settings

    s = get_settings()
    return {
        "model": {
            "chinh": s.openrouter_model_name,
            "generate": s.openrouter_generate_model_name,
            "judge": s.openrouter_judge_model_name,
            "embedding": s.openrouter_embedding_model_name,
            "rerank": s.openrouter_rerank_model_name,
        },
        "corpus": _dem_corpus() if dem is None else dem,
        "as_of_date": str(as_of_hieu_luc(None)),
        "cache_ttl_ngay": s.cache_ttl_ngay,
    }


def _p95(xs: list[float]) -> float:
    """Nearest-rank: p95 của 20 mẫu là mẫu thứ 19, KHÔNG phải mẫu lớn nhất."""
    if not xs:
        return 0.0
    ds = sorted(xs)
    return ds[math.ceil(0.95 * len(ds)) - 1]


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


# Trần mỗi câu và số câu chạy cùng lúc. ĐO ĐƯỢC 2026-09-16: một lượt trên
# `deepseek/deepseek-v4-flash-0731` chạy 1 giờ 53 phút mà không ghi nổi một tệp
# kết quả — một luồng kẹt trong `_ssl__SSLSocket_read`, và `timeout=180` của
# tầng HTTP không cứu được vì mỗi câu là NHIỀU lượt gọi. Trần ở đây là trần của
# CẢ CÂU, không phải của một lượt gọi.
TRAN_GIAY = 600.0
SONG_SONG = 5


async def mot_cau(g, it: dict, sem: asyncio.Semaphore, tran_giay: float = TRAN_GIAY) -> dict:
    """Một câu — luôn trả về MỘT hàng, kể cả khi hỏng.

    Hết giờ đi chung một đường với mọi lỗi khác (`loi`), nên nó bị loại khỏi CẢ
    tử số lẫn mẫu số của mọi tỉ lệ, đúng cam kết đã có: một câu lỗi không được
    làm mất cả lượt, và cũng không được lặng lẽ thành một câu trả lời sai.
    """
    async with sem:
        t0 = time.perf_counter()
        try:
            st = await asyncio.wait_for(
                g.ainvoke({"query": it["cau_hoi"], "lich_su": []}), timeout=tran_giay
            )
        except Exception as e:  # noqa: BLE001 — một câu lỗi không được làm mất cả lượt
            print(f"[{it['id']}] LỖI {type(e).__name__}: {e}", file=sys.stderr)
            return {"id": it["id"], "loi": f"{type(e).__name__}: {e}"}

        rt = st["result_type"]
        rt = rt.value if hasattr(rt, "value") else str(rt)
        tra = st.get("answer") or ""
        da_dan = _duong_dan_da_dan(st)
        tr = st.get("traces") or {}
        return {
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
            "latency_s": round(time.perf_counter() - t0, 3),
        }


async def chay(items: list[dict], prompt: str, song_song: int = SONG_SONG,
               tran_giay: float = TRAN_GIAY) -> dict:
    g = build_graph_tra_cuu()
    sem = asyncio.Semaphore(song_song)
    # `gather` giữ NGUYÊN thứ tự đầu vào, nên hàng kết quả vẫn so được theo id
    # giữa hai lượt chạy khác mức song song.
    hang = list(await asyncio.gather(*(mot_cau(g, it, sem, tran_giay) for it in items)))

    ok = [h for h in hang if "loi" not in h]
    n = len(ok) or 1
    return {
        "commit_hash": _commit(),
        "moi_truong": {**_moi_truong(), "song_song": song_song, "tran_giay": tran_giay},
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
        "latency_p95": _p95([h["latency_s"] for h in ok]),
        "hang": hang,
    }


def _in(kq: dict) -> None:
    print(f"\n── {kq['prompt']} · commit {kq['commit_hash']} ──")
    mt = kq.get("moi_truong") or {}
    if mt:
        m = mt.get("model") or {}
        print(f"model            {m.get('chinh')} · generate {m.get('generate')} · judge {m.get('judge')}")
        print(f"corpus           {mt.get('corpus')} · as_of {mt.get('as_of_date')} · cache {mt.get('cache_ttl_ngay')} ngày")
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


def _bang(teps: list[Path]) -> None:
    """Bảng ngang nhiều lượt chạy — mỗi cột một lượt.

    `--so-sanh` chỉ nhận hai tệp, đủ cho một thay đổi. Khi đang cân nhắc nhiều
    model thì hai-một-lần bắt người đọc ghép bảng trong đầu, và đó là lúc người
    ta nhớ nhầm con số.

    In `so_chay_duoc` NGAY DƯỚI tên lượt: một lượt 48/77 và một lượt 77/77 có
    tỉ lệ nằm trên hai mẫu số khác nhau, và quên điều đó là cách dễ nhất để đọc
    ra một kết luận ngược.
    """
    kqs = [json.loads(t.read_text(encoding="utf-8")) for t in teps]
    ten = [f"{t.parent.name}/{Path(k['prompt']).stem.replace('assemble.', '')}" for t, k in zip(teps, kqs)]
    rong = max(14, max(len(x) for x in ten) + 1)

    print()
    print(f"{'':<18}" + "".join(f"{x:>{rong}}" for x in ten))
    print(f"{'chạy được':<18}" + "".join(f"{k['so_chay_duoc']}/{k['so_cau']:<{rong-5}}" for k in kqs))
    for nhan, khoa in [
        ("TRÚNG DẪN", "trung_dan"),
        ("trích dẫn đúng", "trich_dan_dung"),
        ("answer", "answer"),
        ("abstain", "abstain"),
    ]:
        print(f"{nhan:<18}" + "".join(f"{k[khoa]:>{rong}.1%}" for k in kqs))
    print(f"{'độ dài tb':<18}" + "".join(f"{k['do_dai_tb']:>{rong}.0f}" for k in kqs))
    print(f"{'chi phí':<18}" + "".join(f"{k['chi_phi_tong']:>{rong}.4f}" for k in kqs))
    print(f"{'lỗi':<18}" + "".join(f"{k['so_loi']:>{rong}}" for k in kqs))
    xau = [t for t, k in zip(ten, kqs) if k["so_loi"]]
    if xau:
        print(f"\n‼️  Lượt có lỗi ({', '.join(xau)}): tỉ lệ nằm trên mẫu số NHỎ HƠN, không so trực tiếp được.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompt", default=None, help="đường dẫn prompt assemble; bỏ trống = mặc định")
    p.add_argument("--so", type=int, default=0, help="chỉ chạy N câu đầu (0 = tất cả)")
    p.add_argument("--song-song", type=int, default=SONG_SONG, help=f"số câu chạy cùng lúc (mặc định {SONG_SONG})")
    p.add_argument("--tran-giay", type=float, default=TRAN_GIAY, help=f"trần giây cho MỖI câu (mặc định {TRAN_GIAY:.0f})")
    p.add_argument("--json", type=Path, help="ghi kết quả ra tệp")
    p.add_argument("--so-sanh", nargs=2, type=Path, metavar=("GOC", "MOI"), help="so hai tệp kết quả")
    p.add_argument("--bang", nargs="+", type=Path, metavar="JSON", help="bảng ngang nhiều lượt")
    a = p.parse_args()

    if a.bang:
        _bang(a.bang)
        return
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

    kq = asyncio.run(chay(items, get_settings().assemble_prompt, a.song_song, a.tran_giay))
    _in(kq)
    if a.json:
        a.json.write_text(json.dumps(kq, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {a.json}")


if __name__ == "__main__":
    main()
