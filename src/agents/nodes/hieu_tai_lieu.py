"""Node `hieu_tai_lieu` — đọc tài liệu người hỏi đã gửi trong hội thoại này
(plan `tai-lieu-tong-quat.md` §Graph S2, CONTEXT.md "User documents").

Cùng hình dạng với `rut_du_kien` và vì cùng một lý do: MỘT lượt gọi mô hình,
rồi mọi thứ sau đó là phép tất định 0 token. Biên của phần "mô hình có thể sai"
nằm gọn trong một file, và cái ra khỏi file này đã được tra ngược về chính chữ
trong tài liệu.

Ba ràng buộc định hình node:

**Quan sát phải neo được, suy luận thì không.** `quan_sat` là điều TÀI LIỆU
nói, nên nó phải chỉ ra được đúng đơn vị chứa câu đó (`neo_du_kien.xac_minh`,
tra chuỗi thuần) — không neo được thì bị loại, y hệt một dữ kiện không trích
dẫn được. `suy_luan` là cách ĐỌC của mô hình; nó không được neo vì nó không
phải một câu của tài liệu, và chính vì thế nó đi ra một danh sách RIÊNG mà giao
diện gắn nhãn "suy luận của mô hình".

**Nhãn tài liệu, không phải id.** Mô hình chỉ tài liệu bằng một chữ cái (`A`,
`B`). Cho nó thấy UUID là mời nó bịa ra một UUID khác; một enum một ký tự thì
`json_schema` chặn được tại chỗ. Đoạn trích gán nhãn A được tra NGƯỢC trong
đơn vị của A mà thôi — gán sai nhãn là không neo được, không phải neo nhầm.

**Traces đếm, không chép.** Không khoá nào của `traces` mang chữ của tài liệu:
sổ traces đi vào bảng dùng chung cho chương đánh giá và cho hạn mức, còn tài
liệu chỉ được sống trong đúng hội thoại của nó (decision 2026-09-16).
"""

import json
import logging
import re
import unicodedata
from pathlib import Path

from src.agents.nodes.verify_tier1 import QUOTE_TOI_THIEU
from src.services.doc_tai_lieu import DonViVanBan, NguonChu
from src.services.neo_du_kien import LyDoNeo, Neo, normalize, xac_minh
from src.services.phep_tinh import so_bang_nhau, tinh, viet_so
from src.services.prompts import messages
from src.services.tai_lieu import VuotTran, kiem_tran_chi_phi_tai_lieu

logger = logging.getLogger(__name__)
PROMPT_PATH = Path("prompts/hieu_tai_lieu.v1.md")

# Một chữ cái cho mỗi tài liệu trong lượt. Dài hơn số tài liệu tối đa một lượt
# được mang (2, quyết định chủ sở hữu Q3) để trần nằm ở chỗ nó thuộc về —
# `TraCuuRequest.tai_lieu_ids` — chứ không ở đây.
NHAN = "ABCDEFGH"

# Tám mục đích của CONTEXT.md ("mục đích"). Lát cắt S2 chỉ XỬ LÝ ba cái đầu;
# năm cái còn lại vẫn được mô hình chọn và được GHI LẠI (`muc_dich_tai_lieu`)
# để S4–S6 rẽ nhánh — không cho chọn thì không bao giờ đo được người dùng hỏi
# gì, và cả ba lát cắt sau phải đoán mò.
MUC_DICH = ("tom_tat", "hoi", "phan_tich", "trich_du_kien", "so_sanh",
            "doi_chieu_luat", "tao_van_ban", "sua_ban_thao")
MUC_DICH_LAM_DUOC = frozenset({"tom_tat", "hoi", "phan_tich", "trich_du_kien", "so_sanh"})

# Trần hình dạng, cưỡng chế 0 token (cùng lý lẽ `assemble.TRAN_GACH`): gọi lại
# mô hình để nó tự rút gọn là thêm một lượt gọi vào đường thành công thường.
TOI_DA_QUAN_SAT = 12
TOI_DA_SUY_LUAN = 5
# Quyết định chủ sở hữu 2026-09-16: ≤20 trường động một lượt. Trần này là của
# NGƯỜI ĐỌC, không phải của mô hình — 20 dòng dữ kiện là thứ còn soát tay được.
TOI_DA_TRUONG = 20

# Thiếu tài liệu thứ hai thì không so được. Nói thẳng bằng `can_du_kien` chứ
# không gọi lại mô hình: nó cũng chỉ có đúng một tài liệu như lần gọi đầu.
CAN_TAI_LIEU_THU_HAI = "tài liệu thứ hai"

# Trên ngưỡng này thì không gửi cả tài liệu nữa. 10 trang là mức mọi hợp đồng,
# quyết định, phiếu đánh giá thật đều nằm dưới (đo trên tệp mẫu: 1 trang).
NGUONG_TRANG = 10
GIU_DAU = 12
GIU_THEO_CAU_HOI = 40

QUA_DAI = ("Tài liệu quá dài để đọc trong một lượt. Hãy tách nhỏ rồi gửi lại, "
           "hoặc hỏi về một phần cụ thể.")
CHUA_DOC_DUOC = "Chưa đọc được tài liệu lúc này. Hãy thử lại."


def _mang(*truong: str) -> dict:
    """Mảng object strict với đúng bộ trường chuỗi đã gọi tên (mọi trường đều
    `required` — `json_schema` strict không có khái niệm trường tuỳ chọn)."""
    return {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": list(truong),
            "properties": {t: {"type": "string"} for t in truong},
        },
    }


def schema_hieu(nhan: list[str]) -> dict:
    """Lược đồ strict cho một lượt đọc. `tai_lieu` là enum NHÃN dựng lúc gọi —
    mô hình không có đường nào chỉ tới một tài liệu không nằm trong lượt này."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["muc_dich", "mo_ta", "tra_loi_ngan", "quan_sat", "suy_luan", "can_du_kien",
                     "phep_tinh", "truong", "khac_biet"],
        "properties": {
            "muc_dich": {"type": "string", "enum": list(MUC_DICH)},
            "mo_ta": {"type": "string"},
            "tra_loi_ngan": {"type": "string"},
            "quan_sat": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["noi_dung", "trich", "tai_lieu"],
                    "properties": {
                        "noi_dung": {"type": "string"},
                        "trich": {"type": "string"},
                        "tai_lieu": {"type": "string", "enum": nhan},
                    },
                },
            },
            "suy_luan": {"type": "array", "items": {"type": "string"}},
            "can_du_kien": {"type": "array", "items": {"type": "string"}},
            # `bieu_thuc` chỉ được chứa số CHÉP TỪ tài liệu; `ket_qua_tai_lieu`
            # là con số tài liệu tự ghi. Kết quả của phép tính KHÔNG có trong
            # lược đồ: nó do `phep_tinh.tinh` sinh ra sau lượt gọi (FR-013).
            "phep_tinh": _mang("bieu_thuc", "ket_qua_tai_lieu", "trich"),
            # Bộ trường ĐỘNG: không có `rules.yaml` nào ở đây, `khoa` do mô hình
            # đặt từ nhãn nó đọc được — đó là toàn bộ điểm của FR-005 (tài liệu
            # ngoài 29 loại có checklist vẫn rút được dữ kiện).
            "truong": _mang("khoa", "nhan", "gia_tri", "trich"),
            # Một khác biệt là HAI câu, mỗi câu của một tài liệu, nên nó mang
            # hai đoạn trích và phải neo được cả hai (FR-014).
            "khac_biet": _mang("noi_dung", "trich_a", "trich_b"),
        },
    }


def _tu_khoa(s: str) -> set[str]:
    """Tập từ đã chuẩn hoá (cùng `normalize` với phép neo — một quy tắc chuẩn
    hoá cho cả hệ, xem docstring `neo_du_kien`). Bỏ từ một ký tự: chúng khớp ở
    khắp nơi nên không xếp hạng được gì."""
    return {t for t in normalize(s or "").split() if len(t) > 1}


def loc_don_vi(don_vi: list[DonViVanBan], cau_hoi: str) -> list[DonViVanBan]:
    """Phần tài liệu được gửi cho mô hình. Hàm THUẦN: không LLM, không I/O.

    Dưới `NGUONG_TRANG` trang thì gửi cả tài liệu — cắt xén một tài liệu ngắn
    chỉ tạo ra rủi ro bỏ sót mà không tiết kiệm được gì đáng kể.

    Trên ngưỡng: giữ `GIU_DAU` đơn vị ĐẦU (tiêu đề, các bên, số hiệu — thứ gần
    như mọi câu hỏi đều cần) cộng `GIU_THEO_CAU_HOI` đơn vị trùng từ khoá với
    câu hỏi nhiều nhất. Thứ tự đọc được GIỮ NGUYÊN: đánh số theo thứ tự trong
    tài liệu là cách duy nhất `[A-12]` còn nghĩa với người đọc lại sau này.
    """
    if not don_vi:
        return []
    if max((d.trang for d in don_vi), default=1) <= NGUONG_TRANG:
        return list(don_vi)
    tu = _tu_khoa(cau_hoi)
    theo_diem = sorted(don_vi[GIU_DAU:], key=lambda d: (-len(tu & _tu_khoa(d.noi_dung)), d.chi_so))
    giu = {d.chi_so for d in don_vi[:GIU_DAU]} | {d.chi_so for d in theo_diem[:GIU_THEO_CAU_HOI]}
    return [d for d in don_vi if d.chi_so in giu]


def _vi_tri(d: DonViVanBan) -> str:
    """"(tr. 1, bảng 1 h2 c3, chân trang)" — vị trí đọc được của một đơn vị.

    `vung`/`bang` đọc bằng `getattr`: S1 đang thêm hai trường này vào
    `DonViVanBan`; node phải chạy đúng trên cả bản trước lẫn bản sau, vì hai lát
    cắt chạy song song.
    """
    phan = [f"tr. {d.trang}"]
    bang = getattr(d, "bang", None)
    if bang:
        # `bang` đếm từ 0 (S1); người đọc — và mô hình đang viết cho người đọc —
        # đếm từ 1, cùng quy ước giao diện (`nhanNeo`).
        phan.append(f"bảng {bang[0] + 1} hàng {bang[1] + 1} cột {bang[2] + 1}")
    vung = getattr(d, "vung", "than")
    if vung == "dau_trang":
        phan.append("đầu trang")
    elif vung == "chan_trang":
        phan.append("chân trang")
    return ", ".join(phan)


def _khop_manh(m: str, d: DonViVanBan) -> bool:
    """Một mảnh (một dòng của `trich`) có nằm trong đơn vị `d` không: bằng cả
    đơn vị, hoặc là đoạn đủ dài (`QUOTE_TOI_THIEU`) nằm trong nó."""
    nd = normalize(d.noi_dung)
    return m == nd or (len(m) >= QUOTE_TOI_THIEU and m in nd)


def _neo_day_lien_tiep(trich: str, don_vi: list[DonViVanBan]) -> Neo | None:
    """Neo một đoạn trích nhiều dòng là MỘT DÃY ĐƠN VỊ LIỀN KỀ — hàng bảng (các ô
    nối bằng xuống dòng) hay hai đoạn đứng cạnh nhau ("Giảng viên hướng dẫn" /
    "(Ký, ghi rõ họ tên)").

    `xac_minh` so với TỪNG đơn vị, nên một hàng bảng trích nguyên văn không khớp
    ô nào. Đo trên tệp mẫu 2026-09-16: 13/13 quan sát bị loại vì mô hình đọc
    bảng theo hàng — đúng cách người đọc bảng — và 3/3 bị loại trên tệp thứ hai
    vì nó chép hai dòng kề nhau.

    Vẫn là tra chuỗi thuần, nới đúng một điều: một dãy đơn vị liền kề, theo
    đúng thứ tự, khớp ở ĐÚNG MỘT chỗ trong tài liệu cũng là một vị trí. Mỗi
    mảnh phải bằng đơn vị thứ i của dãy hoặc là đoạn đủ dài nằm trong nó; khớp
    được ở hai chỗ là không định danh được, loại y như một trích quá ngắn. Neo
    rơi vào đơn vị đầu tiên đủ dài của dãy — ô mang tiêu chí chứ không phải ô
    số — hoặc đơn vị dài nhất khi cả dãy đều ngắn ("Tổng" / "10").
    """
    manh = [m for m in (normalize(x) for x in trich.split("\n")) if m]
    if len(manh) < 2 or len(manh) > len(don_vi):
        return None
    dau: list[int] = [
        i for i in range(len(don_vi) - len(manh) + 1)
        if all(_khop_manh(m, don_vi[i + k]) for k, m in enumerate(manh))
    ]
    if len(dau) != 1:
        return None
    day = don_vi[dau[0] : dau[0] + len(manh)]
    o = next((d for d in day if len(normalize(d.noi_dung)) >= QUOTE_TOI_THIEU), None) or max(
        day, key=lambda d: len(d.noi_dung)
    )
    return Neo(LyDoNeo.ok, chi_so_don_vi=o.chi_so, trang=o.trang, offset_dau=o.offset_dau,
               nguon_chu=o.nguon_chu, do_tin=o.do_tin)


# Tiền tố prompt đặt trước mỗi đơn vị: `[A-12] (tr. 1, bảng 1 hàng 2 cột 2) `.
# Đo trên fixture 2026-09-16: mô hình chép nguyên dòng vào `trich`, kể cả tiền
# tố. Tiền tố là của prompt, không phải của tài liệu, nên bỏ nó đi TRƯỚC khi
# tra — và chỉ bỏ tiền tố: số chỉ mục bên trong không được tin, phép neo vẫn
# tìm đơn vị bằng chính chữ còn lại.
_RE_TIEN_TO = re.compile(r"^\s*\[[A-Z]-\d+\]\s*(?:\([^)\n]*\))?\s*")


def bo_tien_to(trich: str) -> str:
    return "\n".join(_RE_TIEN_TO.sub("", d) for d in trich.split("\n")).strip()


def _neo_o_duy_nhat(manh: str, don_vi: list[DonViVanBan]) -> Neo | None:
    """Neo một mảnh NGẮN bằng phép DUY NHẤT thay cho phép độ dài.

    `QUOTE_TOI_THIEU` (12 ký tự) là quy tắc của trích dẫn ĐIỀU LUẬT: ở đó một
    mẩu ngắn nằm lọt trong hàng chục nghìn dòng nên nó không định danh được gì.
    Một ô bảng thì ngược lại — nó là cả một đơn vị, và "2,0" hay "10" là toàn bộ
    nội dung của ô. Phép đo đúng cho nó là thứ ta thật sự cần: mảnh này có chỉ
    tới ĐÚNG MỘT chỗ không. Đo trên tệp mẫu 2026-09-16: mọi trường điểm bị loại
    oan vì luật độ dài, trong khi "10" chỉ có ở đúng một ô.

    Phải khớp TRỌN đơn vị, không phải nằm trong nó: "Ý thức" nằm trong một ô dài
    vẫn là một mẩu không định danh được, và nới chỗ đó là mở lại đúng lỗ mà
    `QUOTE_TOI_THIEU` đang bịt.
    """
    m = normalize(manh)
    if not m:
        return None
    khop = [d for d in don_vi if normalize(d.noi_dung) == m]
    if len(khop) != 1:
        return None
    d = khop[0]
    return Neo(LyDoNeo.ok, chi_so_don_vi=d.chi_so, trang=d.trang, offset_dau=d.offset_dau,
               nguon_chu=d.nguon_chu, do_tin=d.do_tin)


def _neo_manh_roi_rac(trich: str, don_vi: list[DonViVanBan]) -> Neo | None:
    """Neo một trích nhiều mảnh KHÔNG liền kề — cộng một cột điểm chẳng hạn, nơi
    mô hình chép các ô và bỏ qua cột số thứ tự.

    Đòi hỏi vẫn nguyên: TỪNG mảnh phải tự neo được vào đúng một đơn vị. Cái được
    nới chỉ là tính liền kề, và điều được khẳng định cũng yếu đi đúng chừng ấy —
    "những mẩu này đều có trong tài liệu", không phải "chúng nằm cạnh nhau".

    ponytail: neo trỏ vào mảnh ĐẦU; giao diện hiện một chip. Nếu đo thấy người
    dùng cần bấm tới từng con số, đổi `neo` thành một danh sách.
    """
    manh = [m for m in (x.strip() for x in trich.split("\n")) if m]
    if len(manh) < 2:
        return None
    neo = [_neo_mot_manh(m, don_vi) for m in manh]
    return neo[0] if all(n is not None for n in neo) else None


def _neo_mot_manh(manh: str, don_vi: list[DonViVanBan]) -> Neo | None:
    """Một mảnh của trích rời rạc: phải chỉ tới ĐÚNG MỘT đơn vị.

    Không dùng `xac_minh` ở đây: nó trả về đơn vị KHỚP ĐẦU TIÊN, đúng cho một
    đoạn trích dài tự nó đã định danh, nhưng ở đây mảnh đã ngắn lại còn mất cả
    tính liền kề — lấy hit đầu tiên là đoán. "2,0" có ở ba ô thì nó không chỉ
    tới đâu cả, và phải bị loại chứ không neo vào ô đầu.
    """
    m = normalize(manh)
    if not m:
        return None
    khop = [d for d in don_vi if m == normalize(d.noi_dung)] or (
        [d for d in don_vi if len(m) >= QUOTE_TOI_THIEU and m in normalize(d.noi_dung)]
    )
    if len(khop) != 1:
        return None
    d = khop[0]
    return Neo(LyDoNeo.ok, chi_so_don_vi=d.chi_so, trang=d.trang, offset_dau=d.offset_dau,
               nguon_chu=d.nguon_chu, do_tin=d.do_tin)


def neo_trich(trich: str, don_vi: list[DonViVanBan]) -> Neo:
    """Bốn đường, từ chặt tới lỏng; đường nào cũng là tra chuỗi thuần, 0 token.

    1. `xac_minh` — mảnh nằm trong MỘT đơn vị. Dùng chung với dữ kiện checklist
       và với trích dẫn điều luật, nên nó không được đụng tới.
    2. ô ngắn khớp trọn và duy nhất (`_neo_o_duy_nhat`).
    3. dãy đơn vị LIỀN KỀ — một hàng bảng, hai dòng ký tên.
    4. nhiều mảnh rời rạc mà mảnh nào cũng tự neo được.
    """
    trich = bo_tien_to(trich)
    neo = xac_minh(trich, don_vi)
    if neo.ly_do is LyDoNeo.ok:
        return neo
    if "\n" not in trich:
        return _neo_o_duy_nhat(trich, don_vi) or neo
    return _neo_day_lien_tiep(trich, don_vi) or _neo_manh_roi_rac(trich, don_vi) or neo


def _neo_ra(t: dict, neo: Neo) -> dict:
    """Neo đã kiểm → hình dạng `NeoTaiLieuOut`. MỘT chỗ dựng cho cả quan sát,
    phép tính và khác biệt: ba nơi dựng riêng là ba cơ hội lệch nhau một trường,
    và giao diện đọc cả ba bằng cùng một thành phần."""
    d = next(d for d in t["don_vi"] if d.chi_so == neo.chi_so_don_vi)
    bang = getattr(d, "bang", None)
    return {
        "tai_lieu_id": t["id"],
        "chi_so_don_vi": neo.chi_so_don_vi,
        "trang": neo.trang,
        "vung": getattr(d, "vung", "than"),
        "bang": list(bang) if bang else None,
        "nguon_chu": neo.nguon_chu.value if neo.nguon_chu else "lop_chu",
        "do_tin": neo.do_tin,
    }


def _neo_dau_tien(trich: str, goi: list[dict]) -> tuple[dict, Neo] | None:
    """Tài liệu ĐẦU TIÊN trong lượt mà `trich` tra ngược được, hoặc `None`.

    Khác `quan_sat`, ba mảng của S4 không mang nhãn tài liệu: rút dữ kiện và
    kiểm số học là việc trên MỘT tài liệu, và bắt mô hình gắn nhãn ở chỗ nó
    không cần chỉ thêm một đường để nó gắn sai. Vẫn là tra chuỗi thuần — đoạn
    trích khớp ở đâu thì neo ở đó, không có phép đoán nào ở đây.
    """
    for t in goi:
        neo = neo_trich(trich, t["don_vi"])
        if neo.ly_do is LyDoNeo.ok:
            return t, neo
    return None


def _khoa_snake(s: str) -> str:
    """"Họ tên sinh viên" → `ho_ten_sinh_vien`.

    KHÔNG dùng `normalize` của phép neo: ở đó dấu là CHỮ (xem docstring
    `verify_tier1.normalize`), còn ở đây ta cần một khoá ASCII đi vào cột
    `du_kien_tai_lieu.khoa` và hiện ra trong URL, log, biểu mẫu soạn thảo. Hai
    việc khác nhau nên hai hàm khác nhau, không phải một hàm nới ra.
    """
    s = unicodedata.normalize("NFD", (s or "").strip().lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s)).strip("_")[:60]


def _lay_phep_tinh(ra: dict, goi: list[dict]) -> tuple[list[dict], int]:
    """Chạy từng biểu thức BẰNG MÃ rồi đặt kết quả cạnh con số tài liệu ghi.

    Ba cách hỏng, cùng một xử lý: biểu thức không phải bốn phép trên số, đoạn
    trích không neo được, hoặc cả hai. Không cái nào được đi tiếp — một dòng
    "khớp/không khớp" không có chỗ để soi lại là một khẳng định trần trụi.
    """
    giu: list[dict] = []
    bo = 0
    for o in ra.get("phep_tinh") or []:
        if not isinstance(o, dict):
            bo += 1
            continue
        bieu_thuc = str(o.get("bieu_thuc") or "").strip()
        ket_qua_tai_lieu = str(o.get("ket_qua_tai_lieu") or "").strip()
        gia_tri = tinh(bieu_thuc)
        neo = _neo_dau_tien(bo_tien_to(str(o.get("trich") or "")), goi)
        if gia_tri is None or neo is None:
            bo += 1
            continue
        ket_qua_code = viet_so(gia_tri)
        giu.append({
            "bieu_thuc": bieu_thuc,
            "ket_qua_code": ket_qua_code,
            "ket_qua_tai_lieu": ket_qua_tai_lieu,
            "khop": so_bang_nhau(ket_qua_code, ket_qua_tai_lieu),
            "neo": _neo_ra(*neo),
        })
    return giu, bo


# Ký tự người ta kẻ một chỗ ĐỂ ĐIỀN, và dấu hiệu của một chỗ như vậy: dấu chấm
# lửng `…`, hoặc một dãy từ ba dấu chấm / gạch ngang / gạch dưới trở lên. Một
# dấu chấm lẻ thì không — `20.000.000` phân nhóm nghìn bằng đúng ký tự đó.
_KY_TU_KE = "._–—-… \t"
_RE_CHO_DIEN = re.compile(r"…|[._–—-]{3,}")


def vung_trong(gia_tri: str) -> bool:
    """`gia_tri` này có phải một VÙNG CHỜ ĐIỀN chứ không phải một giá trị không.

    Đo trên tệp mẫu 2026-09-16: một phiếu TRẮNG cho ra
    `ho_ten_sinh_vien = "………………………………"` và `thoi_gian = "từ ngày … / … /20 …"`.
    Chép chúng vào bảng dữ kiện là dựng một biểu mẫu TRÔNG NHƯ đã điền, rồi nó
    đi thẳng vào một bản thảo — đúng chế độ hỏng FR-011 cấm.

    Hai dấu hiệu, cái nào cũng đủ:

    * bỏ hết ký tự kẻ mà không còn gì — `"—"`, `"___"`;
    * còn dấu chấm lửng hay một dãy ba chấm/gạch trở lên ở bất kỳ đâu —
      `"từ ngày … / … /20 …"` vẫn là một chỗ trống dù có chữ quanh nó.

    Nghiêng về phía LOẠI: một giá trị thật lỡ mang dấu chấm lửng thì người dùng
    gõ lại được, còn một chỗ trống lọt vào bản thảo thì không ai thấy.
    """
    s = (gia_tri or "").strip()
    return not s.strip(_KY_TU_KE) or bool(_RE_CHO_DIEN.search(s))


def _lay_truong(ra: dict, goi: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Trường động → dòng dữ kiện đúng hình dạng `rut_du_kien` (để `luu_du_kien`
    chỉ có MỘT bộ khoá phải hiểu).

    `nguon` lấy theo HẠNG chữ đã neo được, không theo ý người gọi — cùng luật
    với `neo_du_kien.loc_co_neo`, và cũng là thứ ràng buộc `ck_du_kien_do_tin`
    cưỡng chế ở tầng DB: `do_tin` chỉ sống với `tai_lieu_ocr`.

    Trả thêm SỐ LOẠI TÁCH THEO LÝ DO, cùng lý lẽ `LyDoNeo`/`Tier1Reason` không
    gộp nhãn: "biểu mẫu chưa điền nên không có gì để rút" và "mô hình trích một
    câu không có trong tài liệu" là hai chế độ hỏng khác nhau, đòi hai cách sửa
    khác nhau, và gộp chúng là vứt đi phần dữ liệu có giá trị nhất của chương
    đánh giá.
    """
    giu: list[dict] = []
    dem = {"vung_trong": 0, "khong_neo": 0, "sai_hinh_dang": 0}
    for o in ra.get("truong") or []:
        if not isinstance(o, dict):
            dem["sai_hinh_dang"] += 1
            continue
        khoa = _khoa_snake(str(o.get("khoa") or ""))
        gia_tri = str(o.get("gia_tri") or "").strip()
        if not khoa or not gia_tri:
            dem["sai_hinh_dang"] += 1
            continue
        # Trường tài liệu KHÔNG nói thì không tồn tại: một dòng dữ kiện rỗng
        # trông y hệt một dòng đã kiểm mà không có gì đứng sau nó.
        if vung_trong(gia_tri):
            dem["vung_trong"] += 1
            continue
        neo = _neo_dau_tien(bo_tien_to(str(o.get("trich") or "")), goi)
        if neo is None:
            dem["khong_neo"] += 1
            continue
        t, n = neo
        giu.append({
            "key": khoa,
            "nhan": str(o.get("nhan") or "").strip() or None,
            "gia_tri": gia_tri,
            "trich": bo_tien_to(str(o.get("trich") or "")),
            "nguon": "tai_lieu_ocr" if n.nguon_chu is NguonChu.ocr else "tai_lieu",
            "neo": n,
            "tai_lieu_id": t["id"],
        })
    return giu[:TOI_DA_TRUONG], dem


def _lay_khac_biet(ra: dict, goi: list[dict]) -> tuple[list[dict], int]:
    """Khác biệt giữa hai tài liệu — neo ĐÔI, mỗi đoạn trích trong đúng tài liệu
    của nó. Neo được một bên là một nửa bằng chứng; cả cặp bị bỏ."""
    if len(goi) < 2:
        return [], 0
    a, b = goi[0], goi[1]
    giu: list[dict] = []
    bo = 0
    for o in ra.get("khac_biet") or []:
        if not isinstance(o, dict):
            bo += 1
            continue
        neo_a = neo_trich(bo_tien_to(str(o.get("trich_a") or "")), a["don_vi"])
        neo_b = neo_trich(bo_tien_to(str(o.get("trich_b") or "")), b["don_vi"])
        if neo_a.ly_do is not LyDoNeo.ok or neo_b.ly_do is not LyDoNeo.ok:
            bo += 1
            continue
        giu.append({
            "noi_dung": str(o.get("noi_dung") or "").strip(),
            "neo_a": _neo_ra(a, neo_a),
            "neo_b": _neo_ra(b, neo_b),
        })
    return giu, bo


def _khoi_tai_lieu(goi: list[dict]) -> str:
    dong = []
    for t in goi:
        dong.append(f"## Tài liệu {t['nhan']} — {t['ten_tep']}")
        dong += [f"[{t['nhan']}-{d.chi_so}] ({_vi_tri(d)}) {d.noi_dung}" for d in t["gui"]]
    return "\n".join(dong)


def _ket(muc_dich: str, mo_ta: str | None, tra_loi: str, quan_sat: list[dict],
         suy_luan: list[str], can_du_kien: list[str], da_dung: list[dict],
         phep_tinh: list[dict] | None = None, khac_biet: list[dict] | None = None) -> dict:
    """Hình dạng DUY NHẤT của `tai_lieu_ket` — nhánh thành công và hai nhánh hạ
    cấp dùng chung, nên giao diện không phải biết lượt này đã hỏng hay chưa."""
    return {
        "muc_dich": muc_dich,
        "mo_ta": mo_ta,
        "tra_loi_ngan": tra_loi,
        "quan_sat": quan_sat,
        "suy_luan": suy_luan,
        "phep_tinh": phep_tinh or [],
        "khac_biet": khac_biet or [],
        "can_du_kien": can_du_kien,
        # Dữ kiện đã GHI của hội thoại — `graph_tra_cuu` điền sau khi lưu, vì
        # chỉ ở đó mới có `id` của dòng để giao diện sửa/xoá được.
        "du_kien": [],
        "tai_lieu_da_dung": da_dung,
    }


def hieu_tai_lieu(state: dict, tai_lieu: list[dict], llm, model: str,
                  prompt_path: Path | None = None) -> dict:
    """Đọc `tai_lieu` (mỗi phần tử `{id, ten_tep, don_vi}`) trả lời câu hỏi của lượt.

    Trả về state cộng `tai_lieu_ket`, `muc_dich_tai_lieu`, `tai_lieu_neo` và
    `traces`. Người gọi (`graph_tra_cuu`) lo phần DB — nạp `don_vi` theo chủ sở
    hữu — đúng hợp đồng "node lo phần DB, hàm lo phần suy nghĩ" mà `assemble` đã
    lập.
    """
    prior_traces = state.get("traces") or {}
    cau_hoi = state.get("cau_hoi_day_du") or state.get("query") or ""
    goi = [
        {**t, "nhan": NHAN[i], "gui": loc_don_vi(t["don_vi"], cau_hoi)}
        for i, t in enumerate(tai_lieu[: len(NHAN)])
    ]
    da_dung = [{"id": t["id"], "ten_tep": t["ten_tep"], "nhan": t["nhan"]} for t in goi]
    so_don_vi = sum(len(t["gui"]) for t in goi)

    def _hong(tra_loi: str, nguon: str) -> dict:
        return {
            **state,
            "tai_lieu_ket": _ket("hoi", None, tra_loi, [], [], [], da_dung),
            "muc_dich_tai_lieu": None,
            "tai_lieu_neo": [],
            "tai_lieu_du_kien_moi": [],
            "traces": {**prior_traces, "hieu_tai_lieu_nguon": nguon, "hieu_tai_lieu_model": model,
                       "hieu_tai_lieu_so_don_vi_gui": so_don_vi, "hieu_tai_lieu_so_quan_sat_giu": 0,
                       "hieu_tai_lieu_so_quan_sat_bo": 0, "hieu_tai_lieu_token_in": 0,
                       "hieu_tai_lieu_token_out": 0, "hieu_tai_lieu_cost_usd": 0.0},
        }

    if not goi:
        # Không tài liệu nào đọc được (id không thuộc người gọi, hoặc S1 chưa
        # lưu `don_vi`): nói thật, KHÔNG gọi mô hình với một prompt rỗng rồi để
        # nó tự nghĩ ra một tài liệu.
        return _hong(CHUA_DOC_DUOC, "khong_co_tai_lieu")

    try:
        kiem_tran_chi_phi_tai_lieu(sum(len(d.noi_dung) for t in goi for d in t["gui"]))
    except VuotTran:
        return _hong(QUA_DAI, "vuot_tran")

    prompt = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8").format(
        cau_hoi=cau_hoi, tai_lieu=_khoi_tai_lieu(goi),
    )
    nhan = [t["nhan"] for t in goi]
    usage = None
    try:
        raw, usage = llm.chat(model, messages(prompt), json_schema=schema_hieu(nhan))
        ra = json.loads(raw)
        if not isinstance(ra, dict):
            raise TypeError(f"phản hồi phải là object, được {type(ra).__name__}")
    except Exception as e:
        # Cùng ruling với `rut_du_kien`: lỗi hạ tầng KHÔNG được hạ cấp thành
        # "tài liệu không có gì" — nói rõ là chưa đọc được để người dùng thử lại.
        logger.warning("hieu_tai_lieu: lỗi (%s: %s)", type(e).__name__, e, exc_info=True)
        return _hong(CHUA_DOC_DUOC, "loi")

    theo_nhan = {t["nhan"]: t for t in goi}
    giu: list[dict] = []
    dem = {f"hieu_tai_lieu_bo_{ly.value}": 0 for ly in LyDoNeo if ly is not LyDoNeo.ok}
    so_bo = 0
    for o in ra.get("quan_sat") or []:
        if not isinstance(o, dict):
            continue
        t = theo_nhan.get(str(o.get("tai_lieu") or ""))
        if t is None:
            so_bo += 1
            dem["hieu_tai_lieu_bo_trich_khong_khop"] += 1
            continue
        trich = bo_tien_to(str(o.get("trich") or ""))
        # Tra ngược trong TOÀN BỘ đơn vị của tài liệu đó, không chỉ phần đã gửi:
        # phép neo nói "câu này có trong tài liệu", và phép lọc đầu vào là chuyện
        # của chi phí, không phải của bằng chứng.
        neo = neo_trich(trich, t["don_vi"])
        if neo.ly_do is not LyDoNeo.ok:
            so_bo += 1
            dem[f"hieu_tai_lieu_bo_{neo.ly_do.value}"] += 1
            continue
        giu.append({
            "noi_dung": str(o.get("noi_dung") or "").strip(),
            "trich": trich,
            "neo": _neo_ra(t, neo),
        })

    giu = giu[:TOI_DA_QUAN_SAT]
    muc_dich = str(ra.get("muc_dich") or "hoi")
    phep_tinh, phep_tinh_bo = _lay_phep_tinh(ra, goi)
    truong, truong_bo = _lay_truong(ra, goi)
    # Chỉ lượt SO SÁNH mới có khác biệt: một danh sách "khác biệt" trong lượt
    # tóm tắt là nội dung mô hình tự thêm vào, không phải thứ ai hỏi.
    khac_biet, khac_biet_bo = _lay_khac_biet(ra, goi) if muc_dich == "so_sanh" else ([], 0)
    can_du_kien = [str(s).strip() for s in (ra.get("can_du_kien") or []) if str(s).strip()]
    if muc_dich == "so_sanh" and len(goi) < 2 and CAN_TAI_LIEU_THU_HAI not in can_du_kien:
        can_du_kien.append(CAN_TAI_LIEU_THU_HAI)
    return {
        **state,
        # Mục đích THẬT mô hình đọc được, kể cả cái lát cắt này chưa làm — S5/S6
        # rẽ nhánh trên khoá này.
        "muc_dich_tai_lieu": muc_dich if muc_dich in MUC_DICH else None,
        "tai_lieu_ket": _ket(
            muc_dich if muc_dich in MUC_DICH_LAM_DUOC else "hoi",
            str(ra.get("mo_ta") or "").strip() or None,
            str(ra.get("tra_loi_ngan") or "").strip(),
            giu,
            [str(s).strip() for s in (ra.get("suy_luan") or []) if str(s).strip()][:TOI_DA_SUY_LUAN],
            can_du_kien,
            da_dung,
            phep_tinh,
            khac_biet,
        ),
        # S5 điền: điều khoản đưa sang đường pháp lý mang neo của nó.
        "tai_lieu_neo": [],
        # Dữ kiện MỚI, chưa ghi: node thuần không chạm DB (`graph_tra_cuu` lo).
        "tai_lieu_du_kien_moi": truong,
        "traces": {
            **prior_traces,
            "hieu_tai_lieu_nguon": "llm",
            "hieu_tai_lieu_model": model,
            "hieu_tai_lieu_muc_dich": muc_dich if muc_dich in MUC_DICH else "khong_ro",
            "hieu_tai_lieu_so_don_vi_gui": so_don_vi,
            "hieu_tai_lieu_so_quan_sat_giu": len(giu),
            "hieu_tai_lieu_so_quan_sat_bo": so_bo,
            **dem,
            # Đếm, không chép: `traces` đi vào bảng dùng chung, tài liệu thì chỉ
            # sống trong hội thoại của nó.
            "hieu_tai_lieu_so_phep_tinh": len(phep_tinh),
            "hieu_tai_lieu_so_phep_tinh_bo": phep_tinh_bo,
            "hieu_tai_lieu_so_truong_giu": len(truong),
            "hieu_tai_lieu_so_truong_bo": sum(truong_bo.values()),
            **{f"hieu_tai_lieu_truong_bo_{ly}": n for ly, n in truong_bo.items()},
            "hieu_tai_lieu_so_khac_biet": len(khac_biet),
            "hieu_tai_lieu_so_khac_biet_bo": khac_biet_bo,
            "hieu_tai_lieu_token_in": usage.token_in if usage else 0,
            "hieu_tai_lieu_token_out": usage.token_out if usage else 0,
            "hieu_tai_lieu_cost_usd": usage.cost_usd if usage else 0.0,
        },
    }
