"""Bất biến: MỌI truy vấn đọc `documents`/`provisions`/`chunks`/`"references"`
trong `src/` hoặc lọc bằng tập văn bản được hiện, hoặc được miễn có lý do.

Thẩm quyền: `docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md`
mục 8 — "một văn bản chỉ được hiện cho người dùng (kho, tìm kiếm, bộ lọc, trang
văn bản, trích dẫn) khi đồng thời còn hiệu lực …, đã xác định được tình trạng …
và có link chính thống đã kiểm", văn bản ẩn "giữ trong DB" để chỉ ra văn bản
thay thế và kiểm trích dẫn cũ.

Phạm vi: mọi chuỗi SQL (hằng số, chuỗi ghép `+`, f-string) trong `src/`, quét
bằng AST — không chạy truy vấn nào, 0 DB. Hợp lệ: chuỗi mang `:hien` (tham số
tập được hiện, `services/hien_thi.tap_hien_thi`). Ngoại lệ: `DUOC_MIEN`, mỗi
dòng một lý do; loại `sau_chan` còn bị kiểm thêm là MỌI hàm dùng nó phải gọi
cổng tương ứng (`chan_neu_an` cho trang một văn bản).

Bất biến thứ hai (`docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md` mục 9):
điều khoản bị bãi bỏ không bao giờ được truy hồi, trích dẫn, tìm thấy hay hiện nội
dung trên trang văn bản. MỌI truy vấn đọc `provisions`/`chunks` phải mang `:bai_bo`
(`services/hien_thi.dieu_khoan_an`) hoặc đi qua `bai_bo_tren_trang` (`CONG_BAI_BO`, trang
một văn bản trả `noi_dung`); ngoại lệ ở `MIEN_BAI_BO`, mỗi dòng một lý do — miễn `:hien`
(`DUOC_MIEN`) không kéo theo miễn `:bai_bo` (review 2026-09-30: cây kiểm chứng tier 1).
"""

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
THAM_QUYEN = "docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md mục 8"

# `anh_van_ban`: ảnh trang 1 bản đã ký (migration 040) là nội dung của MỘT văn bản.
_RE_DOC = re.compile(r'\b(?:FROM|JOIN)\s+(?:documents|provisions|chunks|"references"|anh_van_ban)\b')

# Lý do miễn — một chỗ để đọc cả danh sách ngoại lệ.
DO_THI = "đồ thị hiệu lực: văn bản ẩn PHẢI còn ở đây để chỉ ra văn bản thay thế (mục 8)"
KIEM_CHUNG = "kiểm chứng đầu ra mô hình; trích dẫn hiện ra chỉ đến từ tập căn cứ đã lọc"
TIEN_DE = "phép kiểm tiền đề 'Điều N của Bộ luật X có tồn tại' — kiểm trích dẫn cũ, không hiện nội dung"
TRUNG_GIAN = "chỉ ra id trung gian; tập cuối đã lọc ở truy vấn mang :hien của cùng đường"
TAP_HIEN = "chính phép tính tập được hiện / câu trả lời cho văn bản ẩn được nêu tên"
DAU_CACHE = "dấu vân tay corpus cho khoá cache, không trả dòng nào"
NAP = "nạp dữ liệu / kiểm toàn vẹn lúc khởi động, không phải đường đọc của người dùng"
SOAN_THAO = "tập điều khoản của checklist (lru_cache); mọi bề mặt người đọc lọc qua `chi_van_ban_hien`"

# (file tương đối `src/`, tên hằng số hoặc hàm) → (lý do, hàm cổng bắt buộc | None)
DUOC_MIEN: dict[tuple[str, str], tuple[str, str | None]] = {
    **{
        ("services/effectivity.py", n): (DO_THI, None)
        for n in (
            "_SQL_DOC",
            "_SQL_CANH",
            "_SQL_UNG_VIEN",
            "_SQL_SUA_DOI",
            "_SQL_SUA_DOI_VAN_BAN",
            "_SQL_DOC_TAT_CA",
            "_SQL_CANH_TAT_CA",
            "_SQL_BAI_BO",
        )
    },
    ("agents/nodes/verify_tier1.py", "_SQL_CAY"): (KIEM_CHUNG, None),
    ("agents/graph_tra_cuu.py", "_db_provisions"): (KIEM_CHUNG, None),
    ("agents/nodes/verify_tier1.py", "tien_de_cau_hoi_sai"): (TIEN_DE, None),
    **{
        ("agents/nodes/expand.py", n): (TRUNG_GIAN, None)
        for n in ("_SQL_PARENT", "_SQL_CHILDREN", "_SQL_NEO_SUA", "_SQL_THEO_DUONG_DAN")
    },
    ("services/retrieval.py", "provision_ids"): (TRUNG_GIAN, None),
    ("services/retrieval.py", "linh_vuc_cua"): (TRUNG_GIAN, None),
    **{
        ("services/hien_thi.py", n): (TAP_HIEN, None)
        for n in ("_SQL_UNG_VIEN", "_SQL_VAN_BAN_NEU", "_SQL_DOC", "_SQL_THEO_SO", "_SQL_VAN_BAN_BAI_BO")
    },
    ("services/kho.py", "_SQL_KHO"): ("mỗi dòng mang cờ `hien`; mọi con số và danh sách lọc bằng nó", "gan_hien_thi"),
    ("agents/graph_soan_thao.py", "_SQL_PROVISIONS_BY_DUONG_DAN"): (SOAN_THAO, None),
    ("agents/graph_soan_thao.py", "_SQL_DOCUMENTS_BY_ID"): (SOAN_THAO, None),
    ("agents/graph_soan_thao.py", "_SQL_VAN_BAN_CAN_CU"): ("khối Căn cứ", "chi_van_ban_hien"),
    ("services/cache_tra_loi.py", "_SQL_CHECKSUM"): (DAU_CACHE, None),
    ("services/checklist.py", "kiem_tra_can_cu_ton_tai"): (NAP, None),
    ("services/rules.py", "kiem_tra_can_cu_ton_tai"): (NAP, None),
    ("services/chunker.py", "load_provisions"): (NAP, None),
    ("services/xref.py", "resolve_all"): (NAP, None),
    # Trang MỘT văn bản: đọc theo `doc_id` SAU cổng 404 `khong_hien_thi`.
    **{
        ("api/routes.py", n): ("trang một văn bản", "chan_neu_an")
        for n in (
            "_SQL_VAN_BAN_DOC",
            "_SQL_VAN_BAN_MUC_LUC",
            "_SQL_VAN_BAN_DIEU_PHANG",
            "_SQL_VAN_BAN_DIEU_BY_SO_HIEU",
            "_SQL_VAN_BAN_PROVISION_GOC",
            "_SQL_VAN_BAN_DIEU_CHA",
            "_SQL_VAN_BAN_DIEU_TRUOC",
            "_SQL_VAN_BAN_DIEU_SAU",
            "_SQL_VAN_BAN_CAY_DIEU",
            "_SQL_DIEU_TRONG_CHUONG",
        )
    },
    **{
        ("api/routes_van_ban.py", n): ("trang một văn bản", "chan_neu_an")
        for n in ("_SQL_DOC", "_SQL_LIEN_QUAN", "_SQL_NOI_BO", "_SQL_ANH_XEM_TRUOC")
    },
    **{
        ("api/routes_tim_kiem.py", n): ("trang một văn bản", "chan_neu_an")
        for n in ("_SQL_TIM_TRONG_VB", "_SQL_TIM_TRONG_VB_DEM", "_SQL_TIM_TRONG_VB_TRANG", "_SQL_DOC_TOI_THIEU")
    },
}


THAM_QUYEN_BAI_BO = "docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md mục 9"
_RE_DIEU_KHOAN = re.compile(r"\b(?:FROM|JOIN)\s+(?:provisions|chunks)\b")

# Đọc điều khoản mà không cần `:bai_bo` — (file, chủ) → lý do.
TRUNG_GIAN_BAI_BO = "chỉ ra id trung gian; tập cuối lọc ở truy vấn mang :bai_bo của cùng đường"
DIEU_HUONG = "trang một văn bản: số hiệu, tiêu đề, điều hướng — điều khoản bị bãi bỏ vẫn còn số hiệu và tiêu đề"
MIEN_BAI_BO: dict[tuple[str, str], str] = {
    ("api/routes.py", "_SQL_PHAM_VI"): "đếm điều khoản theo văn bản cho trang phạm vi; không trả nội dung",
    ("api/routes_tim_kiem.py", "_SQL_BO_LOC"): "chỉ hỏi văn bản có toàn văn hay không",
    **{
        ("agents/nodes/expand.py", n): TRUNG_GIAN_BAI_BO + " (`_SQL_PROV`)"
        for n in ("_SQL_PARENT", "_SQL_CHILDREN", "_SQL_NEO_SUA", "_SQL_THEO_DUONG_DAN")
    },
    ("services/retrieval.py", "provision_ids"): TRUNG_GIAN_BAI_BO + " (chunk đã lọc ở `_CHI_HIEN`)",
    ("services/retrieval.py", "linh_vuc_cua"): TRUNG_GIAN_BAI_BO + " (chỉ đọc nhãn ngành)",
    ("agents/nodes/verify_tier1.py", "tien_de_cau_hoi_sai"): TIEN_DE,
    **{
        ("services/effectivity.py", n): "đồ thị hiệu lực: chính phép đọc sửa đổi/bãi bỏ"
        for n in ("_SQL_SUA_DOI", "_SQL_SUA_DOI_VAN_BAN", "_SQL_BAI_BO")
    },
    ("services/cache_tra_loi.py", "_SQL_CHECKSUM"): DAU_CACHE + "; tập bãi bỏ đã vào dấu (`corpus_checksum`)",
    ("services/checklist.py", "kiem_tra_can_cu_ton_tai"): NAP,
    ("services/rules.py", "kiem_tra_can_cu_ton_tai"): NAP,
    ("services/xref.py", "resolve_all"): NAP,
    # Đọc cả điều khoản bị bãi bỏ: `build_chunks(…, an)` bỏ chữ của chúng khỏi chunk neo còn hiệu
    # lực, giữ nguyên chunk neo ở chính chúng (truy hồi lọc bằng `:bai_bo`) — quyết định 2026-09-30
    # mục 9(e); chunk đã nhúng đổi theo bằng `scripts.nhung_lai_bai_bo --ghi`.
    ("services/chunker.py", "load_provisions"): NAP,
    # ponytail: tập checklist cấu hình tay; 0 điều khoản checklist bị bãi bỏ (đo 2026-09-30, seed
    # 296 điều khoản). Lọc trong `chi_van_ban_hien` khi một căn cứ checklist bị bãi bỏ.
    ("agents/graph_soan_thao.py", "_SQL_PROVISIONS_BY_DUONG_DAN"): SOAN_THAO,
    ("api/routes_van_ban.py", "_SQL_NOI_BO"): "đếm cạnh nội bộ của trang một văn bản; không trả nội dung",
    **{
        ("api/routes.py", n): DIEU_HUONG
        for n in (
            "_SQL_VAN_BAN_DOC",
            "_SQL_VAN_BAN_MUC_LUC",
            "_SQL_VAN_BAN_DIEU_PHANG",
            "_SQL_VAN_BAN_DIEU_BY_SO_HIEU",
            "_SQL_VAN_BAN_PROVISION_GOC",
            "_SQL_VAN_BAN_DIEU_CHA",
            "_SQL_VAN_BAN_DIEU_TRUOC",
            "_SQL_VAN_BAN_DIEU_SAU",
        )
    },
}
# Trang một văn bản: thân trang đi qua cổng này thay cho `:bai_bo` trong SQL.
CONG_BAI_BO: dict[tuple[str, str], str] = {
    ("api/routes.py", n): "bai_bo_tren_trang" for n in ("_SQL_VAN_BAN_CAY_DIEU", "_SQL_DIEU_TRONG_CHUONG")
}


def _chuoi(node: ast.AST, ten: dict[str, str]) -> str | None:
    """Giá trị tĩnh của một biểu thức chuỗi; phần không suy được coi là rỗng."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    if isinstance(node, ast.Name):
        return ten.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _chuoi(node.left, ten), _chuoi(node.right, ten)
        return None if a is None and b is None else (a or "") + (b or "")
    return None


def quet(goc: Path) -> list[tuple[str, int, str, str]]:
    """`(file, dòng, tên chủ, sql)` cho mọi chuỗi SQL đọc bảng được canh."""
    ra = []
    for f in sorted(goc.rglob("*.py")):
        cay = ast.parse(f.read_text(encoding="utf-8"))
        docstring = {
            id(n.body[0].value)
            for n in ast.walk(cay)
            if isinstance(n, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and n.body
            and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)
        }
        ten: dict[str, str] = {}
        for n in cay.body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                v = n.value.args[0] if isinstance(n.value, ast.Call) and n.value.args else n.value
                if (s := _chuoi(v, ten)) is not None:
                    ten[n.targets[0].id] = s
        cha = {id(c): n for n in ast.walk(cay) for c in ast.iter_child_nodes(n)}

        def chu(n: ast.AST) -> str:
            p = cha.get(id(n))
            while p is not None:
                if isinstance(p, ast.FunctionDef | ast.AsyncFunctionDef):
                    return p.name
                if isinstance(p, ast.Assign) and isinstance(cha.get(id(p)), ast.Module):
                    return p.targets[0].id if isinstance(p.targets[0], ast.Name) else "?"
                p = cha.get(id(p))
            return "<module>"

        for n in ast.walk(cay):
            if not isinstance(n, ast.Constant | ast.BinOp | ast.JoinedStr) or id(n) in docstring:
                continue
            if isinstance(cha.get(id(n)), ast.BinOp | ast.JoinedStr):
                continue  # chỉ xét biểu thức chuỗi LỚN NHẤT
            if (s := _chuoi(n, ten)) and _RE_DOC.search(s):
                ra.append((str(f.relative_to(goc)), n.lineno, chu(n), s))
    return ra


def _ham_dung(cay: ast.Module, ten: str) -> list[ast.FunctionDef]:
    return [
        f
        for f in ast.walk(cay)
        if isinstance(f, ast.FunctionDef | ast.AsyncFunctionDef)
        and any(isinstance(x, ast.Name) and x.id == ten for x in ast.walk(f))
    ]


def _goi(f: ast.AST, ten: str) -> bool:
    return any(
        isinstance(x, ast.Call) and (getattr(x.func, "id", None) == ten or getattr(x.func, "attr", None) == ten)
        for x in ast.walk(f)
    )


def vi_pham(goc: Path, mien: dict) -> list[str]:
    loi = []
    thay = set()
    for file, dong, chu, sql in quet(goc):
        if ":hien" in sql:
            continue
        khoa = (file, chu)
        if khoa not in mien:
            loi.append(
                f"src/{file}:{dong} `{chu}` đọc documents/provisions/chunks mà không lọc tập văn bản được hiện "
                f"(`:hien`) — {THAM_QUYEN}. Lọc bằng `d.id = ANY(CAST(:hien AS text[]))` với "
                "`services/hien_thi.tap_hien_thi`, hoặc thêm vào DUOC_MIEN kèm lý do nếu đây không phải "
                "đường đọc của người dùng."
            )
            continue
        thay.add(khoa)
    for (file, chu), (_ly_do, cong) in mien.items():
        if (file, chu) not in thay and (goc / file).exists():
            loi.append(f"DUOC_MIEN có `{file}:{chu}` nhưng không còn truy vấn nào ở đó — gỡ dòng miễn cũ.")
        if cong and (goc / file).exists():
            cay = ast.parse((goc / file).read_text(encoding="utf-8"))
            for f in _ham_dung(cay, chu):
                if not _goi(f, cong):
                    loi.append(
                        f"src/{file}: hàm `{f.name}` dùng `{chu}` mà không gọi `{cong}` — {THAM_QUYEN}: văn bản ẩn "
                        f"phải bị chặn trước khi đọc. Gọi `{cong}` trước truy vấn."
                    )
    return loi


def vi_pham_bai_bo(goc: Path, mien: dict, cong: dict, duoc_mien: dict) -> list[str]:
    loi, thay = [], set()
    for file, dong, chu, sql in quet(goc):
        khoa = (file, chu)
        if not _RE_DIEU_KHOAN.search(sql) or ":bai_bo" in sql:
            continue
        trang = (duoc_mien.get(khoa) or (None, None))[1] == "chan_neu_an" and re.search(r"\bnoi_dung\b", sql)
        if khoa in mien:
            thay.add(khoa)
        elif khoa in cong and trang:
            thay.add(khoa)
            cay = ast.parse((goc / file).read_text(encoding="utf-8"))
            loi += [
                f"src/{file}: hàm `{f.name}` dùng `{chu}` mà không gọi `{cong[khoa]}` — {THAM_QUYEN_BAI_BO}: điều "
                f"khoản bị bãi bỏ không được hiện nội dung. Đưa các dòng qua `{cong[khoa]}` trước khi trả."
                for f in _ham_dung(cay, chu)
                if not _goi(f, cong[khoa])
            ]
        else:
            loi.append(
                f"src/{file}:{dong} `{chu}` đọc provisions/chunks mà không loại điều khoản bị bãi bỏ (`:bai_bo`) — "
                f"{THAM_QUYEN_BAI_BO}. Thêm `AND NOT (p.id = ANY(CAST(:bai_bo AS bigint[])))` với "
                "`services/hien_thi.dieu_khoan_an`, hoặc thêm vào MIEN_BAI_BO kèm lý do (miễn `:hien` không đủ)."
            )
    loi += [
        f"MIEN_BAI_BO/CONG_BAI_BO có `{f}:{c}` nhưng không còn truy vấn đó — gỡ dòng cũ."
        for f, c in {*mien, *cong} - thay
    ]
    return loi


def test_moi_duong_doc_van_ban_deu_loc_tap_duoc_hien_hoac_duoc_mien_co_ly_do():
    assert vi_pham(SRC, DUOC_MIEN) == []


def test_moi_duong_doc_dieu_khoan_deu_loai_dieu_khoan_bi_bai_bo():
    assert vi_pham_bai_bo(SRC, MIEN_BAI_BO, CONG_BAI_BO, DUOC_MIEN) == []


def test_duong_tra_loi_truyen_tap_duoc_hien_vao_truy_hoi_va_mo_rong():
    """`Retriever.hybrid`/`expand` nhận `hien=None` để đo truy hồi thô (eval); đường
    trả lời thì PHẢI truyền tập được hiện — thiếu nó là văn bản ẩn thành căn cứ."""
    cay = ast.parse((SRC / "agents/graph_tra_cuu.py").read_text(encoding="utf-8"))
    goi = [x for x in ast.walk(cay) if isinstance(x, ast.Call)]
    hybrid = [x for x in goi if getattr(x.func, "attr", None) == "hybrid"]
    expand = [x for x in goi if getattr(x.func, "id", None) == "expand"]
    assert hybrid and all(len(x.args) + len(x.keywords) >= 3 for x in hybrid), "retriever.hybrid(q, hien, bai_bo)"
    assert expand and all(len(x.args) + len(x.keywords) >= 6 for x in expand), "expand(..., hien, bai_bo)"
    # Cây kiểm chứng của tier 1/tier 2/assemble: khoản bị bãi bỏ không được làm chỗ khớp quote.
    db = [x for x in goi if getattr(x.func, "id", None) == "_db_provisions"]
    assert db and all(len(x.args) + len(x.keywords) == 3 for x in db), "_db_provisions(ids, engine, as_of)"


# ─────────────────────────────────── chứng minh hai chiều (encoding-invariants §4)


def test_CHUNG_MINH_AM_bat_duoc_truy_van_moi_khong_loc(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "moi.py").write_text(
        'from sqlalchemy import text\n_SQL_MOI = text("SELECT id, ten FROM documents WHERE loai_van_ban = :l")\n',
        encoding="utf-8",
    )
    (loi,) = vi_pham(tmp_path, {})
    assert "src/api/moi.py:2 `_SQL_MOI`" in loi and "mục 8" in loi and ":hien" in loi, loi


def test_CHUNG_MINH_AM_bat_duoc_anh_van_ban_doc_khong_qua_cong(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "anh.py").write_text(
        'from sqlalchemy import text\n_SQL_ANH = text("SELECT png FROM anh_van_ban WHERE doc_id = :i")\n',
        encoding="utf-8",
    )
    (loi,) = vi_pham(tmp_path, {})
    assert "src/api/anh.py:2 `_SQL_ANH`" in loi, loi


def test_CHUNG_MINH_AM_bat_duoc_trang_van_ban_bo_qua_cong(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "trang.py").write_text(
        "from sqlalchemy import text\n"
        '_SQL_DOC = text("SELECT ten FROM documents WHERE id = :i")\n'
        "def xem(engine, i):\n"
        "    with engine.connect() as c:\n"
        "        return c.execute(_SQL_DOC, {'i': i}).one()\n",
        encoding="utf-8",
    )
    (loi,) = vi_pham(tmp_path, {("api/trang.py", "_SQL_DOC"): ("trang một văn bản", "chan_neu_an")})
    assert "hàm `xem` dùng `_SQL_DOC` mà không gọi `chan_neu_an`" in loi, loi


@pytest.mark.parametrize(
    "sql",
    [
        '"SELECT d.id FROM documents d WHERE d.id = ANY(CAST(:hien AS text[]))"',
        '"SELECT count(*) FROM documents" + _LOC',
    ],
)
def test_CHUNG_MINH_DUONG_truy_van_loc_bang_hien_thi_qua(tmp_path, sql):
    (tmp_path / "m.py").write_text(
        f'from sqlalchemy import text\n_LOC = " WHERE id = ANY(CAST(:hien AS text[]))"\n_SQL = text({sql})\n',
        encoding="utf-8",
    )
    assert vi_pham(tmp_path, {}) == []


def test_CHUNG_MINH_AM_bat_duoc_truy_hoi_khong_loai_dieu_khoan_bai_bo(tmp_path):
    (tmp_path / "m.py").write_text(
        "from sqlalchemy import text\n"
        '_SQL = text("SELECT c.id FROM chunks c WHERE c.provision_id IN'
        ' (SELECT p.id FROM provisions p WHERE p.document_id = ANY(CAST(:hien AS text[]))))")\n',
        encoding="utf-8",
    )
    (loi,) = vi_pham_bai_bo(tmp_path, {}, {}, {})
    assert "src/m.py:2 `_SQL`" in loi and ":bai_bo" in loi and "mục 9" in loi, loi


def test_CHUNG_MINH_AM_bat_duoc_duong_mien_hien_doc_dieu_khoan_khong_ly_do_bai_bo(tmp_path):
    """Review 2026-09-30: `_SQL_CAY` của tier 1 được miễn `:hien` (KIEM_CHUNG) nên từng lọt cả
    bất biến thứ hai, và khoản bị bãi bỏ làm chỗ khớp quote. Miễn `:hien` KHÔNG kéo theo miễn
    `:bai_bo`: mỗi đường đọc điều khoản phải có lý do riêng trong MIEN_BAI_BO."""
    (tmp_path / "m.py").write_text(
        "from sqlalchemy import text\n"
        '_SQL_CAY = text("SELECT id, noi_dung FROM provisions WHERE parent_id = ANY(:ids)")\n',
        encoding="utf-8",
    )
    duoc_mien = {("m.py", "_SQL_CAY"): (KIEM_CHUNG, None)}
    (loi,) = vi_pham_bai_bo(tmp_path, {}, {}, duoc_mien)
    assert "src/m.py:2 `_SQL_CAY`" in loi and "MIEN_BAI_BO" in loi, loi
    assert vi_pham_bai_bo(tmp_path, {("m.py", "_SQL_CAY"): "lý do"}, {}, duoc_mien) == []


def test_CHUNG_MINH_AM_bat_duoc_trang_van_ban_bo_qua_cong_bai_bo(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "trang.py").write_text(
        "from sqlalchemy import text\n"
        '_SQL_CAY = text("SELECT id, noi_dung FROM provisions WHERE parent_id = :i")\n'
        "def xem(conn, i):\n"
        "    return conn.execute(_SQL_CAY, {'i': i}).all()\n",
        encoding="utf-8",
    )
    trang = {("api/trang.py", "_SQL_CAY"): ("trang một văn bản", "chan_neu_an")}
    (loi,) = vi_pham_bai_bo(tmp_path, {}, {}, trang)
    assert "`_SQL_CAY`" in loi and ":bai_bo" in loi, loi
    (loi,) = vi_pham_bai_bo(tmp_path, {}, {("api/trang.py", "_SQL_CAY"): "bai_bo_tren_trang"}, trang)
    assert "hàm `xem` dùng `_SQL_CAY` mà không gọi `bai_bo_tren_trang`" in loi, loi


def test_CHUNG_MINH_DUONG_truy_van_mang_bai_bo_hoac_qua_cong(tmp_path):
    (tmp_path / "m.py").write_text(
        "from sqlalchemy import text\n"
        '_SQL = text("SELECT p.id FROM provisions p WHERE p.document_id = ANY(CAST(:hien AS text[]))'
        ' AND NOT (p.id = ANY(CAST(:bai_bo AS bigint[])))")\n'
        '_SQL_CAY = text("SELECT id, noi_dung FROM provisions WHERE parent_id = :i")\n'
        "def xem(conn, i, b):\n"
        "    return bai_bo_tren_trang(conn, conn.execute(_SQL_CAY, {'i': i}).all(), b, frozenset())\n",
        encoding="utf-8",
    )
    trang = {("m.py", "_SQL_CAY"): ("trang một văn bản", "chan_neu_an")}
    assert vi_pham_bai_bo(tmp_path, {}, {("m.py", "_SQL_CAY"): "bai_bo_tren_trang"}, trang) == []
