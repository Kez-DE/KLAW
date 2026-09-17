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

from src.agents.graph_soan_thao import load_checklist_cached, rules_cho
from src.agents.nodes.gom_du_kien import con_thieu, lua_chon_sai
from src.api.routes import _validate_facts
from src.models.schemas import BanThaoOut, BanThaoTomTatOut, DanhSachBanThaoOut
from src.services import ban_thao, bao_ve
from src.services.bao_ve import nguoi_dung_bat_buoc

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
    )


@router.delete("/ban-thao/{id}", status_code=204)
async def xoa(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    id = _uuid_hop_le(id)
    if not await run_in_threadpool(ban_thao.xoa_mem, nguoi["sub"], id):
        raise HTTPException(status_code=404, detail=ban_thao.LOI_KHONG_THAY)
    return Response(status_code=204)
