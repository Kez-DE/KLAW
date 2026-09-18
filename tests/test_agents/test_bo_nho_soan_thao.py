"""Phase 12 part B — KLAW NHỚ điều người dùng khai, và KHÔNG tự điền nó.

Hợp đồng của chủ sở hữu, nguyên văn: "tôi muốn việc này được nhớ nhưng mà ko
phải văn bản mới mà khách yêu cầu khác là điền luôn mà chỉ cần nhớ thôi".

Bốn điều bị khoá ở đây:

1. **Cái phủ định là sản phẩm.** Một văn bản MỚI, ký ức đã có sẵn, lượt KHÔNG
   hỏi tới những dữ kiện ấy → văn bản dựng ra không mang một giá trị đã nhớ
   nào. Khẳng định trên CHÍNH giá trị (tên giả, mã giả), không trên một lá cờ
   nói rằng chúng đã bị chặn — một lá cờ có thể đúng trong khi văn bản vẫn sai.
2. Lượt CÓ hỏi tới thì giá trị đi vào văn bản bình thường: ký ức không được
   biến thành một thứ không bao giờ dùng được.
3. Rút dữ kiện KHÔNG thêm một lượt gọi mô hình nào — đếm lượt gọi, không tin
   một dòng chú thích.
4. "Đã nhớ" nói đúng một lần cho cái MỚI/ĐỔI, im khi người ta nhắc lại y hệt.

Mọi giá trị trong file là giả rõ ràng: không tên thật, không mã sinh viên thật.
"""

import json
import logging
import uuid

import pytest
from sqlalchemy.exc import StatementError

from src.agents import graph_tra_cuu as g
from src.agents.nodes import assemble as asm
from src.agents.nodes import hieu_tai_lieu as h
from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.route import Intent
from src.services import bao_ve
from src.services import bo_nho_tai_khoan as bn
from src.services.db import get_engine, run_migrations
from src.services.doc_tai_lieu import DonViVanBan

# Tiêu đề khối ký ức trong prompt, kèm xuống dòng hai đầu: quy tắc 15 cũng NHẮC
# tên khối này, nên so chuỗi trần sẽ khớp cả lời dặn và không chứng minh được gì.
KHOI_KY_UC = "\n# Điều người hỏi đã cho tôi biết trước đây\n"
# Dữ kiện GIẢ. Mã "00000000" không thuộc về ai, tên có chữ "Thử" để không lẫn
# với một người thật nếu dòng này lọt ra một bản ghi nào đó.
HO_TEN = "Nguyễn Văn Thử"
MA_SV = "00000000"
NOI_TT = "Công ty Mẫu Thử"
NHO = [
    {"loai": "ca_nhan", "khoa": "ho_ten", "nhan": "Họ và tên", "gia_tri": HO_TEN},
    {"loai": "ca_nhan", "khoa": "ma_sv", "nhan": "Mã sinh viên", "gia_tri": MA_SV},
    {"loai": "ca_nhan", "khoa": "noi_thuc_tap", "nhan": "Nơi thực tập", "gia_tri": NOI_TT},
]


class _Usage:
    token_in, token_out, cost_usd = 10, 20, 0.001


class _LLM:
    def __init__(self, ra):
        self.ra, self.prompt, self.so_lan_goi = ra, None, 0

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        self.prompt = messages[-1]["content"]
        self.so_lan_goi += 1
        return json.dumps(self.ra, ensure_ascii=False), _Usage()


def _van_ban(*noi_dung: str) -> dict:
    """Tên mục không mang chữ số: `lam_sach_van_ban` thay mọi cụm số không có
    trong nguồn, nên một tên mục "Mục 1" sẽ thành "Mục […]" và làm khó đọc
    khẳng định thật của test."""
    return {"tieu_de": "ĐƠN", "muc": [{"ten": f"Mục {chr(ord('A') + i)}", "vung": "than",
                                       "khoi": [{"noi_dung": nd, "bang": []}]}
                                      for i, nd in enumerate(noi_dung)]}


def _ra(**ghi_de) -> dict:
    ra = {"muc_dich": "tao_van_ban", "mo_ta": "", "tra_loi_ngan": "Bản thảo đây.",
          "quan_sat": [], "suy_luan": [], "can_du_kien": []}
    ra.update(ghi_de)
    return ra


def _st(query: str, **ghi_de) -> dict:
    return {"query": query, "intent": Intent.soan_thao, "user_sub": "u", "bo_nho_tai_khoan": NHO, **ghi_de}


def _chu_cua(van_ban: dict) -> str:
    """Toàn bộ chữ của văn bản đã dựng — tên mục, văn xuôi và từng ô bảng. Khẳng
    định phải chạy trên TẤT CẢ, không chỉ trên mục đầu: một giá trị đã nhớ lọt
    vào một ô bảng vẫn là một giá trị đã lọt."""
    return json.dumps(van_ban or {}, ensure_ascii=False)


# ── 1. Cái phủ định: văn bản mới KHÔNG mang điều đã nhớ ──────────────────────


def test_van_ban_moi_khong_mang_mot_gia_tri_da_nho_nao_khi_luot_khong_hoi_toi():
    """SẢN PHẨM của Phase 12 part B. Mô hình ở đây CỐ TÌNH điền cả ba giá trị
    đã nhớ vào văn bản — đúng chế độ hỏng mà hợp đồng cấm — và không giá trị
    nào được ra tới bản thảo. Lượt này chỉ xin "bản kiểm điểm cá nhân": không
    một nhãn nào của ba khoá ấy có mặt trong câu, nên không khoá nào được hỏi
    tới, nên không khoá nào là nguồn."""
    llm = _LLM(_ra(van_ban=_van_ban(
        f"Họ và tên: {HO_TEN}", f"Mã sinh viên: {MA_SV}",
        f"Nơi thực tập: {NOI_TT}", "Tôi xin kiểm điểm về việc đi muộn.")))
    ra = h.hieu_tai_lieu(_st("soạn cho tôi bản kiểm điểm cá nhân"), [], llm, "m")

    chu = _chu_cua(ra["van_ban_tong_quat"])
    assert HO_TEN not in chu, "tên đã nhớ tự chảy vào một văn bản người dùng không hỏi tới nó"
    assert MA_SV not in chu, "mã sinh viên đã nhớ tự chảy vào văn bản"
    assert NOI_TT not in chu, "nơi thực tập đã nhớ tự chảy vào văn bản"
    # Không phải vì mục bị bỏ sạch: văn bản vẫn còn, chỉ chỗ giá trị là chỗ trống.
    assert f"Họ và tên: {h.CHO_TRONG}" in chu and "Tôi xin kiểm điểm về việc đi muộn." in chu
    assert ra["traces"]["dung_ban_thao_so_bo_nho_chan"] == 3


def test_bang_cung_bi_chan_nhu_van_xuoi():
    """Một ô bảng cũng là một chỗ điền. `_sach` là hàm DUY NHẤT cả tên mục, văn
    xuôi và từng ô đi qua, nên lưới nằm ở đó chứ không nằm ở một nhánh riêng."""
    van_ban = {"tieu_de": "ĐƠN", "muc": [{"ten": "Thông tin", "vung": "than", "khoi": [
        {"noi_dung": "", "bang": [["Nhãn", "Giá trị"], ["Họ và tên", HO_TEN], ["Mã sinh viên", MA_SV]]}]}]}
    ra = h.hieu_tai_lieu(_st("soạn giúp tôi đơn xin xác nhận"), [], _LLM(_ra(van_ban=van_ban)), "m")
    chu = _chu_cua(ra["van_ban_tong_quat"])
    assert HO_TEN not in chu and MA_SV not in chu
    assert h.CHO_TRONG in chu


def test_gia_tri_nguoi_dung_tu_go_trong_luot_nay_KHONG_bi_chan():
    """Ranh giới của lưới: người dùng gõ thẳng cái tên ra trong chính lượt này
    mà KHÔNG gọi tên nhãn nào. Ở đó giá trị tới bằng lời họ, không bằng ký ức —
    chặn nó là xoá đúng thứ họ vừa viết, một hồi quy tệ hơn lỗi đang chữa.

    Fix round 1 (review MED) — gõ bằng CÁCH VIẾT HOA/THƯỜNG KHÁC với cái đang
    lưu. Bản trước của test dùng lại đúng cách viết đã lưu, nên nó không bao
    giờ chạm tới chỗ phép loại trừ (`normalize`, so chữ NGHIÊM) lệch với phép
    chặn (`IGNORECASE`) — và cái lệch ấy xoá chữ của chính người dùng."""
    tu_go = HO_TEN.lower()
    assert tu_go != HO_TEN, "test phải khác cách viết đang lưu thì mới đo được điều nó nói"
    llm = _LLM(_ra(van_ban=_van_ban(f"Kính gửi: {tu_go}", "Tôi xin xác nhận.")))
    ra = h.hieu_tai_lieu(_st(f"soạn đơn xin xác nhận gửi {tu_go}"), [], llm, "m")
    assert tu_go in _chu_cua(ra["van_ban_tong_quat"])
    assert ra["traces"]["dung_ban_thao_so_bo_nho_chan"] == 0


# ── 2. Lượt CÓ hỏi tới: ký ức dùng được ──────────────────────────────────────


def test_luot_hoi_toi_dung_nhan_thi_gia_tri_da_nho_di_vao_van_ban():
    llm = _LLM(_ra(van_ban=_van_ban(f"Họ và tên: {HO_TEN}", f"Mã sinh viên: {MA_SV}", "Tôi xin nghỉ.")))
    ra = h.hieu_tai_lieu(_st("soạn đơn xin nghỉ, điền họ và tên với mã sinh viên của tôi vào"), [], llm, "m")
    chu = _chu_cua(ra["van_ban_tong_quat"])
    assert HO_TEN in chu and MA_SV in chu
    # Khoá KHÔNG được hỏi tới trong cùng lượt ấy vẫn bị chặn — phép gác theo
    # từng khoá, không phải một công tắc bật/tắt cho cả ký ức.
    assert NOI_TT not in chu


def test_ky_uc_vao_prompt_du_luot_khong_hoi_toi():
    """R4 nửa còn lại: ký ức là NGỮ CẢNH, tới mô hình đúng đường `# Bản thảo
    đang có` đi. Nó ở trong prompt cả khi lượt không hỏi tới — để KLAW xưng hô
    đúng người — và chính vì thế lưới ở `lam_sach_van_ban` mới là thứ giữ lời
    hứa, không phải việc giấu dữ liệu khỏi mô hình."""
    llm = _LLM(_ra(van_ban=_van_ban("Tôi xin kiểm điểm.")))
    h.hieu_tai_lieu(_st("soạn cho tôi bản kiểm điểm cá nhân"), [], llm, "m")
    # Đúng KHỐI, không phải dòng quy tắc 15 nhắc tên khối: khối bắt đầu ở đầu dòng.
    assert KHOI_KY_UC in llm.prompt
    assert HO_TEN in llm.prompt
    # Không ký ức nào → không khối nào; prompt của mọi lượt khác không đổi một byte.
    llm2 = _LLM(_ra(van_ban=_van_ban("Tôi xin kiểm điểm.")))
    h.hieu_tai_lieu(_st("soạn cho tôi bản kiểm điểm cá nhân", bo_nho_tai_khoan=[]), [], llm2, "m")
    assert KHOI_KY_UC not in llm2.prompt and HO_TEN not in llm2.prompt


# ── 3. Rút dữ kiện: tất định, 0 token ────────────────────────────────────────


def test_rut_du_kien_khong_them_mot_luot_goi_mo_hinh_nao():
    """R5 đo bằng BỘ ĐẾM lượt gọi, không bằng một lời khẳng định. Lượt soạn có
    lời khai vẫn đúng MỘT lượt gọi — y như lượt không có lời khai nào."""
    cau = f"soạn đơn xin thực tập, Họ và tên: {HO_TEN}, mã sv: {MA_SV}, địa điểm thực tập là {NOI_TT}"
    llm = _LLM(_ra(van_ban=_van_ban("Tôi xin thực tập.")))
    ra = h.hieu_tai_lieu(_st(cau, bo_nho_tai_khoan=[]), [], llm, "m")
    assert llm.so_lan_goi == 1
    assert ra["bo_nho_moi"] == [
        {"loai": "ca_nhan", "khoa": "ho_ten", "gia_tri": HO_TEN},
        {"loai": "ca_nhan", "khoa": "ma_sv", "gia_tri": MA_SV},
        {"loai": "ca_nhan", "khoa": "noi_thuc_tap", "gia_tri": NOI_TT},
    ]
    assert ra["traces"]["bo_nho_so_khai"] == 3


@pytest.mark.parametrize("cau, cho", [
    (f"Họ và tên: {HO_TEN}", [("ho_ten", HO_TEN)]),
    ("lớp: K00A và ngành là Luật kinh tế", [("lop", "K00A"), ("nganh", "Luật kinh tế")]),
    ("xưng hô: em; văn phong là trang trọng", [("xung_ho", "em"), ("van_phong", "trang trọng")]),
    (f"nơi thực tập là {NOI_TT} và Đồng sự", [("noi_thuc_tap", f"{NOI_TT} và Đồng sự")]),
    ("ho ten: Tran Van Thu", [("ho_ten", "Tran Van Thu")]),
])
def test_doc_duoc_loi_khai_cua_nguoi_dung(cau, cho):
    assert [(d["khoa"], d["gia_tri"]) for d in h.rut_bo_nho(cau)] == cho


@pytest.mark.parametrize("cau", [
    "soạn cho tôi bản kiểm điểm cá nhân",
    "trong biểu mẫu có dòng Họ và tên: ………………………",
    "mã sinh viên: ___",
])
def test_khong_nhan_ra_loi_khai_nao_thi_khong_nho_gi(cau):
    """Chỗ TRỐNG của một biểu mẫu chưa điền không phải một giá trị — cùng phép
    `vung_trong` mà `_lay_truong` dùng, không phải một bản sao thứ hai."""
    assert h.rut_bo_nho(cau) == []


def test_chi_luot_soan_moi_rut_du_kien():
    """Người hỏi khai tên trong một lượt HỎI tài liệu thì đó là câu hỏi của họ,
    không phải một lời khai để lưu vĩnh viễn vào tài khoản."""
    llm = _LLM(_ra(muc_dich="hoi", tra_loi_ngan="Tài liệu nói vậy."))
    ra = h.hieu_tai_lieu({"query": f"trong phiếu này Họ và tên: {HO_TEN} nằm ở đâu"}, [], llm, "m")
    assert ra["bo_nho_moi"] == []


def test_chi_hai_loai_ca_nhan_va_thoi_quen_duoc_rut():
    """Brief cho phép ĐÚNG hai loại. Một khoá thứ ba lọt vào bảng sẽ đỏ ở đây
    trước khi nó kịp thành một dòng trong DB mà `ghi` từ chối."""
    assert {loai for loai, _ in h.BO_NHO_KHOA.values()} == set(bn.LOAI) == {"ca_nhan", "thoi_quen"}
    assert set(h.BO_NHO_KHOA) <= set(bn.NHAN_KHOA), "mỗi khoá rút được phải có nhãn để hiện cho người dùng"


# ── 4. "Đã nhớ": nói một lần, đúng cái mới ───────────────────────────────────


def test_ghi_bo_nho_chi_dat_nhan_cho_moi_va_doi(monkeypatch):
    """`ghi` trả `"giu"` khi giá trị y hệt cái đang có (part A, fix round
    `1350ae7`). Nói "đã nhớ" ở ca đó là báo cho người dùng mỗi lần họ nhắc lại
    tên mình — họ sẽ học cách bỏ qua dòng ấy, rồi bỏ qua luôn lần nó thật."""
    ket = {"ho_ten": "moi", "ma_sv": "doi", "noi_thuc_tap": "giu"}
    monkeypatch.setattr(bn, "ghi", lambda sub, loai, khoa, gia_tri, pid=None: ket[khoa])
    st = g._ghi_bo_nho({"user_sub": "u", "hoi_thoai_id": str(uuid.uuid4()),
                        "bo_nho_moi": [{"loai": r["loai"], "khoa": r["khoa"], "gia_tri": r["gia_tri"]} for r in NHO]})
    assert st["bo_nho_da_nho"] == ["Họ và tên", "Mã sinh viên"]
    assert st["bo_nho_moi"] == [], "đã ghi rồi thì không còn là việc chờ"


def test_ghi_bo_nho_hong_khong_lam_hong_luot(monkeypatch):
    def no(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(bn, "ghi", no)
    st = g._ghi_bo_nho({"user_sub": "u", "bo_nho_moi": [{"loai": "ca_nhan", "khoa": "ho_ten", "gia_tri": HO_TEN}]})
    assert st["bo_nho_da_nho"] == []


def test_khach_chua_dang_nhap_khong_nap_va_khong_ghi_ky_uc_nao():
    st = {"query": f"soạn đơn, Họ và tên: {HO_TEN}", "bo_nho_moi": [{"loai": "ca_nhan", "khoa": "ho_ten",
                                                                     "gia_tri": HO_TEN}]}
    assert "bo_nho_tai_khoan" not in g._nap_bo_nho(dict(st))
    assert "bo_nho_da_nho" not in g._ghi_bo_nho(dict(st))


def test_loi_dap_noi_da_nho_dung_mot_dong_va_im_khi_khong_co_gi_moi():
    bt = {"id": "b1", "loai": "tong_quat", "ten": "Bản thảo tổng quát", "phien_ban": 1,
          "document": "# ĐƠN", "clauses": [{"key": "muc_1"}], "audit_report": {}, "facts": {},
          "doi_so_voi_truoc": []}
    st = {"query": "soạn đơn", "intent": Intent.soan_thao, "muc_dich_tai_lieu": "tao_van_ban",
          "user_sub": "u", "ban_thao_ket": bt, "bo_nho_da_nho": ["Họ và tên", "Mã sinh viên"]}
    ra = assemble(st, {}, None, "")
    assert ra["result_type"] == ResultType.ban_thao
    assert ra["answer"].endswith(asm.DA_NHO.format(nhan="Họ và tên, Mã sinh viên"))
    assert "kho của tôi" not in ra["answer"], "R5 (Phase 14): không gọi corpus là kho"

    assert asm.DA_NHO.format(nhan="") not in assemble({**st, "bo_nho_da_nho": []}, {}, None, "")["answer"]
    assert "đã nhớ" not in assemble({**st, "bo_nho_da_nho": []}, {}, None, "")["answer"]


def test_luot_soan_hong_van_noi_da_nho():
    """Hết hạn mức: `hieu_tai_lieu` (nơi rút dữ kiện) đã chạy TRƯỚC phép kiểm
    hạn mức ở `dung_ban_thao_tong_quat`, nên điều họ khai ĐÃ được ghi. Im lặng
    ở đây là giấu đúng cái R3 bắt phải nói."""
    st = {"query": "soạn đơn", "intent": Intent.soan_thao, "muc_dich_tai_lieu": "tao_van_ban",
          "user_sub": "u", "ban_thao_ket": None, "ban_thao_tong_quat_loi": "Bạn đã hết lượt soạn thảo hôm nay.",
          "bo_nho_da_nho": ["Họ và tên"]}
    ra = assemble(st, {}, None, "")
    assert ra["result_type"] == ResultType.soan_thao_hoi
    assert ra["answer"].startswith("Bạn đã hết lượt soạn thảo hôm nay.")
    assert ra["answer"].endswith(asm.DA_NHO.format(nhan="Họ và tên"))


# ── 5. Vòng rà soát độc lập: đường ký ức đi vòng qua hợp đồng ───────────────


def test_truong_cua_tai_lieu_khong_thanh_cua_sau_cho_gia_tri_da_nho():
    """Đường vòng số một, và là đường duy nhất mục 1 ở trên KHÔNG thấy: mọi ca
    trên đều chạy với `tai_lieu=[]`, nên `truong` không bao giờ neo được.

    CÓ tài liệu thì khác hẳn. Một biểu mẫu có dòng TRẮNG "Họ và tên:" cho mô
    hình đúng một đoạn trích THẬT để neo, và `_lay_truong` chỉ kiểm đoạn trích
    ấy — nó không kiểm `gia_tri`. Mô hình đặt giá trị ĐÃ NHỚ vào đó là dòng ấy
    đi hai đường cùng lúc: xuống `du_kien_tai_lieu` (facts, R4 cấm) và vào
    `_nguon_soan`, nơi nó tự cấp phép cho chính mình nên `cam` hết hiệu lực.
    Lượt này không gọi tên một nhãn nào."""
    tl = [{"id": "aaaaaaaa-0000-0000-0000-000000000001", "ten_tep": "mau.docx", "don_vi": [
        DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="ĐƠN XIN NGHỈ VIỆC"),
        DonViVanBan(chi_so=1, trang=1, offset_dau=20, noi_dung="Họ và tên:"),
    ]}]
    llm = _LLM(_ra(
        van_ban=_van_ban(f"Họ và tên: {HO_TEN}", "Tôi xin nghỉ việc."),
        truong=[{"khoa": "ho_ten", "nhan": "Họ và tên", "gia_tri": HO_TEN, "trich": "Họ và tên:"}],
    ))
    ra = h.hieu_tai_lieu(_st("soạn giúp tôi đơn xin nghỉ việc"), tl, llm, "m")

    assert HO_TEN not in _chu_cua(ra["van_ban_tong_quat"]), "ký ức đi vòng qua `truong` vào văn bản"
    assert ra["tai_lieu_du_kien_moi"] == [], "ký ức thành dữ kiện của tài liệu — R4 cấm đúng điều này"
    # Đếm ĐÚNG cái thật sự bị chặn: bản lỗi báo 0 trong khi giá trị vẫn ra tới
    # trang giấy, nên một con số 0 ở đây không chứng minh được gì.
    assert ra["traces"]["dung_ban_thao_so_bo_nho_chan"] == 1


@pytest.mark.parametrize("cam, cau", [
    # `nganh = "Luật"` trên một sản phẩm PHÁP LUẬT, ở MỌI bản thảo.
    (["Luật"], "Người lao động cam kết tuân thủ Bộ luật Lao động."),
    # Dòng địa danh-ngày tháng chuẩn của mọi văn bản hành chính Việt Nam.
    (["Hà Nội"], "Hà Nội, ngày … tháng … năm …"),
    (["Thử"], "Thời gian thử việc do hai bên thoả thuận."),
    (["em"], "em xin trình bày như sau."),
])
def test_ky_uc_khong_duoc_xoa_loi_van_binh_thuong(cam, cau):
    """Đường vòng số hai. Lưới `cam` từng là một phép so khớp `\\b…\\b` ở BẤT KỲ
    đâu trong tên mục, văn xuôi và từng ô bảng — nên nó xoá cả tiếng Việt bình
    thường, thành `[…]`, ở mọi bản thảo. Chạy qua CHÍNH `lam_sach_van_ban`, chứ
    không qua một bản sao của phép so khớp."""
    vb = {"tieu_de": "", "muc": [{"ten": "Nội dung", "vung": "than",
                                  "khoi": [{"noi_dung": cau, "bang": []}]}]}
    sach, dem = h.lam_sach_van_ban(vb, "", None, cam)
    assert sach["muc"][0]["khoi"][0]["noi_dung"] == cau
    assert dem["bo_nho_khong_dien"] == 0


def test_thoi_quen_khong_bao_gio_vao_cam():
    """Nửa còn lại của đường vòng số hai, và nó tự gây ra: `_khoi_bo_nho` BẢO mô
    hình dùng ký ức để xưng hô và chọn văn phong, còn nhãn của những khoá ấy
    không phải thứ ai gõ khi xin soạn một lá đơn — nên chúng LUÔN bị coi là
    không được hỏi tới, và luôn nằm trong `cam`. Thiết kế ra lệnh sinh ra đúng
    chuỗi mà chính nó đi xoá."""
    cau = "em xin trình bày như sau."
    nho = [*NHO, {"loai": "thoi_quen", "khoa": "xung_ho", "nhan": "Xưng hô", "gia_tri": "em"}]
    assert not h.khoa_duoc_hoi("soạn giúp tôi đơn xin nghỉ", "xung_ho"), (
        "nếu khoá này bỗng được coi là 'có hỏi tới' thì test không còn đo điều nó nói"
    )
    llm = _LLM(_ra(van_ban=_van_ban(cau)))
    ra = h.hieu_tai_lieu(_st("soạn giúp tôi đơn xin nghỉ", bo_nho_tai_khoan=nho), [], llm, "m")
    assert cau in _chu_cua(ra["van_ban_tong_quat"])
    assert ra["traces"]["dung_ban_thao_so_bo_nho_chan"] == 0


def test_cau_giai_nghia_viet_lai_khong_ghi_de_ky_uc_va_khong_mo_cong():
    """Đường vòng số ba. Từ lượt 2 trở đi `giai_nghia` GHI ĐÈ `query` bằng một
    câu do MÔ HÌNH soạn, nên `cau_hoi_day_du` là chữ của mô hình. Chạy phép rút
    ký ức trên đó là ghi vào TÀI KHOẢN một cái tên mô hình nhặt ở lượt trước;
    chạy phép gác "lượt này có hỏi tới không" trên đó là để mô hình tự cấp phép
    xả ký ức vào văn bản. Không ca nào ở trên đặt `cau_hoi_day_du`, nên bộ test
    cũ mù hẳn với cả hai."""
    viet_lai = "soạn cho tôi bản kiểm điểm cá nhân, họ và tên là Trần Văn Mẫu, về việc đi muộn"
    llm = _LLM(_ra(van_ban=_van_ban(f"Họ và tên: {HO_TEN}", "Tôi xin kiểm điểm.")))
    ra = h.hieu_tai_lieu(
        _st("soạn cho tôi bản kiểm điểm",
            cau_hoi_goc="soạn cho tôi bản kiểm điểm", cau_hoi_day_du=viet_lai),
        [], llm, "m")
    assert ra["bo_nho_moi"] == [], "tên người thứ ba do mô hình viết ra bị ghi đè lên ký ức tài khoản"
    assert HO_TEN not in _chu_cua(ra["van_ban_tong_quat"]), "câu mô hình viết lại tự mở cổng cho ký ức"


def test_dan_ca_bieu_mau_khong_thanh_loi_khai_tung_dong():
    """Đường vòng số bốn. Dấu mở của `_RE_KHAI_BO_NHO` từng nhận `\\n`, nên MỖI
    DÒNG của một khối dán là một lời khai mới: dán nguyên một biểu mẫu ghi cả
    khối ấy vào tài khoản NHƯ THỂ là dữ kiện về chính người dán — dữ liệu cá
    nhân của người thứ ba, kể cả một mã sinh viên, vào DB từ văn bản tự do."""
    mau = ("điền giúp tôi biểu mẫu này\n"
           "Họ và tên: Trần Thị Mẫu\n"
           "Lớp: K00B\n"
           "Mã sinh viên: 00000001")
    assert h.rut_bo_nho(mau) == []


def test_loi_ghi_ky_uc_khong_dua_gia_tri_vao_log(monkeypatch, caplog):
    """Đường vòng số năm. `logger.exception` kèm `exc_info`, và
    `StatementError.__str__` của SQLAlchemy nối thêm `[SQL: …] [parameters: …]`
    — mà `src/services/db.py` dựng engine KHÔNG có `hide_parameters=True`, nên
    tham số ở đây chính là `gia_tri`. Một nhịp chập của DB là họ tên và mã sinh
    viên vào log."""
    def no(*a, **k):
        raise StatementError("khong ghi duoc", "INSERT INTO bo_nho_tai_khoan (gia_tri) VALUES (%(gia_tri)s)",
                             {"gia_tri": HO_TEN, "khoa": "ho_ten"}, Exception("boom"))

    monkeypatch.setattr(bn, "ghi", no)
    with caplog.at_level(logging.WARNING):
        g._ghi_bo_nho({"user_sub": "u", "bo_nho_moi": [{"loai": "ca_nhan", "khoa": "ho_ten",
                                                        "gia_tri": HO_TEN}]})
    assert caplog.records, "lỗi vẫn phải để lại dấu vết — im lặng không phải cách sửa rò dữ liệu"
    for r in caplog.records:
        assert r.exc_info is None, "`exc_info` kéo cả `[parameters: …]` vào log"
        assert HO_TEN not in r.getMessage() and HO_TEN not in (r.exc_text or "")
    # Đủ để lần ra sự cố: TÊN TRƯỜNG, không phải giá trị của nó.
    assert "ho_ten" in caplog.records[0].getMessage()


# ── 6. Đầu-cuối qua DB: khai ở hội thoại này, nhớ ở hội thoại khác ───────────


@pytest.fixture
def tai_khoan():
    # Bảng chỉ được tạo lúc app khởi động (`MIGRATIONS_KHOI_DONG`); test tự áp
    # migration để không lệ thuộc một lần restart uvicorn.
    run_migrations("034")
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    yield sub
    with get_engine().begin() as c:
        from sqlalchemy import text

        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


@pytest.mark.integration
def test_khai_o_hoi_thoai_nay_duoc_nho_o_hoi_thoai_khac_va_khong_noi_lai(tai_khoan):
    """Đầu-cuối qua đúng hai phép DB của graph (`_nap_bo_nho`/`_ghi_bo_nho`),
    không phải qua tầng dịch vụ (part A đã chứng minh tầng đó). Hội thoại thứ
    hai là một `hoi_thoai_id` KHÁC: ký ức thuộc về TÀI KHOẢN, không về hội
    thoại (R1)."""
    ht1, ht2 = str(uuid.uuid4()), str(uuid.uuid4())
    cau_khai = f"soạn đơn xin thực tập, Họ và tên: {HO_TEN}, mã sv: {MA_SV}"

    st1 = g._nap_bo_nho({"query": cau_khai, "intent": Intent.soan_thao, "user_sub": tai_khoan, "hoi_thoai_id": ht1})
    ra1 = g._ghi_bo_nho(h.hieu_tai_lieu(st1, [], _LLM(_ra(van_ban=_van_ban("Tôi xin thực tập."))), "m"))
    assert ra1["bo_nho_da_nho"] == ["Họ và tên", "Mã sinh viên"]

    # Hội thoại KHÁC, cùng tài khoản: ký ức tới được prompt, và tới được văn bản
    # vì lượt này hỏi tới đúng nhãn của nó.
    st2 = g._nap_bo_nho({"query": "soạn đơn xin nghỉ, điền họ và tên của tôi vào",
                         "intent": Intent.soan_thao, "user_sub": tai_khoan, "hoi_thoai_id": ht2})
    assert [r["gia_tri"] for r in st2["bo_nho_tai_khoan"]] == [HO_TEN, MA_SV]
    llm2 = _LLM(_ra(van_ban=_van_ban(f"Họ và tên: {HO_TEN}", "Tôi xin nghỉ.")))
    ra2 = h.hieu_tai_lieu(st2, [], llm2, "m")
    assert HO_TEN in llm2.prompt
    assert HO_TEN in _chu_cua(ra2["van_ban_tong_quat"])

    # Nhắc lại y hệt ở hội thoại thứ hai: `ghi` trả "giu", không nói "đã nhớ" lần nữa.
    st3 = g._nap_bo_nho({"query": cau_khai, "intent": Intent.soan_thao, "user_sub": tai_khoan, "hoi_thoai_id": ht2})
    ra3 = g._ghi_bo_nho(h.hieu_tai_lieu(st3, [], _LLM(_ra(van_ban=_van_ban("Tôi xin thực tập."))), "m"))
    assert ra3["bo_nho_da_nho"] == []
    assert len(bn.liet_ke(tai_khoan)) == 2, "khai lại không sinh dòng thứ ba"


@pytest.mark.integration
def test_van_ban_moi_o_hoi_thoai_khac_van_khong_mang_gia_tri_da_nho(tai_khoan):
    """Cái phủ định, lần này với ký ức đọc THẬT từ DB chứ không từ một fixture
    dựng tay: đường đi đầy đủ nào cũng phải cho ra cùng một văn bản trống chỗ."""
    bn.ghi(tai_khoan, "ca_nhan", "ho_ten", HO_TEN)
    bn.ghi(tai_khoan, "ca_nhan", "ma_sv", MA_SV)
    st = g._nap_bo_nho({"query": "soạn cho tôi bản kiểm điểm cá nhân", "intent": Intent.soan_thao,
                        "user_sub": tai_khoan, "hoi_thoai_id": str(uuid.uuid4())})
    llm = _LLM(_ra(van_ban=_van_ban(f"Họ và tên: {HO_TEN}", f"Mã sinh viên: {MA_SV}", "Tôi xin kiểm điểm.")))
    chu = _chu_cua(h.hieu_tai_lieu(st, [], llm, "m")["van_ban_tong_quat"])
    assert HO_TEN not in chu and MA_SV not in chu
