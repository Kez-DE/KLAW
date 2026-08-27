"""Cổng A — Data Integrity Audit (spec 16.3).

Bắt lỗi parser mất nội dung ÂM THẦM — loại lỗi làm Recall@5 và citation
precision đều xấu mà không để lại dấu vết.

⚠ ĐIỂM THIẾT KẾ QUAN TRỌNG: KHÔNG được kiểm bằng cách chạy lại parse_provisions
rồi so với DB. Cả hai đến từ CÙNG một parser nên phép so đó là hằng đúng — nó
chỉ bắt được lỗi ingest/DB, KHÔNG bắt được lỗi parser.

Phép kiểm thật phải ĐỘC LẬP VỚI PARSER: strip toàn bộ tag khỏi HTML gốc để lấy
tập ký tự "sự thật", rồi đo xem nội dung trong DB phủ được bao nhiêu phần. Nếu
parser bỏ sót prov-content không có id (bẫy #2) thì độ phủ tụt ngay.

Cái cổng này KHÔNG thấy được (mất cấu trúc, token vẫn đủ) là việc của
`prov_parser.parse_anomalies()` — xem docs/gate-a-report.md mục "Lỗ của Cổng A".
"""

import json
import random
import re
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup
from sqlalchemy import text

from scripts.fetch_moj import DOC_IDS
from src.config import get_settings
from src.services.db import get_engine

BO_LUAT = ["95942", "96122", "96115", "96172", "139264", "96117"]


def _norm(s: str) -> str:
    """Gộp khoảng trắng + chuẩn hoá Unicode NFC.

    NFC áp ĐỐI XỨNG cho cả hai phía so sánh: tiếng Việt tồn tại ở cả dạng tổ hợp
    dấu (NFD: "ê" = e + U+0302) và dựng sẵn (NFC: U+00EA). Hai dạng khác nhau về
    codepoint nhưng cùng một chữ, nên nếu một phía là NFD và phía kia là NFC thì
    so sánh token sẽ báo LỆCH GIẢ trên gần như mọi từ có dấu.

    NFC là mức chuẩn hoá ĐỦ VÀ KHÔNG QUÁ TAY: nó chỉ hợp nhất các dãy codepoint
    tương đương chính tắc, KHÔNG bỏ dấu (unaccent), KHÔNG hạ chữ (casefold),
    KHÔNG gộp NFKC (vốn biến "①"→"1", "ﬁ"→"fi"). Nhờ vậy một token thật sự bị mất
    vẫn hiện ra là mất — chuẩn hoá không che được lệch thật.
    """
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", s)).strip()


def _van_ban_goc(html: str) -> str:
    """Sự thật ĐỘC LẬP VỚI PARSER: bỏ hết tag, chỉ giữ text.

    Bỏ <table> vì bảng được lưu riêng (bẫy #4), không nằm trong provisions.noi_dung
    theo đường prov-*.
    """
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all("table"):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with(" ")
    return _norm(soup.get_text(" "))


def audit(n: int = 30, seed: int = 42) -> dict:
    """Hai phép kiểm độc lập.

    A. ĐỘ PHỦ (độc lập với parser) — trên CẢ 6 Bộ luật, không lấy mẫu:
       ghép mọi tieu_de + noi_dung trong DB, đo xem phủ được bao nhiêu phần
       tập token của văn bản gốc đã strip tag. Đây là phép kiểm bắt được bẫy #2.
    B. RỖNG — Điều nào vừa không có nội dung vừa không có con.
    """
    random.seed(seed)
    raw = Path(get_settings().data_raw_dir) / "moj"
    per_doc: list[dict] = []
    chi_tiet: list[dict] = []
    rong_tong = 0

    with get_engine().connect() as conn:
        for doc_id in BO_LUAT:
            so_ky_hieu = DOC_IDS[doc_id][1]
            rows = conn.execute(text(
                "SELECT id, cap, so_hieu_cap, tieu_de, noi_dung,"
                " (SELECT count(*) FROM provisions c WHERE c.parent_id = p.id) AS so_con"
                " FROM provisions p WHERE document_id = :d"
            ), {"d": doc_id}).mappings().all()
            if not rows:
                chi_tiet.append({"doc_id": doc_id, "loi": "KHÔNG CÓ provision nào trong DB"})
                per_doc.append({"doc_id": doc_id, "so_ky_hieu": so_ky_hieu, "do_phu": 0.0,
                                "rong": 0, "provisions": 0, "token_goc": 0, "token_thieu": 0})
                continue

            html = json.loads((raw / f"{doc_id}.json").read_text(encoding="utf-8"))
            goc_tokens = set(_van_ban_goc(html["documentContent"]["content"]).split())
            db_tokens = set(_norm(" ".join(
                f"{r['tieu_de']} {r['noi_dung']}" for r in rows)).split())

            do_phu = len(goc_tokens & db_tokens) / len(goc_tokens) if goc_tokens else 0.0
            thieu = sorted(goc_tokens - db_tokens)

            rong = [r for r in rows if r["cap"] == "dieu"
                    and not (r["noi_dung"] or "").strip() and r["so_con"] == 0]
            rong_tong += len(rong)
            for r in random.sample(rong, min(5, len(rong))):
                chi_tiet.append({"doc_id": doc_id, "dieu": r["so_hieu_cap"],
                                 "loi": "Điều RỖNG và không có con"})
            if do_phu < 0.98:
                chi_tiet.append({"doc_id": doc_id, "loi": f"độ phủ {do_phu:.2%}",
                                 "token_mat_mau": thieu[:n]})

            per_doc.append({"doc_id": doc_id, "so_ky_hieu": so_ky_hieu,
                            "do_phu": round(do_phu, 4), "rong": len(rong),
                            "provisions": len(rows), "token_goc": len(goc_tokens),
                            "token_thieu": len(thieu), "token_thieu_mau": thieu[:n]})

    do_phu_min = min((d["do_phu"] for d in per_doc), default=0.0)
    return {"per_doc": per_doc, "do_phu_min": do_phu_min, "rong_tong": rong_tong,
            "pass": rong_tong == 0 and do_phu_min >= 0.98,
            "chi_tiet": chi_tiet}


if __name__ == "__main__":
    r = audit()
    gon = {k: v for k, v in r.items() if k != "chi_tiet"}
    gon["per_doc"] = [{k: v for k, v in d.items() if k != "token_thieu_mau"}
                      for d in gon["per_doc"]]
    print(json.dumps(gon, ensure_ascii=False, indent=2))
    for c in r["chi_tiet"][:40]:
        print(" -", c)
    raise SystemExit(0 if r["pass"] else 1)
