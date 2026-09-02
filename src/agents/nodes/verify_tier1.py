"""⭐ Verify tầng 1 — ĐÓNG GÓP CHÍNH của khoá luận.

Luận điểm: tính hợp lệ của một trích dẫn pháp luật là phép TRA BẢNG, không phải
bài toán suy luận. Phần lớn hệ thống hiện nay nhờ chính LLM tự kiểm nó — sai về
nguyên tắc, vì cùng một mô hình vừa sinh ra lỗi vừa được giao việc phát hiện lỗi
đó. Tầng này bắt phần lớn ảo giác citation với CHI PHÍ 0 TOKEN và, theo định
nghĩa của phép so chuỗi, không có sai số.

Module này KHÔNG ĐƯỢC gọi mạng: không client LLM, không thư viện HTTP. Ba test
độc lập khẳng định điều đó (chữ ký hàm · quét AST phần import · chặn socket rồi
chạy đủ bốn phép kiểm). Nếu một ngày tầng này cần một lần gọi mô hình thì thiết
kế đã hỏng, không phải test.

Bốn phép kiểm — BA loại, MỘT cảnh báo:

  1. `provision_id` có tồn tại trong CSDL?          → không thì DROP
  2. `provision_id` có trong tập đã truy hồi?       → không thì DROP
  3. `quote` là văn bản nguyên văn của điều đó?     → không thì DROP
     (ba nhánh, ba mã riêng: rỗng · quá ngắn · không khớp)
  4. điều luật còn hiệu lực tại `as_of`?            → không thì WARN, VẪN trả lời

Phép kiểm 2 là phép dễ quên nhất và khó phát hiện nhất khi thiếu: một điều luật
có thể CÓ THẬT trong CSDL mà chưa từng được đưa vào context, nghĩa là mô hình
lấy nó ra từ tham số của chính nó chứ không từ tài liệu được cho xem. Gộp nó vào
phép kiểm 1 sẽ giấu mất đúng chế độ hỏng đó.

Phép kiểm 4 CỐ Ý là cảnh báo chứ không phải loại: một trích dẫn tới điều luật đã
hết hiệu lực vẫn là một trích dẫn CÓ THẬT, và người hỏi thường cần biết chính
xác điều đó ("quy định cũ nói gì, ai thay nó"). Trộn hai chuyện lại sẽ làm bảng
kết quả không phân biệt được "mô hình bịa" với "luật đã đổi".
"""

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import Engine, text

from src.agents.nodes.generate_claims import Claim
from src.services.effectivity import (
    Effectivity,
    ap_sua_doi,
    danh_gia_theo_id,
    nap_sua_doi,
)

# Chuẩn hoá CHỈ ĐỂ SO KHỚP. Cùng bộ ba mà `prov_parser._khoa` đã phải trả giá ở
# Plan 1: zero-width vô hình nhưng làm hai chuỗi "khác nhau"; Ð U+00D0 (LATIN
# CAPITAL LETTER ETH) hiện lên y hệt Đ U+0110 và có thật 2 lần trong 101/2015/QH13
# ("Ðoàn thanh niên", Điều 414 và 420).
_MAP_KHOA = str.maketrans({"​": "", "﻿": "", "Ð": "Đ", "ð": "đ"})

# Sàn độ dài quote, tính bằng ký tự SAU `normalize`.
#
# Không có sàn thì phép kiểm 3 có một đường vòng tầm thường: `quote = "a"` là
# substring của gần như mọi điều luật, nên mô hình "trích dẫn" một ký tự là luôn
# được đóng dấu đã kiểm chứng. Đó là lỗ hổng NGUYÊN TẮC ở đúng phép kiểm trung
# tâm của khoá luận, không phải lỗi cài đặt.
#
# 12 là số ĐO RA, không phải số bịa. Trên 65 quote thật do `generate_claims`
# sinh (30 lần gọi, `temperature=0.0`, câu hỏi lấy từ `golden_qa.yaml`):
#
#     ký tự sau normalize   min=32  p10=80  trung vị=191  tb=217  max=1126
#     số từ                 min=7   p10=17  trung vị=42   tb=48   max=259
#
# Sàn đặt AN TOÀN DƯỚI mức nhỏ nhất quan sát được (32 / 12 ≈ 2,7× dự phòng), cố
# ý KHÔNG đặt sát: mục đích là chặn ca suy biến, không phải lọc quote thật. Ở
# tiếng Việt 12 ký tự là 2-3 từ — dưới mọi mệnh đề có thể làm căn cứ pháp lý.
#
# ponytail: sàn độ dài là phép xấp xỉ THÔ của "quote này có đặc trưng cho điều
# luật được dẫn không". Phép đo đúng là TÍNH ĐẶC TRƯNG — một quote xuất hiện
# trong 500 điều luật không phải bằng chứng cho điều nào cả. Vẫn là tra bảng,
# nhưng đắt hơn mỗi claim. Nâng cấp khi Task 9 cho phân bố ở quy mô lớn hơn;
# n=65 còn ít.
QUOTE_TOI_THIEU = 12


class Tier1Reason(StrEnum):
    """Mỗi phép kiểm có ĐÚNG MỘT lý do của riêng nó.

    Tỉ lệ loại TÁCH THEO TỪNG LÝ DO là số liệu của chương đánh giá: "bịa ra một
    id không tồn tại", "dẫn điều luật chưa từng được cho xem" và "viết lại nội
    dung rồi gọi đó là trích dẫn" là ba chế độ hỏng khác nhau của mô hình, đòi
    ba cách khắc phục khác nhau. Gộp chúng thành một nhãn "không hợp lệ" là vứt
    đi phần dữ liệu có giá trị nhất.
    """

    ok = "ok"
    provision_khong_ton_tai = "provision_khong_ton_tai"   # phép kiểm 1
    khong_trong_context = "khong_trong_context"           # phép kiểm 2
    quote_rong = "quote_rong"                             # phép kiểm 3a
    quote_qua_ngan = "quote_qua_ngan"                     # phép kiểm 3b
    quote_khong_khop = "quote_khong_khop"                 # phép kiểm 3c


@dataclass(frozen=True)
class Tier1Result:
    claim: Claim
    ok: bool
    reason: Tier1Reason
    effectivity: Effectivity | None
    khop_tai: int | None = None
    """`provisions.id` của DÒNG chứa quote — có thể là một Khoản/Điểm con của
    điều được dẫn (xem `_cay_con`). `None` với mọi claim bị loại.

    Không chỉ để debug: nó là bằng chứng phép kiểm 3 đã khớp ở đâu, và cho phép
    câu trả lời neo trích dẫn vào đúng Khoản thay vì cả Điều."""


def normalize(s: str) -> str:
    """Đưa chuỗi về ĐÚNG dạng corpus đã được nạp — không hơn.

    Mức chuẩn hoá ở đây quyết định phép kiểm 3 đúng hay sai, nên nó được chọn
    theo một quy tắc chứ không theo cảm tính: **normalize là hàm ngược của phép
    biến đổi lúc nạp, không phải một núm vặn độ dễ tính.**

    `prov_parser._chuan_hoa` (dạng ĐƯỢC LƯU) = NFC + gộp khoảng trắng, kèm
    `_khoa` thêm Ð→Đ và bỏ zero-width khi so khớp. Đo lại trên DB hiện tại:
    `provisions` có 0/19.135 dòng non-NFC, còn Ð U+00D0 thì vẫn còn 2 dòng —
    nên cả hai phép đều phải áp cho CẢ HAI PHÍA (quote đến từ LLM, không từ
    corpus, và LLM sinh được NFD).

    KHÔNG casefold, KHÔNG bỏ dấu. Cả hai đều là thay đổi NỘI DUNG chứ không phải
    thay đổi cách biểu diễn, và nới đến đó nghĩa là một quote SAI khớp một điều
    luật ĐÚNG — tầng 1 đóng dấu "đã kiểm chứng" cho trích dẫn bịa, đúng chế độ
    hỏng cả khoá luận tồn tại để chống. Trong tiếng Việt dấu là chữ chứ không
    phải trang trí: Điều 127 CẤM "Phạt tiền" người lao động, còn "phát tiền"
    (84/2015/QH13 Điều 23) là hành vi ngược lại — bỏ dấu thì hai chuỗi trùng
    khít. Plan 2 đã đo phần casefold: bật nó nâng độ phủ một văn bản +0,63pp
    bằng cách CHE ~20 token thiếu thật.

    Prompt `generate_claims.v1` cũng đã quy định `quote` là "đoạn NGUYÊN VĂN
    copy... không sửa dấu câu", nên so khớp chặt là THI HÀNH hợp đồng đã nêu với
    mô hình, không phải áp thêm một đòi hỏi mới lên nó.
    """
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", s or "")).strip().translate(_MAP_KHOA)


def _cay_con(goc: int, db_provisions: dict[int, dict]) -> list[dict]:
    """Điều được dẫn + MỌI hậu duệ của nó (Khoản, Điểm...), theo `parent_id`.

    Đây là phần không thể bỏ của phép kiểm 3. Đo trên corpus: 2.289/3.112 Điều
    (73,6%) có `noi_dung` CHỈ LÀ TIÊU ĐỀ, thân điều luật nằm ở các dòng con.
    `45/2019/QH14 > Điều 127` là ca đại diện — `noi_dung` của nó đúng một dòng
    "Điều 127. Các hành vi bị nghiêm cấm khi xử lý kỷ luật lao động", còn
    "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động." nằm ở Khoản 2.

    Đối chiếu quote vào MỘT DÒNG `provisions` sẽ loại nhầm claim hợp lệ trên
    73,6% số Điều — false-negative quy mô lớn ở đúng phép kiểm trung tâm, và
    trong bảng kết quả nó trông y hệt "mô hình bịa trích dẫn".
    """
    con: dict[int, list[dict]] = {}
    for p in db_provisions.values():
        con.setdefault(p.get("parent_id"), []).append(p)

    # `da_tham` chống `parent_id` vòng: dữ liệu vòng làm DFS chạy mãi, và một
    # test CI đứng im tốn nhiều thời gian hơn hẳn một cái set.
    ra: list[dict] = []
    da_tham: set[int] = set()
    ngan_xep = [db_provisions[goc]]
    while ngan_xep:
        nut = ngan_xep.pop()
        if nut["id"] in da_tham:
            continue
        da_tham.add(nut["id"])
        ra.append(nut)
        ngan_xep.extend(con.get(nut["id"], ()))
    return ra


def _tim_quote(q: str, cay: list[dict]) -> int | None:
    """`provisions.id` của dòng chứa `q` (ĐÃ normalize), hoặc None.

    So với TỪNG DÒNG một, KHÔNG nối cả cây thành một chuỗi rồi so: nối lại tạo
    ra những vết ghép không tồn tại trong văn bản gốc, và một "quote" vắt qua
    ranh giới tiêu đề Điều sang thân Khoản 1 sẽ khớp dù nó không nguyên văn ở
    bất kỳ đâu. Một trích dẫn pháp luật nguyên văn luôn nằm gọn trong một đơn vị
    của corpus.

    Đo được, không phải lo xa: 6/65 quote thật (9,2%) do `generate_claims` sinh
    ra ĐÚNG LÀ những mảnh ghép kiểu đó — mô hình nối câu dẫn của Điều với một
    hoặc nhiều Khoản con bằng "\n\n", một trường hợp còn chèn thẳng "..." đánh
    dấu phần đã lược. Nối cây lại sẽ đóng dấu đã kiểm chứng cho chính chúng.
    """
    return next((p["id"] for p in cay if q in normalize(p.get("noi_dung") or "")), None)


def verify_tier1(
    claims: list[Claim],
    expanded: list[dict],
    db_provisions: dict[int, dict],
    effectivity_of: Callable[[int], Effectivity],
) -> list[Tier1Result]:
    """Bốn phép kiểm trên từng claim. Hàm thuần: không I/O, không mạng.

    `expanded`  — đúng những provision đã được đưa vào prompt (phép kiểm 2).
    `db_provisions` — tra cứu theo `provisions.id`, PHẢI chứa cả điều luật được
        claim dẫn (kể cả điều KHÔNG được truy hồi) lẫn hậu duệ của chúng; xem
        `nap_provisions`. Nếu chỉ truyền vào tập đã truy hồi thì mọi claim dẫn
        một điều có thật nhưng chưa được cho xem sẽ bị dán nhãn
        `provision_khong_ton_tai`, và hai lý do loại — hai chế độ hỏng khác
        nhau của mô hình — sẽ lẫn vào nhau đúng ở bảng số liệu cần chúng tách.
    `effectivity_of` — provision_id → `Effectivity`; dùng
        `effectivity_qua_provision` để nó đi qua cơ chế của Task 2.
    """
    trong_context = {p["id"] for p in expanded}
    ra: list[Tier1Result] = []

    for c in claims:
        # ── Phép kiểm 1 — điều luật có tồn tại? ──────────────────────────────
        if c.provision_id not in db_provisions:
            ra.append(Tier1Result(c, False, Tier1Reason.provision_khong_ton_tai, None))
            continue

        # ── Phép kiểm 2 — có trong tập đã truy hồi? ──────────────────────────
        if c.provision_id not in trong_context:
            ra.append(Tier1Result(c, False, Tier1Reason.khong_trong_context, None))
            continue

        # ── Phép kiểm 3 — quote nguyên văn, đối chiếu vào CẢ CÂY CON ─────────
        # Ba nhánh, ba mã: không trích gì · trích một mẩu vô nghĩa · bịa nội
        # dung. Xem `Tier1Reason` — gộp lại là mất đúng thứ cần đo.
        q = normalize(c.quote)
        if not q:
            ra.append(Tier1Result(c, False, Tier1Reason.quote_rong, None))
            continue
        if len(q) < QUOTE_TOI_THIEU:
            ra.append(Tier1Result(c, False, Tier1Reason.quote_qua_ngan, None))
            continue
        khop_tai = _tim_quote(q, _cay_con(c.provision_id, db_provisions))
        if khop_tai is None:
            ra.append(Tier1Result(c, False, Tier1Reason.quote_khong_khop, None))
            continue

        # ── Phép kiểm 4 — hiệu lực: CẢNH BÁO, không loại ─────────────────────
        # Chỉ tra cho claim đã qua ba phép trên: tra cho claim đã bị loại vừa
        # thừa, vừa làm một kết quả DROP trông như đã được kiểm hiệu lực.
        ra.append(Tier1Result(c, True, Tier1Reason.ok, effectivity_of(c.provision_id), khop_tai))

    return ra


def citation_precision(results: list[Tier1Result]) -> float:
    """Metric riêng của đề tài: tính được bằng phép đếm, không cần LLM judge."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.ok) / len(results)


# ── Tầng DB ──────────────────────────────────────────────────────────────────
# `UNION` chứ không `UNION ALL`: `parent_id` vòng làm `UNION ALL` chạy vô hạn
# trong Postgres, còn `UNION` khử trùng nên vòng tự cạn. Cây một Điều chỉ vài
# chục dòng, phần khử trùng không đáng kể.
_SQL_CAY = text(
    "WITH RECURSIVE cay AS ("
    "  SELECT id, parent_id, document_id, duong_dan, noi_dung"
    "    FROM provisions WHERE id = ANY(:ids)"
    "  UNION"
    "  SELECT p.id, p.parent_id, p.document_id, p.duong_dan, p.noi_dung"
    "    FROM provisions p JOIN cay c ON p.parent_id = c.id"
    ") SELECT * FROM cay"
)


def nap_provisions(engine: Engine, provision_ids: Iterable[int]) -> dict[int, dict]:
    """`provisions.id` → dòng, KÈM toàn bộ hậu duệ — nguyên liệu của phép kiểm 1 và 3.

    Truyền vào id của MỌI claim cộng id của tập đã truy hồi, để phép kiểm 1 và
    phép kiểm 2 tách được nhau (xem `verify_tier1`). Id không có trong CSDL đơn
    giản là vắng mặt trong kết quả — đó là phán quyết hợp lệ của phép kiểm 1,
    không phải lỗi. Lỗi truy vấn thì để nổ: một `except` ở đây sẽ biến "CSDL
    hỏng" thành "mô hình bịa toàn bộ trích dẫn".
    """
    ids = list(provision_ids)
    if not ids:
        return {}
    with engine.connect() as conn:
        return {r["id"]: dict(r) for r in conn.execute(_SQL_CAY, {"ids": ids}).mappings().all()}


def effectivity_qua_provision(
    engine: Engine, db_provisions: dict[int, dict], as_of: date
) -> Callable[[int], Effectivity]:
    """Adapter provision_id → `Effectivity` cho phép kiểm 4, ĐI QUA Task 2.

    `danh_gia_theo_id` chứ không phải `documents.tinh_trang`: trường của MOJ SAI
    4/6 trên chính chuỗi nghị định lương tối thiểu (122/2015, 141/2017, 157/2018,
    90/2019 đều đã bị thay nhưng vẫn mang "còn hiệu lực"). Đọc thẳng nó là tái
    lập đúng cái lỗi mà Task 2 sinh ra để sửa.

    Nhớ theo `document_id`: hiệu lực là thuộc tính của VĂN BẢN, còn một câu trả
    lời thường dẫn nhiều điều của cùng một văn bản — không nhớ thì mỗi claim là
    một lượt ba truy vấn lặp lại y hệt.

    **Mức 4 phá đúng giả định "một văn bản, một phán quyết" đó, và cố ý.** Bản
    đồ sửa đổi từ văn bản hợp nhất của Công báo neo ở CẤP ĐIỀU KHOẢN: trong cùng
    Bộ luật Lao động, Khoản 1 Điều 139 đã bị 113/2025/QH15 sửa từ 01/7/2026 còn
    Điều 140 thì không. Nên cache cấp văn bản được GIỮ (nó là phần đắt — ba truy
    vấn), rồi `ap_sua_doi` phủ lên phần cấp điều khoản. Bản đồ nạp MỘT LẦN cho
    cả tập provision, không phải một truy vấn mỗi claim.

    Điều khoản không có bản ghi sửa đổi nhận lại ĐÚNG object cũ — 19.131/19.135
    dòng không đổi một ký tự, nên bảng số liệu cũ vẫn so được.
    """
    da_biet: dict[str, Effectivity] = {}
    ban_do = nap_sua_doi(engine, list(db_provisions))

    def tra(provision_id: int) -> Effectivity:
        doc_id = db_provisions[provision_id]["document_id"]
        if doc_id not in da_biet:
            da_biet[doc_id] = danh_gia_theo_id(engine, doc_id, as_of)
        return ap_sua_doi(da_biet[doc_id], ban_do.get(provision_id, ()), as_of)

    return tra


# ══ Phép kiểm thứ sáu (coordinator, sau phép kiểm thứ năm ở assemble.py) ═════
# Ở ĐẦU VÀO — trước khi chạy pipeline, không phải sau khi có answer. Câu hỏi
# tự nêu "Điều N [văn bản]" mà Điều đó KHÔNG có trong ĐÚNG văn bản được nêu:
# hệ thống không được âm thầm bỏ qua tiền đề sai đó rồi trả lời một câu hỏi
# khác — với một hệ thống chống ảo giác, im lặng trước tiền đề sai cũng là một
# dạng để người dùng tin sai (Điều 999 không tồn tại, nhưng câu trả lời về
# "nghỉ phép" khiến người đọc tin Điều 999 nói đúng điều đó).
#
# Vẫn TRA BẢNG, 0 TOKEN: regex rút "Điều N" + tên văn bản NGAY SAU nó, một
# truy vấn SQL kiểm tồn tại theo ĐÚNG (document, số Điều) — không phải theo
# số Điều một mình (Điều 550 có thật ở Bộ luật Dân sự, KHÔNG có ở Bộ luật Tố
# tụng dân sự — lẫn hai cái là chặn oan hoặc bỏ lọt sai chiều).
#
# Phạm vi CỐ Ý hẹp: chỉ nhận diện 6 Bộ luật trong corpus (tên đầy đủ, viết tắt
# thường gặp, hoặc so_ky_hieu) — không phải một bộ nhận diện thực thể văn bản
# tổng quát. Không nhận ra văn bản nào thì KHÔNG CHẶN (thà bỏ lọt còn hơn chặn
# nhầm câu hỏi hợp lệ) — xem test hai chiều.
_RE_DIEU_CAU_HOI = re.compile(r"[Đđ]iều\s+(\d+)")

# Thứ tự CÓ Ý NGHĨA: mẫu CỤ THỂ HƠN ("tố tụng dân sự") phải đứng TRƯỚC mẫu
# chung ("dân sự"/"hình sự"), nếu không "Bộ luật Tố tụng Dân sự" sẽ khớp nhầm
# thành "dân sự" (thứ tự dò tìm dừng ở mẫu ĐẦU TIÊN khớp).
_VAN_BAN_BO_LUAT: tuple[tuple[re.Pattern, str, str], ...] = (
    (re.compile(r"tố tụng dân sự|blttds", re.IGNORECASE), "92/2015/QH13", "Bộ luật Tố tụng dân sự"),
    (re.compile(r"tố tụng hình sự|bltths", re.IGNORECASE), "101/2015/QH13", "Bộ luật Tố tụng hình sự"),
    (re.compile(r"lao động|bllđ|blld\b", re.IGNORECASE), "45/2019/QH14", "Bộ luật Lao động"),
    (re.compile(r"dân sự|blds\b", re.IGNORECASE), "91/2015/QH13", "Bộ luật Dân sự"),
    (re.compile(r"hình sự|blhs\b", re.IGNORECASE), "100/2015/QH13", "Bộ luật Hình sự"),
    (re.compile(r"hàng hải|blhh\b", re.IGNORECASE), "95/2015/QH13", "Bộ luật Hàng hải"),
    (re.compile(r"45/2019/qh14", re.IGNORECASE), "45/2019/QH14", "Bộ luật Lao động"),
    (re.compile(r"91/2015/qh13", re.IGNORECASE), "91/2015/QH13", "Bộ luật Dân sự"),
    (re.compile(r"100/2015/qh13", re.IGNORECASE), "100/2015/QH13", "Bộ luật Hình sự"),
    (re.compile(r"92/2015/qh13", re.IGNORECASE), "92/2015/QH13", "Bộ luật Tố tụng dân sự"),
    (re.compile(r"101/2015/qh13", re.IGNORECASE), "101/2015/QH13", "Bộ luật Tố tụng hình sự"),
    (re.compile(r"95/2015/qh13", re.IGNORECASE), "95/2015/QH13", "Bộ luật Hàng hải"),
)

_CUA_SO_KY_TU = 40  # đủ cho "Điều N Bộ luật Tố tụng dân sự" hoặc "theo Bộ luật Lao động, Điều N"


def _van_ban_gan_dieu(q: str, m: re.Match) -> tuple[str, str] | None:
    """Văn bản khớp GẦN match "Điều N" NHẤT — quét CẢ HAI CHIỀU (trước và sau
    vị trí "Điều N"), chọn theo KHOẢNG CÁCH TUYỆT ĐỐI tới "Điều N", KHÔNG theo
    thứ tự trong bảng `_VAN_BAN_BO_LUAT` (silent-failure review round 2):

      C1 — chọn theo thứ tự bảng làm "Điều 600 Bộ luật Dân sự về hợp đồng lao
      động" khớp NHẦM "lao động" (đứng trước "dân sự" trong bảng) dù "Bộ luật
      Dân sự" đứng NGAY SAU "Điều 600" trong câu thật — sai sự thật pháp lý
      (Điều 600 có thật ở BLDS) đưa thẳng ra HTTP qua `coverage_note`.

      H2 — quét chỉ MỘT CHIỀU (về sau) bỏ lọt hoàn toàn cách viết văn bản
      đứng TRƯỚC "Điều N" ("Bộ luật Lao động Điều 999...", "Theo BLLĐ thì
      Điều 999...") — và toàn bộ 15 câu `dieu_khong_ton_tai` của trap.yaml
      tình cờ dùng CHUNG một trật tự từ, nên 15/15 không phân biệt được
      "phép kiểm hoạt động" với "phép kiểm hoạt động cho một cách viết".
    """
    sau = q[m.end(): m.end() + _CUA_SO_KY_TU]
    truoc = q[max(0, m.start() - _CUA_SO_KY_TU): m.start()]
    ung_vien: list[tuple[int, str, str]] = []
    for rx, sk, ten in _VAN_BAN_BO_LUAT:
        km = rx.search(sau)
        if km:
            ung_vien.append((km.start(), sk, ten))
        km = rx.search(truoc)
        if km:
            ung_vien.append((len(truoc) - km.end(), sk, ten))
    if not ung_vien:
        return None
    _, sk, ten = min(ung_vien, key=lambda x: x[0])
    return sk, ten


def tien_de_cau_hoi_sai(query: str, engine: Engine) -> str | None:
    """Trả lý do NÊU ĐÍCH DANH nếu câu hỏi dẫn một "Điều N [văn bản]" không có
    thật trong ĐÚNG văn bản đó; trả `None` nếu không phát hiện được văn bản
    nào gần "Điều N" (KHÔNG CHẶN) hoặc mọi cặp (văn bản, Điều) đều tồn tại.
    """
    q = normalize(query)
    cap: list[tuple[str, str, str]] = []
    for m in _RE_DIEU_CAU_HOI.finditer(q):
        so_dieu = m.group(1)
        khop = _van_ban_gan_dieu(q, m)
        if khop is not None:
            cap.append((khop[0], khop[1], so_dieu))
    if not cap:
        return None

    with engine.connect() as conn:
        for so_ky_hieu, ten, so_dieu in cap:
            ton_tai = conn.execute(text(
                "SELECT 1 FROM provisions p JOIN documents d ON d.id = p.document_id"
                " WHERE d.so_ky_hieu = :sk AND p.cap = 'dieu' AND p.so_hieu_cap = :sd LIMIT 1"),
                {"sk": so_ky_hieu, "sd": so_dieu}).first()
            if ton_tai is None:
                return f"{ten} không có Điều {so_dieu}"
    return None


def van_ban_neo_boi_ten(query: str, so_ky_hieu: str) -> bool:
    """Câu hỏi có nhắc tên/viết tắt của `so_ky_hieu` (bảng `_VAN_BAN_BO_LUAT`
    của phép kiểm thứ sáu) không — public wrapper để module khác (assemble.py,
    phép kiểm thứ bảy) tái dùng bộ nhận diện mà không cần biết cấu trúc bảng
    nội bộ. Chỉ khớp theo TỪ/VIẾT TẮT (6 Bộ luật); khớp theo số hiệu dạng
    SỐ/NĂM (áp dụng cho nghị định/thông tư) là việc của caller.
    """
    q = normalize(query)
    return any(sk == so_ky_hieu and rx.search(q) for rx, sk, _ten in _VAN_BAN_BO_LUAT)
