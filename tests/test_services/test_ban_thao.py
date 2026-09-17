import uuid

import pytest
from sqlalchemy import text

from src.services import ban_thao, bao_ve, hoi_thoai
from src.services.db import get_engine

pytestmark = pytest.mark.integration
KET = {
    "document": "# ĐƠN\nMục 1",
    "clauses": [{"stt": 1, "key": "nguoi_lam_don", "noi_dung": "Tôi là A"}],
    "audit_report": {"findings": [], "completeness": 1.0},
}


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM ban_thao WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def test_tao_sua_lui_va_tran_sua(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A", "ngay_nghi": "01/10/2026"}, KET)
    assert bt["phien_ban"] == 1 and bt["document"].startswith("# ĐƠN")
    bt2 = ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "ngay_nghi": "15/10/2026"}, {**KET, "document": "# ĐƠN v2"})
    assert bt2["phien_ban"] == 2 and bt2["phien_ban_truoc"][-1]["phien_ban"] == 1
    assert ban_thao.doi_so_voi(bt, bt2) == ["ngay_nghi"]
    bt3 = ban_thao.lui(nguoi, bt["id"])
    assert bt3["phien_ban"] == 1 and bt3["document"].startswith("# ĐƠN\n")
    # Phase 4 (D11, R2): `lui` không còn xoá hẳn bản bị rời đi (v2) — nó vẫn
    # đọc được trong lịch sử, cùng nội dung và một `luc` mới gắn vào.
    assert [t["phien_ban"] for t in bt3["phien_ban_truoc"]] == [2]
    assert bt3["phien_ban_truoc"][0]["document"] == bt2["document"]
    assert bt3["phien_ban_truoc"][0]["luc"]
    assert ban_thao.sua("00000000-0000-0000-0000-000000000000", bt["id"], {}, KET) is None
    for i in range(ban_thao.TRAN_SUA):
        ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "ngay_nghi": f"{i + 1}/10/2026"}, KET)
    assert len(ban_thao.chi_tiet(nguoi, bt["id"])["phien_ban_truoc"]) == ban_thao.TRAN_SUA
    items, tong = ban_thao.danh_sach(nguoi, 10, 0)
    assert tong == 1 and items[0]["id"] == bt["id"] and items[0]["loai"] == "don_xin_nghi_viec"
    assert ban_thao.xoa_mem(nguoi, bt["id"]) is True and ban_thao.chi_tiet(nguoi, bt["id"]) is None


def test_lui_lien_tiep_di_den_ban_cu_nhat_va_tu_choi_khi_het(nguoi):
    """`lui` là một BƯỚC ĐI LÙI, không phải bật qua bật lại: tạo, sửa hai lần, lùi
    hai lần phải đi dần về ĐÚNG bản gốc (v1), không dừng lại ở v2 rồi bật ngược
    lại v3. Và khi đã ở bản cũ nhất, lùi thêm phải TỪ CHỐI (trả về y nguyên),
    không làm gì bất ngờ — dù giờ (Phase 4, R2) lịch sử không còn rỗng ở đó,
    vì v2 và v3 bị bỏ lại vẫn được GIỮ (không còn "rỗng" nghĩa là "hết đường lùi";
    "hết đường lùi" giờ nghĩa là không còn mục nào mang số NHỎ HƠN bản đang đứng)."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    v1 = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "2"}, {**KET, "document": "# ĐƠN v2"})
    ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "3"}, {**KET, "document": "# ĐƠN v3"})

    ve_v2 = ban_thao.lui(nguoi, v1["id"])
    assert ve_v2["phien_ban"] == 2 and ve_v2["document"] == "# ĐƠN v2"

    ve_v1 = ban_thao.lui(nguoi, v1["id"])
    assert ve_v1["phien_ban"] == 1
    assert (ve_v1["document"], ve_v1["facts"], ve_v1["clauses"], ve_v1["audit"]) == (
        v1["document"],
        v1["facts"],
        v1["clauses"],
        v1["audit"],
    )
    # R2's proof: cả v2 lẫn v3 (hai bản đã bị "lùi" qua) vẫn còn đọc được —
    # "jump forward" tới chúng vẫn còn đường, qua `phien_ban_chi_tiet`.
    giu_lai = {t["phien_ban"]: t for t in ve_v1["phien_ban_truoc"]}
    assert set(giu_lai) == {2, 3}
    assert giu_lai[2]["document"] == "# ĐƠN v2" and giu_lai[3]["document"] == "# ĐƠN v3"
    assert ban_thao.phien_ban_chi_tiet(nguoi, v1["id"], 3)["document"] == "# ĐƠN v3"

    tu_choi = ban_thao.lui(nguoi, v1["id"])
    assert tu_choi == ban_thao.chi_tiet(nguoi, v1["id"])


def test_sua_sau_khi_lui_khong_dung_so_phien_ban(nguoi):
    """Lùi rồi sửa tiếp: số phiên bản mới phải LỚN HƠN mọi số đang có trong bản
    ghi, và không có hai mục nào trùng số. Phase 4 (D11, R1/R2) đổi CÁCH đạt
    được điều đó: trước đây nhánh bị bỏ ("v3 cũ") biến mất hẳn nên không còn gì
    để va số; giờ nó vẫn được GIỮ (R2) nhưng mang một số KHÁC do bộ đếm
    `phien_ban_ke_tiep` cấp (R1) — nội dung "v3 cũ" vẫn đọc được, nguyên vẹn,
    dưới số của chính nó, không đụng tới số mà "v3 mới" vừa được cấp."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    v1 = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "2"}, {**KET, "document": "# ĐƠN v2"})
    v3_cu = ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "3"}, {**KET, "document": "# ĐƠN v3 cũ"})
    ban_thao.lui(nguoi, v1["id"])  # về v2, GIỮ "v3 cũ" lại (R2) thay vì bỏ hẳn

    moi = ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "3 mới"}, {**KET, "document": "# ĐƠN v3 mới"})

    so_lich_su = [b["phien_ban"] for b in moi["phien_ban_truoc"]]
    assert all(moi["phien_ban"] > so for so in so_lich_su)
    assert len(set(so_lich_su)) == len(so_lich_su), "không mục lịch sử nào trùng số phiên bản"
    assert moi["phien_ban"] not in so_lich_su
    # R1's proof: "v3 cũ" (số của chính nó, KHÁC số của "v3 mới") vẫn đọc được
    # nguyên nội dung — bằng chứng nhánh bị bỏ không hề bị mất, chỉ đổi số.
    v3_cu_giu_lai = ban_thao.phien_ban_chi_tiet(nguoi, v1["id"], v3_cu["phien_ban"])
    assert v3_cu_giu_lai is not None and v3_cu_giu_lai["document"] == "# ĐƠN v3 cũ"
    assert v3_cu["phien_ban"] != moi["phien_ban"]


# ═══ Phase 4 (D11) — lịch sử phiên bản không phá huỷ ═══════════════════════


def test_sua_ghi_luc_va_doi_vao_snapshot(nguoi):
    """R3: mỗi lần `sua` phải gắn `luc` (mốc giờ) và `doi` (khoá facts đổi) vào
    chính snapshot bị đẩy vào lịch sử — không chỉ trả một lần trong response
    rồi bỏ đi như trước Phase 4."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A", "ngay_nghi": "01/10/2026"}, KET)
    bt2 = ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "ngay_nghi": "15/10/2026"}, {**KET, "document": "# ĐƠN v2"})

    snap_v1 = bt2["phien_ban_truoc"][-1]
    assert snap_v1["phien_ban"] == 1
    assert snap_v1["luc"], "phải có mốc giờ ISO, không rỗng"
    assert snap_v1["doi"] == ["ngay_nghi"], "đúng khoá facts đã đổi khi rời phiên bản 1"


def test_snapshot_tu_truoc_phase_4_khong_co_luc_doi_van_doc_duoc(nguoi):
    """R3's yêu cầu tương thích ngược: một snapshot ghi TRƯỚC Phase 4 (không có
    `luc`/`doi`, mô phỏng bằng UPDATE thẳng xuống DB) không được làm `lui`,
    `danh_sach_phien_ban`, hay `phien_ban_chi_tiet` nổ lỗi hay bịa dữ liệu."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "buoc": "2"}, {**KET, "document": "# ĐƠN v2"})

    snap_cu = {"phien_ban": 1, "document": "# ĐƠN cũ", "facts": {"ho_ten": "A"}, "clauses": [], "audit": {}}
    with get_engine().begin() as c:
        c.execute(
            text("UPDATE ban_thao SET phien_ban_truoc = CAST(:t AS jsonb) WHERE id = CAST(:id AS uuid)"),
            {"t": '[{"phien_ban": 1, "document": "# ĐƠN cũ", "facts": {"ho_ten": "A"}, "clauses": [], "audit": {}}]',
             "id": bt["id"]},
        )

    lich_su = ban_thao.danh_sach_phien_ban(nguoi, bt["id"])
    assert lich_su == [{"phien_ban": 1, "luc": None, "doi": []}]

    chi_tiet_cu = ban_thao.phien_ban_chi_tiet(nguoi, bt["id"], 1)
    assert chi_tiet_cu == snap_cu

    ve_v1 = ban_thao.lui(nguoi, bt["id"])
    assert ve_v1["phien_ban"] == 1 and ve_v1["document"] == "# ĐƠN cũ"


def test_danh_sach_phien_ban_khong_keo_full_body(nguoi):
    """R4: danh sách lịch sử chỉ mang số/`luc`/`doi` — không kèm
    `document`/`facts`/`clauses`/`audit`, đúng lý do `_SQL_DS` bớt
    `phien_ban_truoc` ở R5 (không kéo cả body vào một danh sách)."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "buoc": "2"}, {**KET, "document": "# ĐƠN v2"})

    lich_su = ban_thao.danh_sach_phien_ban(nguoi, bt["id"])
    assert lich_su == [{"phien_ban": 1, "luc": lich_su[0]["luc"], "doi": ["buoc"]}]
    assert set(lich_su[0]) == {"phien_ban", "luc", "doi"}

    chi_tiet_v1 = ban_thao.phien_ban_chi_tiet(nguoi, bt["id"], 1)
    assert chi_tiet_v1["document"] == bt["document"] and chi_tiet_v1["facts"] == bt["facts"]

    assert ban_thao.phien_ban_chi_tiet(nguoi, bt["id"], 99) is None, "số không tồn tại → None (404)"
    assert ban_thao.danh_sach_phien_ban("00000000-0000-0000-0000-000000000000", bt["id"]) is None, "không phải chủ → None"


def test_danh_sach_khong_con_keo_phien_ban_truoc(nguoi):
    """R5: `danh_sach` (GET /ban-thao) không còn kéo `phien_ban_truoc` — mỗi
    dòng danh sách không có khoá này."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "buoc": "2"}, {**KET, "document": "# ĐƠN v2"})

    items, _ = ban_thao.danh_sach(nguoi, 10, 0)
    assert "phien_ban_truoc" not in items[0]
    assert items[0]["phien_ban"] == 2


def test_soan_thao_cua_phien(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "x")
    khac = "00000000-0000-0000-0000-000000000000"
    assert hoi_thoai.soan_thao_cua_phien(nguoi, pid) is None
    assert hoi_thoai.ghi_soan_thao(khac, pid, {"a": 1}) is False, "sai chủ phải fail closed, không âm thầm ghi"
    assert hoi_thoai.soan_thao_cua_phien(khac, pid) is None, "sai chủ không được đọc được state của người khác"
    assert (
        hoi_thoai.ghi_soan_thao(
            nguoi, pid, {"loai": "don_xin_nghi_viec", "facts": {"ho_ten": "A"}, "ban_thao_id": None, "so_lan_sua": 0}
        )
        is True
    )
    assert hoi_thoai.soan_thao_cua_phien(nguoi, pid)["facts"] == {"ho_ten": "A"}
    assert hoi_thoai.ghi_soan_thao(nguoi, pid, {}) is True
    assert hoi_thoai.soan_thao_cua_phien(nguoi, pid) == {}, "trạng thái rỗng-nhưng-hợp-lệ khác None"
    hoi_thoai.ghi_soan_thao(nguoi, pid, None)
    assert hoi_thoai.soan_thao_cua_phien(nguoi, pid) is None


def test_lui_khong_tra_lai_lan_sua_da_dung(nguoi):
    """`so_lan_sua` là bộ đếm ĐƠN ĐIỆU (migration 025): sửa ba lần rồi lùi ba lần
    vẫn là ba lần đã sửa. Đo trần trên `phien_ban_truoc` — mảng mà `lui` bớt đi —
    cho phép xen kẽ lùi (miễn phí) với dựng lại (một lượt LLM trả phí) để đặt lại
    trần, tức một vòng lặp tiêu tiền không chặn được."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    assert bt["so_lan_sua"] == 0

    for i in range(3):
        ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "buoc": str(i)}, {**KET, "document": f"# ĐƠN v{i + 2}"})
    assert ban_thao.chi_tiet(nguoi, bt["id"])["so_lan_sua"] == 3

    for _ in range(3):
        ban_thao.lui(nguoi, bt["id"])
    sau = ban_thao.chi_tiet(nguoi, bt["id"])
    assert sau["phien_ban"] == 1
    # Phase 4 (D11, R2): ba bản bị lùi qua (2, 3, 4) vẫn được GIỮ, không còn
    # "rỗng" — nhưng trần sửa vẫn đo trên `so_lan_sua`, không trên mảng này.
    assert {t["phien_ban"] for t in sau["phien_ban_truoc"]} == {2, 3, 4}
    assert sau["so_lan_sua"] == 3, "lùi KHÔNG được trả lại một lần sửa nào"


# ═══ Phase 6 (D10) — một bản thảo chết theo cuộc hội thoại của nó ═══════════


def test_xoa_hoi_thoai_xoa_mem_ban_thao_cung_luc(nguoi):
    """R1: `hoi_thoai.xoa_mem` phải kéo theo xoá MỀM chính bản thảo của cuộc
    hội thoại đó, cùng một transaction — không phải một bước dọn riêng có thể
    quên. Bản thảo phải biến mất khỏi cả `chi_tiet` (⇒ `GET /ban-thao/{id}`
    404) lẫn `danh_sach` (⇒ `GET /ban-thao`) NGAY sau lệnh xoá, không cần thêm
    bước nào khác."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)

    assert hoi_thoai.xoa_mem(nguoi, pid) is True

    assert ban_thao.chi_tiet(nguoi, bt["id"]) is None
    assert ban_thao.danh_sach(nguoi, 10, 0) == ([], 0)


def test_xoa_hoi_thoai_khong_dung_ban_thao_khong_hoi_thoai_hoac_cua_phien_khac(nguoi):
    """Ba ca âm brief đòi buộc: (1) bản thảo KHÔNG mang `hoi_thoai_id` không
    phải mồ côi, vẫn phải hiện nguyên; (2) bản thảo của một hội thoại KHÁC còn
    SỐNG không bị đụng khi một hội thoại khác bị xoá — phạm vi UPDATE không
    được nới quá đúng cuộc hội thoại đang xoá."""
    pid_song = hoi_thoai.tao_phien(nguoi, "đơn còn sống")
    bt_song = ban_thao.tao(nguoi, pid_song, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)

    pid_xoa = hoi_thoai.tao_phien(nguoi, "đơn sẽ xoá")
    bt_mo_coi = ban_thao.tao(nguoi, pid_xoa, "don_xin_nghi_viec", {"ho_ten": "B"}, KET)

    bt_khong_hoi_thoai = ban_thao.tao(nguoi, None, ban_thao.LOAI_TONG_QUAT, {}, KET)

    assert hoi_thoai.xoa_mem(nguoi, pid_xoa) is True

    assert ban_thao.chi_tiet(nguoi, bt_song["id"]) is not None, "hội thoại KHÁC còn sống — không bị đụng"
    assert ban_thao.chi_tiet(nguoi, bt_khong_hoi_thoai["id"]) is not None, "không hội thoại nào — không phải mồ côi"
    assert ban_thao.chi_tiet(nguoi, bt_mo_coi["id"]) is None, "bản thảo của hội thoại vừa xoá — phải biến mất"

    ids_con_lai = {i["id"] for i in ban_thao.danh_sach(nguoi, 10, 0)[0]}
    assert ids_con_lai == {bt_song["id"], bt_khong_hoi_thoai["id"]}


def test_ban_thao_mo_coi_TU_TRUOC_van_bi_an_khong_can_backfill(nguoi):
    """R4: một bản thảo mồ côi từ TRƯỚC bản vá này (hội thoại xoá mềm bằng một
    đường KHÔNG PHẢI `hoi_thoai.xoa_mem` — giả lập bằng UPDATE thẳng, y hệt
    "trước R1 tồn tại") vẫn phải bị ẩn. Đây là HỆ QUẢ của bộ lọc đọc ở R2
    (`NOT EXISTS` trên `hoi_thoai.xoa_luc`), không phải một bước backfill dữ
    liệu riêng — R2 không phân biệt được một hội thoại vừa bị xoá với một hội
    thoại đã xoá từ trước khi bản vá này tồn tại, cả hai chỉ là một hàng
    `hoi_thoai.xoa_luc IS NOT NULL`."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn cũ")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    with get_engine().begin() as c:
        c.execute(text("UPDATE hoi_thoai SET xoa_luc = now() WHERE id = CAST(:id AS uuid)"), {"id": pid})

    assert ban_thao.chi_tiet(nguoi, bt["id"]) is None
    assert ban_thao.danh_sach(nguoi, 10, 0) == ([], 0)
