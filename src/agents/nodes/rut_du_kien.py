"""Node `rut_du_kien` — đọc tài liệu người dùng thành dữ kiện có neo nguồn
(spec 2026-09-15 §FR-006, §FR-007, §FR-017).

Node này là chỗ duy nhất trong tính năng có gọi mô hình. Mọi thứ trước nó
(`doc_tai_lieu`) và sau nó (`neo_du_kien`) là phép tất định 0 token, nên biên
của phần "mô hình có thể sai" nằm gọn trong một file.

Hai ràng buộc định hình lược đồ:

**Bộ trường lấy từ `gom_du_kien.truong_cua`, không định nghĩa lại.** Dữ kiện rút
ra tồn tại để điền vào biểu mẫu soạn thảo; một bộ trường thứ hai sẽ lệch khỏi
`rules.yaml` và dữ kiện rút được sẽ không khớp chỗ nào.

**`trich` là trường bắt buộc của mọi dữ kiện.** Không có đường nào cho mô hình
trả về một giá trị không kèm bằng chứng. Giá trị nào có `trich` không tra ngược
được sẽ bị `neo_du_kien.loc_co_neo` loại ngay trong node này, trước khi ra tới
người gọi.
"""

import json
import logging
from pathlib import Path

from src.agents.nodes.gom_du_kien import truong_cua
from src.agents.graph_soan_thao import load_checklist_cached
from src.services.doc_tai_lieu import TaiLieuDaDoc
from src.services.neo_du_kien import LyDoNeo, loc_co_neo
from src.services.prompts import messages

logger = logging.getLogger(__name__)
PROMPT_PATH = Path("prompts/rut_du_kien.v1.md")


def schema_rut(loai: str) -> dict:
    """Lược đồ structured output: mỗi trường là một cặp `{gia_tri, trich}`.

    Dựng LÚC GỌI từ `rules.yaml`, cùng khuôn `gom_du_kien.schema_du_kien`: thêm
    một trường vào YAML là tự động rút được trường đó, không phải sửa code.
    """
    props: dict = {}
    for t in truong_cua(loai):
        gia_tri = (
            {"type": "string", "enum": ["", *t["lua_chon"]]}
            if t.get("lua_chon")
            else {"type": "string"}
        )
        props[t["key"]] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["gia_tri", "trich"],
            "properties": {"gia_tri": gia_tri, "trich": {"type": "string"}},
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(props),
        "properties": props,
    }


def _dong_tai_lieu(tai_lieu: TaiLieuDaDoc) -> str:
    return "\n".join(f"[{d.chi_so}] (trang {d.trang}) {d.noi_dung}" for d in tai_lieu.don_vi)


def _dong_truong(loai: str) -> str:
    return "\n".join(
        f"- `{t['key']}` ({t['nhan']}"
        + (f", chọn một trong: {', '.join(t['lua_chon'])}" if t.get("lua_chon") else "")
        + ")"
        for t in truong_cua(loai)
    )


def rut_du_kien(loai: str, tai_lieu: TaiLieuDaDoc, llm, model: str) -> dict:
    """Trả `{"du_kien": [...], "bo": [...], "traces": {...}}`.

    `du_kien` chỉ chứa những gì có neo hợp lệ. `bo` không bao giờ đi tiếp ra
    giao diện; nó tồn tại để `traces` đếm được tỉ lệ loại tách theo từng lý do,
    y hệt cách tầng 1 tách ba chế độ hỏng của quote.
    """
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        ten=load_checklist_cached(loai).ten,
        tai_lieu=_dong_tai_lieu(tai_lieu),
        truong=_dong_truong(loai),
    )

    nguon = "llm"
    usage = None
    ra: dict = {}
    try:
        raw, usage = llm.chat(model, messages(prompt), json_schema=schema_rut(loai))
        ra = json.loads(raw)
        if not isinstance(ra, dict):
            raise TypeError(f"phản hồi phải là object, được {type(ra).__name__}")
    except Exception as e:
        # Lỗi hạ tầng KHÔNG được hạ cấp thành "tài liệu không có gì": trả rỗng
        # và nói rõ là lỗi, để người gọi cho thử lại thay vì báo sai cho người
        # dùng rằng tài liệu của họ trống.
        logger.warning("rut_du_kien: lỗi (%s: %s)", type(e).__name__, e, exc_info=True)
        ra, usage, nguon = {}, None, "loi"

    tho: list[dict] = []
    for t in truong_cua(loai):
        o = ra.get(t["key"]) or {}
        if not isinstance(o, dict):
            continue
        gia_tri = str(o.get("gia_tri") or "").strip()
        if not gia_tri:
            continue
        tho.append(
            {
                "key": t["key"],
                "nhan": t["nhan"],
                "gia_tri": gia_tri,
                "trich": str(o.get("trich") or "").strip(),
                "nguon": "tai_lieu",
            }
        )

    giu, bo = loc_co_neo(tho, tai_lieu.don_vi)
    dem = {f"rut_du_kien_bo_{ly.value}": 0 for ly in LyDoNeo if ly is not LyDoNeo.ok}
    for f in bo:
        dem[f"rut_du_kien_bo_{f['neo'].ly_do.value}"] += 1

    return {
        "du_kien": giu,
        "bo": bo,
        "traces": {
            "rut_du_kien_nguon": nguon,
            "rut_du_kien_so_giu": len(giu),
            "rut_du_kien_so_bo": len(bo),
            **dem,
            "rut_du_kien_token_in": usage.token_in if usage else 0,
            "rut_du_kien_token_out": usage.token_out if usage else 0,
            "rut_du_kien_cost_usd": usage.cost_usd if usage else 0.0,
        },
    }
