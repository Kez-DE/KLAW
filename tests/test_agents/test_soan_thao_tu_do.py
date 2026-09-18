"""Phase 14 — mô hình soạn; 29 checklist không còn là cổng của đường chat.

Owner (2026-09-18): "bỏ fix cứng tham chiếu 29 văn bản soạn thảo, bỏ fix cứng
tham chiếu 'kho', dữ liệu là thật, tham chiếu thật để hỏi đáp, có móc leo nhưng
LLM cũng phải được tự suy luận và phán đoán". Hai quyết định đã chốt (D14-A,
D14-B): không nhãn "chưa kiểm pháp lý" trên bản thảo soạn trong chat, và
checklist là lời mời chứ không phải điều kiện. File này khoá phần BẤT BIẾN
xuyên các module — chuỗi đã gỡ không còn ở đâu trong `src/`, `audit_report.
muc_kiem` vẫn nói thật cho cả hai đường soạn, phép kiểm neo trích dẫn không
bị nới — còn hành vi từng node nằm trong test của node đó
(`test_re_tat_som`, `test_hieu_tai_lieu`, `test_ban_thao_tong_quat`,
`test_assemble`).

Trước Phase 14 file này (tên cũ `test_huong_dan_soan_thao.py`) khoá điều
NGƯỢC LẠI — "cách chữa KHÔNG phải để chat tự soạn", mọi lượt `soan_thao` phải
chỉ sang biểu mẫu. Owner đã đổi quyết định đó; test cũ đi theo.
"""

import re
import subprocess
from pathlib import Path

from src.agents.nodes import dung_ban_thao_tong_quat as d
from src.agents.nodes.assemble import ResultType, _dieu_khong_duoc_chong_do, assemble
from src.agents.nodes.route import Intent
from src.services import ban_thao

GOC = Path(__file__).resolve().parents[2]

# Nguyên văn các chuỗi R1 đã gỡ — chúng không được quay lại dưới bất kỳ tên nào.
CHUOI_DA_GO = (
    "Kho mẫu của tôi chưa có loại văn bản này",
    "Việc này tôi soạn được, nhưng không phải ở ô hỏi này",
    "bấm Chọn loại văn bản bên dưới",
    "luật trong kho",
)


def test_chuoi_ngo_cut_da_go_khong_con_trong_src():
    """Proof R1: grep toàn `src/` (mã lẫn chú thích) — một chú thích còn dẫn
    nguyên văn câu cũ cũng là chỗ câu đó bò về được."""
    ra = subprocess.run(
        ["grep", "-rn", "-F", "-e", *sum((["-e", c] for c in CHUOI_DA_GO[1:]), [CHUOI_DA_GO[0]]), "src/"],
        cwd=GOC, capture_output=True, text=True,
    )
    assert ra.stdout == "", f"chuỗi ngõ cụt còn trong src/:\n{ra.stdout}"


def test_khach_xin_soan_nhan_loi_moi_dang_nhap_0_token():
    """`_re_sau_route` rẽ khách thẳng tới đây; `llm=None` chứng minh không có
    lượt gọi nào (gọi sẽ nổ AttributeError)."""
    st = assemble({"query": "Soạn cho tôi hợp đồng lao động", "intent": Intent.soan_thao}, {}, None, "")
    assert st["result_type"] == ResultType.soan_thao_hoi
    assert st["soan_thao_hoi"]["can_dang_nhap"] is True
    assert st["traces"]["assemble_token_in"] == 0 and st["citations"] == []


# ── Proof: `audit_report.muc_kiem` vẫn nói thật cho CẢ HAI đường soạn ─────


class _Audit:
    dat, completeness, so_dieu_khoan, self_audit, findings = True, 1.0, 3, True, []


def test_muc_kiem_ghi_dung_duong_da_chay_cho_ban_thao_tong_quat_va_checklist():
    """Bản thảo tổng quát (mô hình soạn, chat): `muc_kiem == "tong_quat"`,
    `dat`/`completeness` là None — chưa rule nào chạy. Bản thảo checklist:
    KHÔNG có khoá `muc_kiem` (quy ước có sẵn: vắng mặt = checklist + rule +
    audit đã chạy), `dat`/`self_audit` là kết quả thật. D14-A chỉ bỏ NHÃN hiển
    thị; bản ghi không được nói dối."""
    tong_quat = d.ket_ban_thao({"tieu_de": "ĐƠN", "muc": [{"ten": "Nội dung", "vung": "than",
                                                            "khoi": [{"noi_dung": "Tôi xin nghỉ.", "bang": []}]}]})
    assert tong_quat["audit_report"]["muc_kiem"] == d.MUC_KIEM == "tong_quat"
    assert tong_quat["audit_report"]["dat"] is None and tong_quat["audit_report"]["completeness"] is None

    checklist = ban_thao.tu_state_soan_thao({"loai": "don_xin_nghi_viec", "clauses": [], "audit_report": _Audit(),
                                             "db_provisions": {}})
    assert "muc_kiem" not in checklist["audit_report"]
    assert checklist["audit_report"]["dat"] is True and checklist["audit_report"]["self_audit"] is True


# ── Proof R4/R6: phép kiểm neo không nới — trích dẫn bịa vẫn bị loại ────────


def test_so_dieu_bia_trong_answer_van_bi_loai_khi_khong_co_trong_citation_da_kiem():
    """Phép kiểm thứ năm (0 token) là lưới cuối: một "Điều 47" mô hình bịa mà
    không nằm trong tập trích dẫn đã qua hai tầng kiểm thì bị nêu tên để
    `assemble` hạ cả câu trả lời — Phase 14 không đụng vào nó."""
    da_kiem = [{"duong_dan": "45/2019/QH14 > Điều 35 > Khoản 1"}]
    assert _dieu_khong_duoc_chong_do("Theo Điều 47 và Điều 35, bạn được nghỉ.", da_kiem) == ["47"]
    assert _dieu_khong_duoc_chong_do("Theo Điều 35, bạn được nghỉ.", da_kiem) == []
    assert _dieu_khong_duoc_chong_do("Điều 47 quy định vậy.", []) == ["47"], "không có trích dẫn nào thì mọi số Điều đều bịa"


def test_regex_so_dieu_bat_ca_khoan_diem_trong_ban_thao_chat():
    """Mục bản thảo tổng quát dẫn Khoản/Điểm cũng bị lưới chặn của `bo_nho`
    bỏ — cùng lưới `lam_sach_van_ban` dùng, nên bản thảo chat không có đường
    nào mang một trích dẫn chưa kiểm ra tới người đọc."""
    from src.services.bo_nho import _vuong_luoi_chan

    assert _vuong_luoi_chan("Theo Khoản 2 Điều 115 người lao động được nghỉ.")
    assert _vuong_luoi_chan("Điểm a khoản 1")
    assert not _vuong_luoi_chan("Tôi xin nghỉ phép ba ngày vì việc gia đình.")
    assert re.search(r"[Đđ]iều\s+\d", "Điều 5") is not None
