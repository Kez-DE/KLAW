"""Điều KLAW nhớ về TÀI KHOẢN (Phase 12, R1): dữ kiện cá nhân và thói quen soạn.

Bảng `bo_nho_tai_khoan` (migration 034) chỉ NHỚ. Không hàm nào ở đây đọc để
điền vào văn bản — đó là việc của lượt người dùng yêu cầu (R4), và một đường
tự điền là một cách làm SAI yêu cầu, không phải một tiện ích thêm.

Khác `bo_nho.py` (hồ sơ tình huống pháp lý, chỉ Pro, lưới chặn loại định danh):
ở đây tên và mã sinh viên là đúng thứ phải giữ, nên không có lưới chặn định
danh, chỉ có giới hạn độ dài và khoá dạng định danh máy. Mọi hàm lọc theo
`user_sub` — ký ức của tài khoản này không bao giờ đọc được từ phiên của tài
khoản khác, và test chứng minh điều đó thay cho một dòng chú thích.
"""

import re

from sqlalchemy import text

from src.services.db import get_engine

LOAI = ("ca_nhan", "thoi_quen")
GIA_TRI_TOI_DA = 200
# Nhãn để giao diện in; khoá lạ (người dùng khai một điều chưa lường) rơi về
# chính tên khoá thay vì bị từ chối — nhớ được vẫn hơn mất.
NHAN_KHOA = {
    "ho_ten": "Họ và tên",
    "ma_sv": "Mã sinh viên",
    "lop": "Lớp",
    "nganh": "Ngành",
    "noi_thuc_tap": "Nơi thực tập",
    "van_phong": "Văn phong",
    "xung_ho": "Cách xưng hô",
    "mau_hay_dung": "Mẫu hay dùng",
}
_RE_KHOA = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

_COT = "id::text AS id, loai, khoa, gia_tri, nguon_hoi_thoai_id::text AS nguon_hoi_thoai_id, cap_nhat_luc"
# Trạng thái trả về phải sinh ra từ CHÍNH lệnh ghi. Một `SELECT ... FOR UPDATE`
# đọc trước không khoá được dòng CHƯA tồn tại, nên hai lượt ghi đầu tiên cùng
# (sub, loai, khoa) sẽ cùng thấy "chưa có" và cùng báo "moi" — người dùng nghe
# "đã nhớ" hai lần. Ở đây `ON CONFLICT` tự khoá dòng đụng độ: `xmax = 0` chỉ
# đúng với dòng vừa CHÈN, còn `WHERE` chặn nhánh sửa khi giá trị y hệt nên
# lệnh không trả dòng nào. Ba kết cục phân biệt được bằng một lượt đi Postgres,
# không còn khoảng hở giữa đọc và ghi.
#
# Đổi lại: giá trị không đổi thì `nguon_hoi_thoai_id` và `cap_nhat_luc` giữ
# nguyên — đúng nghĩa "giu" (không có gì đổi), và tránh một lượt ghi thừa.
_SQL_GHI = text(
    "INSERT INTO bo_nho_tai_khoan (user_sub, loai, khoa, gia_tri, nguon_hoi_thoai_id)"
    " VALUES (CAST(:sub AS uuid), :loai, :khoa, :gia_tri, CAST(:pid AS uuid))"
    " ON CONFLICT (user_sub, loai, khoa) DO UPDATE SET gia_tri = EXCLUDED.gia_tri,"
    " nguon_hoi_thoai_id = EXCLUDED.nguon_hoi_thoai_id, cap_nhat_luc = now()"
    " WHERE bo_nho_tai_khoan.gia_tri IS DISTINCT FROM EXCLUDED.gia_tri"
    " RETURNING (xmax = 0) AS la_moi"
)
_SQL_LIET_KE = text(f"SELECT {_COT} FROM bo_nho_tai_khoan WHERE user_sub = CAST(:sub AS uuid) ORDER BY loai, khoa")
_SQL_XOA_MOT = text("DELETE FROM bo_nho_tai_khoan WHERE id = CAST(:id AS uuid) AND user_sub = CAST(:sub AS uuid)")
_SQL_XOA_HET = text("DELETE FROM bo_nho_tai_khoan WHERE user_sub = CAST(:sub AS uuid)")


def ghi(sub: str, loai: str, khoa: str, gia_tri: str, nguon_hoi_thoai_id: str | None = None) -> str:
    """Upsert một dữ kiện. Trả `"moi"` (chưa từng có), `"doi"` (đã có, giá trị
    khác) hay `"giu"` (đã có, y hệt) — người gọi (R3) chỉ nói "đã nhớ" khi
    kết quả khác `"giu"`. `ValueError` khi loai/khoa/gia_tri không hợp lệ:
    đây là biên nhận dữ liệu từ lượt người dùng, không tin đầu vào."""
    g = " ".join(str(gia_tri or "").split())
    if loai not in LOAI or not _RE_KHOA.match(khoa or "") or not g or len(g) > GIA_TRI_TOI_DA:
        raise ValueError("loai, khoa hoặc gia_tri không hợp lệ")
    with get_engine().begin() as c:
        la_moi = c.execute(
            _SQL_GHI, {"sub": sub, "loai": loai, "khoa": khoa, "gia_tri": g, "pid": nguon_hoi_thoai_id}
        ).scalar_one_or_none()
    # Không dòng nào trả về = `WHERE` đã chặn nhánh sửa = giá trị y hệt cái đang có.
    if la_moi is None:
        return "giu"
    return "moi" if la_moi else "doi"


def liet_ke(sub: str) -> list[dict]:
    """Mọi dữ kiện của tài khoản, bất kể hội thoại nguồn — ký ức là của tài khoản."""
    with get_engine().connect() as c:
        rows = c.execute(_SQL_LIET_KE, {"sub": sub}).mappings().all()
    return [{**r, "nhan": NHAN_KHOA.get(r["khoa"], r["khoa"])} for r in rows]


def xoa_mot(sub: str, id: str) -> bool:
    """Xoá THẬT một dòng của chính `sub`. False khi không có dòng nào khớp — kể cả
    khi `id` tồn tại nhưng thuộc người khác, để tầng API trả 404 chứ không 403."""
    with get_engine().begin() as c:
        return c.execute(_SQL_XOA_MOT, {"id": id, "sub": sub}).rowcount > 0


def xoa_het(sub: str) -> int:
    with get_engine().begin() as c:
        return c.execute(_SQL_XOA_HET, {"sub": sub}).rowcount
