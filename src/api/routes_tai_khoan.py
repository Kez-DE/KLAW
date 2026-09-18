"""`GET /han-muc` · `POST /nguoi-dung` · `GET /ho-so` · `GET|POST /nang-goi/yeu-cau`
— tài khoản người dùng (spec 2026-09-07 §6).

`bao_ve.kiem_han_muc` cưỡng chế hạn mức ngày/tháng của gói (spec 2A §4.2),
nhưng người dùng không có cách nào biết mình còn bao nhiêu cho tới khi bị 429
giữa một câu hỏi. Các endpoint này lấp đúng khoảng đó, và chỉ ĐỌC LẠI thứ cổng
bảo vệ đã đếm — không bộ đếm thứ hai nào được dựng. Hai bộ đếm sẽ lệch nhau và
không cách nào biết bên nào đúng; cùng lý lẽ đã khiến `bao_ve.chi_phi_hom_nay`
đọc thẳng `traces` thay vì nuôi một biến riêng.

## Vì sao `/han-muc` KHÔNG dùng `Depends(cong_bao_ve)`

`cong_bao_ve` ném 429 khi hết hạn mức. Đặt nó trước `/han-muc` nghĩa là
đúng endpoint sinh ra để nói "bạn hết lượt rồi" sẽ tự khoá mình lại ĐÚNG LÚC
người dùng cần nó nhất. Nó cũng ghi một lượt vào `rate_limit_luot` cho mỗi lần
mở trang tài khoản — xem hạn mức không phải là dùng hạn mức.

Cái được giữ lại ở `/han-muc` là `kiem_api_key` và LÁ CHẮN theo IP — KHÔNG
phải danh tính. Từ chế độ khách (spec 2A §8.3) endpoint này trả lời cả người
CHƯA đăng nhập, nên danh tính không còn là cổng vào được: nhánh khách chạy hai
truy vấn `rate_limit_luot` mỗi lần gọi, và `KLAW_API_KEY` phải RỖNG thì trình
duyệt khách mới qua nổi `kiem_api_key` — tức không có lá chắn thì đây là một
bơm truy vấn hoàn toàn không xác thực. Lá chắn đếm ở giỏ RIÊNG (`chan-ip:`,
cùng giỏ `cong_bao_ve` dùng) nên xem hạn mức vẫn không tiêu hạn mức. Bốn
endpoint còn lại vẫn bắt buộc danh tính (`nguoi_dung_bat_buoc`). Không cổng nào
bị bỏ vì lười: các endpoint này không gọi LLM, không gọi embedding.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from src.api import luong_thong_bao
from src.models.schemas import (
    BoNhoTaiKhoanOut,
    CaiDatBoNhoRequest,
    DaDocRequest,
    DanhSachDaNhoOut,
    DanhSachThongBaoOut,
    HanMucResponse,
    HoatDongNgay,
    HoSoResponse,
    MucBoNhoOut,
    MucDaNhoOut,
    MucHanMuc,
    NguoiDungResponse,
    PhanLoai,
    PhienHanMuc,
    SuaBoNhoRequest,
    YeuCauNangGoiOut,
    YeuCauNangGoiRequest,
)
from src.services import bao_ve, bo_nho, bo_nho_tai_khoan, ho_so, nang_goi, thong_bao, xac_thuc
from src.services.bao_ve import kiem_api_key, nguoi_dung_bat_buoc, nguoi_dung_ke_ca_khoa, xac_thuc_nguoi_goi

logger = logging.getLogger(__name__)

router = APIRouter()

GHI_CHU_CACHE = (
    "Lượt trả lời từ bộ đệm, câu ngoài phạm vi và lượt lỗi không tính. Tra cứu luật, soát văn bản không bao giờ tính."
)
GHI_CHU_TAT = (
    "Hạn mức theo người dùng chưa bật trên bản triển khai này (Supabase auth chưa "
    "cấu hình), nên hệ thống không đếm lượt theo tài khoản. Trần chi phí ngày và "
    "giới hạn tần suất vẫn hoạt động."
)


async def _nguoi_goi(request: Request) -> dict | None:
    """`{"sub", "email"}` của người gọi, hoặc None khi auth chưa cấu hình.

    `xac_minh` có thể gọi mạng (nạp JWKS khi TTL hết) nên vào threadpool — cùng
    lý do `cong_bao_ve` làm vậy. Thiếu bọc này là chặn event loop cho mọi
    request khác; dự án đã dính đúng lỗi đó hai lần.
    """
    kiem_api_key(request)
    return await run_in_threadpool(xac_thuc_nguoi_goi, request)


@router.get("/han-muc", response_model=HanMucResponse)
async def han_muc_cua_toi(request: Request) -> HanMucResponse:
    """Hạn mức của người gọi. KHÔNG đi qua `cong_bao_ve` (không tốn lượt, không tự khoá)."""
    bao_ve.kiem_api_key(request)
    # Lá chắn IP, TRƯỚC mọi truy vấn. Nhánh khách bên dưới chạy `dem_cua_so` và
    # nhánh đăng nhập chạy ba truy vấn, còn cổng đứng trước chúng (`kiem_api_key`)
    # phải RỖNG mới cho trình duyệt khách đi qua — nên không có dòng này thì
    # `/han-muc` là bề mặt không xác thực duy nhất đọc Postgres mà không ai đếm.
    #
    # Giỏ `chan-ip:` là giỏ LÁ CHẮN của `cong_bao_ve`, KHÔNG phải hạn mức của
    # người dùng: xem hạn mức vẫn không tiêu hạn mức, đúng bất biến cả module
    # này tồn tại để giữ.
    #
    # KHÔNG bọc try/except quanh nó: `kiem_rate_limit` đã tự ném 429 (vượt) và
    # 503 (DB hỏng), nên bọc là biến đúng cái 429 vừa dựng thành một 503.
    # `bao_ve.get_settings()` chứ không một tên đã import ở đầu file: cùng quy
    # ước "gọi qua `bao_ve.<tên>`" giải thích ở thân hàm bên dưới, và lá chắn
    # PHẢI đọc cùng một đối tượng cấu hình với `kiem_rate_limit` mà nó gọi —
    # hai nguồn cấu hình là hai cái trần bất đồng nhau.
    await run_in_threadpool(
        bao_ve.kiem_rate_limit,
        f"chan-ip:{bao_ve.ip_goi(request)}",
        bao_ve.get_settings().rate_limit_ip_so_luot,
    )
    tz = str(bao_ve.mui_gio())
    nguoi = await run_in_threadpool(bao_ve.xac_thuc_nguoi_goi_hoac_none, request)
    if nguoi is None and not xac_thuc.da_cau_hinh():
        return HanMucResponse(
            ap_dung=False,
            plan=None,
            ten_goi=None,
            mui_gio=tz,
            muc=[],
            phien=PhienHanMuc(luot_toi_da=None),
            het_han_luc=None,
            ghi_chu=GHI_CHU_TAT,
        )
    if nguoi is None:
        kid = bao_ve.khach_id_tu_request(request)
        if kid is None:
            raise HTTPException(status_code=401, detail=bao_ve.LOI_KHACH_DANG_NHAP)
        k = bao_ve._doc_han_muc()["khach"]
        try:
            da_dung, mo_lai = await run_in_threadpool(bao_ve.dem_cua_so, f"khach:{kid}", 86400)
        except Exception as e:
            logger.exception("han_muc: không đếm được lượt thử của khách %s — TỪ CHỐI", kid)
            raise HTTPException(
                status_code=503,
                detail="Không đọc được lượt dùng thử, vui lòng thử lại.",
            ) from e
        return HanMucResponse(
            ap_dung=True,
            plan="khach",
            ten_goi="Dùng thử",
            mui_gio=tz,
            muc=[
                MucHanMuc(
                    khoa="khach_24h",
                    nhan="Lượt thử 24 giờ",
                    da_dung=da_dung,
                    han_muc=int(k["hoi_dap_24h"]),
                    dat_lai_luc=mo_lai,
                )
            ],
            phien=PhienHanMuc(luot_toi_da=int(k["hoi_dap_24h"])),
            het_han_luc=None,
            ghi_chu="Đăng nhập miễn phí để có 200 lượt mỗi ngày, lưu phiên và soạn văn bản.",
        )

    # Gọi qua `bao_ve.<tên>` chứ không tên đã import: `monkeypatch.setattr` của
    # test (và mọi lớp bọc tương lai) tác động lên thuộc tính MODULE, còn tên đã
    # import giữ tham chiếu tới object cũ. Cùng khuôn `routes.py` dùng cho `_g`.
    sub = nguoi["sub"]
    try:
        plan = await run_in_threadpool(bao_ve.ghi_nhan_nguoi_dung, sub, nguoi["email"])
        muc = await run_in_threadpool(bao_ve.mo_ta_muc, sub, plan)
        het_han = await run_in_threadpool(bao_ve.het_han_cua, sub)
        bi_khoa = await run_in_threadpool(bao_ve.bi_khoa, sub)
    except Exception as e:
        # Hỏng ở tầng đếm là TỪ CHỐI, không phải trả một con số đoán. Một
        # `da_dung` bịa ra khi DB hỏng tệ hơn một lỗi — người dùng tin nó, rồi
        # gõ câu hỏi tiếp theo và nhận 429 mà không hiểu vì sao.
        logger.exception("han_muc: không đọc được hạn mức của %s — TỪ CHỐI", sub)
        raise HTTPException(
            status_code=503,
            detail="Không đọc được hạn mức của tài khoản, vui lòng thử lại.",
        ) from e

    return HanMucResponse(
        ap_dung=True,
        plan=plan,
        ten_goi=bao_ve.ten_goi(plan),
        mui_gio=tz,
        muc=[MucHanMuc(**m) for m in muc],
        phien=PhienHanMuc(luot_toi_da=bao_ve.han_muc(plan, "luot_moi_phien")),
        het_han_luc=het_han,
        bi_khoa=bi_khoa,
        ghi_chu=GHI_CHU_CACHE,
    )


@router.get("/ho-so", response_model=HoSoResponse)
async def ho_so_cua_toi(nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> HoSoResponse:
    d = await run_in_threadpool(ho_so.tong_hop, nguoi["sub"])
    if d is None:
        raise HTTPException(status_code=404, detail="Chưa có hồ sơ cho tài khoản này.")
    plan = bao_ve.plan_hieu_luc_tu(d["plan_tho"], d["plan_het_han"])
    return HoSoResponse(
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
    )


@router.post("/nang-goi/yeu-cau", response_model=YeuCauNangGoiOut, status_code=201)
async def gui_yeu_cau(body: YeuCauNangGoiRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> YeuCauNangGoiOut:
    try:
        return YeuCauNangGoiOut(**await run_in_threadpool(nang_goi.tao_yeu_cau, nguoi["sub"], body.goi_muon))
    except nang_goi.GoiKhongHopLe as e:
        raise HTTPException(status_code=422, detail="Gói không hợp lệ.") from e
    except nang_goi.GoiConHieuLuc as e:
        raise HTTPException(
            status_code=422, detail="Gói còn hiệu lực, gia hạn được từ 7 ngày trước khi hết hạn."
        ) from e
    except nang_goi.DangCho as e:
        raise HTTPException(status_code=409, detail="Bạn đã có một yêu cầu đang chờ duyệt.") from e
    except nang_goi.ChuaCoHoSo as e:
        raise HTTPException(status_code=404, detail="Chưa có hồ sơ cho tài khoản này.") from e


@router.get("/nang-goi/yeu-cau", response_model=YeuCauNangGoiOut | None)
async def yeu_cau_moi_nhat(nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> YeuCauNangGoiOut | None:
    r = await run_in_threadpool(nang_goi.moi_nhat, nguoi["sub"])
    return YeuCauNangGoiOut(**r) if r is not None else None


@router.post("/nguoi-dung", response_model=NguoiDungResponse)
async def nguoi_dung(request: Request) -> NguoiDungResponse:
    """Ghi nhận người dùng sau đăng nhập, trả về gói của họ.

    Frontend gọi đúng một lần sau khi Supabase trả token, để dòng `users` tồn
    tại TRƯỚC lượt hỏi đầu tiên. Không bắt buộc — `cong_bao_ve` cũng upsert
    (JIT provisioning) — nhưng nó là chỗ FE lấy `plan` để vẽ trang tài khoản mà
    không phải tiêu một lượt hỏi AI để biết mình đang ở gói nào.

    Idempotent: `ON CONFLICT (sub) DO UPDATE` — gọi lại chỉ làm mới
    `last_seen_at`, không sinh dòng thứ hai.
    """
    nguoi = await _nguoi_goi(request)
    if nguoi is None:
        # KHÔNG 200 với một `sub` bịa: đó là dữ liệu rác vĩnh viễn trong đúng
        # bảng mà hạn mức tháng đếm theo. 501 nói đúng sự thật — tính năng này
        # cần một thứ bản triển khai hiện tại không có.
        raise HTTPException(
            status_code=501, detail=("Chưa cấu hình xác thực (Supabase) — không có danh tính nào để ghi nhận.")
        )
    try:
        plan = await run_in_threadpool(bao_ve.ghi_nhan_nguoi_dung, nguoi["sub"], nguoi["email"])
    except Exception as e:
        logger.exception("nguoi_dung: không ghi được dòng users (%s)", nguoi["sub"])
        raise HTTPException(
            status_code=503,
            detail="Không lưu được thông tin tài khoản, vui lòng thử lại.",
        ) from e
    return NguoiDungResponse(sub=nguoi["sub"], email=nguoi["email"], plan=plan)


_HEADER_SSE = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}


@router.get("/thong-bao", response_model=DanhSachThongBaoOut)
async def hop_thu_cua_toi(
    nguoi: dict = Depends(nguoi_dung_ke_ca_khoa), chi_chua_doc: bool = False
) -> DanhSachThongBaoOut:
    return DanhSachThongBaoOut.model_validate(await run_in_threadpool(thong_bao.hop_thu, nguoi["sub"], chi_chua_doc))


@router.post("/thong-bao/da-doc")
async def da_doc_cua_toi(body: DaDocRequest, nguoi: dict = Depends(nguoi_dung_ke_ca_khoa)) -> dict:
    return {"da_danh_dau": await run_in_threadpool(thong_bao.danh_dau_da_doc, body.ids, nguoi["sub"])}


@router.get("/thong-bao/luong")
async def luong_cua_toi(nguoi: dict = Depends(nguoi_dung_ke_ca_khoa)) -> StreamingResponse:
    return StreamingResponse(luong_thong_bao.phat(nguoi["sub"]), media_type="text/event-stream", headers=_HEADER_SSE)


# ══ /tai-khoan/bo-nho — hồ sơ tình huống xuyên phiên, chỉ Pro (spec 2026-09-09 §6.4) ══

LOI_BO_NHO_CAN_PRO = (
    "Trí nhớ hoàn cảnh xuyên phiên là quyền lợi của gói Cá nhân. Nâng cấp để KLAW nhớ bạn giữa các phiên."
)
LOI_KHOA_BO_NHO = "Khoá hoặc giá trị không hợp lệ: bộ nhớ chỉ giữ bảy dữ kiện về hoàn cảnh của bạn, không giữ số Điều, số hiệu văn bản hay thông tin định danh."


async def _pro_bat_buoc(nguoi: dict) -> str:
    if await run_in_threadpool(bao_ve.plan_hieu_luc, nguoi["sub"]) != "pro":
        raise HTTPException(status_code=403, detail=LOI_BO_NHO_CAN_PRO)
    return nguoi["sub"]


def _bo_nho_out(sub: str) -> BoNhoTaiKhoanOut:
    return BoNhoTaiKhoanOut(
        ghi_nho=bo_nho.doc_ghi_nho(sub), muc=[MucBoNhoOut(**m) for m in bo_nho.ho_so_tai_khoan(sub)]
    )


@router.get("/tai-khoan/bo-nho", response_model=BoNhoTaiKhoanOut)
async def bo_nho_cua_toi(nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BoNhoTaiKhoanOut:
    sub = await _pro_bat_buoc(nguoi)
    return await run_in_threadpool(_bo_nho_out, sub)


@router.patch("/tai-khoan/bo-nho/cai-dat", response_model=BoNhoTaiKhoanOut)
async def cai_dat_bo_nho(body: CaiDatBoNhoRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BoNhoTaiKhoanOut:
    sub = await _pro_bat_buoc(nguoi)
    await run_in_threadpool(bo_nho.dat_ghi_nho, sub, body.ghi_nho)
    return await run_in_threadpool(_bo_nho_out, sub)


@router.patch("/tai-khoan/bo-nho/{khoa}", response_model=BoNhoTaiKhoanOut)
async def sua_bo_nho(khoa: str, body: SuaBoNhoRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> BoNhoTaiKhoanOut:
    sub = await _pro_bat_buoc(nguoi)
    try:
        await run_in_threadpool(bo_nho.sua_khoa_tai_khoan, sub, khoa, body.gia_tri)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=LOI_KHOA_BO_NHO) from e
    return await run_in_threadpool(_bo_nho_out, sub)


@router.delete("/tai-khoan/bo-nho/{khoa}", status_code=204)
async def xoa_mot_bo_nho(khoa: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    sub = await _pro_bat_buoc(nguoi)
    await run_in_threadpool(bo_nho.xoa_khoa_tai_khoan, sub, khoa)
    return Response(status_code=204)


@router.delete("/tai-khoan/bo-nho", status_code=204)
async def xoa_het_bo_nho(nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    sub = await _pro_bat_buoc(nguoi)
    await run_in_threadpool(bo_nho.xoa_het_tai_khoan, sub)
    return Response(status_code=204)


# ══ /tai-khoan/da-nho — điều KLAW đã nhớ về tài khoản (Phase 12, R2) ══════
#
# KHÁC `/tai-khoan/bo-nho` ngay trên: đó là hồ sơ TÌNH HUỐNG pháp lý (chỉ Pro,
# bảy khoá, loại định danh). Đây là dữ kiện cá nhân và thói quen soạn mà người
# dùng tự khai — tên, mã SV — nên mở cho MỌI tài khoản đã đăng nhập: đây là dữ
# liệu cá nhân, quyền xem và xoá nó không phải quyền lợi của một gói.
#
# Chỉ đọc và xoá, không sửa: sửa là nói lại trong lượt soạn thảo (R5 lấy dữ
# kiện từ lượt đã có), và một biểu mẫu sửa tay ở đây là một đường ghi thứ hai
# phải giữ đồng bộ mà chưa ai cần.

LOI_DA_NHO_KHONG_THAY = "Không tìm thấy mục này."


def _da_nho_out(sub: str) -> DanhSachDaNhoOut:
    return DanhSachDaNhoOut(muc=[MucDaNhoOut(**m) for m in bo_nho_tai_khoan.liet_ke(sub)])


@router.get("/tai-khoan/da-nho", response_model=DanhSachDaNhoOut)
async def da_nho_cua_toi(nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> DanhSachDaNhoOut:
    return await run_in_threadpool(_da_nho_out, nguoi["sub"])


@router.delete("/tai-khoan/da-nho/{id}", status_code=204)
async def xoa_mot_da_nho(id: uuid.UUID, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    # 404 cả khi `id` tồn tại nhưng thuộc người khác: 403 sẽ xác nhận với kẻ dò
    # rằng id đó có thật. `uuid.UUID` ở tham số đường dẫn để chuỗi rác thành 422
    # ngay tại biên, không tới CAST của Postgres.
    if not await run_in_threadpool(bo_nho_tai_khoan.xoa_mot, nguoi["sub"], str(id)):
        raise HTTPException(status_code=404, detail=LOI_DA_NHO_KHONG_THAY)
    return Response(status_code=204)


@router.delete("/tai-khoan/da-nho", status_code=204)
async def xoa_het_da_nho(nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    await run_in_threadpool(bo_nho_tai_khoan.xoa_het, nguoi["sub"])
    return Response(status_code=204)
