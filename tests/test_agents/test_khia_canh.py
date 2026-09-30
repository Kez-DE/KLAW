"""Một câu hỏi meta mang được NHIỀU ý, và mỗi ý phải được trả lời.

ĐO ĐƯỢC 2026-09-16 (ex.md §1), câu hỏi:

    bạn làm được gì, có những bộ luật gì, có những lĩnh vực pháp luật gì

nhận về đúng một bài giới thiệu dài, trong đó danh sách Bộ luật và lĩnh vực là
chuỗi VIẾT CỨNG trong mẫu. Hai ý sau của người hỏi rơi mất, và phần phạm vi sẽ
nói sai ngay lần nạp kho tiếp theo.

Nhóm test này canh hai thứ, tách khỏi `test_gioi_thieu.py` (vốn canh từng dạng
câu đơn): bộ phân rã khía cạnh, và câu dự phòng ghép từ bảng dữ kiện đọc kho lúc
chạy (`cau_gioi_thieu`). Từ quyết định 2026-09-30 mục 1 model viết lời đáp từ
chính bảng đó; câu dự phòng là thứ người đọc thấy khi model lỗi hay bị lọc hết.

Fixture kho dựng tại chỗ bằng đúng hình dạng dòng của `nap_kho` — KHÔNG import
từ `test_kho.py`: một test file import một test file khác thì một thay đổi
fixture bên kia làm đỏ bên này với lý do không đọc được.
"""

import re

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.gioi_thieu import (
    HOI_TIEP_KHO,
    THIEU_KHO,
    bang_du_kien,
    can_kho,
    cau_gioi_thieu,
    khia_canh,
)
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from src.services.kho import CAU_GIOI_HAN
from src.services.llm import generate_model


def _vb(so, ten, loai="Bộ luật", depth="deep", verdict=V.con_hieu_luc, linh_vuc=None):
    return {"so_ky_hieu": so, "ten": ten, "loai_van_ban": loai, "depth": depth,
            "hieu_luc": Effectivity(verdict, "cao", "không có tín hiệu chấm dứt nào"),
            "linh_vuc": linh_vuc}


# Tên lĩnh vực lấy NGUYÊN VĂN từ DB thật (`select distinct linh_vuc from
# documents`): chúng là nhãn hành chính dài, không phải ba chữ gọn — câu văn
# xuôi phải đọc được với chính chúng.
_LV_SAU = "Lao động - Thương binh và Xã hội"
_LV_GOC = "Đất đai"
_LV_NONG = "Sở hữu trí tuệ"

BO_LUAT = [
    _vb("91/2015/QH13", "Bộ luật Dân sự số 91/2015/QH13"),
    _vb("100/2015/QH13", "Bộ luật Hình sự số 100/2015/QH13"),
    _vb("92/2015/QH13", "Bộ luật Tố tụng dân sự số 92/2015/QH13"),
    _vb("101/2015/QH13", "Bộ luật Tố tụng hình sự số 101/2015/QH13"),
    # Chữ "Luật" viết hoa giữa tên — đúng như dòng thật trong `documents`.
    _vb("45/2019/QH14", "Bộ Luật lao động số 45/2019/QH14", linh_vuc=_LV_SAU),
    _vb("95/2015/QH13", "Bộ luật Hàng hải số 95/2015/QH13"),
]
TEN_NGAN = ["Dân sự", "Hình sự", "Tố tụng dân sự", "Tố tụng hình sự", "Lao động", "Hàng hải"]

KHO = [
    *BO_LUAT,
    # Bản đã bị thay: vẫn trong kho, KHÔNG được vào danh sách đang dùng.
    _vb("10/2012/QH13", "Bộ luật Lao động số 10/2012/QH13", depth="shallow",
        verdict=V.bi_thay_the),
    _vb("145/2020/NĐ-CP", "Nghị định 145/2020/NĐ-CP", loai="Nghị định", linh_vuc=_LV_SAU),
    _vb("10/2020/TT-BLĐTBXH", "Thông tư 10/2020/TT-BLĐTBXH", loai="Thông tư", linh_vuc=_LV_SAU),
    _vb("45/2013/QH13", "Luật Đất đai số 45/2013/QH13", loai="Luật", linh_vuc=_LV_GOC),
    _vb("50/2005/QH11", "Luật Sở hữu trí tuệ số 50/2005/QH11", loai="Luật",
        depth="shallow", linh_vuc=_LV_NONG),
]

CAU_MAU = "bạn làm được gì, có những bộ luật gì, có những lĩnh vực pháp luật gì"


# ══ §7.1 Câu đơn ════════════════════════════════════════════════════════════


def test_lam_duoc_gi_chi_tra_nang_luc_khong_do_ca_kho():
    """§7.1.1 — và đây là ca đã đo được lỗi: bài năng lực cũ tự liệt kê sáu tên
    Bộ luật cùng bốn tên lĩnh vực."""
    assert khia_canh("bạn làm được gì") == ["nang_luc"]
    ans = cau_gioi_thieu("bạn làm được gì", KHO)
    for ten in TEN_NGAN:
        assert ten not in ans, f"bài năng lực không được liệt kê Bộ luật {ten}"
    assert _LV_SAU not in ans
    assert CAU_GIOI_HAN not in ans, "không có khối phạm vi thì không có câu giới hạn"


def test_hoi_bo_luat_liet_ke_dung_tu_fixture():
    """§7.1.2 — sáu tên đọc TỪ KHO, và bản đã bị thay không lọt vào."""
    assert khia_canh("có những Bộ luật gì") == ["bo_luat"]
    ans = cau_gioi_thieu("có những Bộ luật gì", KHO)
    assert "Tôi hiện có 6 Bộ luật: " + ", ".join(TEN_NGAN[:-1]) + " và " + TEN_NGAN[-1] + "." in ans
    assert "10/2012" not in ans


def test_hoi_linh_vuc_liet_ke_dung_linh_vuc_va_do_sau():
    """§7.1.3 — độ sâu suy từ `depth`/`loai_van_ban`, không viết cứng theo tên
    lĩnh vực."""
    assert khia_canh("có những lĩnh vực pháp luật gì") == ["linh_vuc"]
    ans = cau_gioi_thieu("có những lĩnh vực pháp luật gì", KHO)
    for lv in (_LV_SAU, _LV_GOC, _LV_NONG):
        assert lv in ans
    assert f"{_LV_SAU} là lĩnh vực sâu nhất" in ans
    assert "1 lĩnh vực khác hiện mới có luật gốc." in ans
    # Khoá `""` (văn bản chưa gắn lĩnh vực) không được thành một tên rỗng.
    assert "gồm , " not in ans and " và ." not in ans


def test_hoi_nguon_chi_tra_nguon_va_gioi_han_lien_quan():
    """§7.1.4 — không kèm danh sách Bộ luật, không kèm bảng model."""
    assert khia_canh("dữ liệu lấy từ đâu") == ["nguon"]
    ans = cau_gioi_thieu("dữ liệu lấy từ đâu", KHO)
    assert "cơ sở dữ liệu quốc gia" in ans.lower()
    assert generate_model() not in ans
    for ten in TEN_NGAN:
        assert ten not in ans
    # Quyết định 2026-09-30 mục 5: câu giới hạn phạm vi chỉ đi với câu trả lời về
    # số liệu văn bản — hỏi nguồn không phải hỏi số liệu.
    assert CAU_GIOI_HAN not in ans


def test_hoi_model_chi_tra_model_va_khong_ro_ri():
    """§7.1.5 — giữ nguyên phép canh rò rỉ của `test_gioi_thieu.py` ở tầng
    khía cạnh: "model của bạn là gì" không được kéo theo danh tính."""
    assert khia_canh("model của bạn là gì") == ["model"]
    ans = cau_gioi_thieu("model của bạn là gì", KHO)
    assert "http" not in ans and "sk-" not in ans
    assert "api key" not in ans.lower()


# ══ §7.2 Câu ghép ═══════════════════════════════════════════════════════════


def test_cau_mau_tra_du_ba_y_dung_thu_tu():
    """§7.2.1 — chính câu hỏi mở ra cả đợt này."""
    assert khia_canh(CAU_MAU) == ["nang_luc", "bo_luat", "linh_vuc"]
    ans = cau_gioi_thieu(CAU_MAU, KHO)
    assert ans.startswith(bang_du_kien(CAU_MAU, KHO)["viec"])
    for ten in TEN_NGAN:
        assert ten in ans, f"thiếu Bộ luật {ten}"
    for lv in (_LV_SAU, _LV_GOC, _LV_NONG):
        assert lv in ans, f"thiếu lĩnh vực {lv}"
    # Thứ tự khối theo đúng thứ tự người hỏi (FR-013).
    assert ans.index("Tôi hiện có 6 Bộ luật") < ans.index("Các lĩnh vực đang phủ")
    assert ans.endswith(HOI_TIEP_KHO)
    assert ans.count(CAU_GIOI_HAN) == 1


def test_nang_luc_va_nguon_KHONG_keo_theo_danh_sach_luat():
    """§7.2.2."""
    assert khia_canh("bạn làm được gì và dữ liệu lấy từ đâu") == ["nang_luc", "nguon"]
    ans = cau_gioi_thieu("bạn làm được gì và dữ liệu lấy từ đâu", KHO)
    for ten in TEN_NGAN:
        assert ten not in ans
    assert "cơ sở dữ liệu quốc gia" in ans.lower()


def test_bo_luat_va_soan_thao_tra_du_hai_phan():
    """§7.2.3."""
    cau = "có Bộ luật nào và soạn được văn bản gì"
    assert khia_canh(cau) == ["bo_luat", "soan_thao"]
    ans = cau_gioi_thieu(cau, KHO)
    assert "Tôi hiện có 6 Bộ luật" in ans
    assert "Tôi soạn được" in ans


def test_dao_thu_tu_cau_hoi_thi_dao_thu_tu_khoi():
    """§7.2.4 — thứ tự khối theo người hỏi, không theo một thứ tự cố định."""
    xuoi = cau_gioi_thieu("có Bộ luật nào và soạn được văn bản gì", KHO)
    nguoc = cau_gioi_thieu("soạn được văn bản gì và có Bộ luật nào", KHO)
    assert xuoi.index("Tôi hiện có") < xuoi.index("Tôi soạn được")
    assert nguoc.index("Tôi soạn được") < nguoc.index("Tôi hiện có")


# ══ §7.3 Dữ liệu động ═══════════════════════════════════════════════════════


def test_them_bo_luat_vao_fixture_thi_cau_tra_loi_tu_co_ten_moi():
    """§7.3.1 — không sửa một mẫu nào."""
    them = _vb("60/2030/QH20", "Bộ luật Môi trường số 60/2030/QH20")
    ans = cau_gioi_thieu("có những Bộ luật gì", [*KHO, them])
    assert "Tôi hiện có 7 Bộ luật" in ans and "Môi trường" in ans


def test_danh_dau_bi_thay_the_thi_bo_luat_bien_khoi_cau_tra_loi():
    """§7.3.2."""
    bo = [dict(r) for r in KHO]
    bo[0]["hieu_luc"] = Effectivity(V.bi_thay_the, "cao", "bị 1/2030/QH20 thay thế")
    ans = cau_gioi_thieu("có những Bộ luật gì", bo)
    assert "Tôi hiện có 5 Bộ luật" in ans and "Dân sự" not in ans


def test_them_linh_vuc_moi_thi_cau_tra_loi_tu_co_linh_vuc_moi():
    """§7.3.3."""
    them = _vb("20/2020/QH14", "Luật Xây dựng số 20/2020/QH14", loai="Luật",
               linh_vuc="Xây dựng")
    assert "Xây dựng" in cau_gioi_thieu("có những lĩnh vực gì", [*KHO, them])


def test_do_sau_linh_vuc_doi_theo_depth_va_loai_van_ban():
    """§7.3.4 — cùng logic độ sâu của Bảng 2, không một bảng nhãn thứ hai."""
    day_du = [*KHO,
              _vb("21/2020/NĐ-CP", "Nghị định M", loai="Nghị định", linh_vuc=_LV_GOC),
              _vb("22/2020/TT-BTNMT", "Thông tư N", loai="Thông tư", linh_vuc=_LV_GOC)]
    ans = cau_gioi_thieu("có những lĩnh vực gì", day_du)
    assert f"{_LV_GOC} là lĩnh vực sâu nhất" in ans or f"{_LV_SAU}, {_LV_GOC} là lĩnh vực sâu nhất" in ans


# ══ Hình dạng chung ═════════════════════════════════════════════════════════


def _cac_cau(van: str) -> list[str]:
    """Câu người đọc thấy, bỏ những mẩu quá ngắn để không đếm nhầm nhãn."""
    cac = [c.strip(" -") for dong in van.splitlines()
           for c in re.split(r"(?<=[.?!])\s+", dong)]
    return [c for c in cac if len(c) > 20]


def test_khong_cau_nao_xuat_hien_hai_lan():
    """FR-011 — cùng một năng lực, cảnh báo hay giới hạn không được nằm ở hai
    khối trong cùng câu trả lời."""
    for cau in (CAU_MAU, "bạn là ai và bạn làm được gì",
                "bạn làm được gì, kho có gì, dữ liệu lấy từ đâu",
                "có Bộ luật nào và soạn được văn bản gì"):
        cac = _cac_cau(cau_gioi_thieu(cau, KHO))
        lap = [c for c in cac if cac.count(c) > 1]
        assert lap == [], f"{cau!r} lặp câu: {lap}"


def test_khong_lo_ten_model_khi_khong_ai_hoi():
    """FR-012 — tên model, tên node, số tầng chỉ hiện khi hỏi trực tiếp."""
    ans = cau_gioi_thieu(CAU_MAU, KHO)
    assert generate_model() not in ans


def test_chi_mot_cau_moi_tiep_tuc_va_no_dung_cuoi():
    """FR-015 — và không phải một lời mời chung chung."""
    ans = cau_gioi_thieu(CAU_MAU, KHO)
    assert ans.count("?") == 1 and ans.endswith(HOI_TIEP_KHO)
    # `DANH_TINH` tự kết bằng một câu hỏi — không được dán câu thứ hai lên nó.
    assert cau_gioi_thieu("bạn là ai", KHO).count("?") == 1


def test_thieu_kho_thi_noi_that_MOT_LAN_chu_khong_bia_ten():
    """Khía cạnh kho được hỏi mà chỗ gọi chưa nạp kho: nói thẳng, một câu, và
    KHÔNG một cái tên nào được bịa ra."""
    ans = cau_gioi_thieu("có những bộ luật gì và lĩnh vực nào")
    assert ans.count(THIEU_KHO) == 1
    for ten in TEN_NGAN:
        assert ten not in ans
    assert CAU_GIOI_HAN not in ans, "không có phạm vi nào được nêu thì không có gì để giới hạn"


def test_chao_dan_vao_chi_o_luot_dau():
    """ex.md §4.3 — lượt nối tiếp không chào lại."""
    cau = "chào bạn, bạn làm được gì"
    assert cau_gioi_thieu(cau, KHO).startswith("Chào bạn. ")
    assert cau_gioi_thieu(cau, KHO, luot_dau=False) == cau_gioi_thieu("bạn làm được gì", KHO)


def test_can_kho_dung_cho_ba_khia_canh_kho():
    """Chỗ gọi dùng `can_kho` để nạp kho ĐÚNG MỘT LẦN (FR-014)."""
    assert can_kho(["bo_luat"]) and can_kho(["linh_vuc"]) and can_kho(["kho"])
    assert not can_kho(["nang_luc", "nguon", "model", "soan_thao", "danh_tinh"])


def test_assemble_khong_co_model_van_tra_loi_cau_hoi_ghep():
    """Chỗ gọi trực tiếp không có model và chưa nạp kho: vẫn một lời đáp từ bảng,
    khía cạnh kho nhận `THIEU_KHO` (quyết định 2026-09-30 mục 1 thay FR-005)."""
    st = assemble({"query": CAU_MAU, "intent": "gioi_thieu"}, {}, None, "")
    assert st["result_type"] == ResultType.gioi_thieu
    assert st["answer"] and THIEU_KHO in st["answer"]
