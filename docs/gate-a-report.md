# Cổng A — Data Integrity Audit

Phép kiểm ĐỘC LẬP VỚI PARSER: độ phủ token so với văn bản gốc đã strip tag.
Sinh bởi `python -m scripts.gate_a_audit` (2026-08-27).

| Bộ luật | so_ky_hieu | provisions | token gốc | token thiếu | độ phủ | Điều rỗng |
|---|---|---|---|---|---|---|
| 95942 | 91/2015/QH13 | 2491 | 3129 | 29 | 99.07% | 52 |
| 96122 | 100/2015/QH13 | 4801 | 3428 | 4 | 99.88% | 4 |
| 96115 | 92/2015/QH13 | 2659 | 2821 | 5 | 99.82% | 0 |
| 96172 | 101/2015/QH13 | 2890 | 2972 | 3 | 99.90% | 0 |
| 139264 | 45/2019/QH14 | 1166 | 2320 | 6 | 99.74% | 0 |
| 96117 | 95/2015/QH13 | 1702 | 2647 | 8 | 99.70% | 0 |

- Độ phủ thấp nhất: **99.07%** (ngưỡng 98%) — ĐẠT
- Tổng Điều rỗng: **56** (ngưỡng 0) — KHÔNG ĐẠT
- **Kết quả: FAIL**

## Token thiếu, từng văn bản

- `95942` 91/2015/QH13: [',', '2015./.', ';', 'BỘ', 'CHẤP', 'CƯỢC,', 'CẦM', 'CỌC,', 'CỐ', 'KHOÁN', 'KHÁCH', 'KÝ', 'KẾT', 'LÃNH', 'LƯU', 'LẬP', 'QUỸ', 'RIÊNG', 'SỬA', 'THẾ', 'TOÀN', 'Tiểu', 'TÍN', 'XIII,', 'khóa', 'khấu', 'ĐOẠT', 'ĐẶT', 'ĐỔI,']
- `96122` 100/2015/QH13: ['2015./.', 'Hiến', 'XIII,', 'khóa']
- `96115` 92/2015/QH13: ['2015', 'XIII,', '________', '____________________________________________________________', 'khóa']
- `96172` 101/2015/QH13: ['/.', '_________', '____________________________________________________________']
- `139264` 45/2019/QH14: ['.', '2019./.', 'BỘ', 'XIV,', 'khóa', '“']
- `96117` 95/2015/QH13: ['11', '2015./.', '25', 'Hiến', 'LUẬT', 'XIII,', '____________________________________________________________', 'họp']

## Chi tiết

- {'doc_id': '95942', 'dieu': '654', 'loi': 'Điều RỖNG và không có con'}
- {'doc_id': '95942', 'dieu': '560', 'loi': 'Điều RỖNG và không có con'}
- {'doc_id': '95942', 'dieu': '316', 'loi': 'Điều RỖNG và không có con'}
- {'doc_id': '95942', 'dieu': '679', 'loi': 'Điều RỖNG và không có con'}
- {'doc_id': '95942', 'dieu': '597', 'loi': 'Điều RỖNG và không có con'}
- {'doc_id': '96122', 'dieu': '39', 'loi': 'Điều RỖNG và không có con'}
- {'doc_id': '96122', 'dieu': '1', 'loi': 'Điều RỖNG và không có con'}
- {'doc_id': '96122', 'dieu': '339', 'loi': 'Điều RỖNG và không có con'}
- {'doc_id': '96122', 'dieu': '351', 'loi': 'Điều RỖNG và không có con'}

Chẩn đoán đầy đủ, cơ chế và các lỗ của chính phép đo:
`.superpowers/sdd/2026-08-27-klaw-01-data-layer/task-10-report.md`
