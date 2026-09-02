"""Tầng nông: văn bản BIẾT là có, nhưng không có toàn văn máy đọc được.

`partial_coverage` là nhánh trả lời "văn bản X chi phối câu hỏi của bạn, nhưng
tôi chỉ có metadata của nó nên không diễn giải". Nó được thiết kế, được dựng,
và tới 2026-09-01 **chưa bao giờ kích được**: điều kiện là `not deep and
shallow`, mà DB có `deep: 47`, `metadata: 79`, `shallow: 0`.

Lý do thật KHÔNG phải thiếu nhãn — mà là 79 văn bản metadata có **0 điều
khoản**, nên không có gì để truy hồi. Bộ chia chunk cũng bỏ qua mọi cấp không
phải `dieu`.

Cách chữa: mỗi văn bản tầng nông nhận MỘT hàng `mo_dau` mang tên văn bản, và
bộ chia chunk đánh chỉ mục hàng đó — chỉ cho tầng nông.

Vì sao KHÔNG đánh chỉ mục `mo_dau` của tầng sâu: 47 tiền tố đó là letterhead
lặp lại ("CHÍNH PHỦ / CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM / Căn cứ…", trung
bình 467 ký tự). Thêm chúng vào chỉ mục là thêm 47 chunk gần trùng nhau, đúng
loại nhiễu tệ nhất khi `ts_rank` không có IDF.

Bất biến schema giữ lời hứa "không diễn giải" mà không cần một dòng code nào:
`ux_provisions_neo_trich_dan` và `provisions_noi_dung_citable_check` chỉ phủ
`dieu`/`khoan`/`diem`, nên một hàng `mo_dau` KHÔNG BAO GIỜ trích dẫn nguyên
văn được.
"""

from src.services.chunker import build_chunks

_NONG = {
    "id": 1, "document_id": "d-nong", "parent_id": None, "cap": "mo_dau",
    "so_hieu_cap": "", "duong_dan": "95/2026/NĐ-CP > Mở đầu",
    "noi_dung": "Nghị định 95/2026/NĐ-CP Quy định chi tiết một số điều của Luật Thủ đô",
    "depth": "shallow",
}
_SAU = {**_NONG, "id": 2, "document_id": "d-sau", "depth": "deep",
        "duong_dan": "59/2020/QH14 > Mở đầu",
        "noi_dung": "QUỐC HỘI CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc"}
_DIEU = {
    "id": 3, "document_id": "d-sau", "parent_id": None, "cap": "dieu",
    "so_hieu_cap": "1", "duong_dan": "59/2020/QH14 > Điều 1",
    "noi_dung": "Điều 1. Phạm vi điều chỉnh. Luật này quy định về…", "depth": "deep",
}


def test_mo_dau_cua_van_ban_tang_nong_duoc_danh_chi_muc():
    ch = build_chunks([_NONG], max_tokens=512)
    assert len(ch) == 1, "văn bản tầng nông phải có đúng một chunk mang tên nó"
    assert "95/2026/NĐ-CP" in ch[0].noi_dung_embed
    assert "Luật Thủ đô" in ch[0].noi_dung_embed
    assert ch[0].provision_id == 1


def test_mo_dau_cua_van_ban_tang_SAU_KHONG_duoc_danh_chi_muc():
    """Mặt còn lại — không có nó thì 47 letterhead trùng nhau vào chỉ mục."""
    ch = build_chunks([_SAU, _DIEU], max_tokens=512)
    pids = {c.provision_id for c in ch}
    assert 2 not in pids, "letterhead của văn bản tầng sâu không được vào chỉ mục"
    assert 3 in pids, "Điều của chính văn bản đó vẫn phải được đánh chỉ mục"


def test_mo_dau_rong_khong_sinh_chunk():
    ch = build_chunks([{**_NONG, "noi_dung": "   "}], max_tokens=512)
    assert ch == [], "không có tên thì không có gì để tìm — đừng dựng chunk rỗng"


# ══ Điều kiện kích của partial_coverage ═════════════════════════════════════

from src.agents.nodes.assemble import ResultType, assemble  # noqa: E402

_NGUON_NONG = [{
    "document_id": "d-nong", "so_ky_hieu": "95/2026/NĐ-CP",
    "ten": "Nghị định 95/2026/NĐ-CP Quy định chi tiết một số điều của Luật Thủ đô",
    "duong_dan": "95/2026/NĐ-CP > Mở đầu", "depth": "shallow",
}]


def test_co_nguon_nong_nhung_KHONG_luan_diem_nao_thi_partial_coverage():
    """Đo được 2026-09-01: hỏi "Nghị định 95/2026 quy định gì?" cho ra 18 kết
    quả truy hồi — 16 tầng sâu KHÔNG LIÊN QUAN và 2 tầng nông ĐÚNG. Điều kiện
    cũ `not deep and shallow` thấy `deep` khác rỗng nên không kích, rồi
    `generate_claims` sinh 0 luận điểm từ 16 nguồn kia, và người hỏi nhận một
    `abstain` trơ — trong khi hệ thống đang cầm đúng tên văn bản chi phối.

    Điều kiện đúng là "không luận điểm nào dùng được, NHƯNG có nguồn tầng
    nông". Nó chỉ NÂNG CẤP một `abstain`; không bao giờ chen chỗ một câu trả
    lời thật, vì nhánh này nằm sau nhánh có luận điểm.
    """
    st = assemble(
        {"query": "Nghị định 95/2026 quy định gì?", "insufficient_evidence": True,
         "hits_shallow": _NGUON_NONG, "expanded": [{"duong_dan": "x"}]},
        {}, None, "",
    )
    assert st["result_type"] == ResultType.partial_coverage
    assert st["nguon"] and st["nguon"][0]["so_ky_hieu"] == "95/2026/NĐ-CP"
    assert st["answer"] is None, "nêu văn bản, KHÔNG diễn giải"


def test_khong_luan_diem_va_khong_nguon_nong_thi_van_abstain():
    st = assemble({"query": "x", "insufficient_evidence": True, "hits_shallow": [], "expanded": []},
                  {}, None, "")
    assert st["result_type"] == ResultType.abstain
