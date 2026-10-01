"""`/tai-lieu` — đọc tài liệu người dùng thành dữ kiện có neo nguồn
(spec 2026-09-15).

Cùng khuôn `routes_ban_thao.py`: dữ liệu THEO NGƯỜI ⇒ `nguoi_dung_bat_buoc`
(401 kể cả khi Supabase chưa cấu hình). Tài liệu của người khác là 404, không
tiết lộ tồn tại.

Tệp tải lên được GIỮ cùng cuộc hội thoại làm **khuôn gốc** (quyết định
2026-09-26, migration 036) để "Bản tải lên" hiện đúng từng trang như tệp, và bị
xoá cứng cùng hội thoại. Chỉ ghi khi tệp đã đọc được, nằm trong trần 10 trang
và lượt rút đã chọn (nếu có) không bị ước chi phí từ chối; một tệp bị từ chối
không để lại byte nào. Tệp đã giữ luôn tính vào hạn mức ngày
(`tai_lieu.da_dung_hom_nay`). Ảnh không có khuôn gốc.
"""

import base64
import logging
import re
import uuid
from dataclasses import replace

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from src.agents.nodes.rut_du_kien import rut_du_kien
from src.services import ban_thao, dung_trang
from src.services import llm as llm_svc
from src.services import tai_lieu as tl
from src.services.bao_ve import nguoi_dung_bat_buoc
from src.services.db import get_engine
from src.services.doc_tai_lieu import ChuyenDoiKhongSanSang, KhongDocDuoc, LoaiHong, TaiLieuDaDoc, doc
from src.services.phan_loai_tai_lieu import KetQuaPhanLoai, phan_loai
from src.services.tai_lieu import VuotTran
from src.services.thong_tin_noi_bo import loc_noi_bo

logger = logging.getLogger(__name__)
router = APIRouter()

KHONG_THAY = "Không tìm thấy tài liệu"

# Tên tệp ảnh trong `word/media/` — chữ, số, chấm, gạch. KHÔNG có `/` nên
# không ghép được một đường dẫn nào khác, và `fullmatch` nên một `..` đứng
# riêng cũng không lọt (nó không có phần tên trước dấu chấm).
_TEN_ANH = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,8}")

# Thông điệp cho từng nguyên nhân. Mỗi câu nói được MỘT việc người dùng làm tiếp
# được — đó là toàn bộ lý do bốn nguyên nhân không bị gộp thành một nhãn.
_THONG_DIEP = {
    LoaiHong.dinh_dang_khong_ho_tro: "Chỉ đọc được tệp PDF có lớp chữ, DOCX và DOC. Hãy gửi bản gốc thay vì ảnh chụp.",
    LoaiHong.tep_hong: "Không mở được tệp này. Hãy thử gửi lại, hoặc xuất lại từ phần mềm soạn thảo.",
    LoaiHong.can_mat_khau: "Tệp đang được bảo vệ bằng mật khẩu. Hãy gỡ mật khẩu rồi gửi lại.",
    LoaiHong.khong_co_lop_chu: "Không đọc được chữ trong tệp này. Nếu là ảnh chụp, hãy chụp lại rõ và đủ sáng, hoặc gửi bản gốc.",
}

# Việc hỏng vì trần, không vì tệp. Hai câu riêng vì hai việc người dùng làm tiếp
# khác nhau: một bên chia nhỏ tài liệu, một bên chờ hoặc báo người vận hành.
THONG_DIEP_TRAN = {
    "so_byte": f"Tệp vượt giới hạn {tl.TRAN_BYTE // (1024 * 1024)} MB.",
    "so_trang": f"Tài liệu vượt giới hạn {tl.TRAN_TRANG} trang.",
    "chi_phi": "Tài liệu này quá lớn để xử lý trong một lần. Hãy tách nhỏ rồi gửi lại.",
}

# Fix round 2 — hai nguyên nhân hỏng vì HỆ THỐNG (`ChuyenDoiKhongSanSang`),
# không vì tài liệu: không được nói như bốn nguyên nhân `_THONG_DIEP` ("tệp
# của bạn có vấn đề"), vì tệp không có vấn đề gì cả. Câu cho `khong_co_cong_cu`
# gợi ý một việc làm được NGAY (gửi .pdf) thay vì chỉ bảo "thử lại" — một lỗi
# cấu hình không tự hết. Từ quyết định 2026-09-26 LibreOffice dựng trang cho
# MỌI tệp Word (.doc lẫn .docx) và `pdftoppm` vẽ ảnh trang, nên câu không còn
# chỉ nói về .doc.
_THONG_DIEP_HE_THONG = {
    "khong_co_cong_cu": "Máy chủ chưa sẵn sàng xử lý tệp này lúc này. Hãy thử lại sau, hoặc gửi bản .pdf nếu đang tải tệp Word lên.",
    "qua_tai": "Hệ thống đang xử lý nhiều tài liệu cùng lúc. Hãy thử lại sau ít phút.",
}


class DuKienOut(BaseModel):
    id: str | None = None
    khoa: str
    nhan: str | None = None
    gia_tri: str
    nguon: str
    trich: str | None = None
    trich_goc: str | None = None
    trang: int | None = None
    chi_so_don_vi: int | None = None
    do_tin: float | None = None
    """Chỉ có với `tai_lieu_ocr`. Giao diện dùng nó để nói rõ đây là chữ máy
    đọc từ ảnh, không phải chữ thật của tài liệu."""


class TaiLieuOut(BaseModel):
    id: str
    hoi_thoai_id: str = ""
    """Cuộc trò chuyện tài liệu này thuộc về. Người gọi có thể KHÔNG gửi
    `hoi_thoai_id` (đính kèm ở một đoạn chat chưa mở), nên đây là chỗ họ biết
    phiên vừa được mở là phiên nào và hỏi tiếp vào đúng nó."""
    trang_thai: str
    so_trang: int | None = None
    chay_nen: bool
    co_ocr: bool = False
    loai: str | None = None
    loai_ten: str | None = None
    """Tên loại văn bản, để giao diện nói được nó đã hiểu tài liệu là gì."""
    loai_tu_doan: bool = False
    """Hệ thống tự nhận ra, chứ không phải người dùng chọn. Giả định phải hiện
    thành chữ và sửa được một chạm — `docs/bo-luat-agent.md` QT-5."""
    loai_can_cu: str | None = None
    """Dòng trong tài liệu đã dẫn tới kết luận. Suy luận không giải thích được
    thì người dùng không sửa được."""
    ly_do_hong: str | None = None
    thong_diep: str | None = None
    du_kien: list[DuKienOut] = []
    ten_tep: str = ""
    so_don_vi: int = 0
    """Số đơn vị văn bản đã đọc được. Đây là thứ giao diện nói khi KHÔNG có
    checklist nào khớp: "đã đọc N đơn vị · M trang" thay cho một ngõ cụt."""
    mo_ta: str | None = None
    """Một câu tài liệu này là gì, do lượt hỏi đầu tiên ghi lại (S2). Trống cho
    tới khi có người thật sự hỏi về tài liệu."""
    co_khuon_goc: bool = False
    """Tệp được giữ làm khuôn gốc (quyết định 2026-09-26): `GET …/trang` vẽ được
    nó đúng như bản tải lên. `False` với ảnh và tài liệu tải lên trước đó —
    giao diện lùi về bản xem HTML."""


class DocLaiIn(BaseModel):
    loai: str


class DonViOut(BaseModel):
    chi_so: int
    trang: int
    offset_dau: int
    noi_dung: str
    nguon_chu: str
    do_tin: float | None = None
    vung: str = "than"
    bang: list[int] | None = None
    """`[bảng, hàng, cột]` đếm từ 0, `null` khi đơn vị không nằm trong bảng."""


class DonViTaiLieuOut(BaseModel):
    id: str
    ten_tep: str
    so_trang: int | None = None
    don_vi: list[DonViOut] = []


class SuaDuKienIn(BaseModel):
    gia_tri: str


class SangSoanThaoOut(BaseModel):
    loai: str
    facts: dict[str, str]
    con_thieu: list[dict]
    da_ghi_vao_hoi_thoai: bool = False


def _loi_http(e: Exception, ten_tep: str = "") -> HTTPException:
    """Ánh xạ lỗi đọc sang HTTP. Hàm thuần, tách ra để test được không cần DB.

    Vượt trần và không đọc được đều là 422: yêu cầu hợp lệ về cú pháp nhưng
    không xử lý được, và cả hai đều nói rõ người dùng phải làm gì khác. Trần trang
    có `ten_tep` thì nói tệp nào và số trang thật (B5, owner 2026-09-27): tên tệp
    không phải nội dung tài liệu (FR-025), và chỉ phần tên đi vào câu.

    `ChuyenDoiKhongSanSang` (fix round 2) là 503, KHÔNG phải 422: đây không
    phải "tệp của bạn có vấn đề" (422 nói đúng cho bốn nguyên nhân
    `KhongDocDuoc`), mà là "hệ thống chưa xử lý được NGAY BÂY GIỜ" — đúng
    nghĩa Service Unavailable, và đúng tín hiệu để một client tự động biết
    nên thử lại thay vì coi tệp là hỏng.
    """
    ten = "".join(ch for ch in re.split(r"[\\/]", ten_tep or "")[-1] if ch.isprintable()).strip()[:120]
    if isinstance(e, VuotTran) and e.tran == "so_trang" and ten:
        return HTTPException(status_code=422, detail=f"«{ten}» có {e.thuc_te} trang, vượt giới hạn {e.gioi_han} trang.")
    if isinstance(e, VuotTran):
        return HTTPException(status_code=422, detail=THONG_DIEP_TRAN[e.tran])
    if isinstance(e, KhongDocDuoc):
        return HTTPException(status_code=422, detail=_THONG_DIEP[e.ly_do])
    if isinstance(e, ChuyenDoiKhongSanSang):
        return HTTPException(status_code=503, detail=_THONG_DIEP_HE_THONG[e.ly_do])
    raise e


async def _kiem_han_muc(nguoi: dict) -> None:
    """429 khi hết lượt đọc tài liệu trong ngày — FR-004.

    Nói rõ con số và mốc mở lại, cùng khuôn `bao_ve.kiem_han_muc`: một 429 chung
    chung làm người dùng thử lại vô ích cả ngày.
    """
    from src.services import bao_ve

    # Gói HIỆU LỰC đọc từ `users` (xét `plan_het_han`), không phải từ dict xác
    # thực: `nguoi_dung_bat_buoc` chỉ trả `{"sub", "email"}`, không có `goi`.
    # Cùng khuôn mọi cổng hạn mức khác trong codebase (`routes.py`,
    # `routes_hoi_thoai.py`, `routes_tai_khoan.py`) — đây từng là chỗ DUY NHẤT
    # tự chế lấy gói và luôn ra "free" bất kể tài khoản đã nâng gói.
    goi = await run_in_threadpool(bao_ve.plan_hieu_luc, nguoi["sub"])
    tran = tl.han_muc_ngay(goi)
    da_dung = await run_in_threadpool(tl.da_dung_hom_nay, get_engine(), nguoi["sub"])
    if da_dung >= tran:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Đã đọc {da_dung}/{tran} tài liệu hôm nay (gói {goi}). "
                f"Hạn mức mở lại lúc {bao_ve.moc_ngay_sau():%H:%M %d/%m/%Y}."
            ),
        )


def _uuid_hop_le(id: str) -> str:
    try:
        return str(uuid.UUID(id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=KHONG_THAY) from e


def _chay(viec_id: str, user_sub: str, hoi_thoai_id: str, loai: str, tai_lieu: TaiLieuDaDoc) -> None:
    """Rút + neo + lưu. Dùng chung cho đường tại chỗ, đường chạy nền và rút
    lại (`doc_lai`).

    Nhận tài liệu ĐÃ ĐỌC chứ không nhận bytes: số trang quyết định đường đi nên
    phải đọc trước khi chọn đường, và đọc lại lần thứ hai ở đây là trả giá phân
    tích hai lần cho mỗi tài liệu. Việc rút chỉ cần các đơn vị văn bản, nên
    bytes tệp không đi vào hàm này — khuôn gốc nằm yên ở `khuon_goc`.

    Một hàm cho cả ba đường, nên trần chi phí và cách ghi trạng thái chỉ tồn
    tại ở một chỗ (bài học `ban_thao.dung_lai`).
    """
    engine = get_engine()
    try:
        # FR-036 — chặn TRƯỚC khi tiêu đồng nào. Không còn trần thời gian, nên
        # đây là chỗ duy nhất một tài liệu dị dạng bị chặn trước ví tiền.
        tl.kiem_tran_chi_phi_tai_lieu(tai_lieu.so_ky_tu)

        ra = rut_du_kien(loai, tai_lieu, llm_svc.from_settings(), llm_svc.generate_model())
        chi_phi = ra["traces"]["rut_du_kien_cost_usd"]
        if ra["traces"]["rut_du_kien_nguon"] == "loi":
            tl.dat_trang_thai(engine, viec_id, user_sub, "hong", ly_do_hong="loi_mo_hinh",
                              so_trang=tai_lieu.so_trang, chi_phi_usd=chi_phi)
            return
        if tl.vuot_chi_phi_thuc(chi_phi):
            # Ước sai vẫn phải bị bắt: ước là phòng ngừa, đối chiếu thật là
            # cưỡng chế. Kết quả bị bỏ chứ không lưu nửa vời.
            tl.dat_trang_thai(engine, viec_id, user_sub, "hong", ly_do_hong="vuot_tran_chi_phi",
                              so_trang=tai_lieu.so_trang, chi_phi_usd=chi_phi)
            return
        tl.luu_du_kien(engine, viec_id, hoi_thoai_id, ra["du_kien"])
        tl.dat_trang_thai(engine, viec_id, user_sub, "xong", so_trang=tai_lieu.so_trang,
                          chi_phi_usd=chi_phi)
    except (KhongDocDuoc, VuotTran) as e:
        ly_do = e.ly_do.value if isinstance(e, KhongDocDuoc) else f"vuot_tran_{e.tran}"
        tl.dat_trang_thai(engine, viec_id, user_sub, "hong", ly_do_hong=ly_do)
    except Exception:
        logger.exception("tai_lieu: việc %s hỏng", viec_id)
        tl.dat_trang_thai(engine, viec_id, user_sub, "hong", ly_do_hong="loi_he_thong")


@router.post("/tai-lieu", response_model=TaiLieuOut, status_code=201)
async def tai_len(
    nen: BackgroundTasks,
    tep: UploadFile = File(...),
    hoi_thoai_id: str | None = Form(None),
    loai: str | None = Form(None),
    nguoi: dict = Depends(nguoi_dung_bat_buoc),
) -> TaiLieuOut:
    """Nhận tài liệu, đọc tại chỗ nếu nhỏ, chuyển nền nếu lớn (FR-029/030).

    Không đặt trần thời gian: ra được kết quả quan trọng hơn ra nhanh (FR-032).
    Cái chặn chạy mất kiểm soát là trần chi phí mỗi tài liệu và trần số lần thử
    lại, không phải đồng hồ.
    """
    du_lieu = await tep.read()
    from src.services import hoi_thoai as ht

    # Phiên có sẵn được kiểm CHỦ ngay: phép kiểm này chỉ ĐỌC, và 404 phải đứng
    # trước 429 như `chi_tiet` — không tiết lộ phiên của người khác tồn tại chỉ
    # vì người gọi còn hạn mức hay không.
    #
    # Cuộc hội thoại phải là CỦA NGƯỜI TẢI LÊN. Mọi đường đọc và dọn sau này
    # (`don_vi_cua`, `tai_lieu_cua_hoi_thoai`, `xoa_theo_hoi_thoai`) khoá theo
    # `(hoi_thoai_id, user_sub)`, nên một tệp nhét vào phiên của người khác là
    # một dòng không ai dọn được nữa (FR-024).
    #
    # `if hoi_thoai_id:` chứ không `is not None:` — `Form(None)` chỉ trả `None`
    # khi khoá VẮNG MẶT, còn một người gọi gửi khoá rỗng sẽ rơi vào
    # `_uuid_hop_le("")` và nhận một 404 vô nghĩa thay vì một phiên mới.
    if hoi_thoai_id:
        hoi_thoai_id = _uuid_hop_le(hoi_thoai_id)
        if await run_in_threadpool(ht.lay_phien, nguoi["sub"], hoi_thoai_id) is None:
            raise HTTPException(status_code=404, detail=ht.LOI_KHONG_THAY)
    try:
        tl.kiem_kich_thuoc(len(du_lieu))
    except VuotTran as e:
        raise _loi_http(e) from e

    # FR-004 — cổng hạn mức chạy TRƯỚC khi phân tích tệp, cùng thứ tự `bao_ve`
    # đặt cho mọi endpoint tiêu tiền: kiểm quyền trước, làm việc sau.
    await _kiem_han_muc(nguoi)

    mo_ho = not hoi_thoai_id
    if mo_ho:
        # Đính kèm ở một đoạn chat chưa mở KHÔNG được là ngõ cụt. Phiên chỉ sinh
        # ra sau câu hỏi đầu, nên đòi `hoi_thoai_id` ở đây bắt người dùng hỏi một
        # câu vu vơ trước khi được đưa tờ giấy họ đang cầm. Tên tệp làm tiêu đề:
        # nó là thứ duy nhất ta biết về phiên này cho tới lượt hỏi đầu tiên.
        #
        # SAU hai cổng trên, không trước: mở phiên là một lần GHI, và `danh_sach`
        # không lọc phiên rỗng — một 422/429 mở phiên hộ sẽ để lại một dòng mang
        # tên tệp nằm mãi trong thanh bên mà không có gì dọn nó. Các cổng CÒN LẠI
        # (trần trang, định dạng, tệp hỏng, máy chủ bận) chỉ biết được khi đọc,
        # nên phiên mở hộ bị xoá cứng khi tệp bị từ chối (nhánh `except` dưới).
        hoi_thoai_id = await run_in_threadpool(
            ht.tao_phien, nguoi["sub"], tep.filename or "Tài liệu"
        )

    viec_id = await run_in_threadpool(
        tl.tao_viec,
        get_engine(),
        user_sub=nguoi["sub"],
        hoi_thoai_id=hoi_thoai_id,
        ten_tep=tep.filename or "",
        du_lieu=du_lieu,
        loai=loai,
    )

    # `tong_quat` KHÔNG có checklist (`config/checklist_tong_quat.yaml` không tồn
    # tại), nên `rut_du_kien` đi qua nó là `ValueError` ở `duong_dan_checklist` —
    # xem nhánh "đính kèm không phân tích" ở `_theo_loai`.
    nguoi_chon_loai = loai is not None and loai != ban_thao.LOAI_TONG_QUAT

    # Đọc ĐÚNG MỘT LẦN. Số trang quyết định đường đi, nên phải đọc trước khi
    # chọn đường; `_chay` nhận lại kết quả đó thay vì phân tích lần thứ hai.
    ten = (tep.filename or "").lower()
    khuon = None
    try:
        if ten.endswith(".pdf"):
            # Đếm trang TRƯỚC khi đọc: một bản scan 11 trang bị từ chối trước
            # khi OCR tốn công từng trang của nó.
            tl.kiem_so_trang(await run_in_threadpool(dung_trang.so_trang_pdf, du_lieu))
        tai_lieu = await run_in_threadpool(doc, tep.filename or "", du_lieu)
        # Số trang THẬT (quyết định 2026-09-26): LibreOffice dàn trang Word,
        # PDF tự có trang. Nó thay số trang khai báo/ước theo ký tự ở MỌI chỗ
        # sau — trần, đường nền, cột `so_trang` của việc đọc.
        khuon = await run_in_threadpool(dung_trang.khuon_goc, ten, du_lieu, tai_lieu)
        if khuon:
            tai_lieu = replace(tai_lieu, so_trang=khuon.so_trang)
        tl.kiem_so_trang(tai_lieu.so_trang)
        if khuon and nguoi_chon_loai and tl.vuot_tran_uoc(tai_lieu.so_ky_tu):
            # Lượt rút sắp bị trần chi phí từ chối (`_chay`, FR-036): không giữ
            # tệp, để bị từ chối vẫn là không để lại byte nào và không trừ hạn
            # mức (FR-038, `tl.da_dung_hom_nay` chỉ miễn việc không giữ tệp).
            khuon = None
        if khuon:
            # `.doc` quy đổi có thể nở ra; `ck_khuon_goc_so_byte` sẽ từ chối
            # bằng một lỗi 500, nên nói trần ra trước.
            tl.kiem_kich_thuoc(len(khuon.noi_dung))
            await run_in_threadpool(tl.luu_khuon_goc, get_engine(), viec_id, khuon.dinh_dang, khuon.noi_dung, khuon.kho)
    except (KhongDocDuoc, VuotTran, ChuyenDoiKhongSanSang) as e:
        # `ChuyenDoiKhongSanSang` (fix round 2) tiền tố `he_thong_` — cùng
        # khuôn `vuot_tran_*`, để `tai_lieu.da_dung_hom_nay` loại được CẢ HAI
        # khỏi hạn mức/ngày bằng một mẫu, không phải liệt kê từng giá trị.
        if isinstance(e, KhongDocDuoc):
            ly_do = e.ly_do.value
        elif isinstance(e, ChuyenDoiKhongSanSang):
            ly_do = f"he_thong_{e.ly_do}"
        else:
            ly_do = f"vuot_tran_{e.tran}"
        if mo_ho:
            # B5 (owner 2026-09-27): tệp bị từ chối không để lại hội thoại nào. Phiên
            # này do CHÍNH lần tải lên mở hộ, chưa có lượt nào: xoá cứng, và dòng việc
            # đọc đi theo khoá ngoại (`ON DELETE CASCADE`, migration 026) — lượt hỏng
            # ấy thôi tính hạn mức ngày, đúng như khi người dùng tự xoá hội thoại.
            await run_in_threadpool(ht.xoa_cung_phien_mo_ho, nguoi["sub"], hoi_thoai_id)
        else:
            await run_in_threadpool(tl.dat_trang_thai, get_engine(), viec_id, nguoi["sub"], "hong", ly_do_hong=ly_do)
        raise _loi_http(e, tep.filename or "") from e
    finally:
        # Tệp đã nằm ở `khuon_goc` (hoặc bị từ chối); request không cần cầm
        # thêm bản nào của nó.
        del du_lieu

    # Biểu diễn đã đọc được lưu cho MỌI tài liệu đọc được, TRƯỚC khi rẽ nhánh
    # theo loại — quyết định 2026-09-16. Lưu sau khi rẽ thì nhánh không có
    # checklist lại ra về tay không, đúng cái ngõ cụt việc này đang gỡ.
    await run_in_threadpool(tl.luu_don_vi, get_engine(), viec_id, tai_lieu.don_vi)
    # Bytes ảnh đi NGAY cạnh biểu diễn: mô tả ảnh nằm trong `don_vi` chỉ dựng
    # lại được khi bytes có mặt (quyết định 2026-09-18). Cùng đời hội thoại
    # với khuôn gốc ở trên: cả hai cascade theo dòng việc đọc.
    await run_in_threadpool(tl.luu_anh, get_engine(), viec_id, tai_lieu.anh_byte)
    chung = {
        "id": viec_id, "hoi_thoai_id": hoi_thoai_id,
        "so_trang": tai_lieu.so_trang, "co_ocr": tai_lieu.co_ocr,
        "ten_tep": tep.filename or "", "so_don_vi": len(tai_lieu.don_vi),
        "co_khuon_goc": khuon is not None,
    }

    # Người dùng không phải chọn loại văn bản từ một danh sách 29 mục trước khi
    # đọc được tờ giấy họ đang cầm. Giấy tờ pháp lý tự khai tên ở dòng đầu, nên
    # hệ thống đọc lấy — và khi không nhận ra thì tài liệu vẫn ĐỌC XONG: cái
    # thiếu là bộ trường của một checklist, không phải cả tài liệu. Trạng thái
    # `can_chon_loai` không còn được ghi; nó chỉ còn đọc được ở dòng cũ.
    # `tong_quat` (`nguoi_chon_loai` ở trên) đi qua `rut_du_kien` thì việc đọc bị
    # ghi `hong`/`loi_he_thong` và người dùng thấy "không phân tích được" dù tệp
    # đọc hoàn toàn bình thường. Bản thảo tổng quát rút dữ kiện ở
    # `hieu_tai_lieu` chứ không ở đây, nên nó đi CHÍNH đường "đính kèm không phân
    # tích" bên dưới: đọc xong, không `du_kien`, không gọi mô hình lần hai.
    doan = None if loai else phan_loai(tai_lieu.don_vi)
    loai = loai or (doan.loai if doan else None)
    return await _theo_loai(nen, viec_id, nguoi, hoi_thoai_id, loai, nguoi_chon_loai, doan, tai_lieu, chung)


async def _theo_loai(
    nen: BackgroundTasks,
    viec_id: str,
    nguoi: dict,
    hoi_thoai_id: str,
    loai: str | None,
    nguoi_chon_loai: bool,
    doan: KetQuaPhanLoai | None,
    tai_lieu: TaiLieuDaDoc,
    chung: dict,
) -> TaiLieuOut:
    """Nhánh theo loại văn bản sau khi tài liệu đã đọc và đã lưu — chung cho
    tải lên và rút lại (`doc_lai`), để hai đường không lệch nhau."""
    if loai is not None:
        await run_in_threadpool(tl.dat_loai, get_engine(), viec_id, nguoi["sub"], loai)

    # ĐÍNH KÈM KHÔNG PHÂN TÍCH. Lượt hỏi kế tiếp đi qua `hieu_tai_lieu` — nơi duy
    # nhất thấy chữ của tài liệu — và node đó tự rút dữ kiện, tự neo, tự ghi. Gọi
    # `rut_du_kien` ngay ở đây là trả tiền mô hình lần thứ hai cho cùng một tờ
    # giấy, trước khi người dùng kịp nói họ muốn gì với nó.
    #
    # Ngoại lệ duy nhất: người dùng TỰ chọn loại văn bản ("Rút dữ kiện theo mẫu"
    # → soạn thảo). Lúc đó việc rút chính là thứ họ vừa yêu cầu, nên nó chạy.
    if not nguoi_chon_loai:
        await run_in_threadpool(
            tl.dat_trang_thai, get_engine(), viec_id, nguoi["sub"], "xong",
            so_trang=tai_lieu.so_trang,
        )
        return TaiLieuOut(
            **chung, trang_thai="xong", chay_nen=False, loai=loai, du_kien=[],
            loai_ten=doan.ten if doan else None,
            loai_tu_doan=doan is not None,
            loai_can_cu=doan.can_cu if doan else None,
        )

    if tl.chay_nen(tai_lieu.so_trang):
        nen.add_task(_chay, viec_id, nguoi["sub"], hoi_thoai_id, loai, tai_lieu)
        return TaiLieuOut(
            **chung, trang_thai="dang_doc", chay_nen=True, loai=loai,
            loai_ten=doan.ten if doan else None,
            loai_tu_doan=doan is not None,
            loai_can_cu=doan.can_cu if doan else None,
        )

    await run_in_threadpool(_chay, viec_id, nguoi["sub"], hoi_thoai_id, loai, tai_lieu)
    ra = await chi_tiet(viec_id, nguoi)
    if doan:
        return ra.model_copy(
            update={"loai_ten": doan.ten, "loai_tu_doan": True, "loai_can_cu": doan.can_cu}
        )
    return ra


@router.get("/tai-lieu/{viec_id}", response_model=TaiLieuOut)
async def chi_tiet(viec_id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> TaiLieuOut:
    viec_id = _uuid_hop_le(viec_id)
    viec = await run_in_threadpool(tl.lay_viec, get_engine(), viec_id, nguoi["sub"])
    if not viec:
        raise HTTPException(status_code=404, detail=KHONG_THAY)
    du_kien = await run_in_threadpool(
        tl.du_kien_cua_hoi_thoai, get_engine(), str(viec["hoi_thoai_id"]), nguoi["sub"]
    )
    ly_do = viec.get("ly_do_hong")
    from src.agents.graph_soan_thao import load_checklist_cached

    ten = None
    if viec.get("loai"):
        try:
            ten = load_checklist_cached(viec["loai"]).ten
        except Exception:  # loại lạ trong DB không được làm hỏng cả phản hồi
            ten = None
    return TaiLieuOut(
        id=str(viec["id"]),
        hoi_thoai_id=str(viec["hoi_thoai_id"]),
        co_khuon_goc=bool(viec.get("co_khuon_goc")),
        trang_thai=viec["trang_thai"],
        so_trang=viec.get("so_trang"),
        chay_nen=tl.chay_nen(viec.get("so_trang")),
        ly_do_hong=ly_do,
        thong_diep=_THONG_DIEP.get(ly_do) if ly_do else None,
        du_kien=[DuKienOut(**{**d, "id": str(d["id"])}) for d in du_kien],
        co_ocr=any(d.get("nguon") == "tai_lieu_ocr" for d in du_kien),
        loai=viec.get("loai"),
        loai_ten=ten,
        ten_tep=viec.get("ten_tep") or "",
        so_don_vi=viec.get("so_don_vi") or 0,
        # Mô tả do mô hình viết; dòng lưu trước quyết định 2026-09-30 mục 11 đọc lại qua
        # các luật LUÔN bỏ (`thong_tin_noi_bo`, `cho_phep=None`).
        mo_ta=loc_noi_bo(viec.get("mo_ta"), None),
    )


@router.get("/tai-lieu/{viec_id}/don-vi", response_model=DonViTaiLieuOut)
async def don_vi(viec_id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> DonViTaiLieuOut:
    """Biểu diễn đã đọc của một tài liệu — nguồn của bảng đơn vị và của mọi neo
    người dùng bấm vào (quyết định 2026-09-16).

    Đây là endpoint DUY NHẤT trả nội dung tài liệu ra ngoài, nên nó đi qua đúng
    cổng của `chi_tiet`: tài liệu của người khác là 404, không tiết lộ tồn tại.
    """
    viec_id = _uuid_hop_le(viec_id)
    viec = await run_in_threadpool(tl.lay_viec, get_engine(), viec_id, nguoi["sub"])
    if not viec:
        raise HTTPException(status_code=404, detail=KHONG_THAY)
    don_vi = await run_in_threadpool(tl.don_vi_cua, get_engine(), viec_id, nguoi["sub"])
    return DonViTaiLieuOut(
        id=str(viec["id"]),
        ten_tep=viec.get("ten_tep") or "",
        so_trang=viec.get("so_trang"),
        don_vi=[
            DonViOut(
                chi_so=d.chi_so, trang=d.trang, offset_dau=d.offset_dau, noi_dung=d.noi_dung,
                nguon_chu=str(d.nguon_chu), do_tin=d.do_tin, vung=d.vung,
                bang=list(d.bang) if d.bang else None,
            )
            for d in (don_vi or [])
        ],
    )


@router.get("/tai-lieu/{viec_id}/anh/{ten}")
async def anh(viec_id: str, ten: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    """Bytes của MỘT ảnh đã tách khỏi tài liệu (quyết định 2026-09-18).

    Đường ra DUY NHẤT của media, nên nó gánh cả bốn hàng rào:

    1. CHỦ SỞ HỮU — `tl.anh_cua` lọc theo `user_sub` bằng JOIN ở tầng dữ liệu,
       và ảnh của người khác trả 404 y như `chi_tiet`/`don_vi`: không tiết lộ
       rằng tài liệu đó tồn tại. Con dấu và chữ ký là dữ liệu cá nhân của bên
       thứ ba, nên "không rời khỏi tài khoản đã tải lên" là ràng buộc, không
       phải một lời hứa.
    2. TÊN — chỉ nhận TÊN TỆP trần rồi tự ghép `word/media/`, nên không có
       đường nào để một `..%2f` đọc ra một part khác của zip. Tên trong
       `word/media/` là duy nhất, nên tên trần định danh đủ.
    3. KIỂU — `Content-Type` lấy từ cột `kieu`, vốn do `doc_tai_lieu._kieu_anh`
       nhận ra từ BYTES ĐẦU và bị `ck_anh_tai_lieu_kieu` khoá ở bốn kiểu ảnh.
       Cộng `X-Content-Type-Options: nosniff` để trình duyệt không tự đoán lại
       và không bao giờ chạy nội dung này như HTML/SVG.
    4. BỘ NHỚ ĐỆM — `private`: một proxy dùng chung không được giữ con dấu của
       một người rồi phát cho người khác.
    """
    viec_id = _uuid_hop_le(viec_id)
    if not _TEN_ANH.fullmatch(ten):
        raise HTTPException(status_code=404, detail=KHONG_THAY)
    ra = await run_in_threadpool(
        tl.anh_cua, get_engine(), viec_id, nguoi["sub"], f"word/media/{ten}"
    )
    if ra is None:
        raise HTTPException(status_code=404, detail=KHONG_THAY)
    kieu, du_lieu = ra
    return Response(
        content=du_lieu,
        media_type=kieu,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/tai-lieu/{viec_id}/trang")
async def trang(viec_id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> JSONResponse:
    """Khuôn gốc đúng như bản tải lên: `{"kho": [[rộng_pt, cao_pt], …],
    "trang": ["<base64 png>", …], "o": [...]}` — MỌI trang trong MỘT request,
    vì giới hạn theo IP là 10 request/60 giây (quyết định 2026-09-26). `o`: mỗi
    ô bộ áp tới được của tệp nguyên và chỗ nó nằm (`ban_thao.o_tren_trang`).

    Dựng lại mỗi lần gọi (LibreOffice cho docx, `pdftoppm` cho mọi trang);
    `kho` đọc từ CHÍNH PDF vừa vẽ, nên `kho[i]` luôn là khổ của `trang[i]`.
    Cùng bốn hàng rào của `anh`: chủ sở hữu lọc ở tầng dữ liệu (người khác và
    việc không có khuôn gốc đều 404), không nhận đường dẫn nào, `nosniff`,
    `private`.
    """
    viec_id = _uuid_hop_le(viec_id)
    k = await run_in_threadpool(tl.khuon_goc_cua, get_engine(), viec_id, nguoi["sub"])
    if k is None:
        raise HTTPException(status_code=404, detail=KHONG_THAY)
    do = ban_thao.ban_do(k["dinh_dang"], k["don_vi"], [])
    try:
        kho, png, vi_tri = await run_in_threadpool(
            dung_trang.dung, k["dinh_dang"], k["noi_dung"], nguoi["sub"], None, do
        )
    except (KhongDocDuoc, ChuyenDoiKhongSanSang) as e:
        raise _loi_http(e) from e
    return JSONResponse(
        {
            "kho": kho,
            "trang": [base64.b64encode(p).decode("ascii") for p in png],
            "o": ban_thao.o_tren_trang(k["dinh_dang"], k["don_vi"], [], vi_tri),
        },
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
    )


@router.post("/tai-lieu/{viec_id}/doc-lai", response_model=TaiLieuOut)
async def doc_lai(
    viec_id: str,
    body: DocLaiIn,
    nen: BackgroundTasks,
    nguoi: dict = Depends(nguoi_dung_bat_buoc),
) -> TaiLieuOut:
    """Rút lại theo loại văn bản trên CHÍNH việc đọc đã lưu (quyết định
    2026-09-26) — không tải lên lại, không mở việc mới, không trừ hạn mức, và
    tối đa `tl.TRAN_THU_LAI` lượt có trả tiền mỗi tài liệu (FR-037).

    Chọn loại sau khi đính kèm từng là tải lên lại cả tệp: một việc đọc mới và
    một lượt hạn mức mỗi lần người dùng đổi ý. Việc rút chỉ cần các đơn vị văn
    bản đã lưu (`don_vi`), nên nó chạy trên đó — kể cả với tài liệu không có
    khuôn gốc (ảnh, tài liệu cũ). Dữ kiện người dùng đã sửa vẫn thắng
    (`luu_du_kien` bỏ qua khoá đã có).
    """
    from src.agents.graph_soan_thao import cac_loai
    from src.services import bao_ve

    viec_id = _uuid_hop_le(viec_id)
    viec = await run_in_threadpool(tl.lay_viec, get_engine(), viec_id, nguoi["sub"])
    if not viec:
        raise HTTPException(status_code=404, detail=KHONG_THAY)
    if body.loai != ban_thao.LOAI_TONG_QUAT and body.loai not in cac_loai():
        raise HTTPException(status_code=422, detail="Loại văn bản này chưa có mẫu để rút dữ kiện.")
    don_vi = await run_in_threadpool(tl.don_vi_cua, get_engine(), viec_id, nguoi["sub"])
    chua_xong = HTTPException(status_code=409, detail="Tài liệu này chưa đọc xong nên chưa rút lại được.")
    if not don_vi:
        raise chua_xong

    tai_lieu = TaiLieuDaDoc(
        don_vi=don_vi,
        so_trang=viec.get("so_trang") or max(d.trang for d in don_vi),
        so_ky_tu=sum(len(d.noi_dung) for d in don_vi),
    )
    nguoi_chon_loai = body.loai != ban_thao.LOAI_TONG_QUAT
    if nguoi_chon_loai:
        # Mọi cổng của lượt trả tiền đứng TRƯỚC khi nhận việc: bị từ chối thì
        # dòng giữ nguyên (một tài liệu `xong` không rơi sang `hong` và ra khỏi
        # ngữ cảnh chat) và không tốn lượt FR-037. Ước chi phí đã biết từ đây;
        # trần chi phí ngày là cổng cuối trước ví tiền như mọi endpoint trả tiền.
        if tl.vuot_tran_uoc(tai_lieu.so_ky_tu):
            raise HTTPException(status_code=422, detail=THONG_DIEP_TRAN["chi_phi"])
        await run_in_threadpool(bao_ve.kiem_tran_chi_phi)
    # Nhận việc (`dang_doc`) TRƯỚC khi rút, ở cả đường tại chỗ lẫn đường nền:
    # chỉ kiểm `viec["trang_thai"]` thì dòng vẫn ghi `xong` suốt lượt rút, và lần
    # bấm thứ hai lọt qua chặn này để trả tiền mô hình thêm một lượt.
    try:
        nhan = await run_in_threadpool(tl.nhan_rut_lai, get_engine(), viec_id, nguoi["sub"], tra_phi=nguoi_chon_loai)
    except VuotTran as e:
        # FR-038 — nói đúng nguyên nhân. 429: đã hết lượt, không phải tệp hỏng.
        raise HTTPException(
            status_code=429,
            detail=f"Tài liệu này đã được rút lại đủ {e.gioi_han} lần. Hãy tải lên lại nếu cần rút tiếp.",
        ) from e
    if not nhan:
        raise chua_xong

    hoi_thoai_id = str(viec["hoi_thoai_id"])
    chung = {
        "id": viec_id,
        "hoi_thoai_id": hoi_thoai_id,
        "so_trang": tai_lieu.so_trang,
        "co_ocr": tai_lieu.co_ocr,
        "ten_tep": viec.get("ten_tep") or "",
        "so_don_vi": len(don_vi),
        "co_khuon_goc": bool(viec.get("co_khuon_goc")),
    }
    return await _theo_loai(nen, viec_id, nguoi, hoi_thoai_id, body.loai, nguoi_chon_loai, None, tai_lieu, chung)


@router.post("/tai-lieu/{viec_id}/huy", status_code=204)
async def huy(viec_id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> None:
    """FR-035 — người dùng huỷ một việc đang chạy."""
    viec_id = _uuid_hop_le(viec_id)
    if not await run_in_threadpool(tl.lay_viec, get_engine(), viec_id, nguoi["sub"]):
        raise HTTPException(status_code=404, detail=KHONG_THAY)
    await run_in_threadpool(tl.dat_trang_thai, get_engine(), viec_id, nguoi["sub"], "huy")


@router.patch("/tai-lieu/du-kien/{du_kien_id}", response_model=DuKienOut)
async def sua(du_kien_id: str, body: SuaDuKienIn, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> DuKienOut:
    """FR-013/014/015 — sửa giá trị, giữ trích gốc, đổi nhãn nguồn."""
    du_kien_id = _uuid_hop_le(du_kien_id)
    moi = await run_in_threadpool(tl.sua_du_kien, get_engine(), du_kien_id, nguoi["sub"], body.gia_tri)
    if not moi:
        raise HTTPException(status_code=404, detail=KHONG_THAY)
    return DuKienOut(**{**moi, "id": str(moi["id"])})


@router.delete("/tai-lieu/du-kien/{du_kien_id}", status_code=204)
async def xoa_mot(du_kien_id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> None:
    du_kien_id = _uuid_hop_le(du_kien_id)
    if not await run_in_threadpool(tl.xoa_du_kien, get_engine(), du_kien_id, nguoi["sub"]):
        raise HTTPException(status_code=404, detail=KHONG_THAY)


@router.delete("/tai-lieu/hoi-thoai/{hoi_thoai_id}", status_code=204)
async def xoa_het(hoi_thoai_id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> None:
    """FR-024 — xoá toàn bộ dữ kiện của một cuộc hội thoại bằng một thao tác."""
    hoi_thoai_id = _uuid_hop_le(hoi_thoai_id)
    await run_in_threadpool(tl.xoa_theo_hoi_thoai, get_engine(), hoi_thoai_id, nguoi["sub"])


@router.get("/tai-lieu/hoi-thoai/{hoi_thoai_id}/du-kien", response_model=SangSoanThaoOut)
async def sang_soan_thao(
    hoi_thoai_id: str,
    loai: str,
    ghi: bool = False,
    nguoi: dict = Depends(nguoi_dung_bat_buoc),
) -> SangSoanThaoOut:
    """FR-019/020/021 — tập dữ kiện đã duyệt, ở đúng hình dạng biểu mẫu soạn thảo.

    Endpoint này KHÔNG soạn gì cả: nó trả `facts` để người gọi nộp thẳng vào
    `POST /soan-thao` đang có. Dựng một đường soạn thảo thứ hai chỉ để nhận dữ
    kiện từ tài liệu sẽ tách trần số lần sửa và việc ghi traces ra hai chỗ.

    `con_thieu` tính bằng CHÍNH `gom_du_kien.con_thieu`, nên trường còn trống
    được liệt kê y hệt luồng hội thoại — không có bản sao thứ hai của "thế nào
    là còn thiếu".

    `ghi=true` thì ghi luôn vào trạng thái soạn thảo của cuộc hội thoại. Đây mới
    là chỗ FR-020 thành thật: biểu mẫu React (`KhongGianSoanThao`) có mô hình
    `Draft` riêng, KHÔNG chạy bằng bộ từ vựng `rules.yaml`. Thứ thật sự chạy
    bằng `facts` là đường soạn thảo TRONG HỘI THOẠI, nên "điền sẵn" nghĩa là
    lượt trò chuyện kế tiếp đã biết những gì tài liệu nói, và `gom_du_kien` chỉ
    còn phải hỏi phần thiếu.

    Dữ kiện người dùng đã nhập tay trong hội thoại được GIỮ: tài liệu bổ sung
    vào chỗ trống, không ghi đè thứ người dùng tự khẳng định.
    """
    from src.agents.nodes.gom_du_kien import con_thieu
    from src.services import hoi_thoai as ht

    hoi_thoai_id = _uuid_hop_le(hoi_thoai_id)
    du_kien = await run_in_threadpool(tl.du_kien_cua_hoi_thoai, get_engine(), hoi_thoai_id, nguoi["sub"])
    facts = tl.thanh_facts(du_kien)

    da_ghi = False
    if ghi and facts:
        dang = await run_in_threadpool(ht.soan_thao_cua_phien, nguoi["sub"], hoi_thoai_id) or {}
        cu = dict(dang.get("facts") or {})
        gop = {**facts, **cu}   # người dùng thắng: `cu` đè lên `facts` của tài liệu
        thieu = con_thieu(loai, gop)
        da_ghi = await run_in_threadpool(
            ht.ghi_soan_thao,
            nguoi["sub"],
            hoi_thoai_id,
            {**dang, "loai": loai, "facts": gop, "con_thieu": thieu, "du": not thieu},
        )
        facts = gop

    return SangSoanThaoOut(
        loai=loai, facts=facts, con_thieu=con_thieu(loai, facts), da_ghi_vao_hoi_thoai=da_ghi
    )
