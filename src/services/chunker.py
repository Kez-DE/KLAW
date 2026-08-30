"""provisions → chunks.

Chunk = một Điều (gồm cả Khoản/Điểm con), KHÔNG cắt cứng theo token.
Điều dài hơn max_tokens thì cắt theo Khoản, nhưng mỗi chunk vẫn mang context
header = đường dẫn + tiêu đề/câu dẫn của Điều cha — đó là contextual retrieval
nhẹ, giải một phần pain point #4/#5.

Khi cắt theo Khoản, chunk neo vào provision_id của KHOẢN (không của Điều) để
citation trỏ đúng cấp mà người dùng cần kiểm.

Chỉ đọc `noi_dung`: đó là toàn văn (nhãn + thân); `tieu_de` chỉ là nhãn ngắn và
đọc thêm nó sẽ trùng lặp hoặc lệch với nội dung thật. Input được lọc qua
`CITABLE` (Điều/Khoản/Điểm — cùng bất biến DB dùng ở `provisions_cap_check`)
trước khi dựng cây, nên `mo_dau`/`phu_luc` (chữ không thuộc điều luật nào)
không thể lọt vào một chunk — kể cả khi dữ liệu lỗi gán nhầm parent_id.
"""

import re
from dataclasses import dataclass

from sqlalchemy import Engine, text

from src.services.prov_parser import CITABLE


@dataclass(frozen=True)
class ChunkRow:
    provision_id: int
    noi_dung_embed: str
    token_count: int


def dem_token(s: str) -> int:
    """Xấp xỉ: số từ × 1.3. Không dùng tokenizer thật vì embedding qua API.

    ponytail: đủ chính xác để quyết định cắt hay không. Thay bằng tokenizer thật
    nếu đo được sai lệch gây cắt sai.
    """
    return int(len(re.findall(r"\S+", s)) * 1.3)


def _text_of(p: dict) -> str:
    return (p.get("noi_dung") or "").strip()


def build_chunks(provisions: list[dict], max_tokens: int) -> list[ChunkRow]:
    citable = [p for p in provisions if p.get("cap") in CITABLE]
    con: dict[int, list[dict]] = {}
    for p in citable:
        if p.get("parent_id") is not None:
            con.setdefault(p["parent_id"], []).append(p)

    def gom(p: dict) -> str:
        """Text của p + toàn bộ con, theo thứ tự."""
        acc = [_text_of(p)]
        for c in con.get(p["id"], []):
            acc.append(gom(c))
        return " ".join(x for x in acc if x).strip()

    out: list[ChunkRow] = []
    for p in citable:
        if p["cap"] != "dieu":
            continue
        full = gom(p)
        if not full:
            continue
        header = p["duong_dan"]
        body = f"{header}\n{full}"

        if dem_token(body) <= max_tokens:
            out.append(ChunkRow(p["id"], body, dem_token(body)))
            continue

        # Quá dài → cắt theo Khoản. Header mỗi mảnh = duong_dan của chính Khoản
        # ("… > Điều N > Khoản M") CỘNG `_text_of(p)`, tức tiêu đề Điều và câu
        # dẫn trước Khoản 1. `duong_dan` chỉ mang SỐ HIỆU, không mang chữ: thiếu
        # dòng này thì chủ đề duy nhất phân biệt Điều 42 ("đưa người lao động
        # Việt Nam đi làm việc ở nước ngoài") với hàng trăm điều xử phạt khác
        # KHÔNG tồn tại ở bất kỳ đâu trong index; câu dẫn — thường mang điều
        # kiện áp dụng — cũng mất. Đo trên corpus: 190 chunk, 6/49 gold anchor.
        # CHỈ tiêu đề + câu dẫn, KHÔNG nhồi toàn văn Điều cha: nhồi vào là phình
        # chunk và trùng lặp, đúng thứ mà việc cắt theo Khoản sinh ra để tránh.
        khoans = [c for c in con.get(p["id"], []) if c["cap"] == "khoan"]
        if not khoans:
            out.append(ChunkRow(p["id"], body, dem_token(body)))
            continue
        dan = _text_of(p)
        for k in khoans:
            ktext = gom(k)
            if not ktext:
                continue
            kbody = "\n".join(x for x in (k["duong_dan"], dan, ktext) if x)
            out.append(ChunkRow(k["id"], kbody, dem_token(kbody)))

    return out


def load_provisions(engine: Engine) -> list[dict]:
    """Đọc provision từ DB thành dict cho build_chunks()."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, document_id, parent_id, cap, so_hieu_cap, noi_dung, duong_dan"
            " FROM provisions ORDER BY document_id, thu_tu"
        )).mappings().all()
        return [dict(r) for r in rows]
