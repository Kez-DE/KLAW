"""Cache câu trả lời `/tra-cuu` — bảng Postgres (`answer_cache`), KHÔNG Redis.

Vì sao Postgres và không phải một tầng in-process: dự án sẽ scale worker khi
deploy thật (`Dockerfile` hiện chạy MỘT worker uvicorn, đó là trạng thái tạm),
và một cache in-process là N cache khác nhau trên N worker — N lần chi phí, và
N câu trả lời có thể lệch nhau cho cùng một câu hỏi. Postgres đã là dependency
bắt buộc của mọi request nên cache ở đây thêm 0 thành phần vận hành.

KHOÁ có bốn thành phần, mỗi thành phần khoá một chế độ hỏng riêng:

  * **câu hỏi đã chuẩn hoá** — bằng CHÍNH `verify_tier1.normalize` mà phép kiểm
    tầng 1 dùng, KHÔNG phải một hàm chuẩn hoá thứ hai. Hai hàm chuẩn hoá là
    cách chắc chắn để cache bắn nhầm: chúng luôn lệch nhau ở một ca biên nào
    đó, và ca biên đó trả về câu trả lời của một câu hỏi khác.
  * **config_name** — nhãn ablation (`full`, `bm25_only`, `dense_only`…). Hai
    cấu hình truy hồi khác nhau cho hai câu trả lời khác nhau.
  * **as_of_date** — ĐÃ GIẢI QUYẾT thành một ngày cụ thể (`config.as_of_hieu_luc`).
    Hiệu lực phụ thuộc nó; dùng chung một câu trả lời cho hai mốc thời gian là
    trả về hiệu lực SAI, đúng chế độ hỏng khoá luận tồn tại để chống.
  * **corpus_checksum** — seed lại corpus thì cache TỰ hết hiệu lực, không phụ
    thuộc việc có ai nhớ xoá tay hay không.

Chỉ `answer` và `partial_coverage` vào cache. `abstain` KHÔNG: một lần thiếu
căn cứ do lỗi TẠM (OpenRouter 429 — đã xảy ra thật, DB chậm) sẽ bị đóng băng 7
ngày thành "không tìm thấy căn cứ". `abstain` là hành vi ĐÚNG và ĐƯỢC TÍNH
ĐIỂM, không phải lỗi — nhưng cũng không phải thứ được phép hoá đá.
"""

import hashlib
import json
import logging
from datetime import date

from sqlalchemy import text

from src.agents.nodes.verify_tier1 import normalize
from src.config import get_settings
from src.services.db import get_engine

logger = logging.getLogger(__name__)

# `out_of_scope` cũng bị loại: nó là phán đoán của node `route` trên MỘT lần
# đọc câu hỏi, và một lần route sai (mô hình router là model rẻ nhất trong ba
# vai) sẽ hoá đá thành "ngoài phạm vi" cho câu hỏi đó.
KET_QUA_DUOC_CACHE = frozenset({"answer", "partial_coverage"})

_SQL_CHECKSUM = text(
    "SELECT (SELECT count(*) FROM provisions) AS n,"
    " (SELECT max(crawled_at) FROM documents) AS moc"
)
_SQL_DOC = text(
    "SELECT tra_loi FROM answer_cache"
    " WHERE khoa = :khoa AND tao_luc >= now() - make_interval(days => :ttl)"
)
_SQL_DON = text("DELETE FROM answer_cache WHERE tao_luc < now() - make_interval(days => :ttl)")
_SQL_GHI = text(
    "INSERT INTO answer_cache (khoa, cau_hoi_chuan, config_name, as_of_date,"
    " corpus_checksum, tra_loi, tao_luc)"
    " VALUES (:khoa, :cau_hoi_chuan, :config_name, :as_of_date, :corpus_checksum,"
    " CAST(:tra_loi AS JSONB), now())"
    # Ghi đè khi khoá đã tồn tại: hai request song song cùng câu hỏi đều tính
    # xong rồi đều ghi. Cả hai câu trả lời hợp lệ như nhau (cùng khoá = cùng
    # câu hỏi, cùng config, cùng mốc hiệu lực, cùng corpus) nên lấy bản mới
    # nhất và làm mới `tao_luc`. `DO NOTHING` sẽ giữ bản cũ và một
    # IntegrityError trần sẽ giết một request đã tính ĐÚNG.
    " ON CONFLICT (khoa) DO UPDATE SET tra_loi = EXCLUDED.tra_loi, tao_luc = now()"
)


def corpus_checksum() -> str:
    """Dấu vết của corpus đang nạp: `<số provision>:<lần crawl gần nhất>`.

    Suy từ hai đại lượng đã có thay vì thêm một bảng phiên bản: cả hai đổi khi
    và chỉ khi corpus được nạp lại (`scripts/ingest.py` chèn provisions và cập
    nhật `documents.crawled_at`). Đo trên DB hiện tại: 19.135 provision,
    `max(crawled_at)` = 2026-08-30T14:59:20Z.

    KHÔNG cache trong tiến trình: một worker giữ giá trị cũ sẽ tiếp tục phục vụ
    cache của corpus đã bị thay — đúng thứ cột này tồn tại để chặn. `count(*)`
    trên 19.135 dòng là vài ms, không đáng kể cạnh p50 10s của đường không-cache.
    """
    with get_engine().connect() as c:
        n, moc = c.execute(_SQL_CHECKSUM).one()
    return f"{n}:{moc.isoformat() if moc else 'chua-crawl'}"


def khoa_cache(cau_hoi: str, config_name: str, as_of: date, checksum: str) -> str:
    """sha256 của bốn thành phần, phân tách bằng `\\x1f` (unit separator).

    Hash chứ không phải khoá tổ hợp bốn cột: `query` cho phép tới 2.000 ký tự,
    và 2.000 ký tự tiếng Việt là ~6.000 byte UTF-8 — vượt trần ~2.704 byte của
    một dòng index btree, tức INSERT sẽ NỔ đúng trên câu hỏi dài.

    Phân tách bằng `\\x1f` chứ không bằng `|` hay `:`: ký tự đó không xuất hiện
    trong câu hỏi người dùng gõ, nên không có cách nào chế một câu hỏi trùng
    khoá với một (câu hỏi, config) khác.
    """
    thanh_phan = "\x1f".join([normalize(cau_hoi), config_name, as_of.isoformat(), checksum])
    return hashlib.sha256(thanh_phan.encode("utf-8")).hexdigest()


def _doc_dong(khoa: str, ttl: int) -> dict | None:
    with get_engine().connect() as c:
        dong = c.execute(_SQL_DOC, {"khoa": khoa, "ttl": ttl}).scalar_one_or_none()
    return dong


def _ghi_dong(params: dict, ttl: int) -> None:
    with get_engine().begin() as c:
        c.execute(_SQL_DON, {"ttl": ttl})
        c.execute(_SQL_GHI, params)


def tra_cache(cau_hoi: str, config_name: str, as_of: date) -> tuple[str | None, str | None, dict | None]:
    """Toàn bộ đường ĐỌC cache: `(khoa, checksum, payload)`.

    Cache tắt (`KLAW_CACHE_TTL_NGAY=0`) → `(None, None, None)` và **KHÔNG một
    truy vấn DB nào**. Đây là lý do hàm này gộp cả `corpus_checksum()` vào trong
    thay vì để caller gọi riêng: bản trước tính checksum TRƯỚC khi kiểm TTL, nên
    mỗi request vẫn trả một `count(*)` trên 19.135 dòng dù cache đã tắt. Hai hệ
    quả thật, đo được: (a) `eval/run.py` chạy không-cache — đúng cấu hình phải
    dùng để đo — vẫn phải trả round-trip đó mỗi lượt; (b) toàn bộ test không-DB
    của `/tra-cuu` bỗng cần Postgres, tức CI (`-m "not integration"`, không có
    Postgres) đỏ. MỘT chỗ quyết định cache bật/tắt, và nó là chỗ này.

    `khoa` khác None là tín hiệu cho caller biết đường GHI có nghĩa hay không —
    không cần hỏi lại settings ở đó.

    CÓ THỂ RAISE. Lỗi ĐỌC cache không được nuốt: nếu bảng cache không đọc được
    thì Postgres đang không lành, và Postgres là dependency của cả pipeline
    (truy hồi, verify, traces) — chạy tiếp là tiêu 5 lượt LLM cho một request
    gần như chắc chắn sẽ hỏng ở bước sau. Caller (`routes.tra_cuu`) phân loại
    ngoại lệ này thành 503 bằng ĐÚNG khối except đã có, không thêm nhánh mới.
    """
    ttl = get_settings().cache_ttl_ngay
    if ttl <= 0:
        return None, None, None
    checksum = corpus_checksum()
    khoa = khoa_cache(cau_hoi, config_name, as_of, checksum)
    return khoa, checksum, _doc_dong(khoa, ttl)


def ghi_cache(
    khoa: str, cau_hoi: str, config_name: str, as_of: date, checksum: str, tra_loi: dict
) -> None:
    """Ghi (hoặc làm mới) một dòng cache. Dọn dòng quá TTL trong cùng transaction.

    `cau_hoi` được `normalize` TẠI ĐÂY trước khi lưu, để cột `cau_hoi_chuan`
    thật sự chứa dạng đã chuẩn hoá — cùng dạng đã đi vào `khoa`. Lưu bản thô
    dưới một cột tên `_chuan` là một lời nói dối nhỏ mà người đọc bảng sau này
    phải tự phát hiện.

    KHÔNG raise ra ngoài: khác lượt ĐỌC, tại đây câu trả lời đã được tính ĐÚNG
    và đã sẵn sàng trả cho người dùng — từ chối nó vì một INSERT trục trặc là
    làm hỏng chính thứ vừa tốn 5 lượt LLM. Lỗi được log ĐẦY ĐỦ (không im lặng);
    hệ quả duy nhất là lượt sau tính lại, và tổng chi tiêu vẫn bị trần chi phí
    ngày chặn. Cùng lý lẽ `_ghi_traces` là best-effort.
    """
    ttl = get_settings().cache_ttl_ngay
    if ttl <= 0:
        return
    try:
        _ghi_dong(
            {
                "khoa": khoa, "cau_hoi_chuan": normalize(cau_hoi), "config_name": config_name,
                "as_of_date": as_of, "corpus_checksum": checksum,
                "tra_loi": json.dumps(tra_loi, ensure_ascii=False),
            },
            ttl,
        )
    except Exception:
        logger.exception("ghi_cache thất bại (khoa=%s) — KHÔNG chặn response đã tính đúng", khoa)
