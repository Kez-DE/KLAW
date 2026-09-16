"""Bản thảo đã lưu và phiên bản (spec 2026-09-09 §8.3). Mọi hàm lọc theo `user_sub`."""

import dataclasses
import json
import logging
import time
import uuid

from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.agents.graph_soan_thao import graph_soan_thao_cached, load_checklist_cached
from src.config import get_settings
from src.services.db import get_engine
from src.services.traces import _ghi_traces

logger = logging.getLogger(__name__)

TRAN_SUA = 10
LOI_KHONG_THAY = "Không tìm thấy bản thảo này."
LOI_HET_LAN_SUA = f"Bản thảo này đã sửa {TRAN_SUA} lần. Mở bản mới để tiếp tục."
# Giá trị của cột `loai` cho bản thảo KHÔNG theo checklist nào (S6). Khai ở đây
# chứ không ở node dựng nó: cột này là của bảng, và `dung_lai` phải nhận ra nó
# mà không được nhập ngược một module `agents` (vòng import).
LOAI_TONG_QUAT = "tong_quat"
LOI_SUA_TONG_QUAT = "Bản thảo tổng quát sửa bằng cách nói với trợ lý trong cuộc trò chuyện, không qua biểu mẫu dữ kiện."

_COT = (
    "id::text AS id, hoi_thoai_id::text AS hoi_thoai_id, loai, facts, document, clauses, audit,"
    " phien_ban, phien_ban_truoc, so_lan_sua, tao_luc, cap_nhat_luc"
)
_SQL_TAO = text(
    "INSERT INTO ban_thao (user_sub, hoi_thoai_id, loai, facts, document, clauses, audit)"
    " VALUES (CAST(:sub AS uuid), CAST(:pid AS uuid), :loai, CAST(:facts AS jsonb), :document,"
    " CAST(:clauses AS jsonb), CAST(:audit AS jsonb)) RETURNING " + _COT
)
_SQL_LAY = text(
    f"SELECT {_COT} FROM ban_thao WHERE id = CAST(:id AS uuid) AND user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL"
)
_SQL_SUA = text(
    "UPDATE ban_thao SET facts = CAST(:facts AS jsonb), document = :document, clauses = CAST(:clauses AS jsonb),"
    " audit = CAST(:audit AS jsonb), phien_ban = :phien_ban, phien_ban_truoc = CAST(:truoc AS jsonb),"
    " so_lan_sua = so_lan_sua + :tang, cap_nhat_luc = now()"
    " WHERE id = CAST(:id AS uuid) AND user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL RETURNING " + _COT
)
_SQL_DS = text(
    f"SELECT {_COT} FROM ban_thao WHERE user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL"
    " ORDER BY cap_nhat_luc DESC LIMIT :limit OFFSET :offset"
)
_SQL_DEM = text("SELECT count(*)::int FROM ban_thao WHERE user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL")
_SQL_MOI_NHAT = text(
    f"SELECT {_COT} FROM ban_thao WHERE user_sub = CAST(:sub AS uuid)"
    " AND hoi_thoai_id = CAST(:pid AS uuid) AND loai = :loai AND xoa_luc IS NULL"
    " ORDER BY cap_nhat_luc DESC LIMIT 1"
)
_SQL_XOA = text(
    "UPDATE ban_thao SET xoa_luc = now() WHERE id = CAST(:id AS uuid) AND user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL"
)


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False)


def _duong_dan_index(db_provisions: dict[int, dict]) -> dict[str, dict]:
    """duong_dan -> dòng provisions. Bản sao của `routes._duong_dan_index`, ăn thẳng
    `st["db_provisions"]` (chính tập `retrieve_requirements` tra về) thay vì gọi lại
    `requirements(loai)` — hai nguồn là MỘT nhưng `tu_state_soan_thao` chỉ nhận `st`."""
    return {row["duong_dan"]: row for row in db_provisions.values()}


def _finding_out(f, duong_dan_index: dict[str, dict]) -> dict:
    """Bản sao của `routes._finding_out` — giữ NGUYÊN tên khoá và cách tra
    doc_id/khop_tai_id, vì đây là hình dạng `SoanThaoResponse` đã pin bằng test."""
    duong_dan = (f.can_cu or {}).get("duong_dan")
    khop = duong_dan_index.get(duong_dan) if duong_dan else None
    return {
        "loai": f.loai,
        "muc_do": f.muc_do,
        "thong_diep": f.mo_ta,
        "dieu_khoan_lien_quan": f.dieu_khoan_lien_quan,
        "can_cu": duong_dan,
        "rule_id": f.rule_id,
        "doc_id": khop["document_id"] if khop else None,
        "khop_tai_id": khop["id"] if khop else None,
        "khong_kiem_duoc": getattr(f, "khong_kiem_duoc", False),
    }


def _render_markdown(loai: str, clauses: list, tieu_de: str | None = None) -> str:
    """Bản sao của `routes._render_markdown` — cùng khuôn Markdown thuần.

    Nhánh `tong_quat` (S6) dựng THẲNG từ `clauses` (dict, không phải
    `DraftClause`) và từ `tieu_de` của chính văn bản: một bản thảo tổng quát
    theo định nghĩa KHÔNG có checklist nào để tra, nên gọi `load_checklist_cached`
    ở đó sẽ nổ — và cái phải đổi là hàm này, không phải một hàm render thứ hai
    đi song song rồi trôi lệch khuôn Markdown.
    """
    if loai == "tong_quat":
        phan = [f"# {tieu_de or 'Văn bản'}", ""]
        for i, c in enumerate(clauses, 1):
            phan.append(f"## {i}. {c['ten']}\n\n{c['noi_dung']}\n")
        return "\n".join(phan)
    cl = load_checklist_cached(loai)
    phan = [f"# {cl.tieu_de}", ""]
    for i, c in enumerate(clauses, 1):
        phan.append(f"## {cl.don_vi_muc} {i}. {c.ten}\n\n{c.noi_dung}\n")
    return "\n".join(phan)


def kiem_tran_sua(cu: dict) -> None:
    """Trần sửa của MỘT bản thảo, phát biểu ở đúng một chỗ.

    `dung_lai` (bản thảo checklist) và `dung_ban_thao_tong_quat` (S6) đều gọi
    hàm này TRƯỚC khi làm bất cứ việc tốn kém nào, nên ngưỡng và lời từ chối chỉ
    có một bản. Đo trên cột ĐƠN ĐIỆU `so_lan_sua` chứ không trên độ dài
    `phien_ban_truoc` — xem docstring `dung_lai`.
    """
    if int(cu.get("so_lan_sua") or 0) >= TRAN_SUA:
        raise ValueError(LOI_HET_LAN_SUA)


def moi_nhat_cua_hoi_thoai(sub: str, hoi_thoai_id: str, loai: str) -> dict | None:
    """Bản thảo `loai` MỚI NHẤT của chính hội thoại này, hoặc `None`.

    Một lệnh sửa bằng lời ("đổi mục 2 thành…") không mang id nào, nên "bản thảo
    nào" phải suy ra được: trong một cuộc trò chuyện, đó là bản vừa dựng. Lọc
    theo `user_sub` ở tầng dữ liệu như mọi hàm khác trong file này.
    """
    with get_engine().connect() as c:
        r = c.execute(_SQL_MOI_NHAT, {"sub": sub, "pid": hoi_thoai_id, "loai": loai}).mappings().one_or_none()
    return dict(r) if r is not None else None


def tu_state_soan_thao(st: dict) -> dict:
    """State sau `graph_soan_thao.ainvoke` → JSON thuần cùng nội dung `SoanThaoResponse`
    (trừ `trace_id`). Được chuyển từ thân endpoint `/soan-thao` sang đây để node
    `dung_ban_thao` dùng chung.

    KHÔNG dùng `.model_dump()`/`__dict__` phẳng như một bản chuyển đổi chung: `document`
    không phải một khoá có sẵn trong `SoanThaoState` (route cũ TỰ RENDER markdown từ
    `clauses`), và `audit_report` thô (`AuditReport` dataclass) thiếu `doc_id`/`khop_tai_id`
    — hai trường route cũ tra thêm từ `db_provisions` qua `_duong_dan_index`/`_finding_out`.
    Dùng `st["loai"]` (mã enum, KHÔNG đổi trong suốt graph) và `st["db_provisions"]`
    (đúng tập `requirements(loai)[2]` mà route cũ gọi lại) để tái tạo đúng y hệt.
    """
    clauses = st.get("clauses") or []
    idx = _duong_dan_index(st.get("db_provisions") or {})
    r = st["audit_report"]
    audit_report = {
        "dat": r.dat,
        "completeness": r.completeness,
        "so_dieu_khoan": r.so_dieu_khoan,
        "self_audit": r.self_audit,
        "findings": [_finding_out(f, idx) for f in r.findings],
    }
    return {
        "document": _render_markdown(st["loai"], clauses),
        "clauses": [dataclasses.asdict(c) for c in clauses],
        "audit_report": audit_report,
    }


def tao(sub: str, hoi_thoai_id: str | None, loai: str, facts: dict, ket: dict) -> dict:
    with get_engine().begin() as c:
        r = (
            c.execute(
                _SQL_TAO,
                {
                    "sub": sub,
                    "pid": hoi_thoai_id,
                    "loai": loai,
                    "facts": _j(facts),
                    "document": ket["document"],
                    "clauses": _j(ket["clauses"]),
                    "audit": _j(ket["audit_report"]),
                },
            )
            .mappings()
            .one()
        )
    return dict(r)


def chi_tiet(sub: str, id: str) -> dict | None:
    with get_engine().connect() as c:
        r = c.execute(_SQL_LAY, {"sub": sub, "id": id}).mappings().one_or_none()
    return dict(r) if r is not None else None


def _snap(row: dict) -> dict:
    """Chụp MỌI thứ cần để khôi phục lại đúng một phiên bản — `document`/`facts` một
    mình là không đủ: `clauses`/`audit` bị thiếu từng làm `lui` trả về một bản ghi
    lẫn (văn bản của phiên bản cũ với clauses/audit của phiên bản đang bị rời đi)."""
    return {
        "phien_ban": row["phien_ban"],
        "document": row["document"],
        "facts": row["facts"],
        "clauses": row["clauses"],
        "audit": row["audit"],
    }


def sua(sub: str, id: str, facts: dict, ket: dict) -> dict | None:
    cu = chi_tiet(sub, id)
    if cu is None:
        return None
    truoc = [*(cu["phien_ban_truoc"] or []), _snap(cu)][-TRAN_SUA:]
    with get_engine().begin() as c:
        r = (
            c.execute(
                _SQL_SUA,
                {
                    "sub": sub,
                    "id": id,
                    "facts": _j(facts),
                    "document": ket["document"],
                    "clauses": _j(ket["clauses"]),
                    "audit": _j(ket["audit_report"]),
                    "phien_ban": cu["phien_ban"] + 1,
                    "truoc": _j(truoc),
                    # Bộ đếm trần sửa — chỉ ĐI LÊN, và chỉ ở đây (xem `lui`).
                    "tang": 1,
                },
            )
            .mappings()
            .one()
        )
    return dict(r)


async def dung_lai(sub: str, id: str, facts: dict, hoi_thoai_id: str | None = None) -> dict | None:
    """Sửa bản thảo từ facts mới — MỘT đường dùng chung cho drawer xếp chồng
    (`POST /ban-thao/{id}/dung`, Task 25) và cho lệnh bằng lời trong hội thoại
    (`graph_tra_cuu.n_dung_ban_thao`, nhánh `la_sua`): một trần sửa, một cách
    chạy graph, một cách ghi trace — không phải hai bản sao trôi lệch nhau.

    `hoi_thoai_id` giữ để khớp chữ ký với nơi gọi từ node (nó luôn biết phiên
    hội thoại đang mở); hàm CHƯA dùng tới nó — `_ghi_traces` không có cột đó,
    và endpoint gọi hàm này không có hội thoại nào để truyền.

    Trần sửa đo bằng cột ĐƠN ĐIỆU `so_lan_sua` (migration 025), KHÔNG bằng độ
    dài `phien_ban_truoc`: mảng đó là ngăn xếp hoàn tác và `lui()` BỚT nó đi,
    nên đo trên nó thì xen kẽ `lui` (miễn phí, 0 token) với `dung` (một lượt LLM
    trả phí) đặt lại trần và mở một vòng lặp tiêu tiền không chặn được. Cột này
    chỉ do `sua()` tăng, `lui()` không đụng tới — nên "bản thảo NÀY đã sửa đủ
    `TRAN_SUA` lần" là một sự thật không lùi lại được, bất kể qua bao nhiêu phiên
    hội thoại hay bao nhiêu lần hoàn tác.
    """
    cu = await run_in_threadpool(chi_tiet, sub, id)
    if cu is None:
        return None
    if cu["loai"] == LOAI_TONG_QUAT:
        # Bản thảo tổng quát không có checklist, nên `graph_soan_thao` dưới đây
        # sẽ nổ ở `load_checklist_cached`. Chặn tại CHỖ DÙNG CHUNG này, không ở
        # riêng endpoint: cả drawer sửa mục lẫn lệnh sửa bằng lời của đường
        # checklist đi qua đây, và cả hai phải nhận cùng một lời từ chối.
        raise ValueError(LOI_SUA_TONG_QUAT)
    kiem_tran_sua(cu)
    bat_dau = time.monotonic()
    st = await graph_soan_thao_cached().ainvoke(
        {"loai": cu["loai"], "loai_van_ban": cu["loai"], "facts": facts, "nganh": "thuong_mai"}
    )
    bt = await run_in_threadpool(sua, sub, id, facts, tu_state_soan_thao(st))
    if bt is None:
        # Bản thảo bị xoá giữa lúc dựng lại (đua với một lượt xoá khác) — fail
        # closed, KHÔNG spread `None`: cùng hợp đồng 404 với mọi hàm khác ở đây.
        return None
    try:
        await run_in_threadpool(
            _ghi_traces,
            str(uuid.uuid4()),
            "/api/v1/soan-thao/sua",
            cu["loai"],
            get_settings().eval_config_name,
            {"result_type": "ban_thao", "traces": st.get("traces") or {}},
            int((time.monotonic() - bat_dau) * 1000),
            user_sub=sub,
        )
    except Exception:
        logger.exception("ban_thao.dung_lai: không ghi được traces")
    return {**bt, "ten": load_checklist_cached(cu["loai"]).ten, "doi_so_voi_truoc": doi_so_voi(cu, bt)}


def lui(sub: str, id: str) -> dict | None:
    """Lùi MỘT BƯỚC, không phải bật qua bật lại: bỏ hẳn bản đang đứng (không đẩy
    nó vào đâu cả) và khôi phục NGUYÊN VẸN mục gần nhất trong lịch sử — nên KHÔNG
    có đường tiến trở lại bản vừa bỏ. Gọi liên tiếp đi dần về bản CŨ NHẤT còn giữ
    (bị chặn bởi `TRAN_SUA`); tới đó rồi thì từ chối, trả về y nguyên bản hiện tại
    (`phien_ban_truoc` rỗng nghĩa là không còn gì để lùi).

    Bỏ hẳn, không giữ lại, là điều CỐ Ý: giữ lại bản bị rời đi từng để nó tồn tại
    song song với một bản MỚI cùng đánh số (sửa tiếp sau khi lùi đặt `phien_ban =
    gan["phien_ban"] + 1`, đúng số nhánh cũ đang giữ) — hai nội dung khác nhau
    cùng mang một số phiên bản. Không giữ nhánh bỏ đi thì không còn gì để va số.
    """
    cu = chi_tiet(sub, id)
    if cu is None or not cu["phien_ban_truoc"]:
        return cu
    *con, gan = cu["phien_ban_truoc"]
    with get_engine().begin() as c:
        r = (
            c.execute(
                _SQL_SUA,
                {
                    "sub": sub,
                    "id": id,
                    "facts": _j(gan["facts"]),
                    "document": gan["document"],
                    "clauses": _j(gan["clauses"]),
                    "audit": _j(gan["audit"]),
                    "phien_ban": gan["phien_ban"],
                    "truoc": _j(con),
                    # `tang = 0`: lùi KHÔNG trả lại một lần sửa. Trần đo bằng cột đơn điệu
                    # `so_lan_sua` chính vì mảng `phien_ban_truoc` bị hàm này bớt đi.
                    "tang": 0,
                },
            )
            .mappings()
            .one()
        )
    return dict(r)


def danh_sach(sub: str, limit: int, offset: int) -> tuple[list[dict], int]:
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_DEM, {"sub": sub}).scalar_one())
        items = [dict(r) for r in c.execute(_SQL_DS, {"sub": sub, "limit": limit, "offset": offset}).mappings().all()]
    return items, tong


def xoa_mem(sub: str, id: str) -> bool:
    with get_engine().begin() as c:
        return c.execute(_SQL_XOA, {"sub": sub, "id": id}).rowcount > 0


def doi_so_voi(truoc: dict, sau: dict) -> list[str]:
    a, b = truoc.get("facts") or {}, sau.get("facts") or {}
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
