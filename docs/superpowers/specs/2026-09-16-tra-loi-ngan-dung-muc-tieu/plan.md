# Plan: Câu trả lời ngắn, đúng mục tiêu (GĐ0 + GĐ1)

**Source spec**: [spec.md](./spec.md)
**Selected milestone**: GĐ0 (mốc đo hợp lệ) + GĐ1 (sửa nhanh hành vi trả lời)
**Complexity**: Medium

## Summary

Dựng một mốc đo so sánh được trên model đang dùng, rồi sửa ba hành vi làm câu trả lời
đọc như máy: văn dài không trần, đuôi hỏi gắn bừa, và lời chào lặp ở phiên đã có tóm
tắt. Không đụng truy hồi, không đụng hai tầng kiểm chứng, không thêm một lượt gọi mô
hình nào.

## Patterns to Mirror

| Category | Source | Pattern |
|---|---|---|
| Suy biến an toàn | `src/agents/nodes/assemble.py:1002-1011` | Bước hành văn cuối KHÔNG raise; ghi `logger.warning` + `degraded=True` rồi đi tiếp |
| Phép kiểm 0 token | `src/agents/nodes/assemble.py:1013-1046` | Kiểm sau khi có `answer`, chạy trên CẢ đường LLM lẫn đường fallback, kết quả ghi vào `traces` |
| Không raise ở nhánh cuối | `src/agents/nodes/hoi_lai.py:252-266` | Khâu cuối của một lượt không có câu trả lời thì không được biến thành HTTP 500 |
| Cấu hình | `src/config.py:110-126` | `Field(default=..., validation_alias="KLAW_*")` kèm chú thích ghi ĐO ĐƯỢC ngày nào, số bao nhiêu |
| Test hành vi | `tests/test_agents/test_giong_tra_loi.py:1-25` | Docstring mở đầu kể SỐ ĐO và lý do tồn tại của phép kiểm, không chỉ mô tả assert |
| Test hàm thuần | `tests/test_eval/test_run_mo_ho.py:1-12` | Tách hàm thuần ra khỏi graph để test không cần mạng/DB |
| Prompt | `prompts/assemble.v*.md` | Phiên bản mới là tệp mới; đổi bằng `KLAW_ASSEMBLE_PROMPT`, không sửa đè |

## Files to Change

| File | Action | Why |
|---|---|---|
| `eval/run_cau_tra_loi.py` | UPDATE ✅ đã xong | Ghi metadata lượt đo + độ trễ p95 (FR-001…FR-003) |
| `tests/test_eval/test_metadata_luot_do.py` | CREATE ✅ đã xong | Bằng chứng metadata, kể cả chiều "không lộ khoá API" |
| `eval/run_cau_tra_loi.py` | UPDATE ✅ đã xong | Chạy song song có trần + trần giây mỗi câu — lượt tuần tự treo 1h53 không ghi nổi kết quả |
| `tests/test_eval/test_song_song_va_tran_gio.py` | CREATE ✅ đã xong | Một câu treo thành hàng `loi`, không treo cả lượt |
| `src/agents/nodes/assemble.py` | UPDATE | Phép kiểm hình dạng 0 token; lời mở xét cả tóm tắt; đuôi hỏi có điều kiện |
| `src/agents/nodes/hoi_lai.py` | UPDATE | `duoi_hoi_them` nhận đúng chiều vừa giả định, trần 160 ký tự |
| `tests/test_agents/test_hinh_dang_tra_loi.py` | CREATE | Trần 4 gạch, trần 900, không cắt giữa câu, ghi trace |
| `tests/test_agents/test_duoi_hoi_them.py` | UPDATE | Đổi hợp đồng: chỉ hỏi khi lượt vừa suy ra vai |
| `tests/test_agents/test_giong_tra_loi.py` | UPDATE | Thêm ca phiên có tóm tắt nhưng lịch sử rỗng |
| `Makefile` | UPDATE | `check` không ghi tệp; lane test khớp CI |
| `src/config.py` | UPDATE (có điều kiện) | Chỉ khi một ứng viên vượt cổng: đổi prompt mặc định |
| `docs/decisions/2026-09-16-*.md` | CREATE (có điều kiện) | Ghi lại lựa chọn prompt kèm số đo |

## Tasks

### Task 0 — Metadata lượt đo ✅ HOÀN THÀNH

- **Action**: ghi model từng vai, dấu vân tay corpus, `as_of_date`, trạng thái cache,
  p95 và chi phí vào chính tệp kết quả.
- **Mirror**: `_commit()` sẵn có trong cùng tệp; hỏng DB thì trả `{}` chứ không nổ.
- **Validate**: `.venv/bin/pytest -q tests/test_eval/test_metadata_luot_do.py` — 5 passed.

### Task 1 — Mốc đo ba ứng viên

- **Action**: `assemble.v3` / `v4` / `v5`, mỗi lượt đủ 77 câu, cache tắt, cùng model;
  thêm `run_trap` (57 bẫy) và `run_mo_ho` (20 câu).
- **Chặn đã gỡ**: lượt tuần tự đầu tiên chạy 1 giờ 53 phút mà không ghi nổi một tệp
  kết quả (2,3 giây CPU, một luồng kẹt trong `_ssl__SSLSocket_read`). Bộ chạy nay có
  trần giây cho MỖI CÂU và chạy song song có trần, nên một câu treo thành một hàng
  `loi` thay vì giữ cả lượt.
- **Hệ quả đo được**: `latency_p95` của lượt chạy song song KHÔNG so được với một lượt
  tuần tự; `moi_truong.song_song` ghi lại mức song song của chính lượt đó.
- **Không cần lượt đo "trước khi có phép cắt" riêng**: `traces.assemble_hinh_dang` ghi
  cả `do_dai_truoc` (mô hình viết ra) lẫn `do_dai` (phát hành), nên một lượt nói được
  cả hiệu quả prompt lẫn hiệu quả phép cắt.
- **Mirror**: cột `so_loi` đã có — lượt nào `so_loi > 0` thì không dùng để kết luận.
- **Validate**: `python -m eval.run_cau_tra_loi --bang eval/results/deepseek/v{3,4,5}-77.json`

### Task 2 — Phép kiểm hình dạng, 0 token

- **Action**: sau khi hai phép kiểm thẻ và số Điều đã qua, cắt gạch thứ 5 trở đi, đo độ
  dài, ghi `traces` khi vượt trần. Không cắt giữa câu.
- **Mirror**: `assemble.py:1013-1046` — kiểm sau khi có `answer`, kết quả vào `traces`.
- **Validate**: `.venv/bin/pytest -q tests/test_agents/test_hinh_dang_tra_loi.py`

### Task 3 — Đuôi hỏi thêm chỉ khi vừa có giả định mới

- **Action**: `duoi_hoi_them` nhận chiều vừa được suy ra trong lượt (tín hiệu
  `traces["suy_dien_chu_the"]`), hỏi đúng chiều đó, bỏ hẳn nếu chuỗi vượt 160 ký tự;
  nhánh từ chối và phủ một phần không đổi.
- **Mirror**: `hoi_lai.py` — hằng số câu hỏi trong `CHIEU`, 0 token, không gọi LLM.
- **Validate**: `.venv/bin/pytest -q tests/test_agents/test_duoi_hoi_them.py tests/test_agents/test_hoi_lai.py`

### Task 4 — Lượt đầu xét cả tóm tắt

- **Action**: `MO_DAU_NOI_TIEP if state.get("lich_su") or state.get("tom_tat") else …`
- **Mirror**: `assemble.py:988`.
- **Validate**: `.venv/bin/pytest -q tests/test_agents/test_giong_tra_loi.py`

### Task 5 — Tách lệnh kiểm tra

- **Action**: `check` = `lint` + `test` (không `format`); `test` khớp lane CI; thêm
  `test-all` và `check-fix`.
- **Mirror**: `.github/workflows/ci.yml:43` là nguồn sự thật của lane.
- **Validate**: `make check` trên cây bẩn rồi `git status --porcelain` không đổi.

### Task 6 — Chọn prompt mặc định theo cổng (có điều kiện)

- **Action**: nếu một ứng viên đạt cả 5 cổng thì đổi `assemble_prompt` mặc định và ghi
  một decision record kèm số đo; nếu không, giữ nguyên và báo cáo.
- **Mirror**: `src/config.py:110-126` — chú thích ghi ngày đo và con số.
- **Validate**: lượt đo sau khi đổi phải lặp lại được con số đã báo cáo.

### Task 7 — Đo lại và báo cáo

- **Action**: chạy lại ứng viên được chọn + `run_trap` + `run_mo_ho` trên mã đã sửa;
  so với mốc; ghi `tdd.md` trong thư mục đặc tả này.
- **Validate**: `so_loi = 0` ở mọi lượt dùng để kết luận.

## Validation

```bash
.venv/bin/pytest -q tests/test_agents/test_hinh_dang_tra_loi.py \
  tests/test_agents/test_duoi_hoi_them.py tests/test_agents/test_hoi_lai.py \
  tests/test_agents/test_giong_tra_loi.py tests/test_agents/test_assemble.py \
  tests/test_eval/test_metadata_luot_do.py
make check
KLAW_CACHE_TTL_NGAY=0 .venv/bin/python -m eval.run_cau_tra_loi --prompt <chọn> --json eval/results/deepseek/<chọn>-sau.json
.venv/bin/python -m eval.run_cau_tra_loi --bang eval/results/deepseek/*.json
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Cắt gạch làm mất một điều kiện đảo kết luận | Trung bình | Chỉ cắt khi >4 gạch; ghi trace mọi lần cắt để đọc lại trong lượt đo; cổng SC-003 chặn tụt trúng dẫn |
| Cả ba ứng viên đều trượt cổng | Trung bình | Giữ prompt hiện hành, báo cáo, không đổi mặc định để lấy tiến độ |
| Bỏ đuôi hỏi làm `run_mo_ho` tụt | ~~Trung bình~~ **Thấp** | Đọc `eval/run_mo_ho.dung`: nó chấm DÒNG GIẢ ĐỊNH trong `answer` ("tôi hiểu bạn là"), KHÔNG chấm đuôi hỏi. Thu hẹp đuôi vẫn đúng vì quyết định 2026-09-09 đòi hỏi lại dữ kiện vừa giả định, nhưng bộ đo đó không phải lưới bắt |
| Lượt đo hỏng vì DB hoặc 429 | Trung bình | `so_loi > 0` thì lượt không hợp lệ; chạy lại, không tính trên mẫu nhỏ hơn |
| Đổi `make test` làm CI lệch | Thấp | Lấy đúng chuỗi marker từ `ci.yml`, không tự chế |
| Phát sinh chi phí ngoài dự tính | Thấp | Mỗi lượt 77 câu ≈ $0.8 đã đo; chỉ chạy lại ứng viên được chọn ở Task 7 |

## Acceptance

- [ ] Mọi task hoàn thành hoặc nêu rõ vì sao dừng
- [ ] Lane test tập trung xanh, `make check` không đổi tệp nào
- [ ] Mốc đo và lượt đo sau sửa đều đủ 77/77, `so_loi = 0`
- [ ] Không phép kiểm 0 token nào bị gỡ; không thêm lượt gọi mô hình nào
- [ ] Báo cáo cuối ghi số đo trước/sau, giới hạn còn lại và cách lùi
