"""Câu hỏi VỀ CHÍNH TRỢ LÝ không phải câu hỏi pháp luật ngoài phạm vi.

Chủ dự án hỏi "bạn làm được những gì" và nhận về "Câu hỏi này nằm ngoài phạm vi
của hệ thống." Thông tin đúng nằm ngay bên dưới lời từ chối đó — nên hệ thống
BIẾT câu trả lời và vẫn chọn từ chối. Đó là hỏng ở khâu định tuyến, không phải
thiếu dữ liệu.

Hai câu này khác hẳn nhau và trước bản này dùng chung một lời đáp:

  "Thuế thu nhập cá nhân tính thế nào?"  → ngoài phạm vi THẬT, từ chối là đúng
  "bạn làm được những gì"                → hỏi về chính trợ lý, phải trả lời

`gioi_thieu` tách hai thứ đó. Nó KHÔNG gọi LLM để dựng câu trả lời — nội dung
là sự thật về hệ thống, đọc từ DB, nên 0 token cho khâu hành văn.
"""

import pytest

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.route import Intent
from src.config import get_settings
from src.services.llm import generate_model, judge_model, router_model


def test_intent_co_nhanh_gioi_thieu():
    assert Intent.gioi_thieu == "gioi_thieu"


def test_hoi_ve_tro_ly_KHONG_ra_out_of_scope():
    """Lỗi chủ dự án chỉ ra: câu hỏi về trợ lý bị đối xử như câu hỏi về thuế."""
    st = assemble({"query": "bạn làm được những gì", "intent": "gioi_thieu"}, {}, None, "")
    assert st["result_type"] != ResultType.out_of_scope, (
        "hỏi trợ lý làm được gì KHÔNG phải câu hỏi ngoài phạm vi — "
        "hệ thống biết câu trả lời và phải nói ra"
    )
    assert st["result_type"] == ResultType.gioi_thieu


def test_gioi_thieu_tra_loi_thay_vi_tu_choi():
    st = assemble({"query": "bạn là ai", "intent": "gioi_thieu"}, {}, None, "")
    ans = st["answer"] or ""
    assert ans, "phải CÓ câu trả lời, không được để rỗng như abstain"
    assert "ngoài phạm vi" not in ans, "không được mở bằng lời từ chối"
    # Nêu được cả hai việc nó làm, và nêu ra ranh giới — nói được mình làm gì
    # mà không nói được mình KHÔNG làm gì thì vẫn là quảng cáo, không phải
    # câu trả lời trung thực.
    assert "tra cứu" in ans.lower()
    assert "soạn thảo" in ans.lower()
    assert "thuế" in ans.lower(), "phải nêu thứ KHÔNG phủ, không chỉ khoe thứ phủ"


def test_gioi_thieu_khong_ton_token():
    """0 token: `llm=None` ở trên đã chứng minh — gọi LLM sẽ nổ AttributeError."""
    st = assemble({"query": "klaw là gì", "intent": "gioi_thieu"}, {}, None, "")
    assert st["traces"]["assemble_token_in"] == 0
    assert st["traces"]["assemble_token_out"] == 0


def test_ngoai_pham_vi_van_tu_choi_nhu_cu():
    """Mặt còn lại: câu hỏi pháp luật ngoài phạm vi VẪN phải bị từ chối."""
    st = assemble({"query": "thuế TNCN tính sao", "intent": "ngoai_pham_vi"}, {}, None, "")
    assert st["result_type"] == ResultType.out_of_scope
    assert st["answer"] is None


# ══ Một lời đáp cho MỌI câu hỏi là chính lỗi, không phải nền để cải thiện ════
#
# ĐO ĐƯỢC trên UI 2026-09-02, hai dòng liền nhau trong bảng `traces`:
#   09:21:36  "bạn làm được những gì"  → gioi_thieu
#   09:22:22  "model của bạn là gì"    → gioi_thieu
# Hai câu hỏi KHÁC NHAU nhận về đúng cùng một đoạn văn, TỪNG CHỮ MỘT. Câu đó mở
# bằng "Chào bạn." rồi liệt kê năng lực — hợp lý cho câu thứ nhất, vô nghĩa cho
# câu thứ hai, và vô nghĩa cho một lời chào đơn thuần.
#
# Các phép kiểm dưới đây khoá HÌNH DẠNG của lời đáp, không khoá lời: chúng so
# các dạng với NHAU và tra tên model từ chính config, nên viết lại câu chữ không
# làm chúng đỏ oan — chỉ gộp hai dạng lại làm một mới làm.


def _tra_loi(cau_hoi: str) -> str:
    st = assemble({"query": cau_hoi, "intent": "gioi_thieu"}, {}, None, "")
    return st["answer"] or ""


# Bốn dạng brief đòi, cộng "cảm ơn" — dạng thứ năm `docs/bo-luat-agent.md` (dòng
# 5) ghi là cũng rơi vào `intent=gioi_thieu`.
DANG = {
    "chao": "chào bạn",
    "nang_luc": "bạn làm được những gì",
    "model": "model của bạn là gì",
    "nguon": "dữ liệu của bạn lấy từ đâu",
    "cam_on": "cảm ơn bạn nhiều",
}


def test_moi_dang_cau_hoi_cho_MOT_cau_tra_loi_RIENG():
    """Chính lỗi cần chặn. So các dạng với nhau, không so với một chuỗi chép
    tay: một phép kiểm liệt kê lời sẽ đỏ mỗi lần ai đó sửa câu chữ, còn phép
    kiểm này chỉ đỏ khi hai dạng lại dùng chung một lời đáp."""
    dap = {ten: _tra_loi(cau) for ten, cau in DANG.items()}
    trung = {a: b for i, (a, x) in enumerate(dap.items())
             for b, y in list(dap.items())[i + 1:] if x == y}
    assert trung == {}, f"các dạng dùng chung một lời đáp: {trung}"


def test_cau_hoi_ve_model_neu_TEN_MODEL_tu_config():
    """Tên model TRA TỪ CONFIG THẬT, không viết cứng: config đang chạy
    `deepseek/deepseek-v4-flash-0731` cho vai sinh, khác hẳn mặc định trong mã —
    một chuỗi viết cứng sẽ nói sai mà không test nào đỏ."""
    ans = _tra_loi(DANG["model"])
    for vai, ten in (("định tuyến", router_model()),
                     ("sinh", generate_model()),
                     ("thẩm định", judge_model())):
        assert ten in ans, f"thiếu tên model vai {vai}: {ten}"
        assert vai in ans.lower(), f"nêu tên model mà không nêu vai {vai}"
    # Điểm đáng nói không phải tên model mà là việc hai vai KHÁC HỌ nhau.
    assert "họ" in ans.lower()


def test_cau_hoi_ve_model_KHONG_ro_ri_gi_ngoai_TEN_MODEL():
    """Không API key, không base URL, không một giá trị nào khác từ `.env`.
    Key thật ĐANG có trong `.env.local` của máy chạy, nên phép kiểm này đo được
    chứ không phải giả định."""
    s = get_settings()
    for cau in (DANG["model"], "bạn chạy bằng gì", "bạn dùng AI gì"):
        ans = _tra_loi(cau)
        assert "sk-" not in ans
        assert "OPENROUTER_API_KEY" not in ans
        assert "api key" not in ans.lower() and "api_key" not in ans.lower()
        assert "http" not in ans, "không in URL nào"
        if s.openrouter_api_key:
            assert s.openrouter_api_key not in ans
        if s.openrouter_base_url:
            assert s.openrouter_base_url not in ans


def test_loi_chao_KHONG_doi_ca_bai_nang_luc_vao_mat_nguoi_ta():
    chao, nang_luc = _tra_loi(DANG["chao"]), _tra_loi(DANG["nang_luc"])
    assert len(chao) * 3 < len(nang_luc), (
        f"lời chào dài {len(chao)} so với bài năng lực {len(nang_luc)} — "
        "một lời chào không phải chỗ liệt kê phạm vi"
    )
    assert "thuế" not in chao.lower(), "lời chào không liệt kê thứ chưa phủ"
    # Vẫn phải mời hỏi, không phải một câu chào rồi hết.
    assert "?" in chao or "hỏi" in chao.lower()


def test_chao_kem_cau_hoi_KHONG_bi_doc_thanh_chao_don_thuan():
    """"chào bạn, bạn làm được những gì" là một câu HỎI có lời chào dẫn vào —
    trả nó lời chào ngắn là bỏ mất câu hỏi thật."""
    assert _tra_loi("chào bạn, bạn làm được những gì") == _tra_loi(DANG["nang_luc"])


def test_cau_hoi_ve_nguon_neu_TEN_nguon_va_KHONG_in_URL():
    s = get_settings()
    ans = _tra_loi("dữ liệu của bạn lấy từ đâu, có tin được không")
    assert "cơ sở dữ liệu quốc gia về văn bản pháp luật" in ans.lower()
    assert "hợp nhất" in ans.lower(), "phải nói kho là văn bản GỐC, không phải bản hợp nhất"
    assert "hai tầng" in ans.lower(), "phải nêu cơ chế kiểm chứng hai tầng"
    assert "http" not in ans and s.moj_api_base not in ans, "nêu TÊN nguồn, không in URL"
    assert "moj.gov.vn" not in ans


def test_dang_LA_roi_ve_bai_nang_luc_chu_khong_roi_vao_im_lang():
    """Mặc định an toàn hiện nay là dạng 2 — câu không khớp dạng nào vẫn nhận
    được lời đáp đầy đủ nhất, không nhận màn hình trắng."""
    nang_luc = _tra_loi(DANG["nang_luc"])
    for cau in ("bạn hoạt động ra sao", "klaw là gì", "bạn là ai", ""):
        assert _tra_loi(cau) == nang_luc, f"{cau!r} phải rơi về bài năng lực"


@pytest.mark.parametrize("cau_hoi", list(DANG.values()), ids=list(DANG))
def test_moi_dang_deu_giu_0_TOKEN(cau_hoi):
    """`llm=None` là bằng chứng, không phải giả định: một lượt gọi LLM ở nhánh
    này sẽ nổ AttributeError chứ không lặng lẽ tốn token."""
    st = assemble({"query": cau_hoi, "intent": "gioi_thieu"}, {}, None, "")
    assert st["result_type"] == ResultType.gioi_thieu
    assert st["traces"]["assemble_token_in"] == 0
    assert st["traces"]["assemble_token_out"] == 0
