"""Cổng A — Data Integrity Audit (spec 16.3).

Bắt lỗi parser mất nội dung ÂM THẦM — loại lỗi làm Recall@5 và citation
precision đều xấu mà không để lại dấu vết.

⚠ ĐIỂM THIẾT KẾ QUAN TRỌNG: KHÔNG được kiểm bằng cách chạy lại parse_provisions
rồi so với DB. Cả hai đến từ CÙNG một parser nên phép so đó là hằng đúng — nó
chỉ bắt được lỗi ingest/DB, KHÔNG bắt được lỗi parser.

Phép kiểm thật phải ĐỘC LẬP VỚI PARSER: strip toàn bộ tag khỏi HTML gốc để lấy
tập ký tự "sự thật", rồi đo xem nội dung trong DB phủ được bao nhiêu phần.

PHẠM VI: cả 21 văn bản. Bản trước chỉ đo 6 Bộ luật, và đó chính là lý do nó
không thấy gì: đã đo lại, 6 Bộ luật chỉ mất 1.882 ký tự (0,13%) còn 15 văn bản
còn lại mất 111.239 (TT 09/2020: 64,4% tài liệu). Cổng soi đúng phần parser làm
tốt và bỏ qua đúng phần parser hỏng nặng.

BA PHÉP KIỂM, mỗi phép bắt một loại lỗi loại kia không thấy:

  A. ĐỘ PHỦ TOKEN — bắt MẤT CHỮ. Ngưỡng 0.98.
  B. RỖNG — `noi_dung` rỗng ở cấp trích dẫn được. Ngưỡng 0. Trước vòng sửa
     gốc, phép này vô nghĩa vì `noi_dung` rỗng ở 93,4% provision theo THIẾT KẾ;
     giờ toàn văn nằm ở `noi_dung` nên nó đo được thứ nó nói là đo.
  C. CẤU TRÚC — hai thứ độ phủ dùng `set()` về bản chất KHÔNG THẤY:
     C1. Dãy số Điều liên tục từng văn bản. Một Điều bị gộp vào Điều bên cạnh
         vẫn để lại đủ token nên độ phủ vẫn 100%; chỉ dãy số hở ra.
     C2. `duong_dan` duy nhất ở cấp trích dẫn được, TRÊN TOÀN CORPUS. Hai
         provision cùng neo ⇒ một claim sai được "kiểm chứng thành công".

Cổng CẤU TRÚC phía parser (bảo toàn ký tự, provision trong <table>) là việc của
`prov_parser.parse_anomalies()`, chạy trong `build_seed` — xem docs/gate-a-report.md.
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup
from sqlalchemy import text

from scripts.fetch_moj import DOC_IDS
from src.config import get_settings
from src.services.db import get_engine

CITABLE = ("dieu", "khoan", "diem")

# Số Điều đã kiểm tay của 6 Bộ luật — trục tra cứu, phải liên tục hoàn hảo.
SO_DIEU_BO_LUAT = {"95942": 689, "96115": 517, "96172": 510,
                   "96122": 426, "96117": 341, "139264": 220}


def _norm(s: str) -> str:
    """Gộp khoảng trắng + chuẩn hoá Unicode NFC.

    NFC áp ĐỐI XỨNG cho cả hai phía so sánh: tiếng Việt tồn tại ở cả dạng tổ hợp
    dấu (NFD: "ê" = e + U+0302) và dựng sẵn (NFC: U+00EA). Hai dạng khác nhau về
    codepoint nhưng cùng một chữ, nên nếu một phía là NFD và phía kia là NFC thì
    so sánh token sẽ báo LỆCH GIẢ trên gần như mọi từ có dấu. Đã đo: NFD một phía
    làm độ phủ sụp về 0,28–0,37.

    NFC là mức chuẩn hoá ĐỦ VÀ KHÔNG QUÁ TAY: nó chỉ hợp nhất các dãy codepoint
    tương đương chính tắc, KHÔNG bỏ dấu (unaccent), KHÔNG hạ chữ (casefold),
    KHÔNG gộp NFKC (vốn biến "①"→"1", "ﬁ"→"fi"). Đã đo bằng số: casefold nâng độ
    phủ BLDS +0,63pp bằng cách CHE ~20 token thiếu THẬT. Chuẩn hoá quá tay ở cổng
    này không làm cổng chặt hơn, nó làm cổng mù.
    """
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", s)).strip()


def _van_ban_goc(html: str) -> str:
    """Sự thật ĐỘC LẬP VỚI PARSER: bỏ hết tag, chỉ giữ text.

    Bỏ <table> vì bảng được lưu riêng (bẫy #4), không nằm trong provisions.noi_dung
    theo đường prov-*.

    `get_text(" ")` chèn khoảng trắng ở MỌI biên thẻ, kể cả thẻ inline, nên công
    thức `T<sub>Q</sub> = [T<sub>N</sub> …]` ở đây thành `T Q = [T N …]` còn phía
    parser là `TQ = [TN …]`. Đó là chênh lệch TÁCH TỪ, không phải mất chữ, và là
    toàn bộ phần dưới 100% còn lại của độ phủ. KHÔNG chỉnh hàm này cho khớp
    parser: cổng phải giữ được tính độc lập, kể cả khi cái giá là vài token dấu
    câu. Phép bảo toàn ký tự tuyệt đối là việc của parse_anomalies().
    """
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all("table"):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with(" ")
    return _norm(soup.get_text(" "))


def audit(n: int = 30) -> dict:
    raw = Path(get_settings().data_raw_dir) / "moj"
    per_doc: list[dict] = []
    chi_tiet: list[dict] = []
    rong_tong = 0
    day_so_hong = 0

    with get_engine().connect() as conn:
        for doc_id, (_, so_ky_hieu) in DOC_IDS.items():
            rows = conn.execute(text(
                "SELECT cap, so_hieu_cap, tieu_de, noi_dung, duong_dan"
                " FROM provisions WHERE document_id = :d"
            ), {"d": doc_id}).mappings().all()
            if not rows:
                chi_tiet.append({"doc_id": doc_id, "loi": "KHÔNG CÓ provision nào trong DB"})
                per_doc.append({"doc_id": doc_id, "so_ky_hieu": so_ky_hieu, "do_phu": 0.0,
                                "rong": 0, "provisions": 0, "token_goc": 0, "token_thieu": 0,
                                "dieu": 0, "day_so": "KHÔNG CÓ DỮ LIỆU"})
                day_so_hong += 1
                continue

            html = json.loads((raw / f"{doc_id}.json").read_text(encoding="utf-8"))
            goc_tokens = set(_van_ban_goc(html["documentContent"]["content"]).split())
            db_tokens = set(_norm(" ".join(
                f"{r['tieu_de']} {r['noi_dung']}" for r in rows)).split())

            do_phu = len(goc_tokens & db_tokens) / len(goc_tokens) if goc_tokens else 0.0
            thieu = sorted(goc_tokens - db_tokens)

            # B — RỖNG ở cấp trích dẫn được. Giờ phép đo này có nghĩa thật.
            rong = [r for r in rows
                    if r["cap"] in CITABLE and not (r["noi_dung"] or "").strip()]
            rong_tong += len(rong)
            for r in rong[:5]:
                chi_tiet.append({"doc_id": doc_id, "duong_dan": r["duong_dan"],
                                 "loi": "noi_dung RỖNG ở cấp trích dẫn được"})

            # C1 — dãy số Điều liên tục. Hậu tố chữ ("33a") đếm riêng khi tìm
            # trùng nhưng quy về số khi tìm lỗ, vì "33a" không phải một lỗ.
            dieu = [r["so_hieu_cap"] for r in rows if r["cap"] == "dieu"]
            nums = {int(re.sub(r"\D", "", x) or 0) for x in dieu}
            trung = sorted(k for k, v in Counter(dieu).items() if v > 1)
            lo = sorted(set(range(min(nums), max(nums) + 1)) - nums) if nums else []
            day_so = "liên tục" if not lo and not trung else f"lỗ={lo[:8]} trùng={trung[:4]}"
            if lo or trung:
                day_so_hong += 1
                chi_tiet.append({"doc_id": doc_id, "loi": f"dãy số Điều: {day_so}"})
            if doc_id in SO_DIEU_BO_LUAT and len(dieu) != SO_DIEU_BO_LUAT[doc_id]:
                day_so_hong += 1
                chi_tiet.append({"doc_id": doc_id,
                                 "loi": f"đếm được {len(dieu)} Điều, phải {SO_DIEU_BO_LUAT[doc_id]}"})

            if do_phu < 0.98:
                chi_tiet.append({"doc_id": doc_id, "loi": f"độ phủ {do_phu:.2%}",
                                 "token_mat_mau": thieu[:n]})

            per_doc.append({"doc_id": doc_id, "so_ky_hieu": so_ky_hieu,
                            "do_phu": round(do_phu, 4), "rong": len(rong),
                            "provisions": len(rows), "token_goc": len(goc_tokens),
                            "token_thieu": len(thieu), "dieu": len(dieu),
                            "day_so": day_so, "token_thieu_mau": thieu[:n]})

        # C2 — duong_dan duy nhất ở cấp trích dẫn được, TRÊN TOÀN CORPUS.
        neo_trung = conn.execute(text(
            "SELECT duong_dan, count(*) FROM provisions"
            f" WHERE cap IN {CITABLE} GROUP BY 1 HAVING count(*) > 1"
        )).all()
        for dd, c in neo_trung:
            chi_tiet.append({"loi": f"neo trích dẫn TRÙNG {c} lần: {dd}"})

        # Cấp container được phép trùng — NĐ 145/2020 thật sự có hai "Chương XI".
        container_trung = conn.execute(text(
            "SELECT duong_dan, count(*) FROM provisions"
            f" WHERE cap NOT IN {CITABLE} GROUP BY 1 HAVING count(*) > 1"
        )).all()

    do_phu_min = min((d["do_phu"] for d in per_doc), default=0.0)
    return {
        "van_ban_da_do": len(per_doc),
        "per_doc": per_doc,
        "do_phu_min": do_phu_min,
        "rong_tong": rong_tong,
        "day_so_hong": day_so_hong,
        "neo_trung": [list(x) for x in neo_trung],
        "container_trung_chap_nhan": [list(x) for x in container_trung],
        "pass": (rong_tong == 0 and do_phu_min >= 0.98
                 and day_so_hong == 0 and not neo_trung),
        "chi_tiet": chi_tiet,
    }


if __name__ == "__main__":
    r = audit()
    gon = {k: v for k, v in r.items() if k != "chi_tiet"}
    gon["per_doc"] = [{k: v for k, v in d.items() if k != "token_thieu_mau"}
                      for d in gon["per_doc"]]
    print(json.dumps(gon, ensure_ascii=False, indent=2))
    for c in r["chi_tiet"][:40]:
        print(" -", c)
    raise SystemExit(0 if r["pass"] else 1)
