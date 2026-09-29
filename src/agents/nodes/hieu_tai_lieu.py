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
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from src.agents.nodes.dung_ban_thao_tong_quat import chua_dien_khuon
from src.agents.nodes.route import Intent
from src.agents.nodes.verify_tier1 import QUOTE_TOI_THIEU
from src.services import khuon_mau
from src.services.bo_nho import _RE_DIEU, _vuong_luoi_chan
from src.services.bo_nho_tai_khoan import GIA_TRI_TOI_DA
from src.services.doc_tai_lieu import (
    KY_TU_MOI_TRANG,
    RE_CHO_DIEN,
    ChoTrong,
    DinhDangChu,
    DonViVanBan,
    GianCach,
    NguonChu,
    _la_cham,
    nhan_sach_don_vi,
)
from src.services.llm import TruncatedOutputError, Usage
from src.services.neo_du_kien import LyDoNeo, Neo, normalize, xac_minh
from src.services.phep_tinh import SAI_SO, so_bang_nhau, tinh, viet_so
from src.services.prompts import messages
from src.services.tai_lieu import VuotTran, kiem_tran_chi_phi_tai_lieu

logger = logging.getLogger(__name__)
PROMPT_PATH = Path("prompts/hieu_tai_lieu.v1.md")
# Tài liệu có khuôn gốc (kế hoạch `khuon-goc-dien-tai-cho.md`, P4b): prompt v2 thay
# quy tắc 15 (dựng lại cả văn bản) bằng phép sửa trên chính tệp. v1 giữ nguyên cho
# đường HTML — tài liệu tải lên trước khuôn gốc, và lượt soạn không có tài liệu.
PROMPT_KHUON_PATH = Path("prompts/hieu_tai_lieu.v2.md")

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
# Hai mục đích SOẠN (S6): lượt này không nói VỀ tài liệu nữa mà dựng một văn
# bản MỚI từ nó — `graph_tra_cuu` rẽ sang `dung_ban_thao_tong_quat`.
MUC_DICH_SOAN = frozenset({"tao_van_ban", "sua_ban_thao"})
MUC_DICH_LAM_DUOC = frozenset({"tom_tat", "hoi", "phan_tich", "trich_du_kien", "so_sanh",
                               "doi_chieu_luat"}) | MUC_DICH_SOAN

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
# Câu trả lời THAY cho văn xuôi của mô hình khi lượt so sánh chỉ có một tài
# liệu. Đo ba lần liên tiếp 2026-09-16: mô hình vẫn viết "bản này khác bản
# trước đó về thời giờ làm việc, chế độ nghỉ phép…" — một so sánh với một tài
# liệu KHÔNG TỒN TẠI. `can_du_kien` nói đúng, nhưng nó nói SAU khi văn xuôi đã
# khẳng định xong, và người đọc chỉ đọc câu đầu.
SO_SANH_THIEU_TAI_LIEU = (
    "Lượt này tôi chỉ có một tài liệu nên chưa so sánh được. Hãy đính kèm tài liệu thứ hai, "
    "tôi đặt hai bên cạnh nhau và chỉ ra từng chỗ khác."
)
# Người hỏi XIN SO SÁNH — đọc từ chính chữ họ gõ, 0 token. Gác trên `muc_dich`
# của mô hình là để một phép kiểm an toàn bật tắt theo nhãn nó vừa chọn: đo năm
# lần cùng một câu hỏi, nó gán lúc `so_sanh` lúc `hoi`, và ở nhánh `hoi` câu
# khẳng định "khác bản trước đó" đi thẳng ra người dùng. Cùng khuôn
# `kho.xin_dang_bang` và `gioi_thieu.chac_chan_meta`: chữ người dùng thắng.
#
# "khác" một mình KHÔNG đủ — "Điều 3 khác Điều 2" là so sánh trong CÙNG một tài
# liệu và là câu hỏi hợp lệ. Phải có dấu hiệu của một tài liệu THỨ HAI.
_RE_XIN_SO_SANH = re.compile(
    r"so\s*sánh|đối\s*chiếu\s+với|khác\s+(?:gì\s+)?(?:so\s+với|với)\s|so\s+với\s+(?:bản|tài\s*liệu|phiên\s*bản)"
    r"|(?:hai|2)\s+(?:bản|tài\s*liệu|tệp|file)|bản\s+(?:trước|cũ|kia|còn\s*lại)",
    re.IGNORECASE,
)


def xin_so_sanh(cau_hoi: str) -> bool:
    """Câu hỏi này có xin đặt tài liệu cạnh một tài liệu KHÁC không. Hàm thuần."""
    return bool(_RE_XIN_SO_SANH.search(cau_hoi or ""))


# ── Lượt nối tiếp trên khuôn gốc (owner 2026-09-28, G7) ─────────────────────
#
# Router gọi "Điền họ và tên … mã số …" trên một biểu mẫu đã tải lên là `tai_lieu`
# (câu hỏi VỀ tài liệu), nên gác `_muc_dich_soan_da_xac_nhan` hạ mọi lượt điền, sửa,
# dựng lại nối tiếp về `hoi` (hội thoại thật a99dfda8…). Trên tài liệu CÓ khuôn gốc,
# bằng chứng thay cho ý kiến router là động từ trong CHÍNH lời người hỏi cộng phép đã
# qua `kiem_phep_sua` — mọi giá trị vẫn chỉ đến từ lời người hỏi. Mỗi mẫu có hai dạng:
# có dấu và không dấu; một chữ khớp dạng không dấu chỉ được nhận khi người hỏi gõ
# nó KHÔNG dấu, hoặc gõ đúng chữ có dấu — "điện thoại", "đại diện" không phải "điền".
def _mau_dong_tu(co_dau: str, khong_dau: str) -> tuple[re.Pattern, re.Pattern]:
    bien = r"(?<!\w)(?:{})(?!\w)"
    return re.compile(bien.format(co_dau)), re.compile(bien.format(khong_dau))


_RE_DIEN_SUA = _mau_dong_tu(
    r"điền|ghi\b.{0,40}?\bvào|sửa|thay(?!\s+(?:mặt|vì))|đổi\b.{0,40}?\bthành|bổ\s+sung|xoá|xóa"
    r"|thêm\b.{0,40}?\bvào|cập\s+nhật",
    r"dien|ghi\b.{0,40}?\bvao|sua|thay(?!\s+(?:mat|vi))|doi\b.{0,40}?\bthanh|bo\s+sung|xoa"
    r"|them\b.{0,40}?\bvao|cap\s+nhat",
)
# Không có "xuất bản" trần: đó là "phát hành" ("được xuất bản năm nào?").
_RE_TAO_LAI = _mau_dong_tu(
    r"soạn\s+thảo|soạn\s+lại|tạo\s+lại|dựng\s+lại|xuất\s+(?:ra\s+)?(?:file|tệp|văn\s+bản)|làm\s+lại\s+văn\s+bản",
    r"soan\s+thao|soan\s+lai|tao\s+lai|dung\s+lai|xuat\s+(?:ra\s+)?(?:file|tep|van\s+ban)|lam\s+lai\s+van\s+ban",
)
# Dấu hỏi (review G7): một động từ dựng lại trong câu HỎI ("Văn bản này do ai soạn
# thảo?") không tự thành lượt soạn — `_quyet_khuon`. "không"/"chưa" chỉ hỏi ở cuối câu
# ("… được không"); giữa câu chúng phủ định ("không cần điền").
_RE_CAU_HOI = _mau_dong_tu(
    r"ai|gì|nào|sao|bao\s+giờ|đâu|(?:không|chưa)(?=[\s.!…]*$)",
    r"ai|gi|nao|sao|bao\s+gio|dau|(?:khong|chua)(?=[\s.!…]*$)",
)
# Lời xin XEM bản đã có (Q3): CẢ câu phải là lời xin xem, trên dạng không dấu — một
# danh sách đóng, nên "cho tôi xem biểu mẫu này nói gì" (hỏi nội dung) không khớp.
_XEM_DT = r"(?:van ban|ban thao|ban|phieu|bieu mau|tep|file)"
_XEM_SAU_DT = (
    r"(?: (?:moi|nay|do|vua roi|hien tai|hoan chinh|cuoi cung|cua toi"
    r"|(?:da|vua|sau khi|toi da|toi vua) (?:dien|sua)(?: xong)?))*"
)
_RE_XEM = re.compile(
    r"(?:(?:vay|the|ok|oke|roi|gio) )?(?:(?:hay|lam on|vui long|xin) )?(?:(?:cho|de|giup) )?"
    r"(?:(?:toi|minh|em|tui) )?(?:(?:muon|can|duoc|thu) )*"
    rf"(?:(?:xem|mo)(?: lai)? {_XEM_DT}{_XEM_SAU_DT}|{_XEM_DT}{_XEM_SAU_DT} (?:o )?dau)"
    r"(?: (?:di|nhe|nha|voi|giup|giup toi|cho toi|duoc khong|roi|nao|a|ha))*"
)


def _cau_thuong(cau: str) -> str:
    """NFC, chữ thường, khoảng trắng gộp — cùng độ dài với `_bo_dau` của nó."""
    return " ".join(unicodedata.normalize("NFC", cau or "").casefold().split())


def _co_dong_tu(mau: tuple[re.Pattern, re.Pattern], cau: str) -> bool:
    goc = _cau_thuong(cau)
    for m in mau[1].finditer(_bo_dau(goc)):
        doan = goc[m.start() : m.end()]
        if doan == m.group() or mau[0].fullmatch(doan):
            return True
    return False


def xin_xem_ban_thao(cau: str) -> bool:
    """Cả câu là lời xin XEM bản thảo đã có ("cho tôi xem văn bản mới sau khi điền",
    "mở bản đã điền", "bản đã điền đâu"). Hàm thuần, 0 token."""
    return bool(_RE_XEM.fullmatch(_bo_dau(_cau_thuong(cau)).strip(" .!?…")))


def xin_dien_sua(cau: str) -> bool:
    """Lời người hỏi có động từ ĐIỀN/SỬA ('điền', 'ghi … vào', 'sửa', 'thay', 'đổi …
    thành', 'bổ sung', 'xoá', 'thêm … vào', 'cập nhật') — trừ lời xin xem ("… sau khi
    điền"). Hàm thuần, 0 token."""
    return _co_dong_tu(_RE_DIEN_SUA, cau) and not xin_xem_ban_thao(cau)


def xin_tao_lai(cau: str) -> bool:
    """Lời người hỏi xin DỰNG LẠI chính văn bản ('soạn thảo (lại)', 'soạn lại', 'tạo
    lại', 'dựng lại', 'xuất file/tệp/văn bản', 'làm lại văn bản'). Hàm thuần."""
    return _co_dong_tu(_RE_TAO_LAI, cau)


def _la_cau_hoi(cau: str) -> bool:
    """Câu có dạng câu hỏi: '?' hay một từ hỏi. Lời xin lịch sự ("… được không?")
    cũng khớp — ở đó cách đọc của mô hình quyết định (`_quyet_khuon`). Hàm thuần."""
    return "?" in (cau or "") or _co_dong_tu(_RE_CAU_HOI, cau)


# Dấu nội bộ của prompt khuôn gốc (`_dong_tai_cho`): `⟦n⟧`, `⟦n=«giá trị»⟧`, `¶n`. Mô
# hình chép chúng vào lời đáp (đo được: "… vào chỗ trống số 0 … ⟦0⟧ … ⟦1⟧"); người
# đọc không bao giờ thấy chúng. Dấu mang giá trị nhường chỗ cho giá trị.
_RE_DAU_GIA_TRI = re.compile(r"⟦\d+=«([^»⟧\n]*)»⟧")
_RE_DAU_NOI_BO = re.compile(r"⟦[^⟧\n]*⟧|⟦\d*|⟧|¶\d*")


def bo_dau_noi_bo(s: str) -> str:
    """Chữ mô hình viết cho người đọc, bỏ dấu nội bộ. Chữ không mang dấu nào ra y
    nguyên từng byte; có dấu thì dọn khoảng trắng nó để lại."""
    if not any(ch in s for ch in "⟦⟧¶"):
        return s
    s = _RE_DAU_NOI_BO.sub("", _RE_DAU_GIA_TRI.sub(r"\1", s))
    s = re.sub(r"[ \t]+([,.;:!?)])", r"\1", s)
    s = re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", s))
    return s.strip()


# Lời mô hình tự nhận đã làm một thay đổi — không bao giờ ra khỏi một lượt hỏi đáp
# (không áp gì). "Tôi đã ghi nhận" không phải một thay đổi.
_RE_DA_LAM = re.compile(
    r"\btôi\s+(?:đã|vừa)\s+(?:điền|sửa|thay|cập\s+nhật|bổ\s+sung|xoá|xóa|thêm|ghi(?!\s+nhận)|dựng|tạo|soạn)",
    re.IGNORECASE,
)
# Câu thay cho lời tự nhận đó khi lượt kết thúc là hỏi đáp mà không có khuôn gốc nào
# để nói cụ thể hơn (`chua_dien_khuon`).
CHUA_THAY_DOI = (
    "Lượt này tôi chưa sửa hay điền gì: tôi đọc câu của bạn là một câu hỏi về tài liệu, nên không "
    "bản thảo nào thay đổi. Nếu bạn muốn sửa, hãy nói rõ chỗ cần sửa và nội dung mới."
)
# Nhiều biểu mẫu có khuôn gốc mà mô hình không nêu biểu mẫu nào: không áp gì, hỏi lại.
CHUA_RO_KHUON = (
    "Lượt này tôi chưa điền gì: bạn có {so} biểu mẫu ({ds}) và tôi chưa rõ bạn muốn điền vào biểu mẫu "
    "nào. Hãy nói tên biểu mẫu cùng giá trị cần điền, hoặc bấm vào chỗ trống trên trang."
)


# Phase 3 Half B, fix round 1 — safety net trên `MUC_DICH_SOAN`, thêm sau một
# sự cố THẬT: owner hỏi "tôi muốn biết đây là đơn gì" (một câu hỏi, không xin
# sửa gì) và mô hình gán `muc_dich = "sua_ban_thao"` — `dung_ban_thao_tong_quat`
# tin tuyệt đối nhãn đó và VIẾT ĐÈ bản thảo thật, từ 9 mục xuống còn 5.
#
# Bản ĐẦU của gác này (rút lại — xem review) là hai danh sách regex tiếng Việt
# ("dấu hiệu câu hỏi" / "dấu hiệu soạn"). Bị bác vì hai lý do gốc rễ, không chỉ
# vì thiếu vài mẫu: (1) liệt kê cách diễn đạt là một danh sách MỞ — luôn còn
# một câu thật không khớp mẫu nào ("đây là đơn gì" không chứa cụm "là gì");
# (2) tiếng Việt DÙNG CHUNG một cấu trúc cho câu hỏi thật VÀ cho một YÊU CẦU
# lịch sự ("Có thể… được không?" là xin làm, không phải hỏi thông tin) — không
# quy tắc từ vựng/cú pháp nào tách được hai điều đó, vì khác biệt nằm ở NGHĨA
# (hỏi thông tin và xin hành động), không nằm ở CHỮ.
#
# Gác THẬT không dựng thêm một bộ phân loại tiếng Việt nào — nó dùng lại một
# Ý KIẾN THỨ HAI đã có sẵn, MIỄN PHÍ, từ một mô hình KHÁC: `route()` (khác
# prompt, khác việc — "đây có phải một yêu cầu soạn thảo không", chạy TRƯỚC
# `hieu_tai_lieu` với chính câu hỏi này) đã đặt `state["intent"]` trước khi
# `hieu_tai_lieu` chạy, mỗi khi lượt đi qua `route` (xem `_re_sau_route`
# `graph_tra_cuu.py` — đường DUY NHẤT một lượt KHÔNG đính-kèm-tươi tới được
# đây). Một `muc_dich in MUC_DICH_SOAN` chỉ được TIN khi ý kiến ĐỘC LẬP đó
# CŨNG là `Intent.soan_thao` — hai mô hình khác nhau cùng đồng ý, không phải
# một mô hình tự xác nhận chính nó. Khi `route` đã chọn `Intent.tai_lieu` (câu
# hỏi VỀ tài liệu — chính xác trường hợp "đây là đơn gì"), một `sua_ban_thao`
# từ `hieu_tai_lieu` là một BẤT ĐỒNG giữa hai lượt gọi, không phải bằng
# chứng — hạ về `hoi`.
#
# `intent` VẮNG MẶT (lượt đính kèm tài liệu TƯƠI, `_vao_graph` rẽ tất định
# TRƯỚC `route`, quyết định chủ sở hữu Q4) thì không có ý kiến thứ hai nào để
# đối chiếu — tin `hieu_tai_lieu` như trước bản vá này: gửi một tệp kèm một
# câu là hành động đã đủ rõ ràng để không cần một phép kiểm thứ hai (cùng lý
# lẽ Q4 đã lập cho chính lượt đó).
def _muc_dich_soan_da_xac_nhan(intent: object) -> bool:
    """`state["intent"]` (từ `route()`, nếu có chạy) có XÁC NHẬN một
    `muc_dich in MUC_DICH_SOAN` của `hieu_tai_lieu` hay không. Hàm thuần, 0
    token — không phân tích câu chữ, chỉ đối chiếu HAI QUYẾT ĐỊNH mô hình đã
    đưa ra."""
    if intent is None:
        return True
    return intent == Intent.soan_thao


# Quyết định chủ sở hữu 2026-09-16 (Q3): ≤3 điều khoản mỗi lượt đối chiếu. Trần
# của NGƯỜI ĐỌC chứ không của mô hình — ba điều khoản là số còn đọc hết được
# cạnh căn cứ luật của chúng trong một câu trả lời.
TOI_DA_DIEU_KHOAN = 3
# Trần câu hỏi ghép gửi sang đường pháp lý. `rewrite_query` truy hồi theo chính
# chuỗi này; dài hơn thì nó loãng ra chứ không tìm được nhiều hơn.
CAU_HOI_TOI_DA = 300
# Xin đối chiếu mà KHÔNG điều khoản nào tra ngược được: lượt này rơi về `hoi`,
# và người hỏi phải biết vì sao — im lặng ở đây trông y hệt một lượt đã đối
# chiếu xong và không thấy gì đáng nói.
DOI_CHIEU_KHONG_NEO = (
    "Tôi chưa lấy được điều khoản nào ra khỏi tài liệu để đặt cạnh luật, nên lượt này tôi "
    "chỉ đọc tài liệu chứ chưa đối chiếu. Bạn chỉ giúp tôi điều khoản cần đối chiếu — "
    "chép lại một đoạn hoặc nói rõ mục nào — tôi tra căn cứ cho đúng đoạn đó."
)

# Trên ngưỡng này thì không gửi cả tài liệu nữa. 10 trang là mức mọi hợp đồng,
# quyết định, phiếu đánh giá thật đều nằm dưới (đo trên tệp mẫu: 1 trang).
NGUONG_TRANG = 10
GIU_DAU = 12
GIU_THEO_CAU_HOI = 40

# Phase 16 R1 — đo TRỰC TIẾP qua OpenRouter (.sdd/phase-16-report.md,
# 2026-09-18): endpoint `google/gemini-2.5-flash-lite` khai
# `max_completion_tokens=65535` ở CẢ NĂM route (google-vertex, .../eu,
# google-ai-studio, .../flex, .../priority — không route nào thấp hơn). Không
# đặt `max_tokens` thì trần THẬT do OpenRouter/provider tự quyết — không ai
# biết là bao nhiêu (đúng như brief nêu), và production đã đo được
# `finish_reason=length` HAI lần liên tiếp trên một tài liệu mà gọi lại có
# `max_tokens` tường minh chỉ cần 9.744/65.535 token. Đặt THẲNG gần trần thật,
# trừ biên nhỏ cho phần bao (envelope) JSON của `response_format`.
TOI_DA_TOKEN_RA = 64_000

# Phase 16 R2 — trên ngưỡng ký tự này (tổng `noi_dung` của `t["gui"]`, MỘT tài
# liệu), một lượt gọi có nguy cơ cần nhiều hơn `TOI_DA_TOKEN_RA` để dựng lại
# TOÀN VĂN `van_ban.muc` — nên bị chia thành nhiều lượt kế tiếp
# (`_hieu_theo_phan`), mỗi lượt dựng một phần rồi ghép. Đo được (tài liệu thật
# 4.276 ký tự → 9.744 token ra, .sdd/phase-16-report.md): ~2,28 token/ký tự.
# Áp biên an toàn 1,5× (bảng/ô dày đặc hơn tốn token hơn văn xuôi thường, chưa
# đo trực tiếp trên ca đó) ⇒ ~3,42 token/ký tự khi LẬP KẾ HOẠCH; dành 90%
# `TOI_DA_TOKEN_RA` cho `van_ban` (10% còn lại cho các mảng khác dù được dặn để
# rỗng — không dựa vào việc mô hình có nghe lời): 57.600 ÷ 3,42 ≈ 16.842, làm
# tròn XUỐNG một số dễ nhớ. Với trần chi phí hiện tại (50.000 ký tự,
# `tai_lieu.kiem_tran_chi_phi_tai_lieu`), tài liệu LỚN NHẤT được phép chỉ cần
# chia tối đa 4 lượt (`ceil(50000/15000)`).
NGUONG_PHAN_KY_TU = 15_000

QUA_DAI = ("Tài liệu quá dài để đọc trong một lượt. Hãy tách nhỏ rồi gửi lại, "
           "hoặc hỏi về một phần cụ thể.")
# Fix round 2 (N3) — trần này (cùng `QUA_DAI`) đếm cả tài liệu nguồn LẪN bản
# thảo đang có (I2's fix) — khi chính bản thảo là phần đẩy nó vượt trần,
# "tách nhỏ tài liệu rồi gửi lại" không làm được gì (tài liệu không phải thứ
# vượt trần) VÀ lượt sửa bằng lời KẾ TIẾP sẽ vấp lại y hệt, vì bản thảo vẫn
# còn đó. Nói đúng thứ người dùng thật sự làm được: rút ngắn bản thảo trực
# tiếp (gõ tay, `PATCH /ban-thao/{id}/muc`) trước khi nhờ sửa tiếp bằng lời.
QUA_DAI_VOI_BAN_THAO = (
    "Bản thảo hiện tại cộng với tài liệu nguồn đã vượt giới hạn một lượt đọc. "
    "Sửa bằng lời sẽ vấp lại giới hạn này ở lượt sau — hãy tự rút ngắn bản "
    "thảo (gõ tay từng mục trên khung xem trước) trước khi nhờ sửa tiếp."
)
CHUA_DOC_DUOC = "Chưa đọc được tài liệu lúc này. Hãy thử lại."

# Phase 14 (owner D14-B) — lượt SOẠN TỰ DO: router nói `soan_thao`, hội thoại
# không có tài liệu nào. Khối `{tai_lieu}` của prompt mang lời dặn này thay cho
# danh sách đơn vị — cùng một prompt, cùng một lược đồ, không node thứ hai. Mọi
# giá trị vẫn phải lấy từ lời người hỏi: `lam_sach_van_ban` tra ngược về đúng
# nguồn ấy (`_nguon_soan` không có đơn vị tài liệu nào để cộng vào), và quy tắc
# 15 vẫn cấm "căn cứ Điều …" — một bản thảo chat không mang trích dẫn nào (R4).
KHONG_TAI_LIEU = (
    "(Lượt này KHÔNG có tài liệu nào. Người hỏi xin SOẠN một văn bản từ chính lời họ: `muc_dich` là "
    "`tao_van_ban` — hoặc `sua_ban_thao` khi có mục \"# Bản thảo đang có\" bên dưới và họ xin đổi nó. "
    "Dựng `van_ban` đủ các mục một văn bản Việt loại đó thường có (quy tắc 15); mọi giá trị lấy từ lời "
    "người hỏi, không có thì `[…]`. `quan_sat`, `truong`, `phep_tinh`, `dieu_khoan`, `khac_biet` để "
    "rỗng — không có tài liệu để trích.)"
)
# Lượt soạn tự do hỏng: không có tài liệu nào để "chưa đọc được", và không còn
# lời chỉ sang biểu mẫu (R1) — nói đúng việc đã hỏng.
CHUA_SOAN_DUOC = "Chưa soạn được lúc này. Hãy thử lại."

# Phase 16 R3 — `QUA_DAI` ở trên chặn TRƯỚC khi gọi mô hình (chi phí ước quá
# trần) và lời khuyên "tách nhỏ rồi gửi lại" đúng nghĩa ở đó: người dùng còn tự
# tách được nội dung HỌ gõ. Thông điệp này khác — nó chỉ tới sau khi ĐÃ chia
# tài liệu thành nhiều lượt (`_hieu_theo_phan`) mà một lượt VẪN cắt giữa chừng
# (`TruncatedOutputError`): với một BIỂU MẪU người dùng không tự viết ra, "tách
# nhỏ" không phải việc họ làm được — nói thẳng độ dài đo được và cho hai lối đi
# thật (hỏi từng mục, hoặc tự sửa trên bản gốc) thay vì lặp lại lời khuyên sai
# chỗ của `QUA_DAI`.
KHONG_DUNG_LAI_DUOC = (
    "Biểu mẫu này dài {so_ky_tu} ký tự — mô hình không dựng lại được toàn bộ "
    "trong giới hạn một lượt trả lời, dù đã chia thành nhiều phần. Bạn có thể "
    "hỏi tôi về từng mục cụ thể của biểu mẫu thay vì xin dựng lại toàn bộ, "
    "hoặc tự chỉnh sửa trực tiếp trên bản gốc."
)


# `DonViVanBan.vung` (Phase 8 R2) — cùng ba giá trị, cùng nghĩa: một mục của
# `van_ban` lấy từ đầu/chân trang thật thì mang đúng nhãn đó, không phải một
# mã riêng bịa ra cho `van_ban`.
VUNG_HOP_LE = ("than", "dau_trang", "chan_trang")


# ── Phase 12 part B — ký ức TÀI KHOẢN trong một lượt soạn ──────────────────
#
# Hợp đồng của chủ sở hữu, nguyên văn: "tôi muốn việc này được nhớ nhưng mà ko
# phải văn bản mới mà khách yêu cầu khác là điền luôn mà chỉ cần nhớ thôi".
# NHỚ, KHÔNG TỰ ĐIỀN — và một bản dựng lặng lẽ tự điền là một cách làm SAI yêu
# cầu, không phải một tiện ích thêm. Ba mảnh dưới đây là toàn bộ phần lượt soạn
# phải biết:
#
# * `rut_bo_nho` đọc dữ kiện người dùng TỰ KHAI trong chính câu họ gõ — phép
#   tất định 0 token, KHÔNG thêm một lượt gọi mô hình nào cho mỗi lượt soạn
#   (R5). Trường `truong` mà mô hình đã trả về không làm được việc này: nó đòi
#   neo về một ĐƠN VỊ TÀI LIỆU (`_lay_truong`), mà lượt soạn tự do không có tài
#   liệu nào để neo.
# * `khoa_duoc_hoi` quyết định lượt NÀY có hỏi tới một khoá hay không. Chỉ khoá
#   được hỏi mới cộng vào NGUỒN của phép làm sạch (`_nguon_soan`); mọi khoá
#   khác đi vào `cam` của `lam_sach_van_ban` và bị thay `[…]` nếu mô hình tự
#   điền. Đó là chỗ DUY NHẤT quy tắc "chỉ nhớ" được cưỡng chế bằng mã — một lời
#   dặn trong prompt chưa bao giờ đủ để chặn một mô hình.
# * `_khoi_bo_nho` đưa ký ức vào PROMPT, đúng đường mọi ngữ cảnh khác đi
#   (`# Bản thảo đang có`) — không vào `clauses`, không vào `facts`, không vào
#   một khối đã dựng.
_BO_DAU = str.maketrans("đĐ", "dD")


def _bo_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt, GIỮ NGUYÊN ĐỘ DÀI — một ký tự vào, một ký tự ra.

    Độ dài phải giữ vì `rut_bo_nho` khớp trên bản KHÔNG DẤU rồi cắt giá trị ra
    khỏi chuỗi GỐC bằng chính vị trí đã khớp: lệch một ký tự là cắt sai tên
    người. `normalize` (dùng chung cả hệ) CỐ Ý không bỏ dấu — trong tiếng Việt
    dấu là chữ, không phải trang trí — nên phép này sống ở đây và chỉ cho đúng
    một việc: nhận ra cái NHÃN người dùng gõ ("mã sv" hay "ma sv" là một nhãn).
    """
    return "".join(unicodedata.normalize("NFD", c)[0] for c in s.translate(_BO_DAU))


# Hai LOẠI mà `bo_nho_tai_khoan` cho phép, và không gì khác (brief Phase 12):
# dữ kiện về NGƯỜI (`ca_nhan`) và THÓI QUEN soạn (`thoi_quen`). Không biên bản
# hội thoại, không tài liệu, không thân bản thảo.
#
# Mỗi khoá đi kèm các NHÃN người Việt hay gõ cho nó, viết thường KHÔNG DẤU —
# `_bo_dau` đưa câu người dùng về đúng dạng ấy trước khi khớp. MỘT bảng phục vụ
# HAI việc, để không có hai bộ từ vựng trôi lệch nhau: nhận ra lời KHAI
# (`rut_bo_nho`) và nhận ra lời HỎI TỚI (`khoa_duoc_hoi`).
BO_NHO_KHOA: dict[str, tuple[str, tuple[str, ...]]] = {
    "ho_ten": ("ca_nhan", ("ho va ten", "ho ten", "ten toi", "toi ten")),
    "ma_sv": ("ca_nhan", ("ma so sinh vien", "ma sinh vien", "mssv", "ma sv")),
    "lop": ("ca_nhan", ("lop",)),
    "nganh": ("ca_nhan", ("nganh",)),
    "noi_thuc_tap": ("ca_nhan", ("dia diem thuc tap", "don vi thuc tap", "noi thuc tap")),
    "van_phong": ("thoi_quen", ("van phong",)),
    "xung_ho": ("thoi_quen", ("xung ho",)),
    "mau_hay_dung": ("thoi_quen", ("mau hay dung",)),
}
_NHAN_BO_NHO = {nhan: khoa for khoa, (_, nhan_cua) in BO_NHO_KHOA.items() for nhan in nhan_cua}
# Nhãn DÀI đứng trước nhãn ngắn trong phép hoặc: "ma so sinh vien" phải thắng
# "ma sv", nếu không giá trị bị cắt từ giữa nhãn. Dấu mở là đầu câu, dấu ngắt
# hay một liên từ — nhãn phải đứng ĐẦU một mệnh đề thì mới là lời khai, chứ
# không phải hai chữ lọt giữa một câu kể.
_NHAN_HOAC = "|".join(sorted((re.escape(n) for n in _NHAN_BO_NHO), key=len, reverse=True))
# Giá trị dừng ở dấu ngắt, HOẶC ngay trước một lời khai kế tiếp nối bằng
# "và"/"với" ("lớp: K00A và ngành là Luật kinh tế" là HAI lời khai, không phải
# một). Chỉ cắt khi sau liên từ là một NHÃN kèm dấu gán — "Công ty Mẫu Thử và
# Đồng sự" không có nhãn nào đằng sau nên đi qua nguyên vẹn.
# Fix round 1 (review MED) — dấu mở KHÔNG nhận `\n`. Nhận nó thì MỖI DÒNG của
# một khối dán là một lời khai mới: dán nguyên một biểu mẫu ("Họ và tên: … /
# Lớp: … / Mã sinh viên: …") ghi cả khối ấy vào tài khoản NHƯ THỂ là dữ kiện về
# chính người dán — dữ liệu cá nhân của người thứ ba, kể cả một mã sinh viên,
# vào thẳng DB từ văn bản tự do. Lời khai thật là thứ người ta GÕ trong câu của
# mình, và câu ấy nằm trên một dòng, ngắt bằng dấu câu.
# ponytail: trần đã biết — người dùng mở lượt bằng đúng một dòng nhãn rồi mới
# dán phần còn lại thì dòng ĐẦU vẫn được nhận. Siết thêm (chặn hẳn lượt nhiều
# dòng) khi đo được ca đó xảy ra thật; ở đây mất một lời khai thật còn tệ hơn.
_RE_KHAI_BO_NHO = re.compile(
    r"(?:^|[,;(]|\bva\b|\bvoi\b|\bnoi dung la\b)\s*"
    rf"({_NHAN_HOAC})"
    r"\s*(?::|=|\bla\b)\s*"
    rf"(.+?)(?=$|[,;\n]|\s+(?:va|voi)\s+(?:{_NHAN_HOAC})\s*(?::|=|la\b))",
    re.IGNORECASE,
)


def rut_bo_nho(cau_hoi: str) -> list[dict]:
    """Dữ kiện người dùng TỰ KHAI trong câu vừa gõ → hàng cho `bo_nho_tai_khoan.ghi`.

    Tất định, 0 token (R5). Một khoá khai hai lần trong cùng câu giữ lần ĐẦU:
    lượt sau người ta khai lại thì `ghi` upsert, nên không cần đoán ý ở đây.

    Lọc giá trị bằng `vung_trong` — hàm ĐÃ CÓ, dùng chung với `_lay_truong`:
    một câu chép lại dòng biểu mẫu trắng ("Họ và tên: ………") không được thành
    một ký ức rỗng mà người dùng phải vào màn hình tài khoản xoá tay. KHÔNG lọc
    bằng `_vuong_luoi_chan`: lưới đó CHẶN dấu vết định danh, còn ở đây họ tên và
    mã sinh viên CHÍNH LÀ thứ phải giữ (quyết định D12-A).
    """
    goc = cau_hoi or ""
    ra: dict[str, dict] = {}
    for m in _RE_KHAI_BO_NHO.finditer(_bo_dau(goc)):
        khoa = _NHAN_BO_NHO[m.group(1).lower()]
        gia_tri = " ".join(goc[m.start(2):m.end(2)].split())
        if khoa in ra or not gia_tri or len(gia_tri) > GIA_TRI_TOI_DA or vung_trong(gia_tri):
            continue
        ra[khoa] = {"loai": BO_NHO_KHOA[khoa][0], "khoa": khoa, "gia_tri": gia_tri}
    return list(ra.values())


def khoa_duoc_hoi(cau_hoi: str, khoa: str) -> bool:
    """Lượt NÀY có hỏi tới khoá này không — phép gác duy nhất của R4.

    Khoá lạ (người dùng khai một điều bảng trên chưa lường; `bo_nho_tai_khoan`
    cố ý không dùng enum cho `khoa`) rơi về chính tên khoá viết rời: `noi_o` →
    "noi o". Nhận nhầm về phía KHÔNG hỏi là phía an toàn: mất một lần điền hộ,
    không mất quy tắc.
    """
    nhan = BO_NHO_KHOA.get(khoa, ("", (khoa.replace("_", " "),)))[1]
    s = _bo_dau(cau_hoi or "")
    return any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", s, re.IGNORECASE) for n in nhan)


def _khoi_bo_nho(nho: list[dict]) -> str:
    """Ký ức tài khoản → một khối của CHÍNH prompt này (R4), y như `# Bản thảo
    đang có`. Rỗng khi chưa nhớ gì: `.format()` nối một chuỗi rỗng và không lượt
    nào khác đổi một byte.

    Khối này là NGỮ CẢNH chứ không phải nguồn — lời dặn dưới đây nói thẳng điều
    đó, còn `lam_sach_van_ban(cam=…)` mới là chỗ cưỡng chế nó.
    """
    if not nho:
        return ""
    dong = "\n".join(f"- {r.get('nhan') or r.get('khoa')}: {r.get('gia_tri')}" for r in nho)
    return (
        "\n# Điều người hỏi đã cho tôi biết trước đây\n\n"
        f"{dong}\n\n"
        "Đây là điều NGƯỜI HỎI từng nói về chính họ ở lượt khác, không phải nội dung của lượt này. Chỉ "
        "được đưa một mục ở trên vào `van_ban` khi CHÍNH lượt này hỏi tới nó; lượt không hỏi thì để "
        "`[…]` như mọi chỗ chưa có dữ kiện. Vẫn được dùng để xưng hô và chọn văn phong cho đúng người.\n"
    )


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
                     "phep_tinh", "truong", "khac_biet", "dieu_khoan", "van_ban"],
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
                        # Không tài liệu (soạn tự do, Phase 14) thì không có
                        # nhãn nào để ép — `enum: []` là lược đồ không hợp lệ
                        # với provider. Quan sát gán nhãn lạ vẫn bị phía đọc
                        # loại (`theo_nhan.get(...)` trả None).
                        "tai_lieu": {"type": "string", **({"enum": nhan} if nhan else {})},
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
            # Điều khoản đưa sang đường pháp lý (S5). `cau_hoi_phap_ly` là câu
            # HỎI KHO, không phải một phán quyết trá hình: mô hình ở node này
            # không bao giờ được hỏi "điều khoản này có hợp pháp không" — nó chỉ
            # nói điều luật nào cần tra để người đọc tự thấy khác biệt (QT-1).
            "dieu_khoan": _mang("trich", "cau_hoi_phap_ly"),
            # Văn bản MỚI mô hình soạn từ tài liệu (S6). Rỗng ở mọi lượt khác
            # `tao_van_ban`/`sua_ban_thao` — `muc_dich` là thứ quyết định, không
            # phải sự có mặt của mảng này.
            #
            # `khoi` (Phase 8 R1, thay `noi_dung`/`bang` cố định của Phase 7):
            # một mục không còn "văn xuôi HOẶC bảng" mà là MẢNG khối theo ĐÚNG
            # thứ tự tài liệu — "câu dẫn, bảng, câu kết" là BA khối, không thể
            # nén vào hai trường cố định. Mỗi khối lại là `noi_dung`/`bang`
            # cùng quy ước rỗng-thay-vắng-mặt của Phase 7 (một trong hai rỗng).
            # `vung` (Phase 8 R2) mang `DonViVanBan.vung` qua tới đây, để một
            # mục lấy từ chân/đầu trang không lẫn vào thân bài.
            "van_ban": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tieu_de", "muc"],
                "properties": {
                    "tieu_de": {"type": "string"},
                    "muc": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["ten", "vung", "khoi"],
                            "properties": {
                                "ten": {"type": "string"},
                                "vung": {"type": "string", "enum": list(VUNG_HOP_LE)},
                                "khoi": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["noi_dung", "bang"],
                                        "properties": {
                                            "noi_dung": {"type": "string"},
                                            "bang": {
                                                "type": "array",
                                                "items": {"type": "array", "items": {"type": "string"}},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def _tu_khoa(s: str) -> set[str]:
    """Tập từ đã chuẩn hoá (cùng `normalize` với phép neo — một quy tắc chuẩn
    hoá cho cả hệ, xem docstring `neo_du_kien`). Bỏ từ một ký tự: chúng khớp ở
    khắp nơi nên không xếp hạng được gì."""
    return {t for t in normalize(s or "").split() if len(t) > 1}


def loc_don_vi(don_vi: list[DonViVanBan], cau_hoi: str) -> list[DonViVanBan]:
    """Phần tài liệu được gửi cho mô hình. Hàm THUẦN: không LLM, không I/O.

    Dưới `NGUONG_TRANG` trang VÀ dưới ngần ấy trang quy theo KÝ TỰ thì gửi cả
    tài liệu — cắt xén một tài liệu ngắn chỉ tạo ra rủi ro bỏ sót mà không tiết
    kiệm được gì đáng kể.

    Hai điều kiện chứ không một, và điều kiện thứ hai là điều kiện THẬT cho
    `.docx`: từ khi `doc_tai_lieu` đọc trang theo ngắt tệp KHAI
    (`_DemTrang`), `d.trang` của một `.docx` không còn là thước đo độ DÀY —
    một hợp đồng 40 trang không ấn Ctrl+Enter lần nào khai đúng 1 trang. Chỉ
    còn `d.trang` ở đây thì cả tài liệu ấy đi thẳng vào prompt. Số ký tự là
    thứ `KY_TU_MOI_TRANG` vẫn luôn đo (xem ghi chú tại hằng số đó), nên cổng
    này hỏi nó trực tiếp thay vì hỏi qua một số trang đã đổi nghĩa. PDF giữ
    nguyên hành vi cũ: ở đó `d.trang` là trang thật, và nó vẫn chặn trước.

    Trên ngưỡng: giữ `GIU_DAU` đơn vị ĐẦU (tiêu đề, các bên, số hiệu — thứ gần
    như mọi câu hỏi đều cần) cộng `GIU_THEO_CAU_HOI` đơn vị trùng từ khoá với
    câu hỏi nhiều nhất. Thứ tự đọc được GIỮ NGUYÊN: đánh số theo thứ tự trong
    tài liệu là cách duy nhất `[A-12]` còn nghĩa với người đọc lại sau này.

    Bỏ hẳn đơn vị RỖNG CHỮ trước khi tính (Phase 11 fix round 2) — `doc_tai_lieu`
    giờ giữ cả Ô BẢNG rỗng (để `_bang_theo_nhan` biết bảng có đủ hàng/cột thật,
    xem docstring `_duyet_than`), nhưng một ô rỗng không có gì để mô hình đọc
    hay trích — gửi nó vào prompt chỉ tốn token cho một dòng không chữ. Bảng
    thật vẫn dựng lại ĐỦ hàng vì `_khop_bang` đọc từ `t["don_vi"]` (TOÀN BỘ,
    không phải phần đã lọc gửi mô hình) — model không cần "biết" ô trống tồn
    tại để bảng vẫn đủ hàng sau khi khớp lại.
    """
    don_vi = [d for d in don_vi if d.noi_dung]
    if not don_vi:
        return []
    if (
        max((d.trang for d in don_vi), default=1) <= NGUONG_TRANG
        and sum(len(d.noi_dung) for d in don_vi) <= NGUONG_TRANG * KY_TU_MOI_TRANG
    ):
        return list(don_vi)
    tu = _tu_khoa(cau_hoi)
    theo_diem = sorted(don_vi[GIU_DAU:], key=lambda d: (-len(tu & _tu_khoa(d.noi_dung)), d.chi_so))
    giu = {d.chi_so for d in don_vi[:GIU_DAU]} | {d.chi_so for d in theo_diem[:GIU_THEO_CAU_HOI]}
    return [d for d in don_vi if d.chi_so in giu]


def _chia_theo_ky_tu(don_vi: list[DonViVanBan], ky_tu_moi_phan: int) -> list[list[DonViVanBan]]:
    """Chia `don_vi` (ĐÃ lọc, giữ thứ tự tài liệu) thành nhiều phần LIÊN TIẾP,
    mỗi phần tối đa `ky_tu_moi_phan` ký tự CỘNG DỒN (Phase 16 R2) — để một lượt
    gọi mô hình không phải dựng lại quá nhiều ký tự cùng lúc. Hàm THUẦN, không
    LLM, không I/O — cùng khuôn `loc_don_vi`.

    Một đơn vị DÀI HƠN cả ngưỡng vẫn được giữ NGUYÊN trong một phần riêng
    (không cắt giữa một đơn vị): hiếm khi xảy ra với văn bản Việt thật, và một
    phần vượt ngưỡng đôi chút còn an toàn hơn cắt giữa câu."""
    phan: list[list[DonViVanBan]] = []
    hien: list[DonViVanBan] = []
    dem = 0
    for d in don_vi:
        do_dai = len(d.noi_dung)
        if hien and dem + do_dai > ky_tu_moi_phan:
            phan.append(hien)
            hien, dem = [], 0
        hien.append(d)
        dem += do_dai
    if hien:
        phan.append(hien)
    return phan


def _phan_doan(i: int, so_phan: int, nhan: str, lo: int, hi: int, muc_dich: str | None) -> str:
    """Đoạn chèn vào prompt (`{phan_doan}`) khi một tài liệu ĐƠN bị chia nhiều
    lượt (Phase 16 R2). Rỗng khi `so_phan <= 1` — một lượt không chia không
    đổi một chữ nào trong prompt so với trước bản vá này.

    `muc_dich=None` là lượt ĐẦU (chưa biết mục đích, mô hình vẫn phải tự trả
    lời `muc_dich` như một lượt bình thường — chỉ phạm vi tài liệu THẤY được bị
    thu hẹp). `muc_dich` khác `None` là lượt TIẾP THEO: mục đích đã biết, lượt
    này CHỈ được tin ở `van_ban.muc` (xem `_hieu_theo_phan` — mọi mảng khác của
    một lượt tiếp theo bị bỏ qua ở tầng gộp, không dựa vào việc mô hình có nghe
    lời dặn "để rỗng" dưới đây hay không)."""
    if so_phan <= 1:
        return ""
    pham_vi = f"đơn vị {nhan}-{lo} đến {nhan}-{hi}"
    # Dòng trống HAI ĐẦU đoạn nằm ở đây, không nằm trong template: nhờ đó lượt
    # không chia (`phan_doan=""`) render ra đúng từng byte template trước Phase
    # 16, còn lượt chia vẫn có một dòng trống mỗi bên đoạn chèn.
    if muc_dich is None:
        return (
            f"\nTài liệu này dài hơn một lượt trả lời an toàn nên được chia {so_phan} phần liên "
            f"tiếp — LƯỢT NÀY chỉ thấy phần 1/{so_phan} ({pham_vi}). Nếu câu hỏi xin dựng/sửa văn "
            f"bản (`tao_van_ban`/`sua_ban_thao`): `van_ban.muc` CHỈ viết cho đúng phạm vi đang "
            f"thấy, ĐỪNG viết phần kết luận/chữ ký — phần sau còn tiếp tục và sẽ tự nối vào cuối "
            f"`muc` của lượt này. Mọi mục khác trả lời bình thường theo quy tắc bên dưới.\n"
        )
    la_cuoi = i == so_phan - 1
    ket_luan = "viết đủ phần kết luận/chữ ký nếu tài liệu có" if la_cuoi else "ĐỪNG viết phần kết luận/chữ ký"
    return (
        f"\nĐây là phần {i + 1}/{so_phan} của CÙNG một tài liệu ({pham_vi}); mục đích lượt này đã "
        f"xác định là `{muc_dich}` ở phần trước. CHỈ tiếp tục `van_ban.muc` cho đúng phạm vi đang "
        f"thấy, đúng thứ tự, không lặp lại mục đã dựng ở phần trước; đây "
        f"{'LÀ' if la_cuoi else 'CHƯA phải'} phần cuối — {ket_luan}. Mọi mảng khác (quan_sat, "
        f"suy_luan, can_du_kien, phep_tinh, truong, khac_biet, dieu_khoan) để RỖNG — đã trả lời ở "
        f"phần trước.\n"
    )


def _hieu_theo_phan(llm, model: str, cau_hoi: str, goi: list[dict], prompt_path: Path,
                    khoi_ban_thao: str = "", khoi_bo_nho: str = "") -> tuple[dict, Usage]:
    """Phase 16 R2 — dựng `van_ban.muc` qua NHIỀU lượt gọi liên tiếp cho một
    tài liệu ĐƠN quá dài để một lượt an toàn (`hieu_tai_lieu` đã kiểm điều kiện
    này — `len(goi) == 1` và vượt `NGUONG_PHAN_KY_TU` — trước khi gọi hàm này).

    Lượt ĐẦU vẫn trả lời ĐỦ mọi trường như một lượt bình thường (kể cả
    `muc_dich`) — chỉ phạm vi tài liệu THẤY được (`gui`) bị thu hẹp về phần
    1/N. Nếu `muc_dich` không thuộc `MUC_DICH_SOAN` (không xin dựng/sửa văn
    bản), DỪNG NGAY sau lượt đầu — không có gì để dựng thêm, và không lãng phí
    thêm lượt gọi nào cho một câu hỏi không xin dựng lại tài liệu.

    Mọi lượt SAU chỉ được tin ở `van_ban.muc` của nó — `quan_sat`/`phep_tinh`/
    `truong`/`khac_biet`/`dieu_khoan`/`suy_luan`/`can_du_kien`/`muc_dich`/
    `mo_ta`/`tra_loi_ngan` của các lượt đó bị BỎ QUA hoàn toàn ở đây (ĐÚNG
    RỖNG theo lời dặn trong `_phan_doan`, nhưng kết quả không phụ thuộc việc mô
    hình có tuân thủ hay không — `ra` gộp trả về vẫn chỉ mang các trường đó từ
    lượt đầu).

    `t["don_vi"]` (TOÀN BỘ tài liệu, dùng cho neo/khớp bảng ở `hieu_tai_lieu`
    sau khi hàm này trả về) KHÔNG đổi qua các lượt — chỉ `t["gui"]` (phần văn
    bản THẤY được trong MỘT lượt) bị thu hẹp. Vì vậy `_khop_bang`/
    `_bang_theo_nhan` (dùng `goi` gốc, không phải bản đã thu hẹp riêng cho mỗi
    lượt gọi ở đây) không bao giờ khớp một bảng với một tài liệu chưa đầy đủ —
    đúng ràng buộc round 3 của Phase 8 vẫn giữ nguyên dù tài liệu bị chia lượt.
    """
    t = goi[0]
    nhan_chu = t["nhan"]
    nhan = [g["nhan"] for g in goi]
    phan = _chia_theo_ky_tu(t["gui"], NGUONG_PHAN_KY_TU)
    so_phan = len(phan)
    tong: dict[str, int | float] = {"token_in": 0, "token_out": 0, "cost_usd": 0.0}

    def _cong(usage: Usage) -> None:
        for k, v in (("token_in", usage.token_in), ("token_out", usage.token_out), ("cost_usd", usage.cost_usd)):
            tong[k] += v

    def _goi_mot_phan(i: int, muc_dich_da_biet: str | None) -> dict:
        lo, hi = phan[i][0].chi_so, phan[i][-1].chi_so
        goi_phan = [{**t, "gui": phan[i]}, *goi[1:]]
        prompt = prompt_path.read_text(encoding="utf-8").format(
            cau_hoi=cau_hoi,
            tai_lieu=_khoi_tai_lieu(goi_phan),
            phan_doan=_phan_doan(i, so_phan, nhan_chu, lo, hi, muc_dich_da_biet),
            ban_thao_dang_co=khoi_ban_thao,
            bo_nho=khoi_bo_nho,
        )
        try:
            raw, usage = llm.chat(model, messages(prompt), json_schema=schema_hieu(nhan), max_tokens=TOI_DA_TOKEN_RA)
            _cong(usage)
            ra_i = json.loads(raw)
        except (TruncatedOutputError, json.JSONDecodeError) as e:
            # Chi phí đã trả THẬT cho OpenRouter dù lượt hỏng: các phần đã qua
            # (và phần JSON hỏng — `_cong` chạy trước `json.loads`) nằm trong
            # `tong`, phần bị cắt mang usage riêng trong lỗi. Gộp lại rồi gắn vào
            # lỗi để `hieu_tai_lieu` ghi đúng vào traces thay vì 0.
            u = getattr(e, "usage", None)
            if u is not None:
                _cong(u)
            e.usage = Usage(token_in=tong["token_in"], token_out=tong["token_out"], cost_usd=tong["cost_usd"])
            raise
        if not isinstance(ra_i, dict):
            raise TypeError(f"phản hồi phải là object, được {type(ra_i).__name__}")
        return ra_i

    ra = _goi_mot_phan(0, None)
    muc_dich = str(ra.get("muc_dich") or "hoi")
    if muc_dich in MUC_DICH_SOAN:
        muc_gop = list((ra.get("van_ban") or {}).get("muc") or [])
        for i in range(1, so_phan):
            ra_i = _goi_mot_phan(i, muc_dich)
            muc_gop.extend((ra_i.get("van_ban") or {}).get("muc") or [])
        ra["van_ban"] = {"tieu_de": (ra.get("van_ban") or {}).get("tieu_de") or "", "muc": muc_gop}

    return ra, Usage(token_in=tong["token_in"], token_out=tong["token_out"], cost_usd=tong["cost_usd"])


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


# Ký tự người ta kẻ một chỗ ĐỂ ĐIỀN. DẤU HIỆU của một chỗ như vậy
# (`RE_CHO_DIEN`: `…`, hoặc từ ba chấm / gạch ngang / gạch dưới liền) nằm ở
# `doc_tai_lieu`, dùng chung với bộ đọc chỗ trống của khuôn gốc.
_KY_TU_KE = "._–—-… \t"

# Chữ nói "chỗ này trống". Đo trên tập mẫu 2026-09-16: cấm chép dãy chấm thì mô
# hình viết thẳng "chưa điền" vào `gia_tri` — cùng một chỗ trống, một cách viết
# khác, và một bảng đầy dòng "chưa điền" vẫn trông như đã rút được năm trường.
# Prompt đã cấm; danh sách này cưỡng chế, 0 token.
_CUM_TRONG = frozenset({
    "chưa điền", "chưa ghi", "chưa có", "chưa xác định", "chưa rõ", "chưa nhập",
    "không có", "không rõ", "không xác định", "không đề cập", "không ghi",
    "để trống", "bỏ trống", "trống", "rỗng", "n/a", "na", "none", "null", "-",
})


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
    if not s.strip(_KY_TU_KE) or RE_CHO_DIEN.search(s):
        return True
    # So CẢ giá trị đã chuẩn hoá, không tìm từ trong câu: "Trống Đồng Group" là
    # một cái tên thật, và một phép tìm từ sẽ xoá mọi công ty có chữ ấy khỏi
    # bảng dữ kiện.
    return normalize(s).lower().strip("()[] ") in _CUM_TRONG


# Chỗ để trống của một bản thảo. CÙNG chuỗi mà `mucTuBanThao` (frontend) điền
# vào một mục chưa có nội dung — một quy ước hiển thị cho cả hai đầu (FR-011).
CHO_TRONG = "[…]"
# "Giá trị" trong một mục do mô hình viết: mọi cụm có chữ số (ngày, tiền, điểm,
# số hiệu, số Điều) và địa chỉ thư điện tử. Chữ thuần KHÔNG nằm ở đây: một cái
# tên bịa cũng sai, nhưng nó không tra ngược được bằng phép tra chuỗi, nên nó
# do prompt chặn (quy tắc 15) chứ không do hàm này.
_RE_GIA_TRI = re.compile(r"\S+@\S+|\d[\d.,/:\-]*\d|\d")
# Cụm số THUẦN — dạng duy nhất được phép so bằng GIÁ TRỊ thay vì bằng chuỗi.
# "01/10/2026" không vào đây: `tinh` sẽ đọc dấu `/` thành phép chia và một ngày
# tháng bịa sẽ khớp một con số có thật.
_RE_SO_THUAN = re.compile(r"\d[\d.,]*\d|\d")

# ── Thể thức hành chính của một văn bản KLAW TỰ SOẠN ────────────────────────
#
# Chỉ áp cho lượt soạn KHÔNG có tài liệu nào (`tu_soan` trong `lam_sach_van_ban`).
# Có tài liệu thì mọi sự thật trình bày đọc từ chính tệp (`_can_le_theo_dong`,
# `_chu_theo_dong`, `_gian_cach_theo_dong`) và quy ước ở đây KHÔNG chạy: một
# quy ước không bao giờ được ghi đè điều tệp nói.

# Chỗ điền của một BIỂU MẪU: dãy chấm để viết tay lên, đúng cách chính tài liệu
# nguồn vẽ nó (đo trên BM.M05: "Cơ quan/Đơn vị tiếp nhận: ……………………").
# `[…]` KHÔNG bị bỏ — nó đổi nghĩa và thu hẹp lại: sau bản vá này `[…]` chỉ còn
# do CHÍNH KLAW chèn (`_sach` gỡ một giá trị không tra ngược được, `_chan_bo_nho`
# từ chối điền một điều đã nhớ mà lượt này không hỏi tới), còn chỗ trống mà mô
# hình khai là "tôi chưa có dữ kiện" thì vẽ thành dòng chấm. Phân biệt đó rút
# được TRUNG THỰC từ thứ mô hình đã trả về, vì `_duong_dien` chạy TRƯỚC `_sach`:
# cái gì là `[…]` sau đó thì đúng là KLAW cố ý không điền.
DAU_DIEN = "…"
# Một dòng A4 theo lề NĐ 30/2020 (trái 30mm, phải 20mm ⇒ ~145mm) chứa khoảng
# ngần này ký tự thường ở Times New Roman 13. Đây là một NÚM CHỈNH, không phải
# một hằng số của bài toán — đo lại rồi sửa nếu đổi cỡ chữ hay lề.
_KY_TU_MOI_DONG = 70
# Bề rộng một "…" quy ra ký tự thường. Làm tròn LÊN (thật ra ~2,2) để sai số
# luôn đẩy về phía dòng NGẮN hơn: một dòng chấm hụt vài mm vẫn viết được, một
# dòng tràn thì xuống dòng và vỡ bố cục biểu mẫu.
_RONG_DAU_DIEN = 3
# Sàn/trần số dấu chấm. Sàn giữ cho một dòng chật vẫn còn thấy rõ là CHỖ ĐIỀN;
# trần giữ cho một chỗ điền đứng một mình không kéo dài hết cả dòng.
_DIEN_TOI_THIEU, _DIEN_TOI_DA = 3, 20


def _duong_dien(s: str) -> str:
    """`[…]` của MÔ HÌNH → dòng chấm dài vừa đủ, tính theo từng DÒNG.

    Độ dài chia theo chỗ còn lại của dòng: một dòng biểu mẫu "Họ và tên: […]"
    được một dòng chấm dài gần hết dòng, còn một câu văn xuôi có ba chỗ trống
    ("Tôi tên là […], sinh ngày […] tại […]") thì mỗi chỗ ngắn lại để cả câu
    vẫn nằm trên MỘT dòng. Một độ dài cố định không làm được cả hai: đủ dài cho
    ca đầu thì ca sau tràn sang ba dòng.
    """
    ra: list[str] = []
    for dong in s.split("\n"):
        n = dong.count(CHO_TRONG)
        if not n:
            ra.append(dong)
            continue
        con_lai = _KY_TU_MOI_DONG - (len(dong) - n * len(CHO_TRONG))
        dai = max(_DIEN_TOI_THIEU, min(_DIEN_TOI_DA, con_lai // (_RONG_DAU_DIEN * n)))
        ra.append(dong.replace(CHO_TRONG, DAU_DIEN * dai))
    return "\n".join(ra)


# Quốc hiệu. Hai cách gõ "HOÀ"/"HÒA" là HAI chuỗi NFC khác nhau (dấu trên `o`
# hay trên `a`), không phải một — `normalize` không gộp chúng, nên regex phải
# nhận cả hai.
_RE_QUOC_HIEU = re.compile(r"^cộng\s+h(?:òa|oà)\s+xã\s+hội\s+chủ\s+nghĩa\s+việt\s+nam$")
_RE_TIEU_NGU = re.compile(r"^độc\s+lập\s*[-–—]\s*tự\s+do\s*[-–—]\s*hạnh\s+phúc$")
# Dòng địa danh — ngày tháng. Neo ĐẦU dòng và giới hạn phần đứng trước dấu phẩy
# để một câu thân bài ("...đã nộp đơn ngày 05 tháng 3 năm 2026") không bị nhận
# nhầm: ở đó cụm ngày tháng nằm GIỮA câu, không mở đầu bằng "<địa danh>,".
_RE_DIA_DANH_NGAY = re.compile(r"^[^,]{1,40},\s*ngày\b.*\btháng\b.*\bnăm\b")
# Khối ký. Hai nhóm: chữ viết tắt quyền hạn người ký mà chính NĐ 30/2020 liệt
# kê, và vai người ký của một lá đơn.
#
# `Q.` (quyền) CỐ Ý không có trong danh sách dù Nghị định có kê: `q` cũng là
# một chữ cái đánh mục trong tiếng Việt (a, b, c... p, q, r), nên "q. Nội dung
# ..." là một mục con của thân bài chứ không phải một khối ký — và đẩy một mục
# con sang lề phải tệ hơn hẳn việc bỏ sót một chức danh quyền hiếm gặp trong
# đúng loại văn bản KLAW soạn từ đầu (đơn từ cá nhân). `tm`/`kt`/`tl`/`tuq`
# không trùng chữ cái đánh mục nào nên không vướng.
_RE_KHOI_KY = re.compile(
    r"^(?:tm|kt|tl|tuq)\.\s*\S"
    r"|^người\s+(?:làm\s+đơn|viết\s+đơn|nộp\s+đơn|khai|đề\s+nghị|yêu\s+cầu|cam\s+đoan)\b"
)


def _vai_the_thuc(dong: str, tieu_de: str) -> str | None:
    """Căn lề mà NĐ 30/2020/NĐ-CP đặt cho MỘT dòng, hoặc `None` khi Nghị định
    không nói gì về dòng ấy (⇒ nó là thân bài).

    Bốn luật, và chỉ bốn — mỗi luật là một câu Nghị định thật sự viết ra:

    - Tiêu ngữ "được canh giữa dưới Quốc hiệu" (Phụ lục I, mục II.1) ⇒ `giua`.
      Quốc hiệu đi cùng nó về `giua` theo quyết định của chủ sản phẩm: Nghị định
      đặt Quốc hiệu ở Ô SỐ 2 (nửa PHẢI đầu trang) chứ không nói căn lề của
      chính nó, mà bản thảo KLAW không có lưới hai cột để dựng lại ô ấy.
    - Tên loại và trích yếu nội dung "được đặt canh giữa" (mục II.5) ⇒ `giua`.
      Nhận ra bằng phép so ĐÚNG chữ với `van_ban.tieu_de`, không bằng "dòng in
      hoa thì căn giữa" — một tiêu đề MỤC in hoa ("PHẦN I. THÔNG TIN CHUNG")
      không phải tên loại văn bản và Nghị định không bảo căn giữa nó.
    - Nội dung văn bản "được canh đều cả hai lề" (mục II.6) ⇒ `deu`, tức mọi
      dòng không rơi vào ba luật kia.
    - Địa danh — ngày tháng (mục II.4) và khối ký (mục II.7, ô 7a/7b) ⇒ `phai`.
      Ở đây Nghị định nói VỊ TRÍ chứ không nói căn lề: địa danh "được đặt canh
      giữa dưới Quốc hiệu, Tiêu ngữ" và khối ký nằm ở ô 7a/7b — cả hai đều là
      "canh giữa BÊN TRONG một ô nằm ở nửa phải trang". Không có lưới hai cột
      thì `phai` là hình chiếu trung thực của vị trí ấy, và đó là quy ước chủ
      sản phẩm đã chọn.
    """
    if _RE_QUOC_HIEU.match(dong) or _RE_TIEU_NGU.match(dong) or (tieu_de and dong == tieu_de):
        return "giua"
    if _RE_DIA_DANH_NGAY.match(dong) or _RE_KHOI_KY.match(dong):
        return "phai"
    return None


def _the_thuc_hanh_chinh(noi_dung: str, tieu_de: str) -> str:
    """Căn lề thể thức của MỘT khối văn xuôi KLAW tự soạn.

    Một dòng NHẬN DIỆN ĐƯỢC quyết định cả khối, các dòng còn lại không phủ
    quyết: mô hình gộp "Người làm đơn" với "(Ký và ghi rõ họ tên)" vào cùng một
    khối, và dòng thứ hai không khớp luật nào — đòi mọi dòng đồng thuận thì cả
    khối ký rơi về thân bài. Hai dòng nhận ra HAI vai khác nhau thì mới bỏ cuộc
    (về `deu`): ở đó không có câu trả lời đúng, cùng lý lẽ `_can_le_khoi`.

    ponytail: quy ước không nhìn khối LIỀN TRƯỚC. Mô hình tách "(Ký và ghi rõ
    họ tên)" thành một khối RIÊNG thì khối đó về `deu` (vẽ như căn trái) trong
    khi "Người làm đơn" ngay trên nó đã sang phải. Chữa đúng cách cần trạng
    thái theo thứ tự khối; chưa làm vì hình dạng đo được là mô hình gộp hai
    dòng ấy vào CÙNG một khối. Nâng khi đo thấy ngược lại.
    """
    tap = {v for d in noi_dung.split("\n") if (v := _vai_the_thuc(_khong_hoa(d), tieu_de))}
    return tap.pop() if len(tap) == 1 else "deu"


def _co_trong_nguon(gia_tri: str, nguon: str, so_nguon: list) -> bool:
    """Giá trị này có THẬT trong nguồn của lượt không.

    Hai phép, theo thứ tự: chuỗi đã chuẩn hoá nằm trong nguồn; hoặc — chỉ với
    số thuần — cùng GIÁ TRỊ với một con số của nguồn, đọc bằng đúng
    `phep_tinh.tinh` (quy ước Việt: `20.000.000` và `20000000` là một số, `2,0`
    và `2.0` cũng vậy). Không có phép thứ ba: "gần giống" là chỗ một con số bịa
    đi lọt.
    """
    if normalize(gia_tri) in nguon:
        return True
    if not _RE_SO_THUAN.fullmatch(gia_tri):
        return False
    v = tinh(gia_tri)
    return v is not None and any(abs(v - s) <= SAI_SO for s in so_nguon)


def _khong_hoa(s: str) -> str:
    """`normalize()` rồi gập chữ hoa/thường — CHỈ cho phép `ten_that` so khớp
    (Phase 9 U1 fix round 1), KHÔNG áp cho `normalize()` dùng chung của cả
    file (neo trích dẫn, đối chiếu bảng): reviewer đo được model tái hiện một
    tiêu đề THẬT ("PHIẾU ĐÁNH GIÁ...", viết hoa toàn bộ trong nguồn, một quy
    ước biểu mẫu phổ biến) thành chữ hoa/thường thường ("Phiếu đánh giá..."),
    và so khớp CHỮ HOA/THƯỜNG NGHIÊM (như `normalize()` gốc) khiến nó bị coi
    là bịa — brief đã cảnh báo đúng ca này ("không được xoá oan một tiêu đề
    thật"). `casefold()` chỉ đổi CÁCH VIẾT hoa/thường, không đụng dấu tiếng
    Việt (`"Đ".casefold() == "đ"`, dấu vẫn còn nguyên) — khác hẳn việc bỏ dấu,
    nơi "Phạt tiền" và "phát tiền" là hai từ khác nghĩa
    (`verify_tier1.normalize` từ chối bỏ dấu vì lý do đó, và lý do đó vẫn giữ
    nguyên ở đây). Cố tình KHÔNG đi xa hơn thành so khớp mờ/paraphrase: một
    tên bịa "giống" một tiêu đề thật sẽ bị GIỮ oan nếu so mờ, và bịa mà vẫn
    hiện ra là đúng lỗi U1 phải sửa — chấp nhận đánh đổi hẹp (chỉ hoa/thường)
    hơn là rủi ro đó, cùng tinh thần "exact-text, not fuzzy" round 2 đã chọn
    cho `_khop_bang`."""
    return normalize(s).casefold()


def _nhan_that(goi: list[dict]) -> set[str]:
    """Chữ CHUẨN HOÁ (đã gập hoa/thường, `_khong_hoa`) của mọi đoạn văn (KHÔNG
    phải ô bảng) của tài liệu này — dùng để phân biệt TÊN MỤC là chữ THẬT của
    tài liệu hay do mô hình đặt ra để tổ chức bản thảo (Phase 9 U1, "quốc hiệu
    và tiêu ngữ" kiểu KLAW tự bịa không có trong nguồn). Không xét ô bảng: một
    tên mục trùng một nhãn cột ngắn ("TT", "Tổng") là trùng ngẫu nhiên, không
    phải một tiêu đề thật — cùng lý lẽ `_bang_cua` chỉ xét bảng, hàm này chỉ
    xét đoạn."""
    return {_khong_hoa(d.noi_dung) for t in goi for d in t["don_vi"] if d.bang is None and d.noi_dung}


def _vi_tri_theo_don_vi(goi: list[dict]) -> dict[str, int]:
    """Chữ CHUẨN HOÁ của một đơn vị nguồn (đoạn văn HAY ô bảng, khác rỗng) →
    chỉ số (`chi_so`) của nó trong tài liệu (Phase 11 fix round 2) — dùng để
    đặt một khối/tiêu đề vào ĐÚNG vị trí nguồn, thay vì một quy ước trình bày
    cố định (luôn ở đầu trang). Loại khỏi từ điển khi CÙNG một chữ xuất hiện
    ở NHIỀU vị trí (nhập nhằng, không định vị được) — cùng nguyên tắc
    `_can_le_theo_dong`.

    ponytail: chỉ xét tài liệu ĐẦU của lượt (`goi[0]`) — soạn lại một văn bản
    (mục đích duy nhất dùng hàm này) luôn dựa trên ĐÚNG một tài liệu nguồn,
    khác lượt so sánh hai tài liệu (không cần thứ tự liên tài liệu). Nới ra
    nhiều tài liệu nếu đo thấy cần.
    """
    if not goi:
        return {}
    theo_chu: dict[str, set[int]] = {}
    for d in goi[0]["don_vi"]:
        if d.noi_dung:
            theo_chu.setdefault(_khong_hoa(d.noi_dung), set()).add(d.chi_so)
    return {s: v.pop() for s, v in theo_chu.items() if len(v) == 1}


def _vi_tri_khoi(khoi: list[dict], vi_tri: dict[str, int]) -> int | None:
    """Vị trí NGUỒN của khối ĐẦU TIÊN của một mục — dòng đầu nếu là văn xuôi
    (một khối có thể gộp nhiều dòng nguồn bằng `\\n`), ô ĐẦU khác rỗng nếu là
    bảng. `None` khi không định vị được (mô hình paraphrase, không còn khớp
    nguyên văn) — mục đó không tham gia so sánh vị trí, giữ nguyên thứ tự mô
    hình đã đặt nó."""
    if not khoi:
        return None
    k = khoi[0]
    if k["bang"]:
        for hang in k["bang"]:
            for o in hang:
                if o and (vt := vi_tri.get(_khong_hoa(o))) is not None:
                    return vt
        return None
    dong = k["noi_dung"].split("\n") if k["noi_dung"] else []
    return vi_tri.get(_khong_hoa(dong[0])) if dong else None


def _bo_dong_trung_ten(khoi: list[dict], ten: str) -> list[dict]:
    """Bỏ dòng ĐẦU của khối văn xuôi ĐẦU TIÊN khi nó LẶP LẠI chính TÊN mục
    (Phase 11 fix round 2) — một mục `ten_that=True` đã in `ten` ra làm tiêu
    đề mục; nếu nội dung mục CŨNG mở đầu bằng đúng dòng đó (đo thật trên
    BM.M05: mục "Xác nhận của Cơ quan/Đơn vị" có khối đầu là chính hai chữ đó
    nối `\\n` với "(Ký và ghi rõ họ tên, chức vụ, đóng dấu)"), trang in ra
    cùng một câu hai lần — một lần làm tiêu đề, một lần làm dòng đầu thân bài.

    Chỉ bỏ ĐÚNG dòng trùng, giữ phần còn lại của khối; khối chỉ có mỗi dòng đó
    thì bỏ CẢ khối (mục không vô đề vì `ten` đã in ra rồi, không cần khối đó
    lặp lại để "giữ chỗ"). Không đụng khối THỨ HAI trở đi, và không đụng khối
    bảng — trùng tên chỉ có nghĩa với văn xuôi đứng NGAY sau tiêu đề."""
    if not khoi or khoi[0]["bang"] or not khoi[0]["noi_dung"]:
        return khoi
    dong = khoi[0]["noi_dung"].split("\n")
    if _khong_hoa(dong[0]) != _khong_hoa(ten):
        return khoi
    con_lai = "\n".join(dong[1:])
    if not con_lai:
        return khoi[1:]
    return [{**khoi[0], "noi_dung": con_lai}, *khoi[1:]]


def _can_le_theo_dong(goi: list[dict]) -> dict[str, str]:
    """Chữ CHUẨN HOÁ của một đơn vị nguồn → căn lề THẬT của nó, đọc thẳng từ
    `DonViVanBan.can_le` (Phase 9 U5) — cùng nguyên tắc "cấu trúc reader đã
    biết" của `_bang_theo_nhan`, áp cho căn lề thay vì ô bảng. Một dòng trùng
    chữ nhưng khác căn lề ở hai chỗ (hiếm — hai đoạn tình cờ cùng chữ) bị LOẠI
    khỏi từ điển: một dòng không xác định căn lề còn an toàn hơn một dòng gán
    nhầm.

    KỂ CẢ ô bảng (sửa 2026-09-18). Bản trước bỏ qua mọi đơn vị có `bang` — hệ
    quả đo được trên một đơn xin học lại: "Người làm đơn" nằm trong một Ô của
    bảng ký, nên nó không có mặt trong từ điển này, `_can_le_khoi` trượt và về
    mặc định `trai`, trong khi nguồn khai `w:jc="center"`. Cùng dòng ấy nếu
    nằm ngoài bảng thì lại ra đúng — một sự thật reader ĐÃ đọc được bị chặn
    lại đúng ở chỗ nó cần dùng. Ô bảng không trở thành khối văn xuôi ở đây:
    khi mô hình tái hiện một ô thành khối văn xuôi (bảng không khớp đủ để giữ
    nguyên cấu trúc), căn lề của chính ô đó LÀ câu trả lời đúng cho khối ấy.
    Ca trùng chữ giữa một ô và một đoạn vẫn rơi vào luật bất đồng ở trên.
    """
    theo_dong: dict[str, set[str]] = {}
    for t in goi:
        for d in t["don_vi"]:
            if not d.noi_dung:
                continue
            theo_dong.setdefault(normalize(d.noi_dung), set()).add(d.can_le)
    return {s: v.pop() for s, v in theo_dong.items() if len(v) == 1}


def _can_le_khoi(noi_dung: str, theo_dong: dict[str, str]) -> str:
    """Căn lề của MỘT khối văn xuôi (có thể gộp nhiều dòng nguồn bằng `\\n`,
    ví dụ quốc hiệu + tiêu ngữ) — mọi dòng khác rỗng khớp được phải ĐỒNG THUẬN
    một căn lề mới dùng nó. Không dòng nào khớp, hoặc khớp mà bất đồng (một
    khối trộn chữ từ hai chỗ căn khác nhau), thì về mặc định `trai` — an toàn:
    một khối chưa xác định vẫn đọc đúng thứ tự, chỉ không bị căn giữa oan."""
    tap = {theo_dong[s] for d in noi_dung.split("\n") if (s := normalize(d)) in theo_dong}
    return tap.pop() if len(tap) == 1 else "trai"


def _chu_theo_dong(goi: list[dict]) -> dict[str, tuple]:
    """Chữ NGUYÊN VĂN của một đơn vị nguồn → `DonViVanBan.dinh_dang` của nó.

    Khoá là chuỗi NGUYÊN VĂN, KHÔNG `normalize` như `_can_le_theo_dong`: định
    dạng ở đây là những khoảng `[dau, cuoi)` đo trên đúng chuỗi ấy, và
    `normalize` đổi độ dài (gộp khoảng trắng, bỏ dấu) nên mọi offset sẽ trỏ
    lệch sang ký tự khác. Một căn lề gán nhầm dòng chỉ lệch một dòng; một
    khoảng định dạng gán nhầm chuỗi in đậm nửa từ.

    Đổi lại, phép tra này CHẶT hơn: mô hình gõ lại một dòng lệch một dấu cách
    là dòng đó mất định dạng, không phải nhận nhầm. Đúng phía nên sai — bản
    thảo vẫn đọc được, chỉ không đậm.

    Dòng trùng chữ mà khác định dạng ở hai chỗ bị LOẠI, cùng luật
    `_can_le_theo_dong`: không xác định còn an toàn hơn gán nhầm.
    """
    theo: dict[str, set[tuple]] = {}
    for t in goi:
        for d in t["don_vi"]:
            if d.noi_dung and d.dinh_dang:
                theo.setdefault(d.noi_dung, set()).add(d.dinh_dang)
    return {s: v.pop() for s, v in theo.items() if len(v) == 1}


def _manh_chu(rs: tuple[DinhDangChu, ...], lech: int = 0) -> list[dict]:
    """`DonViVanBan.dinh_dang` → khoảng ĐÁNG VẼ, dịch đi `lech` ký tự.

    Chỉ giữ khoảng thật sự NÓI gì và thật sự phủ ký tự nào: một run rỗng chữ
    là một điều tệp khai — `eval.run_trung_thuc` chấm nó — nhưng trên màn
    hình nó không có gì để vẽ, và đưa xuống render chỉ tốn JSON.

    Dùng chung cho CẢ hai đường xuống render (`_chu_khoi` cho văn xuôi,
    `_bang_theo_nhan` cho ô bảng): cùng một phép lọc, cùng một bộ khoá, nên
    `chuHopLe` phía giao diện chỉ phải biết MỘT hình dạng.
    """
    return [
        {
            "dau": r.dau + lech,
            "cuoi": r.cuoi + lech,
            "dam": r.dam,
            "nghieng": r.nghieng,
            "gach": r.gach,
            "co": r.co,
            "phong": r.phong,
        }
        for r in rs
        if r.cuoi > r.dau and (r.dam or r.nghieng or r.gach or r.co or r.phong)
    ]


def _chu_khoi(noi_dung: str, theo_chu: dict[str, tuple]) -> list[dict]:
    """Định dạng chữ của MỘT khối văn xuôi — dịch khoảng của từng dòng nguồn
    về offset trong khối (khối có thể gộp nhiều dòng bằng `\\n`, ví dụ quốc
    hiệu + tiêu ngữ).

    Dòng không tra được không đóng góp khoảng nào: chỗ đó render giữ chữ
    thường, đúng luật "không suy diễn thêm ngoài những gì tệp nói".
    """
    ra: list[dict] = []
    lech = 0
    for dong in noi_dung.split("\n"):
        ra.extend(_manh_chu(theo_chu.get(dong, ()), lech))
        lech += len(dong) + 1
    return ra


def _gian_cach_theo_dong(goi: list[dict]) -> dict[str, tuple]:
    """Chữ NGUYÊN VĂN của một đơn vị nguồn → `DonViVanBan.gian_cach` của nó.

    Khoá NGUYÊN VĂN, cùng lý do `_chu_theo_dong`: `GianCach.tab` là offset đo
    trên đúng chuỗi ấy, và `normalize` đổi độ dài nên mọi mốc tab sẽ trỏ lệch
    sang ký tự khác — một đường dẫn "……" vẽ từ giữa một từ.

    Dòng trùng chữ mà khác giãn cách ở hai chỗ bị LOẠI: không xác định vẫn an
    toàn hơn gán nhầm nhịp trang của chỗ này cho chỗ kia.
    """
    theo: dict[str, set[tuple]] = {}
    for t in goi:
        for d in t["don_vi"]:
            if d.noi_dung and d.gian_cach:
                theo.setdefault(d.noi_dung, set()).add(d.gian_cach)
    return {s: v.pop() for s, v in theo.items() if len(v) == 1}


def _manh_tab(g: GianCach, lech: int = 0) -> list[dict]:
    """`GianCach` → những chỗ tab VẼ ĐƯỢC, dịch đi `lech` ký tự.

    Ghép tab thứ n với mốc thứ n. Đây là một TRẦN có chủ ý, không phải luật
    của Word: Word nhảy tới mốc đầu tiên nằm SAU vị trí con trỏ hiện tại, mà
    vị trí ấy chỉ biết được sau khi đã đo chữ — bộ đọc Python không đo được
    chữ, và để ba nơi vẽ tự đo là ba lần cài lại cùng một luật, đúng thứ trôi
    dạt mà "một nguồn, ba nơi dùng" tồn tại để chặn.
    Đo trên tám biểu mẫu thật: 51/55 đoạn có tab chỉ có ĐÚNG một tab, và cả
    45 đoạn có đường dẫn (`leader`) đều thuộc nhóm đó — nên phép ghép này
    đúng ở mọi chỗ nó vẽ ra thứ gì.
    Tab thừa (nhiều tab hơn mốc) KHÔNG nhận mốc nào và không được vẽ: giữ
    nguyên hành vi trước bản vá, thay vì đoán một mốc mặc định.

    ponytail: trần "tab thứ n → mốc thứ n". Nâng lên luật thật của Word khi
    ba nơi vẽ cùng đo được vị trí con trỏ trên cùng một hệ quy chiếu — việc
    đó cần `w:pgMar` (mục `le_trang`, còn CHƯA CÀI) để quy đổi twip sang toạ
    độ màn hình cho đúng.
    """
    return [
        {"o": o + lech, "val": m.val, "pos": m.pos, "leader": m.leader}
        for o, m in zip(g.tab, g.moc, strict=False)
        if m.pos > 0
    ]


def _gian_cach_khoi(noi_dung: str, theo_gc: dict[str, tuple]) -> dict:
    """Giãn cách/thụt lề/tab của MỘT khối văn xuôi — `{}` khi không tra được.

    Giãn cách và thụt lề là thuộc tính của CẢ khối (một `<p>` trên màn hình,
    một `w:p` trong tệp), nên chỉ nhận khi mọi dòng tra được ĐỒNG THUẬN —
    cùng luật `_can_le_khoi`. Một khối gộp hai dòng nguồn giãn cách khác nhau
    thì không có câu trả lời đúng, và chọn bừa dòng đầu là đoán.

    Mốc tab thì ngược lại, KHÔNG cần đồng thuận: mỗi mốc gắn với một offset
    trong chính khối, nên hai dòng nguồn góp hai chỗ tab khác nhau vẫn không
    mâu thuẫn — chỉ dịch offset theo dòng, đúng như `_chu_khoi` làm.

    Đoạn có `w:pPr` chỉ khai một thứ không vẽ được (ví dụ `w:beforeAutospacing`
    một mình) ra `{}`: không có gì để vẽ thì không thêm khoá nào, và mọi phía
    đọc vốn đã mặc định "không khai".
    """
    tab: list[dict] = []
    tap: set[tuple] = set()
    lech = 0
    for dong in noi_dung.split("\n"):
        for g in theo_gc.get(dong, ()):
            tab.extend(_manh_tab(g, lech))
            tap.add((g.truoc, g.sau, g.dong, g.luat_dong, g.trai, g.phai, g.dau_dong, g.treo))
        lech += len(dong) + 1

    ra: dict = {}
    if len(tap) == 1:
        truoc, sau, dong, luat_dong, trai, phai, dau_dong, treo = tap.pop()
        if truoc or sau or dong or trai or phai or dau_dong or treo:
            ra = {
                "truoc": truoc,
                "sau": sau,
                "dong": dong,
                "luat_dong": luat_dong,
                "trai": trai,
                "phai": phai,
                "dau_dong": dau_dong,
                "treo": treo,
            }
    if tab:
        ra["tab"] = tab
    return ra


def _hang_gon(
    cot: dict[int, str],
    nhip_cot: dict[int, int],
    can_le_cot: dict[int, str],
    chu_cot: dict[int, list[dict]],
    so_cot: int,
) -> tuple[list[str], list[int], list[str], list[list[dict]]]:
    """Một hàng bảng THẬT, GỌN — chỉ giữ ô có chữ cộng thêm Ô ĐỆM cho khoảng
    TRỐNG thật (Phase 11 R6), không phải một mảng phẳng một-ô-một-cột.

    `cot`/`nhip_cot` khoá theo cột LƯỚI THẬT (đã cộng dồn `w:gridSpan`, xem
    `doc_tai_lieu._duyet_than`). Đi từ trái sang phải: một cột lưới còn trống
    TRƯỚC ô tiếp theo (ô gộp ở hàng khác chiếm chỗ, hoặc chính hàng này chỉ
    có vài ô đầu — ca đo được trên "Tuần 1(từ…)" của BM.ĐT.18.05) được lấp
    bằng đúng MỘT ô đệm rỗng mang nhịp bằng khoảng trống đó — không phải một
    ô rỗng cho MỖI cột trống, để một ô gộp thật (như "Tổng") vẫn hiện ĐÚNG
    nhịp của nó, không bị tách lại thành nhiều ô 1-cột.

    Trả thêm căn lề TỪNG Ô (`w:pPr/w:jc` của đoạn đầu ô, `doc_tai_lieu` đã
    đọc sẵn vào `DonViVanBan.can_le`) và định dạng chữ TỪNG Ô (`w:rPr`, đọc
    `DonViVanBan.dinh_dang`): một ô ĐỆM không đến từ ô nguồn nào nên nhận
    `trai` và không khoảng định dạng nào — mặc định của chính `DonViVanBan`,
    không phải một giá trị thứ ba nghĩa là "không biết".
    """
    hang: list[str] = []
    nhip: list[int] = []
    can_le: list[str] = []
    chu: list[list[dict]] = []
    chay = 0
    for c in sorted(cot):
        if c > chay:
            hang.append("")
            nhip.append(c - chay)
            can_le.append("trai")
            chu.append([])
        hang.append(cot[c])
        n = nhip_cot.get(c, 1)
        nhip.append(n)
        can_le.append(can_le_cot.get(c, "trai"))
        chu.append(chu_cot.get(c, []))
        chay = c + n
    if chay < so_cot:
        hang.append("")
        nhip.append(so_cot - chay)
        can_le.append("trai")
        chu.append([])
    return hang, nhip, can_le, chu


_CSS_CANH = ("top", "right", "bottom", "left")


def _vien_o_bang(
    vien_canh: tuple[tuple[str, str, str], ...],
    o_canh: dict[tuple[int, int], tuple[tuple[str, str, str], ...]],
    nhip: list[list[int]],
    so_cot: int,
) -> list[list[str]] | None:
    """Viền của TỪNG Ô sau khi ghép, cùng hình dạng `hang` — `None` khi bảng
    không có chi tiết theo cạnh nào để ghép.

    Mỗi ô ra MỘT chuỗi `"trên|phải|dưới|trái"`, mỗi phần là `"w:val/w:sz"`
    NGUYÊN VĂN nguồn (phần rỗng = cạnh đó không có nét). Thứ tự trên/phải/
    dưới/trái là thứ tự của chính CSS, để ba nơi vẽ đọc cùng một dãy mà không
    nơi nào phải nhớ một quy ước riêng.

    Đây là chỗ DUY NHẤT biết cả hình dạng bảng lẫn khai báo từng cạnh, nên
    cũng là chỗ duy nhất ghép được luật của Word: cạnh `w:tcBorders` của
    chính ô ĐÈ; không khai thì ô lấy cạnh BẢNG tương ứng với CHỖ nó đứng —
    `top` của hàng đầu là `top` của bảng, của hàng giữa là `insideH`; `left`
    của cột đầu là `left`, của cột giữa là `insideV`. Một ô đứng một mình
    không biết nó có phải hàng cuối không, nên phép ghép này không thể nằm ở
    `doc_tai_lieu`.

    FAIL CLOSED CẢ BẢNG khi một `w:sz` khai giá trị không phải số: nửa bảng vẽ
    theo cạnh nguồn, nửa kia vẽ theo một bề dày đoán bừa là tệ hơn hẳn cả bảng
    lùi về nét đều của `vien` — đúng luật `_gian_cach_doan` đã theo cho một
    `w:spacing` hỏng.
    """
    moi_canh = (*vien_canh, *(c for canh in o_canh.values() for c in canh))
    if not moi_canh:
        return None
    if any(sz and not sz.isdigit() for _, _, sz in moi_canh):
        return None
    bang = {canh: f"{val}/{sz}" for canh, val, sz in vien_canh}
    so_hang = len(nhip)
    ra: list[list[str]] = []
    for h, nhip_hang in enumerate(nhip):
        cot = 0
        dong: list[str] = []
        for n in nhip_hang:
            rieng = {canh: f"{val}/{sz}" for canh, val, sz in o_canh.get((h, cot), ())}
            thua_ke = {
                "top": "top" if h == 0 else "insideH",
                "bottom": "bottom" if h == so_hang - 1 else "insideH",
                "left": "left" if cot == 0 else "insideV",
                "right": "right" if cot + n >= so_cot else "insideV",
            }
            dong.append("|".join(rieng.get(c, bang.get(thua_ke[c], "")) for c in _CSS_CANH))
            cot += n
        ra.append(dong)
    return ra


def _bang_theo_nhan(goi: list[dict]) -> dict[str, dict]:
    """Mọi bảng THẬT của lượt này, dựng lại 0 token thẳng từ `don_vi` — khoá
    "A0"/"B2" (nhãn tài liệu + số bảng, 0-based, đúng số `_vi_tri` đã hiện cho
    mô hình). Không đoán ô nào ở đâu: lưới hàng×cột đến thẳng từ `(bảng, hàng,
    cột)` mà `doc_tai_lieu` đã gán cho từng ô khi đọc file — ĐÂY là "cấu trúc
    reader đã biết" mà review round 2 chỉ ra không nên bắt mô hình đoán lại.
    Dùng `t["don_vi"]` (TOÀN BỘ), không phải `t["gui"]` (phần đã lọc gửi mô
    hình) — cùng lý lẽ neo trích dẫn: phép lọc đầu vào là chuyện chi phí,
    không phải chuyện bằng chứng.

    Trả về, mỗi khoá bảng, MỘT bộ cùng nguồn gốc thay vì chỉ `hang`: `nhip`
    (số cột mỗi ô CHIẾM, cùng hình dạng `hang`, đọc thẳng `bang_nhip` —
    RENDER dùng trực tiếp, không suy đoán lại từ số ô như `coSpanHang` cũ),
    `ti_le` (% mỗi cột lưới, đọc `bang_ti_le`, rỗng khi bảng không khai
    lưới), `vien` (bảng có vẽ viền không, đọc `bang_vien`), `vien_o` (viền
    TỪNG CẠNH của từng ô sau khi ghép bảng+ô+vị trí, cùng hình dạng `hang` —
    xem `_vien_o_bang`; RỖNG khi bảng không có chi tiết theo cạnh, và ba nơi
    vẽ khi đó lùi về nét đều của `vien`), `cao` (chiều cao khai báo mỗi HÀNG
    theo twip, đọc `bang_cao`, `0` khi hàng không khai), `cao_luat`
    (`@w:hRule` mỗi hàng, đọc `bang_cao_luat`, `""` khi không khai),
    `can_le_o` (căn lề TỪNG Ô, cùng hình dạng `hang`, đọc `can_le`) và
    `chu_o` (định dạng chữ TỪNG Ô — dãy khoảng `[dau, cuoi)` trên CHÍNH chữ
    của ô, cùng hình dạng `hang`, đọc `dinh_dang`). Không đẻ ra một hàm/một
    lượt duyệt `don_vi` thứ hai cho từng trường — tất cả đến từ ĐÚNG một vòng
    lặp này (xem R3 trong brief: "một chỗ carry cả bộ, không phải năm chỗ
    chép từng trường").

    `chu_o` KHÔNG cần tra ngược theo chữ như `_chu_theo_dong` phải làm cho
    văn xuôi: chữ mỗi ô ở đây đến THẲNG từ `d.noi_dung` của chính đơn vị mang
    `d.dinh_dang`, nên khoảng và chuỗi đo trên cùng một chuỗi theo cấu trúc,
    không phải theo một phép khớp có thể sai. Ô của một bảng mô hình TỰ GÕ
    không đi qua đây (xem `_khoi_sach`) nên vẫn hiện chữ thường — đúng luật
    "chữ viết lại thì mất định dạng".
    """
    ra: dict[str, dict] = {}
    for t in goi:
        theo_bang: dict[int, dict[int, dict[int, str]]] = {}
        nhip_bang: dict[int, dict[int, dict[int, int]]] = {}
        can_le_bang: dict[int, dict[int, dict[int, str]]] = {}
        chu_bang: dict[int, dict[int, dict[int, list[dict]]]] = {}
        ti_le_bang: dict[int, tuple[int, ...]] = {}
        vien_bang: dict[int, bool] = {}
        cao_bang: dict[int, dict[int, int]] = {}
        cot_toi_da: dict[int, int] = {}
        vien_canh_bang: dict[int, tuple[tuple[str, str, str], ...]] = {}
        o_canh_bang: dict[int, dict[tuple[int, int], tuple[tuple[str, str, str], ...]]] = {}
        cao_luat_bang: dict[int, dict[int, str]] = {}
        for d in t["don_vi"]:
            if d.bang is None:
                continue
            b, h, c = d.bang
            theo_bang.setdefault(b, {}).setdefault(h, {})[c] = d.noi_dung
            nhip_bang.setdefault(b, {}).setdefault(h, {})[c] = d.bang_nhip
            can_le_bang.setdefault(b, {}).setdefault(h, {})[c] = d.can_le
            chu_bang.setdefault(b, {}).setdefault(h, {})[c] = _manh_chu(d.dinh_dang)
            cot_toi_da[b] = max(cot_toi_da.get(b, 0), c + d.bang_nhip)
            if d.bang_ti_le and b not in ti_le_bang:
                ti_le_bang[b] = d.bang_ti_le
            # Viền là sự thật của cả BẢNG (`doc_tai_lieu._vien_bang` chép cùng
            # một giá trị lên mọi ô); chiều cao là sự thật của từng HÀNG. Lấy
            # `max` thay vì ô đầu gặp: mọi ô cùng hàng mang cùng số, nên `max`
            # chỉ là cách viết không phụ thuộc thứ tự duyệt.
            vien_bang[b] = vien_bang.get(b, False) or d.bang_vien
            cao_hang = cao_bang.setdefault(b, {})
            cao_hang[h] = max(cao_hang.get(h, 0), d.bang_cao)
            # Viền từng cạnh CẤP BẢNG cũng chép trên mọi ô (như `bang_ti_le`),
            # nên ô đầu gặp là đủ; viền cấp Ô thì khoá theo (hàng, cột LƯỚI) vì
            # nó là sự thật riêng của chính ô đó. `bang_cao_luat` giống
            # `bang_cao`: một giá trị cho cả hàng.
            if d.bang_vien_canh and b not in vien_canh_bang:
                vien_canh_bang[b] = d.bang_vien_canh
            if d.o_vien_canh:
                o_canh_bang.setdefault(b, {})[(h, c)] = d.o_vien_canh
            if d.bang_cao_luat:
                cao_luat_bang.setdefault(b, {})[h] = d.bang_cao_luat
        for b, theo_hang in theo_bang.items():
            ti_le = ti_le_bang.get(b, ())
            so_cot = len(ti_le) or cot_toi_da.get(b, 0)
            hang: list[list[str]] = []
            nhip: list[list[int]] = []
            can_le_o: list[list[str]] = []
            chu_o: list[list[list[dict]]] = []
            cao: list[int] = []
            for h in range(max(theo_hang) + 1):
                h_hang, h_nhip, h_can_le, h_chu = _hang_gon(
                    theo_hang.get(h, {}),
                    nhip_bang.get(b, {}).get(h, {}),
                    can_le_bang.get(b, {}).get(h, {}),
                    chu_bang.get(b, {}).get(h, {}),
                    so_cot,
                )
                hang.append(h_hang)
                nhip.append(h_nhip)
                can_le_o.append(h_can_le)
                chu_o.append(h_chu)
                cao.append(cao_bang.get(b, {}).get(h, 0))
            vien_o = _vien_o_bang(
                vien_canh_bang.get(b, ()), o_canh_bang.get(b, {}), nhip, so_cot
            )
            ra[f"{t['nhan']}{b}"] = {
                "hang": hang,
                "nhip": nhip,
                "ti_le": list(ti_le),
                "vien": vien_bang.get(b, True),
                "vien_o": vien_o or [],
                "cao": cao,
                "cao_luat": [cao_luat_bang.get(b, {}).get(h, "") for h in range(len(hang))],
                "can_le_o": can_le_o,
                "chu_o": chu_o,
            }
    return ra


def _o_theo_bang(goi: list[dict]) -> dict[str, list[str]]:
    """Với mỗi bảng thật, DÃY chữ các ô KHÁC RỖNG của nó theo đúng thứ tự đọc
    (hàng rồi cột, thứ tự `t["don_vi"]` đã có sẵn) — dùng để khớp một khối văn
    xuôi gộp NHIỀU dòng nguồn bằng `\\n` với TOÀN BỘ một bảng cùng lúc (Phase
    11 R7, xem `_bang_cua_nhieu_dong`)."""
    ra: dict[str, list[str]] = {}
    for t in goi:
        for d in t["don_vi"]:
            if d.bang is not None and d.noi_dung:
                ra.setdefault(f"{t['nhan']}{d.bang[0]}", []).append(d.noi_dung)
    return ra


def _khop_day_dong(dong: list[str], o: list[str]) -> bool:
    """`dong` (các dòng của MỘT khối, tách bằng `\\n`) có ghép lại ĐÚNG VÀ ĐỦ
    thành dãy ô thật `o` không — không dòng nào thừa, không ô nào thiếu.

    Một Ô có thể trải trên NHIỀU dòng nguồn (một ô gộp nhiều đoạn văn nối
    bằng dấu CÁCH, xem `doc_tai_lieu._duyet_than`), nên phép ghép CỘNG DỒN
    từng dòng cho tới khi khớp NGUYÊN VĂN ô hiện tại rồi mới sang ô kế —
    không phải so từng dòng với từng ô một-một."""
    li = 0
    for muc_tieu in o:
        s = normalize(muc_tieu)
        if not s:
            continue
        gop = ""
        khop = False
        while li < len(dong):
            gop = f"{gop} {dong[li]}".strip() if gop else dong[li]
            li += 1
            if normalize(gop) == s:
                khop = True
                break
        if not khop:
            return False
    return li == len(dong)


def _bang_cua_nhieu_dong(noi_dung: str, o_theo_bang: dict[str, list[str]]) -> str | None:
    """Một khối văn xuôi GỘP NHIỀU DÒNG (`\\n`) có tái hiện ĐÚNG VÀ ĐỦ mọi ô
    khác rỗng của MỘT bảng thật không (Phase 11 R7) — bổ sung cho `_bang_cua`
    (chỉ khớp khi CẢ khối bằng NGUYÊN một ô).

    Đo trên form thật (BM.ĐT.18.05): letterhead 2 cột, mỗi ô 2 đoạn văn nối
    bằng DẤU CÁCH (`"TRƯỜNG ĐẠI HỌC PHENIKAA TRƯỜNG CÔNG NGHỆ THÔNG TIN"`).
    Mô hình gộp cả 4 dòng nguồn (2 ô × 2 đoạn) thành MỘT khối, nối bằng `\\n`
    — khớp nguyên văn CẢ khối vào MỘT ô (`_bang_cua`) không bao giờ đúng (khối
    dài hơn bất kỳ ô nào), nên `_khop_bang` bỏ qua, letterhead ở lại dạng văn
    xuôi. Khớp GHÉP DÒNG vào TOÀN BỘ dãy ô của bảng (`_khop_day_dong`) thì
    đúng: cộng dồn dòng cho tới khi ra nguyên ô 1, rồi ô 2, không dòng nào
    thừa. Cùng luật round 3 ("mọi ô khác rỗng phải khớp, không lọc bỏ rồi xét
    phần còn lại"), áp cho HƯỚNG NGƯỢC LẠI: khớp phải TRỌN VẸN cả hai phía —
    không ô nào của bảng bị bỏ sót, không dòng nào của khối bị thừa ra ngoài.
    Một khối chỉ khớp MỘT PHẦN của bảng, hay khớp được nhiều hơn một bảng,
    không được cứu — `_khop_day_dong` (không thừa/không thiếu) cộng với đếm
    SỐ BẢNG khớp (giữ >1 thì nhập nhằng) đã ép đủ cả hai."""
    dong = [d for d in (x.strip() for x in noi_dung.split("\n")) if d]
    if len(dong) < 2:
        return None
    khoa = [k for k, o in o_theo_bang.items() if o and _khop_day_dong(dong, o)]
    return khoa[0] if len(khoa) == 1 else None


def _khop_bang(
    khoi: list[dict], goi: list[dict], bang_theo_nhan: dict[str, dict], nguon_muc: list[int] | None = None,
) -> tuple[list[dict], list[int]]:
    """Khớp lại nội dung mô hình viết (văn xuôi HAY bảng tự gõ) với đúng bảng
    THẬT của tài liệu — không đợi mô hình tự khai đúng, tự đối chiếu.

    **Review round 2** — đo được hai chế độ hỏng CÙNG một gốc ("mô hình đoán
    lại cấu trúc reader đã biết"): (BM.M05, thật) một letterhead 2 cột bị mô
    hình xé thành 3 khối văn xuôi RIÊNG, bỏ sót một ô; (BM.ĐT.18.11, thật) một
    hàng gộp bị đệm dư `["Tổng","10","",""]`. Cả hai đều SỬA được bằng cách
    khớp NGUYÊN VĂN từng khối với chính đơn vị-trong-bảng của tài liệu
    (`normalize`, cùng phép neo `neo_du_kien` dùng cho mọi trích dẫn khác) rồi
    THAY bằng bảng THẬT khi khớp — không sửa chữ, không đoán, chỉ đối chiếu.

    Một khối BẢNG (mô hình tự gõ `bang`) được thay khi MỌI ô khác rỗng của nó
    khớp riêng một bảng DUY NHẤT — mô hình đã tự khai "đây là bảng", chỉ có
    thể đúng hay sai bảng nào, không cần ngưỡng. **Review round 3 [HIGH],
    "MỌI ô" phải là luật THẬT, không phải lời hứa suông:** một bản trước chỉ
    xét các ô ĐÃ khớp (`- {None}` loại ô không khớp ra khỏi phép kiểm, thay vì
    đòi mọi ô phải khớp), nên MỘT ô dùng chung tình cờ khớp (ví dụ "TT" hay
    một nhãn cột lặp lại) đã đủ để cả khối bị THAY — kể cả khi người dùng xin
    sửa bảng ("chỉ giữ lại hàng Tổng") và mô hình làm đúng, giữ lại đúng MỘT ô
    gốc: khối đó vẫn bị ghi đè về nguyên bảng cũ, âm thầm huỷ sửa đổi thật.
    Đây là chiều nguy hiểm hơn chiều đã disclose ở round 2 (bỏ lỡ một lần cứu
    còn hơn ghi đè một lần sửa) — sửa bằng cách đòi ĐỦ: một ô không khớp được
    (kể cả khớp nhập nhằng nhiều bảng) chặn NGAY, không lọc bỏ nó rồi xét phần
    còn lại. Một khối VĂN XUÔI cần ÍT NHẤT HAI khối LIỀN KỀ cùng khớp một bảng
    mới gộp — một câu trùng khớp một ô không đủ để kết luận cả đoạn đó là một
    bảng bị xé lẻ (nhánh này KHÔNG đổi, review round 3 xác nhận đã đúng).

    Bảng nào mô hình soạn MỚI (không có trong tài liệu, ví dụ mục lục thiết bị
    tự liệt kê) — hay bảng mô hình đã SỬA THẬT, giữ lại một vài ô gốc thôi —
    không còn khớp MỌI ô → giữ NGUYÊN như mô hình viết. Chức năng "mô hình tự
    soạn/sửa bảng" không bị mất vì phép khớp lại này.

    **Phase 11 R1/R6/R7** — bảng thay vào (`bang_theo_nhan[chi]`) giờ mang cả
    `ti_le` (tỉ lệ % mỗi cột lưới) và `nhip` (số cột mỗi ô CHIẾM, đặt cùng
    chỗ mọi cột), cả hai đọc thẳng từ `w:tblGrid`/`w:gridSpan` qua
    `doc_tai_lieu`/`_bang_theo_nhan` — không suy đoán lại từ số ô một hàng
    có, như `coSpanHang` phía render từng phải làm khi chỉ có `bang`. Thêm
    `_bang_cua_nhieu_dong`: một khối văn xuôi GỘP NHIỀU dòng nguồn bằng `\\n`
    (một letterhead 2 cột, mỗi ô 2 đoạn văn, mô hình gộp cả 4 dòng thành MỘT
    khối) mà `_bang_cua` không khớp được (khối dài hơn một ô) nay được thử
    khớp GHÉP DÒNG vào TOÀN BỘ một bảng — khớp đủ TỰ THÂN (biến `manh`) nên
    được thay dù chỉ MỘT khối, không cần đợi ≥2 khối liền kề.

    **Phase 11 fix round 1** — `khoi` giờ có thể là TOÀN VĂN BẢN đã ghép PHẲNG
    từ NHIỀU mục (không chỉ khối của MỘT mục), và `nguon_muc` (song song với
    `khoi`) ghi mục GỐC của từng khối — trả về thêm mảng này (đã cập nhật theo
    khối RA) để người gọi (`lam_sach_van_ban`) phân phối lại đúng mục. Lý do:
    đo được thật trên BM.M05 (draft `b0c76517…`) — mô hình xé letterhead 2 cột
    thành HAI MỤC RIÊNG, mỗi mục đúng MỘT khối (`"Quốc hiệu và tiêu ngữ"` và
    `"Thông tin cơ quan tiếp nhận"`), không phải hai khối trong CÙNG một mục
    như test `test_khop_bang_cuu_letterhead_bi_xe_thanh_van_xuoi` mô phỏng.
    Gọi hàm này CHỈ trong phạm vi một mục thì không bao giờ thấy đủ ≥2 khối để
    gộp — ranh giới MỤC là một ranh giới TRÌNH BÀY của mô hình, không phải một
    ranh giới bằng chứng: hai khối liền kề nhau trong TOÀN VĂN BẢN, dù ở hai
    mục khác nhau, vẫn là "hai khối liền kề cùng khớp một bảng" đúng nghĩa
    docstring này đã định nghĩa từ round 2. Không đổi luật gộp (vẫn ≥2 khối
    liền kề hoặc `manh`) — chỉ đổi PHẠM VI khối được xét liền kề với nhau,
    không mở rộng thành "khớp ở bất kỳ đâu trong tài liệu" (vẫn đòi liền kề
    thật, để không gộp nhầm hai đoạn văn ở hai nơi xa nhau tình cờ cùng chữ)."""

    def _bang_cua(chu: str) -> str | None:
        """Chữ này khớp NGUYÊN VĂN ô nào của bảng thật — trả khoá bảng khi mọi
        ô khớp cùng quy về MỘT bảng, dù khớp nhiều Ô (Phase 9 U2 [diagnostic]).

        Đo trên form thật (BM.ĐT.18.11, `.sdd/phase-9-brief.md` U2): cột "Điểm
        tối đa" của bảng chấm lặp lại "2,0" ba lần (ba tiêu chí đều 2 điểm).
        Bản trước của hàm này đòi khớp ĐÚNG MỘT Ô trên toàn tài liệu
        (`len(khop) == 1` trên danh sách CẶP (nhãn, đơn vị)) — "2,0" khớp ba ô
        CÙNG một bảng thì `len(khop) == 3`, hàm trả `None`, và `_bang_khop_het`
        (đòi MỌI ô khác rỗng khớp) thấy một ô "không khớp được" dù nó khớp thật
        những ba lần — cả khối bị bỏ, hàng "Tổng" đệm dư không được cứu. Cái
        hàm này THẬT SỰ cần khẳng định là "chữ này định danh được MỘT BẢNG",
        không phải "MỘT Ô" — vị trí ô không quan trọng vì `_khop_bang` thay
        NGUYÊN bảng thật, không ghép theo từng ô. Gộp theo KHOÁ BẢNG (nhãn +
        chỉ số bảng) trước khi đếm sửa đúng lỗ hổng đó: nhiều ô cùng bảng vẫn
        là MỘT bảng; khớp ở hai bảng khác nhau thì vẫn nhập nhằng, vẫn `None`
        như cũ — không nới lỏng luật round 3 ("mọi ô phải khớp"), chỉ sửa
        đúng nghĩa "khớp" mà luật đó đã hứa.
        """
        s = normalize(chu)
        if not s:
            return None
        khoa = {f"{t['nhan']}{d.bang[0]}" for t in goi for d in t["don_vi"] if d.bang is not None and normalize(d.noi_dung) == s}
        return khoa.pop() if len(khoa) == 1 else None

    def _bang_khop_het(hang_o: list[list[str]]) -> str | None:
        """MỌI ô khác rỗng của bảng này khớp riêng ĐÚNG MỘT bảng thật — một ô
        không khớp được (rỗng kết quả `_bang_cua`, dù vì không có trong tài
        liệu hay vì khớp nhập nhằng nhiều chỗ) chặn NGAY, không bị lọc bỏ rồi
        xét phần còn lại (review round 3 [HIGH])."""
        o_khac_rong = [o for hang in hang_o for o in hang if o]
        if not o_khac_rong:
            return None
        b = {_bang_cua(o) for o in o_khac_rong}
        return b.pop() if len(b) == 1 and None not in b else None

    o_theo_bang = _o_theo_bang(goi)
    khoa: list[str | None] = []
    # `manh` — khớp đủ TỰ THÂN để thay dù chỉ MỘT khối (Phase 11 R7): khối
    # bảng (`_bang_khop_het`, mọi ô khớp) và khối văn xuôi ghép trọn một bảng
    # (`_bang_cua_nhieu_dong`) đều đã tự chứng minh đủ bằng chứng một mình —
    # không cần đợi ≥2 khối liền kề như một câu trùng khớp MỘT ô lẻ.
    manh: list[bool] = []
    for k in khoi:
        if k["bang"]:
            khoa.append(_bang_khop_het(k["bang"]))
            manh.append(True)
            continue
        khoi_nhieu_dong = _bang_cua_nhieu_dong(k["noi_dung"], o_theo_bang) if "\n" in k["noi_dung"] else None
        if khoi_nhieu_dong is not None:
            khoa.append(khoi_nhieu_dong)
            manh.append(True)
        else:
            khoa.append(_bang_cua(k["noi_dung"]) if k["noi_dung"] else None)
            manh.append(False)

    nguon = nguon_muc if nguon_muc is not None else list(range(len(khoi)))
    ra: list[dict] = []
    ra_nguon: list[int] = []
    i = 0
    while i < len(khoi):
        chi = khoa[i]
        if chi is None or chi not in bang_theo_nhan:
            ra.append(khoi[i])
            ra_nguon.append(nguon[i])
            i += 1
            continue
        j = i
        while j < len(khoi) and khoa[j] == chi:
            j += 1
        if manh[i] or (j - i) >= 2:
            bang = bang_theo_nhan[chi]
            ra.append({
                "noi_dung": "",
                "bang": bang["hang"],
                "nhip": bang["nhip"],
                "ti_le": bang["ti_le"],
                "can_le": "trai",
                "vien": bang["vien"],
                "cao": bang["cao"],
                "can_le_o": bang["can_le_o"],
                # `vien_o`/`cao_luat` cùng luật `chu_o` ngay dưới: chỉ CÓ MẶT
                # khi nguồn nói một điều gì đó. Một bảng không có chi tiết theo
                # cạnh giữ NGUYÊN hình dạng khối cũ, và mọi phía đọc vốn đã
                # mặc định rỗng — nét đều của `vien` chạy y như trước bản vá.
                **({"vien_o": bang["vien_o"]} if bang["vien_o"] else {}),
                **({"cao_luat": bang["cao_luat"]} if any(bang["cao_luat"]) else {}),
                # `chu_o` chỉ CÓ MẶT khi có ít nhất một ô mang định dạng —
                # cùng luật `chu` của khối văn xuôi: một bảng không định dạng
                # giữ NGUYÊN hình dạng khối cũ, và mọi phía đọc
                # (`khoiMotHopLe`) vốn đã mặc định rỗng.
                **({"chu_o": bang["chu_o"]} if any(any(h) for h in bang["chu_o"]) else {}),
            })
            # Khối gộp gán về mục ĐẦU TIÊN của nhóm — khi nhóm bắc qua ranh
            # giới mục (fix round 1), mục còn lại rỗng và bị bỏ ở tầng gọi,
            # đúng luật "mục không còn khối nào" đã có sẵn.
            ra_nguon.append(nguon[i])
        else:
            ra.extend(khoi[i:j])
            ra_nguon.extend(nguon[i:j])
        i = j
    return ra, ra_nguon


def lam_sach_van_ban(van_ban: dict, nguon: str, goi: list[dict] | None = None,
                     cam: list[str] | None = None) -> tuple[dict, dict]:
    """Bỏ khỏi văn bản mô hình vừa soạn mọi giá trị KHÔNG có trong `nguon`.
    Hàm THUẦN, 0 token — `nguon` là chữ của tài liệu cộng lời người hỏi.

    **`cam` (Phase 12 part B, R4) — giá trị KLAW đã NHỚ mà lượt này không hỏi
    tới.** `_RE_GIA_TRI` chỉ nhìn thấy cụm CÓ CHỮ SỐ và địa chỉ thư, nên một
    cái TÊN đã nhớ đi thẳng qua phép làm sạch ở trên mà không vướng gì — đúng
    chế độ hỏng mà hợp đồng "nhớ, không tự điền" cấm. `cam` là lưới riêng cho
    đúng ca đó: chỉ chặn ở CHỖ ĐIỀN (cả ô/cả dòng, hoặc phần sau "Nhãn:" —
    xem `_chan_bo_nho`), thay bằng `[…]`, và đếm riêng để đo được mô hình tự
    điền bao nhiêu lần. Chỉ dữ kiện CÁ NHÂN vào đây; thói quen soạn thảo thì
    không (xem chỗ dựng `bo_nho_cam` trong `hieu_tai_lieu`).

    **Thay bằng `[…]`, không bỏ mục.** Một con số bịa là một LỖ trong một câu
    còn lại đúng, và `[…]` chính là chỗ trống mà cả bản thảo checklist lẫn giao
    diện (`mucTuBanThao`) đã dùng cho "chưa có dữ kiện": người đọc thấy ngay
    phải điền gì. Bỏ cả mục thì cái mất đi là một ĐỀ MỤC người ta đã xin, và nó
    biến mất không dấu vết — đúng thứ FR-011 cấm (không bao giờ đoán, nhưng
    cũng không im lặng).

    **Một ngoại lệ, và nó fail closed:** mục nào SAU KHI làm sạch vẫn vướng
    `bo_nho._vuong_luoi_chan` (số Điều/Khoản/Điểm, số hiệu văn bản, dấu vết
    định danh cá nhân) thì bị BỎ và đếm riêng. Ở đó không còn là một lỗ để chừa
    trống: một bản thảo mang mức kiểm `tong_quat` mà dẫn số Điều trông như đã
    qua rà soát pháp lý, và một số điện thoại/email lọt vào bản thảo là dữ liệu
    cá nhân đi ra khỏi hội thoại của nó.

    **Phase 8 R1:** một mục không còn `noi_dung`/`bang` cố định mà là `khoi` —
    mảng khối theo đúng thứ tự tài liệu, mỗi khối lại là `noi_dung`/`bang` như
    Phase 7 (một trong hai rỗng). Làm sạch từng khối bằng ĐÚNG `_sach`/
    `_bang_sach` cũ; một khối rỗng cả hai sau khi sạch bị bỏ (không phân biệt
    được là văn xuôi hay bảng nữa), còn cả mục thì bị bỏ khi KHÔNG CÒN khối
    nào — tương đương "không `noi_dung` không `bang`" của Phase 7, chỉ đổi chỗ
    kiểm từ một cặp trường sang một mảng.

    **Phase 8 fix round 2:** `goi` (tài liệu của lượt này, mỗi phần tử mang
    `don_vi`) là NGUỒN của `_khop_bang` — sau khi làm sạch từng khối, khớp lại
    với bảng THẬT của tài liệu và thay vào khi khớp (xem `_khop_bang`). `None`
    (mặc định, giữ cho test cũ không phải sửa) tắt hẳn bước này — không bảng
    nào được thay, đúng hành vi trước round 2.

    ponytail: lưới chặn đo cả MỤC chứ không định vị được từng cụm, nên một số
    Điều mà CHÍNH tài liệu của người hỏi có cũng làm mất mục đó. Nâng cấp khi
    đo thấy nó cắn thật: tách `_RE_DIEU`/`_RE_DINH_DANH` của `bo_nho` thành
    phép thay theo cụm dùng chung, thay vì một hàm bool.
    """
    nguon = normalize(nguon or "")
    so_nguon = [v for m in _RE_SO_THUAN.findall(nguon) if (v := tinh(m)) is not None]
    bang_theo_nhan = _bang_theo_nhan(goi or [])
    # Phase 9 U1/U5 — hai lưới đối chiếu 0 token khác, cùng nguồn `goi`: tên
    # mục có phải chữ THẬT của tài liệu (`_nhan_that`), và mỗi dòng của tài
    # liệu căn lề gì (`_can_le_theo_dong`, `_can_le_khoi` dùng ở `_khoi_sach`).
    nhan_that = _nhan_that(goi or [])
    theo_dong = _can_le_theo_dong(goi or [])
    # Lượt soạn KHÔNG có tài liệu nào — điều kiện duy nhất bật thể thức hành
    # chính và dòng chấm. Gác bằng `goi` chứ không bằng `theo_dong` rỗng: `goi`
    # là câu hỏi thật ("lượt này có nguồn nào không"), còn một từ điển rỗng chỉ
    # là hệ quả. Gác như vậy thì đường TÁI HIỆN không đổi một byte nào.
    tu_soan = not goi
    # Tên loại văn bản để so với từng dòng (`_vai_the_thuc`). Lấy bản THÔ: bản
    # đã `_sach` chỉ có sau vòng làm sạch mục, và gọi `_sach` thêm lần nữa ở đây
    # sẽ cộng trùng `gia_tri_lam_sach`.
    tieu_de_kh = _khong_hoa(str((van_ban or {}).get("tieu_de") or "").strip()) if tu_soan else ""
    # Định dạng chữ (`w:rPr`, quyết định 2026-09-18) — lưới thứ ba cùng nguồn
    # `goi`, tra theo chữ NGUYÊN VĂN chứ không chuẩn hoá, xem `_chu_theo_dong`.
    theo_chu = _chu_theo_dong(goi or [])
    # Giãn cách/thụt lề/mốc tab (`w:spacing`/`w:ind`/`w:tabs`) — lưới thứ tư
    # cùng nguồn `goi`, cũng tra theo chữ NGUYÊN VĂN, xem `_gian_cach_theo_dong`.
    theo_gc = _gian_cach_theo_dong(goi or [])
    # Lề trang (`w:sectPr/w:pgMar`) — KHÔNG phải một lưới tra theo dòng như bốn
    # cái trên: nó là sự thật của cả TỆP, một bộ số duy nhất, và mọi đơn vị đều
    # chở đúng nó (xem `DonViVanBan.le_trang`). Lấy ở đơn vị đầu đọc được rồi
    # gắn lên TỪNG mục vì `clauses` là kênh duy nhất đi ra giao diện — bản thảo
    # không có chỗ nào cất một sự thật cấp tài liệu, và `XemTruocA4` đọc lại ở
    # mục đầu.
    le_trang = next(
        (list(d.le_trang) for t in (goi or []) for d in t["don_vi"] if d.le_trang), []
    )
    # Ảnh đã tách (quyết định 2026-09-18) đi ĐÚNG đường lề trang: cũng là sự
    # thật cấp TÀI LIỆU, cũng chép trên mọi đơn vị, cũng lấy ở đơn vị đầu đọc
    # được. Không tra theo dòng như `chu`/`gian_cach` được: một logo letterhead
    # nằm trong một `w:p` KHÔNG CÓ CHỮ, nên không có chuỗi nguyên văn nào để
    # làm khoá.
    #
    # Ra giao diện là một ĐƯỜNG DẪN, không phải bytes: nhúng data URI vào đây
    # sẽ đẩy con dấu của bên thứ ba vào mọi phản hồi bản thảo và mọi khung SSE.
    # `routes_tai_lieu.anh` mới là chỗ phát bytes, và nó kiểm chủ sở hữu.
    anh = next(
        (
            [
                {
                    "url": f"/tai-lieu/{t['id']}/anh/{d_anh.phan.rsplit('/', 1)[-1]}",
                    "rong": d_anh.rong,
                    "cao": d_anh.cao,
                    "vung": d_anh.vung,
                    "thu_tu": d_anh.thu_tu,
                }
                for d_anh in d.anh
            ]
            for t in (goi or [])
            for d in t["don_vi"]
            # `t.get("id")`: một gói KHÔNG có id việc đọc (mã gọi cũ, kịch bản
            # kiểm) không dựng được đường dẫn ảnh nào — bỏ hẳn thay vì sinh một
            # `/tai-lieu//anh/...` chắc chắn 404.
            if d.anh and t.get("id")
        ),
        [],
    )
    dem = {"muc_lam_sach": 0, "gia_tri_lam_sach": 0, "muc_bo": 0, "bo_nho_khong_dien": 0}
    # Giá trị đã nhớ mà CÓ trong `nguon` thì KHÔNG cấm: ở đó nó tới bằng chính
    # lời người hỏi lượt này (hay tài liệu, hay bản thảo đang có), không bằng ký
    # ức — cấm nó là xoá đúng thứ người dùng vừa gõ ra. `_nguon_soan` đã cộng
    # sẵn giá trị của những khoá lượt này HỎI TỚI, nên một lượt xin điền cũng rơi
    # vào đúng nhánh "có trong nguồn" này.
    #
    # Fix round 1 (review MED) — gập hoa/thường CẢ HAI PHÍA. `normalize` cố ý
    # KHÔNG casefold (nó là phép so khớp trích dẫn, xem docstring của nó), nên
    # phép loại trừ cũ so chữ NGHIÊM trong khi phép chặn lại `IGNORECASE`: người
    # dùng gõ lại chính giá trị của mình bằng cách viết khác ("nguyễn văn thử")
    # thì không khớp `nguon`, vẫn nằm trong `cam`, và bị xoá thành `[…]` — xoá
    # đúng thứ họ vừa viết. `_khong_hoa` là hàm ĐÃ CÓ cho đúng việc này.
    nguon_kh = _khong_hoa(nguon)
    cam_bo = {_khong_hoa(v) for v in (cam or []) if v and _khong_hoa(v) not in nguon_kh}

    def _chan_bo_nho(s: str) -> str:
        """Gỡ giá trị đã nhớ ra khỏi CHỖ ĐIỀN, không ra khỏi văn xuôi.

        Fix round 1 (review HIGH). Bản trước so khớp `\\b<giá trị>\\b` ở BẤT KỲ
        đâu trong tên mục, văn xuôi và từng ô bảng — tức nó xoá cả tiếng Việt
        bình thường. Đo được trên chính `lam_sach_van_ban`: `nganh = "Luật"`
        biến "tuân thủ Bộ luật Lao động" thành "tuân thủ Bộ […] Lao động" (trên
        một sản phẩm PHÁP LUẬT, ở mọi bản thảo); `noi_thuc_tap = "Hà Nội"` phá
        dòng địa danh-ngày tháng chuẩn "Hà Nội, ngày … tháng …"; `ho_ten =
        "Thử"` cắt nát "Thời gian thử việc".

        Thứ R4 cấm là KLAW tự ĐIỀN một ô trống, nên lưới chỉ nhìn đúng hình
        dạng một ô đã điền: cả ô bảng / cả dòng là giá trị, hoặc phần đứng sau
        "Nhãn:" của dòng ấy. Một giá trị lọt giữa câu là chữ của câu, không
        phải một ô được điền hộ — và giữ oan một chữ giữa câu rẻ hơn nhiều so
        với xoá oan chữ của người dùng ở mọi bản thảo.

        ponytail: trần đã biết — mô hình viết giá trị giữa một câu ("Tôi là
        Nguyễn Văn Thử, xin trình bày") thì lọt. Siết lại khi đo được là mô
        hình thật sự tự điền theo hình dạng đó, chứ không phải bằng một phép
        so khớp rộng hơn đã chứng minh là cắn nhầm nhiều hơn cắn đúng.
        """
        if not cam_bo:
            return s
        ra_dong: list[str] = []
        for dong in s.split("\n"):
            le = dong[: len(dong) - len(dong.lstrip())]
            than = dong.strip()
            if than and _khong_hoa(than) in cam_bo:
                dem["bo_nho_khong_dien"] += 1
                ra_dong.append(le + CHO_TRONG)
                continue
            # Cắt ở dấu hai chấm ĐẦU TIÊN: nhãn của một dòng biểu mẫu đứng
            # trước nó, còn mọi dấu hai chấm sau đó thuộc về giá trị ("Giờ làm:
            # 8:00").
            nhan, dau, sau = dong.partition(":")
            if dau and sau.strip() and _khong_hoa(sau.strip()) in cam_bo:
                dem["bo_nho_khong_dien"] += 1
                dong = nhan + ":" + sau[: len(sau) - len(sau.lstrip())] + CHO_TRONG
            ra_dong.append(dong)
        return "\n".join(ra_dong)

    def _sach(s: str) -> str:
        s = _chan_bo_nho(s)

        def _thay(m: re.Match) -> str:
            if _co_trong_nguon(m.group(0), nguon, so_nguon):
                return m.group(0)
            dem["gia_tri_lam_sach"] += 1
            return CHO_TRONG

        return _RE_GIA_TRI.sub(_thay, s)

    def _bang_sach(bang_tho) -> list[list[str]]:
        """`bang` thô → hàng×ô đã làm sạch, đúng phép `_sach` như `ten`/
        `noi_dung`: một ô cũng là một giá trị có thể bịa (Phase 7 R1). Hàng nào
        không phải mảng thì bị BỎ (không nổ cả mục vì một hàng sai hình dạng).

        Hàng NGẮN hơn hàng tiêu đề (Phase 8 R4, ô gộp trong tài liệu nguồn) đi
        qua NGUYÊN — không đệm, không cắt.

        **Review round 1 [CRITICAL], KHÔNG cắt ô rỗng ở cuối hàng — đã thử và
        bị bỏ.** Một bản trước của hàm này cắt các ô rỗng Ở CUỐI, để sửa ca đo
        được trên BM.ĐT.18.11 (mô hình trả `["Tổng", "10", "", ""]` cho một
        hàng nguồn chỉ có 2 ô gộp). Nhưng phép cắt đó không phân biệt được
        "hàng bị mô hình đệm dư" với "hàng ĐỦ cột, ô cuối trống vì bản thân
        tài liệu để trống ô đó" — một phiếu ĐANG CHỜ ĐIỀN có đúng hình dạng
        thứ hai ở khắp nơi (ví dụ một cột "Điểm đánh giá" toàn ô trống). Cắt
        nhầm biến một hàng ĐỦ cột, không hề gộp, thành một hàng NGẮN — rồi
        `coSpanHang` (phía đọc) gộp nhầm ô liền trước sang cột kế, cùng lỗi
        R4 cấm nhưng do CHÍNH bản vá gây ra, không phải do mô hình. Không có
        thông tin nào ở tầng này (một hàng, đứng riêng) đủ để phân biệt hai
        ca — độ dài hàng tiêu đề không nói cho biết ô cuối trống vì gộp hay
        vì để trống. Chấp nhận: hàng ngắn do mô hình đệm dư mà KHÔNG cắt được
        vẫn hiện sai cột — một hạn chế của việc dựa vào lời dặn prompt, không
        phải một lỗi có thể sửa an toàn ở tầng làm sạch này."""
        if not isinstance(bang_tho, list):
            return []
        return [[_sach(str(o).strip()) for o in hang] for hang in bang_tho if isinstance(hang, list)]

    def _khoi_sach(khoi_tho) -> list[dict]:
        """`khoi` thô (Phase 8 R1) → khối đã làm sạch, bỏ khối nào RỖNG CẢ HAI
        sau khi sạch — một khối trắng không còn phân biệt được là văn xuôi hay
        bảng, cùng luật "không noi_dung không bang" Phase 7 áp cho cả mục.

        **Review round 1 [IMPORTANT]:** rule 15 XIN mô hình để mỗi khối MỘT
        trong hai (`noi_dung` HOẶC `bang`), nhưng schema strict không ép được
        điều đó — một khối vẫn có thể tới đây với CẢ HAI khác rỗng (mô hình
        chú thích một bảng ngay trong cùng một khối chẳng hạn). Đo được: hai
        phía đọc dữ liệu này (`dung_ban_thao_tong_quat._khoi_thanh_van_ban` và
        `xuat-tep.ts::khoiMotHopLe`) từng tự chọn ưu tiên NGƯỢC NHAU cho ca
        này — một bên giữ `noi_dung` bỏ `bang`, bên kia ngược lại — tức luật
        "một khối một loại" chưa từng được ép ở đâu, chỉ được TIN. TÁCH một
        khối như vậy thành HAI khối sạch, văn xuôi TRƯỚC rồi bảng (đúng thứ tự
        Phase 7 R1 fix round 1 đã dùng ở cấp MỤC cho chính ca này) — cả hai
        nội dung đều được giữ, và không phía đọc nào phải tự đoán ưu tiên nữa,
        vì tới tay nó đã là hai khối một-loại-mỗi-khối rồi."""
        if not isinstance(khoi_tho, list):
            return []
        ra = []
        for k in khoi_tho:
            if not isinstance(k, dict):
                continue
            tho = str(k.get("noi_dung") or "").strip()
            # Chỗ trống của MÔ HÌNH thành dòng chấm — chỉ ở văn bản tự soạn, và
            # chỉ TRƯỚC `_sach`, để `[…]` còn lại sau đó đúng là chỗ CHÍNH KLAW
            # cố ý không điền (xem `_duong_dien`). Tái hiện một tài liệu thì
            # không đụng tới: ở đó dãy chấm là của chính tệp và đã đi qua
            # nguyên văn từ trước.
            noi_dung = _sach(_duong_dien(tho) if tu_soan else tho)
            bang = _bang_sach(k.get("bang"))
            if noi_dung:
                # `can_le` (Phase 9 U5) — căn lề THẬT của khối này, đối chiếu
                # từng dòng với `theo_dong`; bảng giữ `trai` làm chỗ trống
                # (không đọc), căn lề trong bảng là chuyện của TỪNG ô, ngoài
                # phạm vi field này (xem cảnh báo ở brief).
                #
                # KHÔNG có tài liệu nào thì không có gì để đối chiếu và mọi khối
                # rơi về `trai` — đó là dòng "Người làm đơn" nằm sát lề trái mà
                # chủ sản phẩm đo được. Ca ấy (và CHỈ ca ấy) dùng thể thức hành
                # chính NĐ 30/2020 thay cho phép tra nguồn rỗng.
                ra.append({
                    "noi_dung": noi_dung,
                    "bang": [],
                    "can_le": (
                        _the_thuc_hanh_chinh(noi_dung, tieu_de_kh)
                        if tu_soan
                        else _can_le_khoi(noi_dung, theo_dong)
                    ),
                    "nhip": [],
                    "ti_le": [],
                    "vien": True,
                    "cao": [],
                    "can_le_o": [],
                    # `chu` chỉ CÓ MẶT khi tra được định dạng: một khối không
                    # định dạng giữ nguyên hình dạng khối cũ, và mọi phía đọc
                    # (`khoiMotHopLe` phía giao diện) vốn đã mặc định rỗng.
                    **({"chu": chu} if (chu := _chu_khoi(noi_dung, theo_chu)) else {}),
                    # `gian_cach` cùng luật `chu`: chỉ CÓ MẶT khi tra được,
                    # nên một khối không giãn cách giữ nguyên hình dạng cũ.
                    **({"gian_cach": gc} if (gc := _gian_cach_khoi(noi_dung, theo_gc)) else {}),
                })
            if bang:
                # `nhip`/`ti_le`/`cao`/`can_le_o` rỗng: bảng mô hình tự gõ
                # không có lưới nguồn nào để đọc — `coSpanHang` (frontend) vẫn
                # suy đoán từ số ô như trước Phase 11, đúng "quy tắc cho ca
                # không có lưới khai báo" R6 yêu cầu giữ lại. `vien: True` vì
                # một bảng mô hình tự soạn là bảng dữ liệu (nó gõ ra hàng/cột
                # để ĐỌC như bảng), không phải khối xếp cột của một biểu mẫu —
                # và đó cũng là hành vi trước bản vá viền, không đổi ngầm.
                ra.append({
                    "noi_dung": "",
                    "bang": bang,
                    "can_le": "trai",
                    "nhip": [],
                    "ti_le": [],
                    "vien": True,
                    "cao": [],
                    "can_le_o": [],
                })
        return ra

    # Mục (Phase 11 fix round 1) — làm sạch TỪNG mục trước (`_sach`/
    # `_khoi_sach`, như cũ), nhưng CHƯA khớp bảng vội: một bảng bị mô hình xé
    # ra thành nhiều MỤC riêng (không chỉ nhiều khối trong CÙNG một mục, xem
    # `_khop_bang`) chỉ cứu được khi phép khớp thấy TOÀN VĂN BẢN, không phải
    # từng mục một. `dem_delta` giữ đúng phần `gia_tri_lam_sach` DO CHÍNH mục
    # này gây ra, để bỏ mục sau này (khối rỗng hoặc dính lưới chặn) chỉ lùi
    # lại phần của NÓ, không đụng phần các mục khác đã cộng dồn xen giữa.
    muc_sach: list[dict] = []
    for o in (van_ban or {}).get("muc") or []:
        if not isinstance(o, dict):
            continue
        ten = str(o.get("ten") or "").strip()
        if not ten:
            continue
        vung = str(o.get("vung") or "than")
        if vung not in VUNG_HOP_LE:
            vung = "than"
        truoc = dem["gia_tri_lam_sach"]
        ten = _sach(ten)
        khoi = _khoi_sach(o.get("khoi"))
        muc_sach.append({
            "ten": ten, "vung": vung, "khoi": khoi, "dem_delta": dem["gia_tri_lam_sach"] - truoc,
        })

    if goi and muc_sach:
        khoi_toan_bo: list[dict] = []
        nguon_muc: list[int] = []
        for mi, m in enumerate(muc_sach):
            for k in m["khoi"]:
                khoi_toan_bo.append(k)
                nguon_muc.append(mi)
        khoi_moi, nguon_moi = _khop_bang(khoi_toan_bo, goi, bang_theo_nhan, nguon_muc)
        theo_muc: dict[int, list[dict]] = {}
        for k, mi in zip(khoi_moi, nguon_moi, strict=True):
            theo_muc.setdefault(mi, []).append(k)
        for mi, m in enumerate(muc_sach):
            m["khoi"] = theo_muc.get(mi, [])

    # Fix round 2 — tiêu đề văn bản (`van_ban.tieu_de`) đặt vào ĐÚNG vị trí
    # nguồn của nó khi nó là chữ THẬT nhưng CHƯA xuất hiện ở đâu trong thân
    # bài — thay vì một quy ước trình bày cố định (luôn ở đầu trang, qua
    # `<h1>` phía `XemTruocA4`). Đo thật trên BM.M05: tiêu đề nằm ở chỉ số 4
    # trong nguồn, SAU letterhead (chỉ số 1–3) — render cũ luôn đặt nó TRƯỚC
    # letterhead vì `<h1>` luôn vẽ ở đầu, không phải vì đó là vị trí thật.
    # Không chèn khi mô hình ĐÃ tự in tiêu đề ra thân bài (giữ nguyên, tránh
    # lặp — cùng ca R4 xử lý ở phía render) hay khi không định vị được (soạn
    # từ đầu, không có vị trí nguồn nào để dùng) — hai ca đó `<h1>` phía
    # render đã lo đúng, không cần khối này.
    # Vị trí nguồn dựng MỘT lần, dùng cho HAI việc: chèn tiêu đề vào đúng chỗ
    # (dưới) và gán TRANG NGUỒN cho từng mục (khối `giu` phía sau). Trước bản
    # vá dòng chảy trang, nó chỉ tồn tại bên trong nhánh tiêu đề.
    vi_tri = _vi_tri_theo_don_vi(goi)
    trang_theo_chi_so = {d.chi_so: d.trang for d in goi[0]["don_vi"]} if goi else {}
    tieu_de_sach = _sach(str((van_ban or {}).get("tieu_de") or "").strip())
    if goi and tieu_de_sach and muc_sach:
        tieu_de_ch = _khong_hoa(tieu_de_sach)
        tieu_de_vt = vi_tri.get(tieu_de_ch)
        # Fix round 3 (reviewer I2) — quét CẢ ô bảng, không chỉ đoạn văn xuôi:
        # `_vi_tri_theo_don_vi` cố tình đánh chỉ số cho ô bảng luôn (xem
        # docstring hàm đó), nên một tiêu đề sống ngay trong Ô LETTERHEAD
        # (thường gặp ở form tiếng Việt: tên biểu mẫu in trong bảng đầu trang)
        # phải được nhận là "đã có" giống hệt một đoạn văn xuôi — quét thiếu ô
        # bảng khiến chính tiêu đề đó bị chèn thêm một bản sao thứ hai.
        da_co = any(
            tieu_de_ch == _khong_hoa(chu)
            for m in muc_sach
            for k in m["khoi"]
            for chu in (k["noi_dung"].split("\n") if not k["bang"] else (o for hang in k["bang"] for o in hang))
        )
        # Fix round 3 (reviewer I1) — chỉ chèn vào GIỮA khi có ÍT NHẤT MỘT mục
        # định vị được nguồn. Trước bản vá này, `idx` mặc định là cuối danh
        # sách và chỉ dời lên khi tìm thấy một mục đứng SAU tiêu đề — nên khi
        # KHÔNG mục nào định vị được (mọi mục bị mô hình paraphrase hết) tiêu
        # đề vẫn bị cắm xuống CUỐI, dù không có bằng chứng nào nó thật sự đứng
        # cuối. Vì `<h1>` đã bị R4 ẩn đi (tiêu đề giờ trùng chữ với thân bài),
        # kết quả là tiêu đề biến mất khỏi ĐẦU trang mà rơi xuống DƯỚI CÙNG —
        # tệ hơn hành vi trước khi có khối chèn này. Không định vị được mục
        # nào thì bỏ qua, để `<h1>` phía render lo như trước.
        vi_tri_khoi_muc = [_vi_tri_khoi(m["khoi"], vi_tri) for m in muc_sach]
        if tieu_de_vt is not None and not da_co and any(vt is not None for vt in vi_tri_khoi_muc):
            idx = len(muc_sach)
            for i, vt in enumerate(vi_tri_khoi_muc):
                if vt is not None and vt > tieu_de_vt:
                    idx = i
                    break
            muc_sach.insert(idx, {
                # Tên KHÔNG khớp chữ thật nào (`ten_that` sẽ tự ra `False`) —
                # nội dung mới là tiêu đề, `ten` chỉ là nhãn tổ chức nội bộ
                # như "Tiêu đề biểu mẫu" mô hình đã tự đặt cho các mục khác.
                "ten": "Tiêu đề văn bản",
                "vung": "than",
                "khoi": [{
                    "noi_dung": tieu_de_sach,
                    "bang": [],
                    "can_le": theo_dong.get(tieu_de_ch, "giua"),
                    "nhip": [],
                    "ti_le": [],
                    "vien": True,
                    "cao": [],
                    "can_le_o": [],
                    **({"chu": chu} if (chu := _chu_khoi(tieu_de_sach, theo_chu)) else {}),
                    **({"gian_cach": gc} if (gc := _gian_cach_khoi(tieu_de_sach, theo_gc)) else {}),
                }],
                "dem_delta": 0,
            })

    giu: list[dict] = []
    # Trang NGUỒN của mục đã in gần nhất — cái sàn để một mục không định vị
    # được (mô hình paraphrase hết, không còn khớp nguyên văn dòng nào) THEO
    # mục đứng trước nó thay vì tự tụt về trang 1. Fail closed về phía "cùng
    # trang với khối liền trước": vẽ một ngắt trang không có thật xé đôi tài
    # liệu ở chỗ nguồn không hề ngắt, tệ hơn hẳn thiếu một ngắt.
    trang_gan_nhat = 1
    for m in muc_sach:
        ten, vung, khoi, dem_delta = m["ten"], m["vung"], m["khoi"], m["dem_delta"]
        # `ten_that` (Phase 9 U1, fix round 1 gập hoa/thường qua `_khong_hoa`
        # — xem docstring hàm đó) — tên mục này có phải chữ THẬT của tài liệu
        # hay do mô hình đặt ra để tổ chức bản thảo. `goi` rỗng (test cũ,
        # hoặc lượt không có tài liệu cấu trúc) thì không đối chiếu được gì —
        # mặc định GIỮ tên (an toàn về phía không ẩn oan một tiêu đề thật).
        ten_that = (not goi) or _khong_hoa(ten) in nhan_that
        # Fix round 2 — bỏ dòng đầu khối khi nó LẶP LẠI chính `ten`, nhưng CHỈ
        # khi `ten` thật sự in ra làm tiêu đề (`ten_that`): một tên KLAW bịa
        # (`ten_that=False`) không in ra trang (R4/U1) nên không có gì để
        # "trùng" với dòng đầu nội dung. Làm TRƯỚC các phép kiểm dưới, để
        # mục hết nội dung vì bị trùng tên đi qua ĐÚNG MỘT nhánh "hết khối".
        # Fix round 3 (reviewer I3) — khối bị `_bo_dong_trung_ten` xoá SẠCH
        # (nội dung của nó CHỈ có đúng dòng trùng tên, không còn gì khác) phải
        # được phân biệt với một mục vốn dĩ rỗng: mục này đã in `ten` ra làm
        # tiêu đề rồi, chỉ là không còn dòng thân bài nào THÊM — giống một
        # trường biểu mẫu chưa điền gì ngoài tên trường. Áp luật "không khối
        # thì bỏ mục" (dưới) vào ca này biến "in ra HAI lần" (lỗi round 2 sửa)
        # thành "in ra KHÔNG lần nào" — mất cả tên lẫn nội dung, tệ hơn lỗi
        # gốc. `trung_het` chỉ bật đúng ca này, không đụng mục rỗng từ đầu hay
        # mục bị gộp hết vào bảng của mục khác (fix round 1).
        trung_het = False
        if ten_that:
            khoi_truoc = khoi
            khoi = _bo_dong_trung_ten(khoi, ten)
            trung_het = bool(khoi_truoc) and not khoi
        # Mục KHÔNG còn khối nào sau khi sạch, và KHÔNG phải vì trùng tên hết
        # sạch — tương đương "không noi_dung không bang" của Phase 7: không
        # phải một đề mục có nội dung, chỉ là cái tên đứng một mình. Cũng là
        # kết cục của một mục bị GỘP HẾT vào bảng của mục khác (fix round 1).
        if not khoi and not trung_het:
            dem["gia_tri_lam_sach"] -= dem_delta
            continue
        kiem_tra = "\n".join(
            [ten, *(k["noi_dung"] for k in khoi), *(c for k in khoi for hang in k["bang"] for c in hang)]
        )
        if _vuong_luoi_chan(kiem_tra):
            dem["muc_bo"] += 1
            # Giá trị đã thay trong một mục bị bỏ không còn là một phép làm
            # sạch người đọc thấy được — trả lại bộ đếm cho đúng.
            dem["gia_tri_lam_sach"] -= dem_delta
            continue
        if dem_delta > 0:
            dem["muc_lam_sach"] += 1
        # Trang NGUỒN của mục — `DonViVanBan.trang` của đơn vị mà khối đầu của
        # mục định vị được (`_vi_tri_khoi`), tức số trang tệp KHAI
        # (`doc_tai_lieu._DemTrang`), không phải một con số mô hình tự đặt:
        # `van_ban.muc[*]` không có trường nào cho trang, và hỏi mô hình một
        # sự thật đọc thẳng ra được từ XML là mời nó bịa. Chỉ TIẾN, không lùi:
        # mô hình có thể đảo thứ tự mục, và một trang lùi lại sẽ vẽ ra một
        # ngắt trang ngược đời trên màn hình.
        if (vt := _vi_tri_khoi(khoi, vi_tri)) is not None:
            trang_gan_nhat = max(trang_gan_nhat, trang_theo_chi_so.get(vt, trang_gan_nhat))
        giu.append({
            "ten": ten,
            "ten_that": ten_that,
            "vung": vung,
            "trang": trang_gan_nhat,
            "khoi": khoi,
            # Chỉ CÓ MẶT khi tệp khai — cùng luật `chu`/`gian_cach` của khối:
            # một mục không có lề nguồn giữ nguyên hình dạng cũ, và ba nơi vẽ
            # giữ lề mặc định của chính chúng.
            **({"le_trang": le_trang} if le_trang else {}),
            # Cùng luật `le_trang`: chỉ CÓ MẶT khi tệp có ảnh, nên một bản thảo
            # KLAW tự soạn giữ nguyên hình dạng cũ.
            **({"anh": anh} if anh else {}),
        })
    return {"tieu_de": tieu_de_sach, "muc": giu}, dem


def _nguon_soan(goi: list[dict], state: dict, truong: list[dict], quan_sat: list[dict],
                bo_nho_cho_phep: list[str] | None = None) -> str:
    """Chữ mà một mục của bản thảo được phép lấy giá trị từ đó.

    Nguồn thứ SÁU (Phase 12 part B, R4) là `bo_nho_cho_phep` — và nó CÓ ĐIỀU
    KIỆN, khác năm nguồn kia: chỉ những giá trị đã nhớ mà CHÍNH lượt này hỏi
    tới (`khoa_duoc_hoi`) mới vào đây. Một ký ức không được hỏi tới không phải
    là nguồn của văn bản này; nó chỉ là ngữ cảnh trong prompt, và
    `lam_sach_van_ban(cam=…)` gỡ nó ra nếu mô hình vẫn tự điền.

    NĂM nguồn (review, fix round 1 — trước đây bốn): TOÀN BỘ đơn vị của tài
    liệu trong lượt (không chỉ phần đã gửi cho mô hình — phép lọc đầu vào là
    chuyện chi phí, không phải chuyện bằng chứng, cùng lý lẽ với phép neo
    `quan_sat`), đoạn trích đã neo của lượt, chính lời người hỏi, hồ sơ tình
    huống của hội thoại, và (mới) chính BẢN THẢO ĐANG CÓ (R4,
    `ban_thao_tong_quat_dang_mo`) khi hội thoại này đã có một. Đoạn trích đã
    neo về mặt tập hợp nằm trong đơn vị rồi; giữ nó ở đây để khi phép neo nới
    ra (nối nhiều đơn vị) thì nguồn không hụt theo.

    Thiếu nguồn thứ năm là chính lỗ hổng R4 để lại: prompt (R4) đã ra lệnh
    "giữ nguyên câu người dùng đã viết", nhưng lưới chặn bịa (`_sach`/
    `_vuong_luoi_chan` ngay dưới đây) không hề biết bản thảo đang có là một
    nguồn hợp lệ — một mã số sinh viên/số điện thoại/ngày tháng người dùng
    tự gõ ở LƯỢT TRƯỚC (đã nằm trong `document`, không phải bịa) sẽ bị coi là
    KHÔNG CÓ NGUỒN ở lượt SAU, thay bằng `[…]` hoặc bị bỏ nguyên mục — biến
    "mô hình quên" thành "mô hình nhớ đúng rồi bị lưới chặn xoá", cùng một
    mất mát, khó thấy hơn.
    """
    phan = [d.noi_dung for t in goi for d in t["don_vi"]]
    phan += [q.get("trich") or "" for q in quan_sat]
    phan += [str(state.get(k) or "") for k in ("cau_hoi_goc", "query", "cau_hoi_day_du")]
    phan += [str(v.get("gia_tri") or "") for v in (state.get("ho_so") or {}).values() if isinstance(v, dict)]
    phan += [str(o.get("gia_tri") or "") for o in truong]
    phan.append(str((state.get("ban_thao_tong_quat_dang_mo") or {}).get("document") or ""))
    phan += list(bo_nho_cho_phep or [])
    return "\n".join(phan)


def _loi_nguoi_hoi(state: dict) -> str:
    """Lời NGƯỜI HỎI của lượt: câu họ gõ và câu đầy đủ của lượt nối tiếp."""
    return "\n".join(str(state.get(k) or "") for k in ("cau_hoi_goc", "query", "cau_hoi_day_du"))


def _nguon_nguoi(state: dict, bo_nho_cho_phep: list[str] | None = None) -> str:
    """Nguồn của GIÁ TRỊ MỚI trên khuôn gốc — luật owner 2026-09-27 ("nếu người dùng
    yêu cầu sửa thì hãy sửa, còn nếu bảo soạn thảo văn bản ra thì phải đúng 100%"):
    chỉ điều NGƯỜI HỎI đưa ra — lời của họ (`_loi_nguoi_hoi`), hồ sơ trừ giả định
    (`suy_dien` là KLAW tự đọc ra, CONTEXT.md "giả định"), và ký ức lượt này hỏi tới.

    KHÁC `_nguon_soan` (đường HTML): chữ của tài liệu, đoạn trích `quan_sat` và
    `document` của bản thảo đang mở KHÔNG vào. Đo được 2026-09-27: với "soạn thảo văn
    bản này cho tôi", mô hình chép «Trường Đại học Phenikaa» IN SẴN trong câu vào chỗ
    «Khoa» của chính câu ấy, và phép nguồn cũ cho qua vì chữ đó "có trong tài liệu".
    Giá trị phiên bản đang có đã điền vẫn ở lại qua phép gộp; một phép lặp lại y hệt
    không phải giá trị mới (`kiem_phep_sua`, `dang_co`)."""
    ho_so = (state.get("ho_so") or {}).values()
    phan = [_loi_nguoi_hoi(state)]
    phan += [str(v.get("gia_tri") or "") for v in ho_so if isinstance(v, dict) and v.get("nguon") != "suy_dien"]
    phan += list(bo_nho_cho_phep or [])
    return "\n".join(phan)


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
        gia_tri = bo_dau_noi_bo(str(o.get("gia_tri") or "").strip())
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
        # Khoá TRÙNG trong cùng một lượt được đánh số. Đo toàn tuyến 2026-09-16:
        # một phiếu chấm cho ra `diem_toi_da` bốn lần với bốn giá trị — bốn dòng
        # cùng tên, không dòng nào nói nó thuộc tiêu chí nào, và `PATCH
        # /tai-lieu/du-kien/{id}` sửa theo id nên người dùng sửa mò. Chống trùng
        # ở `luu_du_kien` chỉ so với dòng ĐÃ CÓ, nên nó không thấy ca này.
        da_dung = {d["key"] for d in giu}
        if khoa in da_dung:
            goc, i = khoa, 2
            while f"{goc}_{i}" in da_dung:
                i += 1
            khoa = f"{goc}_{i}"
        giu.append({
            "key": khoa,
            "nhan": bo_dau_noi_bo(str(o.get("nhan") or "").strip()) or None,
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


def _lay_dieu_khoan(ra: dict, goi: list[dict]) -> tuple[list[dict], int]:
    """Điều khoản của người hỏi → `tai_lieu_neo`, hình dạng `NeoTaiLieuOut` cộng
    `trich` và `cau_hoi_phap_ly` (hai trường lược đồ đã dành sẵn cho nhánh này).

    Cùng một đòi hỏi với `quan_sat`, và vì một lý do nặng hơn: đoạn trích này sắp
    được đặt CẠNH điều luật. Một điều khoản không tra ngược được về đúng chữ
    trong tài liệu mà vẫn đi tiếp thì cả lượt đối chiếu đứng trên một câu do mô
    hình viết ra — và người đọc sẽ thấy nó nằm cạnh một trích dẫn đã qua hai tầng
    kiểm, tức mượn uy tín của căn cứ cho một dữ kiện không có thật.

    Thiếu `cau_hoi_phap_ly` cũng bị loại: không có câu hỏi thì không có gì để
    hỏi kho, và một điều khoản không hỏi được kho chỉ làm loãng lời nhắc.
    """
    giu: list[dict] = []
    bo = 0
    for o in ra.get("dieu_khoan") or []:
        if not isinstance(o, dict):
            bo += 1
            continue
        trich = bo_tien_to(str(o.get("trich") or ""))
        cau_hoi = " ".join(str(o.get("cau_hoi_phap_ly") or "").split())
        neo = _neo_dau_tien(trich, goi) if (trich and cau_hoi) else None
        if neo is None:
            bo += 1
            continue
        giu.append({**_neo_ra(*neo), "trich": trich, "cau_hoi_phap_ly": cau_hoi})
    return giu[:TOI_DA_DIEU_KHOAN], bo


def cau_hoi_doi_chieu(dieu_khoan: list[dict]) -> str:
    """Câu hỏi mà đường pháp lý sẽ đi tra — ghép BẰNG MÃ từ `cau_hoi_phap_ly` của
    từng điều khoản, không thêm một lượt gọi nào.

    Đây là điểm mấu chốt của lát cắt: truy hồi chạy trên câu hỏi PHÁP LÝ ("thời
    gian thử việc tối đa là bao lâu"), không trên câu người hỏi gõ ("hợp đồng này
    có đúng luật không"). Câu sau không có từ nào của điều luật cần tìm, nên tra
    theo nó là tra vào chỗ khác rồi trả lời một điều không ai hỏi.
    """
    return "; ".join(d["cau_hoi_phap_ly"] for d in dieu_khoan)[:CAU_HOI_TOI_DA].strip().rstrip(";")


# ── Khuôn gốc: phép sửa thay cho `van_ban` (P4b) ────────────────────────────
#
# Quyết định 2026-09-26 mục 3: trên một tài liệu có khuôn gốc, mô hình chỉ trả
# PHÉP SỬA gắn với đơn vị văn bản, KLAW áp lên chính tệp. Mọi phép qua
# `kiem_phep_sua` — tất định, 0 token — TRƯỚC khi chạm bảng nào; phép bị bỏ chỉ
# còn lại dưới dạng SỐ ĐẾM trong traces và một nhãn chỗ trống cho `assemble`.
#
# Loại phép mỗi định dạng nhận, đúng hai bộ áp: PDF không dàn lại được dòng
# (`dien_khuon_pdf`), nên không chèn, không xoá.
LOAI_PHEP = {"docx": ("dien", "thay", "chen_sau", "xoa"), "pdf": ("dien", "thay")}
# Ký tự điều khiển, kể cả `\n`/`\t`: `dien` là MỘT dòng. `thay`/`chen_sau` DOCX
# được giữ `\n` (bộ áp tách đoạn), PDF thì không (một dòng trên trang).
_RE_DIEU_KHIEN = re.compile(r"[\x00-\x1f\x7f]")


def co_khuon(t: dict) -> bool:
    """Tài liệu này có khuôn gốc KLAW áp phép sửa lên được không. `co_khuon_goc`/
    `dinh_dang` do `graph_tra_cuu` đọc từ DB — node này không chạm DB."""
    return bool(t.get("co_khuon_goc")) and t.get("dinh_dang") in LOAI_PHEP


def _dia_duoc(d: DonViVanBan, dinh_dang: str) -> bool:
    """Đơn vị có chỗ ghim để bộ áp đi thẳng tới: `dia_chi` (docx), `hop` (pdf)."""
    return (d.dia_chi if dinh_dang == "docx" else d.hop) is not None


def _cho_dien_duoc(d: DonViVanBan, dinh_dang: str) -> list[ChoTrong]:
    """Chỗ trống của `d` mà bộ áp điền được — PDF còn đòi hộp của chính chỗ trống."""
    if not _dia_duoc(d, dinh_dang):
        return []
    return [c for c in d.cho_trong if dinh_dang == "docx" or c.hop]


def cho_trong_khuon(t: dict) -> list[dict]:
    """Mọi chỗ trống điền được của tài liệu, theo thứ tự đọc — nền cho bản tóm
    tắt bản thảo và cho danh sách "Còn trống" (`assemble`). `doan` (đoạn chứa chỗ
    trống) để một `thay` theo đoạn chỉ gỡ chỗ trống của đúng đoạn đó."""
    return [
        {"don_vi": d.chi_so, "so": c.so, "kieu": c.kieu, "nhan": c.nhan, "doan": c.doan}
        for d in t["don_vi"]
        for c in _cho_dien_duoc(d, t["dinh_dang"])
    ]


def _hoac_null(kieu: str) -> dict:
    # `anyOf` chứ không `["integer", "null"]`: hình dạng null-được-phép mà schema
    # strict đã chạy thật ở `generate_claims` (xem chú thích `hang` ở đó).
    return {"anyOf": [{"type": "null"}, {"type": kieu}]}


# `khuon.yeu_cau` — luật owner 2026-09-27 ("nếu người dùng yêu cầu sửa thì hãy sửa,
# còn nếu bảo soạn thảo văn bản ra thì phải đúng 100%"): `tao_lai` dựng lại CHÍNH tệp
# (mọi phép đề xuất bị bỏ, tất định), `dien_sua` điền/sửa nó, `van_ban_khac` là một văn
# bản khác. Thiếu hay lạ là `dien_sua` — an toàn vì phép nguồn chỉ nhận lời người hỏi.
YEU_CAU = ("tao_lai", "dien_sua", "van_ban_khac")


def _quyet_khuon(cau: str, soan: bool, tin_soan: bool, yeu_cau: str, co_phep: bool) -> tuple[bool, str]:
    """`(lượt soạn?, yeu_cau)` trên tài liệu có khuôn gốc (G7, Q4). Hàm thuần.

    `soan`: đường cũ (nhãn mô hình sau gác router) nói soạn; `tin_soan`: mô hình hay
    router từng đọc là soạn, hay mô hình đề xuất phép. Lời xin điền/sửa, hay `dien_sua`
    có ≥1 phép qua kiểm → lượt điền (không phép nào qua thì `dung_ban_thao_tong_quat`
    không đổi bản thảo nào); lời xin điền mà không ai đọc là soạn và không phép nào
    ("tôi phải điền gì vào ô Mã số?") vẫn là hỏi đáp; lời xin dựng lại → `tao_lai`,
    đúng tệp tải lên — trừ câu hỏi không ai đọc là soạn ("Văn bản này do ai soạn
    thảo?"): dựng lại xoá mọi giá trị đã điền. `van_ban_khac` của mô hình đứng nguyên:
    bộ nhận câu không biết văn bản NÀO được soạn ("dựa vào phiếu này soạn đơn…, sửa
    cho trang trọng")."""
    if yeu_cau == "van_ban_khac":
        return soan, yeu_cau
    dien = xin_dien_sua(cau)
    if (co_phep and yeu_cau == "dien_sua") or (dien and (co_phep or tin_soan)):
        return True, "dien_sua"
    if dien:
        return False, yeu_cau
    if xin_tao_lai(cau) and (tin_soan or not _la_cau_hoi(cau)):
        return True, "tao_lai"
    return soan, yeu_cau


def schema_khuon(nhan: list[str], nhan_khuon: list[str], loai: list[str]) -> dict:
    """`schema_hieu` với `khuon` THAY cho `van_ban`: không còn đường nào để mô hình
    viết lại văn bản. `tai_lieu` là enum nhãn của tài liệu CÓ khuôn gốc; mọi trường
    của một phép đều `required` (strict), trường không dùng thì `null`. `yeu_cau`
    (`YEU_CAU`): người hỏi xin dựng lại CHÍNH tài liệu này, điền/sửa nó, hay một văn
    bản khác dựa trên nó — không suy ra từ việc `phep_sua` rỗng. `khong_dat`: giá trị
    người hỏi đưa mà mô hình không đặt được vào chỗ nào (KLAW báo lại, không đoán)."""
    s = schema_hieu(nhan)
    del s["properties"]["van_ban"]
    s["required"] = [k for k in s["required"] if k != "van_ban"] + ["khuon"]
    s["properties"]["khuon"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["tai_lieu", "yeu_cau", "phep_sua", "khong_dat"],
        "properties": {
            "tai_lieu": {"type": "string", "enum": nhan_khuon},
            "yeu_cau": {"type": "string", "enum": list(YEU_CAU)},
            "khong_dat": {"type": "array", "items": {"type": "string"}},
            "phep_sua": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["loai", "don_vi", "cho_trong", "gia_tri", "noi_dung", "doan"],
                    "properties": {
                        "loai": {"type": "string", "enum": loai},
                        "don_vi": {"type": "integer"},
                        "cho_trong": _hoac_null("integer"),
                        "gia_tri": _hoac_null("string"),
                        "noi_dung": _hoac_null("string"),
                        # `thay` MỘT đoạn của đơn vị (số sau `¶` trong prompt).
                        "doan": _hoac_null("integer"),
                    },
                },
            },
        },
    }
    return s


def _phep_dang_mo(bt: dict | None, viec_id: str, loai: str | None = None) -> list[dict]:
    """Phép `loai` (`None`: mọi loại) của bản thảo đang mở, khi nó nằm trên đúng khuôn gốc này."""
    if not bt or str(bt.get("viec_id") or "") != viec_id:
        return []
    return [p for p in bt.get("phep_sua") or [] if isinstance(p, dict) and loai in (None, p.get("loai"))]


def _dang_dien(bt: dict | None, viec_id: str) -> dict[tuple[int, int], str]:
    """Giá trị ĐANG điền của bản thảo đang mở, khi nó nằm trên đúng khuôn gốc này."""
    return {
        (p.get("don_vi"), p.get("cho_trong")): str(p.get("gia_tri") or "") for p in _phep_dang_mo(bt, viec_id, "dien")
    }


def _dang_thay(bt: dict | None, viec_id: str) -> dict[tuple[int, int | None], str]:
    """Chữ HIỆN TẠI của đoạn (`doan`) hay cả đơn vị (`None`) mà bản thảo đang mở đã
    `thay`: prompt hiện chữ đó thay cho chữ gốc, không còn dấu chỗ trống nào — một
    dấu ở đó mời `dien` vào chỗ mà `gop_phep_sua` sẽ gỡ."""
    return {
        (p.get("don_vi"), p.get("doan")): " ".join(str(p.get("noi_dung") or "").split())
        for p in _phep_dang_mo(bt, viec_id, "thay")
    }


def _dien_bo_nho(s: str, cam_bo: set[str]) -> bool:
    """Chữ này có điền một điều đã NHỚ vào một chỗ điền không — đúng hai hình dạng
    `lam_sach_van_ban._chan_bo_nho` nhận: cả dòng là giá trị, hoặc phần sau "Nhãn:"."""
    for dong in s.split("\n"):
        sau = dong.partition(":")[2].strip()
        if _khong_hoa(dong.strip()) in cam_bo or (sau and _khong_hoa(sau) in cam_bo):
            return True
    return False


def _nhan_khong_nguon(chu: str, nguon_kh: str, so_nguon: list) -> bool:
    """Có dòng "Nhãn: giá trị" nào mà giá trị KHÔNG qua phép nguồn của `dien` không.
    Dãy chấm cắt giá trị thành từng mảnh (chấm đi kèm không rửa được một tên bịa);
    dấu câu cuối mảnh là trình bày, không phải dữ kiện."""
    for dong in chu.split("\n"):
        for manh in RE_CHO_DIEN.split(dong.partition(":")[2]):
            v = manh.strip().rstrip(".;,").strip()
            if v and not _co_trong_nguon(v.casefold(), nguon_kh, so_nguon):
                return True
    return False


def _so_dieu(s: str) -> set[str]:
    """Số Điều/Khoản/Điểm của `s`, mỗi số một CỤM ("điều50"): so theo cụm, không
    theo chuỗi con — "Điều 5" không nằm trong "Điều 50"."""
    return {re.sub(r"[\s.]", "", m.group(0)) for m in _RE_DIEU.finditer(_khong_hoa(s))}


_RE_TU = re.compile(r"\w+")


def _khong_dau(s: str) -> str:
    """Gập hoa/thường VÀ bỏ dấu — CHỈ để biết một từ của `thay` có sẵn trong chữ cũ
    của đoạn không ("TÊN CƠ QUAN" = "Ten co quan"). Không bao giờ để so nguồn:
    phép nguồn vẫn là `_co_trong_nguon`, giữ dấu (xem `_khong_hoa`)."""
    s = unicodedata.normalize("NFD", s.casefold().replace("đ", "d"))
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _cum_them(moi: str, cu: str) -> list[str]:
    """Các cụm từ `moi` THÊM so với `cu`: mỗi đoạn `insert`/`replace` của phép so
    DÃY từ (`SequenceMatcher`, không so tập — xem `_them_khong_nguon`), cắt nguyên
    văn từ `moi` (NFC)."""
    moi, cu = unicodedata.normalize("NFC", moi), unicodedata.normalize("NFC", cu)
    tu = list(_RE_TU.finditer(moi))
    so = SequenceMatcher(
        None, [_khong_dau(m) for m in _RE_TU.findall(cu)], [_khong_dau(m.group()) for m in tu], autojunk=False
    )
    return [
        moi[tu[j1].start() : tu[j2 - 1].end()] for op, _, _, j1, j2 in so.get_opcodes() if op in ("insert", "replace")
    ]


def _them_khong_nguon(moi: str, cu: str, nguon_kh: str, so_nguon: list) -> bool:
    """`moi` có THÊM cụm từ nào so với `cu` mà không qua phép nguồn của `dien`
    không. So DÃY từ (`_cum_them`), không so tập: một cụm của chính `cu` lặp
    lại hay chuyển chỗ là chữ THÊM — review fix/g4-backend đo được «…Trường Đại học
    Phenikaa, thuộc Khoa Trường Đại học Phenikaa» lọt qua phép so tập. Mỗi cụm đi
    `_co_trong_nguon` NGUYÊN cụm (chặt hơn từng từ: "Công ty Bịa Việt" không lọt
    nhờ "Việt" có ở nguồn). Thay cho lời từ chối `co_cho_trong`: điền cụm giữ chỗ
    viết hoa hay đè một dòng có chỗ trống là một lần điền, dù đi đường nào."""
    return any(not _co_trong_nguon(c.casefold(), nguon_kh, so_nguon) for c in _cum_them(moi, cu))


# Nhãn số hiệu NGẮN ("Số", "Số:", "No.") và nhãn phần ngày ("… ngày", "tháng",
# "năm"): chỗ trống sau chúng là một con số. Hẹp có chủ ý — đúng lỗi owner đo được
# 2026-09-27 (tên cơ quan có nguồn rơi vào «Số» của BM.M05), không luật nhãn nào
# khác: phép nguồn không bắt được một giá trị THẬT đặt sai chỗ.
_RE_NHAN_SO = re.compile(r"(?:số|no\.?)\s*:?")
_RE_NHAN_NGAY = re.compile(r"(?:^|\W)(?:ngày|tháng|năm)\W*$")
# Cột bảng danh sách (chỗ `o`, G5) mang một mã hay số: «Mã sinh viên…», «Số điện
# thoại», «STT»/«TT». Đo được 2026-09-27: tên sinh viên (có nguồn) vào ô «Mã sinh
# viên/ học viên» của BM.M05 — cùng lỗi «Số» ở trên, hình dạng bảng.
_RE_COT_SO = re.compile(r"(?:mã|số|s?tt)\b")
_RE_DONG_O = re.compile(r" \(dòng \d+\)$")


def _khop_nhan(nhan: str, v: str, kieu: str = "cham") -> bool:
    n = _khong_hoa(nhan).strip()
    can_so = (
        _RE_COT_SO.match(_RE_DONG_O.sub("", n)) if kieu == "o" else _RE_NHAN_SO.fullmatch(n) or _RE_NHAN_NGAY.search(n)
    )
    return any(ch.isdigit() for ch in v) if can_so else True


def _mot_phep(
    p: object, theo_chi_so: dict[int, DonViVanBan], dinh_dang: str, nguon_kh: str, so_nguon: list, cam_bo: set[str]
) -> dict | str:
    """Một phép thô → phép đúng hình dạng hợp đồng, hoặc MÃ lý do bỏ. Không đoán:
    thiếu gì là bỏ."""
    if not isinstance(p, dict) or p.get("loai") not in LOAI_PHEP["docx"]:
        return "sai_hinh_dang"
    loai = p["loai"]
    if loai not in LOAI_PHEP[dinh_dang]:
        return "loai_khong_ho_tro"
    dv = p.get("don_vi")
    if type(dv) is not int:
        return "sai_hinh_dang"
    d = theo_chi_so.get(dv)
    if d is None:
        return "khong_co_don_vi"
    if not _dia_duoc(d, dinh_dang):
        return "khong_co_dia_chi"
    # `doan` chỉ có nghĩa với `thay`: `xoa`/`chen_sau` mang nó mà nới ra cả đơn vị
    # là xoá cả ô tiêu đề thư khi người hỏi chỉ xin bỏ dòng "Số …/…".
    if loai in ("xoa", "chen_sau") and p.get("doan") is not None:
        return "sai_hinh_dang"
    if loai == "xoa":
        return {"loai": "xoa", "don_vi": dv}
    if loai == "dien":
        so, v = p.get("cho_trong"), p.get("gia_tri")
        if type(so) is not int or not isinstance(v, str):
            return "sai_hinh_dang"
        c = next((c for c in _cho_dien_duoc(d, dinh_dang) if c.so == so), None)
        if c is None:
            return "khong_co_cho_trong"
        v = v.strip()
        if _RE_DIEU_KHIEN.search(v):
            return "sai_hinh_dang"
        # Rỗng = gỡ chỗ điền ở lượt sửa (dãy chấm trở lại): không có gì để kiểm.
        if v:
            if vung_trong(v):
                return "vung_trong"
            if _khong_hoa(v) in cam_bo:
                return "bo_nho"
            # Gập hoa/thường hai phía: viết hoa tên riêng là trình bày, không
            # phải một dữ kiện mới. Luật định danh của `_vuong_luoi_chan` KHÔNG
            # áp ở đây — số điện thoại người hỏi tự nói là một giá trị điền đúng.
            if not _co_trong_nguon(v.casefold(), nguon_kh, so_nguon):
                return "khong_nguon"
            if not _khop_nhan(c.nhan, v, c.kieu):
                return "khong_khop_nhan"
            # Chỗ trống `tab`: bộ áp đặt giá trị NGAY sau nhãn, không dấu cách.
            # ponytail: `nhan` đã `strip()` nên luôn thêm một dấu cách; một nhãn
            # thô vốn kết bằng dấu cách thì ra hai — đọc chuỗi thô khi đo thấy.
            if c.kieu == "tab" and c.nhan and not c.nhan[-1].isspace():
                v = " " + v
        return {"loai": "dien", "don_vi": dv, "cho_trong": so, "gia_tri": v}
    chu = p.get("noi_dung")
    if not isinstance(chu, str):
        return "sai_hinh_dang"
    chu = chu.replace("\r\n", "\n").strip()
    if not chu or _RE_DIEU_KHIEN.search(chu.replace("\n", "") if dinh_dang == "docx" else chu):
        return "sai_hinh_dang"
    # `thay` MỘT đoạn (`doan`, số sau `¶` trong prompt): chỉ DOCX, một dòng, đoạn
    # phải có. Đơn vị không mang `doan_chu` là một đoạn — trừ khi nó có chỗ trống:
    # khi đó đó là dòng lưu TRƯỚC `doan_chu`, số đoạn không biết, nên bỏ.
    # ponytail: ô bảng NHIỀU đoạn không chỗ trống của dòng cũ cũng không mang
    # `doan_chu` và ở đây bị coi là một đoạn; bộ áp đếm `w:p` thật và bỏ phép
    # (`khong_co_dia_chi`), không ghi sai đoạn. Đọc lại tệp (`doc-lai`) là đủ —
    # thêm dấu phiên bản bộ đọc khi đo thấy dòng cũ còn dùng.
    doan = p.get("doan") if loai == "thay" else None
    goc = d.noi_dung
    if doan is not None:
        if dinh_dang != "docx":
            return "loai_khong_ho_tro"
        if type(doan) is not int or doan < 0 or "\n" in chu:
            return "sai_hinh_dang"
        cac_doan = d.doan_chu or ((d.noi_dung,) if not d.cho_trong else ())
        if doan >= len(cac_doan):
            return "khong_co_doan"
        goc = cac_doan[doan]
    if _dien_bo_nho(chu, cam_bo):
        return "bo_nho"
    # Luật Điều/Khoản của `_vuong_luoi_chan`, theo cụm: một số Điều mà CHÍNH đơn
    # vị gốc đã có thì giữ, số Điều mới thì không — bản thảo chưa kiểm pháp lý.
    if _so_dieu(chu) - _so_dieu(d.noi_dung):
        return "dieu_luat"
    # Chữ cũ mà phép này GIỮ: `thay` giữ chữ của chính đoạn (hay đơn vị) nó thay;
    # `chen_sau` không thay gì, nên mọi chữ của nó là chữ THÊM (luật owner 2026-09-27
    # — trước đó `chen_sau` chỉ qua lưới chữ số/email và "Nhãn: giá trị").
    cu = goc if loai == "thay" else ""
    nguon_p = nguon_kh + "\n" + _khong_hoa(cu)
    so_p = so_nguon + [v for m in _RE_SO_THUAN.findall(_khong_hoa(cu)) if (v := tinh(m)) is not None]
    # Cùng lưới giá trị của `lam_sach_van_ban`, nhưng BỎ cả phép thay vì chừa
    # `[…]`: một `[…]` áp lên tệp thật là chữ lạ in lên biểu mẫu của người hỏi.
    # Cộng phép nguồn của `dien` cho mọi giá trị sau "Nhãn:" — một đoạn mới
    # "Họ và tên: <tên bịa>" là một lần điền, dù đi đường nào. Số đã có trong chữ
    # cũ của đoạn không phải số mới Ở ĐÂY; chép nó sang chỗ khác hay lặp lại nó là
    # chữ THÊM, và `_them_khong_nguon` (so dãy từ) bên dưới đòi nguồn cho nó.
    if any(
        not _co_trong_nguon(m.group(0).casefold(), nguon_p, so_p) for m in _RE_GIA_TRI.finditer(chu)
    ) or _nhan_khong_nguon(chu, nguon_p, so_p):
        return "khong_nguon"
    # Thay cho lời từ chối `co_cho_trong` cũ: MỌI `thay`/`chen_sau` qua phép nguồn
    # của `dien` cho chữ nó thêm so với chữ cũ của đoạn (hay đơn vị) đó. Cụm giữ chỗ
    # ("TÊN CHỦ QUẢN…") có thể là đơn vị một đoạn không chỗ trống — nơi `doan` null
    # ghi đúng byte của `doan` 0 — hay ô nhiều đoạn: một trường null không được quyết
    # định tên bịa có lên biểu mẫu không. Đổi lại, câu mô hình tự viết lại bằng chữ
    # người hỏi không nói bị bỏ (khuôn gốc: "Bạn KHÔNG viết lại văn bản").
    if _them_khong_nguon(chu, cu, nguon_kh, so_nguon):
        return "khong_nguon"
    # Luật cột của `dien` cho ô rỗng (`o`): `thay` hay `chen_sau` (bộ áp chèn đoạn VÀO
    # ô) lên ô ấy cũng đặt chữ vào cột đó — tên vào «Mã sinh viên» bị bỏ, không lặng lẽ.
    if (o := next((c for c in d.cho_trong if c.kieu == "o"), None)) and not _khop_nhan(
        o.nhan, " ".join(_cum_them(chu, cu)), "o"
    ):
        return "khong_khop_nhan"
    return {"loai": loai, "don_vi": dv, **({"doan": doan} if doan is not None else {}), "noi_dung": chu}


def _khoa_giong(p: dict) -> tuple:
    """Hai phép cùng khoá này là CÙNG một thay đổi (so chữ sau khi gộp khoảng trắng)."""
    dien = p.get("loai") == "dien"
    chu = p.get("gia_tri") if dien else p.get("noi_dung")
    # Đầu ra mô hình có thể mang list/dict ở bất kỳ trường nào: khoá phải băm được.
    so = [x if type(x) is int else None for x in (p.get("don_vi"), p.get("cho_trong" if dien else "doan"))]
    return (str(p.get("loai")), *so, " ".join(str(chu or "").split()))


# Ngày ĐỦ trong một cụm ("01/10/2026", "1-10-2026", "1.10.2026"): ngày, tháng, năm.
_RE_NGAY_DU = re.compile(r"(\d{1,2})([/.-])(\d{1,2})\2(\d{4})")
_RE_TRUOC_NGAY = re.compile(r"(?:^|\W)ngày$")


def _bo_ba_ngay(d: DonViVanBan | None, so: int) -> list[ChoTrong] | None:
    """Chỗ trống `so` của `d` cùng hai chỗ trống ngay sau nó trong CÙNG đoạn, khi biểu
    mẫu chia một ngày thành ba: `… / … / …` (giữa chúng chỉ có `/`) hay `ngày … tháng …
    năm …` (`so` là chỗ sau "ngày"). Đọc trên chữ THÔ của đoạn (`doan_chu`); không có
    thì `None` — không đoán (hàng lưu trước `doan_chu`, PDF)."""
    if d is None or not d.doan_chu:
        return None
    cham = sorted((c for c in d.cho_trong if c.kieu == "cham"), key=lambda c: (c.doan, c.dau))
    i = next((i for i, c in enumerate(cham) if c.so == so), None)
    if i is None or len(cham[i : i + 3]) < 3 or len({c.doan for c in cham[i : i + 3]}) > 1:
        return None
    a, b, c = cham[i : i + 3]
    if a.doan >= len(d.doan_chu):
        return None
    s = unicodedata.normalize("NFC", d.doan_chu[a.doan]).casefold()
    giua = (s[a.cuoi : b.dau].strip(), s[b.cuoi : c.dau].strip())
    if giua == ("/", "/") or (giua == ("tháng", "năm") and _RE_TRUOC_NGAY.search(s[: a.dau].rstrip())):
        return [a, b, c]
    return None


def _tach_ngay(phep: list, theo_chi_so: dict[int, DonViVanBan]) -> list:
    """Một `dien` mang ngày ĐỦ vào chỗ đầu của một bộ ba ngày (`_bo_ba_ngay`) → ba
    `dien` ngày, tháng, năm, đúng như prompt dặn mà mô hình không làm — trừ khi chính
    lượt này đã điền một trong hai chỗ sau. Chạy TRƯỚC phép kiểm, nên mỗi phần qua
    đúng phép nguồn và phép nhãn của chỗ nó vào. Hẹp có chủ ý (BM.M05 trang 2
    "Thời gian: từ … / … / … đến … / … / …"): không hình dạng nào khác bị tách."""

    def _o(p: object) -> tuple[int, int] | None:
        ok = isinstance(p, dict) and p.get("loai") == "dien"
        return (
            (p["don_vi"], p["cho_trong"]) if ok and type(p.get("don_vi")) is type(p.get("cho_trong")) is int else None
        )

    da_dien = {o for p in phep if (o := _o(p))}
    ra = []
    for p in phep:
        o = _o(p)
        m = _RE_NGAY_DU.fullmatch(p["gia_tri"].strip()) if o and isinstance(p.get("gia_tri"), str) else None
        ba = _bo_ba_ngay(theo_chi_so.get(o[0]), o[1]) if m else None
        if ba and not {(o[0], c.so) for c in ba[1:]} & da_dien:
            ra += [{**p, "cho_trong": c.so, "gia_tri": v} for c, v in zip(ba, (m[1], m[3], m[4]), strict=True)]
        else:
            ra.append(p)
    return ra


def _gia_tri_cua(p: object, theo_chi_so: dict[int, DonViVanBan]) -> list[str]:
    """Giá trị một phép mang tới: chữ `dien`, hay các cụm `thay`/`chen_sau` THÊM so
    với chữ cũ của đoạn (hay đơn vị) nó thay (`_cum_them`; `chen_sau` không thay gì)."""
    if not isinstance(p, dict):
        return []
    if p.get("loai") == "dien":
        return [v] if isinstance(v := p.get("gia_tri"), str) and v.strip() else []
    chu, dv, doan = p.get("noi_dung"), p.get("don_vi"), p.get("doan")
    if p.get("loai") not in ("thay", "chen_sau") or not isinstance(chu, str):
        return []
    d = theo_chi_so.get(dv) if type(dv) is int else None
    cu = ""
    if p["loai"] == "thay" and d is not None:
        cu = d.doan_chu[doan] if type(doan) is int and 0 <= doan < len(d.doan_chu) else d.noi_dung
    return _cum_them(chu, cu)


def kiem_phep_sua(
    phep: object, t: dict, nguon: str, cam: list[str], dang_co: list[dict] | None = None
) -> tuple[list[dict], list[dict], list[str]]:
    """Phép sửa mô hình trả cho tài liệu `t` → `(giữ, bỏ, giá trị bỏ)`. Hàm THUẦN, 0 token.

    `giu` theo đúng thứ tự mô hình trả, CHƯA khử trùng: lượt sửa mang THAY ĐỔI, và
    một `dien` rỗng (gỡ chỗ điền) chỉ có nghĩa khi gộp với phép đang có —
    `ban_thao.gop_phep_sua` khử trùng mới-thắng lúc gộp. `bo` mang
    `{don_vi, cho_trong, ly_do}` — không bao giờ giá trị: nó đi tới traces (đếm)
    và tới `assemble` (gọi tên chỗ trống).

    `nguon` là lời NGƯỜI HỎI (`_nguon_nguoi`) — không phải chữ của tài liệu; `cam`
    là giá trị đã nhớ mà lượt này không hỏi tới — trừ khi chính nguồn đã có nó.
    `dang_co`: phép của phiên bản đang mở trên khuôn này. Một phép y hệt một phép
    trong đó không phải giá trị MỚI (phép gộp giữ nó), nên bị bỏ qua lặng lẽ — không
    vào `bo`, không qua phép nguồn mà giá trị của một lượt trước sẽ trượt.

    `giá trị bỏ` (`_gia_tri_cua` của mỗi phép bị bỏ, theo thứ tự) CHỈ cho
    `_lay_khong_dat`: giá trị người hỏi đưa mà phép của nó bị bỏ không được mất lặng
    lẽ (G5) — không đi traces hay `bo`.
    """
    nguon_kh = _khong_hoa(nguon or "")
    so_nguon = [v for m in _RE_SO_THUAN.findall(nguon_kh) if (v := tinh(m)) is not None]
    cam_bo = {_khong_hoa(v) for v in cam if v and _khong_hoa(v) not in nguon_kh}
    theo_chi_so = {d.chi_so: d for d in t["don_vi"]}
    da_co = {_khoa_giong(q) for q in dang_co or []}
    giu: list[dict] = []
    bo: list[dict] = []
    gia_tri_bo: list[str] = []
    for p in _tach_ngay(phep if isinstance(phep, list) else [], theo_chi_so):
        if isinstance(p, dict) and _khoa_giong(p) in da_co:
            continue
        ra = _mot_phep(p, theo_chi_so, t["dinh_dang"], nguon_kh, so_nguon, cam_bo)
        if isinstance(ra, dict):
            giu.append(ra)
            continue
        gia_tri_bo += _gia_tri_cua(p, theo_chi_so)
        q = p if isinstance(p, dict) else {}
        bo.append(
            {
                "don_vi": q.get("don_vi") if type(q.get("don_vi")) is int else None,
                "cho_trong": q.get("cho_trong") if type(q.get("cho_trong")) is int else None,
                "ly_do": ra,
            }
        )
    return giu, bo, gia_tri_bo


def _lay_khong_dat(tho: object, loi_nguoi: str, phep: list[dict]) -> list[str]:
    """Giá trị của các phép bị bỏ, rồi `khuon.khong_dat` của mô hình → giá trị người
    hỏi đưa mà chưa đặt được vào chỗ nào. Chỉ giữ mục là CHUỖI CON của lời người hỏi
    (không phân biệt hoa/thường, dấu — `_khong_dau`): lời đáp nhắc lại nó, nên một
    mục mô hình tự nghĩ ra không được lên đó. Bỏ trùng, bỏ mục đã nằm trong một phép
    vừa giữ (mô hình vừa đặt vừa kể)."""
    nguon = _khong_dau(" ".join(loi_nguoi.split()))
    da_dat = [_khong_dau(" ".join(str(p.get("gia_tri") or p.get("noi_dung") or "").split())) for p in phep]
    ra: list[str] = []
    da: set[str] = set()
    for x in tho if isinstance(tho, list) else []:
        v = " ".join(x.split()) if isinstance(x, str) else ""
        k = _khong_dau(v)
        # 120 ký tự: một giá trị điền là một dòng; dài hơn là một câu, không phải giá trị.
        if v and len(v) <= 120 and k in nguon and k not in da and not any(k in s for s in da_dat):
            da.add(k)
            ra.append(v)
    return ra


def _dong_tai_cho(
    d: DonViVanBan, cho: list[ChoTrong], hien: dict[tuple[int, int], str], thay: dict[tuple[int, int | None], str]
) -> str | None:
    """Chữ của đơn vị với mỗi chỗ trống điền được đặt TẠI CHỖ của nó — `⟦so⟧`, hay
    `⟦so=«giá trị»⟧` khi bản thảo đang điền — và, đơn vị nhiều đoạn, mỗi đoạn mở
    bằng `¶doan` (chỉ số thô, đoạn rỗng vẫn được đếm). Dãy chấm của chỗ trống
    nhường chỗ cho dấu; `tab` thì dấu đứng ngay sau nhãn. Đoạn bản thảo đang mở đã
    `thay` hiện chữ mới (`_dang_thay`; `cho` đã bỏ chỗ trống của nó).

    `None` khi vị trí KHÔNG chứng minh được — không `doan_chu` (dòng cũ, PDF), chữ
    các đoạn ghép lại khác `noi_dung`, hay một chỗ trống không còn đúng là dãy chấm
    ở `[dau:cuoi]` của đoạn nó: người gọi giữ dòng `chỗ trống:` cũ cho đơn vị ấy.
    Đặt dấu sai chỗ là đúng lỗi owner đo được, nên không có đường đoán nào."""
    doan = d.doan_chu
    if not doan or " ".join(s.strip() for s in doan if s.strip()) != d.noi_dung:
        return None
    theo_doan: dict[int, list[ChoTrong]] = {}
    for c in cho:
        s = doan[c.doan] if c.doan < len(doan) else None
        if s is None or c.cuoi > len(s) or (c.kieu == "cham" and not _la_cham(s[c.dau : c.cuoi])):
            return None
        theo_doan.setdefault(c.doan, []).append(c)
    phan = []
    for j, s in enumerate(doan):
        s = thay.get((d.chi_so, j), s)
        ra, truoc = [], 0
        # Cùng thứ tự đọc của bộ đọc: `tab` đứng trước dãy chấm bắt đầu cùng chỗ.
        for c in sorted(theo_doan.get(j, []), key=lambda c: (c.dau, c.kieu == "cham")):
            if c.dau < truoc:
                return None
            v = hien.get((d.chi_so, c.so), "").strip()
            dau = f"⟦{c.so}" + (f"=«{v}»" if v else "") + "⟧"
            if c.kieu == "tab":
                dau = ("" if not s[: c.dau] or s[c.dau - 1].isspace() else " ") + dau
                dau += "" if c.dau >= len(s) or s[c.dau].isspace() else " "
            ra += [s[truoc : c.dau], dau]
            truoc = c.cuoi
        if chu := ("".join(ra) + s[truoc:]).strip():
            phan.append(f"¶{j} {chu}" if len(doan) > 1 else chu)
    return " ".join(phan)


def _khoi_tai_lieu(goi: list[dict], ban_thao_dang_mo: dict | None = None) -> str:
    """Khối `{tai_lieu}` của prompt. Tài liệu có khuôn gốc đặt mỗi chỗ điền được
    TẠI CHỖ trong câu (`_dong_tai_cho`); đơn vị nào không chứng minh được vị trí
    thì thêm, dưới nó, một dòng `chỗ trống:` (số, «nhãn» và — lượt sửa — giá trị
    đang điền) như trước. Tài liệu không có khuôn gốc ra đúng từng byte như trước."""
    dong = []
    for t in goi:
        khuon = co_khuon(t)
        dong.append(
            f"## Tài liệu {t['nhan']} — {t['ten_tep']}"
            + (f" (khuôn gốc {t['dinh_dang']}, {t.get('so_trang') or '?'} trang)" if khuon else "")
        )
        hien = _dang_dien(ban_thao_dang_mo, t["id"]) if khuon else {}
        thay = _dang_thay(ban_thao_dang_mo, t["id"]) if khuon else {}
        for d in t["gui"]:
            # Cả đơn vị đã viết lại — đơn vị không `doan_chu` là một đoạn, `doan` 0 là nó.
            moi = thay.get((d.chi_so, None), None if d.doan_chu else thay.get((d.chi_so, 0)))
            if moi is not None:
                dong.append(f"[{t['nhan']}-{d.chi_so}] ({_vi_tri(d)}) {moi}")
                continue
            cho = [c for c in _cho_dien_duoc(d, t["dinh_dang"]) if (d.chi_so, c.doan) not in thay] if khuon else []
            if khuon and (tai_cho := _dong_tai_cho(d, cho, hien, thay)) is not None:
                dong.append(f"[{t['nhan']}-{d.chi_so}] ({_vi_tri(d)}) {tai_cho}")
                # Ô rỗng (`o`, G5): dấu đứng một mình trong ô, nên tên cột và số dòng
                # của nó đi ở dòng `chỗ trống:` ngay dưới.
                if o := [c for c in cho if c.kieu == "o"]:
                    dong.append("  chỗ trống: " + " | ".join(f"{c.so} «{c.nhan}»" for c in o))
                continue
            dong.append(f"[{t['nhan']}-{d.chi_so}] ({_vi_tri(d)}) {d.noi_dung}")
            if cho:
                dong.append(
                    "  chỗ trống: "
                    + " | ".join(
                        f"{c.so} «{c.nhan}»" + (f" = «{v}»" if (v := hien.get((d.chi_so, c.so), "").strip()) else "")
                        for c in cho
                    )
                )
    return "\n".join(dong)


# Phase 3 (Half A, R4) — lượt `sua_ban_thao` KHÔNG được để mô hình tưởng nó
# đang soạn LẠI TỪ ĐẦU từ tài liệu nguồn: nếu hội thoại này đã có một bản
# thảo tổng quát, `hieu_tai_lieu()` cho mô hình thấy CHÍNH bản thảo đó (không
# chỉ tài liệu nguồn), và nói thẳng khi nó đã bị NGƯỜI DÙNG sửa tay — một mô
# hình tin rằng chính nó viết ra câu đó sẽ âm thầm viết đè lên câu người dùng
# vừa gõ (đúng cảnh báo brief nêu). Rỗng khi hội thoại chưa có bản thảo tổng
# quát nào — `.format()` vẫn chạy bình thường vì nối một chuỗi rỗng, không đổi
# hành vi của mọi lượt khác (`tom_tat`/`hoi`/… không đọc mục này).
def _khoi_ban_thao_dang_co(bt: dict | None) -> str:
    if not bt or not bt.get("document"):
        return ""
    da_sua_tay = bool((bt.get("audit") or {}).get("sua_tay"))
    canh_bao = (
        "Phần dưới đây đã có chỗ do NGƯỜI DÙNG tự tay sửa lại (không phải bạn soạn ra) — "
        "KHÔNG được coi câu người dùng viết là câu của chính bạn. GIỮ NGUYÊN từng câu người "
        "dùng đã viết, chỉ áp dụng đúng phần lượt này yêu cầu đổi.\n"
        if da_sua_tay
        else "Đây là bản thảo bạn đã soạn ở lượt trước — coi nó là NỀN để sửa, không phải bắt "
        "đầu lại từ tài liệu nguồn.\n"
    )
    return f"\n# Bản thảo đang có\n\n{canh_bao}\n{bt['document']}\n"


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
    """Đọc `tai_lieu` (mỗi phần tử `{id, ten_tep, don_vi}`, cộng `co_khuon_goc`/
    `dinh_dang`/`so_trang`/`viec_id` khi tài liệu có khuôn gốc) trả lời câu hỏi của lượt.

    Trả về state cộng `tai_lieu_ket`, `muc_dich_tai_lieu`, `tai_lieu_neo`,
    `van_ban_tong_quat` hoặc — tài liệu có khuôn gốc — `khuon_tong_quat`,
    `bo_nho_moi` (điều người hỏi vừa tự khai, chờ ghi) và `traces`. Người gọi (`graph_tra_cuu`) lo phần DB — nạp `don_vi` theo chủ sở
    hữu — đúng hợp đồng "node lo phần DB, hàm lo phần suy nghĩ" mà `assemble` đã
    lập.
    """
    prior_traces = state.get("traces") or {}
    cau_hoi = state.get("cau_hoi_day_du") or state.get("query") or ""
    # Fix round 1 (review HIGH) — lời NGƯỜI HỎI, tách hẳn khỏi `cau_hoi`. Từ
    # lượt 2 trở đi `giai_nghia` GHI ĐÈ `query` bằng một câu do MÔ HÌNH viết
    # lại, nên `cau_hoi` ở trên là chữ của mô hình chứ không phải của người
    # dùng. Rút ký ức từ đó là ghi vào TÀI KHOẢN một cái tên mô hình nhặt ở lượt
    # trước (đo được: `ho_ten` của tài khoản bị thay bằng tên người thứ ba, và
    # lượt ấy còn báo "Tôi đã nhớ Họ và tên"), còn gác "lượt này có hỏi tới
    # không" bằng đó là để mô hình tự cấp phép xả ký ức vào văn bản. Hai phép ấy
    # — và CHỈ hai phép ấy — chạy trên `cau_hoi_nguoi`; phần ĐỌC tài liệu vẫn
    # dùng `cau_hoi` đã giải nghĩa, vì ở đó ngữ cảnh lượt trước là thứ cần.
    cau_hoi_nguoi = state.get("cau_hoi_goc") or state.get("query") or ""
    # Khuôn gốc (P4b): ≤10 trang thật đã được cam kết lúc tải lên, nên gửi TRỌN —
    # kể cả ô bảng rỗng, chỗ duy nhất một phép `thay` điền được một hàng danh
    # sách. Trần chi phí bên dưới vẫn từ chối (`QUA_DAI`) thay vì cắt ngầm.
    # Nhãn chỗ trống qua `nhan_sach_don_vi`: hàng lưu TRƯỚC bộ đọc làm sạch nhãn
    # mang nhãn thô, còn prompt, "Còn trống" và `khong_khop_nhan` phải gọi ô đúng
    # tên trang hiện (`ban_thao.cho_trong_khuon`).
    tai_lieu = [{**t, "don_vi": nhan_sach_don_vi(t["don_vi"])} if co_khuon(t) else t for t in tai_lieu]
    goi = [
        {**t, "nhan": NHAN[i], "gui": list(t["don_vi"]) if co_khuon(t) else loc_don_vi(t["don_vi"], cau_hoi)}
        for i, t in enumerate(tai_lieu[: len(NHAN)])
    ]
    da_dung = [{"id": t["id"], "ten_tep": t["ten_tep"], "nhan": t["nhan"]} for t in goi]
    so_don_vi = sum(len(t["gui"]) for t in goi)
    # Phase 14 — soạn tự do: không tài liệu, nhưng router (ý kiến ĐỘC LẬP, xem
    # `_muc_dich_soan_da_xac_nhan`) đã nói đây là một lượt soạn thảo. Chỉ ca này
    # mới được gọi mô hình với khối tài liệu rỗng (`KHONG_TAI_LIEU`); mọi lượt
    # không-tài-liệu khác vẫn nói thật là chưa đọc được, không gọi gì.
    soan_tu_do = not goi and state.get("intent") == Intent.soan_thao
    # Lượt này đi đường KHUÔN GỐC (prompt v2, lược đồ `khuon`) khi có tài liệu
    # mang khuôn gốc. ponytail: một hội thoại trộn tài liệu cũ (không khuôn) với
    # tài liệu mới chỉ soạn được trên tài liệu mới — enum `khuon.tai_lieu` chỉ
    # có nhãn khuôn gốc; mở thêm `van_ban` khi đo thấy ca ấy xảy ra thật.
    goi_khuon = [t for t in goi if co_khuon(t)]
    # Ký ức tài khoản (Phase 12 part B) — `graph_tra_cuu` đã nạp sẵn, vì node
    # này thuần và không chạm DB. Chia làm hai NGAY ở đây, MỘT lần, để không có
    # hai bản sao của cùng một quyết định trôi lệch nhau: khoá lượt này hỏi tới
    # thì giá trị của nó là NGUỒN hợp lệ; khoá còn lại đi vào `cam` và không có
    # đường nào vào văn bản.
    nho = state.get("bo_nho_tai_khoan") or []
    hoi_toi = {str(r.get("khoa") or "") for r in nho
               if khoa_duoc_hoi(cau_hoi_nguoi, str(r.get("khoa") or ""))}
    bo_nho_cho_phep = [str(r.get("gia_tri") or "") for r in nho if str(r.get("khoa") or "") in hoi_toi]
    # Fix round 1 (review HIGH) — `thoi_quen` (xưng hô, văn phong, mẫu hay dùng)
    # KHÔNG BAO GIỜ vào `cam`. `_khoi_bo_nho` BẢO mô hình dùng chúng để xưng hô
    # và chọn văn phong, còn nhãn của chúng ("xưng hô", "văn phong") không phải
    # thứ ai gõ ra khi xin soạn một lá đơn — nên `khoa_duoc_hoi` luôn `False` và
    # chúng luôn nằm trong `cam`: thiết kế ra lệnh sinh ra đúng chuỗi mà chính
    # nó đi xoá. Đo được: `xung_ho = "em"` khiến mọi câu mở đầu bằng "em" bị
    # thay thành `[…]`. Thứ R4 cấm là tự ĐIỀN một dữ kiện cá nhân vào ô trống;
    # một thói quen soạn thảo không phải một ô nào để điền.
    bo_nho_cam = [str(r.get("gia_tri") or "") for r in nho
                  if str(r.get("khoa") or "") not in hoi_toi and r.get("loai") != "thoi_quen"]
    khoi_bo_nho = _khoi_bo_nho(nho)

    def _hong(tra_loi: str, nguon: str, usage: Usage | None = None) -> dict:
        # `usage`: chi phí đã trả THẬT cho OpenRouter dù lượt hỏng — traces phải
        # ghi đúng, không phải 0 như trước (Phase 16, Concern 3).
        return {
            **state,
            "tai_lieu_ket": _ket("hoi", None, tra_loi, [], [], [], da_dung),
            "muc_dich_tai_lieu": None,
            "tai_lieu_neo": [],
            "tai_lieu_du_kien_moi": [],
            "bo_nho_moi": [],
            # Lỗi hạ tầng KHÔNG được để lại một văn bản soạn dở của lượt trước:
            # `dung_ban_thao_tong_quat` đọc đúng khoá này để quyết định có lưu.
            "van_ban_tong_quat": None,
            "khuon_tong_quat": None,
            # Lượt soạn tự do hỏng: `assemble._ban_thao_tong_quat` đọc khoá này
            # để nói "chưa soạn được" — không phải "chưa đọc được tài liệu"
            # (không có tài liệu nào). Vượt trần thì do CHÍNH bản thảo đang có,
            # giữ thông điệp riêng của nó (`QUA_DAI_VOI_BAN_THAO`).
            **({"ban_thao_tong_quat_loi": tra_loi if nguon == "vuot_tran" else CHUA_SOAN_DUOC}
               if soan_tu_do else {}),
            "traces": {**prior_traces, "hieu_tai_lieu_nguon": nguon, "hieu_tai_lieu_model": model,
                       "hieu_tai_lieu_so_don_vi_gui": so_don_vi, "hieu_tai_lieu_so_quan_sat_giu": 0,
                       "hieu_tai_lieu_so_quan_sat_bo": 0,
                       "hieu_tai_lieu_token_in": usage.token_in if usage else 0,
                       "hieu_tai_lieu_token_out": usage.token_out if usage else 0,
                       "hieu_tai_lieu_cost_usd": usage.cost_usd if usage else 0.0},
        }

    if not goi and not soan_tu_do:
        # Không tài liệu nào đọc được (id không thuộc người gọi, hoặc S1 chưa
        # lưu `don_vi`): nói thật, KHÔNG gọi mô hình với một prompt rỗng rồi để
        # nó tự nghĩ ra một tài liệu.
        return _hong(CHUA_DOC_DUOC, "khong_co_tai_lieu")

    # Khuôn mẫu (quyết định 2026-09-29 mục 5): mọi lượt soạn không tài liệu mà
    # `graph_tra_cuu` đã chuẩn bị khuôn mẫu ra một tệp .docx — prompt v3, mô hình chỉ
    # viết điều khoản. Thiếu `khuon_mau_ngu_canh` (người gọi trực tiếp node, không qua
    # graph) giữ đường `van_ban` cũ bên dưới.
    if soan_tu_do and state.get("khuon_mau_ngu_canh") is not None:
        return _soan_khuon_mau(
            state, llm, model, cau_hoi, cau_hoi_nguoi, bo_nho_cho_phep, bo_nho_cam, khoi_bo_nho, _hong
        )

    # Fix round 1 (review, cùng I2) — bản thảo đang có (R4) cộng thêm vào
    # CHÍNH prompt này, không phải một prompt riêng — trần chi phí phải đếm cả
    # nó, không chỉ tài liệu nguồn, nếu không một lượt sua_ban_thao có thể tốn
    # gấp đôi trần 0,05 USD/request mà trần đó tồn tại để chặn.
    ban_thao_dang_co = state.get("ban_thao_tong_quat_dang_mo")
    do_dai_ban_thao = len((ban_thao_dang_co or {}).get("document") or "")
    so_ky_tu_vao = sum(len(d.noi_dung) for t in goi for d in t["gui"])
    try:
        # Khối ký ức cũng vào prompt nên cũng phải đếm vào trần chi phí — cùng
        # lý lẽ đã áp cho `do_dai_ban_thao` ở fix round 1.
        kiem_tran_chi_phi_tai_lieu(so_ky_tu_vao + do_dai_ban_thao + len(khoi_bo_nho))
    except VuotTran:
        # Fix round 2 (N3) — thông điệp riêng khi bản thảo góp phần vượt trần,
        # xem chú thích tại `QUA_DAI_VOI_BAN_THAO`.
        return _hong(QUA_DAI_VOI_BAN_THAO if do_dai_ban_thao > 0 else QUA_DAI, "vuot_tran")

    # Bản thảo đang có (Phase 3 R4) đi kèm MỌI lượt gọi, kể cả từng phần khi
    # chia lượt (Phase 16): một lượt sửa cần thấy nền để sửa ở bất kỳ phần nào.
    khoi_ban_thao = _khoi_ban_thao_dang_co(ban_thao_dang_co)
    nhan = [t["nhan"] for t in goi]
    if goi_khuon:
        loai_phep = [lo for lo in LOAI_PHEP["docx"] if any(lo in LOAI_PHEP[t["dinh_dang"]] for t in goi_khuon)]
        luoc_do = schema_khuon(nhan, [t["nhan"] for t in goi_khuon], loai_phep)
    else:
        luoc_do = schema_hieu(nhan)
    usage = None
    try:
        # Phase 16 R2 — tài liệu ĐƠN (so sánh/đối chiếu nhiều tài liệu đi
        # nguyên đường một lượt như trước, không chia: `_khop_bang` chỉ được
        # kiểm chứng an toàn cho một tài liệu tại một thời điểm) và đủ dài để
        # một lượt có nguy cơ cần nhiều token ra hơn `TOI_DA_TOKEN_RA` (đo
        # được, xem `NGUONG_PHAN_KY_TU`) thì chia thành nhiều lượt kế tiếp.
        # Ngắn hơn ngưỡng: ĐÚNG một lượt như trước bản vá này, không đổi hành
        # vi, không đổi chi phí. Khuôn gốc KHÔNG chia: đầu ra là danh sách phép
        # sửa, nhỏ, không phải toàn văn.
        if len(goi) == 1 and so_ky_tu_vao > NGUONG_PHAN_KY_TU and not goi_khuon:
            ra, usage = _hieu_theo_phan(llm, model, cau_hoi, goi, prompt_path or PROMPT_PATH,
                                        khoi_ban_thao, khoi_bo_nho)
        else:
            khoi_tai_lieu = KHONG_TAI_LIEU if soan_tu_do else _khoi_tai_lieu(goi, ban_thao_dang_co)
            duong = prompt_path or (PROMPT_KHUON_PATH if goi_khuon else PROMPT_PATH)
            prompt = duong.read_text(encoding="utf-8").format(
                cau_hoi=cau_hoi,
                tai_lieu=khoi_tai_lieu,
                phan_doan="",
                ban_thao_dang_co=khoi_ban_thao,
                bo_nho=khoi_bo_nho,
            )
            raw, usage = llm.chat(model, messages(prompt), json_schema=luoc_do, max_tokens=TOI_DA_TOKEN_RA)
            ra = json.loads(raw)
            if not isinstance(ra, dict):
                raise TypeError(f"phản hồi phải là object, được {type(ra).__name__}")
    except TruncatedOutputError as e:
        # Phase 16 R3 — đã chia lượt (hoặc tài liệu ngắn nhưng vẫn cắt) mà vẫn
        # cắt cấu trúc: nói thẳng độ dài đo được và hai lối đi thật, không lặp
        # lại lời khuyên "tách nhỏ rồi gửi lại" sai chỗ của `QUA_DAI` cho một
        # biểu mẫu người dùng không tự viết ra.
        logger.warning("hieu_tai_lieu: %d ký tự vượt khả năng dựng lại dù đã chia phần", so_ky_tu_vao)
        return _hong(KHONG_DUNG_LAI_DUOC.format(so_ky_tu=so_ky_tu_vao), "qua_dai_dau_ra", e.usage)
    except json.JSONDecodeError as e:
        # JSON hỏng ở `finish_reason=stop` (đo được một lần trong Phase 16, xem
        # docstring `llm.chat`) — llm.py chỉ thử lại khi `length`, nên ca này
        # rơi tới đây. Ghi `nguon` riêng để đếm được lỗi này, tách khỏi lỗi
        # mạng/khác; thông điệp vẫn là CHUA_DOC_DUOC vì thử lại là lời khuyên
        # đúng cho một phản hồi hỏng không tất định. Đường chia phần gắn `usage`
        # gộp vào lỗi (`_hieu_theo_phan`); đường một lượt đã có `usage` cục bộ
        # từ trước `json.loads`.
        logger.warning("hieu_tai_lieu: model %s trả JSON hỏng dù không bị cắt — %s tại vị trí %d",
                       model, e.msg, e.pos)
        return _hong(CHUA_DOC_DUOC, "json_hong", getattr(e, "usage", usage))
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
            "noi_dung": bo_dau_noi_bo(str(o.get("noi_dung") or "").strip()),
            "trich": trich,
            "neo": _neo_ra(t, neo),
        })

    giu = giu[:TOI_DA_QUAN_SAT]
    muc_dich = str(ra.get("muc_dich") or "hoi")
    if state.get("intent") == Intent.soan_thao and muc_dich not in MUC_DICH_SOAN:
        # Gác trên Ý KIẾN CỦA ROUTER, không trên việc hội thoại có tài liệu hay
        # không. Bản trước gác `soan_tu_do` (= KHÔNG tài liệu), mà điều kiện đó
        # sai ngay khi hội thoại sở hữu một tài liệu: "dựa vào hợp đồng này
        # soạn giúp tôi đơn xin nghỉ việc" đi `hieu_tai_lieu` với tài liệu, mô
        # hình gán `hoi`, nhãn không bao giờ được sửa, và lượt chết ở
        # `assemble._ban_thao_tong_quat` với "Lượt này tôi chưa soạn được mục
        # nào." — đúng ngõ cụt R1 đã gỡ, vào lại bằng cửa sau. Router đã nói
        # soạn thảo thì một nhãn khác từ mô hình NÀY là gán nhầm, dù có tài
        # liệu hay không.
        #
        # `doi_chieu_luat` cũng bị sửa, CÓ CHỦ Ý: `assemble` rẽ theo `intent`
        # (`intent == "soan_thao"`) nên một lượt router đã gọi là soạn thảo
        # KHÔNG bao giờ được dựng thành câu trả lời pháp lý — để nó chạy hết
        # rewrite → retrieve → expand → generate → hai tầng kiểm là trả tiền
        # năm lượt gọi cho một kết quả `assemble` vứt đi. Không câu trả lời đã
        # kiểm nào bị bỏ ở đây, vì không câu nào được dựng: R4 nguyên vẹn.
        #
        # Có bản thảo đang mở thì lượt xin SỬA nó, không mở một bản thứ hai;
        # `van_ban` rỗng thì `dung_ban_thao_tong_quat` nói thật "chưa soạn được
        # mục nào".
        muc_dich = "sua_ban_thao" if khoi_ban_thao else "tao_van_ban"
    # Phase 3 Half B, fix round 1 — safety net: một `muc_dich` SOẠN (có thể
    # GHI ĐÈ bản thảo thật) không đủ tin nếu ý kiến ĐỘC LẬP của `route()` (nếu
    # có chạy cho lượt này) không CŨNG là `Intent.soan_thao` — xem
    # `_muc_dich_soan_da_xac_nhan`. Hạ về `hoi` TRƯỚC khi bất cứ điều gì dưới
    # đây (kể cả `lam_sach_van_ban`) chạy trên nó, để
    # `_re_sau_hieu_tai_lieu`/`dung_ban_thao_tong_quat` không bao giờ thấy
    # được một `sua_ban_thao`/`tao_van_ban` chưa được xác nhận.
    tin_soan = muc_dich in MUC_DICH_SOAN
    if muc_dich in MUC_DICH_SOAN and not _muc_dich_soan_da_xac_nhan(state.get("intent")):
        muc_dich = "hoi"
    # Khuôn gốc (P4b): phép sửa thay cho `van_ban`, kiểm trước khi bất cứ gì được
    # lưu. Nguồn là LỜI NGƯỜI HỎI (`_nguon_nguoi`, luật owner 2026-09-27) — không chữ
    # tài liệu, không `truong`: giá trị của một trường chỉ được neo qua đoạn trích,
    # không qua chính nó (xem chú thích `cam_kh` bên dưới).
    k_ra = ra.get("khuon") if isinstance(ra.get("khuon"), dict) else {}
    t_k = (
        {t["nhan"]: t for t in goi_khuon}.get(str(k_ra.get("tai_lieu") or ""))
        or (goi_khuon[0] if len(goi_khuon) == 1 else None)
        if goi_khuon
        else None
    )
    soan_khuon, chua_dien = False, None
    # Lời mô hình tự nhận đã thay đổi gì đó ("Tôi đã điền …"): chỉ đi ra ở lượt soạn.
    da_lam = bool(_RE_DA_LAM.search(unicodedata.normalize("NFC", str(ra.get("tra_loi_ngan") or ""))))
    phep, bo, khong_dat, gia_tri_bo, de_xuat, yeu_cau = [], [], [], [], [], "dien_sua"
    if t_k is not None:
        # Thiếu hay lạ (kể cả `van_ban_nay` của lược đồ cũ) là `dien_sua` (`YEU_CAU`).
        yeu_cau = k_ra.get("yeu_cau") if k_ra.get("yeu_cau") in YEU_CAU else "dien_sua"
        de_xuat = k_ra.get("phep_sua") if isinstance(k_ra.get("phep_sua"), list) else []
        phep, bo, gia_tri_bo = kiem_phep_sua(
            de_xuat, t_k, _nguon_nguoi(state, bo_nho_cho_phep), bo_nho_cam, _phep_dang_mo(ban_thao_dang_co, t_k["id"])
        )
        # G7 (owner 2026-09-28, Q4): trên khuôn gốc, lượt soạn hay không quyết định bằng
        # chứng cứ tất định — thay cho gác router ở trên, CHỈ ở đây.
        tin_soan = tin_soan or bool(de_xuat)
        soan_khuon, yeu_cau = _quyet_khuon(cau_hoi_nguoi, muc_dich in MUC_DICH_SOAN, tin_soan, yeu_cau, bool(phep))
        # `tao_lai` BỎ mọi phép đề xuất, tất định: "bảo soạn thảo văn bản ra thì phải
        # đúng 100%" — bản thảo là chính tệp tải lên.
        if soan_khuon and yeu_cau == "tao_lai":
            phep, bo, gia_tri_bo = [], [], []
        if yeu_cau == "dien_sua":
            # Giá trị của phép BỊ BỎ đứng trước danh sách của mô hình (G5): tên đặt
            # sai cột không được mất lặng lẽ khi mô hình tưởng đã đặt được nó.
            tho = [*gia_tri_bo, *(k_ra.get("khong_dat") if isinstance(k_ra.get("khong_dat"), list) else [])]
            khong_dat = _lay_khong_dat(tho, _loi_nguoi_hoi(state), phep)
        if soan_khuon:
            dang_mo = str((ban_thao_dang_co or {}).get("viec_id") or "") == t_k["id"]
            muc_dich = muc_dich if muc_dich in MUC_DICH_SOAN else ("sua_ban_thao" if dang_mo else "tao_van_ban")
        else:
            muc_dich = "hoi" if muc_dich in MUC_DICH_SOAN else muc_dich
            # Lượt ai đó tưởng là soạn (mô hình, router, hay một phép đề xuất) mà không áp
            # gì, hay lời mô hình tự nhận đã điền: câu cố định nói thật, không bao giờ lời
            # "Tôi đã điền …" của mô hình.
            if tin_soan or da_lam:
                chua_dien = chua_dien_khuon(t_k["ten_tep"], bo, bool(phep), bool(de_xuat), khong_dat)
    elif goi_khuon and muc_dich not in MUC_DICH_SOAN and (tin_soan or da_lam):
        # Nhiều biểu mẫu, mô hình không nêu biểu mẫu nào: không áp gì, hỏi lại.
        ds = ", ".join(f"«{t['ten_tep']}»" for t in goi_khuon)
        chua_dien = CHUA_RO_KHUON.format(so=len(goi_khuon), ds=ds)
    if chua_dien is None and da_lam and muc_dich not in MUC_DICH_SOAN:
        # Mọi đường hỏi đáp khác (gác cũ trên bản HTML, tài liệu không khuôn gốc).
        chua_dien = CHUA_THAY_DOI
    phep_tinh, phep_tinh_bo = _lay_phep_tinh(ra, goi)
    truong, truong_bo = _lay_truong(ra, goi)
    # Fix round 1 (review HIGH) — `_lay_truong` kiểm ĐOẠN TRÍCH neo được về tài
    # liệu, nó KHÔNG kiểm giá trị. Một biểu mẫu có dòng trắng "Họ và tên:" cho
    # mô hình đúng một đoạn trích THẬT để neo vào, rồi nó điền giá trị ĐÃ NHỚ
    # vào `gia_tri` của dòng ấy. Từ đó dòng đi HAI đường cùng lúc: xuống
    # `du_kien_tai_lieu` (thành "dữ kiện của tài liệu" — R4 cấm ký ức thành
    # facts) và vào `_nguon_soan`, nơi nó tự cấp phép cho chính mình nên `cam`
    # hết hiệu lực và giá trị ra tới trang giấy. Bỏ dòng TRƯỚC cả hai đường,
    # tại đúng chỗ duy nhất cả hai cùng đi qua. Gập hoa/thường vì `cam` bên
    # dưới cũng gập — hai phép gác cùng một ký ức phải cùng một độ chặt.
    cam_kh = {_khong_hoa(v) for v in bo_nho_cam if v}
    if cam_kh:
        truong = [o for o in truong if _khong_hoa(str(o.get("gia_tri") or "")) not in cam_kh]
    # Chỉ lượt SO SÁNH mới có khác biệt: một danh sách "khác biệt" trong lượt
    # tóm tắt là nội dung mô hình tự thêm vào, không phải thứ ai hỏi.
    khac_biet, khac_biet_bo = _lay_khac_biet(ra, goi) if muc_dich == "so_sanh" else ([], 0)
    # Chỉ lượt ĐỐI CHIẾU mới lấy điều khoản: cùng lý lẽ `khac_biet` ngay trên —
    # một danh sách điều khoản trong lượt tóm tắt là hình dạng được điền cho đủ,
    # không phải thứ ai hỏi, và nó sẽ kéo cả lượt sang đường pháp lý.
    dieu_khoan, dieu_khoan_bo = _lay_dieu_khoan(ra, goi) if muc_dich == "doi_chieu_luat" else ([], 0)
    # Văn bản mới CHỈ ở hai lượt soạn (S6), và chỉ sau khi mọi giá trị trong nó
    # được tra ngược về nguồn của lượt. Ra khỏi chỗ này rồi thì nó là dữ liệu
    # thuần — `dung_ban_thao_tong_quat` không phải biết gì về mô hình nữa.
    van_ban, van_ban_dem = (
        lam_sach_van_ban(ra.get("van_ban") or {}, _nguon_soan(goi, state, truong, giu, bo_nho_cho_phep),
                         goi, bo_nho_cam)
        if muc_dich in MUC_DICH_SOAN and not goi_khuon
        else (None, {"muc_lam_sach": 0, "gia_tri_lam_sach": 0, "muc_bo": 0, "bo_nho_khong_dien": 0})
    )
    khuon_tong_quat, khuon_dem = None, {}
    if soan_khuon:
        khuon_tong_quat = {
            "viec_id": t_k["id"],
            "ten_tep": t_k["ten_tep"],
            "dinh_dang": t_k["dinh_dang"],
            "so_trang": t_k.get("so_trang"),
            "yeu_cau": yeu_cau,
            "phep_sua": phep,
            "bo_qua": bo,
            "khong_dat": khong_dat,
            "cho_trong": cho_trong_khuon(t_k),
            # Lời xin điền/sửa mà không phép nào qua kiểm (G7): không dựng phiên bản 1
            # nào cho nó (`dung_ban_thao_tong_quat`) — bản đã có thì vẫn là bản đang có.
            **({"xin_dien_rong": True} if yeu_cau == "dien_sua" and not phep and xin_dien_sua(cau_hoi_nguoi) else {}),
        }
        khac, tao_lai = yeu_cau == "van_ban_khac", yeu_cau == "tao_lai"
        khuon_dem = {
            "khuon_so_phep_giu": len(phep),
            "khuon_so_phep_bo": len(bo),
            **{f"khuon_bo_{ly}": n for ly, n in Counter(b["ly_do"] for b in bo).items()},
            # `van_ban_khac` không dựng gì (`dung_ban_thao_tong_quat`): mọi phép
            # đã qua phép kiểm của lượt ấy cũng bị bỏ — đếm để thấy phân loại sai.
            "khuon_yeu_cau_khac": int(khac),
            "khuon_so_phep_bo_yeu_cau_khac": len(phep) if khac else 0,
            # `tao_lai` bỏ mọi phép ĐỀ XUẤT: đếm để thấy một lượt điền bị gọi nhầm là
            # dựng lại.
            "khuon_tao_lai": int(tao_lai),
            "khuon_so_phep_bo_tao_lai": len(de_xuat) if tao_lai else 0,
            "khuon_so_khong_dat": len(khong_dat),
        }
    # R5 — 0 token: dữ kiện người dùng tự khai đọc từ CHÍNH câu họ gõ, và chỉ ở
    # lượt SOẠN (nơi họ đang khai để dựng một văn bản). `graph_tra_cuu` ghi
    # xuống DB, đúng con đường `tai_lieu_du_kien_moi` đã đi — node này thuần.
    bo_nho_moi = rut_bo_nho(cau_hoi_nguoi) if muc_dich in MUC_DICH_SOAN else []
    can_du_kien = [s for x in (ra.get("can_du_kien") or []) if (s := bo_dau_noi_bo(str(x).strip()))]
    # Thiếu tài liệu để so: quyết định bằng LỜI NGƯỜI HỎI hoặc nhãn của mô hình,
    # cái nào đúng cũng đủ — xem `xin_so_sanh`.
    thieu_de_so = len(goi) < 2 and (muc_dich == "so_sanh" or xin_so_sanh(cau_hoi))
    if thieu_de_so and CAN_TAI_LIEU_THU_HAI not in can_du_kien:
        can_du_kien.append(CAN_TAI_LIEU_THU_HAI)
    # Xin đối chiếu mà không neo được điều khoản nào ⇒ hành xử như `hoi`, và nói
    # ra. KHÔNG đẩy một danh sách rỗng vào đường pháp lý: ở đó không còn dữ kiện
    # nào của người hỏi, nên câu trả lời sẽ là một bài giảng luật chung chung
    # đội lốt một lượt đối chiếu.
    lam_duoc = muc_dich in MUC_DICH_LAM_DUOC and (muc_dich != "doi_chieu_luat" or bool(dieu_khoan))
    tra_loi = chua_dien or bo_dau_noi_bo(str(ra.get("tra_loi_ngan") or "").strip())
    if muc_dich == "doi_chieu_luat" and not dieu_khoan:
        tra_loi = "\n\n".join(x for x in (tra_loi, DOI_CHIEU_KHONG_NEO) if x)
    # THAY hẳn, không nối thêm: văn xuôi ở đây khẳng định một so sánh với một
    # tài liệu không tồn tại, nên giữ lại nó rồi đính chính bên dưới là vẫn để
    # câu khẳng định ấy đứng đầu câu trả lời.
    if thieu_de_so:
        tra_loi = SO_SANH_THIEU_TAI_LIEU
    ket = {
        **state,
        # Mục đích THẬT mô hình đọc được, kể cả cái lát cắt này chưa làm — S6 rẽ
        # nhánh trên khoá này.
        "muc_dich_tai_lieu": muc_dich if muc_dich in MUC_DICH else None,
        "tai_lieu_ket": _ket(
            muc_dich if lam_duoc else "hoi",
            bo_dau_noi_bo(str(ra.get("mo_ta") or "").strip()) or None,
            tra_loi,
            giu,
            [s for x in (ra.get("suy_luan") or []) if (s := bo_dau_noi_bo(str(x).strip()))][:TOI_DA_SUY_LUAN],
            can_du_kien,
            da_dung,
            phep_tinh,
            khac_biet,
        ),
        # Điều khoản đưa sang đường pháp lý, mỗi cái mang neo của nó.
        "tai_lieu_neo": dieu_khoan,
        # Văn bản đã làm sạch cho `dung_ban_thao_tong_quat` (S6).
        "van_ban_tong_quat": van_ban,
        # Phép sửa đã kiểm trên khuôn gốc (P4b) — `None` ở mọi lượt khác.
        "khuon_tong_quat": khuon_tong_quat,
        # Dữ kiện MỚI, chưa ghi: node thuần không chạm DB (`graph_tra_cuu` lo).
        "tai_lieu_du_kien_moi": truong,
        # Điều người hỏi vừa tự khai về họ, chưa ghi — cùng lý do ngay trên.
        "bo_nho_moi": bo_nho_moi,
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
            "hieu_tai_lieu_so_dieu_khoan": len(dieu_khoan),
            "hieu_tai_lieu_so_dieu_khoan_bo": dieu_khoan_bo,
            # Đếm, không chép (S6): bao nhiêu mục đã soạn, bao nhiêu mục phải
            # chừa trống, bao nhiêu giá trị bịa bị thay, bao nhiêu mục bị bỏ vì
            # còn vướng lưới chặn. Không khoá nào mang chữ của bản thảo.
            "dung_ban_thao_so_muc": len((van_ban or {}).get("muc") or []),
            "dung_ban_thao_so_muc_lam_sach": van_ban_dem["muc_lam_sach"],
            "dung_ban_thao_so_gia_tri_lam_sach": van_ban_dem["gia_tri_lam_sach"],
            "dung_ban_thao_so_muc_bo": van_ban_dem["muc_bo"],
            # Đếm, không chép (Phase 12 part B): bao nhiêu lần mô hình tự điền
            # một điều đã nhớ mà lượt này không hỏi tới — con số duy nhất đo
            # được rằng lưới "nhớ, không tự điền" đang cắn thật, và bao nhiêu
            # điều người hỏi vừa khai. Không khoá nào mang giá trị đã nhớ.
            "dung_ban_thao_so_bo_nho_chan": van_ban_dem["bo_nho_khong_dien"],
            "bo_nho_so_khai": len(bo_nho_moi),
            # Đếm, không chép (P4b): phép sửa giữ/bỏ theo lý do, chỉ ở lượt khuôn gốc.
            **khuon_dem,
            "hieu_tai_lieu_token_in": usage.token_in if usage else 0,
            "hieu_tai_lieu_token_out": usage.token_out if usage else 0,
            "hieu_tai_lieu_cost_usd": usage.cost_usd if usage else 0.0,
        },
    }
    if dieu_khoan:
        # Đúng quy ước `giai_nghia`: `query` là câu CẢ PIPELINE chạy trên, và ở
        # lượt này nó phải là câu hỏi PHÁP LÝ của điều khoản; `cau_hoi_goc` giữ
        # câu người hỏi gõ, để prompt hành văn còn trả lời đúng người trước mặt.
        # `cau_hoi_goc` có sẵn (lượt nối tiếp đã qua `giai_nghia`) thì không ghi
        # đè — ở đó `query` đã là câu giải nghĩa, không phải câu người ta gõ.
        ket["cau_hoi_goc"] = state.get("cau_hoi_goc") or state.get("query") or ""
        ket["cau_hoi_day_du"] = cau_hoi_doi_chieu(dieu_khoan)
        ket["query"] = ket["cau_hoi_day_du"]
    return ket


# ═══ Khuôn mẫu — soạn tự do thành một tệp .docx (thiết kế `khuon-mau-thiet-ke.md` §4, §6) ═══
#
# Lượt SOẠN không tài liệu (`soan_tu_do`) mà `graph_tra_cuu` đã chuẩn bị khuôn mẫu
# (`khuon_mau_ngu_canh`: loại registry hay tự soạn, các mục checklist, căn cứ, bản thảo
# đang có) đi prompt v3: mô hình chỉ viết ĐIỀU KHOẢN và chỉ ra giá trị người hỏi nói
# cho trường nào của bên nào; khung do `khuon_mau.dung_docx` dựng. Một lượt gọi, rồi
# `kiem_khuon_mau` (0 token) làm sạch — ra khỏi đây chữ điều khoản không mang số điều
# luật, số hiệu, danh tính hay giá trị không nguồn nào.

PROMPT_KHUON_MAU_PATH = Path("prompts/hieu_tai_lieu.v3.md")
MUC_TIEU = ("ban_moi", "sua_ban_dang_co")
THAO_TAC = ("thay", "them_sau", "xoa")
# Câu hỏi lại khi lượt sửa không chỉ được Điều nào (§4 bước 5).
CHUA_RO_DIEU = "Tôi chưa xác định được điều cần sửa — hãy nêu số hoặc tên điều."
_RE_KHOA_BEN = re.compile(r"[^a-z0-9_]")
_RE_DIEU_NAY = re.compile(r"\b(?:khoản|điểm)\s+\w+(?:\s*(?:,|và)\s*\w+)*\s+(?:của\s+)?Điều\s+này\b", re.IGNORECASE)
_THAM_CHIEU_LOAI = ("hợp đồng", "văn bản", "quy chế", "nội quy", "quyết định", "thỏa thuận", "thoả thuận", "đơn")
_RE_TIEU_DE_DIEU = re.compile(r"^##\s+Điều\s+(\d+)\.\s*(.*)$", re.MULTILINE)


def schema_khuon_mau(sua: bool, khoa: list[str] | None = None) -> dict:
    """Lược đồ strict của prompt v3 (§6). `sua=False` (không có khuôn mẫu đang mở,
    hay bản cũ là HTML): `muc_tieu` chỉ `ban_moi`, `sua_dieu` chỉ `null` — lượt ấy
    luôn dựng một bản MỚI. `khoa`: mã mục checklist và mục thân của loại."""
    chu = {"type": "string"}
    key = _hoac_null("string") if not khoa else {"anyOf": [{"type": "null"}, {"type": "string", "enum": sorted(khoa)}]}
    dieu = {
        "type": "object",
        "additionalProperties": False,
        "required": ["key", "ten", "doan"],
        "properties": {"key": key, "ten": chu, "doan": {"type": "array", "items": chu}},
    }
    thao_tac = {
        "type": "object",
        "additionalProperties": False,
        "required": ["thao_tac", "dieu", "key", "ten", "doan"],
        "properties": {
            "thao_tac": {"type": "string", "enum": list(THAO_TAC)},
            "dieu": {"type": "integer"},
            "key": key,
            "ten": _hoac_null("string"),
            "doan": {"anyOf": [{"type": "null"}, {"type": "array", "items": chu}]},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "muc_tieu",
            "tieu_de",
            "trich_yeu",
            "bo_cuc",
            "ben",
            "can_cu",
            "gia_tri",
            "dieu",
            "sua_dieu",
            "khong_dat",
        ],
        "properties": {
            "muc_tieu": {"type": "string", "enum": list(MUC_TIEU) if sua else ["ban_moi"]},
            "tieu_de": _hoac_null("string"),
            "trich_yeu": _hoac_null("string"),
            "bo_cuc": {"anyOf": [{"type": "null"}, {"type": "string", "enum": list(khuon_mau.BO_CUC)}]},
            "ben": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["khoa", "vai", "loai"],
                            "properties": {
                                "khoa": chu,
                                "vai": chu,
                                "loai": {"type": "string", "enum": ["ca_nhan", "to_chuc"]},
                            },
                        },
                    },
                ]
            },
            "can_cu": {"anyOf": [{"type": "null"}, {"type": "array", "items": chu}]},
            "gia_tri": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ben", "truong", "gia_tri"],
                    "properties": {
                        "ben": chu,
                        "truong": {"type": "string", "enum": sorted(khuon_mau.truong())},
                        "gia_tri": chu,
                    },
                },
            },
            "dieu": {"anyOf": [{"type": "null"}, {"type": "array", "items": dieu}]},
            "sua_dieu": {"anyOf": [{"type": "null"}, {"type": "array", "items": thao_tac}]}
            if sua
            else {"type": "null"},
            "khong_dat": {"type": "array", "items": chu},
        },
    }


def _chu_giu(i: int) -> str:
    """Mã giữ chỗ CHỈ chữ cái (không số, không @): hai lưới không bao giờ cắn nó."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return f"KLAWGIU{s}Q"


def _luoi_doan(chu: str, nguon: str, cam: list[str]) -> tuple[str | None, int]:
    """MỘT đoạn qua hai lưới (§6 bước 5): lưới chặn (`_vuong_luoi_chan` — số điều luật,
    số hiệu văn bản, dấu vết định danh) BỎ cả đoạn; lưới giá trị (`lam_sach_van_ban`,
    đoạn là một mục của chính nó) đổi mỗi giá trị không nguồn thành "……". "khoản n
    Điều này" (dẫn chiếu trong CHÍNH điều) được che trước cả hai lưới rồi trả lại.
    Trả `(đoạn | None, số giá trị đã thay)`."""
    giu: list[str] = []

    def _che(m: re.Match) -> str:
        giu.append(m.group(0))
        return _chu_giu(len(giu) - 1)

    an = _RE_DIEU_NAY.sub(_che, chu)
    if _vuong_luoi_chan(an):
        return None, 0
    vb, dem = lam_sach_van_ban(
        {"tieu_de": "", "muc": [{"ten": "_", "vung": "than", "khoi": [{"noi_dung": an, "bang": []}]}]}, nguon, None, cam
    )
    khoi = vb["muc"][0]["khoi"] if vb["muc"] else []
    if not khoi:
        return None, 0
    s = khoi[0]["noi_dung"].replace(CHO_TRONG, khuon_mau.CHO)
    for i, g in enumerate(giu):
        s = s.replace(_chu_giu(i), g)
    return khuon_mau.chuan_chu(s)[0], dem["gia_tri_lam_sach"]


def _viet_thuong_dau(s: str) -> str:
    return s[:1].lower() + s[1:]


def _re_tham_chieu(ten_loai: str | None) -> re.Pattern:
    loai = [re.escape(x) for x in {*(_THAM_CHIEU_LOAI), *([ten_loai.lower()] if ten_loai else [])}]
    return re.compile(
        r"\bĐiều\s+(\d+)\s+(?:(?:của|tại)\s+)?(?:" + "|".join(sorted(loai, key=len, reverse=True)) + r")\s+này\b",
        re.IGNORECASE,
    )


def ten_dieu_cua(document: str | None) -> list[str]:
    """Tên các Điều theo SỐ HIỆN TẠI trong `document` của một khuôn mẫu
    (`ban_thao.tom_tat_khuon_mau`) — để một lượt sửa gọi đúng điều bằng số."""
    return [m[2].strip() for m in _RE_TIEU_DE_DIEU.finditer(document or "")]


def _sach_dieu(
    d: dict,
    ten_ds: list[str],
    re_tc: re.Pattern,
    nguon: str,
    cam: list[str],
    khoa: set,
    n: int,
    ghi: list[str],
    dem: Counter,
) -> dict | None:
    """Một điều mô hình viết → điều bộ dựng ghi được, hay `None` khi không còn đoạn nào."""
    ten, so = khuon_mau.chuan_chu(khuon_mau.bo_so_dau(str(d.get("ten") or "")))
    dem["cho_mo_hinh"] += so
    if ten and _vuong_luoi_chan(_RE_DIEU_NAY.sub("", ten)):
        ghi.append(f"Bỏ tên của Điều {n} vì dẫn số điều luật không kiểm được")
        ten = ""
    key = d.get("key") if d.get("key") in khoa else None

    def _doi_ten(m: re.Match) -> str:
        k = int(m[1])
        return f"Điều về {_viet_thuong_dau(ten_ds[k - 1])}" if 1 <= k <= len(ten_ds) and ten_ds[k - 1] else m[0]

    doan_ra = []
    tho = [x for x in d.get("doan") or [] if isinstance(x, str) and x.strip()]
    if tho and ten and normalize(khuon_mau.bo_so_dau(tho[0])).casefold() == normalize(ten).casefold():
        tho = tho[1:]
    for x in tho:
        x, so = khuon_mau.chuan_chu(re_tc.sub(_doi_ten, x))
        dem["cho_mo_hinh"] += so
        if not x:
            continue
        sach, so = _luoi_doan(x, nguon, cam)
        dem["gia_tri_lam_sach"] += so
        if sach is None:
            ghi.append(f"Bỏ 1 đoạn ở Điều {n} vì dẫn số điều luật, số hiệu hay thông tin định danh không kiểm được")
            dem["doan_bo"] += 1
            continue
        if len(sach) > khuon_mau.TOI_DA_KY_TU_DOAN:
            sach = sach[: khuon_mau.TOI_DA_KY_TU_DOAN].rsplit(" ", 1)[0].rstrip(",;:") + "."
            ghi.append(f"Cắt bớt một đoạn quá dài ở Điều {n}")
        doan_ra.append(sach)
    if len(doan_ra) > khuon_mau.TOI_DA_DOAN:
        doan_ra = doan_ra[: khuon_mau.TOI_DA_DOAN]
        ghi.append(f"Điều {n} quá {khuon_mau.TOI_DA_DOAN} đoạn: bỏ các đoạn sau")
    if not doan_ra:
        return None
    return {"key": key, "ten": ten, "doan": doan_ra}


def kiem_khuon_mau(ra: dict, ngu_canh: dict, nguon: str, cam: list[str], ten_cu: list[str]) -> dict:
    """Đầu ra v3 → nội dung đã làm sạch (§6, 0 token, thuần). Thứ tự: bỏ số đầu tên
    Điều → viết lại dẫn chiếu "Điều n <loại> này" theo TÊN (sống qua lần đánh số lại)
    → giữ chỗ và dãy chấm lẻ → hai lưới từng đoạn → trần và ngân sách → điều bắt buộc
    (chỉ lúc tạo) → giá trị các bên (lọc hình dạng; phép kiểm nguồn chạy sau khi dựng,
    trên chính chỗ trống của tệp). Trả `{muc_tieu, khung, dieu, sua_dieu, gia_tri,
    khong_dat, ghi_chu, hoan_thanh, dem}`."""
    sua = bool(ngu_canh.get("sua"))
    muc_tieu = ra.get("muc_tieu") if sua and ra.get("muc_tieu") in MUC_TIEU else "ban_moi"
    loai = ngu_canh.get("loai")
    khung_cu = ngu_canh.get("khung_cu") or {}
    ghi: list[str] = []
    dem: Counter = Counter()

    def _luoi_khung(chu: str, ten: str) -> str | None:
        # Chữ khung mô hình viết (tên loại, trích yếu, vai một bên) in lên trang như chữ
        # điều khoản, nên qua CÙNG hai lưới: lưới chặn bỏ cả trường (người gọi dùng mặc
        # định) và nêu tên; lưới giá trị để "……" chỗ giá trị không nguồn.
        if not chu:
            return None
        sach, so = _luoi_doan(chu, nguon, cam)
        dem["gia_tri_lam_sach"] += so
        if sach is None:
            ghi.append(f"Bỏ {ten} vì dẫn số điều luật, số hiệu hay thông tin định danh không kiểm được")
        return sach or None

    # Khung: loại registry lấy từ dữ liệu; tự soạn lấy lời mô hình lúc TẠO, giữ khung
    # đã lưu lúc SỬA (sửa điều khoản không đổi loại văn bản hay các bên).
    if muc_tieu == "sua_ban_dang_co":
        khung = {k: khung_cu.get(k) for k in ("loai", "bo_cuc", "tieu_de", "trich_yeu", "ben")}
        khung["can_cu"] = khung_cu.get("can_cu") or []
    elif loai:
        khung = {
            "loai": loai,
            "bo_cuc": ngu_canh.get("bo_cuc"),
            "tieu_de": ngu_canh.get("tieu_de"),
            "trich_yeu": None,
            "ben": ngu_canh.get("ben") or [],
            "can_cu": ngu_canh.get("can_cu") or [],
        }
        if ngu_canh.get("co_trich_yeu"):
            khung["trich_yeu"] = _luoi_khung(khuon_mau.chuan_chu(str(ra.get("trich_yeu") or ""))[0][:200], "trích yếu")
    else:
        bo_cuc = ra.get("bo_cuc") if ra.get("bo_cuc") in khuon_mau.BO_CUC else "hop_dong"
        # Văn bản hành chính: cơ quan ban hành và người ký là HAI bên cố định của khung
        # (`khung_tong_quat`) — chỗ trống trên tệp mang đúng hai khoá đó, không khoá mô
        # hình tự đặt.
        co_dinh = khuon_mau.khung_tong_quat("hanh_chinh", [])["ben"] if bo_cuc == "hanh_chinh" else []
        ben, da = [{k: b[k] for k in ("khoa", "vai", "loai")} for b in co_dinh], set()
        for b in [] if co_dinh else ra.get("ben") or []:
            if not isinstance(b, dict):
                continue
            k = (
                _RE_KHOA_BEN.sub("_", _bo_dau(str(b.get("khoa") or "")).lower()).strip("_")[:30]
                or f"ben_{len(ben) + 1}"
            )
            if k in da or k == khuon_mau.BEN_VAN_BAN:
                continue
            da.add(k)
            ben.append(
                {
                    "khoa": k,
                    "vai": _luoi_khung(khuon_mau.chuan_chu(str(b.get("vai") or ""))[0], "tên gọi của một bên"),
                    "loai": "to_chuc" if b.get("loai") == "to_chuc" else "ca_nhan",
                }
            )
        tieu_de, _ = khuon_mau.chuan_chu(khuon_mau.bo_so_dau(str(ra.get("tieu_de") or "")))
        khung = {
            "loai": None,
            "bo_cuc": bo_cuc,
            "tieu_de": (_luoi_khung(tieu_de, "tên văn bản") or "")[:150] or "Văn bản",
            "trich_yeu": _luoi_khung(khuon_mau.chuan_chu(str(ra.get("trich_yeu") or ""))[0][:200], "trích yếu"),
            "ben": ben[:8],
            "can_cu_so": [s.strip() for s in ra.get("can_cu") or [] if isinstance(s, str) and s.strip()][:8],
        }
    khoa = set(ngu_canh.get("khoa") or [])
    re_tc = _re_tham_chieu(khung.get("tieu_de"))

    def _sach_ds(ds: list, ten_ds: list[str]) -> list[dict]:
        ra_ds = []
        for n, d in enumerate(ds, 1):
            if isinstance(d, dict) and (x := _sach_dieu(d, ten_ds, re_tc, nguon, cam, khoa, n, ghi, dem)):
                ra_ds.append(x)
        return ra_ds

    dieu = sua_dieu = None
    if isinstance(ra.get("dieu"), list) and (muc_tieu == "ban_moi" or ra["dieu"]):
        ten_moi = [khuon_mau.bo_so_dau(str((d or {}).get("ten") or "")) for d in ra["dieu"] if isinstance(d, dict)]
        dieu = _sach_ds(ra["dieu"], ten_moi)
    elif muc_tieu == "sua_ban_dang_co" and isinstance(ra.get("sua_dieu"), list):
        sua_dieu = []
        for op in ra["sua_dieu"]:
            if not isinstance(op, dict) or op.get("thao_tac") not in THAO_TAC or type(op.get("dieu")) is not int:
                continue
            n = op["dieu"]
            if not (0 if op["thao_tac"] == "them_sau" else 1) <= n <= len(ten_cu):
                ghi.append(CHUA_RO_DIEU)
                continue
            if op["thao_tac"] == "xoa":
                sua_dieu.append({"thao_tac": "xoa", "dieu": n})
                continue
            x = _sach_dieu(op, ten_cu, re_tc, nguon, cam, khoa, max(n, 1), ghi, dem)
            if x is None:
                ghi.append(f"Chưa sửa được Điều {max(n, 1)}: nội dung đề xuất không còn đoạn nào dùng được")
                continue
            sua_dieu.append({"thao_tac": op["thao_tac"], "dieu": n, **x})
    # Loại có mục thân cố định (đơn, công văn) mà không có danh sách Điều: điều khoản
    # phải đúng một mục của mẫu — mẫu quyết định vị trí.
    if dieu is not None and ngu_canh.get("khoa_than") and not ngu_canh.get("co_dieu"):
        than = set(ngu_canh["khoa_than"])
        for d in [d for d in dieu if d["key"] not in than]:
            ghi.append(f"Chưa đưa vào: «{d['ten'] or 'một mục'}» — mẫu này không có mục đó")
        dieu = [d for d in dieu if d["key"] in than]
    if dieu is not None:
        bat_buoc = set(ngu_canh.get("bat_buoc") or [])
        if len(dieu) > khuon_mau.TOI_DA_DIEU:
            giu = [d for d in dieu if d["key"] in bat_buoc]
            du = khuon_mau.TOI_DA_DIEU - len(giu)
            khac = [d for d in dieu if d["key"] not in bat_buoc]
            for d in khac[max(du, 0) :]:
                ghi.append(f"Chưa đưa vào vì quá {khuon_mau.TOI_DA_DIEU} điều: «{d['ten']}»")
            con = set(map(id, giu + khac[: max(du, 0)]))
            dieu = [d for d in dieu if id(d) in con]
        while sum(len(x) for d in dieu for x in d["doan"]) > khuon_mau.NGAN_SACH_KY_TU:
            khac = [d for d in dieu if d["key"] not in bat_buoc]
            if not khac:
                break
            ghi.append(f"Chưa đưa vào vì quá dài: «{khac[-1]['ten']}»")
            dieu = [d for d in dieu if d is not khac[-1]]
    hoan_thanh = {"thieu": [], "completeness": None}
    if dieu is not None and loai:
        dieu, hoan_thanh = khuon_mau.them_dieu_bat_buoc(dieu, loai, tao=muc_tieu == "ban_moi")
        dieu = [{k: v for k, v in d.items() if k != "chen"} | ({"chen": True} if d.get("chen") else {}) for d in dieu]
    ben_hop_le = {b["khoa"] for b in khung.get("ben") or []} | {khuon_mau.BEN_VAN_BAN}
    gia_tri, khong_cho = [], []
    for g in ra.get("gia_tri") or []:
        v = " ".join(str((g or {}).get("gia_tri") or "").split()) if isinstance(g, dict) else ""
        if not v or len(v) > GIA_TRI_TOI_DA:
            continue
        if g.get("ben") in ben_hop_le and g.get("truong") in khuon_mau.truong():
            gia_tri.append({"ben": g["ben"], "truong": g["truong"], "gia_tri": v})
        else:
            # Bên hay trường không có trên tệp: không có chỗ trống nào nhận — báo "chưa
            # đặt được" (người gọi lọc theo lời người hỏi), không bỏ im.
            khong_cho.append(v)
    khong_dat = [
        " ".join(x.split()) for x in [*(ra.get("khong_dat") or []), *khong_cho] if isinstance(x, str) and x.strip()
    ][:8]
    return {
        "muc_tieu": muc_tieu,
        "khung": khung,
        "dieu": dieu,
        "sua_dieu": sua_dieu,
        "gia_tri": gia_tri,
        "khong_dat": khong_dat,
        "ghi_chu": list(dict.fromkeys(ghi)),
        "hoan_thanh": hoan_thanh,
        "dem": dict(dem),
    }


def _khoi_muc_khuon_mau(ngu_canh: dict) -> str:
    """Khối "Các mục" của prompt v3: mục checklist (và căn cứ của nó, nguyên văn rút
    gọn) hay mục thân cố định của mẫu."""
    muc = ngu_canh.get("muc") or []
    if not muc:
        return ""
    dong = [f"- `{m['key']}` — {m['ten']}" + (f" (căn cứ: {m['trich']})" if m.get("trich") else "") for m in muc]
    dan = (
        "Chỉ viết đúng các mục dưới đây, mỗi mục là một phần tử `dieu` mang `key` của nó (mẫu cố định vị trí):"
        if ngu_canh.get("khoa_than") and not ngu_canh.get("co_dieu")
        else "Văn bản phải có đủ các mục luật đòi dưới đây (mỗi mục một điều, mang `key` của nó), cộng các điều "
        "thông dụng khác của loại văn bản này (`key` null):"
    )
    return "# Các mục\n\n" + dan + "\n" + "\n".join(dong) + "\n"


def _soan_khuon_mau(
    state: dict,
    llm,
    model: str,
    cau_hoi: str,
    cau_hoi_nguoi: str,
    bo_nho_cho_phep: list[str],
    bo_nho_cam: list[str],
    khoi_bo_nho: str,
    hong,
) -> dict:
    """Lượt soạn tự do trên khuôn mẫu: MỘT lượt v3 → `kiem_khuon_mau` → state
    `khuon_mau_tong_quat` cho `dung_ban_thao_tong_quat`."""
    prior = state.get("traces") or {}
    ng = state["khuon_mau_ngu_canh"]
    bt = state.get("ban_thao_tong_quat_dang_mo") or {}
    sua = bool(ng.get("sua"))
    tai_lieu_cu = str(bt.get("document") or "")
    khoi_ban_thao = (
        f"\n# Bản thảo đang có\n\nĐây là bản thảo bạn đã soạn — số Điều là số HIỆN TẠI.\n\n{tai_lieu_cu}\n"
        if sua and tai_lieu_cu
        else (f"\n# Bản thảo cũ (chỉ để tham khảo)\n\n{tai_lieu_cu}\n" if tai_lieu_cu else "")
    )
    khoi_muc = _khoi_muc_khuon_mau(ng)
    try:
        kiem_tran_chi_phi_tai_lieu(len(khoi_ban_thao) + len(khoi_muc) + len(khoi_bo_nho))
    except VuotTran:
        return hong(QUA_DAI_VOI_BAN_THAO, "vuot_tran")
    loai = (
        f"{ng.get('ten') or ng.get('tieu_de')} — loại có sẵn: khung, các bên và căn cứ do hệ thống dựng; bạn chỉ "
        "viết điều khoản."
        if ng.get("loai")
        else (
            f"Văn bản tự soạn «{(ng.get('khung_cu') or {}).get('tieu_de')}» — giữ tên loại, bố cục và các bên."
            if sua
            else "Tự soạn (chưa có mẫu sẵn): chọn `tieu_de`, `trich_yeu`, `bo_cuc`, `ben`, `can_cu` theo quy tắc 2–3."
        )
    )
    ben = ", ".join([*(b["khoa"] for b in (ng.get("ben") or [])), khuon_mau.BEN_VAN_BAN])
    prompt = PROMPT_KHUON_MAU_PATH.read_text(encoding="utf-8").format(
        cau_hoi=cau_hoi,
        loai=loai,
        muc=khoi_muc,
        ban_thao_dang_co=khoi_ban_thao,
        bo_nho=khoi_bo_nho,
        toi_da_dieu=khuon_mau.TOI_DA_DIEU,
        toi_da_doan=khuon_mau.TOI_DA_DOAN,
        toi_da_ky_tu_doan=khuon_mau.TOI_DA_KY_TU_DOAN,
        ngan_sach=khuon_mau.NGAN_SACH_KY_TU,
        so_trang=khuon_mau.NGAN_SACH_KY_TU // 2500,
        truong=", ".join(f"{k} ({v})" for k, v in khuon_mau.truong().items()),
        ben=ben
        if ng.get("ben")
        else f"{khuon_mau.BEN_VAN_BAN}; `co_quan`, `nguoi_ky` với văn bản hành chính; với văn bản tự soạn khác là "
        "`khoa` bạn đặt ở `ben`",
    )
    usage = None
    try:
        raw, usage = llm.chat(
            model, messages(prompt), json_schema=schema_khuon_mau(sua, ng.get("khoa")), max_tokens=TOI_DA_TOKEN_RA
        )
        ra = json.loads(raw)
        if not isinstance(ra, dict):
            raise TypeError(f"phản hồi phải là object, được {type(ra).__name__}")
    except TruncatedOutputError as e:
        return hong(CHUA_SOAN_DUOC, "qua_dai_dau_ra", e.usage)
    except json.JSONDecodeError:
        return hong(CHUA_SOAN_DUOC, "json_hong", usage)
    except Exception as e:
        logger.warning("hieu_tai_lieu khuôn mẫu: lỗi (%s: %s)", type(e).__name__, e, exc_info=True)
        return hong(CHUA_SOAN_DUOC, "loi")
    kq = kiem_khuon_mau(
        ra, ng, _nguon_soan([], state, [], [], bo_nho_cho_phep), bo_nho_cam, ten_dieu_cua(tai_lieu_cu) if sua else []
    )
    muc_dich = "sua_ban_thao" if kq["muc_tieu"] == "sua_ban_dang_co" else "tao_van_ban"
    return {
        **state,
        "muc_dich_tai_lieu": muc_dich,
        "tai_lieu_ket": _ket(muc_dich, None, "", [], [], [], []),
        "tai_lieu_neo": [],
        "tai_lieu_du_kien_moi": [],
        "van_ban_tong_quat": None,
        "khuon_tong_quat": None,
        # Nguồn của GIÁ TRỊ các bên (lời người hỏi, hồ sơ trừ giả định, ký ức được hỏi
        # tới) và ký ức bị cấm: `dung_ban_thao_tong_quat` kiểm `gia_tri` trên chính chỗ
        # trống của tệp vừa dựng bằng `kiem_phep_sua` — luật khuôn gốc (B2).
        "khuon_mau_tong_quat": {**kq, "nguon_gia_tri": _nguon_nguoi(state, bo_nho_cho_phep), "cam": bo_nho_cam},
        "bo_nho_moi": rut_bo_nho(cau_hoi_nguoi),
        "traces": {
            **prior,
            "hieu_tai_lieu_nguon": "llm",
            "hieu_tai_lieu_model": model,
            "hieu_tai_lieu_muc_dich": muc_dich,
            "hieu_tai_lieu_prompt": "v3",
            "khuon_mau_so_dieu": len(kq["dieu"] or []),
            "khuon_mau_so_sua_dieu": len(kq["sua_dieu"] or []),
            "khuon_mau_so_gia_tri": len(kq["gia_tri"]),
            **{f"khuon_mau_{k}": v for k, v in kq["dem"].items()},
            "hieu_tai_lieu_token_in": usage.token_in if usage else 0,
            "hieu_tai_lieu_token_out": usage.token_out if usage else 0,
            "hieu_tai_lieu_cost_usd": usage.cost_usd if usage else 0.0,
        },
    }
