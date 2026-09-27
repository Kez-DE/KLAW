"""Bản thảo đã lưu và phiên bản (spec 2026-09-09 §8.3). Mọi hàm lọc theo `user_sub`."""

import dataclasses
import json
import logging
import re
import time
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any

from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.agents.graph_soan_thao import graph_soan_thao_cached, load_checklist_cached
from src.config import get_settings
from src.services.db import get_engine
from src.services.dien_khuon import ap_dung_docx, danh_dau_docx
from src.services.dien_khuon_pdf import ap_dung_pdf
from src.services.doc_tai_lieu import KhongDocDuoc, nhan_sach
from src.services.tai_lieu import _cho_trong_tu_hang, _dia_chi_tu_hang, _so_tu_nhien
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
    " phien_ban, phien_ban_ke_tiep, phien_ban_truoc, so_lan_sua, tao_luc, cap_nhat_luc,"
    " viec_id::text AS viec_id, phep_sua"
)
# Phase 4 (D11, R5) — danh sách KHÔNG kéo `phien_ban_truoc`: cột này nặng tới
# ~4.3 kB/snapshot (`_snap`), và `danh_sach`/`BanThaoTomTatOut` không hề dùng
# tới nó — chỉ `chi_tiet`/`sua`/`lui` (nơi cần đọc lịch sử) mới cần `_COT` đầy
# đủ. Vẫn giữ `phien_ban_ke_tiep`: không nặng (một số nguyên), và không phải
# thứ R5 nhắm tới.
_COT_DS = (
    "id::text AS id, hoi_thoai_id::text AS hoi_thoai_id, loai, facts, document, clauses, audit,"
    " phien_ban, phien_ban_ke_tiep, so_lan_sua, tao_luc, cap_nhat_luc"
)
# Migration 037 — khuôn gốc của bản thảo, chỉ khi việc đọc ấy CÒN và là của
# CHÍNH chủ bản thảo: một `viec_id` lạ (tài khoản khác, đã xoá, `None`) ghi ra
# NULL — bản thảo HTML — thay vì một khoá ngoại nổ hay một khuôn gốc mượn. `lui`
# khôi phục `viec_id` từ snapshot qua CÙNG biểu thức, nên không bao giờ ghi lại
# một khoá ngoại đã bị `ON DELETE SET NULL` cắt.
_VIEC_CUA_CHU = (
    "(SELECT v.id FROM viec_doc_tai_lieu v WHERE v.id = CAST(:viec_id AS uuid) AND v.user_sub = CAST(:sub AS uuid))"
)
_SQL_TAO = text(
    "INSERT INTO ban_thao (user_sub, hoi_thoai_id, loai, facts, document, clauses, audit, viec_id, phep_sua)"
    " VALUES (CAST(:sub AS uuid), CAST(:pid AS uuid), :loai, CAST(:facts AS jsonb), :document,"
    f" CAST(:clauses AS jsonb), CAST(:audit AS jsonb), {_VIEC_CUA_CHU}, CAST(:phep_sua AS jsonb)) RETURNING " + _COT
)
# Phase 6 (D10, R2) — một bản thảo MỒ CÔI: `hoi_thoai_id` của nó trỏ tới một
# hội thoại đã xoá mềm. `NOT EXISTS` (không phải JOIN) để không thêm một hàng
# nào vào kết quả — `_COT` đã kéo `phien_ban_truoc` trên mọi dòng danh sách,
# một JOIN chỉ cộng thêm chi phí mà không cộng thêm gì đúng, vì `hoi_thoai.id`
# là khoá chính (chưa từng nhân dòng). `hoi_thoai_id IS NULL` (bản thảo CHƯA
# TỪNG có hội thoại, `tao()` nhận `pid=None`) không khớp hàng `h` nào ⇒
# NOT EXISTS luôn đúng ⇒ không bao giờ bị coi là mồ côi — đúng yêu cầu R2.
_KHONG_MO_COI = "NOT EXISTS (SELECT 1 FROM hoi_thoai h WHERE h.id = ban_thao.hoi_thoai_id AND h.xoa_luc IS NOT NULL)"
_SQL_LAY = text(
    f"SELECT {_COT} FROM ban_thao WHERE id = CAST(:id AS uuid) AND user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL"
    f" AND {_KHONG_MO_COI}"
)
# Fix round 1 (Critical, R1) — `sua`/`lui` phải ĐỌC hàng này TRONG CÙNG một
# transaction với cú GHI, và khoá nó (`FOR UPDATE`): `get_engine()`
# (`src/services/db.py`) không đặt isolation level nào khác READ COMMITTED
# mặc định, nên hai request gần như đồng thời trên CÙNG một bản thảo (double
# submit, hai tab, một retry đua với bản gốc) — mỗi request một connection từ
# pool — nếu đọc bằng `chi_tiet()` (không khoá) trên connection RIÊNG rồi mới
# mở transaction để ghi, cả hai sẽ đọc CÙNG `phien_ban_ke_tiep`, cùng tính một
# số phiên bản mới, và bên ghi SAU đè sạch bên ghi TRƯỚC — đúng va chạm số
# phiên bản mà R1 sinh ra để chặn, chỉ đi vòng qua một cửa khác (đường đua,
# không phải công thức backfill). `FOR UPDATE` bắt giao dịch thứ hai CHỜ tới
# khi giao dịch thứ nhất commit rồi mới đọc — nên nó luôn thấy
# `phien_ban_ke_tiep` đã tăng và snapshot của giao dịch trước đã được đẩy vào
# lịch sử (`_snap`), không có gì mất tích không dấu vết.
_SQL_LAY_KHOA = text(
    f"SELECT {_COT} FROM ban_thao WHERE id = CAST(:id AS uuid) AND user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL"
    f" AND {_KHONG_MO_COI} FOR UPDATE"
)
_SQL_SUA = text(
    "UPDATE ban_thao SET facts = CAST(:facts AS jsonb), document = :document, clauses = CAST(:clauses AS jsonb),"
    " audit = CAST(:audit AS jsonb), phien_ban = :phien_ban, phien_ban_ke_tiep = :phien_ban_ke_tiep,"
    " phien_ban_truoc = CAST(:truoc AS jsonb),"
    f" viec_id = {_VIEC_CUA_CHU}, phep_sua = CAST(:phep_sua AS jsonb),"
    " so_lan_sua = so_lan_sua + :tang, cap_nhat_luc = now()"
    " WHERE id = CAST(:id AS uuid) AND user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL RETURNING " + _COT
)
_SQL_DS = text(
    f"SELECT {_COT_DS} FROM ban_thao WHERE user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL AND {_KHONG_MO_COI}"
    " ORDER BY cap_nhat_luc DESC LIMIT :limit OFFSET :offset"
)
_SQL_DEM = text(
    f"SELECT count(*)::int FROM ban_thao WHERE user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL AND {_KHONG_MO_COI}"
)
# Tích hợp wave D — lọc theo `viec_id` của phiên bản ĐANG sống (`IS NOT DISTINCT
# FROM`: `NULL` là bản thảo HTML), vì một hội thoại có thể xen kẽ bản thảo trên
# khuôn gốc và bản thảo HTML; bản mới nhất của hội thoại không nói lượt sửa này
# nhắm bản nào.
_SQL_MOI_NHAT = text(
    f"SELECT {_COT} FROM ban_thao WHERE user_sub = CAST(:sub AS uuid)"
    " AND hoi_thoai_id = CAST(:pid AS uuid) AND loai = :loai AND xoa_luc IS NULL"
    " AND viec_id IS NOT DISTINCT FROM CAST(:viec_id AS uuid)"
    " ORDER BY cap_nhat_luc DESC LIMIT 1"
)
# Phase 3 (PostgreSQL review) — bản NHẸ của truy vấn trên, CHỈ hai cột
# `routes._chuan_bi_phien`/`hieu_tai_lieu._khoi_ban_thao_dang_co` thật sự đọc.
# `_chuan_bi_phien` chạy MỖI lượt hỏi có danh tính (không chỉ lượt soạn), nên
# kéo cả `_COT` (gồm `phien_ban_truoc` — ~4,3 kB/snapshot, tới 10 snapshot) ở
# đó là tái diễn đúng chi phí một phase trước đã cố tình bỏ khỏi `danh_sach`
# (xem chú thích `_COT_DS`), trên một đường còn NÓNG hơn. `dung_ban_thao_tong_quat`
# (chỉ chạy ở lượt soạn thật) vẫn dùng `_SQL_MOI_NHAT`/`moi_nhat_cua_hoi_thoai`
# đầy đủ — nó cần `id`/`so_lan_sua`/`clauses` mà bản nhẹ này không có.
# `:moi_loai` (không lọc) cho `_chuan_bi_phien`; `graph_tra_cuu._nap_ban_thao_dang_mo`
# lọc theo `viec_id` của lượt, cùng mệnh đề với `_SQL_MOI_NHAT`.
_SQL_MOI_NHAT_NHE = text(
    "SELECT document, audit, viec_id::text AS viec_id, phep_sua FROM ban_thao WHERE user_sub = CAST(:sub AS uuid)"
    " AND hoi_thoai_id = CAST(:pid AS uuid) AND loai = :loai AND xoa_luc IS NULL"
    " AND (:moi_loai OR viec_id IS NOT DISTINCT FROM CAST(:viec_id AS uuid))"
    " ORDER BY cap_nhat_luc DESC LIMIT 1"
)
# `khuon` của một bản thảo: KHÔNG kéo `noi_dung` (bytea, tới 20 MB) — chỉ khổ và
# `don_vi` để tính ô điền. Chủ sở hữu lọc bằng JOIN như `tai_lieu.khuon_goc_cua`.
_SQL_KHUON = text(
    "SELECT k.dinh_dang, k.so_trang, v.don_vi FROM khuon_goc k JOIN viec_doc_tai_lieu v ON v.id = k.viec_id"
    " WHERE k.viec_id = CAST(:viec_id AS uuid) AND v.user_sub = CAST(:sub AS uuid)"
)
# Cùng hàng, CÓ bytes — chỉ cho lần áp phép thật (dựng trang, tải về, lưu ô).
_SQL_KHUON_DAY = text(
    "SELECT k.dinh_dang, k.noi_dung, k.so_trang, v.don_vi, v.ten_tep FROM khuon_goc k"
    " JOIN viec_doc_tai_lieu v ON v.id = k.viec_id"
    " WHERE k.viec_id = CAST(:viec_id AS uuid) AND v.user_sub = CAST(:sub AS uuid)"
)
_SQL_XOA = text(
    "UPDATE ban_thao SET xoa_luc = now() WHERE id = CAST(:id AS uuid) AND user_sub = CAST(:sub AS uuid) AND xoa_luc IS NULL"
)


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False)


def _cot_khuon(viec_id: str | None, phep_sua: list | None) -> dict:
    """Tham số `viec_id`/`phep_sua` của `_SQL_TAO`/`_SQL_SUA`. `None` đi xuống là
    SQL NULL, không phải jsonb `null` — "không trên khuôn gốc" chỉ có một dạng."""
    return {"viec_id": viec_id, "phep_sua": None if phep_sua is None else _j(phep_sua)}


def _khuon_goc(c, sub: str, viec_id: str | None, *, bytes_: bool = False) -> dict | None:
    if not viec_id:
        return None
    r = c.execute(_SQL_KHUON_DAY if bytes_ else _SQL_KHUON, {"viec_id": viec_id, "sub": sub}).mappings().one_or_none()
    if r is None:
        return None
    return {**dict(r), **({"noi_dung": bytes(r["noi_dung"])} if bytes_ else {})}


def _khuon_tu(k: dict | None, viec_id: str | None, phep_sua: list | None) -> dict | None:
    """Hàng `_SQL_KHUON` + phép của MỘT phiên bản → `khuon` (hợp đồng BanThaoOut)."""
    if k is None:
        return None
    return {
        "viec_id": viec_id,
        "dinh_dang": k["dinh_dang"],
        "so_trang": k["so_trang"],
        "cho_trong": cho_trong_khuon(k["dinh_dang"], k["don_vi"], phep_sua),
    }


def _khuon(c, sub: str, viec_id: str | None, phep_sua: list | None) -> dict | None:
    """`khuon` của một phiên bản, hay `None`: không trên khuôn gốc, khuôn gốc đã
    bị xoá cùng hội thoại, hoặc không phải của `sub`. Bản thảo HTML không tốn
    truy vấn nào."""
    return _khuon_tu(_khuon_goc(c, sub, viec_id), viec_id, phep_sua)


def _voi_khuon(c, sub: str, row: dict) -> dict:
    return {**row, "khuon": _khuon(c, sub, row.get("viec_id"), row.get("phep_sua"))}


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

    Cả hai nhánh đọc `clauses` bằng KHOÁ DICT (`c["ten"]`/`c["noi_dung"]`), kể
    cả nhánh checklist (Phase 3, R2) — trước bản vá này nhánh đó đọc bằng
    THUỘC TÍNH (`c.ten`), chỉ đúng khi gọi bằng `DraftClause` thô như
    `tu_state_soan_thao` từng làm. `sua_tay` (R2, viết tay KHÔNG qua một lượt
    `draft_generate` mới) chỉ có sẵn `clauses` dạng dict (đọc thẳng từ cột
    JSONB) — ép cả hai nhánh về MỘT quy ước đọc là để hàm này dùng lại được
    cho `sua_tay` mà không cần một bản render thứ hai; `tu_state_soan_thao`
    (bên dưới) đổi sang truyền `dataclasses.asdict(c)` TRƯỚC khi gọi vào đây.
    """
    if loai == "tong_quat":
        phan = [f"# {tieu_de or 'Văn bản'}", ""]
        for i, c in enumerate(clauses, 1):
            phan.append(f"## {i}. {c['ten']}\n\n{c['noi_dung']}\n")
        return "\n".join(phan)
    cl = load_checklist_cached(loai)
    phan = [f"# {cl.tieu_de}", ""]
    for i, c in enumerate(clauses, 1):
        phan.append(f"## {cl.don_vi_muc} {i}. {c['ten']}\n\n{c['noi_dung']}\n")
    return "\n".join(phan)


def _tieu_de_tu_document(document: str | None) -> str | None:
    """Tiêu đề THẬT của một bản thảo tổng quát — dòng H1 đầu tiên của
    `document` (bản sao backend của `xuat-tep.tieuDeTuBanThao`, phía FE).

    `sua_tay` cần hàm này để dựng LẠI `document` sau khi sửa một khối mà
    KHÔNG đổi tiêu đề văn bản — `_render_markdown` chỉ nhận `tieu_de` làm
    tham số, nó không tự nhớ tiêu đề cũ."""
    dong_dau = (document or "").split("\n", 1)[0]
    m = re.match(r"^#\s+(.+)$", dong_dau.strip())
    return m.group(1).strip() if m else None


def kiem_tran_sua(cu: dict) -> None:
    """Trần sửa của MỘT bản thảo, phát biểu ở đúng một chỗ.

    `dung_lai` (bản thảo checklist) và `dung_ban_thao_tong_quat` (S6) đều gọi
    hàm này TRƯỚC khi làm bất cứ việc tốn kém nào, nên ngưỡng và lời từ chối chỉ
    có một bản. Đo trên cột ĐƠN ĐIỆU `so_lan_sua` chứ không trên độ dài
    `phien_ban_truoc` — xem docstring `dung_lai`.
    """
    if int(cu.get("so_lan_sua") or 0) >= TRAN_SUA:
        raise ValueError(LOI_HET_LAN_SUA)


# Giá trị mặc định của `ban_thao_tong_quat_dang_mo_nhe(viec_id=…)`: KHÔNG lọc — khác `None` (bản HTML).
_MOI_LOAI = object()


def moi_nhat_cua_hoi_thoai(sub: str, hoi_thoai_id: str, loai: str, *, viec_id: str | None) -> dict | None:
    """Bản thảo `loai` MỚI NHẤT của chính hội thoại này mà phiên bản đang sống
    nằm trên khuôn gốc `viec_id` (`None`: bản thảo HTML), hoặc `None`.

    Một lệnh sửa bằng lời ("đổi mục 2 thành…") không mang id nào, nên "bản thảo
    nào" phải suy ra được: trong một cuộc trò chuyện, đó là bản vừa dựng TRÊN
    CÙNG loại nguồn — `viec_id` bắt buộc nói ra, vì sửa nhầm loại là ghi đè
    (`sua` lưu `viec_id` của `ket`). Lọc theo `user_sub` ở tầng dữ liệu như mọi
    hàm khác trong file này.
    """
    with get_engine().connect() as c:
        r = (
            c.execute(_SQL_MOI_NHAT, {"sub": sub, "pid": hoi_thoai_id, "loai": loai, "viec_id": viec_id})
            .mappings()
            .one_or_none()
        )
        return _voi_khuon(c, sub, dict(r)) if r is not None else None


def ban_thao_tong_quat_dang_mo_nhe(
    sub: str, hoi_thoai_id: str, *, viec_id: str | None | object = _MOI_LOAI
) -> dict | None:
    """Bản thảo tổng quát MỚI NHẤT của hội thoại, bản NHẸ; KHÔNG lọc theo
    `viec_id` trừ khi được truyền (`None`: bản HTML, cùng luật `moi_nhat_cua_hoi_thoai`
    — `graph_tra_cuu._nap_ban_thao_dang_mo`) — CHỈ `document`/`audit`, đúng hai cột `routes._chuan_bi_phien` (chạy
    MỖI lượt hỏi có danh tính) và `hieu_tai_lieu._khoi_ban_thao_dang_co` thật
    sự đọc. Không kéo `clauses`/`facts`/`phien_ban_truoc` — nặng, và không ai
    ở hai nơi đó cần tới.

    P4a — thêm `viec_id`/`phep_sua` (hai cột nhỏ): lượt sửa bằng lời trên khuôn
    gốc cần biết phiên bản đang có đã điền gì. KHÔNG tính `khuon` ở đây (một lần
    đọc `don_vi` trên MỌI lượt hỏi); `moi_nhat_cua_hoi_thoai` có nó."""
    with get_engine().connect() as c:
        r = (
            c.execute(
                _SQL_MOI_NHAT_NHE,
                {
                    "sub": sub,
                    "pid": hoi_thoai_id,
                    "loai": LOAI_TONG_QUAT,
                    "moi_loai": viec_id is _MOI_LOAI,
                    "viec_id": None if viec_id is _MOI_LOAI else viec_id,
                },
            )
            .mappings()
            .one_or_none()
        )
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
    # Chuyển sang dict TRƯỚC khi gọi `_render_markdown` (Phase 3, R2): hàm đó
    # giờ đọc CẢ HAI nhánh bằng khoá dict, để `sua_tay` gọi lại được nó trên
    # `clauses` đã lưu (JSONB, luôn là dict, chưa từng là `DraftClause`).
    clauses_dict = [dataclasses.asdict(c) for c in clauses]
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
        "document": _render_markdown(st["loai"], clauses_dict),
        "clauses": clauses_dict,
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
                    **_cot_khuon(ket.get("viec_id"), ket.get("phep_sua")),
                },
            )
            .mappings()
            .one()
        )
        return _voi_khuon(c, sub, dict(r))


def _hang(c, sub: str, id: str) -> dict | None:
    r = c.execute(_SQL_LAY, {"sub": sub, "id": id}).mappings().one_or_none()
    return dict(r) if r is not None else None


def chi_tiet(sub: str, id: str) -> dict | None:
    with get_engine().connect() as c:
        r = _hang(c, sub, id)
        return _voi_khuon(c, sub, r) if r is not None else None


def _snap(row: dict, *, doi: list[str] | None = None) -> dict:
    """Chụp MỌI thứ cần để khôi phục lại đúng một phiên bản — `document`/`facts` một
    mình là không đủ: `clauses`/`audit` bị thiếu từng làm `lui` trả về một bản ghi
    lẫn (văn bản của phiên bản cũ với clauses/audit của phiên bản đang bị rời đi).

    Phase 4 (D11, R3) thêm `luc` (mốc giờ rời khỏi phiên bản này — luôn có,
    tính ngay tại đây) và `doi` (những gì đổi khi rời đi — CHỈ khi kẻ gọi đã
    tính được, `sua()` tính bằng `doi_so_voi`; `lui()` không sửa gì nên không
    truyền). Bỏ qua `doi` khi rỗng/`None` thay vì ghi `[]`: một danh sách rỗng
    trông như "đã kiểm, không đổi gì", còn bỏ khoá thì giao diện đọc y hệt một
    snapshot TỪ TRƯỚC bản vá này (không khoá `doi`) — không bịa ra một sự thật
    không tính được.

    Snapshot ghi TRƯỚC bản vá này không có hai khoá này — mọi nơi ĐỌC lại một
    `dict` từ `phien_ban_truoc` (đây, `lui`, và hai hàm đọc lịch sử bên dưới)
    phải dùng `.get(...)`, không chỉ số `[...]`, mới không nổ trên dữ liệu cũ.
    """
    snap = {
        "phien_ban": row["phien_ban"],
        "document": row["document"],
        "facts": row["facts"],
        "clauses": row["clauses"],
        "audit": row["audit"],
        "luc": datetime.now(UTC).isoformat(),
        # P4a — một phiên bản trên khuôn gốc LÀ danh sách phép của nó (cùng khuôn
        # gốc nó áp lên); `lui` khôi phục cả hai. Snapshot HTML giữ nguyên hình dạng.
        **(
            {"viec_id": row.get("viec_id"), "phep_sua": row.get("phep_sua")}
            if row.get("viec_id") or row.get("phep_sua") is not None
            else {}
        ),
    }
    if doi:
        snap["doi"] = doi
    return snap


def sua(sub: str, id: str, facts: dict, ket: dict) -> dict | None:
    # Fix round 1 (Critical) — đọc bằng `_SQL_LAY_KHOA` (FOR UPDATE) TRONG CÙNG
    # transaction với cú ghi bên dưới, không phải `chi_tiet()` trên một
    # connection riêng: xem chú thích ở khai báo `_SQL_LAY_KHOA` — đây là chỗ
    # duy nhất số phiên bản được cấp, nên đây là chỗ duy nhất cần khoá.
    with get_engine().begin() as c:
        cu = c.execute(_SQL_LAY_KHOA, {"sub": sub, "id": id}).mappings().one_or_none()
        if cu is None:
            return None
        cu = dict(cu)
        # Phase 4 (D11, R1) — số phiên bản MỚI lấy từ bộ đếm riêng
        # `phien_ban_ke_tiep`, không phải `cu["phien_ban"] + 1` nữa: cột đó có
        # thể bị `lui` kéo NGƯỢC xuống, còn bộ đếm này chỉ ĐI LÊN nên không bao
        # giờ cấp lại một số đã dùng — kể cả số của một nhánh `lui` đã bỏ đi mà
        # giờ vẫn được GIỮ LẠI (R2). `doi_so_voi` so facts CŨ (`cu`) với facts
        # MỚI (tham số `facts`) — đúng cặp mà `dung_lai` vẫn so sau khi gọi hàm
        # này, chỉ tính SỚM hơn một nhịp để gắn vào chính snapshot đang bị rời
        # đi (R3).
        # P4a — bản thảo trên khuôn gốc: "đổi gì" là các ô đổi giá trị, không
        # phải `facts` (luôn rỗng ở đó). Bản thảo HTML: hai `khuon` là `None`,
        # không truy vấn nào, `doi_so_voi` so `facts` như trước.
        khuon_moi = _khuon(c, sub, ket.get("viec_id"), ket.get("phep_sua"))
        khuon_cu = _khuon(c, sub, cu.get("viec_id"), cu.get("phep_sua"))
        doi = doi_so_voi({**cu, "khuon": khuon_cu}, {"facts": facts, "khuon": khuon_moi})
        # Fix round 1 (Important) — SẮP XẾP theo `phien_ban` trước khi cắt còn
        # `TRAN_SUA`: mảng không còn chắc tăng dần một khi `lui` đã giữ lại một
        # nhánh số LỚN hơn bản đang đứng (R2), nên cắt theo VỊ TRÍ mảng (phần tử
        # đầu) có thể bỏ đúng nhánh vừa bị rời đi thay vì tổ tiên cũ nhất — kém
        # hữu ích hơn để giữ. Sắp xếp trước khi cắt luôn bỏ SỐ NHỎ NHẤT trước,
        # bất kể mảng đã bị `lui` xáo trộn thế nào.
        truoc = sorted([*(cu["phien_ban_truoc"] or []), _snap(cu, doi=doi)], key=lambda t: t["phien_ban"])[
            -TRAN_SUA:
        ]
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
                    "phien_ban": cu["phien_ban_ke_tiep"],
                    "phien_ban_ke_tiep": cu["phien_ban_ke_tiep"] + 1,
                    "truoc": _j(truoc),
                    **_cot_khuon(ket.get("viec_id"), ket.get("phep_sua")),
                    # Bộ đếm trần sửa — chỉ ĐI LÊN, và chỉ ở đây (xem `lui`).
                    "tang": 1,
                },
            )
            .mappings()
            .one()
        )
    # `viec_id` lạ ghi ra NULL (`_VIEC_CUA_CHU`) — cùng lúc `_khuon` trả `None`.
    return {**dict(r), "khuon": khuon_moi}


LOI_MUC_KHONG_THAY = "Không tìm thấy mục này trong bản thảo."
LOI_KHOI_KHONG_SUA_DUOC = "Khối này không sửa được (không tồn tại, hoặc là một bảng)."
# Review (I3, frontend finding 6) — sửa tay là một PATCH THEO VỊ TRÍ
# (`muc_key`/`khoi_index`), và khoá `muc_key` được CẤP LẠI theo vị trí mỗi
# lần `dung_ban_thao_tong_quat`/`clauses_tu` dựng lại toàn bộ `clauses` (một
# lượt sửa bằng lời) — nên `muc_1` TRƯỚC một lượt sửa như vậy và `muc_1` SAU
# đó có thể là hai mục hoàn toàn khác nhau. Một khối đang mở trên màn hình từ
# TRƯỚC lượt sửa đó, blur SAU khi nó đã chạy, sẽ ghi đúng vị trí nhưng SAI
# mục. `phien_ban_ky_vong` là phiên bản người dùng ĐANG NHÌN THẤY lúc gõ —
# không khớp phiên bản THẬT (đọc trong CÙNG khoá `FOR UPDATE`, không phải so
# sánh lạc hậu) thì từ chối thay vì đoán mò.
LOI_PHIEN_BAN_DA_DOI = (
    "Bản thảo đã đổi (một lượt sửa khác vừa chạy) — tải lại bản thảo trước khi sửa tiếp."
)


def _khoi_hop_le_mot(k: dict) -> list[str]:
    """MỘT khối thô (`clause['khoi'][i]`) → danh sách "loai" khối nó thật sự
    hiển thị ra ("van_xuoi", "bang") — bản sao backend của `xuat-tep.
    khoiMotHopLe`: một khối lẽ ra chỉ mang MỘT trong hai (`noi_dung` HOẶC
    `bang`), nhưng không được TIN điều đó (Phase 8 fix round 1) — cả hai
    không rỗng thì trả CẢ HAI, văn xuôi trước, đúng thứ tự phía FE dựng.
    """
    if not isinstance(k, dict):
        return []
    noi_dung = k.get("noi_dung") if isinstance(k.get("noi_dung"), str) else ""
    bang = k.get("bang")
    ra = []
    if noi_dung != "":
        ra.append("van_xuoi")
    if isinstance(bang, list) and bang:
        ra.append("bang")
    return ra


def _vi_tri_khoi_tho(khoi_tho: list, khoi_index: int) -> int | None:
    """`khoi_index` (chỉ số khối HIỂN THỊ, đúng thứ tự `Muc.khoi` phía FE
    dựng — xem `khoiTuClause`) → chỉ số phần tử THÔ tương ứng trong
    `clause['khoi']`, hoặc `None` khi khối đó là bảng (chưa sửa được ở giai
    đoạn này — quyết định D dưới) hoặc `khoi_index` vượt quá số khối có.
    """
    dem = 0
    for i, k in enumerate(khoi_tho):
        for loai in _khoi_hop_le_mot(k):
            if dem == khoi_index:
                return i if loai == "van_xuoi" else None
            dem += 1
    return None


def _ap_dung_khoi(clause: dict, khoi_index: int, noi_dung_moi: str) -> dict | None:
    """`clause` cộng một khối văn xuôi đã sửa, hoặc `None` khi `khoi_index`
    không trỏ tới một khối văn xuôi sửa được.

    Ba hình dạng `clause` từng có (Phase 8 `khoi`; Phase 7 `noi_dung`+`bang`
    rời; trước đó chỉ `noi_dung`) — CÙNG bản đồ thứ tự `xuat-tep.
    khoiTuClause` phía FE dùng để dựng `Muc.khoi`, vì `khoi_index` gửi lên
    trỏ vào ĐÚNG mảng đó, không phải một chỉ số backend tự suy ra khác.

    Quyết định D (R1 — bảng không sửa được ở giai đoạn này): một khối `bang`
    luôn trả `None` ở đây, bất kể hình dạng — xem lý do trong báo cáo phase 3
    (`_khop_bang`/`_bang_khop_het` chỉ chạy lúc DỰNG bản thảo, không chạy lại
    trên một sửa tay; nhưng tỉ lệ cột/nhịp merge của một bảng chỉ sống trong
    `nhip`/`ti_le` — sửa ô rồi không có chỗ nào giữ lại hai trường đó nếu ghi
    đè cả `bang`, nên việc đó để một giai đoạn sau, có UI biên tập theo ô).
    """
    khoi = clause.get("khoi")
    if isinstance(khoi, list):
        i = _vi_tri_khoi_tho(khoi, khoi_index)
        if i is None:
            return None
        khoi_moi = list(khoi)
        khoi_moi[i] = {**khoi[i], "noi_dung": noi_dung_moi}
        return {**clause, "khoi": khoi_moi}
    # Hình dạng cũ (Phase 7 trở về trước, không có khoá `khoi`) — mirror thứ
    # tự văn-xuôi-rồi-bảng của `khoiTuClause`'s nhánh fallback.
    bang = clause.get("bang")
    bang_hop_le = isinstance(bang, list) and len(bang) > 0
    noi_dung_cu = clause.get("noi_dung")
    if noi_dung_cu is None:
        noi_dung_cu = "" if bang_hop_le else "[…]"
    if noi_dung_cu == "" or khoi_index != 0:
        return None
    return {**clause, "noi_dung": noi_dung_moi}


def sua_tay(
    sub: str, id: str, muc_key: str, khoi_index: int, noi_dung_moi: str, phien_ban_ky_vong: int
) -> dict | str | None:
    """Ghi văn bản gõ TAY vào một khối của một mục — 0 lượt gọi mô hình (Phase
    3, R1/R2): không đi qua `graph_soan_thao`/`draft_generate` như `sua()`
    thường được gọi (qua `dung_lai`), chỉ sửa TẠI CHỖ một khối của `clauses`
    đã lưu rồi ghi lại bằng ĐÚNG `_SQL_LAY_KHOA`/`_SQL_SUA` mà `sua()` dùng —
    một transaction, một khoá, không một cơ chế ghi song song.

    Trả `dict` (bản thảo mới) khi thành công; MỘT CHUỖI lỗi tiếng Việt khi
    request đúng hình dạng nhưng không làm được (hết trần sửa, mục/khối
    không thấy, phiên bản đã đổi — 422 ở tầng route); `None` khi bản thảo
    không thấy/không phải chủ (404, cùng hợp đồng mọi hàm khác ở đây).

    `TRAN_SUA` (R2) — MỘT sửa tay tính vào ĐÚNG bộ đếm `so_lan_sua` mà `sua()`
    dùng, không một bộ đếm riêng miễn phí: sửa tay không tốn tiền LLM, nhưng
    mỗi lần ghi đều đẩy một snapshot vào `phien_ban_truoc` (mảng CHỈ giữ
    `TRAN_SUA` bản gần nhất — xem `_snap`/dòng cắt mảng bên dưới), và một
    đường sửa không đếm vào trần sẽ ghi KHÔNG GIỚI HẠN, đủ để đẩy sạch mọi
    phiên bản THẬT (tốn tiền LLM) ra khỏi lịch sử — đúng rủi ro brief nêu
    ("uncapped edit path can evict real generated versions"). Chia sẻ trần
    với `dung_lai` nghĩa là một phiên sửa tay nhiều câu vẫn có thể chạm trần
    và phải mở bản thảo mới — đánh đổi đã biết, chấp nhận được vì mỗi lần gọi
    hàm này là một lần COMMIT (blur/rời khối), không phải mỗi phím gõ.

    `document` được DỰNG LẠI từ `clauses` đã sửa (R2) — không patch một dòng
    Markdown, để `document`/`clauses` không bao giờ trôi lệch nhau; tiêu đề
    (`tieu_de`) giữ NGUYÊN từ chính `document` cũ, không đổi.

    `phien_ban_ky_vong` (I3, fix round 1) — bản mà người dùng ĐANG NHÌN THẤY
    lúc gõ. `muc_key` là khoá CẤP THEO VỊ TRÍ (`clauses_tu`: `muc_1`, `muc_2`…)
    và bị CẤP LẠI mỗi khi một lượt sửa bằng lời dựng lại toàn bộ `clauses` —
    nên `muc_1` cũ và `muc_1` mới có thể là hai mục khác nhau. So sánh xảy ra
    TRONG CÙNG giao dịch, sau `_SQL_LAY_KHOA` (đọc phiên bản THẬT SỰ ĐANG có,
    không phải một giá trị đọc từ trước rồi lạc hậu) — không khớp thì từ chối
    thay vì âm thầm ghi đè một mục khác vị trí đó giờ đang giữ.
    """
    with get_engine().begin() as c:
        cu = c.execute(_SQL_LAY_KHOA, {"sub": sub, "id": id}).mappings().one_or_none()
        if cu is None:
            return None
        cu = dict(cu)
        if cu["phien_ban"] != phien_ban_ky_vong:
            return LOI_PHIEN_BAN_DA_DOI
        try:
            kiem_tran_sua(cu)
        except ValueError as e:
            return str(e)
        clauses = list(cu["clauses"] or [])
        idx = next((i for i, cl in enumerate(clauses) if isinstance(cl, dict) and cl.get("key") == muc_key), None)
        if idx is None:
            return LOI_MUC_KHONG_THAY
        clause_moi = _ap_dung_khoi(clauses[idx], khoi_index, noi_dung_moi)
        if clause_moi is None:
            return LOI_KHOI_KHONG_SUA_DUOC
        clauses_moi = list(clauses)
        clauses_moi[idx] = clause_moi
        # R3 (D3) — một sửa tay hạ MỨC KIỂM: bất cứ audit/checklist nào đã
        # chạy trên văn bản CŨ không còn nói đúng về văn bản NGƯỜI DÙNG vừa
        # viết. Dùng lại đúng giá trị `muc_kiem` mà một bản thảo tổng quát
        # (chưa qua checklist) đã mang — không phát minh một mã mới — cộng
        # thêm `sua_tay=True` để phân biệt "chưa ai kiểm" (bản thảo tổng quát
        # gốc) với "người dùng đã tự sửa" (badge khác nhau, xem `nhanMucKiem`).
        audit_moi = {**(cu["audit"] or {}), "muc_kiem": LOAI_TONG_QUAT, "sua_tay": True}
        # `_render_markdown`'s nhánh `tong_quat` đọc `c['noi_dung']` PHẲNG —
        # một `clause` tổng quát thật mang `khoi` (mảng khối), không phải một
        # chuỗi. `ket_ban_thao` (dung_ban_thao_tong_quat.py) đã giải quyết
        # đúng chỗ lệch này một lần cho đường DỰNG bản thảo, bằng
        # `_khoi_thanh_van_ban`; dùng LẠI đúng hàm đó ở đây (import trễ để
        # tránh vòng import — `dung_ban_thao_tong_quat` nhập module này ở đầu
        # file) thay vì một bản làm phẳng thứ hai có thể trôi lệch với bản
        # gốc. Bản thảo checklist (`loai != tong_quat`) đã đúng hình dạng
        # phẳng sẵn (`{ten, noi_dung}`), không cần bước này.
        #
        # Fix round 1 (review) — một clause KHÔNG có `khoi` (hình dạng Phase 7
        # trở về trước, `_ap_dung_khoi` vẫn sửa đúng bằng cách ghi thẳng vào
        # `noi_dung`/`bang` rời) từng làm `cl.get("khoi") or []` rơi về `[]`,
        # và `_khoi_thanh_van_ban([])` trả CHUỖI RỖNG — `document` bị GHI ĐÈ
        # bằng markdown trống cho đúng mục đó, không một lỗi nào báo ra (200,
        # `clauses` vẫn đúng). `_khoi_hien_thi_tu_clause` gói `noi_dung`/`bang`
        # rời thành MỘT khối tổng hợp khi không có `khoi`, để luôn có gì đó
        # cho `_khoi_thanh_van_ban` flatten — không phát minh một bản làm
        # phẳng thứ hai, chỉ đưa đúng dữ liệu vào hàm đã có.
        if cu["loai"] == LOAI_TONG_QUAT:
            from src.agents.nodes.dung_ban_thao_tong_quat import _khoi_thanh_van_ban

            def _khoi_hien_thi_tu_clause(cl: dict) -> list[dict]:
                khoi = cl.get("khoi")
                return khoi if isinstance(khoi, list) else [{"noi_dung": cl.get("noi_dung") or "", "bang": cl.get("bang") or []}]

            hien_thi = [
                {"ten": cl["ten"], "noi_dung": _khoi_thanh_van_ban(_khoi_hien_thi_tu_clause(cl))}
                for cl in clauses_moi
            ]
        else:
            hien_thi = clauses_moi
        document_moi = _render_markdown(cu["loai"], hien_thi, _tieu_de_tu_document(cu["document"]))
        # `facts` không đổi — `doi_so_voi` luôn `[]` cho một sửa tay (nó sửa
        # `clauses`, không sửa `facts`); giữ nguyên tham số cho `_snap` không
        # cần một hình dạng thứ hai.
        truoc = sorted([*(cu["phien_ban_truoc"] or []), _snap(cu)], key=lambda t: t["phien_ban"])[-TRAN_SUA:]
        r = (
            c.execute(
                _SQL_SUA,
                {
                    "sub": sub,
                    "id": id,
                    "facts": _j(cu["facts"]),
                    "document": document_moi,
                    "clauses": _j(clauses_moi),
                    "audit": _j(audit_moi),
                    "phien_ban": cu["phien_ban_ke_tiep"],
                    "phien_ban_ke_tiep": cu["phien_ban_ke_tiep"] + 1,
                    "truoc": _j(truoc),
                    **_cot_khuon(cu.get("viec_id"), cu.get("phep_sua")),
                    "tang": 1,
                },
            )
            .mappings()
            .one()
        )
        return _voi_khuon(c, sub, dict(r))


LOI_KHONG_PHAI_KHUON = (
    "Bản thảo này không điền trên tài liệu tải lên (hoặc tài liệu đó đã bị xoá), nên không có ô nào để lưu."
)
LOI_O_KHONG_THAY = "Không tìm thấy ô điền này trên tài liệu tải lên — tải lại bản thảo rồi thử lại."
# Bộ áp bỏ một phép: ô không còn khớp tài liệu (`cho_trong_da_doi`…) hay, trên
# PDF, chữ không vừa ô kể cả khi thu nhỏ (`khong_vua`) — hai việc người dùng làm
# được là rút gọn hoặc bỏ trống. `{o}` nêu TÊN các ô bị bỏ (`_nhan_o`, cùng tên
# bảng ô điền hiện) — không thì "ô đó" không chỉ ra ô nào giữa các ô vừa sửa.
LOI_KHONG_AP_DUOC = (
    "Không lưu được: {n} ô không điền được vào tài liệu tải lên{o} — giá trị quá dài cho ô,"
    " hoặc ô không còn khớp tài liệu. Rút gọn hay bỏ trống ô đó rồi lưu lại."
)
LOI_KHUON_HONG = "Không mở được tài liệu tải lên để điền. Hãy tải tài liệu lên lại."


def ap_phep_sua(dinh_dang: str, khuon_goc: bytes, don_vi: list | None, phep_sua: list | None) -> tuple[bytes, dict]:
    """Khuôn gốc NGUYÊN + danh sách phép ĐẦY ĐỦ của một phiên bản → `(bytes đã
    điền, báo cáo)` của bộ áp đúng định dạng. Bỏ trùng trước khi gọi: bộ áp PDF
    cho phép ĐẦU giữ vùng, còn một phiên bản muốn phép SAU thắng. Việc CPU —
    route gọi qua `run_in_threadpool`. `KhongDocDuoc` khi khuôn gốc không mở được."""
    ap = ap_dung_docx if dinh_dang == "docx" else ap_dung_pdf
    return ap(khuon_goc, don_vi or [], gop_phep_sua([], phep_sua, doan_cua_cho(don_vi)))


def khuon_cua_phien_ban(sub: str, id: str, phien_ban: int | None = None) -> dict | None:
    """Mọi thứ để dựng MỘT phiên bản trên khuôn gốc: `{dinh_dang, noi_dung,
    so_trang, don_vi, ten_tep, phep_sua, phien_ban}` — `phien_ban` `None` là bản
    đang sống. `None` khi bản thảo không thấy/không phải chủ, số phiên bản không
    có, hay phiên bản ấy không trên khuôn gốc (HTML, hoặc khuôn đã bị xoá)."""
    with get_engine().connect() as c:
        bt = _hang(c, sub, id)
        if bt is None:
            return None
        ban = (
            bt
            if phien_ban in (None, bt["phien_ban"])
            else next((t for t in bt["phien_ban_truoc"] or [] if t["phien_ban"] == phien_ban), None)
        )
        k = _khuon_goc(c, sub, (ban or {}).get("viec_id"), bytes_=True)
    return None if k is None else {**k, "phep_sua": ban.get("phep_sua"), "phien_ban": ban["phien_ban"]}


def sua_o_dien(sub: str, id: str, phien_ban: int, gia_tri: list[dict]) -> dict | str | None:
    """Lưu các ô người dùng sửa ở bảng ô điền thành MỘT phiên bản mới — 0 lượt
    gọi mô hình, cùng giao dịch/khoá/trần của `sua_tay` (xem docstring đó).

    `gia_tri`: `[{don_vi, cho_trong, gia_tri}]`, `gia_tri` rỗng gỡ ô. Trả `dict`
    (bản thảo, kể cả KHÔNG đổi gì — khi đó không tốn phiên bản), chuỗi lỗi tiếng
    Việt (422: phiên bản đã đổi, hết trần, không trên khuôn gốc, ô lạ, giá trị
    nhiều dòng, bộ áp bỏ một phép), `None` khi không thấy/không phải chủ (404).

    Gộp bằng `gop_phep_sua` vào phép của phiên bản ĐANG có, rồi CHẠY THỬ bộ áp
    trên khuôn gốc nguyên: một phép rơi vào `bo_qua` thì không lưu gì — không
    bao giờ có một phiên bản mà phép của nó không áp được. Không dựng trang: giao
    diện gọi `GET …/trang` MỘT lần sau khi lưu.

    ponytail: lần chạy thử (≤ 1 s cho một docx 10 trang) nằm TRONG khoá
    `FOR UPDATE` của đúng một bản thảo; đưa ra ngoài khoá (đọc, thử, ghi kèm so
    `phien_ban`) khi hai lần lưu cùng bản thảo đo được là chờ nhau. Nó KHÔNG giữ
    lượt dựng của tài khoản (`dung_trang._mot_luot`, từ chối ngay khi bận): một
    lần lưu trong lúc trang đang dựng không được thành 503. Khoá hàng đã nối
    tiếp mọi lần lưu của một bản thảo; nhiều bản thảo × nhiều IP của một tài
    khoản vẫn chạy thử song song — thêm một suất chờ theo tài khoản khi đo
    được."""
    with get_engine().begin() as c:
        cu = c.execute(_SQL_LAY_KHOA, {"sub": sub, "id": id}).mappings().one_or_none()
        if cu is None:
            return None
        cu = dict(cu)
        if cu["phien_ban"] != phien_ban:
            return LOI_PHIEN_BAN_DA_DOI
        try:
            kiem_tran_sua(cu)
        except ValueError as e:
            return str(e)
        k = _khuon_goc(c, sub, cu["viec_id"], bytes_=True)
        if k is None:
            return LOI_KHONG_PHAI_KHUON
        khuon_cu = _khuon_tu(k, cu["viec_id"], cu["phep_sua"])
        o_theo_khoa = {(o["don_vi"], o["so"]): o for o in khuon_cu["cho_trong"]}
        moi = []
        for g in gia_tri:
            o = o_theo_khoa.get((g.get("don_vi"), g.get("cho_trong")))
            if o is None:
                return LOI_O_KHONG_THAY
            try:
                gia_tri_o = chuan_hoa_dien(g.get("gia_tri"), o)
            except ValueError as e:
                return str(e)
            moi.append({"loai": "dien", "don_vi": o["don_vi"], "cho_trong": o["so"], "gia_tri": gia_tri_o})
        doan = doan_cua_cho(k["don_vi"])
        phep = gop_phep_sua(cu["phep_sua"], moi, doan)
        if phep == (cu["phep_sua"] or []):
            return {**cu, "khuon": khuon_cu}
        try:
            _, bao_cao = ap_phep_sua(k["dinh_dang"], k["noi_dung"], k["don_vi"], phep)
        except KhongDocDuoc:
            return LOI_KHUON_HONG
        if bao_cao["bo_qua"]:
            # Chỉ số `phep` trỏ vào đúng danh sách bộ áp nhận (`ap_phep_sua` gộp lại
            # một lần nữa — gộp là lũy đẳng). Phép không phải `dien` không có tên ô.
            ap = gop_phep_sua([], phep, doan)
            ten = [
                _nhan_o(o_theo_khoa[k])
                for b in bao_cao["bo_qua"]
                if (k := (ap[b["phep"]].get("don_vi"), ap[b["phep"]].get("cho_trong"))) in o_theo_khoa
            ]
            o = f" ({', '.join(f'“{t}”' for t in ten)})" if ten else ""
            return LOI_KHONG_AP_DUOC.format(n=len(bao_cao["bo_qua"]), o=o)
        khuon_moi = _khuon_tu(k, cu["viec_id"], phep)
        doi = doi_so_voi({"khuon": khuon_cu}, {"khuon": khuon_moi})
        truoc = sorted(
            [*(cu["phien_ban_truoc"] or []), _snap(cu, doi=doi)],
            key=lambda t: t["phien_ban"],
        )[-TRAN_SUA:]
        r = (
            c.execute(
                _SQL_SUA,
                {
                    "sub": sub,
                    "id": id,
                    "facts": _j(cu["facts"]),
                    "document": tom_tat_khuon(_tieu_de_tu_document(cu["document"]), khuon_moi),
                    "clauses": _j(cu["clauses"]),
                    # Cùng luật `sua_tay` (R3, D3): người dùng tự sửa hạ mức kiểm.
                    "audit": _j({**(cu["audit"] or {}), "muc_kiem": LOAI_TONG_QUAT, "sua_tay": True}),
                    "phien_ban": cu["phien_ban_ke_tiep"],
                    "phien_ban_ke_tiep": cu["phien_ban_ke_tiep"] + 1,
                    "truoc": _j(truoc),
                    **_cot_khuon(cu["viec_id"], phep),
                    "tang": 1,
                },
            )
            .mappings()
            .one()
        )
    return {**dict(r), "khuon": khuon_moi, "doi_so_voi_truoc": doi}


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
    """Lùi MỘT BƯỚC: khôi phục NGUYÊN VẸN mục gần nhất TRƯỚC bản đang đứng (số
    phiên bản nhỏ hơn, lớn nhất trong số đó). Gọi liên tiếp đi dần về bản CŨ
    NHẤT còn giữ (bị chặn bởi `TRAN_SUA`); tới đó rồi thì từ chối, trả về y
    nguyên bản hiện tại (không còn mục nào mang số NHỎ HƠN số đang đứng).

    Phase 4 (D11, R2) đổi "bỏ hẳn" thành GIỮ LẠI bản bị rời đi (đẩy vào chính
    `phien_ban_truoc`, giống `sua`), để một "phiên bản N" đã lùi qua vẫn đọc
    được sau này (`danh_sach_phien_ban`/`phien_ban_chi_tiet`). Giữ được là vì
    `phien_ban_ke_tiep` (R1) không đụng tới ở đây — số của bản bị rời đi không
    bao giờ bị một `sua()` sau này cấp lại, nên không còn gì để va số nữa.

    Vì mảng giờ có thể lẫn cả bản CŨ (tổ tiên, số nhỏ hơn) lẫn bản MỚI vừa bị
    bỏ (số LỚN hơn số đang đứng, giữ lại từ một lượt `lui` trước), "gần nhất
    trong lịch sử" không còn là phần tử CUỐI mảng nữa — phải LỌC những mục có
    số nhỏ hơn bản đang đứng rồi lấy số LỚN NHẤT trong đó mới đúng là tổ tiên
    gần nhất; nếu không còn mục nào như vậy (kể cả khi mảng không rỗng — toàn
    mục bị bỏ từ trước, số đều LỚN hơn) thì từ chối, đúng bất biến cũ.

    Fix round 1 (Critical) — đọc bằng `_SQL_LAY_KHOA` (FOR UPDATE) TRONG CÙNG
    transaction với cú ghi bên dưới, cùng lý do `sua()` khoá: `lui` cũng ghi
    lại `phien_ban_ke_tiep` (không đổi giá trị, nhưng cùng hàng), nên nó cũng
    phải nằm trong vùng khoá — nếu không, một `lui` và một `sua` gần như đồng
    thời có thể xen kẽ và một trong hai ghi đè bên kia bằng dữ liệu đã đọc từ
    trước khi bên kia commit.
    """
    with get_engine().begin() as c:
        cu = c.execute(_SQL_LAY_KHOA, {"sub": sub, "id": id}).mappings().one_or_none()
        if cu is None:
            return None
        cu = dict(cu)
        lich_su = cu["phien_ban_truoc"] or []
        ung_vien = [t for t in lich_su if t["phien_ban"] < cu["phien_ban"]]
        if not ung_vien:
            return _voi_khuon(c, sub, cu)
        gan = max(ung_vien, key=lambda t: t["phien_ban"])
        con = [t for t in lich_su if t is not gan]
        # Fix round 1 (Important) — sắp xếp trước khi cắt còn `TRAN_SUA`, cùng
        # lý do ở `sua()`: luôn bỏ số phiên bản NHỎ NHẤT trước, không phải
        # phần tử ở đầu mảng (có thể là nhánh vừa bị rời đi, hữu ích hơn để
        # giữ, nếu mảng đã bị xáo trộn bởi một lượt `lui` trước đó).
        truoc = sorted([*con, _snap(cu)], key=lambda t: t["phien_ban"])[-TRAN_SUA:]
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
                    # Bộ đếm KHÔNG lùi theo `phien_ban`: `lui` không cấp một số
                    # mới nào, nên giữ nguyên giá trị đang có (xem docstring).
                    "phien_ban_ke_tiep": cu["phien_ban_ke_tiep"],
                    "truoc": _j(truoc),
                    # `.get`: snapshot trước P4a không có hai khoá này — phiên bản HTML.
                    **_cot_khuon(gan.get("viec_id"), gan.get("phep_sua")),
                    # `tang = 0`: lùi KHÔNG trả lại một lần sửa. Trần đo bằng cột đơn điệu
                    # `so_lan_sua` chính vì mảng `phien_ban_truoc` bị hàm này bớt đi.
                    "tang": 0,
                },
            )
            .mappings()
            .one()
        )
        return _voi_khuon(c, sub, dict(r))


def danh_sach(sub: str, limit: int, offset: int) -> tuple[list[dict], int]:
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_DEM, {"sub": sub}).scalar_one())
        items = [dict(r) for r in c.execute(_SQL_DS, {"sub": sub, "limit": limit, "offset": offset}).mappings().all()]
    return items, tong


def xoa_mem(sub: str, id: str) -> bool:
    with get_engine().begin() as c:
        return c.execute(_SQL_XOA, {"sub": sub, "id": id}).rowcount > 0


def danh_sach_phien_ban(sub: str, id: str) -> list[dict] | None:
    """Phase 4 (D11, R4) — danh sách các phiên bản CŨ của một bản thảo, đủ để vẽ
    một bảng lịch sử: số, `luc`, `doi`. KHÔNG kèm `document`/`facts`/`clauses`/
    `audit` — cùng lý do R5 bớt `phien_ban_truoc` khỏi `danh_sach()`, chỉ ở quy
    mô một bản thảo thay vì cả trang danh sách. `None` khi không thấy/không
    phải chủ (404, giống mọi hàm khác ở đây).

    `.get("luc")`/`.get("doi") or []` — KHÔNG chỉ số `[...]`: một snapshot ghi
    TRƯỚC Phase 4 không có hai khoá này (`_snap` cũ), phải đọc được mà không
    nổ, không phải giả một mốc giờ hay một danh sách đổi bịa ra.
    """
    with get_engine().connect() as c:
        bt = _hang(c, sub, id)
    if bt is None:
        return None
    return [
        {"phien_ban": t["phien_ban"], "luc": t.get("luc"), "doi": t.get("doi") or []}
        for t in (bt["phien_ban_truoc"] or [])
    ]


def phien_ban_chi_tiet(sub: str, id: str, so: int) -> dict | None:
    """Phase 4 (D11, R4) — toàn bộ nội dung của MỘT phiên bản cũ cụ thể (tra
    trong `phien_ban_truoc` theo số). `None` khi bản thảo không thấy/không
    phải chủ, HOẶC khi `so` không khớp phiên bản cũ nào (kể cả khi `so` chính
    là số đang SỐNG — bản thảo hiện tại đã có `GET /ban-thao/{id}`, route này
    không phải một đường vòng thứ hai qua nó).
    """
    with get_engine().connect() as c:
        bt = _hang(c, sub, id)
        for t in (bt or {}).get("phien_ban_truoc") or []:
            if t["phien_ban"] == so:
                return {**t, "khuon": _khuon(c, sub, t.get("viec_id"), t.get("phep_sua"))}
    return None


def doi_so_voi(truoc: dict, sau: dict) -> list[str]:
    """Những gì đổi giữa hai phiên bản. Bản thảo trên khuôn gốc (một trong hai
    mang `khuon`): các ô đổi giá trị, `"nhãn: cũ → mới"` theo `(don_vi, so)`.
    Mọi bản thảo khác: các khoá `facts` đổi, đúng hình dạng trước P4a."""
    if truoc.get("khuon") or sau.get("khuon"):
        return _doi_o(truoc.get("khuon"), sau.get("khuon"))
    a, b = truoc.get("facts") or {}, sau.get("facts") or {}
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


# ═══ Khuôn gốc — quyết định 2026-09-26, kế hoạch `khuon-goc-dien-tai-cho.md` ═══
# Bản thảo trên một tài liệu có khuôn gốc mang `viec_id` + `phep_sua` (migration
# 037) thay cho văn bản mô hình viết lại. Mỗi phiên bản là danh sách phép ĐẦY
# ĐỦ của nó, áp lên khuôn gốc NGUYÊN (`ap_phep_sua`); `khuon` là thứ giao diện
# cần để vẽ bảng ô điền, tính lại từ `don_vi` đã lưu mỗi lần đọc.

LOI_GIA_TRI_DIEN = "Giá trị điền chỉ được một dòng chữ, không xuống dòng hay ký tự điều khiển."
_LOAI_PHEP = ("dien", "thay", "xoa", "chen_sau")


def _khoa_phep(p: Any) -> tuple | None:
    """Khoá gộp của một phép, hay `None` khi nó không phải một trong bốn loại
    đúng hình dạng khoá (bộ áp sẽ bỏ nó dù sao; ở đây nó không được chiếm chỗ)."""
    if not isinstance(p, dict) or p.get("loai") not in _LOAI_PHEP or not _so_tu_nhien(p.get("don_vi")):
        return None
    if p["loai"] == "dien":
        return ("dien", p["don_vi"], p["cho_trong"]) if _so_tu_nhien(p.get("cho_trong")) else None
    if p["loai"] == "chen_sau":
        return ("chen_sau", p["don_vi"], p["noi_dung"]) if isinstance(p.get("noi_dung"), str) else None
    if p["loai"] == "thay" and _so_tu_nhien(p.get("doan")):
        return ("thay_doan", p["don_vi"], p["doan"])
    return ("cau_truc", p["don_vi"])


def doan_cua_cho(don_vi: list | None) -> dict[tuple[int, int], int]:
    """`(don_vi, so)` → đoạn chứa chỗ trống DOCX đó — để `gop_phep_sua` biết
    `thay` theo đoạn gỡ ô nào."""
    return {
        (d["chi_so"], c.so): c.doan
        for d in don_vi or []
        if isinstance(d, dict) and _so_tu_nhien(d.get("chi_so"))
        for c in _cho_trong_tu_hang(d.get("cho_trong"))
        if c.hop is None
    }


def gop_phep_sua(
    cu: list[dict] | None, moi: list[dict] | None, doan_cua: dict[tuple[int, int], int] | None = None
) -> list[dict]:
    """Danh sách phép của phiên bản mới: `cu` (phiên bản đang có) cộng CHỈ PHẦN
    ĐỔI `moi` — MỘT luật cho lượt sửa bằng lời (P4b) và bảng ô điền
    (`sua_o_dien`). Thuần, không sửa đầu vào.

    `dien` khoá theo `(don_vi, cho_trong)`, phép sau thắng; `gia_tri` rỗng (sau
    `strip`) gỡ ô đó — dãy chấm trở lại. `thay`/`xoa` chung MỘT khoá `don_vi`,
    phép sau thắng (bộ áp coi phép cấu trúc thứ hai trên một vật chứa là xung
    đột). `chen_sau` khoá theo `(don_vi, noi_dung)`: bỏ trùng, giữ thứ tự. Phép
    đổi giá trị giữ CHỖ cũ trong danh sách, nên bộ áp PDF (phép trước giữ vùng)
    thấy một danh sách đã bỏ trùng.

    Chéo loại: một `thay`/`xoa` trên một đơn vị gỡ MỌI `dien` của đơn vị ấy, dù
    đến trước hay sau — đoạn đã thay/xoá không còn dãy chấm nào, bộ áp sẽ bỏ
    `dien` đó (`xung_dot`) mà `assemble` lại đếm là đã điền.

    `thay` theo `doan` khoá theo `(don_vi, doan)`, phép sau thắng; nó và phép cả
    đơn vị (`thay`/`xoa`) trên cùng đơn vị cũng loại nhau, phép sau thắng (bộ áp
    coi hai thứ ấy là xung đột). Nó chỉ gỡ `dien` của chỗ trống thuộc CHÍNH đoạn
    đó — `doan_cua` (`doan_cua_cho`) nói chỗ trống nào ở đoạn nào; thiếu thì
    không gỡ `dien` nào (bộ áp sẽ báo `xung_dot` cho chỗ trống của đoạn đã thay)."""
    gop: dict[tuple, dict] = {}
    for p in [*(cu or []), *(moi or [])]:
        k = _khoa_phep(p)
        if k is None:
            continue
        if k[0] == "dien" and not str(p.get("gia_tri") or "").strip():
            gop.pop(k, None)
        elif k[0] == "chen_sau":
            gop.setdefault(k, p)
        else:
            for cu_k in [c for c in gop if c[1] == k[1] and {c[0], k[0]} == {"cau_truc", "thay_doan"}]:
                del gop[cu_k]
            gop[k] = p
    da_doi = {k[1] for k in gop if k[0] == "cau_truc"}
    doan_doi = {k[1:] for k in gop if k[0] == "thay_doan"}
    return [
        p
        for k, p in gop.items()
        if not (k[0] == "dien" and (k[1] in da_doi or (k[1], (doan_cua or {}).get(k[1:], -1)) in doan_doi))
    ]


def cho_trong_khuon(dinh_dang: str, don_vi: list | None, phep_sua: list | None) -> list[dict]:
    """Các ô điền được của MỘT phiên bản: `[{don_vi, so, kieu, nhan, gia_tri}]`,
    `gia_tri` là giá trị phiên bản đó đã điền hay `None` (còn dãy chấm).

    Chỉ ô bộ áp tới được: DOCX cần đơn vị có `dia_chi` và chỗ trống kiểu DOCX,
    PDF cần chỗ trống có `hop`. Đơn vị đã bị `thay`/`xoa` (hay ĐOẠN đã bị `thay`
    theo `doan`) không còn dãy chấm nào, nên ô của nó không được mời điền — một
    lần lưu chắc chắn bị bỏ."""
    phep = gop_phep_sua([], phep_sua, doan_cua_cho(don_vi))
    doan_doi = {(p["don_vi"], p["doan"]) for p in phep if p["loai"] == "thay" and _so_tu_nhien(p.get("doan"))}
    da_doi = {
        p["don_vi"] for p in phep if p["loai"] == "xoa" or (p["loai"] == "thay" and not _so_tu_nhien(p.get("doan")))
    }
    gia_tri = {(p["don_vi"], p["cho_trong"]): p["gia_tri"] for p in phep if p["loai"] == "dien"}
    ra = []
    nhan = ""  # `nhan_sach` lại trên hàng đã lưu: tài liệu cũ mang nhãn thô
    for d in don_vi or []:
        if not isinstance(d, dict) or not _so_tu_nhien(d.get("chi_so")) or d["chi_so"] in da_doi:
            continue
        if dinh_dang == "docx" and _dia_chi_tu_hang(d.get("dia_chi")) is None:
            continue
        for c in _cho_trong_tu_hang(d.get("cho_trong")):
            if (c.hop is not None) == (dinh_dang == "pdf") and (d["chi_so"], c.doan) not in doan_doi:
                nhan = nhan_sach(c.nhan, nhan)
                o = {"don_vi": d["chi_so"], "so": c.so, "kieu": c.kieu, "nhan": nhan}
                ra.append({**o, "gia_tri": gia_tri.get((d["chi_so"], c.so))})
    return ra


def ban_do(dinh_dang: str, don_vi: list | None, phep_sua: list | None):
    """Bước `do` của `dung_trang.dung` cho một phiên bản: bản dò mốc ĐÚNG các ô
    `o_tren_trang` sẽ liệt kê (cùng `cho_trong_khuon`). `None` với PDF — hộp đã
    lưu — hay khi phiên bản không có ô nào."""
    o = [(x["don_vi"], x["so"]) for x in cho_trong_khuon(dinh_dang, don_vi, phep_sua)]
    if dinh_dang != "docx" or not o:
        return None
    return lambda docx: danh_dau_docx(docx, don_vi or [], o)


def o_tren_trang(dinh_dang: str, don_vi: list | None, phep_sua: list | None, vi_tri: dict | None = None) -> list[dict]:
    """Khoá `o` của hai route trang: mỗi ô `cho_trong_khuon` của phiên bản, theo
    thứ tự đọc, `{don_vi, so, trang, hop, nhan, gia_tri}` — `trang` chỉ số từ 0
    vào `trang` của phản hồi, `hop` bằng điểm gốc trên-trái như `kho`, `gia_tri`
    đã `strip` hay `None`.

    PDF: hộp bộ đọc đã lưu, trên trang của đơn vị (ô đã điền giữ hộp của nó).
    DOCX: `vi_tri` đo trên chính trang vừa dựng (`dung_trang.vi_tri_o`). Không
    đo được thì `trang`/`hop` là `None` — giao diện gọi là "chưa định vị"."""
    if dinh_dang == "pdf":
        vi_tri = {}
        for d in don_vi or []:
            if isinstance(d, dict) and _so_tu_nhien(d.get("chi_so")) and _so_tu_nhien(d.get("trang")) and d["trang"]:
                for c in _cho_trong_tu_hang(d.get("cho_trong")):
                    if c.hop is not None:
                        vi_tri[(d["chi_so"], c.so)] = (d["trang"] - 1, list(c.hop))
    ra = []
    for o in cho_trong_khuon(dinh_dang, don_vi, phep_sua):
        trang, hop = (vi_tri or {}).get((o["don_vi"], o["so"]), (None, None))
        gia_tri = (o["gia_tri"] or "").strip() or None
        ra.append(
            {"don_vi": o["don_vi"], "so": o["so"], "trang": trang, "hop": hop, "nhan": o["nhan"], "gia_tri": gia_tri}
        )
    return ra


def chuan_hoa_dien(gia_tri: str, o: dict) -> str:
    """Giá trị người dùng gõ cho ô `o` → giá trị bộ áp nhận, hoặc `ValueError`
    (`LOI_GIA_TRI_DIEN`). Rỗng sau `strip` là "gỡ ô".

    Khoảng trắng Unicode (NBSP dán từ Word) về dấu cách thường, NFC, `strip`;
    còn ký tự không in được (xuống dòng, tab, điều khiển, zero-width) thì từ
    chối — bộ áp PDF bỏ chúng, còn một ô điền là một dòng. Ô `tab` đặt giá trị
    ngay sau nhãn, không ký tự nào xen giữa: thêm một dấu cách khi nhãn không kết
    bằng khoảng trắng (bộ đọc `strip` nhãn, nên thực tế là luôn thêm)."""
    s = "".join(" " if unicodedata.category(ch) == "Zs" else ch for ch in gia_tri or "")
    s = unicodedata.normalize("NFC", s).strip()
    if not s.isprintable():
        raise ValueError(LOI_GIA_TRI_DIEN)
    if s and o.get("kieu") == "tab" and not (o.get("nhan") or "")[-1:].isspace():
        s = " " + s
    return s


def _nhan_o(o: dict) -> str:
    return (o.get("nhan") or "").strip().rstrip(":").strip() or f"Ô {o['don_vi']}.{o['so']}"


def _doi_o(a: dict | None, b: dict | None) -> list[str]:
    cu = {(o["don_vi"], o["so"]): o for o in (a or {}).get("cho_trong") or []}
    moi = {(o["don_vi"], o["so"]): o for o in (b or {}).get("cho_trong") or []}
    ra = []
    for k in [*moi, *(k for k in cu if k not in moi)]:
        x, y = (cu.get(k) or {}).get("gia_tri"), (moi.get(k) or {}).get("gia_tri")
        if x != y:
            ra.append(f"{_nhan_o(moi.get(k) or cu[k])}: {(x or '').strip() or '…'} → {(y or '').strip() or '…'}")
    return ra


def tom_tat_khuon(tieu_de: str | None, khuon: dict | None) -> str:
    """`document` Markdown của một bản thảo trên khuôn gốc: tiêu đề và một dòng
    cho mỗi ô đã điền. Bản thật là khuôn gốc đã áp phép; `document` chỉ để chat,
    tìm kiếm và `_tieu_de_tu_document` có chữ để đọc."""
    dong = [f"- {_nhan_o(o)}: {o['gia_tri'].strip()}" for o in (khuon or {}).get("cho_trong") or [] if o.get("gia_tri")]
    return f"# {tieu_de or 'Văn bản'}\n" + ("\n" + "\n".join(dong) + "\n" if dong else "")


# Khoá dòng việc đọc (chính chủ) cho `mo_ban_thao_khuon`: hai cú bấm "mở bảng ô
# điền" đồng thời nối tiếp nhau, nên cú thứ hai thấy bản cú đầu vừa tạo.
_SQL_KHOA_VIEC = text(
    "SELECT hoi_thoai_id::text AS hoi_thoai_id, ten_tep FROM viec_doc_tai_lieu"
    " WHERE id = CAST(:viec_id AS uuid) AND user_sub = CAST(:sub AS uuid) FOR UPDATE"
)


def mo_ban_thao_khuon(sub: str, viec_id: str) -> tuple[dict, bool] | None:
    """Bản thảo để bảng ô điền mở được trên khuôn gốc `viec_id` — thao tác RÕ của
    người dùng, 0 lượt mô hình, không hạn mức (Outcome 4 của kế hoạch). `(bản
    thảo, đã_tạo)`: bản MỚI NHẤT của việc đó (phiên bản đang sống trên
    `viec_id`), hay phiên bản 1 mới với `phep_sua` rỗng. `None` khi việc đọc lạ,
    của người khác, hoặc không có khuôn gốc (404)."""
    with get_engine().begin() as c:
        v = c.execute(_SQL_KHOA_VIEC, {"sub": sub, "viec_id": viec_id}).mappings().one_or_none()
        k = _khuon_goc(c, sub, viec_id) if v is not None else None
        if k is None:
            return None
        cu = (
            c.execute(
                _SQL_MOI_NHAT,
                {"sub": sub, "pid": v["hoi_thoai_id"], "loai": LOAI_TONG_QUAT, "viec_id": viec_id},
            )
            .mappings()
            .one_or_none()
        )
        if cu is not None:
            return _voi_khuon(c, sub, dict(cu)), False
        khuon = _khuon_tu(k, viec_id, [])
        audit = {
            "dat": None,
            "completeness": None,
            "so_dieu_khoan": 0,
            "self_audit": False,
            "findings": [],
            "muc_kiem": LOAI_TONG_QUAT,
        }
        r = (
            c.execute(
                _SQL_TAO,
                {
                    "sub": sub,
                    "pid": v["hoi_thoai_id"],
                    "loai": LOAI_TONG_QUAT,
                    "facts": _j({}),
                    "document": tom_tat_khuon(PurePath(v["ten_tep"] or "").stem or None, khuon),
                    "clauses": _j([]),
                    "audit": _j(audit),
                    **_cot_khuon(viec_id, []),
                },
            )
            .mappings()
            .one()
        )
    return {**dict(r), "khuon": khuon}, True
