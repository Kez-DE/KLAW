"""`/ban-thao` — bản thảo đã lưu của tài khoản (spec 2026-09-09 §8.3).

Cùng khuôn `routes_hoi_thoai.py`: dữ liệu THEO NGƯỜI ⇒ `nguoi_dung_bat_buoc`
(401 kể cả khi Supabase chưa cấu hình). Mọi truy vấn lọc theo `sub` ngay ở
tầng `src.services.ban_thao` — bản thảo của người khác là 404, không tiết lộ
tồn tại (không phân biệt được với một id không có thật).
"""

import base64
import logging
import re
import unicodedata
import uuid
from pathlib import PurePath
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.agents.graph_soan_thao import load_checklist_cached, rules_cho
from src.agents.nodes.gom_du_kien import con_thieu, lua_chon_sai
from src.api.routes import _validate_facts
from src.api.routes_tai_lieu import KHONG_THAY, _loi_http
from src.api.routes_tai_lieu import _uuid_hop_le as _uuid_viec
from src.models.schemas import (
    BanThaoOut,
    BanThaoPhienBanChiTietOut,
    BanThaoPhienBanOut,
    BanThaoTomTatOut,
    DanhSachBanThaoOut,
    DanhSachPhienBanOut,
)
from src.services import ban_thao, bao_ve, dung_trang
from src.services.bao_ve import nguoi_dung_bat_buoc
from src.services.doc_tai_lieu import ChuyenDoiKhongSanSang, KhongDocDuoc
from src.services.retrieval import _bo_dau

logger = logging.getLogger(__name__)
router = APIRouter()


def _uuid_hop_le(id: str) -> str:
    # Chuỗi không phải UUID → 404 như bản thảo không tồn tại; không để Postgres
    # nổ lỗi kiểu (xem `routes_hoi_thoai._uuid_hop_le`).
    try:
        return str(uuid.UUID(id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY) from e


# `loai` không mang checklist nào (S6, `ban_thao.LOAI_TONG_QUAT`) → tên hiển thị
# cố định, không tra `load_checklist_cached` (hàm đó nổ `ValueError` cho nó,
# đúng định nghĩa "không theo checklist nào").
_TEN_LOAI_DAC_BIET = {ban_thao.LOAI_TONG_QUAT: "Bản thảo tổng quát"}


def _ten_loai(loai: str) -> str:
    """Tên hiển thị của `loai` — MỘT chỗ cho cả `_out()` lẫn `danh_sach()`, để
    route sau này cần tên không thể tự mở lại một nhánh riêng rồi trôi lệch.

    Khuôn phòng thủ giống `routes_tai_lieu.chi_tiet:356-363`: một `loai` lạ
    trong DB (checklist bị xoá sau khi bản thảo đã lưu) không được làm hỏng cả
    phản hồi — `ten` khi đó là chính `loai`, không phải một 500.
    """
    if loai in _TEN_LOAI_DAC_BIET:
        return _TEN_LOAI_DAC_BIET[loai]
    try:
        return load_checklist_cached(loai).ten
    except Exception:
        return loai


def _out(bt: dict) -> BanThaoOut:
    return BanThaoOut(
        id=bt["id"],
        loai=bt["loai"],
        ten=_ten_loai(bt["loai"]),
        phien_ban=bt["phien_ban"],
        document=bt["document"],
        clauses=bt["clauses"],
        audit_report=bt["audit"],
        facts=bt["facts"],
        khuon=bt.get("khuon"),
    )


@router.get("/ban-thao", response_model=DanhSachBanThaoOut)
async def danh_sach(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    nguoi: dict = Depends(nguoi_dung_bat_buoc),
) -> DanhSachBanThaoOut:
    items, tong = await run_in_threadpool(ban_thao.danh_sach, nguoi["sub"], limit, offset)
    return DanhSachBanThaoOut(
        tong=tong,
        items=[
            BanThaoTomTatOut(
                id=i["id"],
                loai=i["loai"],
                ten=_ten_loai(i["loai"]),
                phien_ban=i["phien_ban"],
                cap_nhat_luc=i["cap_nhat_luc"],
                hoi_thoai_id=i["hoi_thoai_id"],
            )
            for i in items
        ],
    )


@router.get("/ban-thao/{id}", response_model=BanThaoOut)
async def chi_tiet(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BanThaoOut:
    id = _uuid_hop_le(id)
    bt = await run_in_threadpool(ban_thao.chi_tiet, nguoi["sub"], id)
    if bt is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return _out(bt)


@router.get("/ban-thao/{id}/phien-ban", response_model=DanhSachPhienBanOut)
async def danh_sach_phien_ban(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> DanhSachPhienBanOut:
    """Phase 4 (D11, R4) — danh sách phiên bản CŨ của một bản thảo, để vẽ một
    bảng lịch sử. Phiên bản đang SỐNG không nằm trong danh sách này — giao
    diện đã có nó từ `GET /ban-thao/{id}` (`BanThaoOut.phien_ban`)."""
    id = _uuid_hop_le(id)
    lich_su = await run_in_threadpool(ban_thao.danh_sach_phien_ban, nguoi["sub"], id)
    if lich_su is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return DanhSachPhienBanOut(items=[BanThaoPhienBanOut(**s) for s in lich_su])


@router.get("/ban-thao/{id}/phien-ban/{so}", response_model=BanThaoPhienBanChiTietOut)
async def phien_ban_chi_tiet(
    id: str, so: int, nguoi: dict = Depends(nguoi_dung_bat_buoc)
) -> BanThaoPhienBanChiTietOut:
    """Phase 4 (D11, R4) — toàn bộ nội dung của MỘT phiên bản cũ, theo số. 404
    khi bản thảo không thấy/không phải chủ, hoặc `so` không khớp phiên bản cũ
    nào (kể cả số đang sống — xem docstring `ban_thao.phien_ban_chi_tiet`)."""
    id = _uuid_hop_le(id)
    snap = await run_in_threadpool(ban_thao.phien_ban_chi_tiet, nguoi["sub"], id, so)
    if snap is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return BanThaoPhienBanChiTietOut(
        phien_ban=snap["phien_ban"],
        luc=snap.get("luc"),
        doi=snap.get("doi") or [],
        document=snap["document"],
        facts=snap["facts"],
        clauses=snap["clauses"],
        audit_report=snap["audit"],
        khuon=snap.get("khuon"),
    )


@router.post("/ban-thao/{id}/lui", response_model=BanThaoOut)
async def lui(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BanThaoOut:
    id = _uuid_hop_le(id)
    bt = await run_in_threadpool(ban_thao.lui, nguoi["sub"], id)
    if bt is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return _out(bt)


FACTS_TOI_DA = 40
GIA_TRI_TOI_DA = 500
_KIEU_GIA_TRI = (str, int, float, bool, type(None))


class DungLaiRequest(BaseModel):
    facts: dict


def loi_facts_ngoai_bien(facts: dict) -> str | None:
    """Câu tiếng Việt nói biên nào bị vượt, hoặc None khi `facts` hợp lệ.

    `facts` đi thẳng vào placeholder `{facts}` của `draft_generate` — một lượt
    LLM TRẢ PHÍ. Không có biên thì mỗi lời gọi mang được tới trần body (2 MB)
    vào prompt đó, tức kẻ gọi tự chọn giá của một request. Ba biên, cùng khuôn
    với những gì biểu mẫu và `gom_du_kien` thật sự sinh ra.

    Trả CHUỖI thay vì ném từ một validator của pydantic: `detail` của lỗi
    pydantic là một DANH SÁCH object, mà giao diện chỉ hiện `detail` dạng chuỗi
    — nên câu giải thích sẽ không bao giờ tới được người dùng. Hai lỗi 422 anh
    em ngay dưới (`con_thieu`, `lua_chon_sai`) đã là chuỗi; đây là cái thứ ba.
    """
    if len(facts) > FACTS_TOI_DA:
        return f"Quá nhiều dữ kiện: tối đa {FACTS_TOI_DA} trường."
    for khoa, gia_tri in facts.items():
        if not isinstance(gia_tri, _KIEU_GIA_TRI):
            return f"Dữ kiện `{khoa}` phải là chữ, số hoặc đúng/sai."
        if isinstance(gia_tri, str) and len(gia_tri) > GIA_TRI_TOI_DA:
            return f"Dữ kiện `{khoa}` dài quá {GIA_TRI_TOI_DA} ký tự."
    return None


@router.post("/ban-thao/{id}/dung", response_model=BanThaoOut)
async def dung(id: str, body: DungLaiRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BanThaoOut:
    """Dựng lại bản thảo từ facts mới — drawer xếp chồng (Task 25). Cùng
    `ban_thao.dung_lai` mà lệnh bằng lời trong hội thoại dùng, nên trần sửa và
    cách chạy graph là MỘT, không phải hai đường khác nhau cho cùng một việc.

    Kiểm trường bắt buộc bằng CHÍNH `gom_du_kien.con_thieu`, và giá trị lựa
    chọn bằng CHÍNH `gom_du_kien.lua_chon_sai` — hai hàm mà lượt sửa bằng lời
    cũng dùng (trực tiếp, hoặc gián tiếp qua ràng buộc `enum` của
    `schema_du_kien`) — để drawer không thành một đường vòng qua ràng buộc đó
    chỉ vì nó gọi thẳng HTTP thay vì trò chuyện.

    ĐÂY LÀ MỘT ENDPOINT TIÊU TIỀN: `dung_lai` chạy `draft_generate` trên
    `generate_model()`. Nó KHÔNG đếm vào hạn mức soạn thảo — spec §8.4 nói lần
    sửa ghi trace `/api/v1/soan-thao/sua` và không đếm — nên ba cổng còn lại
    phải có đủ: danh tính (`nguoi_dung_bat_buoc`), trần chi phí NGÀY của cả hệ
    thống (`kiem_tran_chi_phi`, cùng cổng cuối mà `cong_bao_ve` gọi cho
    `/tra-cuu` và `/soan-thao`), và trần sửa của CHÍNH bản thảo này
    (`ban_thao.TRAN_SUA`, đo trên cột đơn điệu `so_lan_sua`).
    """
    id = _uuid_hop_le(id)
    cu = await run_in_threadpool(ban_thao.chi_tiet, nguoi["sub"], id)
    if cu is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    loi_bien = loi_facts_ngoai_bien(body.facts)
    if loi_bien:
        raise HTTPException(status_code=422, detail=loi_bien)
    thieu = con_thieu(cu["loai"], body.facts)
    if thieu:
        raise HTTPException(
            status_code=422,
            detail="Còn thiếu dữ kiện bắt buộc: " + ", ".join(t["nhan"] for t in thieu) + ".",
        )
    sai = lua_chon_sai(cu["loai"], body.facts)
    if sai:
        raise HTTPException(
            status_code=422,
            detail="Giá trị không hợp lệ cho: " + ", ".join(t["nhan"] for t in sai) + ".",
        )
    # CHÍNH hàm mà `/soan-thao` dùng (nhập từ module route kia, cùng lệ đã có với
    # `LOI_KHOA_BO_NHO` ở `routes_hoi_thoai`), không phải một bản chép: khoá trùng
    # tên tham số của rule là 422 ở cả hai cửa, nếu không cửa này là đường vòng qua nó.
    _validate_facts(body.facts, rules_cho(cu["loai"]))
    # Cổng cuối trước ví tiền, ngay TRƯỚC lượt LLM trả phí — cùng vị trí và cùng
    # hình dạng lỗi (429/503 do chính hàm ném) như `cong_bao_ve` gọi nó.
    await run_in_threadpool(bao_ve.kiem_tran_chi_phi)
    try:
        bt = await ban_thao.dung_lai(nguoi["sub"], id, body.facts)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    if bt is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return BanThaoOut(
        id=bt["id"],
        loai=bt["loai"],
        ten=bt["ten"],
        phien_ban=bt["phien_ban"],
        document=bt["document"],
        clauses=bt["clauses"],
        audit_report=bt["audit"],
        facts=bt["facts"],
        doi_so_voi_truoc=bt["doi_so_voi_truoc"],
        khuon=bt.get("khuon"),
    )


class SuaMucRequest(BaseModel):
    muc_key: str = Field(..., min_length=1, max_length=100)
    # Chỉ số khối HIỂN THỊ (đúng thứ tự `Muc.khoi` phía FE dựng), không phải
    # chỉ số của `clauses[i].khoi` thô — `ban_thao.sua_tay`/`_ap_dung_khoi` tự
    # quy đổi, đúng khuôn `xuat-tep.khoiTuClause` (xem docstring ở đó).
    khoi_index: int = Field(..., ge=0)
    # Trần đủ rộng cho một khối văn xuôi gõ tay (một điều/đoạn), hẹp hơn hẳn
    # `GIA_TRI_TOI_DA` của `facts` (500) vì đây là CẢ MỘT đoạn, không một
    # trường — nhưng vẫn phải có trần: request này không qua `kiem_tran_chi_phi`
    # (không LLM), nên không có cổng nào khác chặn một thân bất thường.
    noi_dung: str = Field(..., max_length=20000)
    # Review (I3, fix round 1) — phiên bản người dùng ĐANG NHÌN THẤY lúc gõ.
    # `muc_key` cấp theo VỊ TRÍ và bị cấp lại mỗi lượt sửa bằng lời dựng lại
    # `clauses` — thiếu trường này thì một khối mở từ TRƯỚC một lượt sửa như
    # vậy, blur SAU khi nó chạy xong, ghi đúng vị trí nhưng sai mục, không một
    # dấu hiệu nào báo ra. Bắt buộc (không có mặc định): route mới, chưa ai
    # gọi nó theo hình dạng cũ để giữ tương thích ngược.
    phien_ban: int = Field(..., ge=1)


@router.patch("/ban-thao/{id}/muc", response_model=BanThaoOut)
async def sua_muc(id: str, body: SuaMucRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BanThaoOut:
    """Sửa TAY một khối văn xuôi của một mục — Phase 3 (Half A, R1/R2).

    KHÁC HẲN `POST /ban-thao/{id}/dung`: route đó chạy `draft_generate` trên
    `generate_model()` (một lượt LLM TRẢ PHÍ) và dựng lại TOÀN BỘ bản thảo từ
    facts; route này KHÔNG gọi mô hình nào — nó chỉ ghi lại đúng chữ người
    dùng vừa gõ vào đúng khối, nên không cần `bao_ve.kiem_tran_chi_phi` (cổng
    đó gác trần chi phí NGÀY của lượt LLM, không áp dụng ở đây) — nhưng vẫn
    cần danh tính (`nguoi_dung_bat_buoc`, như mọi route `/ban-thao` khác) và
    `ban_thao.TRAN_SUA` (`sua_tay` tự gác, cùng bộ đếm `dung`/`dung_lai` dùng,
    xem docstring `sua_tay` cho lý do chia sẻ trần).

    422 khi mục/khối không thấy, khối đó là bảng (chưa sửa được ở giai đoạn
    này), đã hết trần sửa, hoặc `phien_ban` đã đổi (I3 — một lượt sửa bằng lời
    khác vừa chạy trong lúc khối này còn mở, xem docstring `sua_tay`) — bốn
    lỗi CÙNG MỘT HÌNH DẠNG (`sua_tay` trả chuỗi), không phân biệt được bằng mã
    HTTP nhưng phân biệt được bằng `detail`. 404 khi bản thảo không thấy/
    không phải chủ, cùng hợp đồng mọi route khác ở đây.
    """
    id = _uuid_hop_le(id)
    ket = await run_in_threadpool(
        ban_thao.sua_tay, nguoi["sub"], id, body.muc_key, body.khoi_index, body.noi_dung, body.phien_ban
    )
    if ket is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    if isinstance(ket, str):
        raise HTTPException(status_code=422, detail=ket)
    return _out(ket)


# ═══ Khuôn gốc — quyết định 2026-09-26, kế hoạch `khuon-goc-dien-tai-cho.md` ═══
# Ba route cho bản thảo trên khuôn gốc: trang đã điền, tải về, lưu ô điền. Cùng
# hàng rào của `routes_tai_lieu.trang`: chủ sở hữu lọc ở tầng dữ liệu (người
# khác, bản thảo HTML, khuôn gốc đã xoá đều 404), `nosniff`, `private`. Áp phép
# và dựng là việc CPU/tiến trình con: luôn qua `run_in_threadpool`, trong MỘT
# lượt mỗi tài khoản (`dung_trang._mot_luot`) cho cả hai. Log chỉ mang id và số
# đếm — không một giá trị đã điền nào.

LOI_PDF_KHONG_CO_DOCX = "Tài liệu tải lên là PDF nên chỉ tải được bản PDF đã điền."
_KIEU_TAI_VE = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}
# ASCII in được, trừ hai ký tự phải thoát trong một quoted-string (RFC 6266).
_ASCII_TEN = re.compile(r'[^\x20-\x7e]|["\\]')


def _tai_ve_dau(ten_tep: str, dang: str) -> str:
    """`Content-Disposition` của bản đã điền: `<tên tệp tải lên> - đã điền.<dang>`.

    Chỉ PHẦN TÊN (bỏ thư mục và đuôi — một `.doc` tải về là `.docx`), bỏ ký tự
    không in được (không `\r\n` nào chen được vào header). `filename*` (RFC 5987,
    UTF-8) cho tên thật; `filename` ASCII dự phòng: bỏ dấu, ký tự còn lại ngoài
    ASCII và `"`/`\\` thành `_`."""
    goc = re.split(r"[\\/]", unicodedata.normalize("NFC", ten_tep or ""))[-1]
    ten = "".join(ch for ch in PurePath(goc).stem if ch.isprintable()).strip() or "ban-thao"
    ascii_ = _ASCII_TEN.sub("_", _bo_dau(ten))
    return f"attachment; filename=\"{ascii_} - da dien.{dang}\"; filename*=UTF-8''{quote(f'{ten} - đã điền.{dang}', safe='')}"


async def _khuon_phien_ban(sub: str, id: str, phien_ban: int | None) -> dict:
    k = await run_in_threadpool(ban_thao.khuon_cua_phien_ban, sub, _uuid_hop_le(id), phien_ban)
    if k is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return k


def _bo_ap(id: str, k: dict):
    """Bước `ap` của `dung_trang`: khuôn gốc NGUYÊN + phép ĐẦY ĐỦ của phiên bản,
    chạy TRONG lượt dựng của tài khoản (không trước lượt). Phép bị bộ áp bỏ vẫn
    cho ra trang (phần áp được) — chỉ `sua_o_dien` từ chối lưu; ở đây chỉ log
    số đếm. `KhongDocDuoc` đi ra cùng lỗi dựng."""

    def ap(khuon_goc: bytes) -> bytes:
        ban, bao_cao = ban_thao.ap_phep_sua(k["dinh_dang"], khuon_goc, k["don_vi"], k["phep_sua"])
        if bo := len(bao_cao["bo_qua"]):
            logger.warning(
                "ban_thao %s phiên bản %s: bộ áp bỏ %d/%d phép", id, k["phien_ban"], bo, bo + len(bao_cao["da_ap"])
            )
        return ban

    return ap


@router.get("/ban-thao/{id}/trang")
async def trang(
    id: str, phien_ban: int | None = Query(default=None, ge=1), nguoi: dict = Depends(nguoi_dung_bat_buoc)
) -> JSONResponse:
    """Trang của MỘT phiên bản đã điền — cùng hình dạng `GET /tai-lieu/{id}/trang`:
    `{"kho": [[rộng_pt, cao_pt], …], "trang": ["<base64 png>", …]}`, áp và dựng
    MỘT lần mỗi request, trong một lượt mỗi tài khoản (`dung_trang.dung`).

    Không `phien_ban`: bản đang sống — đổi sau mỗi lần lưu, nên `no-store`. Có
    `phien_ban`: số phiên bản không bao giờ cấp lại, nội dung của nó không đổi,
    nên trình duyệt giữ được một giờ như `/tai-lieu/{id}/trang`."""
    k = await _khuon_phien_ban(nguoi["sub"], id, phien_ban)
    try:
        kho, png = await run_in_threadpool(dung_trang.dung, k["dinh_dang"], k["noi_dung"], nguoi["sub"], _bo_ap(id, k))
    except (KhongDocDuoc, ChuyenDoiKhongSanSang) as e:
        raise _loi_http(e) from e
    return JSONResponse(
        {"kho": kho, "trang": [base64.b64encode(p).decode("ascii") for p in png]},
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store" if phien_ban is None else "private, max-age=3600",
        },
    )


@router.get("/ban-thao/{id}/tai-xuong")
async def tai_xuong(
    id: str,
    dang: Literal["docx", "pdf"] = Query(...),
    phien_ban: int | None = Query(default=None, ge=1),
    nguoi: dict = Depends(nguoi_dung_bat_buoc),
) -> Response:
    """Tệp đã điền của một phiên bản (mặc định bản đang sống), dạng tệp đính kèm.

    Khuôn DOCX: `dang=docx` là chính khuôn gốc đã áp phép (mở bằng Word), `dang=pdf`
    là bản LibreOffice dựng từ nó. Khuôn PDF: chỉ `dang=pdf` (422 cho `docx` —
    PDF không dàn lại được). `private, no-store`: bytes mang dữ liệu cá nhân."""
    k = await _khuon_phien_ban(nguoi["sub"], id, phien_ban)
    if k["dinh_dang"] == "pdf" and dang == "docx":
        raise HTTPException(status_code=422, detail=LOI_PDF_KHONG_CO_DOCX)
    try:
        ban = await run_in_threadpool(
            dung_trang.tep_tai_ve, k["dinh_dang"], k["noi_dung"], dang, nguoi["sub"], _bo_ap(id, k)
        )
    except (KhongDocDuoc, ChuyenDoiKhongSanSang) as e:
        raise _loi_http(e) from e
    return Response(
        content=ban,
        media_type=_KIEU_TAI_VE[dang],
        headers={
            "Content-Disposition": _tai_ve_dau(k.get("ten_tep") or "", dang),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


class ODienIn(BaseModel):
    don_vi: int = Field(..., ge=0)
    cho_trong: int = Field(..., ge=0)
    # Một ô là một dòng; cùng trần của một `facts` (`GIA_TRI_TOI_DA`).
    gia_tri: str = Field(..., max_length=GIA_TRI_TOI_DA)


class SuaODienRequest(BaseModel):
    # Phiên bản người dùng ĐANG NHÌN THẤY — khoá lạc quan, cùng lý do `SuaMucRequest`.
    phien_ban: int = Field(..., ge=1)
    # Mọi ô đổi trong MỘT lần lưu (một phiên bản, một lần tính vào `TRAN_SUA`).
    gia_tri: list[ODienIn] = Field(..., min_length=1, max_length=500)


@router.patch("/ban-thao/{id}/o-dien", response_model=BanThaoOut)
async def sua_o_dien(id: str, body: SuaODienRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BanThaoOut:
    """Lưu các ô của bảng ô điền thành MỘT phiên bản mới — 0 lượt gọi mô hình,
    cùng trần sửa của lượt sửa bằng lời (`ban_thao.sua_o_dien`). Không dựng
    trang: giao diện gọi `GET …/trang` một lần sau khi lưu.

    422 (chuỗi `detail`) khi phiên bản đã đổi, hết trần, bản thảo không trên
    khuôn gốc, ô lạ, giá trị nhiều dòng hay bộ áp không điền được một ô — cùng
    quy ước `PATCH …/muc`. 404 khi không thấy/không phải chủ."""
    id = _uuid_hop_le(id)
    ket = await run_in_threadpool(
        ban_thao.sua_o_dien, nguoi["sub"], id, body.phien_ban, [g.model_dump() for g in body.gia_tri]
    )
    if ket is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    if isinstance(ket, str):
        raise HTTPException(status_code=422, detail=ket)
    return _out(ket)


@router.post("/tai-lieu/{viec_id}/ban-thao", response_model=BanThaoOut)
async def mo_ban_thao(viec_id: str, response: Response, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BanThaoOut:
    """Mở bảng ô điền trên khuôn gốc của một tài liệu khi KLAW chưa điền ô nào
    (lượt mô hình không điền được gì thì không lưu bản thảo). Thao tác RÕ của
    người dùng: 0 lượt mô hình, không tính hạn mức. 200 + bản thảo MỚI NHẤT của
    việc đó, hay 201 + phiên bản 1 với `phep_sua` rỗng. 404: việc lạ, của người
    khác, hoặc không có khuôn gốc (ảnh, tài liệu tải lên trước khuôn gốc)."""
    viec_id = _uuid_viec(viec_id)
    ra = await run_in_threadpool(ban_thao.mo_ban_thao_khuon, nguoi["sub"], viec_id)
    if ra is None:
        raise HTTPException(status_code=404, detail=KHONG_THAY)
    bt, da_tao = ra
    if da_tao:
        response.status_code = 201
    return _out(bt)


@router.delete("/ban-thao/{id}", status_code=204)
async def xoa(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    id = _uuid_hop_le(id)
    if not await run_in_threadpool(ban_thao.xoa_mem, nguoi["sub"], id):
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return Response(status_code=204)
