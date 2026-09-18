/**
 * R5 (owner, Phase 14): "ko đề cập 'kho' trong kho của tôi nữa mà sẽ là pháp
 * luật việt nam có, … luật này, điều này trong pháp luật việt nam, bộ luật
 * này". Gọi corpus là kho RIÊNG của KLAW làm nó nghe như một danh mục tư nhân,
 * trong khi thứ nó đang trích LÀ văn bản pháp luật Việt Nam. Nửa Python của
 * phép kiểm này đã có ở `tests/test_agents/test_soan_thao_tu_do.py`; đây là
 * nửa FE, cùng hai vế: bỏ chữ, và bỏ đúng cách.
 *
 * PHẠM VI CỐ Ý HẸP — `src/components/klaw/`, nơi KLAW nói về câu trả lời của
 * CHÍNH nó. Các trang công bố (`routes/mien-tru`, `routes/du-lieu`,
 * `components/legal/`) vẫn gọi corpus là "kho" và đó là chủ đích: việc của
 * chúng là thú nhận corpus chỉ là một tập hợp có hạn chứ không phải toàn bộ
 * pháp luật Việt Nam — đúng lời thú nhận mà ranh giới (a) của R5 bắt phải sống.
 * Nới phạm vi quét ra đó sẽ đòi xoá chính lời thú nhận ấy.
 *
 * Bắt được: một chuỗi mới cho người đọc trong `components/klaw/` gọi lại corpus
 * là "kho", và việc bỏ chữ "kho" ở ba bề mặt đã sửa mà làm câu thành vô danh
 * hoặc thành lời hứa phủ hết pháp luật Việt Nam.
 *
 * Chạy: `npm run kiem-goi-ten-luat`.
 */
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const THU_MUC = "src/components/klaw";

// `\b` của JS coi "khoản" là "kho" + ranh giới sai vì "ả" nằm ngoài [A-Za-z];
// lookaround theo \p{L}\p{N} mới bắt đúng chữ "kho" đứng một mình, không bắt
// "khoản", "khoá", "khoảng", "không".
const RE_KHO = /(?<![\p{L}\p{N}])kho(?![\p{L}\p{N}])/giu;

/** Ranh giới (b) của R5: chú thích và tên định danh giữ nguyên tên của chúng. */
function boChuThich(ma: string): string {
  return ma.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

function moiTep(thuMuc: string): string[] {
  return readdirSync(thuMuc).flatMap((ten) => {
    const p = join(thuMuc, ten);
    if (statSync(p).isDirectory()) return moiTep(p);
    return /\.tsx?$/.test(p) ? [p] : [];
  });
}

const tep = moiTep(THU_MUC);
assert.ok(tep.length > 10, `${THU_MUC}: không quét được tệp nào — sai đường dẫn?`);

const vuong: string[] = [];
for (const t of tep) {
  boChuThich(readFileSync(t, "utf8"))
    .split("\n")
    .forEach((dong, i) => {
      RE_KHO.lastIndex = 0;
      if (RE_KHO.test(dong)) vuong.push(`${t}:${i + 1}: ${dong.trim()}`);
    });
}
assert.deepEqual(vuong, [], `lời cho người đọc còn gọi corpus là kho:\n${vuong.join("\n")}`);

// Nửa sau: bỏ chữ "kho" chỉ đúng nếu chỗ nó đứng nay gọi TÊN thứ đang đối
// chiếu — và nếu lời thú nhận độ phủ vẫn còn nguyên ở đó.
const doc = (t: string) => readFileSync(join(THU_MUC, t), "utf8");
{
  const s = doc("SoatBanThao.tsx");
  assert.match(s, /Soát theo văn bản pháp luật Việt Nam/);
  assert.match(s, /dựng từ chính nguyên\s+văn văn bản pháp luật/);
  assert.match(s, /KLAW chưa dựng rule hay checklist nào cho loại văn bản này/);
}
{
  const s = doc("PhamViKho.tsx");
  assert.match(s, /Văn bản pháp luật đang có/);
  assert.match(s, /mới có thông tin văn bản, chưa có toàn văn/);
}
{
  const s = doc("BaoLoi.tsx");
  // 404 nói KLAW chưa có nguyên văn, KHÔNG nói pháp luật Việt Nam không có —
  // đó là ranh giới (a): lời mới không được hứa nhiều hơn lời cũ.
  assert.match(s, /KLAW chưa có nguyên văn của văn bản hoặc điều khoản này\./);
  assert.doesNotMatch(boChuThich(s), /pháp luật Việt Nam (không|chưa)/);
}

console.info(`kiem-goi-ten-luat: ${tep.length} tệp sạch, 6/6 đạt`);
