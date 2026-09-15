# Tập mẫu tài liệu — đo SC-002

Dùng cho `python -m eval.run_tai_lieu`. Đo **tỉ lệ trường bắt buộc rút đúng** từ
tài liệu người dùng, ngưỡng 80%.

## Vì sao tài liệu tự dựng, không dùng giấy tờ thật

Giấy tờ thật của khách chứa thông tin cá nhân của **bên thứ ba** — người lao
động có tên trong hợp đồng chưa từng dùng KLAW và chưa đồng ý gì cả. Đưa vào kho
mã là công bố dữ liệu của họ. Cùng lý do `traces` không lưu toàn văn `/soat`
(`src/api/routes.py:1053-1060`, migration `011_soat_xoa_toan_van.sql`).

Tài liệu tự dựng còn có hai lợi thế: công bố được kèm khoá luận, và chạy lại
được bởi người khác.

## Cần bao nhiêu

20–30 tài liệu, **phủ các loại văn bản chính** chứ không dồn vào một loại — một
tập lệch sẽ cho một con số không nói lên điều gì về các loại còn lại.

## Cách dựng một mục

1. Soạn một tài liệu `.docx` hoặc xuất `.pdf` **có lớp chữ** (không phải ảnh
   chụp), đặt vào thư mục này.
2. Ghi nhãn: giá trị ĐÚNG của từng trường bắt buộc, gõ tay, không chép từ đầu ra
   của hệ thống. Nhãn chép từ đầu ra thì phép đo chỉ còn đo chính nó.
3. Thêm một mục vào `manifest.yaml`.

## `manifest.yaml`

```yaml
da_nguoi_duyet: false   # đổi thành true SAU KHI đã soát tay toàn bộ nhãn
duyet_boi: ""           # tên người soát
items:
  - id: hdld-thu-viec-01
    tep: hdld-thu-viec-01.docx
    loai: hdld           # phải là một `loai` có trong config/checklist_*.yaml
    ghi_chu: "HĐLĐ có điều khoản thử việc, lương vùng I"
    nhan:                # CHỈ trường bắt buộc; khoá lấy từ `rules.yaml`
      thoi_gian_thu_viec_ngay: "60"
      nhom_chuc_danh: cao_dang_tro_len
      luong_thu_viec: "17000000"
      luong_chinh_thuc: "20000000"
      luong_thang: "20000000"
      vung: "I"
```

Xem khoá của một loại:

```bash
python -c "from src.agents.nodes.gom_du_kien import truong_cua; [print(t['key'], '|', t['nhan'], '| bắt buộc' if t['bat_buoc'] else '') for t in truong_cua('hdld')]"
```

## Quy tắc khi đo

- **Không tinh chỉnh prompt trên chính tập này.** Cùng quy tắc `trap.yaml` đã
  đặt cho ngưỡng abstain: tinh chỉnh trên tập báo cáo là tự chấm điểm cho mình.
- Cột `trích khớp` phải luôn bằng 1.000. Nó thấp hơn nghĩa là có dữ kiện ra tới
  người dùng mà không tra ngược được — lỗi nghiêm trọng, không phải điểm thấp.
- Số xấu vẫn báo cáo.
