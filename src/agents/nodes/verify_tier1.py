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
from src.services.effectivity import Effectivity, danh_gia_theo_id

# Chuẩn hoá CHỈ ĐỂ SO KHỚP. Cùng bộ ba mà `prov_parser._khoa` đã phải trả giá ở
# Plan 1: zero-width vô hình nhưng làm hai chuỗi "khác nhau"; Ð U+00D0 (LATIN
# CAPITAL LETTER ETH) hiện lên y hệt Đ U+0110 và có thật 2 lần trong 101/2015/QH13
# ("Ðoàn thanh niên", Điều 414 và 420).
_MAP_KHOA = str.maketrans({"​": "", "﻿": "", "Ð": "Đ", "ð": "đ"})


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
    quote_khong_khop = "quote_khong_khop"                 # phép kiểm 3


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


def _tim_quote(quote: str, cay: list[dict]) -> int | None:
    """`provisions.id` của dòng chứa `quote`, hoặc None.

    So với TỪNG DÒNG một, KHÔNG nối cả cây thành một chuỗi rồi so: nối lại sẽ
    tạo ra những vết ghép không tồn tại trong văn bản gốc, và một "quote" vắt
    qua ranh giới tiêu đề Điều sang thân Khoản 1 sẽ khớp dù nó không nguyên văn
    ở bất kỳ đâu. Một trích dẫn pháp luật nguyên văn luôn nằm gọn trong một đơn
    vị của corpus.
    """
    q = normalize(quote)
    if not q:
        return None
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
        khop_tai = _tim_quote(c.quote, _cay_con(c.provision_id, db_provisions))
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
    """
    da_biet: dict[str, Effectivity] = {}

    def tra(provision_id: int) -> Effectivity:
        doc_id = db_provisions[provision_id]["document_id"]
        if doc_id not in da_biet:
            da_biet[doc_id] = danh_gia_theo_id(engine, doc_id, as_of)
        return da_biet[doc_id]

    return tra
