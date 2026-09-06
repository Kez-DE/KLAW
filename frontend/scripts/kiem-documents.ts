/**
 * Kiểm chạy được cho `chuanHoaDocuments`: khoá `documents` vắng (payload cache
 * cũ) → `[]`; phần tử sai hình dạng bị loại; phần tử đúng giữ nguyên.
 * Chạy: `npm run kiem-documents`.
 */
import assert from "node:assert/strict";
import { chuanHoaDocuments, laVanBanTraLoi } from "../src/lib/klaw.ts";

const dung = {
  doc_id: "139264",
  ten: "Bộ Luật lao động",
  so_ky_hieu: "45/2019/QH14",
  loai_van_ban: "Bộ luật",
  links: { vbpl: "https://vbpl.vn/x", chinhphu: null, tvpl: null },
};

// 1. Thiếu khoá → mảng rỗng, các khoá khác giữ nguyên.
{
  const ra = chuanHoaDocuments({ result_type: "answer", citations: [] }) as Record<string, unknown>;
  assert.deepEqual(ra["documents"], []);
  assert.equal(ra["result_type"], "answer");
}

// 2. Phần tử thiếu `links` hoặc `doc_id` sai kiểu bị loại; phần tử đúng giữ.
{
  const ra = chuanHoaDocuments({ documents: [dung, { doc_id: "1" }, { ...dung, doc_id: 5 }] }) as {
    documents: unknown[];
  };
  assert.deepEqual(ra.documents, [dung]);
}

// 3. Không phải bản ghi → trả nguyên `x` để guard phía sau tự từ chối.
{
  assert.equal(chuanHoaDocuments(null), null);
  assert.equal(chuanHoaDocuments("x"), "x");
}

// 4. Guard đúng/sai.
{
  assert.equal(laVanBanTraLoi(dung), true);
  assert.equal(laVanBanTraLoi({ ...dung, links: null }), false);
}

console.info("kiem-documents: 4/4 đạt");
