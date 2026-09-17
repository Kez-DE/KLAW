import threading
import time
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


# ═══ Fix round 1 — sua()/lui() phải khoá hàng khi đọc-rồi-ghi ══════════════


def _giu_khoa_va_doi_ke_tiep(id: str, da_khoa: threading.Event, tha_khoa: threading.Event, ke_tiep_moi: int):
    """Mở một transaction RIÊNG, THẬT SỰ đổi `phien_ban_ke_tiep` của hàng này
    (không phải chỉ khoá suông rồi không đổi gì), báo hiệu đã xong, CHỜ tới
    khi bị `.set()` từ bên ngoài mới commit.

    Đổi THẬT là điểm mấu chốt để bài test phân biệt được hai hành vi: một
    UPDATE luôn phải chờ khoá hàng của giao dịch này giải phóng, cho DÙ đọc có
    khoá hay không — nên "có bị chặn hay không" không phân biệt được bản lỗi
    với bản đã sửa (cả hai đều bị UPDATE chặn). Cái phân biệt được là DỮ LIỆU
    dùng để tính ra bản ghi mới: đọc SAU khi khoá được thả (đúng, `FOR UPDATE`
    trong `sua`/`lui`) thấy `ke_tiep_moi`; đọc TỪ TRƯỚC lúc vào cuộc đua (sai,
    `chi_tiet()` không khoá) thấy giá trị CŨ, ghi đè mất `ke_tiep_moi` không
    dấu vết khi cuối cùng cũng tới lượt UPDATE của nó."""
    with get_engine().begin() as c:
        c.execute(
            text("UPDATE ban_thao SET phien_ban_ke_tiep = :k WHERE id = CAST(:id AS uuid)"),
            {"k": ke_tiep_moi, "id": id},
        )
        da_khoa.set()
        tha_khoa.wait(timeout=5)


def test_sua_dung_gia_tri_moi_nhat_khong_dung_gia_tri_da_doc_tu_truoc(nguoi):
    """[Fix round 1, Critical] Trong lúc `sua()` đang chờ một transaction khác
    nhả hàng này ra, transaction kia vừa TĂNG `phien_ban_ke_tiep` lên rất xa
    (mô phỏng một `sua()` khác vừa commit ngay trước đó). `sua()` phải dùng
    giá trị MỚI NHẤT (đọc LẠI sau khi khoá được thả) để cấp số phiên bản kế
    tiếp — nếu nó đọc bằng `chi_tiet()` không khoá TỪ TRƯỚC khi vào cuộc đua,
    nó sẽ cấp một số đã lỗi thời và ghi đè luôn cả bộ đếm về một giá trị CŨ,
    mở lại đúng va chạm số phiên bản mà R1 sinh ra để chặn."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ke_tiep_da_doi = bt["phien_ban_ke_tiep"] + 100

    da_khoa = threading.Event()
    tha_khoa = threading.Event()
    t_khoa = threading.Thread(target=_giu_khoa_va_doi_ke_tiep, args=(bt["id"], da_khoa, tha_khoa, ke_tiep_da_doi))
    t_khoa.start()
    da_khoa.wait(timeout=5)
    assert da_khoa.is_set(), "không dựng lại được tình huống: transaction giữ khoá chưa commit được bước đổi"

    ket_qua = {}

    def thu_sua():
        ket_qua["sua"] = ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "buoc": "2"}, {**KET, "document": "# ĐƠN v2"})

    t_sua = threading.Thread(target=thu_sua)
    t_sua.start()
    # Nhường CPU đủ lâu để `t_sua` chắc chắn đã VÀO tới lượt đọc của `sua()`
    # trước khi khoá được thả — không có mốc này, `t_sua` có thể khởi động
    # trễ hơn `tha_khoa.set()`, đọc được giá trị ĐàCOMMIT một cách tình cờ,
    # và bài test đỗ mà chẳng thử được cuộc đua nào (đã thấy xảy ra: chạy
    # không có `sleep` này cho kết quả PASS giả trên chính bản lỗi).
    time.sleep(0.2)

    tha_khoa.set()
    t_khoa.join(timeout=5)
    t_sua.join(timeout=5)

    assert ket_qua["sua"] is not None
    assert ket_qua["sua"]["phien_ban"] == ke_tiep_da_doi, (
        "sua() phải cấp đúng phien_ban_ke_tiep MỚI NHẤT — cấp một số cũ hơn nghĩa là nó "
        "đã đọc TRƯỚC khi transaction kia commit, ghi đè mất giá trị mới không dấu vết"
    )


def test_lui_khong_lam_lui_bo_dem_ve_gia_tri_cu(nguoi):
    """[Fix round 1, Critical] Cùng tình huống trên, cho `lui()`: nó ghi lại
    `phien_ban_ke_tiep` KHÔNG đổi giá trị (chỉ để không mất nó khi UPDATE ghi
    cả hàng) — nhưng phải là giá trị NÓ VỪA ĐỌC LẠI sau khi khoá được thả, chứ
    không phải giá trị đọc từ trước khi vào cuộc đua. Đọc từ trước sẽ làm
    `lui()` ghi đè bộ đếm VỀ một số CŨ hơn, mở lại đúng va chạm R1 chặn."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "buoc": "2"}, {**KET, "document": "# ĐƠN v2"})
    ke_tiep_da_doi = 999

    da_khoa = threading.Event()
    tha_khoa = threading.Event()
    t_khoa = threading.Thread(target=_giu_khoa_va_doi_ke_tiep, args=(bt["id"], da_khoa, tha_khoa, ke_tiep_da_doi))
    t_khoa.start()
    da_khoa.wait(timeout=5)
    assert da_khoa.is_set(), "không dựng lại được tình huống: transaction giữ khoá chưa commit được bước đổi"

    ket_qua = {}

    def thu_lui():
        ket_qua["lui"] = ban_thao.lui(nguoi, bt["id"])

    t_lui = threading.Thread(target=thu_lui)
    t_lui.start()
    # Cùng lý do ở bài test của `sua()`: nhường đủ CPU để `t_lui` chắc chắn đã
    # vào tới lượt đọc trước khi khoá được thả.
    time.sleep(0.2)

    tha_khoa.set()
    t_khoa.join(timeout=5)
    t_lui.join(timeout=5)

    assert ket_qua["lui"] is not None
    assert ket_qua["lui"]["phien_ban_ke_tiep"] == ke_tiep_da_doi, (
        "lui() phải GIỮ NGUYÊN phien_ban_ke_tiep MỚI NHẤT — ghi lại một giá trị cũ hơn "
        "nghĩa là nó đã đọc TRƯỚC khi transaction kia commit, làm bộ đếm LÙI lại"
    )


def test_hai_sua_dong_thoi_khong_va_so_khong_mat_ban_ghi(nguoi):
    """[Fix round 1, Critical] Hai request THẬT SỰ đồng thời (hai luồng, mỗi
    luồng một connection lấy từ pool — đúng hình dạng hai request async chạy
    qua `run_in_threadpool`) trên CÙNG một bản thảo: không được cấp trùng số
    phiên bản, và bản ghi của bên "thua" cuộc đua không được biến mất không
    dấu vết — nó phải còn đọc được, hoặc là bản đang sống, hoặc trong lịch sử."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ke_tiep_ban_dau = bt["phien_ban_ke_tiep"]

    rao_can = threading.Barrier(2)
    ket_qua = {}

    def sua_dong_thoi(nhan):
        rao_can.wait(timeout=5)
        ket_qua[nhan] = ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "buoc": nhan}, {**KET, "document": f"# ĐƠN {nhan}"})

    luong = [threading.Thread(target=sua_dong_thoi, args=(nhan,)) for nhan in ("a", "b")]
    for t in luong:
        t.start()
    for t in luong:
        t.join(timeout=5)

    a, b = ket_qua["a"], ket_qua["b"]
    assert a is not None and b is not None
    assert a["phien_ban"] != b["phien_ban"], "hai request đồng thời KHÔNG được cấp trùng số phiên bản"

    sau = ban_thao.chi_tiet(nguoi, bt["id"])
    assert sau["phien_ban_ke_tiep"] == ke_tiep_ban_dau + 2, "bộ đếm phải tăng đúng HAI lần, không phải một"

    tai_lieu_con_lai = {sau["document"]} | {t["document"] for t in sau["phien_ban_truoc"]}
    assert "# ĐƠN a" in tai_lieu_con_lai and "# ĐƠN b" in tai_lieu_con_lai, (
        "bản ghi của bên 'thua' cuộc đua không được biến mất"
    )

    so_tat_ca = [sau["phien_ban"], *[t["phien_ban"] for t in sau["phien_ban_truoc"]]]
    assert len(so_tat_ca) == len(set(so_tat_ca)), "không số phiên bản nào trùng nhau trong toàn bộ bản ghi"


def test_tran_sua_bo_so_nho_nhat_truoc_du_mang_bi_xao_tron(nguoi):
    """[Fix round 1, Important] Khi vượt `TRAN_SUA`, mục bị bỏ phải là số
    phiên bản NHỎ NHẤT — kể cả sau khi `lui` đã xáo trộn thứ tự mảng (giữ lại
    một nhánh số LỚN hơn bản đang đứng), cắt theo VỊ TRÍ mảng (phần tử đầu)
    có thể bỏ nhầm nhánh vừa bị rời đi thay vì tổ tiên cũ nhất."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    for i in range(1, 4):
        ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "buoc": str(i)}, {**KET, "document": f"d{i}"})
    # Live v4. Lùi hai bước — mảng giờ giữ cả tổ tiên (số nhỏ) lẫn nhánh vừa
    # rời đi (số lớn hơn bản đang đứng), không còn tăng dần theo vị trí.
    ban_thao.lui(nguoi, bt["id"])  # -> v3, giữ v4
    ban_thao.lui(nguoi, bt["id"])  # -> v2, giữ v3, v4
    for i in range(4, 4 + ban_thao.TRAN_SUA):
        r = ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "buoc": str(i)}, {**KET, "document": f"d{i}"})

    so_giu_lai = sorted(t["phien_ban"] for t in r["phien_ban_truoc"])
    assert len(so_giu_lai) == ban_thao.TRAN_SUA
    # Đúng TRAN_SUA số CAO NHẤT còn tồn tại (trừ bản đang sống) phải được giữ —
    # nghĩa là mọi số NHỎ hơn min(so_giu_lai) đã bị bỏ, không sót một số nhỏ
    # nào lại trong khi một số lớn hơn nó đã bị bỏ.
    tat_ca_so_tung_co = set(range(1, r["phien_ban"])) | {r["phien_ban"]}
    con_lai = set(so_giu_lai) | {r["phien_ban"]}
    bi_bo = tat_ca_so_tung_co - con_lai
    if bi_bo:
        assert max(bi_bo) < min(so_giu_lai), (
            f"bỏ nhầm số {bi_bo} trong khi số nhỏ hơn {min(so_giu_lai)} vẫn còn giữ lại"
        )


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
