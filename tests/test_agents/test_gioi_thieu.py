"""Câu hỏi VỀ CHÍNH TRỢ LÝ không phải câu hỏi pháp luật ngoài phạm vi.

Chủ dự án hỏi "bạn làm được những gì" và nhận về "Câu hỏi này nằm ngoài phạm vi
của hệ thống." Thông tin đúng nằm ngay bên dưới lời từ chối đó — nên hệ thống
BIẾT câu trả lời và vẫn chọn từ chối. Đó là hỏng ở khâu định tuyến, không phải
thiếu dữ liệu.

Hai câu này khác hẳn nhau và trước bản này dùng chung một lời đáp:

  "Thuế thu nhập cá nhân tính thế nào?"  → ngoài phạm vi THẬT, từ chối là đúng
  "bạn làm được những gì"                → hỏi về chính trợ lý, phải trả lời

`gioi_thieu` tách hai thứ đó. Từ quyết định 2026-09-30 mục 1, lời đáp do model
viết trong MỘT lượt, chỉ từ bảng dữ kiện mã dựng (`test_tra_loi_meta.py`). Các
test ở đây gọi `assemble(..., llm=None)`: không có model thì lời đáp là câu dự
phòng ghép từ chính các dòng của bảng — và các test canh sự thật của từng dạng
trên chính câu đó.
"""

from pathlib import Path

import pytest

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.gioi_thieu import cau_gioi_thieu
from src.agents.nodes.route import Intent
from src.config import get_settings
from src.services.llm import Usage, generate_model, judge_model, router_model


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
    # Trước bản này câu hỏi ở đây là "bạn là ai" — T3 tách nó sang `DANH_TINH`
    # (xem test_giong_tra_loi_khac_nhau_chi_mot_tu ở dưới), nên đổi sang đúng
    # dạng bài này canh: "làm được những gì".
    st = assemble({"query": "bạn làm được những gì", "intent": "gioi_thieu"}, {}, None, "")
    ans = st["answer"] or ""
    assert ans, "phải CÓ câu trả lời, không được để rỗng như abstain"
    assert "ngoài phạm vi" not in ans, "không được mở bằng lời từ chối"
    # Nêu được cả hai việc nó làm.
    assert "tra cứu" in ans.lower()
    assert "soạn" in ans.lower()
    # ĐỔI HỢP ĐỒNG (ex.md §4.2, §4.3): bản trước đòi bài năng lực nêu đích danh
    # "thuế" — tức đòi nó liệt kê phạm vi kho. Phạm vi kho nay là hai khía cạnh
    # RIÊNG (`bo_luat`, `linh_vuc`) dựng từ DB lúc chạy, chỉ nói khi người ta
    # hỏi; "bạn làm được gì?" chỉ trả năng lực chính. Một danh sách lĩnh vực
    # hay tên Bộ luật viết cứng trong bài năng lực chính là lỗi §2.5.
    assert "thuế" not in ans.lower(), "câu hỏi năng lực không tự đổ phạm vi kho ra"
    assert "Hàng hải" not in ans, "không còn tên Bộ luật viết cứng trong bài năng lực"


def test_khong_co_model_van_tra_loi_tu_bang_va_ghi_ly_do():
    """Không có model (hay model lỗi) không phải HTTP 500: lời đáp là câu dự
    phòng từ bảng, và trace nói vì sao (`gioi_thieu_nguon`)."""
    st = assemble({"query": "klaw là gì", "intent": "gioi_thieu"}, {}, None, "")
    assert st["answer"] and st["traces"]["gioi_thieu_nguon"] == "loi"
    assert st["traces"]["assemble_token_in"] == 0


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


# Bốn dạng brief gốc đòi, cộng "cảm ơn" (dạng thứ năm, `docs/bo-luat-agent.md`
# dòng 5 ghi là cũng rơi vào `intent=gioi_thieu`), cộng "danh tính"/"bản chất"
# (T3 tách khỏi năng lực — trước bản này "bạn là ai" và "klaw là gì" đều rơi về
# `nang_luc`).
DANG = {
    "chao": "chào bạn",
    "nang_luc": "bạn làm được những gì",
    "model": "model của bạn là gì",
    "nguon": "dữ liệu của bạn lấy từ đâu",
    "cam_on": "cảm ơn bạn nhiều",
    "danh_tinh": "bạn là ai",
    "ban_chat": "bạn là gì",
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
    """ĐỔI HỢP ĐỒNG (ex.md §4.2): phép canh cũ khoá TỈ LỆ `len(chao)*3 <
    len(nang_luc)` — nó chỉ có nghĩa khi bài năng lực là một bức tường chữ.
    Bài năng lực nay ngắn theo đúng yêu cầu ("tối đa 3 khối", "mỗi ý một lần"),
    nên tỉ lệ đó đo ngược lại chính thứ nó muốn bảo vệ. Khoá thẳng ĐIỀU CẦN
    CHẶN: một lời chào không phải chỗ liệt kê phạm vi kho."""
    chao, nang_luc = _tra_loi(DANG["chao"]), _tra_loi(DANG["nang_luc"])
    assert chao != nang_luc
    assert "thuế" not in chao.lower(), "lời chào không liệt kê lĩnh vực"
    assert "Bộ luật" not in chao, "lời chào không liệt kê Bộ luật"
    # Vẫn phải mời hỏi, không phải một câu chào rồi hết.
    assert "?" in chao or "hỏi" in chao.lower()


def test_chao_kem_cau_hoi_KHONG_bi_doc_thanh_chao_don_thuan():
    """"chào bạn, bạn làm được những gì" là một câu HỎI có lời chào dẫn vào —
    trả nó lời chào ngắn là bỏ mất câu hỏi thật.

    ĐỔI HỢP ĐỒNG (ex.md §4.3): lượt đầu nay ĐƯỢC chào lại một cụm ngắn khi câu
    hỏi mở bằng lời chào, nên hai lời đáp lệch nhau đúng tiền tố đó — phần trả
    lời thật vẫn phải giống hệt."""
    assert _tra_loi("chào bạn, bạn làm được những gì") == "Chào bạn. " + _tra_loi(DANG["nang_luc"])


def test_cau_hoi_ve_nguon_neu_TEN_nguon_va_KHONG_in_URL():
    s = get_settings()
    ans = _tra_loi("dữ liệu của bạn lấy từ đâu, có tin được không")
    assert "cơ sở dữ liệu quốc gia về văn bản pháp luật" in ans.lower()
    assert "hợp nhất" in ans.lower(), "phải nói kho là văn bản GỐC, không phải bản hợp nhất"
    assert "hai tầng" in ans.lower(), "phải nêu cơ chế kiểm chứng hai tầng"
    assert "http" not in ans and s.moj_api_base not in ans, "nêu TÊN nguồn, không in URL"
    assert "moj.gov.vn" not in ans


def test_cau_khong_khop_dang_nao_roi_ve_bai_nang_luc_chu_khong_im_lang():
    """Đổi tên (trước đây tên này còn canh CẢ "bạn là ai" và "klaw là gì" rơi về
    đây — nay hai câu đó có lời đáp RIÊNG, `DANH_TINH`/`BAN_CHAT`, xem
    `test_la_ai_va_la_gi_khac_nhau_chi_mot_tu` bên dưới). Mặc định an toàn hiện
    nay vẫn là dạng năng lực — câu không khớp dạng nào (kể cả danh tính/bản
    chất) vẫn nhận được lời đáp đầy đủ nhất, không nhận màn hình trắng."""
    nang_luc = _tra_loi(DANG["nang_luc"])
    # "bạn có bao nhiêu văn bản" đã RỜI danh sách này: nó nay là khía cạnh
    # `kho` (ex.md §4.3 "kho có gì?" trả phạm vi kho, không thành bài năng lực).
    for cau in ("bạn hoạt động ra sao", "bạn giúp được gì", ""):
        assert _tra_loi(cau) == nang_luc, f"{cau!r} phải rơi về bài năng lực"


def test_la_ai_va_la_gi_khac_nhau_chi_mot_tu():
    """Phép canh TRUNG TÂM của T3: "bạn là ai" và "bạn là gì" chỉ khác một từ,
    và chủ dự án nêu đích danh hai câu này phải ra hai lời đáp khác nhau —
    trước bản này cả hai đều rơi về `NANG_LUC`."""
    danh_tinh, ban_chat = _tra_loi(DANG["danh_tinh"]), _tra_loi(DANG["ban_chat"])
    assert danh_tinh != ban_chat
    assert danh_tinh.startswith("Tôi là KLAW")
    assert "luật sư" in ban_chat.lower() and "không phải" in ban_chat.lower()


def test_model_va_nguon_khong_bi_la_ai_la_gi_cuop_mat():
    """`model của bạn là ai` phải vẫn ra bảng model (không phải `DANH_TINH`), và
    `bạn chạy bằng mô hình gì` phải vẫn ra bảng model (không phải `BAN_CHAT`) —
    ba biểu thức không tranh nhau nhờ thứ tự kiểm trong `cau_gioi_thieu`."""
    bang_model = _tra_loi(DANG["model"])
    tu_la_ai = _tra_loi("model của bạn là ai")
    tu_la_gi = _tra_loi("bạn chạy bằng mô hình gì")
    assert tu_la_ai == bang_model and tu_la_ai != _tra_loi(DANG["danh_tinh"])
    assert tu_la_gi == bang_model and tu_la_gi != _tra_loi(DANG["ban_chat"])


def test_nang_luc_khong_con_noi_chua_phu_thue():
    """Trước bản này `NANG_LUC` nói "chưa phủ: thuế, ..." — nay kho đã có luật
    gốc cho các lĩnh vực đó nên câu đó SAI. Canh rằng không còn cả hai chuỗi
    cùng lúc, tránh hồi quy về đúng câu bịa cũ (tuyên bố phạm vi đã ĐỒNG BỘ,
    không phải chỉ hứa là đã đồng bộ)."""
    ans = _tra_loi(DANG["nang_luc"])
    assert not ("chưa phủ" in ans and "thuế" in ans)


def test_soan_thao_neu_dung_so_loai_van_ban_dem_luc_chay():
    """Trước bản này lời tự giới thiệu ghi cứng "ba loại" trong khi
    `config/checklist_*.yaml` đã có 27 file. Đếm THẬT lúc chạy TEST (không
    chép số 27 vào đây) nên phép canh này tự đỏ ngay khi ai thêm một checklist
    mà quên sửa lời giới thiệu.

    ĐỔI HỢP ĐỒNG (ex.md §4.2): con số này nay thuộc khía cạnh `soan_thao`, chỉ
    nói khi người ta hỏi soạn thảo — "Không nêu số lượng loại văn bản soạn thảo
    nếu người dùng không hỏi soạn thảo chi tiết"."""
    so_file = len(list(Path("config").glob("checklist_*.yaml")))
    assert str(so_file) in _tra_loi("bạn soạn được văn bản gì")
    assert not any(c.isdigit() for c in _tra_loi(DANG["nang_luc"])), (
        "bài năng lực không mang con số nào — số liệu kho và số loại văn bản "
        "soạn thảo đều là khía cạnh riêng"
    )


class _DemLuot:
    def __init__(self):
        self.luot = 0

    def chat(self, model, messages, json_schema=None):
        self.luot += 1
        return '{"tra_loi": "Tôi là KLAW."}', Usage(30, 10, 0.0001)


@pytest.mark.parametrize("cau_hoi", list(DANG.values()), ids=list(DANG))
def test_moi_dang_dung_MOT_luot_model_va_tien_vao_trace(cau_hoi):
    """Quyết định 2026-09-30, Consequences: câu hỏi về KLAW tốn đúng MỘT lượt
    model — không truy hồi, không sinh luận điểm — và lượt đó phải đếm được."""
    llm = _DemLuot()
    st = assemble({"query": cau_hoi, "intent": "gioi_thieu"}, {}, llm, "m")
    assert st["result_type"] == ResultType.gioi_thieu
    assert llm.luot == 1
    assert st["traces"]["assemble_token_in"] == 30 and st["traces"]["assemble_token_out"] == 10


def test_Q1_moi_chuoi_hien_thi_xung_toi_khong_xung_minh():
    """Quyết định Q1 (spec 2026-09-06 §2): một giọng duy nhất.

    Quét MỌI chuỗi ký tự trong mã của bốn module có lời đáp cho người đọc (kể
    cả f-string trong thân hàm như `_ly_do_moi_nguon_bi_thay`), bỏ docstring và
    chú thích — một hằng số chữ hoa không phải nơi duy nhất câu chữ sống.
    `services/kho.py` nằm trong danh sách vì `CAU_GIOI_HAN` của nó được
    `gioi_thieu.NGUON` nhúng thẳng vào câu trả lời cho người dùng.
    """
    import ast
    import re
    from pathlib import Path

    minh = re.compile(r"\b[Mm]ình\b")
    src = Path(__file__).resolve().parents[2] / "src"

    def chuoi_trong_ma(duong: Path) -> list[str]:
        cay = ast.parse(duong.read_text(encoding="utf-8"))
        docstring: set[int] = set()
        for n in ast.walk(cay):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
                    docstring.add(id(n.body[0].value))
        return [n.value for n in ast.walk(cay)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstring]

    for duong_tuong_doi in ("agents/nodes/gioi_thieu.py", "agents/nodes/hoi_lai.py",
                            "agents/nodes/assemble.py", "services/kho.py"):
        for s in chuoi_trong_ma(src / duong_tuong_doi):
            assert not minh.search(s), f"{duong_tuong_doi} còn xưng 'mình': {s[:80]!r}"

    for cau in ("chào bạn", "cảm ơn", "bạn là ai", "bạn là gì", "bạn làm được những gì",
                "bạn dùng model gì", "nguồn dữ liệu của bạn là gì"):
        assert not minh.search(cau_gioi_thieu(cau)), f"{cau!r} còn xưng 'mình'"
