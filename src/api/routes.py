import dataclasses
import logging
import time
import uuid

import httpx
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from starlette.concurrency import run_in_threadpool

from src.agents.graph_soan_thao import (
    build_graph_soan_thao,
    extract_clauses,
    load_facts_meta_cached,
    load_rules_cached,
    requirements,
)
from src.agents.graph_tra_cuu import build_graph_tra_cuu
from src.agents.nodes.draft_audit import draft_audit
from src.config import get_settings
from src.models.schemas import (
    PhamViResponse,
    TangPhamViOut,
    VanBanPhamViOut,
    AuditReportOut,
    FactFieldOut,
    LoaiVanBan,
    MauResponse,
    MucLucItem,
    ProvisionOut,
    SoanThaoRequest,
    SoanThaoResponse,
    SoatRequest,
    SoatResponse,
    TraCuuRequest,
    TraCuuResponse,
    VanBanMucLucResponse,
    VanBanProvisionsResponse,
)
from src.services.db import get_engine
from src.services.rules import Rule, enum_facts, mo_ta_facts, ten_tham_so

# _tong_hop_traces re-exported here: test_tra_cuu.py imports it from routes, not services.traces.
from src.services.traces import _ghi_traces, _tong_hop_traces  # noqa: F401

logger = logging.getLogger(__name__)

# Chỉ "hdld" có checklist nội dung thật (Task 3 mới xây
# config/checklist_hdld.yaml) — "noi_quy"/"quyet_dinh_ky_luat" là hai giá trị
# LoaiVanBan hợp lệ ở tầng Pydantic (dự phòng cho FE/tương lai) nhưng CHƯA có
# checklist riêng; áp nhầm checklist HĐLĐ lên chúng sẽ cho một audit report
# trông hợp lệ nhưng SAI loại văn bản — từ chối trung thực bằng 501 thay vì
# giả vờ hỗ trợ.
_LOAI_CO_CHECKLIST = {"hdld"}

router = APIRouter()

_graph = None


def _g():
    global _graph
    if _graph is None:
        _graph = build_graph_tra_cuu()
    return _graph


@router.post("/tra-cuu", response_model=TraCuuResponse)
async def tra_cuu(req: TraCuuRequest) -> TraCuuResponse:
    """spec 8.0a. `result_type` là enum bốn giá trị (không phải cờ `abstained`
    boolean): `partial_coverage` không thể ép vào "đã trả lời"/"đã từ chối" mà
    không mất thông tin, và ABSTAIN là hành vi ĐÚNG của hệ thống — không phải
    lỗi cần che giấu bằng một cờ nhị phân.
    """
    s = get_settings()
    trace_id = str(uuid.uuid4())
    bat_dau = time.monotonic()
    try:
        st = await _g().ainvoke({"query": req.query, "as_of_date": req.as_of_date, "trace_id": trace_id})
    except (httpx.HTTPStatusError, httpx.TransportError, OperationalError) as e:
        # Lỗi hạ tầng NHẤT THỜI, nhận diện được theo LOẠI ngoại lệ — OpenRouter
        # 429/5xx cạn retry (httpx) hoặc Postgres không kết nối được
        # (OperationalError): 503, đúng nghĩa "client NÊN thử lại". Chi tiết
        # đầy đủ vào log server (không lộ ra response — LlmClient không bao
        # giờ đưa OPENROUTER_API_KEY vào message ngoại lệ, nhưng response vẫn
        # chỉ mang TÊN loại lỗi, không mang str(e), để không mở rộng bề mặt rò
        # rỉ nếu một ngoại lệ tương lai vô tình mang theo dữ liệu nhạy cảm).
        logger.exception("tra_cuu: lỗi hạ tầng nhất thời khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=503, detail=f"tra cứu thất bại: {type(e).__name__}") from e
    except Exception as e:
        # Không thuộc hai loại rõ ràng-nhất-thời ở trên — bug thật (KeyError,
        # AttributeError...) hoặc ValueError của chính LlmClient khi OpenRouter
        # trả nội dung dị dạng (content rỗng/usage thiếu, xem llm.py) — 500,
        # KHÔNG ngụ ý client nên tự ý thử lại. Giới hạn đã biết: ValueError đó
        # về BẢN CHẤT cũng là dấu hiệu OpenRouter không ổn định, nhưng llm.py
        # dùng ValueError trần (không phải exception riêng) nên không tách
        # được khỏi ValueError từ một bug thật bằng KIỂU — nâng cấp lên một
        # exception riêng nếu cần tách rạch hơn.
        logger.exception("tra_cuu: lỗi không xác định khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=500, detail=f"tra cứu thất bại: {type(e).__name__}") from e
    latency_ms = int((time.monotonic() - bat_dau) * 1000)

    config_name = req.config_name or s.eval_config_name
    try:
        await run_in_threadpool(_ghi_traces, trace_id, "/api/v1/tra-cuu", req.query, config_name, st, latency_ms)
    except Exception:
        # Telemetry hỏng không phải lý do từ chối người dùng một câu trả lời
        # đã tính ĐÚNG — khác lỗi hạ tầng của chính graph ở trên, cái đó PHẢI
        # nổ ra vì nó quyết định result_type; ghi traces không quyết định gì.
        logger.exception("tra_cuu: ghi traces thất bại (trace_id=%s) — KHÔNG chặn response", trace_id)

    rt = st["result_type"]
    return TraCuuResponse(
        result_type=rt.value if hasattr(rt, "value") else rt,
        answer=st.get("answer"), citations=st.get("citations") or [],
        warnings=st.get("warnings") or [], coverage_note=st.get("coverage_note"),
        # `nguon` có mặc định `[]` trong model, nên quên truyền KHÔNG gây lỗi —
        # nó chỉ làm `partial_coverage` mất đường mở văn bản, im lặng. Ca thứ BA
        # của cùng một kiểu hỏng, sau `khop_tai_id` và `doc_id`.
        nguon=st.get("nguon") or [],
        trace_id=trace_id, config_name=config_name,
    )


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

_SQL_VAN_BAN_DOC = text("SELECT so_ky_hieu, ten FROM documents WHERE id = :doc_id")

_SQL_VAN_BAN_MUC_LUC = text(
    "SELECT id, cap, so_hieu_cap, tieu_de, thu_tu FROM provisions"
    " WHERE document_id = :doc_id AND cap IN ('phan', 'chuong', 'muc', 'tieu_muc')"
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

# Một Điều + TOÀN BỘ Khoản/Điểm con — con trực tiếp (Khoản, hoặc Điểm nếu nó
# nằm thẳng dưới Điều) HOẶC cháu trực tiếp (Điểm dưới Khoản). Không cần đệ quy
# sâu hơn: `dieu > khoan > diem` là đáy của cây (xem `Cap` trong domain.py).
_SQL_VAN_BAN_CAY_DIEU = text(
    "SELECT id, cap, so_hieu_cap, duong_dan, tieu_de, noi_dung FROM provisions"
    " WHERE id = :dieu_id OR parent_id = :dieu_id"
    "    OR parent_id IN (SELECT id FROM provisions WHERE parent_id = :dieu_id)"
    " ORDER BY thu_tu"
)


_SQL_DIEU_TRONG_CHUONG = text(
    "WITH RECURSIVE cay AS ("
    "  SELECT id, cap, document_id FROM provisions WHERE id = :goc"
    "  UNION ALL"
    "  SELECT p.id, p.cap, p.document_id FROM provisions p JOIN cay ON p.parent_id = cay.id"
    ")"
    " SELECT p.id, p.cap, p.so_hieu_cap, p.duong_dan, p.tieu_de, p.noi_dung"
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
    """
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
                doc_id=doc_id, so_ky_hieu=doc["so_ky_hieu"], bo_luat=doc["ten"],
                # `la_tam=False` cho tất cả: đang DUYỆT mục lục, chưa chọn Điều
                # nào làm tâm. Đánh dấu bừa một Điều là tâm sẽ rọi sáng nhầm.
                provisions=[ProvisionOut(**dict(r), la_tam=False) for r in rows],
            )

        if so_dieu is None and around is None:
            muc_luc = [
                MucLucItem(**dict(r))
                for r in conn.execute(_SQL_VAN_BAN_MUC_LUC, {"doc_id": doc_id}).mappings().all()
            ]
            return VanBanMucLucResponse(
                doc_id=doc_id, so_ky_hieu=doc["so_ky_hieu"], bo_luat=doc["ten"], muc_luc=muc_luc
            )

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

        return VanBanProvisionsResponse(
            doc_id=doc_id, so_ky_hieu=doc["so_ky_hieu"], bo_luat=doc["ten"], provisions=provisions
        )


_SQL_PHAM_VI = text(
    "SELECT d.id, d.so_ky_hieu, d.ten, d.loai_van_ban, d.tinh_trang,"
    "       count(p.id)::int AS so_dieu_khoan"
    " FROM documents d LEFT JOIN provisions p ON p.document_id = d.id"
    " GROUP BY d.id, d.so_ky_hieu, d.ten, d.loai_van_ban, d.tinh_trang"
    " ORDER BY count(p.id) DESC, d.so_ky_hieu"
)


def _pham_vi() -> PhamViResponse:
    with get_engine().connect() as c:
        rows = c.execute(_SQL_PHAM_VI).mappings().all()

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
    if loai_van_ban not in _LOAI_CO_CHECKLIST:
        raise HTTPException(status_code=501, detail=(
            f"loai_van_ban='{loai_van_ban}' chưa có checklist/rules riêng "
            f"(hiện chỉ hỗ trợ: {sorted(_LOAI_CO_CHECKLIST)})"
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
        "can_cu": duong_dan,
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


_TIEU_DE_VAN_BAN = {
    "hdld": "HỢP ĐỒNG LAO ĐỘNG",
    "noi_quy": "NỘI QUY LAO ĐỘNG",
    "quyet_dinh_ky_luat": "QUYẾT ĐỊNH KỶ LUẬT LAO ĐỘNG",
}


def _render_markdown(loai_van_ban: str, clauses: list) -> str:
    """Markdown thuần — KHÔNG python-docx, không LaTeX (ràng buộc toàn dự
    án). Đánh số Điều theo THỨ TỰ clause được sinh, không theo `stt` của
    checklist: draft_generate có thể bỏ một mục (schema_error, thiếu can_cu
    phù hợp) nên thứ tự thật của output mới là thứ tự đáng tin.
    """
    phan = [f"# {_TIEU_DE_VAN_BAN.get(loai_van_ban, loai_van_ban.upper())}", ""]
    for i, c in enumerate(clauses, 1):
        phan.append(f"## Điều {i}. {c.ten}\n\n{c.noi_dung}\n")
    return "\n".join(phan)


@router.post("/soan-thao", response_model=SoanThaoResponse)
async def soan_thao(req: SoanThaoRequest) -> SoanThaoResponse:
    """collect → retrieve_requirements → draft_generate → draft_audit
    (`build_graph_soan_thao`). `self_audit=True` luôn đúng ở đây — draft_generate
    CHỈ được gọi trên đường sinh của hệ thống (xem docstring node đó)."""
    _tu_choi_neu_chua_ho_tro(req.loai_van_ban)
    rules = load_rules_cached()
    _validate_facts(req.facts, rules)

    trace_id = str(uuid.uuid4())
    bat_dau = time.monotonic()
    try:
        st = await _g_soan_thao().ainvoke(
            {"loai_van_ban": req.loai_van_ban, "facts": req.facts, "nganh": req.nganh}
        )
    except (httpx.HTTPStatusError, httpx.TransportError, OperationalError) as e:
        # Cùng phân loại lỗi hạ tầng nhất thời như tra_cuu() — xem docstring ở đó.
        logger.exception("soan_thao: lỗi hạ tầng nhất thời khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=503, detail=f"soạn thảo thất bại: {type(e).__name__}") from e
    except Exception as e:
        logger.exception("soan_thao: lỗi không xác định khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=500, detail=f"soạn thảo thất bại: {type(e).__name__}") from e
    latency_ms = int((time.monotonic() - bat_dau) * 1000)

    config_name = req.config_name or get_settings().eval_config_name
    try:
        await run_in_threadpool(
            _ghi_traces, trace_id, "/api/v1/soan-thao", req.loai_van_ban, config_name, st, latency_ms
        )
    except Exception:
        logger.exception("soan_thao: ghi traces thất bại (trace_id=%s) — KHÔNG chặn response", trace_id)

    clauses = st.get("clauses") or []
    _, _, db_provisions = requirements()
    return SoanThaoResponse(
        document=_render_markdown(req.loai_van_ban, clauses),
        clauses=[dataclasses.asdict(c) for c in clauses],
        audit_report=_audit_report_out(st["audit_report"], _duong_dan_index(db_provisions)),
        trace_id=trace_id,
    )


@router.post("/soat", response_model=SoatResponse)
async def soat(req: SoatRequest) -> SoatResponse:
    """Soát văn bản NGƯỜI DÙNG dán vào — tách `clauses` bằng từ khoá
    (`extract_clauses`, KHÔNG LLM), rồi chạy CHÍNH rule engine đã soát output
    của draft_generate (`draft_audit`). `self_audit=False` luôn đúng ở đây.
    """
    _tu_choi_neu_chua_ho_tro(req.loai_van_ban)
    rules = load_rules_cached()
    _validate_facts(req.facts, rules)

    trace_id = str(uuid.uuid4())
    bat_dau = time.monotonic()
    rules, checklist, db_provisions = requirements()
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
        await run_in_threadpool(_ghi_traces, trace_id, "/api/v1/soat", req.text, config_name, st, latency_ms)
    except Exception:
        logger.exception("soat: ghi traces thất bại (trace_id=%s) — KHÔNG chặn response", trace_id)

    return SoatResponse(
        audit_report=_audit_report_out(st["audit_report"], _duong_dan_index(db_provisions)),
        trace_id=trace_id,
    )


@router.get("/mau/{loai}", response_model=MauResponse)
async def mau(loai: LoaiVanBan) -> MauResponse:
    """Mô tả các fact cần nhập cho `loai` — sinh TỪ config/rules.yaml
    (`rules.mo_ta_facts`), không hardcode danh sách trường trong Python (ràng
    buộc #4): frontend dựng form theo đây, sửa YAML là đủ khi rule đổi.

    `noi_quy`/`quyet_dinh_ky_luat` trả `facts: []` — chưa có checklist riêng
    (chỉ hdld có, Task 3), tái dùng nhầm fact của HĐLĐ sẽ sai loại văn bản.
    """
    if loai not in _LOAI_CO_CHECKLIST:
        return MauResponse(loai_van_ban=loai, facts=[])
    rules = load_rules_cached()
    facts = [FactFieldOut(**f) for f in mo_ta_facts(rules, load_facts_meta_cached())]
    return MauResponse(loai_van_ban=loai, facts=facts)
