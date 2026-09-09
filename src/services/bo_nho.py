"""Bộ nhớ ba lớp của phiên và hồ sơ tình huống theo tài khoản (spec 2026-09-09 §6).

Bộ nhớ chỉ chứa DỮ KIỆN VỀ NGƯỜI HỎI. Nó không bao giờ chống đỡ một khẳng định
pháp luật: các node nhận nó dưới dạng khối "Tình huống của người hỏi" là dữ liệu,
còn luận điểm vẫn phải trích điều khoản trong `context` và qua hai tầng kiểm.
Lưới chặn ở đây loại mọi giá trị mang số Điều/Khoản/Điểm, số hiệu văn bản hay
dấu vết định danh cá nhân (chuỗi 9–12 chữ số, email, số điện thoại) TRƯỚC khi ghi.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from pathlib import Path

from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.config import get_settings
from src.services import bao_ve, hoi_thoai
from src.services.db import get_engine
from src.services.kho import moi_so_hieu_trong
from src.services.llm import Usage, router_model
from src.services.llm import from_settings as llm_from_settings
from src.services.prompts import messages
from src.services.traces import _ghi_traces

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("prompts/bo_nho.v1.md")
K_LUOT_NGUYEN_VAN = hoi_thoai.LUOT_LICH_SU  # 6 — một nguồn duy nhất cho cửa sổ nguyên văn
TOM_TAT_TOI_DA = 1200
GIA_TRI_TOI_DA = 120
KHOA_HO_SO = ("chu_the", "loai_hop_dong", "tham_nien", "vung_luong", "thoi_diem", "van_ban_da_co", "vu_viec")
NHAN_HO_SO = {
    "chu_the": "Vai của bạn",
    "loai_hop_dong": "Loại hợp đồng",
    "tham_nien": "Thâm niên",
    "vung_luong": "Nơi làm việc",
    "thoi_diem": "Thời điểm",
    "van_ban_da_co": "Giấy tờ đang giữ",
    "vu_viec": "Việc đang theo",
}
NGUON = ("suy_dien", "nguoi_noi", "tai_khoan")
# suy_dien là giả định của máy: không được đè lên điều người nói hay điều tài khoản đã lưu.
_HANG_NGUON = {"suy_dien": 0, "tai_khoan": 1, "nguoi_noi": 2}
ENDPOINT_TRACE = "/api/v1/bo-nho"
KHONG_CO_DU_KIEN = "(chưa có dữ kiện nào)"

_RE_DIEU = re.compile(r"\b(Đi[eề]u|Kho[aả]n|Đi[eể]m)\s+\d+", re.IGNORECASE)
_RE_DINH_DANH = re.compile(r"\d{9,12}|@|(?:\+84|0)\d{9}\b")

BO_NHO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tom_tat", "ho_so"],
    "properties": {
        "tom_tat": {"type": "string"},
        "ho_so": {
            "type": "object",
            "additionalProperties": False,
            "required": list(KHOA_HO_SO),
            "properties": {k: {"type": "string"} for k in KHOA_HO_SO},
        },
    },
}


def gia_tri_hop_le(gia_tri: str) -> bool:
    g = " ".join(str(gia_tri or "").split())
    if not g or len(g) > GIA_TRI_TOI_DA:
        return False
    if _RE_DIEU.search(g) or moi_so_hieu_trong(g) or _RE_DINH_DANH.search(g):
        return False
    return True


def gop_ho_so(cu: dict, moi: dict, nguon: str) -> dict:
    """Gộp giá trị mới vào hồ sơ: chỉ khoá trong `KHOA_HO_SO`, giá trị qua lưới chặn,
    và nguồn thấp hơn không đè nguồn cao hơn (`suy_dien` < `tai_khoan` < `nguoi_noi`)."""
    ra = {k: dict(v) for k, v in (cu or {}).items() if k in KHOA_HO_SO and isinstance(v, dict) and v.get("gia_tri")}
    for khoa, gia_tri in (moi or {}).items():
        if khoa not in KHOA_HO_SO or not gia_tri_hop_le(gia_tri):
            continue
        hien = ra.get(khoa)
        if hien is not None and _HANG_NGUON[hien.get("nguon", "suy_dien")] > _HANG_NGUON[nguon]:
            continue
        ra[khoa] = {"gia_tri": " ".join(str(gia_tri).split()), "nguon": nguon}
    return ra


def khoi_tinh_huong(ho_so: dict) -> str:
    dong = [
        f"- {NHAN_HO_SO[k]}: {v['gia_tri']}" + (" (tôi đoán)" if v.get("nguon") == "suy_dien" else "")
        for k in KHOA_HO_SO
        if (v := (ho_so or {}).get(k)) and v.get("gia_tri")
    ]
    return "\n".join(dong) if dong else KHONG_CO_DU_KIEN


def ho_so_da_dung(ho_so: dict) -> list[dict]:
    return [
        {"khoa": k, "nhan": NHAN_HO_SO[k], "gia_tri": v["gia_tri"], "gia_dinh": v.get("nguon") == "suy_dien"}
        for k in KHOA_HO_SO
        if (v := (ho_so or {}).get(k)) and v.get("gia_tri")
    ]


def luot_can_gop(den_cu: int, thu_tu_moi: int) -> tuple[int, int] | None:
    """Khoảng lượt phải gộp vào tóm tắt sau khi lượt `thu_tu_moi` được ghi: từ lượt cuối đã
    gộp + 1 tới lượt vừa rơi khỏi cửa sổ K nguyên văn. None khi chưa có gì rơi ra."""
    tu, den = den_cu + 1, thu_tu_moi - K_LUOT_NGUYEN_VAN
    return (tu, den) if den >= tu else None


_SQL_TK_DOC = text(
    "SELECT khoa, gia_tri, nguon_hoi_thoai_id::text AS nguon_hoi_thoai_id, cap_nhat_luc"
    " FROM ho_so_tai_khoan WHERE user_sub = CAST(:sub AS uuid) ORDER BY khoa"
)
_SQL_TK_GHI = text(
    "INSERT INTO ho_so_tai_khoan (user_sub, khoa, gia_tri, nguon_hoi_thoai_id, cap_nhat_luc)"
    " VALUES (CAST(:sub AS uuid), :khoa, :gia_tri, CAST(:pid AS uuid), now())"
    " ON CONFLICT (user_sub, khoa) DO UPDATE SET gia_tri = EXCLUDED.gia_tri,"
    " nguon_hoi_thoai_id = EXCLUDED.nguon_hoi_thoai_id, cap_nhat_luc = now()"
)
_SQL_TK_XOA_KHOA = text("DELETE FROM ho_so_tai_khoan WHERE user_sub = CAST(:sub AS uuid) AND khoa = :khoa")
_SQL_TK_XOA_HET = text("DELETE FROM ho_so_tai_khoan WHERE user_sub = CAST(:sub AS uuid)")
_SQL_GHI_NHO_DOC = text("SELECT ghi_nho FROM users WHERE sub = CAST(:sub AS uuid)")
_SQL_GHI_NHO_DAT = text("UPDATE users SET ghi_nho = :co WHERE sub = CAST(:sub AS uuid)")


def ho_so_tai_khoan(sub: str) -> list[dict]:
    with get_engine().connect() as c:
        rows = c.execute(_SQL_TK_DOC, {"sub": sub}).mappings().all()
    return [
        {
            "khoa": r["khoa"],
            "nhan": NHAN_HO_SO.get(r["khoa"], r["khoa"]),
            "gia_tri": r["gia_tri"],
            "nguon_hoi_thoai_id": r["nguon_hoi_thoai_id"],
            "cap_nhat_luc": r["cap_nhat_luc"],
        }
        for r in rows
    ]


def ho_so_tu_tai_khoan(sub: str) -> dict:
    return {m["khoa"]: {"gia_tri": m["gia_tri"], "nguon": "tai_khoan"} for m in ho_so_tai_khoan(sub)}


def gop_vao_tai_khoan(sub: str, ho_so: dict, hoi_thoai_id: str | None) -> None:
    """Mới đè cũ theo khoá; chỉ ghi khoá có giá trị và không phải kế thừa từ chính tài khoản."""
    with get_engine().begin() as c:
        for khoa in KHOA_HO_SO:
            v = (ho_so or {}).get(khoa)
            if v and v.get("gia_tri") and v.get("nguon") != "tai_khoan":
                c.execute(_SQL_TK_GHI, {"sub": sub, "khoa": khoa, "gia_tri": v["gia_tri"], "pid": hoi_thoai_id})


def sua_khoa_tai_khoan(sub: str, khoa: str, gia_tri: str) -> None:
    if khoa not in KHOA_HO_SO or not gia_tri_hop_le(gia_tri):
        raise ValueError("khoá hoặc giá trị không hợp lệ")
    with get_engine().begin() as c:
        c.execute(_SQL_TK_GHI, {"sub": sub, "khoa": khoa, "gia_tri": " ".join(gia_tri.split()), "pid": None})


def xoa_khoa_tai_khoan(sub: str, khoa: str) -> None:
    with get_engine().begin() as c:
        c.execute(_SQL_TK_XOA_KHOA, {"sub": sub, "khoa": khoa})


def xoa_het_tai_khoan(sub: str) -> None:
    with get_engine().begin() as c:
        c.execute(_SQL_TK_XOA_HET, {"sub": sub})


def doc_ghi_nho(sub: str) -> bool:
    with get_engine().connect() as c:
        r = c.execute(_SQL_GHI_NHO_DOC, {"sub": sub}).scalar_one_or_none()
    return bool(r) if r is not None else True


def dat_ghi_nho(sub: str, co: bool) -> None:
    with get_engine().begin() as c:
        c.execute(_SQL_GHI_NHO_DAT, {"sub": sub, "co": co})


def _dung_luot(luot: list[dict]) -> str:
    return (
        "\n".join(f"Lượt {r['thu_tu']}\n  Người hỏi: {r['cau_hoi']}\n  KLAW đã trả lời: {r['tra_loi']}" for r in luot)
        or "(không có)"
    )


def cap_nhat_phien(hoi_thoai_id: str, user_sub: str, llm=None, model: str | None = None) -> None:
    """Một lời gọi LLM sau mỗi lượt: tóm tắt cuộn các lượt vừa rơi khỏi cửa sổ K và cập
    nhật hồ sơ từ lượt mới nhất. KHÔNG BAO GIỜ raise; lỗi → log, giữ bản cũ."""
    bat_dau = time.monotonic()
    usage: Usage | None = None
    try:
        bn = hoi_thoai.bo_nho_cua_phien(hoi_thoai_id)
        if bn["khong_ghi_nho"]:
            return
        thu_tu_moi = hoi_thoai.dem_luot(hoi_thoai_id)
        if thu_tu_moi == 0:
            return
        khoang = luot_can_gop(bn["tom_tat_den_thu_tu"], thu_tu_moi)
        luot_gop = hoi_thoai.luot_khoang(hoi_thoai_id, *khoang) if khoang else []
        luot_moi = hoi_thoai.luot_khoang(hoi_thoai_id, thu_tu_moi, thu_tu_moi)
        prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
            tom_tat_cu=bn["tom_tat"] or "(chưa có)",
            ho_so_cu=khoi_tinh_huong(bn["ho_so"]),
            luot_gop=_dung_luot(luot_gop),
            luot_moi=_dung_luot(luot_moi),
        )
        llm = llm or llm_from_settings()
        model = model or router_model()
        raw, usage = llm.chat(model, messages(prompt), json_schema=BO_NHO_SCHEMA)
        ra = json.loads(raw)
        tom_tat = " ".join(str(ra.get("tom_tat") or "").split())[:TOM_TAT_TOI_DA] or bn["tom_tat"]
        if _RE_DIEU.search(tom_tat or "") or moi_so_hieu_trong(tom_tat or ""):
            tom_tat = bn["tom_tat"]  # tóm tắt lọt số Điều/số hiệu → giữ bản cũ
        ho_so = gop_ho_so(bn["ho_so"], ra.get("ho_so") or {}, "nguoi_noi")
        den = khoang[1] if khoang else bn["tom_tat_den_thu_tu"]
        hoi_thoai.ghi_bo_nho(hoi_thoai_id, tom_tat if (luot_gop or bn["tom_tat"]) else None, den, ho_so)
        if bao_ve.plan_hieu_luc(user_sub) == "pro" and doc_ghi_nho(user_sub):
            gop_vao_tai_khoan(user_sub, ho_so, hoi_thoai_id)
    except Exception:
        logger.exception("bo_nho: không cập nhật được phiên %s — giữ bản cũ", hoi_thoai_id)
    finally:
        if usage is not None:
            try:
                _ghi_traces(
                    str(uuid.uuid4()),
                    ENDPOINT_TRACE,
                    hoi_thoai_id,
                    get_settings().eval_config_name,
                    {
                        "result_type": "bo_nho",
                        "traces": {
                            "token_in": usage.token_in,
                            "token_out": usage.token_out,
                            "cost_usd": usage.cost_usd,
                        },
                    },
                    int((time.monotonic() - bat_dau) * 1000),
                    user_sub=user_sub,
                )
            except Exception:
                logger.exception("bo_nho: không ghi được traces cho phiên %s", hoi_thoai_id)


_DANG_CHAY: set[asyncio.Task] = set()


def len_lich_cap_nhat(hoi_thoai_id: str, user_sub: str) -> None:
    """Xếp `cap_nhat_phien` chạy nền trên event loop hiện tại; giữ tham chiếu task để không bị thu gom."""
    if not get_settings().bo_nho_nen:
        return
    task = asyncio.get_running_loop().create_task(run_in_threadpool(cap_nhat_phien, hoi_thoai_id, user_sub))
    _DANG_CHAY.add(task)
    task.add_done_callback(_DANG_CHAY.discard)
