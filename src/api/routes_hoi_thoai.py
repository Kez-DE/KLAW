"""`/hoi-thoai` — phiên hội thoại theo tài khoản (spec 2026-09-07 §5.3).

Không LLM ⇒ không `cong_bao_ve`; nhưng dữ liệu THEO NGƯỜI ⇒ `nguoi_dung_bat_buoc`
(401 kể cả khi Supabase chưa cấu hình). Mọi truy vấn lọc theo `sub`; phiên của
người khác là 404 (không tiết lộ tồn tại).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from src.models.schemas import (
    ChiTietPhienResponse,
    DanhSachPhienResponse,
    DoiTenPhienRequest,
    LuotDaLuuOut,
    NhapPhienRequest,
    NhapPhienResponse,
    PhienTomTatOut,
)
from src.services import hoi_thoai
from src.services.bao_ve import han_muc, nguoi_dung_bat_buoc, plan_hieu_luc

logger = logging.getLogger(__name__)
router = APIRouter()


def _uuid_hop_le(id: str) -> str:
    # Chuỗi không phải UUID → 404 như phiên không tồn tại; không để Postgres nổ lỗi kiểu.
    try:
        return str(uuid.UUID(id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=hoi_thoai.LOI_KHONG_THAY) from e


async def _phien_mo_duoc(sub: str, id: str) -> dict:
    phien = await run_in_threadpool(hoi_thoai.lay_phien, sub, id)
    if phien is None:
        raise HTTPException(status_code=404, detail=hoi_thoai.LOI_KHONG_THAY)
    return phien


@router.post("/hoi-thoai/nhap", response_model=NhapPhienResponse, status_code=201)
async def nhap(body: NhapPhienRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> NhapPhienResponse:
    """Mang đoạn chat của khách vào tài khoản (spec 2A §8.4). `tra_loi` đã qua pydantic
    `TraCuuResponse` nên chỉ payload đúng hình mới vào được; không đụng `traces`."""
    luot = [
        {"cau_hoi": lu.cau_hoi, "tra_loi": lu.tra_loi.model_dump(mode="json"), "trace_id": lu.trace_id}
        for lu in body.luot
    ]
    return NhapPhienResponse(id=await run_in_threadpool(hoi_thoai.nhap_phien, nguoi["sub"], luot))


@router.get("/hoi-thoai", response_model=DanhSachPhienResponse)
async def danh_sach(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    nguoi: dict = Depends(nguoi_dung_bat_buoc),
) -> DanhSachPhienResponse:
    sub = nguoi["sub"]
    plan = await run_in_threadpool(plan_hieu_luc, sub)
    items, tong = await run_in_threadpool(hoi_thoai.danh_sach, sub, limit, offset)
    return DanhSachPhienResponse(
        plan=plan,
        luot_moi_phien=han_muc(plan, "luot_moi_phien"),
        tong=tong,
        items=[PhienTomTatOut(**i) for i in items],
    )


@router.get("/hoi-thoai/{id}", response_model=ChiTietPhienResponse)
async def chi_tiet(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> ChiTietPhienResponse:
    id = _uuid_hop_le(id)
    await _phien_mo_duoc(nguoi["sub"], id)
    ct = await run_in_threadpool(hoi_thoai.chi_tiet, nguoi["sub"], id)
    # Xoá song song giữa `_phien_mo_duoc` và truy vấn này → `None`; 404 chứ không TypeError 500.
    if ct is None:
        raise HTTPException(status_code=404, detail=hoi_thoai.LOI_KHONG_THAY)
    return ChiTietPhienResponse(**{**ct, "luot": [LuotDaLuuOut(**lu) for lu in ct["luot"]]})


@router.patch("/hoi-thoai/{id}", response_model=PhienTomTatOut)
async def doi_ten(id: str, body: DoiTenPhienRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> PhienTomTatOut:
    id = _uuid_hop_le(id)
    await _phien_mo_duoc(nguoi["sub"], id)
    # Cùng cửa sổ xoá song song như `chi_tiet`: cả hai lượt đọc đều có thể trả `None`.
    phien = await run_in_threadpool(hoi_thoai.doi_ten, nguoi["sub"], id, body.tieu_de)
    if phien is None:
        raise HTTPException(status_code=404, detail=hoi_thoai.LOI_KHONG_THAY)
    ct = await run_in_threadpool(hoi_thoai.chi_tiet, nguoi["sub"], id)
    if ct is None:
        raise HTTPException(status_code=404, detail=hoi_thoai.LOI_KHONG_THAY)
    return PhienTomTatOut(**{**phien, "so_luot": len(ct["luot"])})


@router.delete("/hoi-thoai/{id}", status_code=204)
async def xoa(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    id = _uuid_hop_le(id)
    if not await run_in_threadpool(hoi_thoai.xoa_mem, nguoi["sub"], id):
        raise HTTPException(status_code=404, detail=hoi_thoai.LOI_KHONG_THAY)
    return Response(status_code=204)
