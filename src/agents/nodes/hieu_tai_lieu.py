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

from src.agents.nodes.route import Intent
from src.agents.nodes.verify_tier1 import QUOTE_TOI_THIEU
from src.services.bo_nho import _vuong_luoi_chan
from src.services.bo_nho_tai_khoan import GIA_TRI_TOI_DA
from src.services.doc_tai_lieu import DonViVanBan, NguonChu
from src.services.llm import TruncatedOutputError, Usage
from src.services.neo_du_kien import LyDoNeo, Neo, normalize, xac_minh
from src.services.phep_tinh import SAI_SO, so_bang_nhau, tinh, viet_so
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
# tròn XUỐNG một số dễ nhớ. Với trần chi phí hiện tại (25.000 ký tự,
# `tai_lieu.kiem_tran_chi_phi_tai_lieu`), tài liệu LỚN NHẤT được phép chỉ cần
# chia tối đa 2 lượt (`ceil(25000/15000)`).
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
_RE_KHAI_BO_NHO = re.compile(
    r"(?:^|[,;(\n]|\bva\b|\bvoi\b|\bnoi dung la\b)\s*"
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

    Dưới `NGUONG_TRANG` trang thì gửi cả tài liệu — cắt xén một tài liệu ngắn
    chỉ tạo ra rủi ro bỏ sót mà không tiết kiệm được gì đáng kể.

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
    if max((d.trang for d in don_vi), default=1) <= NGUONG_TRANG:
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


# Ký tự người ta kẻ một chỗ ĐỂ ĐIỀN, và dấu hiệu của một chỗ như vậy: dấu chấm
# lửng `…`, hoặc một dãy từ ba dấu chấm / gạch ngang / gạch dưới trở lên. Một
# dấu chấm lẻ thì không — `20.000.000` phân nhóm nghìn bằng đúng ký tự đó.
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
    if not s.strip(_KY_TU_KE) or _RE_CHO_DIEN.search(s):
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
    """Chữ CHUẨN HOÁ của một đoạn (không phải ô bảng) → căn lề THẬT của nó,
    đọc thẳng từ `DonViVanBan.can_le` (Phase 9 U5) — cùng nguyên tắc "cấu trúc
    reader đã biết" của `_bang_theo_nhan`, áp cho căn lề thay vì ô bảng. Một
    dòng trùng chữ nhưng khác căn lề ở hai chỗ (hiếm — hai đoạn tình cờ cùng
    chữ) bị LOẠI khỏi từ điển: một dòng không xác định căn lề còn an toàn hơn
    một dòng gán nhầm."""
    theo_dong: dict[str, set[str]] = {}
    for t in goi:
        for d in t["don_vi"]:
            if d.bang is not None or not d.noi_dung:
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


def _hang_gon(cot: dict[int, str], nhip_cot: dict[int, int], so_cot: int) -> tuple[list[str], list[int]]:
    """Một hàng bảng THẬT, GỌN — chỉ giữ ô có chữ cộng thêm Ô ĐỆM cho khoảng
    TRỐNG thật (Phase 11 R6), không phải một mảng phẳng một-ô-một-cột.

    `cot`/`nhip_cot` khoá theo cột LƯỚI THẬT (đã cộng dồn `w:gridSpan`, xem
    `doc_tai_lieu._duyet_than`). Đi từ trái sang phải: một cột lưới còn trống
    TRƯỚC ô tiếp theo (ô gộp ở hàng khác chiếm chỗ, hoặc chính hàng này chỉ
    có vài ô đầu — ca đo được trên "Tuần 1(từ…)" của BM.ĐT.18.05) được lấp
    bằng đúng MỘT ô đệm rỗng mang nhịp bằng khoảng trống đó — không phải một
    ô rỗng cho MỖI cột trống, để một ô gộp thật (như "Tổng") vẫn hiện ĐÚNG
    nhịp của nó, không bị tách lại thành nhiều ô 1-cột.
    """
    hang: list[str] = []
    nhip: list[int] = []
    chay = 0
    for c in sorted(cot):
        if c > chay:
            hang.append("")
            nhip.append(c - chay)
        hang.append(cot[c])
        n = nhip_cot.get(c, 1)
        nhip.append(n)
        chay = c + n
    if chay < so_cot:
        hang.append("")
        nhip.append(so_cot - chay)
    return hang, nhip


def _bang_theo_nhan(goi: list[dict]) -> dict[str, dict]:
    """Mọi bảng THẬT của lượt này, dựng lại 0 token thẳng từ `don_vi` — khoá
    "A0"/"B2" (nhãn tài liệu + số bảng, 0-based, đúng số `_vi_tri` đã hiện cho
    mô hình). Không đoán ô nào ở đâu: lưới hàng×cột đến thẳng từ `(bảng, hàng,
    cột)` mà `doc_tai_lieu` đã gán cho từng ô khi đọc file — ĐÂY là "cấu trúc
    reader đã biết" mà review round 2 chỉ ra không nên bắt mô hình đoán lại.
    Dùng `t["don_vi"]` (TOÀN BỘ), không phải `t["gui"]` (phần đã lọc gửi mô
    hình) — cùng lý lẽ neo trích dẫn: phép lọc đầu vào là chuyện chi phí,
    không phải chuyện bằng chứng.

    Trả về, mỗi khoá bảng, MỘT bộ ba cùng nguồn gốc (Phase 11 R1/R6), thay vì
    chỉ `hang`: `nhip` (số cột mỗi ô CHIẾM, cùng hình dạng `hang`, đọc thẳng
    `bang_nhip` — RENDER dùng trực tiếp, không suy đoán lại từ số ô như
    `coSpanHang` cũ) và `ti_le` (% mỗi cột lưới, đọc `bang_ti_le`, rỗng khi
    bảng không khai lưới). Không đẻ ra một hàm/một lượt duyệt `don_vi` thứ hai
    cho `ti_le`/`nhip` — cả ba đến từ ĐÚNG một vòng lặp này (xem R3 trong
    brief: "một chỗ carry cả bộ, không phải năm chỗ chép từng trường").
    """
    ra: dict[str, dict] = {}
    for t in goi:
        theo_bang: dict[int, dict[int, dict[int, str]]] = {}
        nhip_bang: dict[int, dict[int, dict[int, int]]] = {}
        ti_le_bang: dict[int, tuple[int, ...]] = {}
        cot_toi_da: dict[int, int] = {}
        for d in t["don_vi"]:
            if d.bang is None:
                continue
            b, h, c = d.bang
            theo_bang.setdefault(b, {}).setdefault(h, {})[c] = d.noi_dung
            nhip_bang.setdefault(b, {}).setdefault(h, {})[c] = d.bang_nhip
            cot_toi_da[b] = max(cot_toi_da.get(b, 0), c + d.bang_nhip)
            if d.bang_ti_le and b not in ti_le_bang:
                ti_le_bang[b] = d.bang_ti_le
        for b, theo_hang in theo_bang.items():
            ti_le = ti_le_bang.get(b, ())
            so_cot = len(ti_le) or cot_toi_da.get(b, 0)
            hang: list[list[str]] = []
            nhip: list[list[int]] = []
            for h in range(max(theo_hang) + 1):
                h_hang, h_nhip = _hang_gon(theo_hang.get(h, {}), nhip_bang.get(b, {}).get(h, {}), so_cot)
                hang.append(h_hang)
                nhip.append(h_nhip)
            ra[f"{t['nhan']}{b}"] = {"hang": hang, "nhip": nhip, "ti_le": list(ti_le)}
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
    đúng ca đó: so chuỗi nguyên văn, thay bằng `[…]`, và đếm riêng để đo được
    mô hình tự điền bao nhiêu lần.

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
    dem = {"muc_lam_sach": 0, "gia_tri_lam_sach": 0, "muc_bo": 0, "bo_nho_khong_dien": 0}
    # Giá trị đã nhớ mà CÓ trong `nguon` thì KHÔNG cấm: ở đó nó tới bằng chính
    # lời người hỏi lượt này (hay tài liệu, hay bản thảo đang có), không bằng ký
    # ức — cấm nó là xoá đúng thứ người dùng vừa gõ ra. `_nguon_soan` đã cộng
    # sẵn giá trị của những khoá lượt này HỎI TỚI, nên một lượt xin điền cũng rơi
    # vào đúng nhánh "có trong nguồn" này.
    #
    # ponytail: so khớp chuỗi nguyên văn (không phân biệt hoa thường), nên một
    # mô hình viết tắt tên ("N.V. Thử") vẫn lọt. Nâng lên so khớp theo từ khi đo
    # được rằng nó xảy ra thật.
    cam_re = [
        re.compile(rf"(?<!\w){re.escape(v)}(?!\w)", re.IGNORECASE)
        for v in (cam or []) if v and normalize(v) not in nguon
    ]

    def _sach(s: str) -> str:
        for r in cam_re:
            s, n = r.subn(CHO_TRONG, s)
            dem["bo_nho_khong_dien"] += n

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
            noi_dung = _sach(str(k.get("noi_dung") or "").strip())
            bang = _bang_sach(k.get("bang"))
            if noi_dung:
                # `can_le` (Phase 9 U5) — căn lề THẬT của khối này, đối chiếu
                # từng dòng với `theo_dong`; bảng giữ `trai` làm chỗ trống
                # (không đọc), căn lề trong bảng là chuyện của TỪNG ô, ngoài
                # phạm vi field này (xem cảnh báo ở brief).
                ra.append({
                    "noi_dung": noi_dung,
                    "bang": [],
                    "can_le": _can_le_khoi(noi_dung, theo_dong),
                    "nhip": [],
                    "ti_le": [],
                })
            if bang:
                # `nhip`/`ti_le` rỗng: bảng mô hình tự gõ không có lưới nguồn
                # nào để đọc — `coSpanHang` (frontend) vẫn suy đoán từ số ô
                # như trước Phase 11, đúng "quy tắc cho ca không có lưới khai
                # báo" R6 yêu cầu giữ lại.
                ra.append({"noi_dung": "", "bang": bang, "can_le": "trai", "nhip": [], "ti_le": []})
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
    tieu_de_sach = _sach(str((van_ban or {}).get("tieu_de") or "").strip())
    if goi and tieu_de_sach and muc_sach:
        vi_tri = _vi_tri_theo_don_vi(goi)
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
                }],
                "dem_delta": 0,
            })

    giu: list[dict] = []
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
        giu.append({"ten": ten, "ten_that": ten_that, "vung": vung, "khoi": khoi})
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


def _khoi_tai_lieu(goi: list[dict]) -> str:
    dong = []
    for t in goi:
        dong.append(f"## Tài liệu {t['nhan']} — {t['ten_tep']}")
        dong += [f"[{t['nhan']}-{d.chi_so}] ({_vi_tri(d)}) {d.noi_dung}" for d in t["gui"]]
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
    """Đọc `tai_lieu` (mỗi phần tử `{id, ten_tep, don_vi}`) trả lời câu hỏi của lượt.

    Trả về state cộng `tai_lieu_ket`, `muc_dich_tai_lieu`, `tai_lieu_neo`,
    `bo_nho_moi` (điều người hỏi vừa tự khai, chờ ghi) và `traces`. Người gọi (`graph_tra_cuu`) lo phần DB — nạp `don_vi` theo chủ sở
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
    # Phase 14 — soạn tự do: không tài liệu, nhưng router (ý kiến ĐỘC LẬP, xem
    # `_muc_dich_soan_da_xac_nhan`) đã nói đây là một lượt soạn thảo. Chỉ ca này
    # mới được gọi mô hình với khối tài liệu rỗng (`KHONG_TAI_LIEU`); mọi lượt
    # không-tài-liệu khác vẫn nói thật là chưa đọc được, không gọi gì.
    soan_tu_do = not goi and state.get("intent") == Intent.soan_thao
    # Ký ức tài khoản (Phase 12 part B) — `graph_tra_cuu` đã nạp sẵn, vì node
    # này thuần và không chạm DB. Chia làm hai NGAY ở đây, MỘT lần, để không có
    # hai bản sao của cùng một quyết định trôi lệch nhau: khoá lượt này hỏi tới
    # thì giá trị của nó là NGUỒN hợp lệ; khoá còn lại đi vào `cam` và không có
    # đường nào vào văn bản.
    nho = state.get("bo_nho_tai_khoan") or []
    hoi_toi = {str(r.get("khoa") or "") for r in nho if khoa_duoc_hoi(cau_hoi, str(r.get("khoa") or ""))}
    bo_nho_cho_phep = [str(r.get("gia_tri") or "") for r in nho if str(r.get("khoa") or "") in hoi_toi]
    bo_nho_cam = [str(r.get("gia_tri") or "") for r in nho if str(r.get("khoa") or "") not in hoi_toi]
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
    usage = None
    try:
        # Phase 16 R2 — tài liệu ĐƠN (so sánh/đối chiếu nhiều tài liệu đi
        # nguyên đường một lượt như trước, không chia: `_khop_bang` chỉ được
        # kiểm chứng an toàn cho một tài liệu tại một thời điểm) và đủ dài để
        # một lượt có nguy cơ cần nhiều token ra hơn `TOI_DA_TOKEN_RA` (đo
        # được, xem `NGUONG_PHAN_KY_TU`) thì chia thành nhiều lượt kế tiếp.
        # Ngắn hơn ngưỡng: ĐÚNG một lượt như trước bản vá này, không đổi hành
        # vi, không đổi chi phí.
        if len(goi) == 1 and so_ky_tu_vao > NGUONG_PHAN_KY_TU:
            ra, usage = _hieu_theo_phan(llm, model, cau_hoi, goi, prompt_path or PROMPT_PATH,
                                        khoi_ban_thao, khoi_bo_nho)
        else:
            prompt = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8").format(
                cau_hoi=cau_hoi, tai_lieu=KHONG_TAI_LIEU if soan_tu_do else _khoi_tai_lieu(goi), phan_doan="",
                ban_thao_dang_co=khoi_ban_thao, bo_nho=khoi_bo_nho,
            )
            raw, usage = llm.chat(model, messages(prompt), json_schema=schema_hieu(nhan), max_tokens=TOI_DA_TOKEN_RA)
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
            "noi_dung": str(o.get("noi_dung") or "").strip(),
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
    if muc_dich in MUC_DICH_SOAN and not _muc_dich_soan_da_xac_nhan(state.get("intent")):
        muc_dich = "hoi"
    phep_tinh, phep_tinh_bo = _lay_phep_tinh(ra, goi)
    truong, truong_bo = _lay_truong(ra, goi)
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
        if muc_dich in MUC_DICH_SOAN
        else (None, {"muc_lam_sach": 0, "gia_tri_lam_sach": 0, "muc_bo": 0, "bo_nho_khong_dien": 0})
    )
    # R5 — 0 token: dữ kiện người dùng tự khai đọc từ CHÍNH câu họ gõ, và chỉ ở
    # lượt SOẠN (nơi họ đang khai để dựng một văn bản). `graph_tra_cuu` ghi
    # xuống DB, đúng con đường `tai_lieu_du_kien_moi` đã đi — node này thuần.
    bo_nho_moi = rut_bo_nho(cau_hoi) if muc_dich in MUC_DICH_SOAN else []
    can_du_kien = [str(s).strip() for s in (ra.get("can_du_kien") or []) if str(s).strip()]
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
    tra_loi = str(ra.get("tra_loi_ngan") or "").strip()
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
            str(ra.get("mo_ta") or "").strip() or None,
            tra_loi,
            giu,
            [str(s).strip() for s in (ra.get("suy_luan") or []) if str(s).strip()][:TOI_DA_SUY_LUAN],
            can_du_kien,
            da_dung,
            phep_tinh,
            khac_biet,
        ),
        # Điều khoản đưa sang đường pháp lý, mỗi cái mang neo của nó.
        "tai_lieu_neo": dieu_khoan,
        # Văn bản đã làm sạch cho `dung_ban_thao_tong_quat` (S6).
        "van_ban_tong_quat": van_ban,
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
