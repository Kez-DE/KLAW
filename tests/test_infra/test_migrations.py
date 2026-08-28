import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.services.db import get_engine, run_migrations

BANG_BAT_BUOC = {
    "documents", "provisions", "references", "chunks",
    "verified_provisions", "verified_documents", "traces",
}


@pytest.mark.integration
def test_migration_tao_du_7_bang():
    run_migrations()
    names = set(inspect(get_engine()).get_table_names())
    assert BANG_BAT_BUOC <= names, f"thiếu: {BANG_BAT_BUOC - names}"


@pytest.mark.integration
def test_migration_idempotent_chay_hai_lan_khong_loi():
    run_migrations()
    run_migrations()


@pytest.mark.integration
def test_provisions_co_index_tren_duong_dan_va_document_id():
    run_migrations()
    idx = {i["name"] for i in inspect(get_engine()).get_indexes("provisions")}
    assert "ix_provisions_duong_dan" in idx
    assert "ix_provisions_document_id" in idx


@pytest.mark.integration
def test_chunks_mang_embedding_model_de_chay_nhieu_bo_song_song():
    run_migrations()
    cols = {c["name"] for c in inspect(get_engine()).get_columns("chunks")}
    assert {"embedding_model", "embedding_dim"} <= cols


@pytest.mark.integration
def test_bang_references_dung_duoc_ten_khoa_sql():
    # "references" là từ khóa SQL — phải quote được
    run_migrations()
    with get_engine().connect() as c:
        c.execute(text('SELECT count(*) FROM "references"'))


@pytest.mark.integration
def test_check_chan_tinh_trang_sai_chinh_ta():
    run_migrations()
    with pytest.raises(IntegrityError):
        with get_engine().begin() as c:
            c.execute(text(
                "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, checksum)"
                " VALUES ('__bad__', 'x/2020', 'Luật', 'x', 'hhl', 'c')"))


@pytest.mark.integration
def test_fk_chan_reference_tu_van_ban_khong_ton_tai():
    run_migrations()
    with pytest.raises(IntegrityError):
        with get_engine().begin() as c:
            c.execute(text(
                'INSERT INTO "references" (from_document_id, loai) VALUES (\'__khong_co__\', 4)'))


@pytest.mark.integration
def test_gia_tri_task8_se_ghi_deu_duoc_chap_nhan():
    """chua_xac_dinh và loai=0 là giá trị Task 8 THỰC SỰ ghi — CHECK phải cho qua.

    Test này ghim hợp đồng giữa Task 3 và Task 8; nếu nó đỏ thì ingest sẽ nổ.
    """
    run_migrations()
    with get_engine().begin() as c:
        c.execute(text(
            "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, checksum)"
            " VALUES ('__t8__', 'x/2020', 'Luật', 'x', 'chua_xac_dinh', 'c')"))
        c.execute(text('INSERT INTO "references" (from_document_id, loai) VALUES (\'__t8__\', 0)'))
        c.execute(text("DELETE FROM documents WHERE id = '__t8__'"))


@pytest.mark.integration
def test_migration_idempotent_KHI_DA_CO_DU_LIEU_dung_moi_cap():
    """`test_migration_idempotent_chay_hai_lan_khong_loi` ở trên chỉ chứng minh
    được idempotency trên bảng RỖNG — `ADD CONSTRAINT` không có dòng nào để kiểm
    nên nó không thể đỏ. Đã gặp thật: 001, 002, 003 mỗi file đều DROP rồi ADD
    `provisions_cap_check`, lần chạy thứ hai đi qua 002 TRƯỚC 003 nên nó thu hẹp
    tập giá trị lại và ném CheckViolation trên chính các dòng `phu_luc` mà 003
    vừa cho phép.

    Bản này chèn một dòng dùng cấp MỚI NHẤT rồi chạy lại migration. `004` cũng
    DROP rồi ADD `provisions_cap_check` và thêm hai ràng buộc nữa (partial unique
    index + CHECK `noi_dung`), nên nó phải sống sót đúng phép thử đó — lần này
    còn có dữ liệu CẤP TRÍCH DẪN ĐƯỢC để `ADD CONSTRAINT` phải kiểm thật."""
    run_migrations()
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, checksum)"
            " VALUES ('mig-test', 'x/2020/NĐ-CP', 'Nghị định', 't', 'CHL', 'c')"
            " ON CONFLICT (id) DO NOTHING"))
        # `so_hieu_cap` rỗng CHỈ hợp lệ ở hai cấp tài liệu — xem `005`.
        for cap, so, dd, nd in (("phu_luc", "", "x/2020/NĐ-CP > Phụ lục", ""),
                                ("mo_dau", "", "x/2020/NĐ-CP > Mở đầu", "Căn cứ Luật X;"),
                                ("dieu", "1", "x/2020/NĐ-CP > Điều 1", "Điều 1. Phạm vi")):
            conn.execute(text(
                "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
                " VALUES ('mig-test', :cap, :so, :nd, :dd, 0)"),
                {"cap": cap, "so": so, "dd": dd, "nd": nd})
    try:
        run_migrations()   # phải KHÔNG ném CheckViolation lẫn UniqueViolation
        run_migrations()
    finally:
        with eng.begin() as conn:
            conn.execute(text("DELETE FROM documents WHERE id = 'mig-test'"))


# ══ H4: hai bất biến nền tảng phải nằm TRONG DB, nơi không thể vòng qua ══

@pytest.mark.integration
def test_hai_bat_bien_neo_trich_dan_ton_tai_trong_DB():
    """Trước `004`, "neo trích dẫn duy nhất" và "`noi_dung` không rỗng ở cấp trích
    dẫn được" chỉ tồn tại ở `prov_parser._kiem_bat_bien` (lúc BUILD) và
    `test_seed_committed.py` (trên FILE ĐÃ COMMIT). Không cái nào nằm trên đường
    INGEST — đường thật sự nạp dữ liệu mà verifier sẽ đọc. `scripts/ingest.py`
    không validate gì cả."""
    run_migrations()
    with get_engine().connect() as c:
        idx = c.execute(text(
            "SELECT indexdef FROM pg_indexes"
            " WHERE tablename = 'provisions' AND indexname = 'ux_provisions_neo_trich_dan'"
        )).scalar_one()
        assert "UNIQUE" in idx and "duong_dan" in idx
        assert "WHERE" in idx, f"phải là PARTIAL index (cấp container được trùng): {idx}"

        chk = c.execute(text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
            " WHERE conname = 'provisions_noi_dung_citable_check'")).scalar_one()
        assert "noi_dung" in chk


@pytest.mark.integration
def test_unique_index_CHAN_neo_trung_nhung_VAN_CHO_container_trung():
    """NĐ 145/2020 thật sự đánh số hai Chương cùng là "Chương XI" — ngoại lệ đã
    chấp nhận có chủ đích, không được bịa "XII" để né. Partial index là đúng công
    cụ: trùng ở cấp trích dẫn được thành BẤT KHẢ THI VỀ MẶT VẬT LÝ, cấp container
    vẫn qua."""
    run_migrations()
    eng = get_engine()
    with eng.begin() as c:
        c.execute(text(
            "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, checksum)"
            " VALUES ('uq-test', 'x/2021/NĐ-CP', 'Nghị định', 't', 'CHL', 'c')"
            " ON CONFLICT (id) DO NOTHING"))
    try:
        with eng.begin() as c:   # container trùng: PHẢI qua
            for _ in range(2):
                c.execute(text(
                    "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
                    " VALUES ('uq-test', 'chuong', 'XI', 'Chương XI', 'x/2021/NĐ-CP > Chương XI', 0)"))
        with pytest.raises(IntegrityError):   # neo trích dẫn trùng: PHẢI chặn
            with eng.begin() as c:
                for _ in range(2):
                    c.execute(text(
                        "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
                        " VALUES ('uq-test', 'dieu', '1', 'Điều 1. X', 'x/2021/NĐ-CP > Điều 1', 0)"))
    finally:
        with eng.begin() as c:
            c.execute(text("DELETE FROM documents WHERE id = 'uq-test'"))


@pytest.mark.integration
def test_check_CHAN_noi_dung_rong_o_cap_trich_dan_duoc():
    """`noi_dung` rỗng ở cấp trích dẫn được = phép kiểm "câu trích khớp nguyên
    văn" không có gì để đối chiếu. Cấp container/tài liệu được phép rỗng."""
    run_migrations()
    eng = get_engine()
    with eng.begin() as c:
        c.execute(text(
            "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, checksum)"
            " VALUES ('chk-test', 'x/2022/NĐ-CP', 'Nghị định', 't', 'CHL', 'c')"
            " ON CONFLICT (id) DO NOTHING"))
    try:
        with eng.begin() as c:   # container rỗng: PHẢI qua
            c.execute(text(
                "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
                " VALUES ('chk-test', 'chuong', 'I', '', 'x/2022/NĐ-CP > Chương I', 0)"))
        for nd in ("", "   "):
            with pytest.raises(IntegrityError):
                with eng.begin() as c:
                    c.execute(text(
                        "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
                        " VALUES ('chk-test', 'khoan', '1', :nd, 'x/2022/NĐ-CP > Điều 9 > Khoản 1', 0)"),
                        {"nd": nd})
    finally:
        with eng.begin() as c:
            c.execute(text("DELETE FROM documents WHERE id = 'chk-test'"))


@pytest.mark.integration
def test_cap_mo_dau_duoc_CHECK_cho_qua():
    """`004` sở hữu đủ tập cấp (M6): `001` và `003` không còn câu lệnh nào cho
    `provisions_cap_check`, nên tập giá trị cuối cùng phải đến từ `004`."""
    run_migrations()
    with get_engine().connect() as c:
        chk = c.execute(text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
            " WHERE conname = 'provisions_cap_check'")).scalar_one()
    for cap in ("phan", "chuong", "muc", "tieu_muc", "dieu", "khoan", "diem",
                "phu_luc", "mo_dau"):
        assert f"'{cap}'" in chk, f"{cap} thiếu trong {chk}"


@pytest.mark.integration
def test_check_so_hieu_cap_CHAN_moi_cap_cau_truc_va_CHO_hai_cap_tai_lieu():
    """`005`. Dạng ĐỒNG NHẤT: mọi cấp phải có số hiệu, trừ `mo_dau`/`phu_luc` —
    hai cấp tài liệu là chữ không thuộc điều luật nào nên không có số hiệu để
    mang. Đồng nhất tốt hơn liệt kê: nó đúng cho cả cấp sẽ thêm về sau, không
    phải chỉ cấp đang có bug. Neo `"… > Điều 33 > Khoản"` (thiếu thành phần, người
    dùng không tra được) trước đây chỉ bị parser chặn, DB nhận hết."""
    run_migrations()
    eng = get_engine()
    with eng.begin() as c:
        chk = c.execute(text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
            " WHERE conname = 'provisions_so_hieu_cap_check'")).scalar_one()
        assert "so_hieu_cap" in chk
        c.execute(text(
            "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, checksum)"
            " VALUES ('sh-test', 'x/2023/NĐ-CP', 'Nghị định', 't', 'CHL', 'c')"
            " ON CONFLICT (id) DO NOTHING"))
    try:
        with eng.begin() as c:   # hai cấp tài liệu rỗng: PHẢI qua
            for cap, dd in (("mo_dau", "x/2023/NĐ-CP > Mở đầu"),
                            ("phu_luc", "x/2023/NĐ-CP > Phụ lục")):
                c.execute(text(
                    "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
                    " VALUES ('sh-test', :cap, '', 'x', :dd, 0)"), {"cap": cap, "dd": dd})
        # mọi cấp cấu trúc rỗng: PHẢI chặn (kể cả chỉ-khoảng-trắng)
        for cap, so in (("khoan", ""), ("diem", "  "), ("dieu", ""), ("chuong", ""),
                        ("muc", ""), ("tieu_muc", ""), ("phan", "")):
            with pytest.raises(IntegrityError):
                with eng.begin() as c:
                    c.execute(text(
                        "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
                        " VALUES ('sh-test', :cap, :so, 'x', 'x/2023/NĐ-CP > Điều 9 > Khoản', 0)"),
                        {"cap": cap, "so": so})
    finally:
        with eng.begin() as c:
            c.execute(text("DELETE FROM documents WHERE id = 'sh-test'"))
