"""`GET /van-ban/{doc_id}/hieu-luc` — phán quyết hiệu lực hai cấp (Pha 2).

Đây là chỗ DUY NHẤT giao diện được phép lấy nhãn hiệu lực, nên nó là chỗ duy
nhất phải bảo đảm nhãn đó không phải `documents.tinh_trang`.

`kiem-ke-fe-lovable.md`: FE Lovable render `tinh_trang` thô ở 11 vị trí, và bộ
lọc mặc định của nó (`tinhTrang: ["Còn hiệu lực"]`) GIẤU ĐI đúng bốn nghị định
lương tối thiểu mà KLAW phát hiện là đã bị thay — CSDL quốc gia vẫn đánh cả bốn
là `CHL`. Không endpoint nào trong file này trả `tinh_trang`; nó không nằm
trong model, không nằm trong câu SQL, và có một test quét cả response.

Hai cấp, vì bằng chứng có ở hai cấp:
  * VĂN BẢN — `effectivity.danh_gia_theo_id` (Mức 1 ngày hết hiệu lực, Mức 2 đồ
    thị quan hệ, Mức 3 `HHL1P`).
  * ĐIỀU KHOẢN — `effectivity.ap_sua_doi` trên `sua_doi_dieu_khoan` (Mức 4,
    nguồn Công báo/VBHN). Đây là tầng biến nhãn mù "hết hiệu lực một phần"
    thành "Khoản 1 Điều 139 bị sửa bởi 113/2025/QH15 từ 01/7/2026".

Không LLM, không embedding ⇒ không cổng `cong_bao_ve` (endpoint đọc thuần).
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.config import as_of_hieu_luc
from src.models.schemas import (
    DanChieuNoiBoOut,
    DieuKhoanHieuLucOut,
    HieuLucOut,
    NhomLienQuanOut,
    SuaBoiOut,
    VanBanHieuLucResponse,
    VanBanLienQuanOut,
    VanBanLienQuanResponse,
)
from src.services.db import get_engine
from src.services.effectivity import (
    Effectivity,
    ap_sua_doi,
    danh_gia_theo_id,
    nap_sua_doi_theo_van_ban,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# CỐ Ý không chọn `tinh_trang`: một cột không được đọc thì không có đường nào rò
# ra response. Cùng kỷ luật với `VanBanHieuLucResponse` (không có field đó).
_SQL_DOC = text("SELECT id, so_ky_hieu, ten FROM documents WHERE id = :doc_id")


def _ra(e: Effectivity) -> HieuLucOut:
    return HieuLucOut(verdict=e.verdict.value, tin_cay=e.tin_cay, ly_do=e.ly_do)


def _hieu_luc_sync(doc_id: str, as_of: date) -> VanBanHieuLucResponse:
    engine = get_engine()
    with engine.connect() as c:
        doc = c.execute(_SQL_DOC, {"doc_id": doc_id}).mappings().one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"văn bản '{doc_id}' không tồn tại")

    goc = danh_gia_theo_id(engine, doc_id, as_of)

    # `ap_sua_doi(goc, ...)` chứ không một phán quyết dựng riêng: Mức 4 là một
    # LỚP PHỦ làm phán quyết cấp văn bản CỤ THỂ hơn, không phải một cơ chế thứ
    # hai chạy song song. Nó cũng tự tôn trọng `_KHOA_O_CAP_VAN_BAN` — một Điều
    # của văn bản đã bị thay thế toàn bộ thì đã chết, bất kể footnote nói gì.
    dieu_khoan = [
        DieuKhoanHieuLucOut(
            provision_id=p["provision_id"], duong_dan=p["duong_dan"], cap=p["cap"],
            so_hieu_cap=p["so_hieu_cap"], tieu_de=p["tieu_de"],
            hieu_luc=_ra(ap_sua_doi(goc, ban_ghi, as_of)),
            sua_boi=[
                SuaBoiOut(
                    vi_tri=b["vi_tri"], so_ky_hieu=b["sua_boi_so_ky_hieu"],
                    duong_dan=b["sua_boi_duong_dan"], tu_ngay=b["tu_ngay"],
                    nguon=b["nguon"], do_tin_cay=b["do_tin_cay"],
                )
                for b in ban_ghi
            ],
        )
        for p, ban_ghi in nap_sua_doi_theo_van_ban(engine, doc_id)
    ]

    return VanBanHieuLucResponse(
        doc_id=doc["id"], so_ky_hieu=doc["so_ky_hieu"], bo_luat=doc["ten"],
        as_of=as_of, van_ban=_ra(goc), dieu_khoan=dieu_khoan,
    )


@router.get("/van-ban/{doc_id}/hieu-luc", response_model=VanBanHieuLucResponse)
async def hieu_luc(doc_id: str, as_of_date: date | None = None) -> VanBanHieuLucResponse:
    """Hiệu lực của `doc_id` tại `as_of_date` (mặc định: hôm nay), hai cấp.

    `dieu_khoan` chỉ liệt kê điều khoản CÓ bằng chứng cấp điều khoản — và cả tổ
    tiên của chúng trong cùng văn bản, vì câu trả lời thường dẫn "Điều 139"
    trong khi bản ghi neo ở "Điều 139 > Khoản 1"; bỏ tổ tiên là để một trích
    dẫn cấp Điều đi qua mà không cảnh báo gì. KHÔNG lan xuống anh em: Khoản 2
    không có bản ghi thì không đeo nhãn.

    Rỗng là kết quả HỢP LỆ (19.131/19.135 điều khoản không có bản ghi nào), và
    KHÔNG có nghĩa là không có phán quyết cấp văn bản.
    """
    return await run_in_threadpool(_hieu_luc_sync, doc_id, as_of_hieu_luc(as_of_date))


# ══ GET /van-ban/{doc_id}/lien-quan ═════════════════════════════════════════
#
# Ba nguồn khác nhau trộn trong `"references"`, và trộn chúng khi hiển thị là
# nói dối ba lần khác nhau — xem `tests/test_api/test_lien_quan.py` cho số đo.
#
# Nhãn quan hệ: 1/3/4/9/10/12 là mã MOJ (nguồn: `docs/superpowers/specs/
# 2026-08-27-klaw-design.md:98,200` và `plans/…-03-verifier.md:198` — cả hai
# trích thẳng từ API MOJ); 20-23 do dự án tự suy, `load_incoming_edges.
# QUAN_HE_HIEU_LUC` là chủ sở hữu tên của chúng.
NHAN_QUAN_HE = {
    1: "Bãi bỏ",
    3: "Căn cứ",
    4: "Dẫn chiếu",
    5: "Đình chỉ",
    8: "Hướng dẫn áp dụng",
    9: "Quy định chi tiết, hướng dẫn thi hành",
    10: "Sửa đổi, bổ sung",
    11: "Tạm ngưng",
    12: "Thay thế",
    20: "Sửa đổi, bổ sung",
    21: "Thay thế",
    22: "Văn bản quy định hết hiệu lực",
    23: "Văn bản quy định hết hiệu lực 1 phần",
}

# CHỈ dải 20-23 có chiều ngữ nghĩa đã đo (nhất quán 46/46 trong
# `relationships.parquet`, xem `effectivity.TAC_DONG`). Mã MOJ thì chưa.
LOAI_CHIEU_DA_DO = frozenset({20, 21, 22, 23})

GHI_CHU_NOI_BO = (
    "Dẫn chiếu chéo giữa các điều khoản TRONG chính văn bản này "
    "(`xref.py` sinh, loai 4 cấp điều khoản). Không phải văn bản liên quan — "
    "đo được 2.971/2.971 dòng nằm trong cùng một văn bản. Mở từng dẫn chiếu "
    "qua GET /api/v1/van-ban/{doc_id}?around=<provision_id>."
)

LIMIT_MOI_NHOM_MAX = 200

# Một câu, hai chiều. `doi_dien` là văn bản BÊN KIA của cạnh; `chieu` nói văn
# bản đang hỏi đứng ở đầu nào. LEFT JOIN (không JOIN): 273/626 cạnh cấp văn bản
# trỏ tới văn bản ngoài corpus, và JOIN thường sẽ nuốt mất chúng — giấu mất một
# nửa bản đồ quan hệ mà không một dòng nào báo.
#
# `from_provision_id IS NULL` lọc ra ĐÚNG cạnh cấp văn bản; cạnh cấp điều khoản
# đếm riêng ở `_SQL_NOI_BO`.
#
# `raw_text` là `docNum` MOJ khai — nguồn duy nhất của số hiệu khi văn bản đối
# diện không có trong corpus. Có thể là "Không số" (văn bản thật không có số
# hiệu); đó là sự thật MOJ khai, không phải lỗi cần che.
_SQL_LIEN_QUAN = text(
    "SELECT r.loai, 'di_ra' AS chieu, r.to_document_id AS doi_dien_id,"
    "       d.so_ky_hieu AS doi_dien_so_ky_hieu, d.ten AS doi_dien_ten, r.raw_text"
    ' FROM "references" r LEFT JOIN documents d ON d.id = r.to_document_id'
    " WHERE r.from_document_id = :doc_id AND r.from_provision_id IS NULL"
    " UNION ALL"
    " SELECT r.loai, 'di_vao', r.from_document_id, d.so_ky_hieu, d.ten, r.raw_text"
    ' FROM "references" r LEFT JOIN documents d ON d.id = r.from_document_id'
    " WHERE r.to_document_id = :doc_id AND r.from_provision_id IS NULL"
    " ORDER BY 1, 2, 4"
)

_SQL_NOI_BO = text(
    'SELECT count(*)::int FROM "references" r'
    " JOIN provisions p ON p.id = r.from_provision_id"
    " WHERE p.document_id = :doc_id"
)


def _mot_van_ban(r: dict, doc_id: str) -> VanBanLienQuanOut | None:
    """Một dòng cạnh → một văn bản đối diện, hoặc None nếu phải bỏ.

    Bỏ đúng hai ca, cả hai đều là dữ liệu vô nghĩa chứ không phải dữ liệu thiếu:
      * cạnh tự trỏ (văn bản là chính nó) — không phải "văn bản liên quan";
      * không có CẢ `so_ky_hieu` lẫn `raw_text` — không còn gì để định danh, và
        một dòng trống trong danh sách chỉ làm người đọc tưởng hệ thống hỏng.
    """
    if r["doi_dien_id"] == doc_id:
        return None
    trong_corpus = r["doi_dien_so_ky_hieu"] is not None
    so_ky_hieu = r["doi_dien_so_ky_hieu"] or (r["raw_text"] or "")
    if not so_ky_hieu:
        return None
    return VanBanLienQuanOut(
        # None khi ngoài corpus: `documents.id` tồn tại trong cạnh nhưng KHÔNG
        # có dòng nào, nên trả id đó ra là mời FE dựng một link 404.
        doc_id=r["doi_dien_id"] if trong_corpus else None,
        so_ky_hieu=so_ky_hieu,
        bo_luat=r["doi_dien_ten"],
        trong_corpus=trong_corpus,
    )


def _lien_quan_sync(doc_id: str, limit_moi_nhom: int) -> VanBanLienQuanResponse:
    with get_engine().connect() as c:
        doc = c.execute(_SQL_DOC, {"doc_id": doc_id}).mappings().one_or_none()
        if doc is None:
            raise HTTPException(status_code=404, detail=f"văn bản '{doc_id}' không tồn tại")
        canh = [dict(r) for r in c.execute(_SQL_LIEN_QUAN, {"doc_id": doc_id}).mappings().all()]
        noi_bo = c.execute(_SQL_NOI_BO, {"doc_id": doc_id}).scalar_one()

    gom: dict[tuple[int, str], list[VanBanLienQuanOut]] = {}
    for r in canh:
        v = _mot_van_ban(r, doc_id)
        if v is None:
            continue
        gom.setdefault((r["loai"], r["chieu"]), []).append(v)

    nhom = [
        NhomLienQuanOut(
            loai=loai,
            # Mã lạ vẫn hiện ra, KHÔNG bị bỏ im lặng: một mã chưa có tên là dấu
            # hiệu loader mới đã nạp thứ chưa ai đặt tên, và giấu nó đi làm cả
            # nhóm quan hệ biến mất khỏi giao diện mà không ai biết.
            nhan=NHAN_QUAN_HE.get(loai, f"quan hệ mã {loai} (chưa đặt tên)"),
            chieu=chieu,
            chieu_da_do=loai in LOAI_CHIEU_DA_DO and loai in NHAN_QUAN_HE,
            so_luong=len(vs[:limit_moi_nhom]),
            van_ban=vs[:limit_moi_nhom],
        )
        for (loai, chieu), vs in sorted(gom.items())
    ]
    return VanBanLienQuanResponse(
        doc_id=doc["id"], so_ky_hieu=doc["so_ky_hieu"], bo_luat=doc["ten"],
        nhom=nhom,
        dan_chieu_noi_bo=DanChieuNoiBoOut(so_luong=noi_bo, ghi_chu=GHI_CHU_NOI_BO),
    )


@router.get("/van-ban/{doc_id}/lien-quan", response_model=VanBanLienQuanResponse)
async def lien_quan(
    doc_id: str,
    limit_moi_nhom: int = Query(default=50, ge=1, le=LIMIT_MOI_NHOM_MAX),
) -> VanBanLienQuanResponse:
    """Văn bản liên quan, nhóm theo (quan hệ, chiều).

    `so_luong` đếm từ chính danh sách trả về — nếu một nhóm bị cắt bởi
    `limit_moi_nhom` thì con số phải nói ra danh sách đang có bao nhiêu, không
    phải tổng trong DB: hai số khác nhau trong một response mà không trường nào
    phân biệt là cách chắc chắn để giao diện hiện "8 văn bản" rồi liệt 5.
    """
    return await run_in_threadpool(_lien_quan_sync, doc_id, limit_moi_nhom)
