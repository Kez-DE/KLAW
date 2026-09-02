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
    # TẦNG NÔNG trước, và nó KHÔNG đi qua `citable`: một văn bản tầng nông là
    # văn bản ta biết là có mà không có toàn văn máy đọc được, nên thứ duy nhất
    # đánh chỉ mục được là TÊN nó, nằm ở hàng `mo_dau`. Không có hàng này thì
    # 79 văn bản metadata vô hình với truy hồi, và nhánh `partial_coverage` —
    # thiết kế đúng cho đúng trường hợp này — không bao giờ kích được.
    #
    # CHỈ tầng nông. `mo_dau` của 47 văn bản tầng sâu là letterhead lặp lại
    # ("CHÍNH PHỦ / CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM / Căn cứ…", trung bình
    # 467 ký tự); đánh chỉ mục chúng là thêm 47 chunk gần trùng nhau, đúng loại
    # nhiễu tệ nhất khi `ts_rank` không có IDF.
    #
    # Lời hứa "nêu văn bản, KHÔNG diễn giải" không cần code nào giữ: schema đã
    # giữ. `ux_provisions_neo_trich_dan` và `provisions_noi_dung_citable_check`
    # chỉ phủ `dieu`/`khoan`/`diem`, nên một hàng `mo_dau` không bao giờ trở
    # thành một trích dẫn nguyên văn được.
    out: list[ChunkRow] = []
    for p in provisions:
        if p.get("cap") != "mo_dau" or p.get("depth") != "shallow":
            continue
        ten = _text_of(p)
        if not ten:
            continue
        out.append(ChunkRow(p["id"], ten, dem_token(ten)))

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
            # `depth` join từ `documents`: `build_chunks` cần biết văn bản
            # thuộc tầng nào để quyết định có đánh chỉ mục `mo_dau` hay không.
            "SELECT p.id, p.document_id, p.parent_id, p.cap, p.so_hieu_cap,"
            " p.noi_dung, p.duong_dan, d.depth"
            " FROM provisions p JOIN documents d ON d.id = p.document_id"
            " ORDER BY p.document_id, p.thu_tu"
        )).mappings().all()
        return [dict(r) for r in rows]
