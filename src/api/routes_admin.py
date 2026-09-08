"""Router `/admin` — đường quản trị cho CMS (spec 2026-09-08 cms-quan-ly-tai-khoan §5.3).

KHÔNG có endpoint nào đọc module hội thoại hay số lượt trong đó: admin thấy bao
nhiêu lượt, không thấy hỏi gì (test grep). KLAW không biết vai trò admin — proxy ở
CMS lọc theo vai trò; KLAW tin CMS và ghi `boi` để truy vết.
"""

import functools
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from src.models.schemas import (
    DanhSachGoiOut,
    DanhSachNhatKyOut,
    DanhSachTaiKhoanOut,
    DanhSachYeuCauOut,
    DatGoiRequest,
    HoatDongNgay,
    KetQuaGoiOut,
    LyDoRequest,
    PhanLoai,
    TaiKhoanChiTietOut,
    TongQuanOut,
    YeuCauNangGoiOut,
)
from src.services import bao_ve, nang_goi, nhat_ky, tai_khoan_qt
from src.services.bao_ve import kiem_admin_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")

_LOI_NGHIEP_VU = (
    nang_goi.KhongTonTai,
    nang_goi.DaXuLy,
    nang_goi.TaiKhoanKhoa,
    nang_goi.KhongCoGiDeThuHoi,
    nang_goi.GoiKhongHopLe,
    nang_goi.ChuaCoHoSo,
    tai_khoan_qt.TrangThaiKhongDoi,
)


def _http(e: Exception) -> HTTPException:
    if isinstance(e, nang_goi.TaiKhoanKhoa):
        return HTTPException(status_code=423, detail="Tài khoản đang bị khoá, mở khoá trước khi duyệt.")
    if isinstance(e, nang_goi.DaXuLy):
        return HTTPException(status_code=409, detail="Yêu cầu này đã được xử lý.")
    if isinstance(e, tai_khoan_qt.TrangThaiKhongDoi):
        return HTTPException(status_code=409, detail="Tài khoản đã ở trạng thái này.")
    if isinstance(e, nang_goi.KhongCoGiDeThuHoi):
        return HTTPException(status_code=409, detail="Tài khoản đang ở gói Miễn phí, không có gì để thu hồi.")
    if isinstance(e, nang_goi.GoiKhongHopLe):
        return HTTPException(status_code=422, detail="Gói không hợp lệ.")
    return HTTPException(status_code=404, detail="Không tìm thấy.")


async def _thuc_hien(hanh_dong: str, doi_tuong: str | None, ctx: dict, fn, *args):
    """Chạy một thao tác ghi; lỗi nghiệp vụ → nhật ký `<hanh_dong>_that_bai` + mã HTTP đúng (§5.3)."""
    try:
        return await run_in_threadpool(fn, *args)
    except _LOI_NGHIEP_VU as e:
        try:
            await run_in_threadpool(
                functools.partial(
                    nhat_ky.ghi,
                    f"{hanh_dong}_that_bai",
                    doi_tuong=doi_tuong,
                    chi_tiet={"loi": type(e).__name__},
                    boi=ctx["boi"],
                    ip=ctx["ip"],
                )
            )
        except Exception:
            logger.exception("routes_admin: không ghi được nhật ký thất bại")
        raise _http(e) from e


def _yeu_cau_out(r: dict) -> YeuCauNangGoiOut:
    return YeuCauNangGoiOut(**{k: r[k] for k in YeuCauNangGoiOut.model_fields})


@router.get("/tong-quan", response_model=TongQuanOut)
async def tong_quan(ctx: dict = Depends(kiem_admin_key)) -> TongQuanOut:
    return TongQuanOut(**await run_in_threadpool(tai_khoan_qt.tong_quan))


@router.get("/goi", response_model=DanhSachGoiOut)
async def goi(ctx: dict = Depends(kiem_admin_key)) -> DanhSachGoiOut:
    return DanhSachGoiOut(**tai_khoan_qt.danh_sach_goi())


@router.get("/yeu-cau", response_model=DanhSachYeuCauOut)
async def yeu_cau(
    ctx: dict = Depends(kiem_admin_key),
    trang_thai: str | None = Query(None, pattern="^(cho_duyet|da_duyet|tu_choi)$"),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DanhSachYeuCauOut:
    tong, rows = await run_in_threadpool(tai_khoan_qt.danh_sach_yeu_cau, trang_thai, q, limit, offset)
    items = [{**r, "plan_hieu_luc": bao_ve.plan_hieu_luc_tu(str(r["plan"]), r["plan_het_han"])} for r in rows]
    return DanhSachYeuCauOut.model_validate({"tong": tong, "items": items})


@router.post("/yeu-cau/{id}/duyet", response_model=KetQuaGoiOut)
async def duyet(id: int, ctx: dict = Depends(kiem_admin_key)) -> KetQuaGoiOut:
    r = await _thuc_hien(
        "duyet_yeu_cau", None, ctx, nang_goi.duyet, id, "admin", f"yeu_cau:{id}", ctx["boi"], ctx["ip"]
    )
    return KetQuaGoiOut(sub=r["sub"], plan=r["plan"], plan_het_han=r["plan_het_han"])


@router.post("/yeu-cau/{id}/tu-choi", response_model=YeuCauNangGoiOut)
async def tu_choi(id: int, body: LyDoRequest, ctx: dict = Depends(kiem_admin_key)) -> YeuCauNangGoiOut:
    await _thuc_hien("tu_choi_yeu_cau", None, ctx, nang_goi.tu_choi, id, body.ly_do, ctx["boi"], ctx["ip"])
    r = await run_in_threadpool(tai_khoan_qt.yeu_cau_theo_id, id)
    if r is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy.")
    return _yeu_cau_out(r)


@router.get("/tai-khoan", response_model=DanhSachTaiKhoanOut)
async def tai_khoan(
    ctx: dict = Depends(kiem_admin_key),
    q: str = Query("", max_length=200),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DanhSachTaiKhoanOut:
    tong, rows = await run_in_threadpool(tai_khoan_qt.tim, q, limit, offset)
    items = [{**r, "plan": bao_ve.plan_hieu_luc_tu(str(r["plan"]), r["plan_het_han"])} for r in rows]
    return DanhSachTaiKhoanOut.model_validate({"tong": tong, "items": items})


@router.get("/tai-khoan/{sub}", response_model=TaiKhoanChiTietOut)
async def chi_tiet(sub: uuid.UUID, ctx: dict = Depends(kiem_admin_key)) -> TaiKhoanChiTietOut:
    d = await run_in_threadpool(tai_khoan_qt.chi_tiet, str(sub))
    if d is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    plan = bao_ve.plan_hieu_luc_tu(d["plan_tho"], d["plan_het_han"])
    return TaiKhoanChiTietOut(
        sub=str(sub),
        email=d["email"],
        plan=plan,
        ten_goi=bao_ve.ten_goi(plan),
        tao_luc=d["tao_luc"],
        het_han_luc=d["plan_het_han"],
        so_phien=d["so_phien"],
        tong_hoi_dap=d["tong_hoi_dap"],
        tong_ban_thao=d["tong_ban_thao"],
        hoat_dong=[HoatDongNgay(**h) for h in d["hoat_dong"]],
        phan_loai=[PhanLoai(**p) for p in d["phan_loai"]],
        khoa_luc=d["khoa_luc"],
        khoa_ly_do=d["khoa_ly_do"],
        yeu_cau=[_yeu_cau_out(y) for y in d["yeu_cau"]],
    )


@router.patch("/tai-khoan/{sub}/goi", response_model=KetQuaGoiOut)
async def dat_goi(sub: uuid.UUID, body: DatGoiRequest, ctx: dict = Depends(kiem_admin_key)) -> KetQuaGoiOut:
    r = await _thuc_hien(
        "dat_goi", str(sub), ctx, nang_goi.dat_goi, str(sub), body.plan, body.so_ngay, ctx["boi"], ctx["ip"]
    )
    return KetQuaGoiOut(**r)


@router.post("/tai-khoan/{sub}/thu-hoi", response_model=KetQuaGoiOut)
async def thu_hoi(sub: uuid.UUID, body: LyDoRequest, ctx: dict = Depends(kiem_admin_key)) -> KetQuaGoiOut:
    r = await _thuc_hien("thu_hoi_goi", str(sub), ctx, nang_goi.thu_hoi, str(sub), body.ly_do, ctx["boi"], ctx["ip"])
    return KetQuaGoiOut(**r)


@router.post("/tai-khoan/{sub}/khoa")
async def khoa(sub: uuid.UUID, body: LyDoRequest, ctx: dict = Depends(kiem_admin_key)) -> dict:
    return await _thuc_hien(
        "khoa_tai_khoan", str(sub), ctx, tai_khoan_qt.khoa, str(sub), body.ly_do, ctx["boi"], ctx["ip"]
    )


@router.post("/tai-khoan/{sub}/mo-khoa")
async def mo_khoa(sub: uuid.UUID, ctx: dict = Depends(kiem_admin_key)) -> dict:
    return await _thuc_hien("mo_khoa_tai_khoan", str(sub), ctx, tai_khoan_qt.mo_khoa, str(sub), ctx["boi"], ctx["ip"])


@router.get("/nhat-ky", response_model=None)
async def nhat_ky_qt(
    ctx: dict = Depends(kiem_admin_key),
    tu: datetime | None = None,
    den: datetime | None = None,
    hanh_dong: str | None = Query(None, max_length=64),
    doi_tuong: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    dinh_dang: str | None = Query(None, pattern="^csv$"),
) -> DanhSachNhatKyOut | Response:
    tong, rows = await run_in_threadpool(
        functools.partial(
            nhat_ky.danh_sach,
            tu=tu,
            den=den,
            hanh_dong=hanh_dong,
            doi_tuong=str(doi_tuong) if doi_tuong else None,
            limit=limit,
            offset=offset,
        )
    )
    if dinh_dang == "csv":
        return Response(
            content=nhat_ky.csv(rows),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="nhat-ky-quan-tri.csv"'},
        )
    return DanhSachNhatKyOut.model_validate({"tong": tong, "items": rows})
