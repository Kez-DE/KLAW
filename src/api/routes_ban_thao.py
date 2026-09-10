"""`/ban-thao` — bản thảo đã lưu của tài khoản (spec 2026-09-09 §8.3).

Cùng khuôn `routes_hoi_thoai.py`: dữ liệu THEO NGƯỜI ⇒ `nguoi_dung_bat_buoc`
(401 kể cả khi Supabase chưa cấu hình). Mọi truy vấn lọc theo `sub` ngay ở
tầng `src.services.ban_thao` — bản thảo của người khác là 404, không tiết lộ
tồn tại (không phân biệt được với một id không có thật).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from src.agents.graph_soan_thao import load_checklist_cached
from src.agents.nodes.gom_du_kien import con_thieu
from src.models.schemas import BanThaoOut, BanThaoTomTatOut, DanhSachBanThaoOut
from src.services import ban_thao
from src.services.bao_ve import nguoi_dung_bat_buoc

router = APIRouter()


def _uuid_hop_le(id: str) -> str:
    # Chuỗi không phải UUID → 404 như bản thảo không tồn tại; không để Postgres
    # nổ lỗi kiểu (xem `routes_hoi_thoai._uuid_hop_le`).
    try:
        return str(uuid.UUID(id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY) from e


def _out(bt: dict) -> BanThaoOut:
    return BanThaoOut(
        id=bt["id"],
        loai=bt["loai"],
        ten=load_checklist_cached(bt["loai"]).ten,
        phien_ban=bt["phien_ban"],
        document=bt["document"],
        clauses=bt["clauses"],
        audit_report=bt["audit"],
        facts=bt["facts"],
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
                ten=load_checklist_cached(i["loai"]).ten,
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


@router.post("/ban-thao/{id}/lui", response_model=BanThaoOut)
async def lui(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BanThaoOut:
    id = _uuid_hop_le(id)
    bt = await run_in_threadpool(ban_thao.lui, nguoi["sub"], id)
    if bt is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return _out(bt)


class DungLaiRequest(BaseModel):
    facts: dict


@router.post("/ban-thao/{id}/dung", response_model=BanThaoOut)
async def dung(id: str, body: DungLaiRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BanThaoOut:
    """Dựng lại bản thảo từ facts mới — drawer xếp chồng (Task 25). Cùng
    `ban_thao.dung_lai` mà lệnh bằng lời trong hội thoại dùng, nên trần sửa và
    cách chạy graph là MỘT, không phải hai đường khác nhau cho cùng một việc.

    Kiểm trường bắt buộc bằng CHÍNH `gom_du_kien.con_thieu` — hàm mà lượt sửa
    bằng lời dùng để quyết định có đủ dữ kiện chưa — để drawer không thành một
    đường vòng qua ràng buộc đó chỉ vì nó gọi thẳng HTTP thay vì trò chuyện.
    """
    id = _uuid_hop_le(id)
    cu = await run_in_threadpool(ban_thao.chi_tiet, nguoi["sub"], id)
    if cu is None:
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    thieu = con_thieu(cu["loai"], body.facts)
    if thieu:
        raise HTTPException(
            status_code=422,
            detail="Còn thiếu dữ kiện bắt buộc: " + ", ".join(t["nhan"] for t in thieu) + ".",
        )
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
    )


@router.delete("/ban-thao/{id}", status_code=204)
async def xoa(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    id = _uuid_hop_le(id)
    if not await run_in_threadpool(ban_thao.xoa_mem, nguoi["sub"], id):
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return Response(status_code=204)
