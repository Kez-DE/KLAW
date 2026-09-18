"""Phase 14 — mô hình soạn; 29 checklist không còn là cổng của đường chat.

Owner (2026-09-18): "bỏ fix cứng tham chiếu 29 văn bản soạn thảo, bỏ fix cứng
tham chiếu 'kho', dữ liệu là thật, tham chiếu thật để hỏi đáp, có móc leo nhưng
LLM cũng phải được tự suy luận và phán đoán". Hai quyết định đã chốt (D14-A,
D14-B): không nhãn "chưa kiểm pháp lý" trên bản thảo soạn trong chat, và
checklist là lời mời chứ không phải điều kiện. File này khoá phần BẤT BIẾN
xuyên các module — chuỗi đã gỡ không còn ở đâu trong `src/`, `audit_report.
muc_kiem` vẫn nói thật cho cả hai đường soạn, phép kiểm neo trích dẫn không
bị nới, và không lời đáp nào còn gọi corpus là "kho" (R5) — còn hành vi từng
node nằm trong test của node đó
(`test_re_tat_som`, `test_hieu_tai_lieu`, `test_ban_thao_tong_quat`,
`test_assemble`).

Trước Phase 14 file này (tên cũ `test_huong_dan_soan_thao.py`) khoá điều
NGƯỢC LẠI — "cách chữa KHÔNG phải để chat tự soạn", mọi lượt `soan_thao` phải
chỉ sang biểu mẫu. Owner đã đổi quyết định đó; test cũ đi theo.
"""

import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

from src.agents.nodes import assemble as asm
from src.agents.nodes import dung_ban_thao_tong_quat as d
from src.agents.nodes import gioi_thieu as gt
from src.agents.nodes.assemble import ResultType, _dieu_khong_duoc_chong_do, assemble
from src.agents.nodes.route import Intent
from src.services import ban_thao, ho_so, kho
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V

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


# ── Proof R5: lời cho người đọc gọi tên thứ đang trích, không gọi cái hộp ───


# `\bkho\b` KHÔNG khớp "khoản"/"khoá"/"khoảng" (ký tự ngay sau vẫn là ký tự
# từ), nên đây bắt đúng chữ "kho" đứng một mình — cách gọi corpus mà owner đã
# bỏ, chứ không phải mọi chữ bắt đầu bằng "kho".
_RE_KHO = re.compile(r"(?i)\bkho\b")


def _vb(so: str, ten: str, loai: str = "Bộ luật") -> dict:
    return {"so_ky_hieu": so, "ten": ten, "loai_van_ban": loai, "depth": "deep",
            "hieu_luc": Effectivity(V.con_hieu_luc, "cao", "không có tín hiệu chấm dứt nào"),
            "linh_vuc": "Lao động - Thương binh và Xã hội"}


# Fixture dựng tại chỗ, KHÔNG import từ test file khác (cùng lý do
# `test_khia_canh.py` nêu: một thay đổi bên kia làm đỏ bên này khó đọc).
_KHO = [_vb("45/2019/QH14", "Bộ Luật lao động số 45/2019/QH14"),
        _vb("145/2020/NĐ-CP", "Nghị định 145/2020/NĐ-CP", loai="Nghị định")]


def _moi_loi_dap_nguoi_doc() -> dict[str, str]:
    """Mọi bề mặt từng gọi corpus là "kho" TRONG LỜI người dùng đọc.

    Đi qua `_mot_khoi` cho ĐỦ chín khía cạnh thay vì đoán vài câu hỏi mẫu: một
    khía cạnh thứ mười thêm vào mà quên sửa lời sẽ đỏ ở đây."""
    ra = {f"gioi_thieu.{t}": gt._mot_khoi(t, "kho của bạn phủ những gì", _KHO) for t in gt.KHIA_CANH}
    ra["gioi_thieu.THIEU_KHO"] = gt.THIEU_KHO
    ra["kho.tom_tat"] = kho.dung_cau_tra_loi("có bao nhiêu bộ luật", _KHO)
    ra["kho.co_van_ban"] = kho.dung_cau_tra_loi("có Nghị định 145/2020 không?", _KHO)
    ra["kho.khong_co_van_ban"] = kho.dung_cau_tra_loi("có Nghị định 999/2099/NĐ-CP không?", _KHO)
    ra["kho.loi_dan_bang"] = kho.loi_dan_bang()
    ra["assemble.NGOAI_PHAM_VI"] = asm.NGOAI_PHAM_VI
    ra["assemble.KHONG_TIM_DUOC"] = asm.KHONG_TIM_DUOC
    ra["assemble.nguon_bi_thay"] = asm._ly_do_moi_nguon_bi_thay(
        [SimpleNamespace(effectivity=Effectivity(V.bi_thay_the, "cao", "bị 145/2020/NĐ-CP thay thế"))])
    ra.update({f"ho_so.{k}": v for k, v in ho_so.NHAN_PHAN_LOAI.items()})
    return ra


def test_khong_loi_dap_nao_goi_corpus_la_kho_cua_toi():
    """R5 (owner): "ko đề cập 'kho' trong kho của tôi nữa mà sẽ là pháp luật
    việt nam có, … luật này, điều này trong pháp luật việt nam, bộ luật này".
    Gọi corpus là một cái kho riêng làm KLAW nghe như danh mục tư nhân, trong
    khi thứ nó đang trích LÀ văn bản pháp luật Việt Nam."""
    vuong = {ten: t for ten, t in _moi_loi_dap_nguoi_doc().items() if _RE_KHO.search(t)}
    assert not vuong, f"lời cho người đọc còn gọi corpus là kho: {vuong}"


def test_loi_dap_con_lai_goi_dung_ten_thu_dang_trich():
    """Nửa sau của R5: bỏ chữ "kho" chỉ đúng nếu chỗ nó đứng nay gọi TÊN văn
    bản — không phải nếu câu trở thành vô danh."""
    loi = _moi_loi_dap_nguoi_doc()
    assert loi["gioi_thieu.bo_luat"] == "Tôi hiện có 1 Bộ luật: Lao động."
    assert "Bộ Luật lao động số 45/2019/QH14" in loi["kho.tom_tat"]
    assert "văn bản pháp luật Việt Nam" in loi["kho.tom_tat"]
    assert "145/2020/NĐ-CP" in loi["kho.co_van_ban"]
    assert "văn bản luật" in loi["gioi_thieu.ban_chat"], "tầng một so chữ với CHÍNH văn bản luật"


def test_bo_chu_kho_KHONG_duoc_thanh_loi_hua_phu_het_phap_luat_viet_nam():
    """Ranh giới brief đặt ra cho R5: nói "pháp luật Việt Nam quy định…" rồi
    đoán thì tệ hơn lời cũ. Câu đóng phạm vi vẫn phải thú nhận đúng những gì
    có, và vẫn phải đi kèm MỌI đường trả lời về corpus."""
    assert "không phải toàn bộ văn bản pháp luật Việt Nam" in kho.CAU_GIOI_HAN
    assert "còn nhiều văn bản tôi chưa có" in kho.CAU_GIOI_HAN
    for cau_hoi in ("có bao nhiêu bộ luật", "có Nghị định 145/2020 không?",
                    "có Nghị định 999/2099/NĐ-CP không?"):
        assert kho.CAU_GIOI_HAN in kho.dung_cau_tra_loi(cau_hoi, _KHO)
