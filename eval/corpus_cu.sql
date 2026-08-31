-- Ô "corpus CŨ" của bảng bốn ô trong `.superpowers/sdd/eval-baseline-moi.md`.
--
-- 21 văn bản có trong `scripts/fetch_moj.py::DOC_IDS` tại commit `c5c2c17` —
-- commit ngay TRƯỚC đợt nạp đầu tiên (`2be37c3`). Lấy lại danh sách:
--   git show c5c2c17:scripts/fetch_moj.py | grep -oE '\("deep", "[^"]+"\)'
--
-- Vì sao là view chứ không dựng lại CSDL, và vì sao thế là CHÍNH XÁC chứ không
-- xấp xỉ — hai tính chất đã kiểm trên DB này:
--   1. `chunks.embedding` KHÔNG có index ANN (chỉ pkey/provision/model/tsv-GIN),
--      nên `ORDER BY embedding <=> …` là k-NN vét cạn: thu hẹp tập ứng viên cho
--      kết quả GIỐNG HỆT một corpus nhỏ hơn thật. Nếu sau này thêm HNSW thì cách
--      này HẾT ĐÚNG (lọc sau index làm hụt recall của chính index) và phải dựng
--      lại CSDL.
--   2. `ts_rank` không có IDF, nên điểm từ vựng của một chunk không phụ thuộc
--      corpus xung quanh.
--
-- Kiểm sau khi chạy: 21 văn bản, 3.283 chunk mỗi model (= 6.566/2 đã ghi nhận
-- trước khi mở rộng).
--
-- Dùng: trỏ search_path Ở TẦNG DSN, KHÔNG `ALTER DATABASE` — như vậy phạm vi chỉ
-- trong tiến trình eval, không đụng tiến trình khác (server FE) và một lần ngắt
-- giữa chừng không để lại CSDL ở trạng thái lạ:
--
--   docker exec -i klaw-p1-db-1 psql -U klaw -d klaw -f - < eval/corpus_cu.sql
--   DATABASE_URL='postgresql://klaw:klaw@localhost:5432/klaw?options=-csearch_path%3Dcorpus_cu,public' \
--     EVAL_DATASET_DIR=<thư mục golden> EVAL_RESULT_DIR=<thư mục kết quả> \
--     python -m eval.run --config dense_only
--
-- `provisions` cố ý KHÔNG bị hạn chế: nó rơi xuống `public` qua search_path, nên
-- `phan_giai_gold` vẫn phân giải được mọi `duong_dan` kể cả khi chunk của nó bị ẩn
-- — đúng thứ cần, vì một gold không phân giải được phải NỔ chứ không phải lặng lẽ
-- thành Recall = 0.

DROP SCHEMA IF EXISTS corpus_cu CASCADE;
CREATE SCHEMA corpus_cu;

CREATE VIEW corpus_cu.chunks AS
  SELECT c.*
  FROM public.chunks c
  JOIN public.provisions p ON p.id = c.provision_id
  JOIN public.documents  d ON d.id = p.document_id
  WHERE d.so_ky_hieu IN (
    -- 6 Bộ luật
    '91/2015/QH13', '100/2015/QH13', '92/2015/QH13', '101/2015/QH13',
    '45/2019/QH14', '95/2015/QH13',
    -- cụm Lao động
    '145/2020/NĐ-CP', '10/2020/TT-BLĐTBXH', '293/2025/NĐ-CP', '337/2025/NĐ-CP',
    '12/2022/NĐ-CP', '09/2020/TT-BLĐTBXH', '18/2021/TT-BLĐTBXH',
    '135/2020/NĐ-CP', '29/2019/NĐ-CP', '84/2015/QH13',
    -- tập bẫy hiệu lực
    '74/2024/NĐ-CP', '90/2019/NĐ-CP', '157/2018/NĐ-CP', '141/2017/NĐ-CP',
    '122/2015/NĐ-CP'
  );

-- Cổng: sai một số hiệu là cả bảng bốn ô sai mà không có dấu hiệu nào.
DO $$
DECLARE n_doc int; n_chunk int;
BEGIN
  SELECT count(DISTINCT p.document_id) INTO n_doc
    FROM corpus_cu.chunks c JOIN public.provisions p ON p.id = c.provision_id;
  SELECT count(*) INTO n_chunk
    FROM corpus_cu.chunks WHERE embedding_model = 'baai/bge-m3';
  IF n_doc <> 21 THEN
    RAISE EXCEPTION 'corpus_cu: % văn bản, phải là 21 — số hiệu sai hoặc corpus đổi', n_doc;
  END IF;
  IF n_chunk <> 3283 THEN
    RAISE EXCEPTION 'corpus_cu: % chunk bge-m3, phải là 3283 (= 6566/2) — corpus cũ đã đổi', n_chunk;
  END IF;
  RAISE NOTICE 'corpus_cu OK: % văn bản, % chunk bge-m3', n_doc, n_chunk;
END $$;
