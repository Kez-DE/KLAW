import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from starlette.concurrency import run_in_threadpool

from src.agents.graph_soan_thao import (
    KhongSoanDuocError,
    build_graph_soan_thao,
    cac_loai,
    chi_van_ban_hien,
    extract_clauses,
    load_checklist_cached,
    load_facts_meta_cached,
    requirements,
    rules_cho,
)
from src.agents.graph_tra_cuu import build_graph_tra_cuu
from src.agents.nodes.assemble import xem_ban_thao_khuon
from src.agents.nodes.draft_audit import draft_audit
from src.agents.nodes.hieu_tai_lieu import xin_xem_ban_thao
from src.config import as_of_hieu_luc, get_settings
from src.models.schemas import (
    AuditReportOut,
    CauTrucMauOut,
    FactFieldOut,
    LoaiVanBan,
    LuotTruoc,
    MauResponse,
    MucLucItem,
    MucMauOut,
    PhamViResponse,
    ProvisionOut,
    SoanThaoRequest,
    SoanThaoResponse,
    SoatRequest,
    SoatResponse,
    TangPhamViOut,
    TraCuuRequest,
    TraCuuResponse,
    VanBanMucLucResponse,
    VanBanPhamViOut,
    VanBanProvisionsResponse,
)
from src.services import ban_thao, bao_ve, bo_nho, cache_tra_loi
from src.services import hoi_thoai as hoi_thoai_svc
from src.services import tai_lieu as tl
from src.services.bao_ve import cong_bao_ve, cong_bao_ve_khach, cong_nhe
from src.services.checklist import KHUNG_HOP_DONG, Checklist
from src.services.db import get_engine
from src.services.hien_thi import chan_neu_an, hien_thi_luc
from src.services.rules import Rule, enum_facts, mo_ta_facts, ten_tham_so

# _tong_hop_traces re-exported here: test_tra_cuu.py imports it from routes, not services.traces.
from src.services.traces import _ghi_traces, _tong_hop_traces, dau_van_ban  # noqa: F401
from src.services.trich_dan import truong_trich_dan

logger = logging.getLogger(__name__)

# Loại văn bản hỗ trợ được = loại CÓ `config/checklist_<loai>.yaml` — suy thẳng
# từ đĩa (`cac_loai()`), không một danh sách viết tay nào trong Python. Một giá
# trị `LoaiVanBan` hợp lệ ở tầng Pydantic nhưng chưa có file checklist vẫn bị từ
# chối trung thực bằng 501: áp nhầm checklist của loại khác lên nó sẽ cho một
# audit report trông hợp lệ nhưng SAI loại văn bản.

router = APIRouter()


async def _ghi_traces_nhe(
    trace_id: str, endpoint: str, query: str, config_name: str, st: dict, latency_ms: int,
    cache_hit: bool = False, user_sub: str | None = None,
) -> None:
    """`_ghi_traces` nhưng KHÔNG BAO GIỜ raise.

    Telemetry hỏng không phải lý do từ chối một câu trả lời đã tính ĐÚNG — khác
    lỗi hạ tầng của chính graph, cái đó PHẢI nổ vì nó quyết định `result_type`;
    ghi traces không quyết định gì.

    Một chỗ, không phải ba khối `try/except` chép tay: hàm này cũng được gọi
    TRONG `finally` của đường lỗi, và ở đó một ngoại lệ thoát ra sẽ THAY THẾ
    ngoại lệ thật đang lan lên — nuốt mất nguyên nhân gốc của sự cố.
    """
    try:
        await run_in_threadpool(
            _ghi_traces, trace_id, endpoint, query, config_name, st, latency_ms,
            cache_hit, user_sub,
        )
    except Exception:
        logger.exception(
            "ghi traces thất bại (trace_id=%s, endpoint=%s) — KHÔNG chặn response",
            trace_id, endpoint,
        )

_graph = None


def _g():
    global _graph
    if _graph is None:
        _graph = build_graph_tra_cuu()
    return _graph


def _payload_cache(st: dict, rt: str) -> dict:
    """Đúng những field của `TraCuuResponse` phụ thuộc NỘI DUNG câu trả lời.

    KHÔNG gồm `trace_id` (mỗi request một cái — xem `_st_tu_cache`) và không gồm
    `config_name` (đã nằm TRONG khoá cache, lưu lại chỉ tạo hai nguồn sự thật).
    """
    return {
        "result_type": rt, "answer": st.get("answer"), "citations": st.get("citations") or [],
        "warnings": st.get("warnings") or [], "coverage_note": st.get("coverage_note"),
        "nguon": st.get("nguon") or [],
        # Đi vào payload dù lượt nối tiếp KHÔNG được cache (xem `chay_tra_cuu`):
        # payload là MỘT hình dạng cho cả hai đường, và `tra_cuu_response` đọc
        # đúng dict này. Ở đường không-cache nó luôn là `None`.
        "cau_hoi_day_du": st.get("cau_hoi_day_du"),
        # `bang` (T4) — list[dict] THUẦN (assemble/graph_tra_cuu đã gọi
        # `model_dump()`), nên `json.dumps` ở `cache_tra_loi.ghi_cache` tuần
        # tự hoá được thẳng, không cần bước chuyển nào ở đây.
        "bang": st.get("bang") or [],
        # `documents` (spec 2026-09-06) — list[dict] thuần, cùng khuôn `bang`.
        "documents": st.get("documents") or [],
        "soan_thao": st.get("soan_thao_goi_y"),
        "ho_so_da_dung": st.get("ho_so_da_dung") or [],
        # Task 19 — hai kết quả của soạn thảo trong chat. `None` ở mọi nhánh
        # khác, cùng lý do `soan_thao` ngay trên.
        "soan_thao_hoi": st.get("soan_thao_hoi"),
        "ban_thao": st.get("ban_thao"),
        # Lượt đọc tài liệu. Không dòng nào của nó vào cache (`_bo_qua_cache`
        # tắt cache cho mọi lượt có tài liệu) — vẫn đi qua đây vì payload là MỘT
        # hình dạng cho cả hai đường, và `tra_cuu_response` đọc đúng dict này.
        "tai_lieu": st.get("tai_lieu"),
        "tai_lieu_neo": st.get("tai_lieu_neo") or [],
        "van_ban_khong_hien_thi": st.get("van_ban_khong_hien_thi") or [],
        # NỘI BỘ — dùng để ghi giả định của `suy_dien` vào phiên sau khi lượt
        # này lưu xong (xem `luu_suy_dien` ở `tra_cuu`/`_chay_nen`). KHÔNG đi
        # vào `TraCuuResponse`: `tra_cuu_response` không đọc khoá này.
        "ho_so": st.get("ho_so") or {},
        # NỘI BỘ (Task 19) — trạng thái soạn thảo của phiên SAU lượt này, để
        # `tra_cuu`/`_chay_nen` chốt nó vào `hoi_thoai.soan_thao` một khi câu
        # trả lời đã tính xong. KHÔNG đi vào `TraCuuResponse`.
        "soan_thao_dang_mo": st.get("soan_thao_dang_mo"),
        # NỘI BỘ (Task 19) — ý định lượt này đã phân loại, chỉ để quyết định có
        # ghi đè `soan_thao_dang_mo` của phiên hay không (giữ nguyên khi
        # `tra_cuu`, xem `tra_cuu`/`_chay_nen`). KHÔNG đi vào `TraCuuResponse`.
        "intent": st.get("intent"),
    }


def _state_vao(
    req: TraCuuRequest,
    as_of: date,
    trace_id: str,
    bo_nho: dict | None = None,
    user_sub: str | None = None,
    hoi_thoai_id: str | None = None,
    soan_thao: dict | None = None,
    tai_lieu_phien: list[dict] | None = None,
    ban_thao_tong_quat: dict | None = None,
) -> dict:
    """State đầu vào của graph — MỘT chỗ dựng cho cả đường POST và đường SSE.

    `query` là câu người dùng GÕ, không phải câu đã giải nghĩa: node `giai_nghia`
    tự thay nó bên trong graph, và endpoint này không được biết trước kết quả của
    một bước chạy sau nó.

    `lich_su` xuống dạng `dict` (`model_dump`), cùng hình dạng với `expanded`/
    `hits_shallow` trong state — LangGraph state là dữ liệu thuần, một model
    pydantic đi lẫn vào đó là một kiểu thứ hai cho cùng một thứ.

    `bo_nho` — `{"tom_tat", "ho_so"}` của `_chuan_bi_phien` (spec 2026-09-09 §6);
    `None` khi ẩn danh hoặc phiên chưa có gì để nạp.

    `user_sub`/`hoi_thoai_id`/`soan_thao` (Task 19) — chủ phiên, phiên hiện tại,
    và trạng thái soạn thảo ĐANG MỞ của phiên (`hoi_thoai.soan_thao_cua_phien`),
    để `route`/`gom_du_kien`/`dung_ban_thao` biết hội thoại này có đang soạn dở
    hay không mà không phải đọc lại request HTTP. `None` cùng lý do `bo_nho`.

    `tai_lieu_phien` — tài liệu hội thoại này đang giữ (`_chuan_bi_phien`, đã
    lọc theo chủ). `tai_lieu_ids` xuống dạng `str`: LangGraph state là dữ liệu
    thuần (cùng quy ước `lich_su`), và một `UUID` lẫn vào đó không `json.dumps`
    được ở tầng cache.

    `ban_thao_tong_quat` (Phase 3 Half B, R5) — bản thảo tổng quát mới nhất
    của hội thoại (`_chuan_bi_phien`), xem `KLawState.ban_thao_tong_quat_dang_mo`.
    """
    return {
        "query": req.query,
        "tai_lieu_ids": [str(i) for i in req.tai_lieu_ids],
        "tai_lieu_phien": list(tai_lieu_phien or []),
        "ban_thao_tong_quat_dang_mo": ban_thao_tong_quat,
        "lich_su": [luot.model_dump() for luot in req.lich_su],
        "as_of_date": as_of,
        "trace_id": trace_id,
        "tom_tat": (bo_nho or {}).get("tom_tat"),
        "ho_so": dict((bo_nho or {}).get("ho_so") or {}),
        "user_sub": user_sub,
        "hoi_thoai_id": hoi_thoai_id,
        "soan_thao_dang_mo": soan_thao,
    }


# Cùng câu chữ với `routes_tai_lieu.KHONG_THAY` — không nhập hằng từ đó: hai
# module đang được hai lát cắt sửa song song, và một `ImportError` ở đây làm
# CẢ API không khởi động được.
LOI_TAI_LIEU_KHONG_THAY = "Không tìm thấy tài liệu"
LOI_TAI_LIEU_DANG_NHAP = "Hãy đăng nhập để hỏi về tài liệu bạn đã gửi."


async def _chuan_bi_phien(
    req: TraCuuRequest, user_sub: str | None
) -> tuple[TraCuuRequest, str | None, dict | None, dict | None, list[dict], dict | None]:
    """Gắn lượt hỏi vào một phiên (spec 2026-09-07 §5.2, spec 2026-09-09 §6.3-6.4).
    Ẩn danh → bỏ qua `hoi_thoai_id` VÀ bộ nhớ. Có danh tính: chưa có id → tạo phiên
    (Pro đang bật ghi nhớ thì seed hồ sơ tài khoản vào phiên mới); có id → kiểm chủ
    (404), kiểm đủ trần lượt của gói → 403, nạp `lich_su` VÀ bộ nhớ ba lớp từ máy
    chủ, BỎ `lich_su` client gửi.

    Trả `(req, hoi_thoai_id, bo_nho, soan_thao, tai_lieu_phien, ban_thao_tong_quat)`
    — `bo_nho` là `{"tom_tat", "ho_so"}`
    hoặc `None` (ẩn danh, hoặc phiên mới không có gì để seed); `soan_thao` (Task 19)
    là trạng thái soạn thảo ĐANG MỞ của phiên (`hoi_thoai.soan_thao_cua_phien`, đã
    lọc theo CHỦ), `None` khi ẩn danh, phiên mới, hoặc phiên chưa từng soạn gì.
    `ban_thao_tong_quat` (Phase 3 Half B, R5) là dòng `ban_thao` TỔNG QUÁT mới
    nhất của phiên (`ban_thao.moi_nhat_cua_hoi_thoai`), `None` cùng lý do
    `soan_thao` — xem `KLawState.ban_thao_tong_quat_dang_mo`.

    `tai_lieu_phien` (plan `tai-lieu-tong-quat.md`) là tài liệu hội thoại đang
    giữ. Đây cũng là chỗ DUY NHẤT kiểm `req.tai_lieu_ids`, và nó phải nằm ở đây
    chứ không trong graph: `/tra-cuu/luong` gọi hàm này TRƯỚC khi mở stream, nên
    404/401 còn ra được mã HTTP thật thay vì một `event: loi` giữa dòng.

    Lỗi DB ở đây KHÔNG bị nuốt: 500 tại chỗ này nghĩa là chính Postgres vốn đã gác
    request ở `cong_bao_ve` đang chết, và âm thầm đánh rơi một lượt của người đã
    đăng nhập khỏi lịch sử là giấu đi một sự cố hạ tầng. Có danh tính mà không có
    `hoi_thoai_id` thì `lich_su` client gửi được giữ nguyên (giao diện đã đăng nhập
    không gửi trường này)."""
    if user_sub is None:
        # Tài liệu luôn thuộc một tài khoản (`routes_tai_lieu` dùng
        # `nguoi_dung_bat_buoc`), nên một lượt ẩn danh mang `tai_lieu_ids` là
        # một yêu cầu không thể phục vụ — 401 nói đúng việc phải làm, còn bỏ qua
        # im lặng thì người dùng nhận một câu trả lời không nhắc gì tới tệp họ
        # vừa gửi và không hiểu vì sao.
        if req.tai_lieu_ids:
            raise HTTPException(status_code=401, detail=LOI_TAI_LIEU_DANG_NHAP)
        return req, None, None, None, [], None
    if req.hoi_thoai_id is None:
        # Tài liệu thuộc về một hội thoại ĐÃ CÓ (nó được tải lên trong hội thoại
        # đó). Một lượt mở hội thoại MỚI mà dẫn tài liệu là dẫn tài liệu của một
        # hội thoại khác — 404, không tiết lộ nó có tồn tại hay không.
        if req.tai_lieu_ids:
            raise HTTPException(status_code=404, detail=LOI_TAI_LIEU_KHONG_THAY)
        pid = await run_in_threadpool(hoi_thoai_svc.tao_phien, user_sub, req.query)
        # Pro và đang bật ghi nhớ: phiên mới kế thừa hồ sơ tài khoản (spec 2026-09-09 §6.4).
        plan = await run_in_threadpool(bao_ve.plan_hieu_luc, user_sub)
        if plan == "pro" and await run_in_threadpool(bo_nho.doc_ghi_nho, user_sub):
            ho_so = await run_in_threadpool(bo_nho.ho_so_tu_tai_khoan, user_sub)
            if ho_so:
                await run_in_threadpool(hoi_thoai_svc.ghi_ho_so, pid, ho_so)
                return req, pid, {"tom_tat": None, "ho_so": ho_so}, None, [], None
        return req, pid, None, None, [], None
    pid = str(req.hoi_thoai_id)
    if await run_in_threadpool(hoi_thoai_svc.lay_phien, user_sub, pid) is None:
        raise HTTPException(status_code=404, detail=hoi_thoai_svc.LOI_KHONG_THAY)
    plan = await run_in_threadpool(bao_ve.plan_hieu_luc, user_sub)
    tran = bao_ve.han_muc(plan, "luot_moi_phien")
    if await run_in_threadpool(hoi_thoai_svc.dem_luot, pid) >= tran:
        raise HTTPException(status_code=403, detail=hoi_thoai_svc.LOI_PHIEN_DAY.format(n=tran))
    lich_su = await run_in_threadpool(hoi_thoai_svc.lich_su_gan_nhat, pid)
    bn = await run_in_threadpool(hoi_thoai_svc.bo_nho_cua_phien, pid)
    soan_thao = await run_in_threadpool(hoi_thoai_svc.soan_thao_cua_phien, user_sub, pid)
    # `tl.tai_lieu_cua_hoi_thoai` tra qua module chứ không nhập tên: S1 đang
    # thêm hàm này trong một lát cắt chạy song song, và một `from … import` ở
    # đầu file sẽ làm cả API không khởi động được cho tới khi lát cắt đó xong.
    tai_lieu_phien = await run_in_threadpool(tl.tai_lieu_cua_hoi_thoai, get_engine(), pid, user_sub)
    co = {str(r["id"]) for r in tai_lieu_phien}
    # Một id không thuộc hội thoại NÀY là 404 kể cả khi nó thuộc chính người
    # gọi: tài liệu sống trong đúng hội thoại đã nhận nó (decision 2026-09-16),
    # nên kéo nó sang hội thoại khác là kéo dài đời nó qua một đường không ai
    # thấy được trên giao diện.
    if any(str(i) not in co for i in req.tai_lieu_ids):
        raise HTTPException(status_code=404, detail=LOI_TAI_LIEU_KHONG_THAY)
    # Phase 3 Half B (R5) — bản thảo tổng quát của CHÍNH hội thoại này, nếu có.
    # Tính một lần ở đây (không phải trong graph): `_re_sau_route` là một hàm
    # THUẦN của state, không được chạm DB, và `hieu_tai_lieu` (R4) cần cùng
    # giá trị này để biết bản thảo ĐANG CÓ khi sửa — một lượt gọi, hai nơi đọc.
    # Bản NHẸ (`ban_thao_tong_quat_dang_mo_nhe`, PostgreSQL review) — hàm này
    # chạy trên MỌI lượt hỏi có danh tính, không chỉ lượt soạn, nên kéo cả
    # `phien_ban_truoc`/`clauses`/`facts` (như `moi_nhat_cua_hoi_thoai` đầy đủ
    # vẫn làm cho `dung_ban_thao_tong_quat`) là trả giá nặng cho một phép
    # kiểm truthy cộng hai trường `document`/`audit`.
    ban_thao_tong_quat = await run_in_threadpool(
        ban_thao.ban_thao_tong_quat_dang_mo_nhe, user_sub, pid
    )
    return (
        req.model_copy(update={"lich_su": [LuotTruoc(**luot) for luot in lich_su]}),
        pid,
        {"tom_tat": bn["tom_tat"], "ho_so": bn["ho_so"]},
        soan_thao,
        tai_lieu_phien,
        ban_thao_tong_quat,
    )


async def _ghi_luot_nhe(hoi_thoai_id: str, cau_hoi: str, payload: dict, trace_id: str) -> str | None:
    """Ghi lượt vào phiên; lỗi → log + trả thông điệp cho `loi_luu`. KHÔNG nuốt im lặng,
    KHÔNG làm mất câu trả lời đã tính."""
    try:
        await run_in_threadpool(hoi_thoai_svc.ghi_luot, hoi_thoai_id, cau_hoi, payload, trace_id)
        return None
    except Exception:
        logger.exception("hoi_thoai: không ghi được lượt (phien=%s, trace=%s)", hoi_thoai_id, trace_id)
        return "Lượt này chưa lưu được vào phiên."


def _st_tu_cache(payload: dict) -> dict:
    """State tối thiểu để `_ghi_traces` ghi được dòng của một lượt CACHE HIT.

    Mọi cột chi phí/claim của dòng đó là 0 THẬT: không lượt LLM nào chạy, không
    provision nào được truy hồi, không claim nào được kiểm. `cache_hit=True`
    (caller truyền) là thứ nói ra rằng chúng là 0 vì-không-chạy, chứ không phải
    0 vì-quên-ghi — nếu không có cờ đó, chương đánh giá đọc dòng này thành "một
    lượt tra cứu không tìm được gì".
    """
    return {"result_type": payload["result_type"], "traces": {}}


# MỌI node THẬT của `build_graph_tra_cuu`, theo thứ tự của đường đi đầy đủ, kèm
# nhãn tiếng Việt cho giao diện. Đường SSE (`routes_luong.py`) phát ĐÚNG danh
# sách này; `test_tra_cuu_luong.py` khoá nó khớp với graph đã compile, để thêm
# một node mà quên cập nhật ở đây không âm thầm biến mất khỏi thanh tiến trình.
#
# `giai_nghia` chỉ chạy ở lượt hỏi NỐI TIẾP, nên ở lượt đầu thanh tiến trình
# không bao giờ phát bước này — danh sách là tập MỌI bước có thể, không phải
# tập bước của mỗi lượt (`tien_de`, `rewrite`… cũng đã vắng ở các đường rẽ tắt).
BUOC_TRA_CUU: tuple[tuple[str, str], ...] = (
    ("giai_nghia", "Giải nghĩa câu hỏi nối tiếp"),
    ("suy_dien", "Nhận ra vai của bạn"),
    ("route", "Phân loại câu hỏi"),
    ("hieu_tai_lieu", "Đọc tài liệu đính kèm"),
    ("dung_ban_thao_tong_quat", "Dựng bản thảo tổng quát"),
    ("gom_du_kien", "Gom dữ kiện cho văn bản"),
    ("dung_ban_thao", "Dựng bản thảo"),
    ("tien_de", "Kiểm tiền đề câu hỏi"),
    ("rewrite", "Viết lại truy vấn"),
    ("retrieve", "Truy hồi điều khoản"),
    ("expand", "Mở rộng dẫn chiếu"),
    ("generate", "Sinh luận điểm"),
    ("tier1", "Kiểm chứng tầng 1 — đối chiếu nguyên văn"),
    ("tier2", "Kiểm chứng tầng 2 — mô hình thẩm định"),
    ("assemble", "Dựng câu trả lời"),
)


def buoc_cua_luot(req: TraCuuRequest) -> tuple[tuple[str, str], ...]:
    """`BUOC_TRA_CUU` bỏ bước mà lượt NÀY chắc chắn không chạy.

    Chỉ có một bước như vậy: `giai_nghia` không chạy khi `lich_su` rỗng, và điều
    đó biết được TRƯỚC khi graph chạy (nhánh vào của graph quyết định bằng đúng
    phép kiểm này). Không có hàm này thì lượt đầu — tức phần lớn lượt — nhận một
    thanh tiến trình bắt đầu ở "bước 2/10" và không bao giờ có bước 1: đúng thứ
    thanh tiến trình bịa mà endpoint SSE sinh ra để thay thế.

    Các bước còn lại (`tien_de`, `rewrite`…) cũng có thể không chạy, nhưng điều
    đó chỉ biết được GIỮA đường (sau `route`, sau phép kiểm tiền đề) — dự đoán
    chúng ở đây sẽ là đoán, nên chúng ở lại danh sách.
    """
    if req.lich_su:
        return BUOC_TRA_CUU
    return tuple(b for b in BUOC_TRA_CUU if b[0] != "giai_nghia")


def chi_tiet_buoc(ten: str, st: dict) -> dict:
    """Con số đã tính được tại bước `ten`, lấy từ state — 0 phép tính thêm.

    "Truy hồi điều khoản — 10 điều khoản" là tiến trình; "Truy hồi điều khoản"
    một mình vẫn là một cái tên không nói gì về việc đã xong tới đâu.
    """
    if ten == "hieu_tai_lieu":
        return {"so_quan_sat": len((st.get("tai_lieu_ket") or {}).get("quan_sat") or [])}
    if ten == "dung_ban_thao_tong_quat":
        # Số mục ĐÃ DỰNG, không số mục mô hình soạn ra: phép làm sạch
        # (`hieu_tai_lieu.lam_sach_van_ban`) có thể đã bỏ bớt, và thanh tiến
        # trình phải nói con số người dùng sắp thấy.
        return {"so_muc": len((st.get("ban_thao_ket") or {}).get("clauses") or [])}
    if ten == "retrieve":
        return {"so_dieu_khoan": len(st.get("retrieved") or [])}
    if ten == "expand":
        return {"so_dieu_khoan": len(st.get("expanded") or [])}
    if ten == "generate":
        return {"so_luan_diem": len(st.get("draft_claims") or [])}
    if ten == "tier1":
        return {"so_luan_diem_dat": sum(1 for r in (st.get("tier1") or []) if getattr(r, "ok", False))}
    if ten == "tier2":
        return {"so_luan_diem_dat": len(st.get("tier2") or [])}
    if ten == "assemble":
        return {"so_trich_dan": len(st.get("citations") or [])}
    return {}


def _bo_qua_cache(
    req: TraCuuRequest,
    bo_nho: dict | None,
    soan_thao: dict | None,
    tai_lieu_phien: list[dict] | None,
    ban_thao_tong_quat: dict | None = None,
) -> bool:
    """Lượt này có được phép dùng `cache_tra_loi` không.

    Khoá cache dựng từ `query` MỘT MÌNH (xem `cache_tra_loi.khoa_cache`), nên
    mọi thứ khác đi vào state mà làm câu trả lời khác đi đều phải TẮT cache —
    nếu không, hai hội thoại cùng gõ một câu nhận câu trả lời của nhau. Lịch sử,
    bộ nhớ phiên và bản thảo đang mở đã thuộc diện đó; tài liệu là diện thứ tư
    và nặng nhất, vì câu trả lời khi ấy nói về TỆP của một người cụ thể.

    `ban_thao_tong_quat` (R5) cùng lý do: một hội thoại có bản thảo tổng quát
    đang mở có thể rẽ `Intent.soan_thao` sang `hieu_tai_lieu` thay vì
    `gom_du_kien` (`_re_sau_route`) — câu trả lời phụ thuộc vào việc đó, nên
    một payload cache (dựng từ `query` một mình) không được phục vụ chéo giữa
    một hội thoại đang có bản thảo và một hội thoại không có.
    """
    return bool(
        req.lich_su
        or (bo_nho and (bo_nho.get("tom_tat") or bo_nho.get("ho_so")))
        or soan_thao
        or req.tai_lieu_ids
        or tai_lieu_phien
        or ban_thao_tong_quat
    )


async def _xem_ban_thao(
    req: TraCuuRequest, user_sub: str | None, hoi_thoai_id: str | None, ban_thao_tong_quat: dict | None
) -> dict | None:
    """Lời xin XEM bản đã điền (owner 2026-09-28, Q3) → state kết quả `ban_thao` của
    bản thảo khuôn gốc mới nhất của hội thoại, TRƯỚC graph: không `giai_nghia`, không
    router, không lượt đọc tài liệu — 0 lượt mô hình, không phiên bản mới. `None` (đi
    đường thường) khi câu không phải lời xin xem, lượt đính kèm tệp mới (câu nói về
    tệp đó), hay bản thảo MỚI NHẤT của hội thoại (`ban_thao_tong_quat`, bản nhẹ) không
    nằm trên khuôn gốc — một lá đơn HTML soạn sau khi điền phiếu là bản "xem bản thảo"
    muốn thấy, và đường thường mở nó."""
    moi_nhat_la_khuon = bool((ban_thao_tong_quat or {}).get("viec_id"))
    if not (user_sub and hoi_thoai_id and moi_nhat_la_khuon) or req.tai_lieu_ids or not xin_xem_ban_thao(req.query):
        return None
    bt = await run_in_threadpool(ban_thao.moi_nhat_tren_khuon, user_sub, hoi_thoai_id=hoi_thoai_id)
    return xem_ban_thao_khuon(bt) if bt and bt.get("khuon") else None


async def chay_tra_cuu(
    req: TraCuuRequest,
    user_sub: str | None,
    trace_id: str,
    phat: Callable[[str, dict], Awaitable[None]] | None = None,
    bo_nho: dict | None = None,
    hoi_thoai_id: str | None = None,
    soan_thao: dict | None = None,
    tai_lieu_phien: list[dict] | None = None,
    ban_thao_tong_quat: dict | None = None,
) -> tuple[dict, str]:
    """Thân dùng chung của `/tra-cuu` và `/tra-cuu/luong`: cache → graph →
    ghi cache → ghi traces. Trả `(payload, config_name)`.

    `phat` — callback `(ten_buoc, chi_tiet)` gọi mỗi khi một node xong. `None`
    (đường POST) chạy `ainvoke` y NGUYÊN như trước; chỉ khi có callback mới đổi
    sang `astream`. Hai lời gọi graph thay vì một là CỐ Ý: `eval/run.py` gọi
    POST và bảng số liệu của khoá luận phụ thuộc nó, nên đường đó không được
    đổi cơ chế để phục vụ một tính năng giao diện.

    spec 8.0a. `result_type` là enum bốn giá trị (không phải cờ `abstained`
    boolean): `partial_coverage` không thể ép vào "đã trả lời"/"đã từ chối" mà
    không mất thông tin, và ABSTAIN là hành vi ĐÚNG của hệ thống — không phải
    lỗi cần che giấu bằng một cờ nhị phân.

    `user_sub` — `traces.user_sub` cần giá trị đó: hạn mức tháng đếm chính cột
    ấy, nên một lượt LLM ghi thiếu `sub` là một lượt dùng miễn phí. None khi
    Supabase chưa cấu hình (eval, dev local).

    `hoi_thoai_id`/`soan_thao` (Task 19) — phiên hiện tại và trạng thái soạn
    thảo đang mở của nó (`_chuan_bi_phien`), truyền THẲNG vào `_state_vao`
    cùng `user_sub`/`bo_nho`: cả hai đường POST và SSE gọi CHÍNH hàm này, nên
    truyền vào đây một lần là đủ cho cả hai, không phải sửa riêng từng đường.
    """
    s = get_settings()
    bat_dau = time.monotonic()
    config_name = req.config_name or s.eval_config_name
    # Mốc hiệu lực GIẢI QUYẾT ngay tại đây, một lần: cùng giá trị đi vào khoá
    # cache VÀ vào graph, nên không có cách nào cache khoá theo một ngày mà
    # graph lọc hiệu lực theo ngày khác.
    as_of = as_of_hieu_luc(req.as_of_date)
    # Khởi tạo TRƯỚC `try` để khối `finally` dưới đây luôn có thứ để ghi. Đường
    # SSE gom state theo từng node, nên khi graph nổ ở lượt LLM thứ 5 thì chi
    # phí của 4 lượt đầu VẪN nằm trong `st` — ghi lại được đúng phần đã tiêu.
    st: dict = {}
    tu_cache = False
    loi: str | None = None
    try:
        # Lời xin xem bản đã điền: một bước, đúng việc đã làm; dòng traces như cache
        # hit (`cache_hit` — không lượt mô hình nào, không trừ hạn mức).
        if (xem := await _xem_ban_thao(req, user_sub, hoi_thoai_id, ban_thao_tong_quat)) is not None:
            if phat is not None:
                await phat("xem_ban_thao", {})
            await _ghi_traces_nhe(
                trace_id,
                "/api/v1/tra-cuu",
                req.query,
                config_name,
                xem,
                int((time.monotonic() - bat_dau) * 1000),
                True,
                user_sub,
            )
            return _payload_cache(xem, xem["result_type"].value), config_name
        # Cache TRƯỚC graph. Lỗi ĐỌC cache cố ý KHÔNG được bắt riêng: nó rơi vào
        # đúng hai khối except dưới đây (OperationalError → 503). Nếu bảng cache
        # không đọc được thì Postgres đang không lành, và cả pipeline (truy hồi,
        # verify, traces) đều cần Postgres — chạy tiếp là tiêu 5 lượt LLM cho
        # một request gần như chắc chắn hỏng ở bước sau.
        #
        # `tra_cache` trả về `checksum` nó ĐÃ dùng để dựng khoá, và lượt ghi
        # dưới đây dùng lại đúng giá trị đó: tính lại sau khi graph chạy (10-60
        # giây) có thể nhận giá trị KHÁC nếu corpus vừa được seed lại giữa lúc
        # đó, và khi ấy dòng cache được ghi dưới một khoá không ai tra được —
        # một cache miss vĩnh viễn, im lặng.
        #
        # `khoa is None` = cache đã tắt; khi đó `tra_cache` không chạm DB lần
        # nào (xem docstring của nó) nên đường này không cần Postgres.
        #
        # Lượt hỏi NỐI TIẾP không đi qua cache, cả đọc lẫn ghi. `khoa_cache`
        # dựng từ `query` GỐC và không có lịch sử trong đó, nên hai hội thoại
        # khác nhau cùng gõ "liệt kê bảng cho tôi" tra CÙNG một khoá — người thứ
        # hai sẽ nhận câu trả lời của cuộc hội thoại người thứ nhất. Bỏ cache là
        # cách rẻ nhất đóng lỗ đó, và không mất gì đo được: khoá phải mang cả
        # lịch sử mới đúng, mà lịch sử đổi mỗi lượt nên tỉ lệ trúng gần 0.
        #
        # Cùng lý lẽ cho `bo_nho` (spec 2026-09-09 §6.5): một tóm tắt hay hồ sơ
        # tình huống khác đi vào state cũng làm câu trả lời có thể khác, và khoá
        # cache không mang chúng — phục vụ payload cache cho một request có bộ
        # nhớ là phục vụ câu trả lời của MỘT phiên khác cho phiên này.
        #
        # `soan_thao` (Task 19) tắt cùng lý do: một hội thoại đang soạn dở cần
        # `gom_du_kien`/`dung_ban_thao` chạy MỖI lượt (dữ kiện tích luỹ từ lượt
        # trước), và khoá cache — dựng từ `query` một mình — không phân biệt
        # được lượt này với một câu hỏi giống hệt của một phiên KHÔNG soạn gì.
        khoa, checksum, payload = (
            (None, None, None)
            if _bo_qua_cache(req, bo_nho, soan_thao, tai_lieu_phien, ban_thao_tong_quat)
            else await run_in_threadpool(cache_tra_loi.tra_cache, req.query, config_name, as_of)
        )
        tu_cache = payload is not None
        if tu_cache:
            st = _st_tu_cache(payload)
            if phat is not None:
                # Giả vờ chạy chín node cho một lượt 3ms là dựng một thanh tiến
                # trình bịa. Một bước, đúng tên việc đã làm.
                await phat("cache", {})
        elif phat is None:
            st = await _g().ainvoke(
                _state_vao(
                    req,
                    as_of,
                    trace_id,
                    bo_nho=bo_nho,
                    user_sub=user_sub,
                    hoi_thoai_id=hoi_thoai_id,
                    soan_thao=soan_thao,
                    tai_lieu_phien=tai_lieu_phien,
                    ban_thao_tong_quat=ban_thao_tong_quat,
                )
            )
        else:
            # `stream_mode="updates"` phát `{ten_node: output}`. Mọi node trong
            # `graph_tra_cuu` trả `{**st, ...}` (state ĐẦY ĐỦ), nhưng gộp bằng
            # `update` thay vì lấy chunk cuối để một node tương lai trả state
            # RIÊNG PHẦN không âm thầm xoá trắng những gì các node trước ghi.
            st = {}
            async for chunk in _g().astream(
                _state_vao(
                    req,
                    as_of,
                    trace_id,
                    bo_nho=bo_nho,
                    user_sub=user_sub,
                    hoi_thoai_id=hoi_thoai_id,
                    soan_thao=soan_thao,
                    tai_lieu_phien=tai_lieu_phien,
                    ban_thao_tong_quat=ban_thao_tong_quat,
                ),
                stream_mode="updates",
            ):
                for ten, ra in chunk.items():
                    if isinstance(ra, dict):
                        st.update(ra)
                    await phat(ten, chi_tiet_buoc(ten, st))
    except (httpx.HTTPStatusError, httpx.TransportError, OperationalError) as e:
        # Lỗi hạ tầng NHẤT THỜI, nhận diện được theo LOẠI ngoại lệ — OpenRouter
        # 429/5xx cạn retry (httpx) hoặc Postgres không kết nối được
        # (OperationalError): 503, đúng nghĩa "client NÊN thử lại". Chi tiết
        # đầy đủ vào log server (không lộ ra response — LlmClient không bao
        # giờ đưa OPENROUTER_API_KEY vào message ngoại lệ, nhưng response vẫn
        # chỉ mang TÊN loại lỗi, không mang str(e), để không mở rộng bề mặt rò
        # rỉ nếu một ngoại lệ tương lai vô tình mang theo dữ liệu nhạy cảm).
        loi = type(e).__name__
        logger.exception("tra_cuu: lỗi hạ tầng nhất thời khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=503, detail=f"tra cứu thất bại: {loi}") from e
    except Exception as e:
        # Không thuộc hai loại rõ ràng-nhất-thời ở trên — bug thật (KeyError,
        # AttributeError...) hoặc ValueError của chính LlmClient khi OpenRouter
        # trả nội dung dị dạng (content rỗng/usage thiếu, xem llm.py) — 500,
        # KHÔNG ngụ ý client nên tự ý thử lại. Giới hạn đã biết: ValueError đó
        # về BẢN CHẤT cũng là dấu hiệu OpenRouter không ổn định, nhưng llm.py
        # dùng ValueError trần (không phải exception riêng) nên không tách
        # được khỏi ValueError từ một bug thật bằng KIỂU — nâng cấp lên một
        # exception riêng nếu cần tách rạch hơn.
        loi = type(e).__name__
        logger.exception("tra_cuu: lỗi không xác định khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=500, detail=f"tra cứu thất bại: {loi}") from e
    finally:
        # Ghi TRONG `finally`, không phải sau `try`: `chay_tra_cuu` raise trước
        # khi tới lượt ghi ở dưới, nên mọi request hỏng từng biến mất khỏi sổ —
        # mà `/tra-cuu` gọi LLM tối đa 5 lần, và chế độ hỏng này kích hoạt đúng
        # lúc OpenRouter trả 429/5xx, tức đúng lúc trần chi phí ngày và hạn mức
        # tháng (cả hai ĐỌC bảng này) cần chính xác nhất.
        #
        # `result_type='loi'` là một giá trị MỚI của cột, và `dem_luot` CỐ Ý loại
        # nó khỏi phép đếm hạn mức: một lượt hỏng không phải thứ người dùng mua.
        # Dòng vẫn được ghi vì trần chi phí ngày và chương đánh giá đều cần nó —
        # `result_type` là thứ tách nó khỏi một lượt thành công ở cả hai chỗ.
        if loi is not None:
            await _ghi_traces_nhe(
                trace_id, "/api/v1/tra-cuu", req.query, config_name,
                {**st, "result_type": "loi"},
                int((time.monotonic() - bat_dau) * 1000), tu_cache, user_sub,
            )
    latency_ms = int((time.monotonic() - bat_dau) * 1000)

    if not tu_cache:
        rt = st["result_type"]
        payload = _payload_cache(st, rt.value if hasattr(rt, "value") else rt)
        if khoa is not None and payload["result_type"] in cache_tra_loi.KET_QUA_DUOC_CACHE:
            # `abstain`/`out_of_scope` KHÔNG vào cache: một lần thiếu căn cứ do
            # lỗi TẠM (OpenRouter 429 — đã xảy ra thật hôm nay) sẽ bị đóng băng
            # 7 ngày thành "không tìm thấy căn cứ". `abstain` là hành vi ĐÚNG và
            # được tính điểm, nhưng không phải thứ được phép hoá đá.
            await run_in_threadpool(
                cache_tra_loi.ghi_cache, khoa, req.query, config_name, as_of, checksum, payload
            )

    # Cache hit vẫn ghi MỘT dòng (nó vẫn là một request thật, và traces là nơi
    # đếm lưu lượng) — nhưng có cờ, để số liệu đánh giá của khoá luận không lẫn
    # lượt cache vào lượt gọi LLM thật. Cùng cờ đó giữ cho cache hit KHÔNG trừ
    # hạn mức tháng của người dùng.
    await _ghi_traces_nhe(
        trace_id, "/api/v1/tra-cuu", req.query, config_name, st, latency_ms,
        tu_cache, user_sub,
    )

    return payload, config_name


def tra_cuu_response(payload: dict, trace_id: str, config_name: str) -> TraCuuResponse:
    """`payload` của `chay_tra_cuu` → model HTTP. MỘT chỗ dựng cho cả hai đường,
    nên `/tra-cuu/luong` không thể trả một shape khác `/tra-cuu`."""
    return TraCuuResponse(
        result_type=payload["result_type"],
        answer=payload["answer"], citations=payload["citations"],
        warnings=payload["warnings"], coverage_note=payload["coverage_note"],
        # `nguon` có mặc định `[]` trong model, nên quên truyền KHÔNG gây lỗi —
        # nó chỉ làm `partial_coverage` mất đường mở văn bản, im lặng. Ca thứ BA
        # của cùng một kiểu hỏng, sau `khop_tai_id` và `doc_id`.
        nguon=payload["nguon"],
        # `.get`, KHÔNG `[...]`: một dòng `answer_cache` ghi TRƯỚC bản này không
        # có khoá này trong JSON, và một KeyError ở đây sẽ biến mọi cache hit cũ
        # thành HTTP 500 cho tới khi TTL 7 ngày trôi hết.
        cau_hoi_day_du=payload.get("cau_hoi_day_du"),
        # Cùng lý do `cau_hoi_day_du`: một dòng cache ghi TRƯỚC T4 không có
        # khoá `bang`. Pydantic tự dựng lại `list[Bang]` từ list[dict] này
        # (cùng cách `citations=payload["citations"]` dựng `list[CitationOut]`).
        bang=payload.get("bang") or [],
        # Cùng lý do `bang`: dòng cache ghi trước 2026-09-06 không có khoá này.
        documents=payload.get("documents") or [],
        soan_thao=payload.get("soan_thao"),
        # Cùng lý do `bang`/`documents`: dòng cache ghi trước bản này không có khoá.
        ho_so_da_dung=payload.get("ho_so_da_dung") or [],
        # Task 19 — cùng lý do `bang`/`documents`: không nhánh nào của chúng
        # từng vào cache (`KET_QUA_DUOC_CACHE` không có `soan_thao_hoi`/`ban_thao`),
        # nhưng `.get` vẫn đúng quy ước chung của hàm này.
        soan_thao_hoi=payload.get("soan_thao_hoi"),
        ban_thao=payload.get("ban_thao"),
        # Cùng lý do `.get` của `bang`: dòng cache ghi trước bản này không có khoá.
        tai_lieu=payload.get("tai_lieu"),
        tai_lieu_neo=payload.get("tai_lieu_neo") or [],
        # Cùng lý do `.get` của `bang`: dòng cache ghi trước bản này không có khoá.
        van_ban_khong_hien_thi=payload.get("van_ban_khong_hien_thi") or [],
        trace_id=trace_id, config_name=config_name,
    )


@router.post("/tra-cuu", response_model=TraCuuResponse)
async def tra_cuu(
    req: TraCuuRequest, response: Response, user_sub: str | None = Depends(cong_bao_ve_khach)
) -> TraCuuResponse:
    """`Depends(cong_bao_ve_khach)` — API key, danh tính, rate limit (theo `sub` khi
    đã đăng nhập, theo `khach:{id}` khi là khách, theo IP khi auth chưa cấu hình),
    hạn mức ngày/tháng của người dùng, trần chi phí ngày — chạy TRƯỚC thân hàm này. Endpoint này gọi LLM tối đa 5 lần, p95 50s,
    tới $0,00735 một request; không cổng nào ở đó là phòng xa (xem `bao_ve.py`).
    """
    trace_id = str(uuid.uuid4())
    req, hoi_thoai_id, bn, soan_thao, tai_lieu_phien, ban_thao_tong_quat = await _chuan_bi_phien(req, user_sub)
    payload, config_name = await chay_tra_cuu(
        req, user_sub, trace_id, bo_nho=bn, hoi_thoai_id=hoi_thoai_id, soan_thao=soan_thao,
        tai_lieu_phien=tai_lieu_phien, ban_thao_tong_quat=ban_thao_tong_quat,
    )
    resp = tra_cuu_response(payload, trace_id, config_name)
    if hoi_thoai_id is not None:
        response.headers["X-Hoi-Thoai-Id"] = hoi_thoai_id
        loi = await _ghi_luot_nhe(hoi_thoai_id, req.query, resp.model_dump(mode="json"), trace_id)
        if loi is None:
            try:
                # An toàn cả trên cache hit: `payload["ho_so"]` khi đó là của lượt đã cache,
                # nhưng đọc cache (dòng 350-352) đã TẮT bất cứ khi nào phiên đã có `ho_so` —
                # nên không có đường nào một cache hit ghi giả định của MỘT phiên khác vào
                # phiên này. Đổi khoá cache trong tương lai phải giữ đúng ràng buộc đó.
                await run_in_threadpool(bo_nho.luu_suy_dien, hoi_thoai_id, payload.get("ho_so") or {})
            except Exception:
                logger.exception("bo_nho: không lưu được giả định suy_dien (phien=%s)", hoi_thoai_id)
            if user_sub is not None:
                bo_nho.len_lich_cap_nhat(hoi_thoai_id, user_sub, bo_nho.loai_luot(payload))
        # Task 19 — chốt trạng thái soạn thảo của phiên SAU lượt này. Bỏ qua
        # khi ý định lượt này thật sự là `tra_cuu`: một câu hỏi luật thường hỏi
        # giữa một hội thoại đang soạn dở vẫn đi qua `gom_du_kien` (xem
        # `graph_tra_cuu._re_sau_route`), nhưng KHÔNG được phép đè lên dữ kiện
        # đã gom của bản thảo bằng một lượt lạc đề — giữ nguyên bản đang mở.
        sd = payload.get("soan_thao_dang_mo")
        if sd and payload.get("intent") != "tra_cuu":
            try:
                await run_in_threadpool(
                    hoi_thoai_svc.ghi_soan_thao,
                    user_sub,
                    hoi_thoai_id,
                    {
                        "loai": sd["loai"],
                        "facts": sd["facts"],
                        "ban_thao_id": sd.get("ban_thao_id"),
                        "so_lan_sua": sd.get("so_lan_sua", 0),
                    },
                )
            except Exception:
                logger.exception("hoi_thoai: không ghi được soan_thao_dang_mo (phien=%s)", hoi_thoai_id)
    return resp


@router.get("/status")
async def agent_status():
    """Kiểm tra trạng thái agent."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}


# ══ GET /van-ban/{doc_id} (Task 7, step 2) — ba dạng LAZY ═══════════════════
# BLDS (doc_id 95942) có 689 Điều — không dạng nào dưới đây được kéo cả cây.
# `so_dieu` là `str`, KHÔNG PHẢI `int`: số hiệu Điều trong luật VN không liên
# tục và có dạng "27a" (Bộ luật khác trong corpus dùng dạng này). "2 Điều
# trước/sau" của `around` được tính theo THỨ TỰ TRONG CÂY (`thu_tu`), KHÔNG
# PHẢI phép toán số học trên `so_hieu_cap` — cùng lý do.

# KHÔNG chọn `tinh_trang`, dù nó nằm cùng dòng: một cột không được đọc thì
# không có đường nào rò ra response. Hiệu lực đi qua
# `GET /van-ban/{doc_id}/hieu-luc` (routes_van_ban.py), chỗ duy nhất
# `effectivity.py` chạy.
_SQL_VAN_BAN_DOC = text(
    "SELECT so_ky_hieu, ten, loai_van_ban, co_quan_ban_hanh, ngay_ban_hanh,"
    " ngay_hieu_luc, ngay_het_hieu_luc, nguoi_ky, chuc_danh_nguoi_ky, link_vbpl, link_chinhphu"
    " FROM documents WHERE id = :doc_id"
)


def _meta(doc_id: str, doc) -> dict:
    """Metadata dùng chung cho CẢ BA dạng lazy (`VanBanMetaMixin`).

    Một chỗ duy nhất dựng bộ trường này: ba lời gọi constructor riêng lẻ đã
    từng lệch nhau ở `nguon`/`khop_tai_id`/`doc_id` — ba lần, cùng một kiểu
    hỏng, mỗi lần là một trường im lặng biến mất ở đúng một nhánh.
    """
    # `ten_van_ban`/`lien_ket`/`cach_trich` (quyết định 2026-09-28); các trường
    # trùng tên của `truong_trich_dan` bị đè bằng đúng giá trị cột bên dưới.
    return {
        **truong_trich_dan(dict(doc)),
        "doc_id": doc_id, "so_ky_hieu": doc["so_ky_hieu"], "bo_luat": doc["ten"],
        "loai_van_ban": doc["loai_van_ban"], "co_quan_ban_hanh": doc["co_quan_ban_hanh"],
        "ngay_ban_hanh": doc["ngay_ban_hanh"], "ngay_hieu_luc": doc["ngay_hieu_luc"],
        "ngay_het_hieu_luc": doc["ngay_het_hieu_luc"],
        "nguoi_ky": doc["nguoi_ky"], "chuc_danh_nguoi_ky": doc["chuc_danh_nguoi_ky"],
    }

_SQL_VAN_BAN_MUC_LUC = text(
    "SELECT id, cap, so_hieu_cap, tieu_de, thu_tu FROM provisions"
    " WHERE document_id = :doc_id AND cap IN ('phan', 'chuong', 'muc', 'tieu_muc')"
    " ORDER BY thu_tu"
)

# Dự phòng cho 11/47 văn bản KHÔNG có Chương/Mục nào (đo 2026-09-01: nhiều
# nhất 10 Điều, trung bình 5,8 — trong đó có cả sáu nghị định lương tối thiểu).
# Với chúng, `_SQL_VAN_BAN_MUC_LUC` trả rỗng và người mở thấy một trang trắng.
# Cấu trúc duyệt được của một văn bản phẳng CHÍNH LÀ danh sách Điều của nó, nên
# trả đúng thứ đó — cùng năm cột, cùng `MucLucItem`, client không phải học gì mới.
_SQL_VAN_BAN_DIEU_PHANG = text(
    "SELECT id, cap, so_hieu_cap, tieu_de, thu_tu FROM provisions"
    " WHERE document_id = :doc_id AND cap = 'dieu'"
    " ORDER BY thu_tu"
)

_SQL_VAN_BAN_DIEU_BY_SO_HIEU = text(
    "SELECT id FROM provisions WHERE document_id = :doc_id AND cap = 'dieu' AND so_hieu_cap = :so_dieu"
)

_SQL_VAN_BAN_PROVISION_GOC = text("SELECT document_id, cap FROM provisions WHERE id = :pid")

# Đi NGƯỢC `parent_id` tới Điều cha gần nhất — CTE đệ quy (không phải một hop
# cố định) vì đo được cả hai cấu trúc thật trong corpus: Điểm có thể là con
# TRỰC TIẾP của Điều (10 dòng) hoặc con của Khoản (6.969 dòng). `UNION` (không
# `UNION ALL`) khử trùng nên một `parent_id` vòng (nếu có) không chạy vô hạn —
# cùng lý do `verify_tier1._SQL_CAY` đã dùng UNION cho đường đi XUÔI.
_SQL_VAN_BAN_DIEU_CHA = text(
    "WITH RECURSIVE nguoc AS ("
    "  SELECT id, parent_id, cap FROM provisions WHERE id = :pid"
    "  UNION"
    "  SELECT p.id, p.parent_id, p.cap FROM provisions p JOIN nguoc ON p.id = nguoc.parent_id"
    ") SELECT id FROM nguoc WHERE cap = 'dieu' LIMIT 1"
)

_SQL_VAN_BAN_DIEU_TRUOC = text(
    "SELECT id FROM provisions WHERE document_id = :doc_id AND cap = 'dieu'"
    " AND thu_tu < (SELECT thu_tu FROM provisions WHERE id = :dieu_id)"
    " ORDER BY thu_tu DESC LIMIT 2"
)
_SQL_VAN_BAN_DIEU_SAU = text(
    "SELECT id FROM provisions WHERE document_id = :doc_id AND cap = 'dieu'"
    " AND thu_tu > (SELECT thu_tu FROM provisions WHERE id = :dieu_id)"
    " ORDER BY thu_tu ASC LIMIT 2"
)

# Một Điều + TOÀN BỘ hậu duệ. ĐỆ QUY, không phải hai tầng cứng: từ khi có cấp
# `hang_bang` (migrations/017) cây sâu tới `Điều > Khoản > Điểm > hàng bảng`, và
# một truy vấn hai tầng sẽ IM LẶNG bỏ rơi các hàng của một bảng nằm trong Điểm.
# Hôm nay chưa có bảng nào ở đó, nhưng "chưa có" là thứ đổi theo văn bản mới,
# còn cách hỏng thì không ai thấy: trang đọc văn bản chỉ thiếu vài dòng.
# Cùng khuôn `WITH RECURSIVE` mà `_SQL_DIEU_TRONG_CHUONG` ngay dưới đã dùng.
_SQL_VAN_BAN_CAY_DIEU = text(
    "WITH RECURSIVE cay AS ("
    "  SELECT id FROM provisions WHERE id = :dieu_id"
    "  UNION ALL"
    "  SELECT p.id FROM provisions p JOIN cay ON p.parent_id = cay.id"
    ")"
    " SELECT p.id, p.cap, p.so_hieu_cap, p.parent_id, p.duong_dan, p.tieu_de,"
    "        p.noi_dung"
    " FROM provisions p JOIN cay ON cay.id = p.id"
    " ORDER BY p.thu_tu"
)


_SQL_DIEU_TRONG_CHUONG = text(
    "WITH RECURSIVE cay AS ("
    "  SELECT id, cap, document_id FROM provisions WHERE id = :goc"
    "  UNION ALL"
    "  SELECT p.id, p.cap, p.document_id FROM provisions p JOIN cay ON p.parent_id = cay.id"
    ")"
    " SELECT p.id, p.cap, p.so_hieu_cap, p.parent_id, p.duong_dan, p.tieu_de,"
    "        p.noi_dung"
    " FROM provisions p JOIN cay ON cay.id = p.id"
    " WHERE p.cap = 'dieu' ORDER BY p.thu_tu"
)

_CAP_CHUA_DIEU = ("phan", "chuong", "muc", "tieu_muc")


def _van_ban_sync(
    doc_id: str, so_dieu: str | None, around: int | None, trong_chuong: int | None = None
) -> VanBanMucLucResponse | VanBanProvisionsResponse:
    """Thân đồng bộ (SQLAlchemy sync) của GET /van-ban/{doc_id} — route PHẢI
    gọi qua `run_in_threadpool` (xem `_ghi_traces` ở trên: thiếu bọc này đã
    từng là một lỗi thật trong dự án). `HTTPException` raise ở đây vẫn nổ
    đúng qua threadpool tới route.

    Văn bản bị ẩn (`services/hien_thi`) trả 404 `khong_hien_thi` ở MỌI dạng,
    trước cả truy vấn đầu tiên của trang.
    """
    chan_neu_an(get_engine(), doc_id, as_of_hieu_luc(None))
    with get_engine().connect() as conn:
        doc = conn.execute(_SQL_VAN_BAN_DOC, {"doc_id": doc_id}).mappings().one_or_none()
        if doc is None:
            raise HTTPException(status_code=404, detail=f"văn bản '{doc_id}' không tồn tại")

        if trong_chuong is not None:
            goc = conn.execute(
                _SQL_VAN_BAN_PROVISION_GOC, {"pid": trong_chuong}
            ).mappings().one_or_none()
            if goc is None or goc["document_id"] != doc_id:
                raise HTTPException(status_code=404, detail=(
                    f"provision {trong_chuong} không thuộc văn bản '{doc_id}'"
                ))
            if goc["cap"] not in _CAP_CHUA_DIEU:
                # Nói thẳng thay vì trả rỗng: một danh sách rỗng ở đây không
                # phân biệt được "Chương này không có Điều nào" với "bạn đưa
                # nhầm id của một Điều".
                raise HTTPException(status_code=422, detail=(
                    f"provision {trong_chuong} có cap='{goc['cap']}' — trong_chuong chỉ nhận "
                    f"cấp chứa Điều: {', '.join(_CAP_CHUA_DIEU)}"
                ))
            rows = conn.execute(_SQL_DIEU_TRONG_CHUONG, {"goc": trong_chuong}).mappings().all()
            return VanBanProvisionsResponse(
                **_meta(doc_id, doc),
                # `la_tam=False` cho tất cả: đang DUYỆT mục lục, chưa chọn Điều
                # nào làm tâm. Đánh dấu bừa một Điều là tâm sẽ rọi sáng nhầm.
                provisions=[ProvisionOut(**dict(r), la_tam=False) for r in rows],
            )

        if so_dieu is None and around is None:
            rows = conn.execute(_SQL_VAN_BAN_MUC_LUC, {"doc_id": doc_id}).mappings().all()
            if not rows:
                # Truy vấn thứ hai CHỈ chạy khi truy vấn đầu không ra gì, nên
                # 36/47 văn bản có Chương không trả thêm đồng nào. Văn bản tầng
                # metadata (0 điều khoản) vẫn đúng: cả hai đều rỗng.
                rows = conn.execute(_SQL_VAN_BAN_DIEU_PHANG, {"doc_id": doc_id}).mappings().all()
            muc_luc = [MucLucItem(**dict(r)) for r in rows]
            return VanBanMucLucResponse(**_meta(doc_id, doc), muc_luc=muc_luc)

        if so_dieu is not None:
            tam_id = conn.execute(
                _SQL_VAN_BAN_DIEU_BY_SO_HIEU, {"doc_id": doc_id, "so_dieu": so_dieu}
            ).scalar_one_or_none()
            if tam_id is None:
                raise HTTPException(
                    status_code=404, detail=f"Điều {so_dieu} không tồn tại trong văn bản '{doc_id}'"
                )
            dieu_ids = [tam_id]
        else:
            goc = conn.execute(_SQL_VAN_BAN_PROVISION_GOC, {"pid": around}).mappings().one_or_none()
            if goc is None or goc["document_id"] != doc_id:
                # KHÔNG âm thầm trả rỗng — around trỏ sang provision của một
                # văn bản khác (hoặc không tồn tại) là lỗi của caller, phải nổ.
                raise HTTPException(
                    status_code=404, detail=f"provision {around} không thuộc văn bản '{doc_id}'"
                )
            if goc["cap"] == "dieu":
                tam_id = around
            else:
                tam_id = conn.execute(_SQL_VAN_BAN_DIEU_CHA, {"pid": around}).scalar_one_or_none()
                if tam_id is None:
                    raise HTTPException(
                        status_code=404, detail=f"provision {around} không thuộc Điều nào"
                    )
            truoc = conn.execute(
                _SQL_VAN_BAN_DIEU_TRUOC, {"doc_id": doc_id, "dieu_id": tam_id}
            ).scalars().all()
            sau = conn.execute(
                _SQL_VAN_BAN_DIEU_SAU, {"doc_id": doc_id, "dieu_id": tam_id}
            ).scalars().all()
            dieu_ids = [*reversed(truoc), tam_id, *sau]

        provisions: list[ProvisionOut] = []
        for dieu_id in dieu_ids:
            rows = conn.execute(_SQL_VAN_BAN_CAY_DIEU, {"dieu_id": dieu_id}).mappings().all()
            provisions.extend(ProvisionOut(**dict(r), la_tam=(dieu_id == tam_id)) for r in rows)

        return VanBanProvisionsResponse(**_meta(doc_id, doc), provisions=provisions)


# `cap <> 'mo_dau'`: đếm điều khoản TRÍCH DẪN ĐƯỢC, không đếm số dòng trong bảng.
# `migrations/016_tang_nong.sql` chèn cho MỌI văn bản không-metadata đúng một hàng
# `cap='mo_dau'` mang tên văn bản — 125 hàng, đúng bằng 49 (deep) + 76 (shallow).
# Hàng đó không phải một điều khoản: nó không có nội dung để dẫn.
#
# `count(...) FILTER` trên LEFT JOIN: văn bản không có provision nào cho `p.cap`
# NULL, `NULL <> 'mo_dau'` ra NULL, không được đếm — ra 0, đúng ý.
#
# `d.id = ANY(:hien)` (quyết định 2026-09-28 mục 8): kích thước kho người đọc
# thấy là số văn bản được HIỆN, không phải số dòng trong bảng.
_SQL_PHAM_VI = text(
    "SELECT d.id, d.so_ky_hieu, d.ten, d.loai_van_ban, d.tinh_trang,"
    "       count(p.id) FILTER (WHERE p.cap <> 'mo_dau')::int AS so_dieu_khoan"
    " FROM documents d LEFT JOIN provisions p ON p.document_id = d.id"
    " WHERE d.id = ANY(CAST(:hien AS text[]))"
    " GROUP BY d.id, d.so_ky_hieu, d.ten, d.loai_van_ban, d.tinh_trang"
    " ORDER BY count(p.id) FILTER (WHERE p.cap <> 'mo_dau') DESC, d.so_ky_hieu"
)


def _pham_vi() -> PhamViResponse:
    hien = hien_thi_luc(get_engine(), as_of_hieu_luc(None))
    with get_engine().connect() as c:
        rows = c.execute(_SQL_PHAM_VI, {"hien": list(hien)}).mappings().all()

    def ra(r) -> VanBanPhamViOut:
        return VanBanPhamViOut(
            doc_id=r["id"], so_ky_hieu=r["so_ky_hieu"], bo_luat=r["ten"] or "",
            loai_van_ban=r["loai_van_ban"] or "", so_dieu_khoan=r["so_dieu_khoan"],
            tinh_trang_moj=r["tinh_trang"],
        )

    # Phân tầng theo SỐ ĐIỀU KHOẢN THẬT, không theo cột `depth`: `depth` là ý
    # định lúc thu thập, còn số điều khoản là kết quả. Nếu một văn bản đánh
    # dấu 'deep' mà nạp hỏng thì nó thuộc tầng nông trên thực tế, và trang
    # phạm vi phải nói ra thực tế đó.
    #
    # ĐO ĐƯỢC 2026-09-02: nguyên tắc trên đúng, nhưng phép đo của nó đã bị
    # `migrations/016_tang_nong.sql` phá — 016 chèn một hàng `mo_dau` cho MỌI văn
    # bản không-metadata, nên `count(p.id) > 0` thành đúng cho cả hai tầng và
    # trang xếp **125** văn bản vào tầng "có toàn văn" khi thật ra chỉ **49**.
    # Phóng đại độ phủ 2,5 lần, trên đúng con số đưa cho khách xem.
    #
    # `_SQL_PHAM_VI` nay đếm điều khoản trích dẫn được (loại `mo_dau`), nên
    # nguyên tắc gốc còn nguyên: một văn bản `deep` nạp hỏng vẫn ra 0 và vẫn rơi
    # vào tầng nông. Chỉ phép đo được sửa, không phải quy tắc.
    sau = [ra(r) for r in rows if r["so_dieu_khoan"] > 0]
    nong = [ra(r) for r in rows if r["so_dieu_khoan"] == 0]
    return PhamViResponse(
        sau=TangPhamViOut(so_van_ban=len(sau), so_dieu_khoan=sum(v.so_dieu_khoan for v in sau), van_ban=sau),
        nong=TangPhamViOut(so_van_ban=len(nong), so_dieu_khoan=0, van_ban=nong),
    )


@router.get("/pham-vi", response_model=PhamViResponse)
async def pham_vi() -> PhamViResponse:
    """Phạm vi corpus, đếm từ DB — trang /pham-vi không được viết cứng con số.

    Hai tầng vì corpus thật có hai tầng: `sau` có toàn văn (ra `answer`),
    `nong` chỉ metadata và CHÍNH LÀ thứ sinh ra `partial_coverage`.
    """
    return await run_in_threadpool(_pham_vi)


@router.get("/van-ban/{doc_id}", response_model=VanBanMucLucResponse | VanBanProvisionsResponse)
async def van_ban(
    doc_id: str,
    so_dieu: str | None = None,
    around: int | None = None,
    trong_chuong: int | None = None,
) -> VanBanMucLucResponse | VanBanProvisionsResponse:
    """Lazy — BLDS 689 điều, không trả cả cây (fe-contract.md).

    không tham số → metadata + danh mục Chương/Mục
    ?so_dieu=25   → một Điều + Khoản/Điểm con
    ?around=<pid> → Điều chứa provision đó + 2 Điều trước/sau, mỗi Điều kèm
                    con của nó (dạng FE dùng nhiều nhất — click-to-verify).
                    `pid` thường là id của một Khoản (`khop_tai_id`), không
                    phải Điều — 73,6% số Điều chỉ có tiêu đề (verify_tier1).
    ?trong_chuong=<pid> → TIÊU ĐỀ các Điều của Chương/Mục đó, KHÔNG kèm
                    Khoản/Điểm. Chương lớn nhất corpus có 156 Điều nhưng 1231
                    dòng hậu duệ — kéo cả cây là phá đúng nguyên tắc lazy mà
                    endpoint này sinh ra để giữ.
    """
    da_chon = [t for t in (so_dieu, around, trong_chuong) if t is not None]
    if len(da_chon) > 1:
        raise HTTPException(
            status_code=422,
            detail="chỉ được chọn MỘT trong ba: so_dieu, around, trong_chuong",
        )
    return await run_in_threadpool(_van_ban_sync, doc_id, so_dieu, around, trong_chuong)


# ══ POST /soan-thao, POST /soat, GET /mau/{loai} (Task 5) ═══════════════════

_graph_soan_thao = None


def _g_soan_thao():
    global _graph_soan_thao
    if _graph_soan_thao is None:
        _graph_soan_thao = build_graph_soan_thao()
    return _graph_soan_thao


def _tu_choi_neu_chua_ho_tro(loai_van_ban: str) -> None:
    if loai_van_ban not in cac_loai():
        raise HTTPException(status_code=501, detail=(
            f"loai_van_ban='{loai_van_ban}' chưa có checklist/rules riêng "
            f"(hiện chỉ hỗ trợ: {sorted(cac_loai())})"
        ))


def _validate_facts(facts: dict, rules: list[Rule]) -> None:
    """Chặn TẠI BIÊN giá trị fact CÓ MẶT nhưng SAI (vd. vung='V') — rule
    engine không phải validator và sẽ không sửa (ràng buộc #1): một giá trị lạ
    dùng làm khoá `bang[khoa]` trong `kiem:` ném KeyError, thành HTTP 500 nếu
    lọt qua đây. `enum_facts` suy tập giá trị hợp lệ THẲNG từ rules.yaml —
    không danh sách tay nào lệch được khỏi rule thật.

    Fact VẮNG MẶT không đi qua đây — đó là "không kiểm được" (`None`), một kết
    quả HỢP LỆ rules.py đã tự xử lý, không phải input sai cần 422.
    """
    trung = sorted(set(facts) & ten_tham_so(rules))
    if trung:
        raise HTTPException(status_code=422, detail=(
            f"facts chứa khoá trùng tên tham số của rule: {trung}. "
            "Tham số rule là dữ liệu của hệ thống, không nhận từ request."
        ))
    for key, allowed in enum_facts(rules).items():
        if key in facts and facts[key] not in allowed:
            raise HTTPException(status_code=422, detail=(
                f"facts.{key} không hợp lệ: {facts[key]!r} — giá trị hợp lệ: {allowed}"
            ))


def _duong_dan_index(db_provisions: dict[int, dict]) -> dict[str, dict]:
    """duong_dan -> dòng provisions — tra ngược `AuditFinding.can_cu`
    (`{"duong_dan": ...}`) thành `(doc_id, khop_tai_id)` cho `FindingOut`
    (ràng buộc #3). Mọi can_cu của rule/checklist ĐÃ được xác nhận tồn tại
    trong DB (test tích hợp Task 2/3) và nằm trong `db_provisions` (đây chính
    là tập `retrieve_requirements` tra về) nên tra luôn ra id thật.
    """
    return {row["duong_dan"]: row for row in db_provisions.values()}


def _finding_out(f, duong_dan_index: dict[str, dict]) -> dict:
    duong_dan = (f.can_cu or {}).get("duong_dan")
    khop = duong_dan_index.get(duong_dan) if duong_dan else None
    return {
        "loai": f.loai,
        "muc_do": f.muc_do,
        "thong_diep": f.mo_ta,
        "dieu_khoan_lien_quan": f.dieu_khoan_lien_quan,
        # Chỉ mục chỉ gồm điều khoản của văn bản được hiện: căn cứ vắng mặt ở đó
        # là căn cứ của văn bản ẩn — không nêu (quyết định 2026-09-28 mục 8).
        "can_cu": duong_dan if khop else None,
        "rule_id": f.rule_id,
        # None cho citation_khong_hop_le: chính can_cu đó không tồn tại, nên
        # không có gì để panel đối chiếu mở.
        "doc_id": khop["document_id"] if khop else None,
        "khop_tai_id": khop["id"] if khop else None,
        "khong_kiem_duoc": getattr(f, "khong_kiem_duoc", False),
    }


def _audit_report_out(r, duong_dan_index: dict[str, dict]) -> AuditReportOut:
    return AuditReportOut(
        dat=r.dat,
        completeness=r.completeness,
        so_dieu_khoan=r.so_dieu_khoan,
        self_audit=r.self_audit,
        findings=[_finding_out(f, duong_dan_index) for f in r.findings],
    )


@router.post("/soan-thao", response_model=SoanThaoResponse)
async def soan_thao(
    req: SoanThaoRequest, user_sub: str | None = Depends(cong_bao_ve)
) -> SoanThaoResponse:
    """collect → retrieve_requirements → draft_generate → draft_audit
    (`build_graph_soan_thao`). `self_audit=True` luôn đúng ở đây — draft_generate
    CHỈ được gọi trên đường sinh của hệ thống (xem docstring node đó).

    `Depends(cong_bao_ve)`, KHÔNG phải bản `_khach` của `/tra-cuu`: endpoint này
    cũng tốn một lượt LLM thật (`draft_generate`), nhưng một bản thảo phải thuộc
    về một tài khoản để người ta còn mở lại được nó — khách chưa đăng nhập nhận
    401 ở đây thay vì một cửa sổ thử. CỐ Ý không cache — output là một văn bản soạn
    theo `facts` cụ thể của một quan hệ lao động cụ thể, tức khoá cache sẽ là
    chính khối facts đó (tên, lương, thời hạn…), và cache nó là lưu dữ liệu cá
    nhân thêm một chỗ nữa để đổi lấy một tỉ lệ hit gần như bằng không.
    """
    _tu_choi_neu_chua_ho_tro(req.loai_van_ban)
    _validate_facts(req.facts, rules_cho(req.loai_van_ban))

    trace_id = str(uuid.uuid4())
    bat_dau = time.monotonic()
    config_name = req.config_name or get_settings().eval_config_name
    st: dict = {}
    loi: str | None = None
    try:
        st = await _g_soan_thao().ainvoke(
            {"loai": req.loai_van_ban, "loai_van_ban": req.loai_van_ban,
             "facts": req.facts, "nganh": req.nganh}
        )
    except KhongSoanDuocError as e:
        # Dừng trước lượt LLM (căn cứ gốc thuộc văn bản ẩn): lời thường, 4xx để
        # giao diện hiện `detail`; không chi phí nào để ghi.
        raise HTTPException(status_code=422, detail=str(e)) from e
    except (httpx.HTTPStatusError, httpx.TransportError, OperationalError) as e:
        # Cùng phân loại lỗi hạ tầng nhất thời như tra_cuu() — xem docstring ở đó.
        loi = type(e).__name__
        logger.exception("soan_thao: lỗi hạ tầng nhất thời khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=503, detail=f"soạn thảo thất bại: {loi}") from e
    except Exception as e:
        loi = type(e).__name__
        logger.exception("soan_thao: lỗi không xác định khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=500, detail=f"soạn thảo thất bại: {loi}") from e
    finally:
        # Cùng lý lẽ với `chay_tra_cuu`: `/soan-thao` cũng tốn một lượt LLM thật
        # (`draft_generate`), nên một request hỏng cũng không được là một
        # request miễn phí. Xem khối `finally` ở đó cho lý do đầy đủ.
        if loi is not None:
            await _ghi_traces_nhe(
                trace_id, "/api/v1/soan-thao", req.loai_van_ban, config_name,
                {**st, "result_type": "loi"},
                int((time.monotonic() - bat_dau) * 1000), False, user_sub,
            )
    latency_ms = int((time.monotonic() - bat_dau) * 1000)

    # `cache_hit=False` LUÔN đúng ở đây — `/soan-thao` cố ý không cache. Truyền
    # tường minh vì `user_sub` là tham số sau nó, và hạn mức tháng đếm cả hai cột.
    await _ghi_traces_nhe(
        trace_id, "/api/v1/soan-thao", req.loai_van_ban, config_name, st, latency_ms,
        False, user_sub,
    )

    ket = ban_thao.tu_state_soan_thao(st)
    return SoanThaoResponse(**ket, trace_id=trace_id)


@router.post("/soat", response_model=SoatResponse)
async def soat(req: SoatRequest, _=Depends(cong_nhe)) -> SoatResponse:
    """Soát văn bản NGƯỜI DÙNG dán vào — tách `clauses` bằng từ khoá
    (`extract_clauses`, KHÔNG LLM), rồi chạy CHÍNH rule engine đã soát output
    của draft_generate (`draft_audit`). `self_audit=False` luôn đúng ở đây.
    """
    _tu_choi_neu_chua_ho_tro(req.loai_van_ban)
    rules, checklist, db_provisions = requirements(req.loai_van_ban)
    _validate_facts(req.facts, rules)

    trace_id = str(uuid.uuid4())
    bat_dau = time.monotonic()
    # Đồng bộ và có thể tốn CPU trên văn bản dài. KHÔNG phải node LangGraph nên
    # không được tự đẩy sang threadpool như các node trong graph — thiếu bọc này
    # là chặn event loop cho mọi request khác.
    def _soat_dong_bo():
        clauses = extract_clauses(req.text, checklist, db_provisions)
        return draft_audit(
            {"clauses": clauses, "facts": req.facts, "nganh": req.nganh, "self_audit": False},
            rules, checklist, db_provisions,
        )

    st = await run_in_threadpool(_soat_dong_bo)
    latency_ms = int((time.monotonic() - bat_dau) * 1000)

    config_name = get_settings().eval_config_name
    try:
        # `dau_van_ban(...)`, KHÔNG `req.text`: tài liệu người dùng dán vào
        # thường chứa dữ liệu cá nhân của NGƯỜI THỨ BA (người lao động có tên
        # trong hợp đồng) — người chưa từng dùng KLAW và chưa đồng ý gì cả. Dấu
        # (hash + độ dài + số clause) đủ cho mọi số liệu mà không giữ nội dung.
        # Xem docstring `dau_van_ban`; `/tra-cuu` cố ý GIỮ nguyên văn `query`,
        # vì ở đó đó là câu hỏi ngắn của chính người dùng và eval cần nó.
        await run_in_threadpool(
            _ghi_traces, trace_id, "/api/v1/soat",
            dau_van_ban(req.text, len(st.get("clauses") or [])),
            config_name, st, latency_ms,
        )
    except Exception:
        logger.exception("soat: ghi traces thất bại (trace_id=%s) — KHÔNG chặn response", trace_id)

    # Link căn cứ của finding chỉ trỏ văn bản được hiện (`services/hien_thi`);
    # phép soát vẫn chạy trên đủ tập điều khoản của checklist.
    hien = await run_in_threadpool(hien_thi_luc, get_engine(), as_of_hieu_luc(None))
    return SoatResponse(
        audit_report=_audit_report_out(st["audit_report"], _duong_dan_index(chi_van_ban_hien(db_provisions, hien))),
        trace_id=trace_id,
    )


@router.get("/mau/{loai}", response_model=MauResponse)
async def mau(loai: LoaiVanBan) -> MauResponse:
    """Mô tả các fact cần nhập cho `loai` — sinh TỪ config/rules.yaml
    (`rules.mo_ta_facts`), không hardcode danh sách trường trong Python (ràng
    buộc #4): frontend dựng form theo đây, sửa YAML là đủ khi rule đổi.

    Chỉ trả fact của những rule mà CHECKLIST CỦA CHÍNH LOẠI NÀY khai báo
    (`rules_cho`): hỏi `vung`/`luong_thang` cho một hợp đồng vay tài sản là hỏi
    người dùng dữ liệu của một chế định khác, và câu trả lời của họ sẽ được đem
    đi kiểm bằng một rule không áp dụng cho văn bản họ đang soạn.

    Loại chưa có `config/checklist_<loai>.yaml` trả `facts: []` — tái dùng nhầm
    fact của HĐLĐ sẽ sai loại văn bản.
    """
    if loai not in cac_loai():
        return MauResponse(loai_van_ban=loai, ho_tro=False, facts=[], cau_truc=None)
    facts = [FactFieldOut(**f) for f in mo_ta_facts(rules_cho(loai), load_facts_meta_cached())]
    return MauResponse(
        loai_van_ban=loai, ho_tro=True, facts=facts,
        cau_truc=_cau_truc_mau(load_checklist_cached(loai), bool(facts)),
    )


def _khung_hop_dong(cl: Checklist) -> list[MucMauOut] | None:
    """Khối các bên + chỗ ký, CHỈ những khối checklist chưa tự có.

    `hop_dong_hop_tac` là ca thật: BLDS Đ505.2 liệt kê "họ, tên, nơi cư trú của
    cá nhân; tên, trụ sở của pháp nhân" là NỘI DUNG CHỦ YẾU, nên nó đã có mục
    `cac_ben` riêng — nằm TRONG mẫu số completeness và dẫn điều luật RIÊNG của
    chế định hợp tác. Phát thêm khối Đ385 chung cho nó sẽ vẽ mục "các bên" hai
    lần, một lần được tính vào tỷ lệ và một lần không.
    Mục của checklist THẮNG: nó cụ thể hơn và nó là thứ `/soat` thật sự đếm.

    Đánh số RIÊNG từ 1 và tách khỏi `muc`: đây là khối trình bày bao quanh văn
    bản, không phải mục nội dung thứ n. `bat_buoc=True` vì Đ400.4 làm chữ ký
    thành điều kiện GIAO KẾT — hợp đồng bằng văn bản chưa ký thì chưa tồn tại,
    không phải "thiếu một mục".
    """
    if not cl.la_hop_dong:
        return None
    da_co = {m["key"] for m in cl.muc}
    con_lai = [k for k in KHUNG_HOP_DONG if k["key"] not in da_co]
    return [MucMauOut(stt=i, bat_buoc=True, **k) for i, k in enumerate(con_lai, 1)] or None


def _cau_truc_mau(cl: Checklist, co_rule: bool) -> CauTrucMauOut:
    """Checklist → cấu trúc cho frontend. ĐỌC THẲNG từ đối tượng checklist đã
    nạp; không có bản mô tả thứ hai nào để lệch.

    Vì sao khoá này phải tồn tại: frontend dựng bản xem trước TỨC THỜI khi
    người dùng gõ, nên nó không thể gọi `/soan-thao` (một lượt LLM mỗi phím).
    Trước khi có `cau_truc`, thứ duy nhất nó nhận được là `facts` và `ho_tro` —
    không đủ để biết văn bản gồm những mục nào, nên nó phải ĐOÁN, và cái nó
    đoán là khuôn hợp đồng thương mại hai bên cho MỌI loại. Đó là cách một công
    văn mọc ra "BÊN A / BÊN B / Mã số thuế / Điều 4. Phạt vi phạm hợp đồng".
    """
    khong_bat_buoc = set(cl.khong_bat_buoc.get("keys") or ())
    return CauTrucMauOut(
        ten=cl.ten,
        tieu_de=cl.tieu_de,
        don_vi_muc=cl.don_vi_muc,
        muc_do_thieu=cl.muc_do_thieu,
        pham_vi_soat=cl.pham_vi_soat,
        # `co_rule` suy từ chính `facts` vừa dựng ở trên chứ không đọc lại
        # `cl.rules`: `facts` là thứ bên gọi THẤY, nên cờ này luôn nhất quán với
        # đáp ứng thay vì với một trường thứ hai họ không nhìn thấy.
        chi_soat_the_thuc=(cl.pham_vi_soat == "the_thuc" and not co_rule),
        la_hop_dong=cl.la_hop_dong,
        # Đánh số RIÊNG từ 1 và tách khỏi `muc`: đây là khối trình bày bao quanh
        # văn bản, không phải mục nội dung thứ n. `bat_buoc=True` vì Đ400.4 làm
        # chữ ký thành điều kiện GIAO KẾT — hợp đồng bằng văn bản chưa ký thì
        # chưa tồn tại, không phải "thiếu một mục".
        khung_hop_dong=_khung_hop_dong(cl),
        can_cu_goc=cl.can_cu_goc,
        can_cu_chi_tiet=cl.can_cu_chi_tiet,
        muc=[
            MucMauOut(
                stt=m.get("stt", i),
                key=m["key"],
                ten=m["ten"],
                can_cu=m["can_cu"],
                bat_buoc=m["key"] not in khong_bat_buoc,
            )
            for i, m in enumerate(cl.muc, 1)
        ],
    )
