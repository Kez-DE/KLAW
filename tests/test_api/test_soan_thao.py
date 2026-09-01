"""Task 5 — /api/v1/soan-thao, /api/v1/soat, /api/v1/mau/{loai}.

Bốn test đầu là nguyên văn task-5-brief.md Step 1 (KHÔNG sửa) — chạm graph
thật (Postgres + OpenRouter thật khi có draft_generate) nên đánh dấu
`@pytest.mark.integration`, đúng quy ước module `test_tra_cuu.py` đã đặt
("Test đụng graph thật (Postgres + OpenRouter thật) đánh dấu
@pytest.mark.integration"). Test 4 (422 do Literal sai) không chạm gì —
không đánh dấu, giống `test_query_rong_bi_422`.

Các test còn lại khoá 5 ràng buộc điều phối trong task-5-brief.md phần "Yêu
cầu": (1) validate facts ở biên → 422, (2) startup can_cu check, (3) Finding
mang doc_id/khop_tai_id, (4) GET /mau/{loai} sinh từ YAML, (5) traces ghi cho
cả hai endpoint mới. Tận dụng LẠI hai test tích hợp có sẵn (test 1/3) để kiểm
(3) và (5) thay vì gọi thêm request LLM thật — giảm chi phí OpenRouter thật.
"""

import pytest

FACTS = {"nhom_chuc_danh": "cong_viec_khac", "thoi_gian_thu_viec_ngay": 30,
         "luong_thang": 10_000_000, "vung": "I",
         "luong_thu_viec": 9_000_000, "luong_chinh_thuc": 10_000_000,
         "co_dieu_khoan_phat_tien": False, "co_dieu_khoan_giu_giay_to": False,
         "co_dieu_khoan_dat_coc": False}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_soan_thao_tra_audit_report_co_self_audit_True(client):
    r = await client.post("/api/v1/soan-thao",
                          json={"loai_van_ban": "hdld", "facts": FACTS, "nganh": "thuong_mai"})
    assert r.status_code == 200
    d = r.json()
    assert d["audit_report"]["self_audit"] is True

    # Ràng buộc #5 — traces phải được ghi cho /soan-thao (endpoint đúng, cùng trace_id).
    from sqlalchemy import text

    from src.services.db import get_engine
    with get_engine().connect() as c:
        row = c.execute(text("SELECT endpoint FROM traces WHERE id = :id"),
                        {"id": d["trace_id"]}).mappings().one_or_none()
    assert row is not None, "endpoint /soan-thao phải ghi một dòng traces cho request này"
    assert row["endpoint"] == "/api/v1/soan-thao"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_soat_van_ban_nguoi_dung_thi_self_audit_False(client):
    r = await client.post("/api/v1/soat",
                          json={"loai_van_ban": "hdld", "text": "Điều 1. Công việc...",
                                "facts": FACTS, "nganh": "thuong_mai"})
    assert r.status_code == 200
    d = r.json()
    assert d["audit_report"]["self_audit"] is False

    # Ràng buộc #5 — cùng phép kiểm cho /soat.
    from sqlalchemy import text

    from src.services.db import get_engine
    with get_engine().connect() as c:
        row = c.execute(text("SELECT endpoint FROM traces WHERE id = :id"),
                        {"id": d["trace_id"]}).mappings().one_or_none()
    assert row is not None, "endpoint /soat phải ghi một dòng traces cho request này"
    assert row["endpoint"] == "/api/v1/soat"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_thieu_vung_thi_audit_bao_khong_kiem_duoc_chu_khong_im_lang(client):
    f = {k: v for k, v in FACTS.items() if k != "vung"}
    d = (await client.post("/api/v1/soan-thao",
                           json={"loai_van_ban": "hdld", "facts": f,
                                 "nganh": "thuong_mai"})).json()
    assert any("không kiểm được" in x["thong_diep"] for x in d["audit_report"]["findings"])

    # Ràng buộc #3 — Finding PHẢI mang doc_id:str và khop_tai_id:int, không
    # chỉ can_cu dạng chuỗi, nếu không panel đối chiếu phía FE không mở được.
    # rule luong_toi_thieu_vung "không kiểm được" (thiếu vung) vẫn giữ can_cu
    # của rule (rules.py: Violation.can_cu = r.can_cu bất kể kiểm được hay
    # không) nên finding này PHẢI tra ra được id thật.
    f_vung = next(x for x in d["audit_report"]["findings"] if x.get("rule_id") == "luong_toi_thieu_vung")
    assert isinstance(f_vung["doc_id"], str) and f_vung["doc_id"]
    assert isinstance(f_vung["khop_tai_id"], int)
    assert f_vung["can_cu"] == "293/2025/NĐ-CP > Điều 3 > Khoản 1"
    assert "mo_ta" not in f_vung and "vi_tri" not in f_vung, (
        "khoá trùng đã gỡ: `mo_ta`/`thong_diep` và `dieu_khoan_lien_quan`/`vi_tri` từng mang "
        "cùng một giá trị dưới hai tên. Giữ cả hai thì một cái sẽ được cập nhật còn cái kia không."
    )


@pytest.mark.asyncio
async def test_loai_van_ban_la_thi_422(client):
    r = await client.post("/api/v1/soan-thao",
                          json={"loai_van_ban": "khong-co-that", "facts": FACTS})
    assert r.status_code == 422


# ══ Ràng buộc #1 — validate facts ở biên bằng Pydantic/HTTP, không để rule
# engine ném KeyError thành 500. Không chạm graph/DB/LLM: _validate_facts
# raise TRƯỚC khi graph được invoke, nên không cần @pytest.mark.integration.


@pytest.mark.asyncio
async def test_vung_gia_tri_la_tra_422_neu_ro_gia_tri_sai_va_gia_tri_hop_le(client):
    f = {**FACTS, "vung": "V"}
    r = await client.post("/api/v1/soan-thao", json={"loai_van_ban": "hdld", "facts": f})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "V" in detail and "vung" in detail
    for hop_le in ("I", "II", "III", "IV"):
        assert hop_le in detail, f"thông báo 422 phải liệt kê giá trị hợp lệ {hop_le}"


@pytest.mark.asyncio
async def test_nhom_chuc_danh_gia_tri_la_cung_tra_422(client):
    f = {**FACTS, "nhom_chuc_danh": "khong-ton-tai"}
    r = await client.post("/api/v1/soat",
                          json={"loai_van_ban": "hdld", "text": "Điều 1. Công việc...", "facts": f})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_thieu_fact_hoan_toan_KHONG_bi_422(client):
    """Đối lập với hai test trên: fact VẮNG MẶT không phải fact SAI giá trị —
    rule engine đã xử lý đúng bằng None ("không kiểm được", xem rules.py); biên
    HTTP không được biến sự vắng mặt hợp lệ đó thành lỗi validate."""
    f = {k: v for k, v in FACTS.items() if k != "vung"}
    r = await client.post("/api/v1/soan-thao", json={"loai_van_ban": "hdld", "facts": f})
    assert r.status_code != 422


# ══ Ràng buộc #4 — GET /api/v1/mau/{loai}: mô tả fact sinh từ YAML, không
# hardcode danh sách trường trong Python. Không chạm DB/LLM.


@pytest.mark.asyncio
async def test_mau_hdld_mo_ta_fact_sinh_tu_yaml(client):
    r = await client.get("/api/v1/mau/hdld")
    assert r.status_code == 200
    d = r.json()
    theo_key = {f["key"]: f for f in d["facts"]}

    # 9 fact xuất hiện trong can_facts của 5 rule (config/rules.yaml) — đúng
    # bộ FACTS mà test tích hợp phía trên dùng, không phải danh sách bịa.
    assert set(theo_key) == set(FACTS)

    vung = theo_key["vung"]
    assert set(vung["lua_chon"]) == {"I", "II", "III", "IV"}, (
        "lua_chon của vung phải suy TRỰC TIẾP từ bang_thang trong rules.yaml"
    )
    assert vung["bat_buoc"] is True
    assert vung["nhan"] and vung["nhan"] != "vung", "phải có nhãn tiếng Việt thật, không phải trả nguyên khoá"

    nhom = theo_key["nhom_chuc_danh"]
    assert set(nhom["lua_chon"]) == {
        "quan_ly_doanh_nghiep", "cao_dang_tro_len", "trung_cap_cnkt_nghiep_vu", "cong_viec_khac",
    }

    # Fact không phải bảng tra (vd. lương) thì không có lua_chon — None, không
    # phải danh sách rỗng bịa ra.
    assert theo_key["luong_thang"]["lua_chon"] is None


@pytest.mark.asyncio
async def test_mau_loai_khong_ho_tro_tra_danh_sach_rong_khong_bia(client, gia_vo_chua_ho_tro):
    """Một `LoaiVanBan` hợp lệ nhưng CHƯA có config/checklist_<loai>.yaml phải
    trả rỗng trung thực, thay vì tái dùng nhầm fact của một loại khác."""
    gia_vo_chua_ho_tro("noi_quy")
    r = await client.get("/api/v1/mau/noi_quy")
    assert r.status_code == 200
    assert r.json()["facts"] == []


@pytest.mark.asyncio
async def test_mau_loai_la_thi_422(client):
    r = await client.get("/api/v1/mau/khong-co-that")
    assert r.status_code == 422


# ══ Ràng buộc: một `LoaiVanBan` chưa có checklist → soạn/soát phải từ chối
# trung thực, không âm thầm áp checklist của loại khác lên sai loại văn bản.
#
# Test KHÔNG dựa vào việc một loại cụ thể nào đó tình cờ chưa được dựng: mỗi
# mẫu mới thêm vào sẽ làm một test như thế mục im lặng (nó vẫn xanh, nhưng
# không còn kiểm cái nó nói là kiểm). `gia_vo_chua_ho_tro` gỡ loại đang xét ra
# khỏi `cac_loai()` — chính cái cổng mà route hỏi — nên phép kiểm nhắm vào cơ
# chế, không vào tình trạng nhất thời của thư mục config.


@pytest.fixture
def gia_vo_chua_ho_tro(monkeypatch):
    from src.api import routes

    def _bo(loai: str):
        con_lai = frozenset(routes.cac_loai()) - {loai}
        monkeypatch.setattr(routes, "cac_loai", lambda: con_lai)

    return _bo


@pytest.mark.asyncio
async def test_soan_thao_loai_chua_ho_tro_tra_loi_trung_thuc_khong_gia_lap(client, gia_vo_chua_ho_tro):
    gia_vo_chua_ho_tro("noi_quy")
    r = await client.post("/api/v1/soan-thao", json={"loai_van_ban": "noi_quy", "facts": {}})
    assert r.status_code == 501


# ══ Ràng buộc #2 — kiểm can_cu lúc STARTUP (lifespan), không phải lúc người
# dùng hỏi. Test THUẦN wiring: kiem_tra_can_cu_ton_tai bản thân đã được Task
# 2/3 test kỹ (test_rules.py, test_checklist.py) — ở đây chỉ khoá việc
# lifespan CÓ gọi nó và CÓ để lỗi nổ ra (fail nhanh), không mock DB thật.


@pytest.mark.asyncio
async def test_lifespan_fail_nhanh_neu_can_cu_chet(monkeypatch):
    from src import main
    from src.services.rules import Rule

    rule_gia = Rule("gia", "khong/ton/tai > Điều 999", "chan", "x", [], "True", {})
    monkeypatch.setattr(main.soan_thao_graph, "requirements", lambda loai: ([rule_gia], None, {}))

    def bom(rules):
        raise ValueError(f"can_cu không tồn tại trong provisions.duong_dan: {[r.can_cu for r in rules]}")

    monkeypatch.setattr(main.rules_svc, "kiem_tra_can_cu_ton_tai", bom)

    with pytest.raises(ValueError, match="can_cu không tồn tại"):
        async with main.lifespan(main.app):
            pass
