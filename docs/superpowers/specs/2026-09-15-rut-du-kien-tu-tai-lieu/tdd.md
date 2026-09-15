# Bằng chứng TDD — Rút dữ kiện có neo nguồn từ tài liệu

**Spec**: [spec.md](./spec.md) · **Kế hoạch**: nêu trong hội thoại `/ecc:plan`, không ghi thành tệp
**Ngày**: 2026-09-15 · **Nhánh**: `feat/tro-ly-phap-luat`
**Commit**: `dd8d9fc` → `f52fd3a`

## Hành trình người dùng (từ spec)

1. **P1** — Tải tài liệu lên, nhận danh sách dữ kiện, mỗi dữ kiện kèm đoạn trích nguyên văn và vị trí.
2. **P2** — Sửa, bỏ, rồi đẩy tập dữ kiện sang soạn thảo; biểu mẫu điền sẵn phần có, để trống phần thiếu.
3. **P3** — Tài liệu không đọc được thì nói thẳng nguyên nhân, không đoán nội dung.

## Từng pha

| Pha | Việc | Lệnh kiểm | RED | GREEN |
|---|---|---|---|---|
| 1 | Đọc PDF/DOCX thành đơn vị có vị trí | `pytest tests/test_services/test_doc_tai_lieu.py` | `ModuleNotFoundError: src.services.doc_tai_lieu`, 14 test không thu thập được | 14 passed |
| 2 | Neo dữ kiện bằng tra chuỗi | `pytest tests/test_services/test_neo_du_kien.py` | `ModuleNotFoundError: src.services.neo_du_kien`, 15 test không thu thập được | 15 passed |
| 3 | Rút dữ kiện bằng LLM + loại phần không neo được | `pytest tests/test_agents/test_rut_du_kien.py` | `ModuleNotFoundError: src.agents.nodes.rut_du_kien`, 12 test không thu thập được | 12 passed |
| 4 | Migration 026 + vòng đời việc đọc | `pytest tests/test_services/test_tai_lieu.py` và `tests/test_api/test_guard_khoi_dong.py` | `ModuleNotFoundError: src.services.tai_lieu` (14 test); guard sẵn có của repo báo `Extra items in the left set: '026'` | 14 passed; guard 10 passed |
| 5+6 | Endpoint, hai đường xử lý, nối sang soạn thảo | `pytest tests/test_api/test_tai_lieu_loi.py` | `ImportError` rồi 14 test không thu thập được | 14 passed |
| 7 | Client và quy tắc trình bày (frontend) | `node scripts/kiem-tai-lieu.ts` | Chưa có module, script không chạy | `kiem-tai-lieu: OK`, typecheck sạch, eslint sạch trên tệp mới |
| 8 | Runner đánh giá SC-001/SC-002 | `pytest tests/test_eval/test_run_tai_lieu.py` | `ModuleNotFoundError: eval.run_tai_lieu`, 14 test không thu thập được | 14 passed |

## Những gì các test bảo đảm

| # | Bảo đảm | Tệp test | Loại | Kết quả |
|---|---|---|---|---|
| 1 | Đoạn, ô bảng là các đơn vị RIÊNG; không đơn vị nào bị gộp | `test_doc_tai_lieu.py::test_DOCX_moi_o_bang_la_mot_don_vi_RIENG` | unit | PASS |
| 2 | Dấu tiếng Việt đi qua tầng đọc nguyên vẹn | `test_doc_tai_lieu.py::test_DOCX_giu_dau` | unit | PASS |
| 3 | Bốn nguyên nhân không đọc được là bốn mã phân biệt | `test_doc_tai_lieu.py::test_BON_nguyen_nhan_la_BON_ma_rieng` | unit | PASS |
| 4 | Hệ thống dùng CHUNG một hàm chuẩn hoá với tầng 1, không có bản thứ hai | `test_neo_du_kien.py::test_DUNG_LAI_normalize_cua_verify_tier1` | unit | PASS |
| 5 | Bỏ dấu hoặc đổi hoa thường thì đoạn trích TRƯỢT | `test_neo_du_kien.py::test_BO_DAU_thi_TRUOT`, `::test_DOI_HOA_THUONG_thi_TRUOT` | unit | PASS |
| 6 | Đoạn trích ghép từ hai đơn vị bị TRƯỢT | `test_neo_du_kien.py::test_GHEP_HAI_DON_VI_thi_TRUOT` | unit | PASS |
| 7 | Dữ kiện có trích không khớp không bao giờ ra khỏi node | `test_rut_du_kien.py::test_LOAI_du_kien_co_trich_KHONG_KHOP`, `::test_MOI_du_kien_tra_ra_deu_co_neo_ok` | unit | PASS |
| 8 | Lỗi LLM không sinh ra dữ kiện bịa | `test_rut_du_kien.py::test_loi_LLM_khong_sinh_du_kien_bia` | unit | PASS |
| 9 | Sửa một dữ kiện giữ trích gốc và đổi nhãn nguồn | `test_tai_lieu.py::test_sua_doi_nguon_va_GIU_trich_goc`, `::test_sua_KHONG_giu_trich_cho_gia_tri_moi` | unit | PASS |
| 10 | Đưa sang soạn thảo chỉ mang trường CÓ dữ kiện | `test_tai_lieu.py::test_thanh_facts_chi_mang_truong_CO_du_kien` | unit | PASS |
| 11 | Sáu thông điệp lỗi phân biệt được, nêu đúng trần bị vượt | `test_tai_lieu_loi.py` (14 test) | unit | PASS |
| 12 | Lỗi hạ tầng không bị nuốt thành 422 | `test_tai_lieu_loi.py::test_loi_LA_thi_KHONG_nuot` | unit | PASS |
| 13 | Giao diện không hiện trích của giá trị cũ như bằng chứng cho giá trị mới | `frontend/scripts/kiem-tai-lieu.ts` mục 3 | unit | PASS |
| 14 | Trường thiếu tính là SAI, không bị loại khỏi mẫu số | `test_run_tai_lieu.py::test_diem_truong_TRUONG_THIEU_tinh_la_SAI_chu_khong_bo_qua` | unit | PASS |
| 15 | Migration 026 chặn dữ kiện `tai_lieu` thiếu neo, và dữ kiện đã sửa thiếu trích gốc | `test_migration_026.py` | integration | **CHƯA CHẠY** |
| 16 | Xoá cuộc hội thoại xoá theo dữ kiện | `test_migration_026.py::test_XOA_HOI_THOAI_XOA_THEO_du_kien` | integration | **CHƯA CHẠY** |

## Toàn bộ suite

```
pytest -m "not integration" -q
43 failed, 1572 passed, 408 deselected
```

Baseline khi cất toàn bộ việc này đi: `43 failed, 1530 passed`. **Cùng 43 test đỏ
trước và sau**, nên không có hồi quy nào; phần thêm là +42 test xanh.

## Vòng hai — 2026-09-15, sau khi Docker lên

| Việc | Kết quả |
|---|---|
| Trần chi phí mỗi tài liệu (FR-036) | 7 passed; ước trước khi gọi + đối chiếu chi phí thật sau khi gọi |
| Hạn mức tài liệu theo gói (FR-004) | 429 nêu đúng con số và mốc mở lại; tệp hỏng vẫn tính lượt |
| Migration 026 trên Postgres thật | 9 passed — hai chiều đầy đủ, gồm cả đường cascade |
| Endpoint chạm DB | 13 passed — quyền sở hữu, sửa giữ trích gốc, bàn giao, hạn mức, dấu vân |
| PDF tiếng Việt thật | 6 passed — dấu nguyên vẹn, NFC, bỏ dấu vẫn trượt |
| Tập mẫu ứng viên | 27 passed — 6 tài liệu, 4 ca bẫy, chưa ai duyệt |
| FR-020 ghi vào hội thoại | 3 passed — dữ kiện người dùng tự nhập không bị đè |

### Tự review, bốn lỗi đã sửa

1. `tai_len` phân tích tài liệu **hai lần**. Giờ đọc một lần, `_chay` nhận
   `TaiLieuDaDoc` thay vì bytes — nên không nhánh nào trong `_chay` còn cầm tệp.
2. Dấu vân tính bằng `.decode("utf-8", errors="replace")` trên bytes nhị phân:
   tốn một bản sao và có thể làm hai tệp khác nhau trùng dấu. Giờ hash thẳng bytes.
3. **FR-004 chưa có nơi cưỡng chế** — không có hạn mức số tài liệu. Đã thêm
   `tai_lieu.theo_goi` vào `han_muc.yaml` và cổng chạy trước khi phân tích tệp.
4. `TRAN_THU_LAI` / `con_thu_lai` là **code chết**, và FR-037 là một lời hứa
   không thể giữ: không lưu tệp gốc thì không thử lại được — thử lại chính là
   tải lên lại, và hạn mức ngày đã đếm việc đó. Đã gỡ cả hằng số lẫn hàm, và có
   một test khoá để không ai thêm lại.

### Sai lệch spec phát hiện khi triển khai

`FR-020` từng viết "biểu mẫu soạn thảo được điền sẵn" mà không nói rõ **bề mặt
nào**. `KhongGianSoanThao.tsx` có mô hình `Draft` riêng và không chạy bằng bộ từ
vựng `rules.yaml`; thứ chạy bằng `facts` là đường soạn thảo trong hội thoại.
FR-019/FR-020 đã viết lại, thêm FR-020a cho ca người dùng đã tự nhập.

## Toàn bộ suite, vòng hai

```
pytest -m "not integration" -q     →  43 failed, 1616 passed
pytest tests/test_api/test_tai_lieu_api.py tests/test_services/test_migration_026.py
                                   →  22 passed  (Postgres thật)
npm run typecheck / lint / kiem-tai-lieu  →  sạch
```

Baseline vẫn `43 failed, 1530 passed`. Cùng 43 test đỏ, +86 test xanh.

## Khoảng trống đã biết

1. **43 test đỏ có sẵn** trong `tests/test_api/`, tất cả `401 Unauthorized`. Có
   từ trước nhánh việc này (kiểm bằng `git stash` rồi chạy lại). Chưa chẩn đoán.
2. **`test_migration_026.py` chưa từng chạy** — cần Postgres, Docker không chạy
   trong môi trường này. Hai ràng buộc CHECK và đường cascade vì thế mới chỉ
   được chứng minh trên giấy, chưa có chứng minh hai chiều theo
   `docs/patterns/encoding-invariants.md` §4. **Phải chạy trước khi tin chúng.**
3. **Endpoint chưa có test chạm DB.** `test_tai_lieu_loi.py` chỉ phủ phần ánh xạ
   lỗi thuần. Quyền sở hữu theo `user_sub`, hạn mức, và đường chạy nền chưa được
   kiểm bằng request thật.
4. **Chưa có giao diện.** Client và quy tắc trình bày đã xong và có kiểm; ô tải
   lên cùng bảng dữ kiện trong `KhongGianSoanThao.tsx` (68,5 KB) chưa làm.
5. **Trần chi phí mỗi tài liệu chưa nối vào cổng** — cột `chi_phi_usd` đã ghi,
   nhưng FR-036 chưa có điểm cưỡng chế trong `bao_ve.py`.
6. **Tập mẫu đánh giá trống.** Định dạng và runner đã có; 20–30 tài liệu cùng
   nhãn là việc tay của chủ dự án (Q5 đã chốt).
7. **PDF chữ Việt chưa đo.** Fixture PDF trong test chỉ dùng ASCII vì Type1
   WinAnsi không mã được dấu; nhánh dấu được khoá bằng DOCX. Rủi ro R3 của kế
   hoạch (pypdf làm vỡ dấu trên PDF font lạ) vì thế vẫn chưa được đo.
