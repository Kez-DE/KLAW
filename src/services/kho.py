"""Câu trả lời về CHÍNH KHO DỮ LIỆU — thuần SQL, 0 token LLM.

ĐO ĐƯỢC 2026-09-02: "Hiện tại có bao nhiêu bộ luật?" bị định tuyến sang đường
tra cứu NỘI DUNG luật (`route.v1.md` dặn "không chắc thì chọn tra_cuu"), truy hồi
10 kết quả, mở rộng ra 30 điều khoản tầng sâu, sinh **0 luận điểm**, rồi trả
`abstain` với `answer` rỗng. Ba mươi điều khoản trong tay, người hỏi nhận màn
hình trắng — trong khi câu trả lời là một phép `count(*)`.

Nguyên tắc ràng buộc (spec mục 2): mọi đường trả lời phải kết thúc ở MỘT TRONG
HAI — một phép tra bảng xác định, hoặc một claim đã qua đủ hai tầng kiểm. Câu
hỏi về kho thuộc loại thứ nhất, nên **không con số nào trong module này do LLM
sinh ra**; không có tham số `llm` ở bất kỳ hàm nào, và đó là chủ đích.

## Vì sao "trong kho của mình" chứ không phải "Việt Nam có"

Kho là một tập được CHỌN cho đề tài, không phải một cuộc tổng điều tra. "Trong
kho của mình hiện có 6 Bộ luật" là sự thật kiểm được bằng SQL; "Việt Nam hiện có
6 Bộ luật" là ảo giác — và là loại verifier **không bắt được**, vì không có
trích dẫn nào để đối chiếu từng chữ. Nên `CAU_GIOI_HAN` là HẰNG SỐ trong mã,
đi kèm mọi nhánh, không do model sinh: model không được phép quên nó.

## Vì sao lọc bằng verdict hiệu lực, không bằng cột nào của `documents`

`loai_van_ban = 'Bộ luật'` trả **12 dòng**: 6 bộ hiện hành cộng 6 bản đã bị thay
(BLLĐ 2012, BLHS 1999, BLTTHS 2003, BLTTDS 2004, BLDS 2005, BLHH 2005). Đếm thô
ra 12 là sai.

- KHÔNG lọc bằng `documents.tinh_trang`: sáu bản cũ đều mang `chua_xac_dinh`,
  còn năm trong sáu bản hiện hành mang `HHL1P` — cột đó không tách được hai nhóm.
- KHÔNG lọc bằng `documents.depth`: `deep`/`shallow` nói MỨC ĐÃ NẠP, không nói
  hiệu lực. Ở kho hiện tại nó trùng khớp một cách TÌNH CỜ (6 bộ hiện hành đều
  `deep`, 6 bản cũ đều `shallow`) và sẽ sai ngay khi ai đó nạp sâu một văn bản
  đã hết hiệu lực.

Lọc bằng `effectivity.danh_gia_theo_id` — cùng cơ chế cạnh đồ thị mà `expand()`
dùng — rồi loại verdict `het_hieu_luc` và `bi_thay_the`. Đây là một QUY TẮC,
không phải một danh sách cứng sáu doc_id.
"""

import re
from datetime import date

from sqlalchemy import Engine, text

from src.models.schemas import Bang
from src.services.effectivity import Effectivity, danh_gia_toan_bo
from src.services.effectivity import EffectivityVerdict as V

# Câu đóng — HẰNG SỐ, không do model sinh. Mọi nhánh trả lời đều ghép nó vào
# cuối; `test_moi_duong_tra_loi_deu_dong_bang_cau_gioi_han_pham_vi` canh điều đó
# bằng cách so với chính hằng số này, nên sửa lời ở đây không làm test đỏ oan —
# chỉ gỡ nó khỏi một nhánh mới làm.
#
# Cố ý KHÔNG chứa cụm "Việt Nam có <số>": nó nói kho KHÔNG phải nền pháp luật,
# chứ không phát biểu gì về nền pháp luật.
#
# Phase 14 (R5, owner): lời cho NGƯỜI ĐỌC không gọi corpus là "kho của tôi"
# nữa — thứ đang trích là văn bản pháp luật Việt Nam, gọi nó là một cái kho
# riêng làm KLAW nghe như một danh mục tư nhân. Định danh nội bộ (tên module,
# `Intent.hoi_ve_kho`, chú thích, log) giữ nguyên: đây là việc đổi LỜI.
# Ranh giới không được vượt: bỏ chữ "kho" KHÔNG được biến câu này thành lời hứa
# phủ hết pháp luật Việt Nam — nó vẫn phải thú nhận đúng phạm vi đang có.
CAU_GIOI_HAN = (
    "Đây là phạm vi văn bản tôi đọc được, không phải toàn bộ văn bản pháp luật Việt Nam — "
    "tôi mới đọc tập văn bản chọn cho đề tài này, và còn nhiều văn bản tôi chưa có."
)

# Hai verdict DỨT KHOÁT là "không còn dùng được". Mọi verdict khác được ĐẾM vào
# kho đang dùng nhưng phải mang nhãn thật của nó (xem `_NHAN`) — đặc biệt
# `chua_xac_dinh`, nghĩa là đồ thị không có tín hiệu nào, KHÔNG phải "còn hiệu
# lực".
_LOAI_BO = frozenset({V.het_hieu_luc, V.bi_thay_the})

# Nhóm "xác định được tình trạng" — liệt kê TƯỜNG MINH, không bằng phép trừ.
# Phép trừ (`not in _LOAI_BO`) đẩy `chua_xac_dinh` và `can_doi_chieu_tay` vào
# cùng rổ với `con_hieu_luc`, và trên DB thật đó là 47/130 văn bản — hơn một
# phần ba kho — được đếm chung vào một con số người đọc hiểu là "dùng được".
# Liệt kê tường minh còn cho mặc định an toàn đúng chiều: một verdict mới thêm
# vào enum mà chưa ai xét ở đây sẽ rơi về "CHƯA xác định", không rơi về "còn
# hiệu lực" — cùng quy tắc `effectivity.py` đã lập.
_XAC_DINH_DUOC = frozenset({
    V.con_hieu_luc,
    V.chua_hieu_luc,   # sắp có hiệu lực — biết rõ, và là thứ người hỏi cần biết
    V.bi_sua_doi,
    V.mot_phan_khong_xac_dinh,  # còn hiệu lực, biết bị sửa bởi văn bản nào
})

# Nhãn ngắn để liệt kê. KHÁC `assemble.CANH_BAO_NHAN` ở hai điểm nên không tái
# dùng được: bảng kia là bảng CẢNH BÁO (cố ý không có dòng `con_hieu_luc`, vì
# không có gì để cảnh báo), còn ở đây mỗi văn bản được liệt kê đều cần một nhãn
# trạng thái — kể cả nhãn "còn hiệu lực".
_NHAN = {
    V.con_hieu_luc: "còn hiệu lực",
    V.chua_hieu_luc: "chưa tới ngày có hiệu lực",
    V.het_hieu_luc: "đã hết hiệu lực",
    V.bi_thay_the: "đã bị thay thế",
    V.bi_sua_doi: "đã bị sửa đổi",
    V.mot_phan_khong_xac_dinh: (
        "hết hiệu lực một phần, cơ sở dữ liệu quốc gia không công bố phần nào"
    ),
    V.can_doi_chieu_tay: "cần đối chiếu tay",
    V.chua_xac_dinh: "chưa xác định được hiệu lực",
}

# Bảng trên phủ đủ 8 verdict hiện có. Một verdict thứ 9 rơi vào mặc định NÀY —
# nói ít hơn sự thật, chưa bao giờ nói nhiều hơn. Mặc định ngược lại (im lặng,
# hoặc "còn hiệu lực") biến một verdict mới thành văn bản duy nhất không cảnh
# báo gì.
_NHAN_MAC_DINH = "chưa xác định được hiệu lực"

# `số/năm` — bắt được cả "145/2020/NĐ-CP" (dạng đầy đủ) lẫn "Nghị định
# 145/2020" (dạng người ta thật sự hỏi). Nhận diện bằng QUY TẮC, 0 token.
#
# Rẻ được là nhờ ngữ cảnh: hàm này chỉ chạy khi `route` đã kết luận câu hỏi là
# `hoi_ve_kho`, nên regex không phải tự phân biệt "hỏi về kho" với "hỏi nội dung
# luật" — nó chỉ phải tách số hiệu ra khỏi một câu đã biết là hỏi về kho.
#
# `(?<![\d/])` chặn ĐUÔI của một ngày: "Từ ngày 1/1/2026, công ty tôi…" (câu
# thật trong `golden_qa.yaml`) có chứa "1/2026", và không có lookbehind này thì
# nó bị đọc thành số hiệu văn bản.
_RE_SO_HIEU = re.compile(r"(?<![\d/])(\d{1,4}/\d{4})\b")

_SQL_KHO = text(
    "SELECT id, so_ky_hieu, ten, loai_van_ban, depth, linh_vuc "
    "FROM documents ORDER BY so_ky_hieu"
)

_CO_TOAN_VAN = "deep"


def moi_so_hieu_trong(cau_hoi: str) -> list[str]:
    """MỌI `số/năm` trong câu hỏi, theo thứ tự xuất hiện, không trùng lặp.
    Rỗng nghĩa là câu hỏi không nêu số hiệu nào (→ đường tóm tắt kho).

    `findall`, KHÔNG `search`: bản trước lấy đúng số hiệu ĐẦU TIÊN, nên
    "có nghị định 145/2020 và nghị định 90/2019 không?" được trả lời về 145/2020
    rồi im lặng hoàn toàn về 90/2019 — không một câu cảnh báo phạm vi nào. Câu
    trả lời TRÔNG đầy đủ và tự tin trong khi đã bỏ mất một nửa câu hỏi, đúng chế
    độ hỏng nguy hiểm nhất của cả đề tài ở dạng thiếu phạm vi.

    `dict.fromkeys` để giữ thứ tự và bỏ trùng: "nghị định 145/2020 ấy, tức
    145/2020/NĐ-CP" nhắc một văn bản hai lần, không phải hai văn bản.
    """
    return list(dict.fromkeys(_RE_SO_HIEU.findall(cau_hoi)))


# Ba cụm này là DANH TỪ pháp lý trong nội dung câu hỏi, không phải yêu cầu
# trình bày — "cho tôi bảng lương", "đưa bảng chấm công", "kẻ bảng giá" KHÔNG
# được khớp dù bốn cụm xin-bảng bên dưới đều là tiền tố đúng nghĩa của chúng.
#
# Fix round 1 (finding 3): lookahead BẢN TRƯỚC chỉ chặn NGAY SAU "bảng", nên chỉ
# phủ bốn cụm KẾT THÚC bằng "bảng" — năm cụm còn lại ("liệt kê", "dạng cột",
# "xem dễ hơn", "bảng hiển thị", "table") không có gác nào, và "liệt kê bảng
# lương"/"dạng cột của bảng giá" lọt qua kích hoạt sai. Hai nhóm tuỳ chọn
# ("của "/"bảng ") cho phép lookahead bỏ qua từ nối GIỮA cụm kích hoạt và danh
# từ pháp lý ("liệt kê [bảng] lương", "dạng cột [của] [bảng] giá") — cả hai đều
# rỗng được nên cụm áp sát danh từ ("cho tôi bảng lương") vẫn bị chặn như cũ.
_KHONG_PHAI_BANG_TRINH_BAY = r"(?!\s*(?:của\s+)?(?:bảng\s*)?(?:lương|chấm\s*công|giá)\b)"

# Fix round 2: fix round 1 gắn guard ở trên vào ĐỦ CHÍN cụm kích hoạt — đó
# CHÍNH LÀ hồi quy fix round 2 sửa, không phải một lựa chọn còn tranh cãi.
# Bảy cụm dưới đây mang guard; "bảng hiển thị" và "\btable\b" thì KHÔNG.
#
# ĐỪNG "dọn cho đều" bằng cách gắn guard vào hai cụm còn lại. Guard chỉ có lý
# do tồn tại ở chỗ câu tiếng Việt THẬT SỰ mơ hồ: khi chữ ngay trước
# "lương"/"chấm công"/"giá" là (hoặc có thể là) chính chữ "bảng", câu vừa đọc
# được thành DANH TỪ GHÉP pháp lý — "bảng lương" = nội dung câu hỏi ("cho tôi
# bảng lương tháng này" hỏi VỀ bảng lương) — vừa đọc được thành "một bảng, chủ
# đề lương" (yêu cầu trình bày). Bốn cụm kết thúc bằng chính chữ "bảng" tạo ra
# đúng cấu trúc mơ hồ đó; "liệt kê"/"dạng cột"/"xem dễ hơn" cũng vậy vì chúng
# đứng cách "bảng lương/chấm công/giá" đúng một từ nối — guard cần cho cả bảy.
#
# "bảng hiển thị" và "table" thì KHÔNG có cấu trúc mơ hồ đó. "hiển thị" và
# "table" đều BẮT BUỘC phải có một chủ đề theo sau — không tồn tại danh từ
# ghép pháp lý nào là "hiển thị lương" hay "table lương". Chữ theo sau hai cụm
# này luôn LÀ chủ đề của cái bảng, không bao giờ là một phần của "bảng
# lương/chấm công/giá". Gắn guard vào đó không chặn được ca mơ hồ nào (không
# có ca nào để chặn) — nó chỉ chặn OAN mọi câu xin bảng thật trùng chủ đề với
# ba danh từ loại trừ, đúng hồi quy ĐÃ ĐO ĐƯỢC ở fix round 1:
#   xin_dang_bang("bảng hiển thị lương của nhân viên theo tháng")  # → False, SAI
#   xin_dang_bang("table lương nhân viên tháng này")               # → False, SAI
# cả hai phải là True — xem cặp test cùng tên chiều-ngược ở test_kho.py.
_RE_XIN_BANG = re.compile(
    r"dạng bảng" + _KHONG_PHAI_BANG_TRINH_BAY + r"|"
    r"cho tôi bảng" + _KHONG_PHAI_BANG_TRINH_BAY + r"|"
    r"đưa bảng" + _KHONG_PHAI_BANG_TRINH_BAY + r"|"
    r"kẻ bảng" + _KHONG_PHAI_BANG_TRINH_BAY + r"|"
    r"dạng cột" + _KHONG_PHAI_BANG_TRINH_BAY + r"|"
    r"xem dễ hơn" + _KHONG_PHAI_BANG_TRINH_BAY + r"|"
    r"bảng hiển thị|"
    r"\btable\b|"
    r"liệt kê" + _KHONG_PHAI_BANG_TRINH_BAY,
    re.IGNORECASE,
)


def xin_dang_bang(cau_hoi: str) -> bool:
    """Câu hỏi về kho có xin trình bày DẠNG BẢNG không — quy tắc, 0 token,
    chạy TRƯỚC khi quyết định gọi `dung_bang` thay vì `dung_cau_tra_loi`.

    Gọi trên câu ĐÃ GIẢI NGHĨA (`cau_hoi_day_du`) khi có, câu người dùng gõ
    (`query`) khi không — xem chỗ gọi ở `graph_tra_cuu.n_assemble`.
    """
    return _RE_XIN_BANG.search(cau_hoi) is not None


def _khop_so_hieu(so: str, so_ky_hieu: str) -> bool:
    """`145/2020` khớp `145/2020/NĐ-CP`, và khớp cả `số: 34/2024/QH15` (có một
    dòng như vậy trong corpus).

    Chặn ở BIÊN KHÔNG-PHẢI-CHỮ-SỐ, không dùng `LIKE '%…%'`: một `LIKE` lỏng làm
    `145/2020` khớp `1145/2020/NĐ-CP`, tức trả lời "có" cho một văn bản kho
    không có. Ngược lại một `LIKE '145/2020/%'` chặt lại bỏ sót dòng `số: …`,
    tức trả lời "không có" cho một văn bản kho THẬT SỰ CÓ — sai chế độ tệ hơn.
    """
    return re.search(rf"(?:^|\D){re.escape(so)}(?:/|$)", so_ky_hieu) is not None


def _nhan(hieu_luc) -> str:
    return _NHAN.get(hieu_luc.verdict, _NHAN_MAC_DINH)


def hien_van_ban(so_ky_hieu: str, ten: str) -> tuple[str, str]:
    """`(số hiệu, tên)` như NGƯỜI ĐỌC được thấy — MỘT chỗ quyết định cho cả
    `kho.py` lẫn `assemble.py`.

    ĐO ĐƯỢC 2026-09-02 trên mặt người dùng: `documents` id 8532 mang
    `so_ky_hieu = 'Không số'` và `ten = 'Luật Thương mại số Không số'` (crawler
    ghép `ten + " số " + so_ky_hieu`), và câu trả lời hiện ra "Không số (Luật
    Thương mại số Không số)". Hai lời nói sai trong một dòng: `Không số` được
    trình bày như một định danh tra được, và cái tên thì lặp lại nó.

    Kiểm bằng CHỮ SỐ, KHÔNG bằng danh sách giá trị xấu: mọi số hiệu văn bản pháp
    luật Việt Nam đều mang năm ban hành, nên phép kiểm này không loại oan một số
    hiệu thật nào — và nó bắt được cả dạng dị dạng chưa từng xuất hiện, thứ mà
    một danh sách `{'Không số'}` sẽ bỏ sót đúng vào lần crawl sau.

    Cắt hậu tố theo QUY TẮC (`" số " + so_ky_hieu`), không theo chuỗi cứng
    `" số Không số"`, vì đó chính là cách crawler dựng `ten`. Chỉ cắt trong
    nhánh DỊ DẠNG: "Bộ luật Dân sự số 91/2015/QH13" thì thừa chứ không sai, và
    cắt nó là sửa lời một dòng đang đúng.

    KHÔNG đụng `so_ky_hieu` trong DB hay trong `duong_dan` — đó là khoá dữ liệu,
    sửa nó là sửa neo trích dẫn.
    """
    so = (so_ky_hieu or "").strip()
    ten = (ten or "").strip()
    if any(c.isdigit() for c in so):
        return so, ten
    hau_to = f" số {so}"
    if so and ten.endswith(hau_to):
        ten = ten[: -len(hau_to)].strip()
    return "", ten


def nap_kho(engine: Engine, as_of: date) -> list[dict]:
    """TOÀN BỘ `documents` kèm phán quyết hiệu lực — kể cả bản đã bị thay.

    Trả về cả bản đã bị thay là CỐ Ý: chúng không được ĐẾM vào số văn bản đang
    dùng, nhưng chúng vẫn nằm trong kho. Trả lời "kho không có BLLĐ 2012" là một
    lời nói sai về chính kho của mình.

    Hiệu lực lấy bằng `danh_gia_toan_bo` (HAI truy vấn cho cả corpus), KHÔNG
    bằng `danh_gia_theo_id` trong vòng lặp. Bản đầu dùng vòng lặp vì đo được
    0,17s cho 130 văn bản và kết luận "đủ nhanh" — phép đo đúng nhưng đo sai
    biến: 0,17s chia cho ~450 round-trip ra ~0,3ms mỗi lượt, tức latency
    LOOPBACK. Đường vòng lặp tốn 392–522 round-trip mỗi request (130 × [1 ping
    của `pool_pre_ping` + 2 truy vấn của `nap_ngu_canh` + 1 truy vấn có điều
    kiện]); với DB ở xa (Railway) riêng phần mạng đã là 0,4–2,6 giây, cho đúng
    cái đường lẽ ra là "0 token, trả lời ngay". Đường gộp là 5 round-trip, không
    phụ thuộc cỡ corpus.

    `danh_gia_toan_bo` KHÔNG phải một đường phán quyết thứ hai — nó gọi cùng hàm
    lõi `danh_gia`. Đã đối chiếu cả 130 văn bản 2026-09-02: **0 lệch verdict**
    (`test_nap_kho_cho_verdict_Y_HET_duong_tung_van_ban` pin điều này). Có lệch
    `ly_do` ở 5 văn bản bị NHIỀU văn bản khác sửa — hai đường nêu tên một văn bản
    sửa khác nhau trong cùng tập, cùng verdict, cả hai câu đều đúng. Lệch đó CÓ
    TỪ TRƯỚC bản này (`routes_tim_kiem.py` vốn đã dùng đường gộp trong khi
    `expand`/`tier1` dùng đường từng-cái), nên không sinh ra ở đây.

    Trả về cả bản đã bị thay nên KHÔNG có đường tắt riêng cho lượt tra một số
    hiệu — một đường đi cho cả hai dạng câu hỏi.
    """
    with engine.connect() as c:
        rows = [dict(r) for r in c.execute(_SQL_KHO).mappings().all()]
    hieu_luc = danh_gia_toan_bo(engine, as_of)
    # `chua_xac_dinh` cho dòng thiếu, KHÔNG `con_hieu_luc`: `danh_gia_toan_bo`
    # phủ mọi dòng `documents` hôm nay nên nhánh này chưa đến được, nhưng mặc
    # định an toàn khi không biết phải là "chưa xác định" — cùng quy tắc
    # `graph_tra_cuu.py:146` đã lập cho tier 1.
    thieu = Effectivity(V.chua_xac_dinh, "thap",
                        "không có trong bản đồ hiệu lực toàn corpus — không đánh giá được")
    return [{**r, "hieu_luc": hieu_luc.get(r["id"], thieu)} for r in rows]


def _muc_phu(depth: str) -> str:
    return ("có toàn văn, tra được tới từng điều khoản" if depth == _CO_TOAN_VAN
            else "tôi chỉ có số hiệu, tên và hiệu lực — chưa có toàn văn")


def _dong_van_ban(r: dict) -> str:
    """Một văn bản, ba dòng. `ly_do` NGUYÊN VĂN của effectivity, không tóm lại:
    nó là chỗ nêu ĐÍCH DANH văn bản đi thay hoặc đi sửa ("bị 19/2023/QH15 sửa
    đổi… từ 2024-07-01"), và một nhãn chung chung xoá mất đúng thông tin đó."""
    return (f"- {' — '.join(x for x in hien_van_ban(r['so_ky_hieu'], r['ten']) if x)}\n"
            f"  Mức phủ: {_muc_phu(r['depth'])}.\n"
            f"  Hiệu lực: {_nhan(r['hieu_luc'])} — {r['hieu_luc'].ly_do}.")


def _khoi_mot_so(so: str, kho: list[dict]) -> list[str]:
    """Các đoạn trả lời cho MỘT số hiệu, KHÔNG kèm `CAU_GIOI_HAN`.

    Tách khỏi `_mot_van_ban` để câu hỏi ghép nhiều số hiệu dùng lại được mà chỉ
    đóng bằng MỘT câu giới hạn phạm vi — lặp câu đó sau mỗi khối làm nó thành
    tiếng ồn, và một câu cảnh báo bị đọc như tiếng ồn thì không còn cảnh báo gì.
    """
    khop = [r for r in kho if _khop_so_hieu(so, r["so_ky_hieu"])]
    if not khop:
        # KHÔNG kéo một văn bản gần giống vào chỗ này. Sai chế độ tệ nhất ở đây
        # không phải "không biết" — mà là gán cho kho một văn bản nó không có.
        return [
            f"Tôi không có văn bản nào mang số hiệu {so}.",
            "Văn bản đó có thể tồn tại mà tôi chưa nạp — tôi chỉ nói được về "
            "những gì tôi có, nên đây không phải kết luận rằng nó không tồn tại.",
        ]
    if len(khop) == 1:
        r = khop[0]
        return [
            "Có. Tôi có "
            f"{' — '.join(x for x in hien_van_ban(r['so_ky_hieu'], r['ten']) if x)}.",
            f"Mức phủ: {_muc_phu(r['depth'])}.",
            f"Hiệu lực: {_nhan(r['hieu_luc'])} — {r['hieu_luc'].ly_do}.",
        ]
    # `số/năm` KHÔNG định danh duy nhất. ĐO ĐƯỢC trên corpus: `128/2025` khớp CẢ
    # `128/2025/NĐ-CP` lẫn `128/2025/QH15` — hai văn bản khác nhau, khác cả loại.
    # Lấy `khop[0]` rồi im lặng về phần còn lại là một phát biểu THIẾU về chính
    # kho: người hỏi tin rằng kho có đúng một văn bản mang số hiệu đó. Nêu hết.
    return [
        f"Có. Tôi có {len(khop)} văn bản mang số hiệu {so}:",
        *(_dong_van_ban(r) for r in khop),
    ]


def _mot_van_ban(so: str, kho: list[dict]) -> str:
    return "\n\n".join((*_khoi_mot_so(so, kho), CAU_GIOI_HAN))


def _nhieu_van_ban(sos: list[str], kho: list[dict]) -> str:
    """Câu hỏi nhắc NHIỀU số hiệu — trả lời về TẤT CẢ.

    Bản trước lấy số hiệu đầu tiên rồi im lặng về phần còn lại: "có nghị định
    145/2020 và nghị định 90/2019 không?" được trả lời về 145/2020 và không một
    chữ nào về 90/2019, không cảnh báo phạm vi. Câu trả lời TRÔNG đầy đủ trong
    khi đã bỏ mất một nửa câu hỏi.
    """
    khoi: list[str] = [f"Bạn hỏi về {len(sos)} số hiệu — tôi trả lời từng cái:"]
    for so in sos:
        khoi.append(f"**{so}**")
        khoi.extend(_khoi_mot_so(so, kho))
    khoi.append(CAU_GIOI_HAN)
    return "\n\n".join(khoi)


def _van_ban_dang_dung(kho: list[dict]) -> list[dict]:
    """Văn bản CÒN DÙNG ĐƯỢC — loại hai verdict dứt khoát (`_LOAI_BO`). Tách
    riêng vì cả `_tom_tat` (văn xuôi) lẫn `dung_bang` (Bảng 1/2) đều lọc trên
    đúng tập này; một bản lọc lặp lại ở `dung_bang` sẽ lệch khỏi văn xuôi đúng
    vào ngày ai đó sửa một bên."""
    return [r for r in kho if r["hieu_luc"].verdict not in _LOAI_BO]


def _nhom_theo_loai(dang_dung: list[dict]) -> dict[str, list[dict]]:
    """`dang_dung` gộp theo `loai_van_ban` — DÙNG CHUNG cho văn xuôi và Bảng 1,
    cùng lý do tách của `_van_ban_dang_dung`."""
    nhom: dict[str, list[dict]] = {}
    for r in dang_dung:
        nhom.setdefault(r["loai_van_ban"] or "Chưa rõ loại", []).append(r)
    return nhom


def _sap_xep_loai(nhom: dict[str, list[dict]]) -> list[tuple[str, list[dict]]]:
    """Thứ tự hiển thị CHUNG cho văn xuôi và Bảng 1 — giảm dần theo số lượng,
    rồi theo tên. Một hàm riêng để hai nơi không rời rạc hai bản sao của cùng
    một khoá sắp xếp."""
    return sorted(nhom.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def _dem_theo_loai(nhom: list[dict]) -> tuple[int, int, int]:
    """`(tổng, có toàn văn, chỉ có số hiệu và tên)` của MỘT loại văn bản —
    DÙNG CHUNG cho dòng văn xuôi (`_dong_theo_loai`) và hàng Bảng 1
    (`dung_bang`), để hai nơi không có hai bản đếm lệch nhau."""
    sau = sum(1 for r in nhom if r["depth"] == _CO_TOAN_VAN)
    return len(nhom), sau, len(nhom) - sau


def _dong_theo_loai(loai: str, nhom: list[dict]) -> str:
    tong, sau, nong = _dem_theo_loai(nhom)
    # `deep` và `shallow` gộp thành một con số là nói quá mức phủ: một văn bản
    # `shallow` chỉ có MỘT hàng `mo_dau` mang tên nó (migration 016), không có
    # điều khoản nào trích dẫn được.
    muc = ", ".join(x for x in (
        f"{sau} có toàn văn" if sau else "",
        f"{nong} chỉ có số hiệu và tên" if nong else "",
    ) if x)
    return f"- {loai}: {tong} — {muc}"


# Câu hỏi nhắm THẲNG vào Bộ luật. Không dùng regex phức tạp: hai cụm này phủ
# cách người ta hỏi thật ("có bao nhiêu bộ luật", "kho có những bộ luật nào").
_CUM_BO_LUAT = ("bo luat", "bộ luật")


def hoi_dich_danh_bo_luat(cau_hoi: str) -> bool:
    """Câu hỏi hỏi RIÊNG về Bộ luật, chứ không hỏi chung về kho.

    Tồn tại vì thứ tự khối quyết định câu trả lời có đúng câu hỏi hay không.
    Đo 2026-09-15: "có bao nhiêu bộ luật" trả về 1761 ký tự, mở bằng
    "1634 văn bản... 209... 234... 59... 1132..." và mãi ~700 ký tự sau mới tới
    "6 Bộ luật". Mọi con số đều đúng; câu trả lời vẫn sai, vì thứ người hỏi cần
    nằm ở giữa một bức tường họ không đọc tới.
    """
    t = (cau_hoi or "").lower()
    return any(c in t for c in _CUM_BO_LUAT)


def _tom_tat(kho: list[dict], uu_tien_bo_luat: bool = False) -> str:
    dang_dung = _van_ban_dang_dung(kho)
    da_thay = len(kho) - len(dang_dung)

    nhom = _nhom_theo_loai(dang_dung)

    # Tách ba nhóm thay vì hai. Gộp "xác định được" với "chưa xác định" thành một
    # con số là chỗ dự án này dễ nói mềm nhất: khoảng cách giữa "đã kiểm và ổn" và
    # "đồ thị không có tín hiệu nào" là toàn bộ lý do bảy phép kiểm tồn tại, và
    # trên DB thật nhóm sau là 47/130 — hơn một phần ba kho.
    xac_dinh = [r for r in dang_dung if r["hieu_luc"].verdict in _XAC_DINH_DUOC]
    # `can_doi_chieu_tay` tách RIÊNG khỏi `chua_xac_dinh`, không gộp: hai thứ đó
    # nói hai mức biết khác nhau. `chua_xac_dinh` = đồ thị KHÔNG có tín hiệu nào;
    # `can_doi_chieu_tay` = BIẾT có văn bản sửa nhưng chưa đọc được ngày, tức CÓ
    # tín hiệu, chỉ thiếu một dữ kiện. Bản trước gộp cả hai vào câu "đồ thị văn
    # bản không có tín hiệu nào về chúng" — một phát biểu SAI về 3 văn bản trong
    # kho thật, và sai đúng thứ dự án này không được phép sai: mức độ mình biết.
    can_nguoi = [r for r in dang_dung if r["hieu_luc"].verdict == V.can_doi_chieu_tay]
    chua_ro = len(dang_dung) - len(xac_dinh) - len(can_nguoi)

    khoi = [
        f"Tôi hiện có {len(kho)} văn bản pháp luật Việt Nam."
        + (f" {len(xac_dinh)} văn bản tôi xác định được tình trạng hiệu lực — còn"
           " hiệu lực, sắp có hiệu lực, hoặc còn hiệu lực nhưng đã bị sửa đổi." if xac_dinh else "")
        # "chưa kết luận được", KHÔNG "không có tín hiệu nào": một verdict mới
        # thêm vào enum mà chưa ai xét ở đây cũng rơi vào nhóm này, và khẳng định
        # "không có tín hiệu" thay cho nó lại là một phát biểu chưa kiểm.
        + (f" {chua_ro} văn bản tôi chưa kết luận được về hiệu lực — đồ thị văn"
           " bản không có tín hiệu nào, hoặc tín hiệu chưa đủ để chốt."
           if chua_ro else "")
        + (f" {len(can_nguoi)} văn bản cần đối chiếu tay: tôi biết có văn bản"
           " sửa nhưng chưa đọc được ngày, nên không tự chốt." if can_nguoi else "")
        + (f" {da_thay} bản đã hết hiệu lực hoặc đã bị thay thế thì tôi vẫn giữ,"
           " để đối chiếu khi câu hỏi thuộc về thời điểm cũ." if da_thay else ""),
        "Phân theo loại văn bản:\n" + "\n".join(
            _dong_theo_loai(loai, ns) for loai, ns in _sap_xep_loai(nhom)
        ),
    ]

    bo_luat = [r for r in dang_dung if r["loai_van_ban"] == "Bộ luật"]
    if bo_luat:
        # Nêu ĐÍCH DANH: một con số không kiểm được, một danh sách thì kiểm
        # được. Kèm nhãn hiệu lực cho từng bộ vì năm trong sáu bộ hiện hành đang
        # bị sửa đổi một phần — liệt kê chúng như văn bản nguyên vẹn là bỏ đúng
        # cái người đọc cần biết.
        khoi.append(f"{len(bo_luat)} Bộ luật tôi đang có:\n" + "\n".join(
            f"- {hien_van_ban(r['so_ky_hieu'], r['ten'])[1]} — {_nhan(r['hieu_luc'])}"
            for r in bo_luat))

    if uu_tien_bo_luat and bo_luat:
        # Đưa khối Bộ luật lên ĐẦU khi người ta hỏi đích danh nó. Không cắt bớt
        # phần còn lại: bối cảnh kho vẫn đúng và vẫn hữu ích, nó chỉ không được
        # đứng trước câu trả lời.
        khoi.insert(0, khoi.pop(-1))
    khoi.append(CAU_GIOI_HAN)
    return "\n\n".join(khoi)


def dung_cau_tra_loi(cau_hoi: str, kho: list[dict]) -> str:
    """Tầng THUẦN — không DB, không LLM. Tách khỏi `nap_kho` để guard chống ảo
    giác chạy được trong bộ test mặc định (`-m "not integration"`) thay vì chỉ
    khi có Postgres.

    Hai hình dạng, chọn bằng quy tắc: câu hỏi nêu đích danh một số hiệu → tra
    có/không; còn lại → tóm tắt kho.
    """
    sos = moi_so_hieu_trong(cau_hoi)
    if not sos:
        return _tom_tat(kho, uu_tien_bo_luat=hoi_dich_danh_bo_luat(cau_hoi))
    return _mot_van_ban(sos[0], kho) if len(sos) == 1 else _nhieu_van_ban(sos, kho)


# Câu dẫn khi câu hỏi xin bảng — NGẮN, không lặp lại số liệu của bảng thành
# văn xuôi (người đọc không cần cùng một con số hai lần). Ghép với
# `CAU_GIOI_HAN` y hệt mọi nhánh khác của module này (`loi_dan_bang`).
CAU_DAN_BANG = (
    "Tôi dựng hai bảng dưới đây từ những văn bản tôi hiện có: một bảng phân theo "
    "loại văn bản, một bảng phân theo lĩnh vực."
)


def loi_dan_bang() -> str:
    """`answer` cho lượt xin bảng — câu dẫn ngắn ở trên rồi đóng bằng
    `CAU_GIOI_HAN`, cùng khuôn `_mot_van_ban`/`_nhieu_van_ban`/`_tom_tat`."""
    return "\n\n".join((CAU_DAN_BANG, CAU_GIOI_HAN))


# Ba tầng gốc của hệ thống văn bản pháp luật Việt Nam mà "Độ sâu" (Bảng 2) suy
# ra từ dữ liệu — Luật/Bộ luật ở trên, Nghị định ở giữa, Thông tư ở dưới. Nêu
# TƯỜNG MINH ở đây (không suy từ tên lĩnh vực) để một lĩnh vực mới xuất hiện
# vẫn tự ra đúng câu, không cần sửa mã.
_TANG_GOC: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("luật", ("Luật", "Bộ luật")),
    ("nghị định", ("Nghị định",)),
    ("thông tư", ("Thông tư",)),
)


# Hai nhãn độ sâu mà `gioi_thieu` đọc lại để dựng câu văn xuôi — HẰNG SỐ ở đây
# chứ không phải hai chuỗi chép sang bên đó, cùng lý do `CAU_GIOI_HAN` chỉ có
# một bản: một bản sao sẽ lệch pha đúng vào ngày ai đó sửa lời một bên.
DO_SAU_DU_BA_TANG = "đủ luật, nghị định, thông tư"
DO_SAU_CHI_LUAT_GOC = "chỉ luật gốc"


def _do_sau_linh_vuc(nhom: list[dict]) -> str:
    """"Độ sâu" đọc được của MỘT lĩnh vực — suy từ các tầng gốc (`_TANG_GOC`)
    đã có TOÀN VĂN trong nhóm, không viết cứng theo tên lĩnh vực.

    Ba câu brief nêu tên (`đủ luật, nghị định, thông tư` / `chỉ luật gốc` /
    `chỉ số hiệu và tên`) là BA CA CỦA cùng một hàm, không phải ba nhánh gõ
    tay: `tang` là tập tầng gốc có toàn văn, và ba câu đó ứng với `tang` đủ ba,
    `tang` chỉ có "luật", và không văn bản nào trong nhóm có toàn văn.

    # ponytail: tổ hợp `tang` khác ba ca trên (vd. chỉ "nghị định", hoặc
    # "luật"+"nghị định" thiếu "thông tư") rơi vào câu chung "có <tầng>,
    # <tầng>" — chưa xảy ra trên DB thật (mọi văn bản `deep` hiện có đều thuộc
    # đúng ba tầng này), nâng cấp thành câu riêng nếu đo được một tổ hợp cần
    # lời khác.
    """
    if not any(r["depth"] == _CO_TOAN_VAN for r in nhom):
        return "chỉ số hiệu và tên"
    tang = [ten for ten, loai in _TANG_GOC
            if any(r["depth"] == _CO_TOAN_VAN and r["loai_van_ban"] in loai for r in nhom)]
    if tang == [t for t, _ in _TANG_GOC]:
        return DO_SAU_DU_BA_TANG
    if tang == ["luật"]:
        return DO_SAU_CHI_LUAT_GOC
    return "có " + ", ".join(tang) if tang else "có toàn văn"


# Tiền tố loại và hậu tố số hiệu trong `ten` — cắt bằng QUY TẮC, không bằng
# danh sách sáu cái tên: một Bộ luật mới nạp vào kho phải tự ra tên ngắn đúng
# (ex.md §7.3.1), không chờ ai sửa mã.
_RE_TIEN_TO_BO_LUAT = re.compile(r"^bộ\s+luật\s*", re.IGNORECASE)
_RE_HAU_TO_SO = re.compile(r"\s+số\s+\d\S*$", re.IGNORECASE)


def ten_ngan_bo_luat(ten: str, so_ky_hieu: str) -> str:
    """"Bộ luật Dân sự số 91/2015/QH13" → "Dân sự" — tên gọi trong một câu văn
    xuôi, nơi lặp lại "Bộ luật" sáu lần sau chữ "6 Bộ luật:" là tiếng ồn.

    Rơi về `ten` nguyên khi quy tắc cắt hết chữ: một cái tên đúng-mà-dài vẫn
    tốt hơn một chuỗi rỗng trong danh sách người đọc dùng để kiểm.
    """
    goc = (ten or "").strip()
    so = (so_ky_hieu or "").strip()
    t = goc
    if so and t.endswith(f" số {so}"):
        t = t[: -len(f" số {so}")]
    t = _RE_TIEN_TO_BO_LUAT.sub("", _RE_HAU_TO_SO.sub("", t)).strip()
    # Chỉ viết hoa CHỮ ĐẦU: "Bộ Luật lao động" → "lao động" → "Lao động", còn
    # `str.capitalize()` sẽ hạ "Tố tụng Dân sự" thành "Tố tụng dân sự".
    return t[0].upper() + t[1:] if t else goc


def danh_sach_bo_luat(kho: list[dict]) -> list[dict]:
    """Các Bộ luật ĐANG DÙNG ĐƯỢC, theo thứ tự kho — cùng `_van_ban_dang_dung`
    mà `_tom_tat` lọc, nên sáu bản đã bị thay không lọt vào (ex.md §7.3.2)."""
    ds = []
    for r in _van_ban_dang_dung(kho):
        if r["loai_van_ban"] != "Bộ luật":
            continue
        so, ten = hien_van_ban(r["so_ky_hieu"], r["ten"])
        ds.append({"ten": ten, "ten_ngan": ten_ngan_bo_luat(ten, so),
                   "so_ky_hieu": so, "hieu_luc": _nhan(r["hieu_luc"])})
    return ds


def tom_tat_linh_vuc(kho: list[dict]) -> list[dict]:
    """Bảng 2 dưới dạng dữ liệu — MỘT phép gộp lĩnh vực cho cả bảng lẫn câu văn
    xuôi của `gioi_thieu`. Hai bản gộp sẽ lệch đúng vào ngày ai đó sửa một bên,
    cùng lý do `_van_ban_dang_dung`/`_dem_theo_loai` được tách ra."""
    nhom: dict[str, list[dict]] = {}
    for r in _van_ban_dang_dung(kho):
        nhom.setdefault(r["linh_vuc"] or "", []).append(r)
    return [{"linh_vuc": lv, "so_van_ban": len(rs), "do_sau": _do_sau_linh_vuc(rs)}
            for lv, rs in sorted(nhom.items(), key=lambda kv: (-len(kv[1]), kv[0]))]


def dung_bang(cau_hoi: str, kho: list[dict]) -> list[Bang]:
    """Tầng THUẦN — không DB, không LLM, cùng tầng và cùng tham số với
    `dung_cau_tra_loi`. `cau_hoi` không lọc gì ở đây hôm nay (hai bảng dưới
    LUÔN tóm tắt TOÀN kho, giống `_tom_tat`) — giữ tham số để chữ ký khớp
    `dung_cau_tra_loi` và không phải đổi lần sau nếu có bảng lọc theo câu hỏi.

    Dựng từ CÙNG `kho: list[dict]` mà `_tom_tat` dùng — không truy vấn DB
    thứ hai. Đọc docstring `dung_cau_tra_loi` để biết vì sao tầng này tách
    khỏi `nap_kho`: guard chống ảo giác phải chạy được trong bộ test mặc định.

    Bảng 1 dùng LẠI đúng phép đếm/sắp xếp mà `_tom_tat`/`_dong_theo_loai`
    dùng (`_van_ban_dang_dung`/`_nhom_theo_loai`/`_sap_xep_loai`/
    `_dem_theo_loai`) — hai bản đếm sẽ lệch đúng vào ngày ai đó sửa một bên.

    Bảng 2 gộp theo GIÁ TRỊ NGUYÊN VĂN của `linh_vuc`, không tách chuỗi nhiều
    lĩnh vực cách nhau bằng dấu phẩy — dữ liệu nguồn (`metadata.parquet`, T1)
    vốn vậy, không phải lỗi cần "làm sạch". `linh_vuc IS NULL` gộp về khoá
    `""`: KHÔNG bịa một nhãn ("Chưa phân loại" đã bị `nap_linh_vuc.py` coi là
    rỗng đúng vì lý do này — xem `_CHUA_PHAN_LOAI` ở đó); một ô trống nói đúng
    "không có giá trị", một nhãn bịa nói một điều không kiểm được.
    """
    dang_dung = _van_ban_dang_dung(kho)

    bang_loai = Bang(
        tieu_de="Phân theo loại văn bản",
        cot=["Loại văn bản", "Tổng", "Có toàn văn", "Chỉ có số hiệu và tên"],
        dong=[[loai, *map(str, _dem_theo_loai(ns))]
              for loai, ns in _sap_xep_loai(_nhom_theo_loai(dang_dung))],
    )

    bang_linh_vuc = Bang(
        tieu_de="Phân theo lĩnh vực",
        cot=["Lĩnh vực", "Số văn bản", "Độ sâu"],
        dong=[[d["linh_vuc"], str(d["so_van_ban"]), d["do_sau"]]
              for d in tom_tat_linh_vuc(kho)],
    )
    return [bang_loai, bang_linh_vuc]


def tra_loi_ve_kho(engine: Engine, cau_hoi: str, as_of: date) -> str:
    """Chuỗi đã hoàn chỉnh, đưa thẳng vào `answer`."""
    return dung_cau_tra_loi(cau_hoi, nap_kho(engine, as_of))
