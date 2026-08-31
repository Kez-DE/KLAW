import type { HieuLuc } from '../../types';

/**
 * Mười lăm phiến của kho luật lơ lửng ở hero — MỖI PHIẾN LÀ MỘT VĂN BẢN CÓ
 * THẬT trong corpus, không phải chữ mẫu.
 *
 * Đây là ràng buộc quan trọng nhất của cả cảnh 3D. Hero của một sản phẩm tồn
 * tại để chống việc bịa nguồn thì không được in một số hiệu văn bản không tồn
 * tại lên mặt phiến. `KLAW-BUILD-SPEC` §10.1 đề bốn số hiệu làm ví dụ; đã tra
 * lại từng cái trong `documents`:
 *
 *   45/2019/QH14      CÓ    → giữ, và mang <Text> trên mặt phiến
 *   91/2015/QH13      CÓ    → giữ, và mang <Text> trên mặt phiến
 *   36/2005/QH11      KHÔNG → thay bằng 84/2015/QH13 (An toàn, vệ sinh lao động)
 *   356/2025/NĐ-CP    KHÔNG → thay bằng 92/2015/QH13 (Tố tụng dân sự)
 *
 * Hai số hiệu bị thay là hai số hiệu KHÔNG CÓ trong corpus. Không suy đoán,
 * không "chắc là có" — `SELECT count(*) FROM documents WHERE so_ky_hieu = ...`
 * trả về 0 cho cả hai.
 *
 * Toàn bộ trường dưới đây sinh trực tiếp từ cơ sở dữ liệu, không gõ tay:
 *
 *   SELECT d.id, d.so_ky_hieu, d.ten, p.duong_dan, p.noi_dung
 *     FROM provisions p JOIN documents d ON d.id = p.document_id
 *    WHERE d.so_ky_hieu = :k AND p.cap = 'khoan'
 *      AND length(p.noi_dung) BETWEEN 120 AND 240
 *    ORDER BY p.thu_tu;
 *
 * `hieuLuc` KHÔNG phải `documents.tinh_trang` đọc thẳng, mà là phán quyết của
 * chính `src/services/effectivity.py` (`danh_gia_theo_id`, as_of 2026-08-31).
 * Khác biệt này có thật và đáng giữ: 122/2015/NĐ-CP mang `tinh_trang = "CHL"`
 * trong CSDL quốc gia nhưng máy kết luận `bi_thay_the` — đúng cái sai 4/6 mà
 * effectivity.py tồn tại để bắt. Hero vì vậy trưng ra một phiến ĐỎ và một
 * phiến hết hiệu lực, không phải mười lăm phiến sạch.
 *
 * Muốn cập nhật: chạy lại truy vấn trên + `danh_gia_theo_id`, đừng sửa tay
 * từng dòng.
 */
export interface Phien {
  /** `documents.id` — đi thẳng vào tuyến THẬT `/van-ban/:docId`. */
  docId: string;
  soKyHieu: string;
  /** `documents.ten` nguyên văn, cho `<DuongDan boLuat>`. */
  ten: string;
  duongDan: string;
  /** Nguyên văn một Khoản, đã chuẩn hoá khoảng trắng. */
  trichDoan: string;
  /** Phán quyết của effectivity.py, không phải `tinh_trang` của MOJ. */
  hieuLuc: HieuLuc;
  tinCay: string;
}

/** Bốn phiến mang <Text> số hiệu trên mặt (§10.1).
 *
 * Cả bốn là ASCII thuần có lý do kỹ thuật, không phải tuỳ ý: troika (drei
 * `<Text>`) vẽ chữ từ MỘT file font, và bản JetBrains Mono tự host đã chia
 * subset — file `latin` có chữ số và dấu `/` nhưng KHÔNG có `Đ` (U+0110), nên
 * mọi số hiệu dạng `NĐ-CP` / `BLĐTBXH` sẽ ra ô tofu trên mặt phiến. Chúng vẫn
 * hiện đầy đủ ở tooltip và thẻ trích đoạn — đó là DOM thật, dùng font thật của
 * trang, phủ tiếng Việt đủ. Thà bớt bốn nhãn WebGL hơn là trưng một ô vuông
 * rỗng ở chỗ đáng ra là số hiệu văn bản.
 */
export const CO_NHAN = new Set(['45/2019/QH14', '91/2015/QH13', '84/2015/QH13', '92/2015/QH13']);

export const PHIEN: readonly Phien[] = [
  {
    docId: '139264',
    soKyHieu: '45/2019/QH14',
    ten: 'Bộ Luật lao động số 45/2019/QH14',
    duongDan: '45/2019/QH14 > Điều 118 > Khoản 1',
    trichDoan:
      '1. Người sử dụng lao động phải ban hành nội quy lao động, nếu sử dụng từ 10 người lao động trở lên thì nội quy lao động phải bằng văn bản.',
    hieuLuc: 'mot_phan_khong_xac_dinh',
    tinCay: 'thap',
  },
  {
    docId: '70811',
    soKyHieu: '84/2015/QH13',
    ten: 'Luật An toàn, vệ sinh lao động số 84/2015/QH13',
    duongDan: '84/2015/QH13 > Điều 49 > Khoản 6',
    trichDoan:
      '6. Mức hưởng trợ cấp tai nạn lao động, bệnh nghề nghiệp hằng tháng, trợ cấp phục vụ được điều chỉnh mức hưởng theo quy định của Luật bảo hiểm xã hội.',
    hieuLuc: 'mot_phan_khong_xac_dinh',
    tinCay: 'thap',
  },
  {
    docId: '96115',
    soKyHieu: '92/2015/QH13',
    ten: 'Bộ luật Tố tụng dân sự số 92/2015/QH13',
    duongDan: '92/2015/QH13 > Điều 242 > Khoản 2',
    trichDoan:
      '2. Trường hợp lời khai của đương sự và người làm chứng có ảnh hưởng lẫn nhau thì chủ toạ phiên tòa có thể quyết định cách ly đương sự với người làm chứng trước khi hỏi người làm chứng.',
    hieuLuc: 'mot_phan_khong_xac_dinh',
    tinCay: 'thap',
  },
  {
    docId: '95942',
    soKyHieu: '91/2015/QH13',
    ten: 'Bộ luật Dân sự số 91/2015/QH13',
    duongDan: '91/2015/QH13 > Điều 351 > Khoản 3',
    trichDoan:
      '3. Bên có nghĩa vụ không phải chịu trách nhiệm dân sự nếu chứng minh được nghĩa vụ không thực hiện được là hoàn toàn do lỗi của bên có quyền.',
    hieuLuc: 'con_hieu_luc',
    tinCay: 'thap',
  },
  {
    docId: '152668',
    soKyHieu: '145/2020/NĐ-CP',
    ten: 'Nghị định số 145/2020/NĐ-CP Quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động về điều kiện lao động và quan hệ lao động',
    duongDan: '145/2020/NĐ-CP > Điều 60 > Khoản 5',
    trichDoan:
      '5. Thời giờ quy định tại các khoản 1 Điều 58 Nghị định này được giảm trừ khi tính tổng số giờ làm thêm trong tháng, trong năm để xác định việc tuân thủ quy định tại điểm b, điểm c khoản 2 Điều 107 của Bộ luật Lao động.',
    hieuLuc: 'mot_phan_khong_xac_dinh',
    tinCay: 'thap',
  },
  {
    docId: '153913',
    soKyHieu: '12/2022/NĐ-CP',
    ten: 'Nghị định số 12/2022/NĐ-CP Quy định xử phạt vi phạm hành chính trong lĩnh vực lao động, bảo hiểm xã hội, người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng',
    duongDan: '12/2022/NĐ-CP > Điều 15 > Khoản 4',
    trichDoan:
      '4. Không bố trí địa điểm, thời gian và các điều kiện vật chất cần thiết khác để tổ chức các cuộc đối thoại tại nơi làm việc.',
    hieuLuc: 'con_hieu_luc',
    tinCay: 'thap',
  },
  {
    docId: '185561',
    soKyHieu: '337/2025/NĐ-CP',
    ten: 'Nghị định số 337/2025/NĐ-CP Quy định về hợp đồng lao động điện tử',
    duongDan: '337/2025/NĐ-CP > Điều 18 > Khoản 2',
    trichDoan:
      '2. Thông qua kết nối, chia sẻ dữ liệu giữa Nền tảng hợp đồng lao động điện tử với các cơ sở dữ liệu quốc gia, cơ sở dữ liệu, hệ thống thông tin liên quan khác.',
    hieuLuc: 'con_hieu_luc',
    tinCay: 'thap',
  },
  {
    docId: '134611',
    soKyHieu: '29/2019/NĐ-CP',
    ten: 'Nghị định số 29/2019/NĐ-CP Quy định chi tiết thi hành Khoản 3 Điều 54 Bộ luật lao động về việc cấp phép hoạt động cho thuê lại lao động, việc ký quỹ và danh mục công việc được thực hiện cho thuê lại lao động',
    duongDan: '29/2019/NĐ-CP > Điều 18 > Khoản 5',
    trichDoan:
      '5. Sở Lao động - Thương binh và Xã hội có trách nhiệm giám sát việc thực hiện thanh toán, bồi thường cho người lao động thuê lại theo quy định tại Khoản 1 Điều này và báo cáo kết quả thực hiện về Ủy ban nhân dân cấp tỉnh.',
    hieuLuc: 'can_doi_chieu_tay',
    tinCay: 'thap',
  },
  {
    docId: '146696',
    soKyHieu: '10/2020/TT-BLĐTBXH',
    ten: 'Thông tư số 10/2020/TT-BLĐTBXH Quy định chi tiết và hướng dẫn thi hành một số điều, khoản sau đây của Bộ luật Lao động về nội dung của Hợp đồng lao động, hội đồng thương lượng tập thể và nghề, công việc có ảnh hưởng xấu tới chức năng sinh sản, nuôi con',
    duongDan: '10/2020/TT-BLĐTBXH > Điều 8 > Khoản 6',
    trichDoan:
      '6. Giám sát việc thực hiện thỏa ước lao động tập thể nhiều doanh nghiệp theo quyết định thành lập Hội đồng thương lượng tập thể, bảo đảm phù hợp với thời gian hoạt động của Hội đồng.',
    hieuLuc: 'con_hieu_luc',
    tinCay: 'thap',
  },
  {
    docId: '152670',
    soKyHieu: '09/2020/TT-BLĐTBXH',
    ten: 'Thông tư số 09/2020/TT-BLĐTBXH Quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động về lao động chưa thành niên',
    duongDan: '09/2020/TT-BLĐTBXH > Điều 6 > Khoản 6',
    trichDoan:
      '6. Bản sao giấy khai sinh, giấy khám sức khỏe của người chưa đủ 13 tuổi. Thời khóa biểu hoặc chương trình học tập của cơ sở giáo dục nơi người chưa đủ 13 tuổi đang học tập nếu đang đi học.',
    hieuLuc: 'mot_phan_khong_xac_dinh',
    tinCay: 'thap',
  },
  {
    docId: '153297',
    soKyHieu: '18/2021/TT-BLĐTBXH',
    ten: 'Thông tư số 18/2021/TT-BLĐTBXH Quy định về thời giờ làm việc, thời giờ nghỉ ngơi đối với người lao động làm các công việc sản xuất có tính thời vụ, công việc gia công theo đơn đặt hàng',
    duongDan: '18/2021/TT-BLĐTBXH > Điều 8 > Khoản 2',
    trichDoan:
      '2. Trường hợp quyết định thực hiện chế độ thời giờ làm việc, thời giờ nghỉ ngơi theo Thông tư này thì phải thực hiện đầy đủ các nội dung sau:',
    hieuLuc: 'con_hieu_luc',
    tinCay: 'thap',
  },
  {
    docId: '152734',
    soKyHieu: '135/2020/NĐ-CP',
    ten: 'Nghị định số 135/2020/NĐ-CP Quy định về tuổi nghỉ hưu',
    duongDan: '135/2020/NĐ-CP > Điều 6 > Khoản 2',
    trichDoan:
      '2. Việc chấm dứt hợp đồng lao động và giải quyết chế độ bảo hiểm xã hội đối với người lao động quy định tại khoản 1 Điều này thực hiện theo quy định tại Mục 3 Chương III của Bộ luật Lao động và quy định của pháp luật về bảo hiểm xã hội.',
    hieuLuc: 'can_doi_chieu_tay',
    tinCay: 'thap',
  },
  {
    docId: '183939',
    soKyHieu: '293/2025/NĐ-CP',
    ten: 'Nghị định số 293/2025/NĐ-CP Quy định mức lương tối thiểu đối với người lao động làm việc theo hợp đồng lao động',
    duongDan: '293/2025/NĐ-CP > Điều 5 > Khoản 3',
    trichDoan:
      '3. Bãi bỏ khoản 7 Điều 15 và Phụ lục I kèm theo của Nghị định số 128/2025/NĐ-CP ngày 11 tháng 6 năm 2025 của Chính phủ quy định về phân quyền, phân cấp trong quản lý nhà nước lĩnh vực nội vụ.',
    hieuLuc: 'con_hieu_luc',
    tinCay: 'thap',
  },
  {
    docId: '168670',
    soKyHieu: '74/2024/NĐ-CP',
    ten: 'Nghị định số 74/2024/NĐ-CP Quy định mức lương tối thiểu đối với người lao động làm việc theo hợp đồng lao động.',
    duongDan: '74/2024/NĐ-CP > Điều 5 > Khoản 2',
    trichDoan:
      '2. Nghị định số 38/2022/NĐ-CP ngày 12 tháng 6 năm 2022 của Chính phủ quy định mức lương tối thiểu đối với người lao động làm việc theo hợp đồng lao động hết hiệu lực kể từ ngày 01 tháng 7 năm 2024.',
    hieuLuc: 'het_hieu_luc',
    tinCay: 'cao',
  },
  {
    docId: '92898',
    soKyHieu: '122/2015/NĐ-CP',
    ten: 'Nghị định số 122/2015/NĐ-CP Quy định mức lương tối thiểu vùng đối với người lao động làm việc ở doanh nghiệp, liên hiệp hợp tác xã, hợp tác xã, tổ hợp tác, trang trại, hộ gia đình, cá nhân và các cơ quan, tổ chức có sử dụng lao động theo hợp đồng lao động',
    duongDan: '122/2015/NĐ-CP > Điều 4 > Khoản 3',
    trichDoan:
      '3. Doanh nghiệp hoạt động trên địa bàn có sự thay đổi tên hoặc chia tách thì tạm thời áp dụng mức lương tối thiểu vùng quy định đối với địa bàn trước khi thay đổi tên hoặc chia tách cho đến khi Chính phủ có quy định mới.',
    hieuLuc: 'bi_thay_the',
    tinCay: 'trung_binh',
  },
];
