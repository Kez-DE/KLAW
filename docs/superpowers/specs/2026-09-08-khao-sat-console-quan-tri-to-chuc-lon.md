# Khảo sát console quản trị của các tổ chức lớn — đối chiếu với CMS KLAW

Ngày khảo sát: 2026-09-08 · Phụ lục cho `2026-09-08-cms-quan-ly-tai-khoan-design.md` (gói 2B)

## 1. Mục tiêu và phạm vi

Gói 2B dựng một trang quản trị tài khoản cho KLAW với hai vai trò, bốn màn hình và mười lăm
endpoint. Trước khi đóng thiết kế, cần biết những gì các console lớn coi là mặc định, để KLAW
biết mình đang bỏ gì và bỏ có ý thức. Khảo sát chỉ đọc tài liệu chính thức của GitHub,
Microsoft, Google Workspace, Slack, Atlassian, Stripe và Payload; mọi câu có sự kiện đều mang
số chú thích trỏ tới trang đã tải thật.

Hai địa chỉ trả 404 và được thay bằng trang tương đương: trang treo tài khoản của GitHub
Enterprise Cloud (thay bằng bản Enterprise Server 3.22 [5]) và trang vô hiệu tài khoản của
Atlassian ở nhánh `organization-administration` (thay bằng nhánh `user-management` [14]).
Bốn chủ đề **không kiểm chứng được** vì chưa tải tài liệu tương ứng, và không được điền bằng
trí nhớ: Conditional Access / IP allowlist của Microsoft, thao tác hàng loạt của GitHub,
kiểm soát "đăng nhập thay" của bất kỳ hãng nào, và cách Slack tính ghế khi vô hiệu tài khoản.

## 2. Bảng so sánh

| Cơ chế | GitHub | Microsoft | Google Workspace | Slack | Atlassian | Stripe |
|---|---|---|---|---|---|---|
| **Vai trò** | Owner, Member, Moderator, Billing manager, Security manager, App manager, Outside collaborator; vai trò tuỳ biến chỉ có ở Enterprise Cloud [1] | Xoá và khôi phục người dùng cần tối thiểu User Administrator [6][8] | Theo "User management privilege"; super admin làm được nhiều hơn admin thường khi xoá [10] | Workspace × Org, mỗi cấp có Admin / Owner / Primary Owner; thêm system role Security Admin và Users Admin [12] | Organization admin cho vòng đời tài khoản [14]; nhật ký chia ba lớp org / app admin / app user [16] | Khoảng 25 vai đặt sẵn; một Owner duy nhất; IAM Administrator chỉ quản trị truy cập; gán nhiều vai là **hợp** quyền, tài liệu cảnh báo "conflicts and unintended authority" [17] |
| **Vòng đời tài khoản** | Mời vào với vai owner / billing manager / member, sau đó gán thêm vai [1]; treo và bỏ treo [5] | Xoá → treo 30 ngày → tự xoá vĩnh viễn, "can't be stopped" [6] | Treo (khôi phục bất cứ lúc nào) hoặc xoá (khôi phục trong 20 ngày) [9][10] | Vô hiệu ↔ kích hoạt lại; ở Enterprise Grid chỉ vô hiệu được ở cấp org, cấp workspace chỉ "gỡ khỏi workspace" [12] | Vô hiệu ↔ kích hoạt lại, hiệu lực ngay; tên hiển thị bị nối thêm "(Deactivated)" [14] | Mời, sửa, gỡ thành viên là quyền của Administrator và IAM Administrator [17] |
| **Khoá vs xoá** | "GitHub recommends suspending users where possible, rather than deleting their accounts"; treo giữ nguyên issue, comment, repo, gist, chặn đăng nhập và push/pull, hiệu lực ngay [5] | Xoá là xoá mềm; khôi phục trả lại toàn bộ thuộc tính [6] | Nói thẳng: đừng xoá để chặn tạm — hãy treo; đừng xoá để tiết kiệm phí — dùng giấy phép Archived User [10] | Vô hiệu không xoá tin nhắn, tệp, hay hồ sơ; chỉ Primary Owner mới xin xoá được hồ sơ [12] | Vô hiệu không xoá dữ liệu cá nhân; muốn xoá vĩnh viễn thì phải dùng lệnh xoá riêng [14] | (Vòng đời gói đã nằm ở §2 của spec 2B) |
| **Audit log** | Giữ 180 ngày; mỗi dòng có người thực hiện, người bị tác động, repo, hành động, quốc gia, thời điểm; **không tìm bằng chữ tự do**, chỉ lọc theo `operation` / `actor` / `action` / `created` / `country` [2] | Audit log và Sign-in log: 7 ngày với bản Free, 30 ngày với P1 và P2 [7] | Công cụ "audit and investigation": nhiều bộ lọc, toán tử AND/OR, quy tắc báo cáo [11] | Audit Logs API **chỉ đọc, không có phương thức ghi**; mỗi sự kiện là actor + action + entity + context, context có `ua`, `ip_address`, `session_id` [13] | Ba lớp nhật ký; phạm vi truy cập gắn với gói thuê bao [16] | "View security history audit logs" là một quyền riêng, có mặt cả ở vai View Only [17] |
| **Xuất / stream nhật ký** | Xuất JSON hoặc CSV, trần cứng 100 MB hoặc 10 phút xử lý; stream tới S3, Azure Blob, Azure Event Hubs, GCS, Datadog, Splunk, đệm 7 ngày khi tạm dừng, tự kiểm tra sức khoẻ mỗi 24 giờ [2][4] | Muốn giữ lâu hơn mặc định thì phải đẩy sang Azure storage qua Azure Monitor [7] | Tải kết quả tìm kiếm, tối đa 100.000 dòng mỗi lần [11] | Kéo bằng API để nạp vào SIEM [13] | Xuất nhật ký, và webhook đẩy hoạt động sang công cụ khác [15] | Không kiểm chứng trong nguồn đã lấy |
| **Gói / ghế** | Treo "open up user licenses ... while preserving the ... data" [5]; người chưa bật 2FA vẫn giữ tư cách thành viên và **vẫn chiếm ghế** [3] | Xoá tài khoản **không** tự giảm số giấy phép — giảm là bước riêng của billing admin [8]; khôi phục trả lại giấy phép kể cả khi không còn ghế trống, có thể tạm vượt hạn mức [6] | Tài khoản bị treo **vẫn bị tính phí như tài khoản hoạt động**; xoá thì gói Flexible tính theo tỷ lệ, gói năm không giảm số giấy phép [9][10] | Tài liệu trỏ sang Fair Billing Policy; chi tiết không kiểm chứng [12] | Vô hiệu: "We'll stop billing your organization for this account"; kích hoạt lại thì tính phí lại [14] | (Đã nằm ở §2 của spec 2B) |
| **Bảo mật admin** | Bắt buộc 2FA toàn tổ chức, tuỳ chọn thêm "Only allow secure two-factor methods" (passkey, khoá bảo mật, ứng dụng xác thực, app GitHub); cộng tác viên ngoài không tuân thủ bị gỡ khỏi tổ chức [3] | Không kiểm chứng | Sau khi nhân sự rời: xoá thiết bị di động, **đặt lại cookie đăng nhập**, thu hồi khoá bảo mật [10] | Vô hiệu ⇒ đăng xuất khỏi mọi thiết bị và không đăng nhập lại được [12] | Mất quyền truy cập ngay lập tức khi vô hiệu [14] | Bắt buộc xác thực hai bước cho cả nhóm ở trang Team settings [18]; vai Transfer Analyst chỉ dùng được khi tài khoản đã bật bắt buộc [17] |
| **Thông báo** | Treo "with no notification to the user"; nhưng admin soạn được thông điệp hiển thị cho người bị treo khi họ đăng nhập [5]; stream cấu hình sai thì email cho enterprise owner [4] | Không kiểm chứng | Không kiểm chứng | "People aren't notified when their accounts are deactivated" [12] | **Có** email cho người dùng cả khi vô hiệu lẫn khi kích hoạt lại [14] | Một số vai nhận email về tài khoản kết nối [17] |
| **Thao tác hàng loạt** | Không kiểm chứng | Chọn nhiều người rồi Delete user; số lượng lớn dùng `Remove-MgUser` [8] | Treo hàng loạt bằng tệp CSV; xoá nhiều người bằng hộp chọn; xuất dữ liệu nhiều người bằng Data Export tool [9][10] | Tích chọn nhiều thành viên rồi Deactivate ở cấp org [12] | API vòng đời để tự động hoá vô hiệu và kích hoạt [14] | "Bulk exports of payments, customers, products" là quyền gắn theo vai [17] |
| **Đăng nhập thay** | Không kiểm chứng | Không kiểm chứng | Không kiểm chứng | Không có, nhưng Audit Logs API nói rõ "do **not** enable monitoring of message content" [13] | Không kiểm chứng | Không kiểm chứng |
| **Xuất dữ liệu / lưu trữ** | Xuất nhật ký [2]; muốn giữ quá 180 ngày phải stream [4] | OneDrive giữ mặc định 30 ngày rồi vào thùng rác 93 ngày; hộp thư đã xoá khôi phục được 30 ngày, hoặc chuyển thành hộp thư dùng chung [8] | Chuyển quyền sở hữu Drive, Docs, Calendar trước khi xoá; Takeout cho dữ liệu cá nhân; Data Export tool khi xoá nhiều người [10] | Hồ sơ vẫn còn sau khi vô hiệu; xoá hồ sơ là yêu cầu riêng của Primary Owner [12] | Vô hiệu giữ dữ liệu, xoá mới xoá dữ liệu cá nhân [14] | Vai Data Migration Specialist có quyền yêu cầu xuất dữ liệu [17] |

## 3. Mẫu hình chung — những gì mọi console đều làm giống nhau

1. **Khoá là mặc định, xoá là ngoại lệ.** GitHub khuyến nghị treo thay vì xoá [5], Google nói
   thẳng đừng xoá để chặn tạm [10], Atlassian và Slack đều giữ nguyên dữ liệu khi vô hiệu
   [12][14]. Không hệ nào coi "xoá" là công cụ kỷ luật.
2. **Xoá luôn có cửa sổ khôi phục, và cửa sổ đó hữu hạn.** Microsoft 30 ngày rồi tự xoá không
   dừng được [6]; Google 20 ngày rồi trả lại địa chỉ email [10]. Cửa sổ được công bố bằng con
   số, không phải "liên hệ hỗ trợ".
3. **Vô hiệu cắt phiên ngay, không đợi token hết hạn.** Slack đăng xuất mọi thiết bị và chặn
   đăng nhập lại [12]; Atlassian mất quyền tức thì [14]; GitHub chặn cả đăng nhập lẫn push/pull
   [5]; Google còn liệt kê "đặt lại cookie đăng nhập" thành việc phải làm [10].
4. **Nhật ký là bản ghi chỉ-đọc, có bộ lọc có cấu trúc, không phải ô tìm kiếm tự do.** GitHub
   nói rõ không tìm được bằng chữ [2]; Slack không có phương thức ghi nào [13].
5. **Nhật ký nào cũng có hạn lưu trữ, và ai muốn giữ lâu hơn phải tự đẩy ra ngoài.** 180 ngày
   ở GitHub [2], 7 hoặc 30 ngày ở Entra [7]; cả hai đều có đường stream hoặc archive [4][7],
   Atlassian có webhook [15].
6. **Xuất nhật ký luôn có trần công bố trước.** 100 MB hoặc 10 phút ở GitHub [2], 100.000 dòng
   mỗi lần tải ở Google [11]. Không hãng nào để một nút "xuất tất cả" không giới hạn.
7. **Vai trò tách "xem" khỏi "sửa", và tách cả "quản trị người dùng" khỏi "quản trị nghiệp
   vụ".** Stripe có IAM Administrator không làm được gì ngoài quản lý truy cập [17]; GitHub có
   security manager và billing manager [1].
8. **Tài khoản quản trị cuối cùng được bảo vệ bằng cấu trúc.** Không ai vô hiệu được Primary
   Owner của Slack trước khi người đó chuyển quyền [12]; GitHub khuyến nghị không dưới hai
   owner [1]; Google không cho admin tự xoá chính mình [10].

Ba chỗ các hãng **không** đồng ý, và đều là chỗ KLAW phải tự chọn:

- **Tiền khi bị khoá.** Google vẫn tính phí tài khoản bị treo và khuyên xoá nếu muốn tiết kiệm
  [9]; Atlassian ngừng tính phí ngay khi vô hiệu [14]; GitHub giải phóng ghế [5]. Ba câu trả
  lời khác nhau cho cùng một câu hỏi.
- **Báo hay không báo cho người bị khoá.** GitHub và Slack không báo [5][12]; Atlassian gửi
  email cả hai chiều [14].
- **Độ dài cửa sổ khôi phục.** 30 ngày [6] so với 20 ngày [10] — nghĩa là con số này là lựa
  chọn chính sách, không phải chuẩn kỹ thuật.

## 4. Đối chiếu với KLAW

**KLAW đã có, và đúng chuẩn ngành.** Khoá **không đổi `plan`**, chỉ đặt cờ (§5.1, §5.2) —
tránh đúng cái bẫy Google mô tả, nơi "khoá" và "tiền" bị trộn vào nhau [9]. Bắt buộc lý do khi
khoá, từ chối và thu hồi (§0 quyết định 4 và 5, §5.3) trùng ô "Log reason" GitHub bắt nhập khi
treo [5]. Nhật ký chỉ ghi thêm, có test grep chặn `UPDATE` và `DELETE` (§5.1, §9) là bản KLAW
của "read only, no write methods" [13]; bộ lọc theo thời gian, hành động, đối tượng (§5.3) đúng
mô hình lọc có cấu trúc của GitHub [2]. Ghi cả thao tác thất bại lẫn lần đăng nhập CMS sai
(§5.3, §6.3) là điều Slack đưa vào `user_login` [13]. `guardLastAdmin` (§6.2) là bản thu nhỏ
của bảo vệ Primary Owner [12]. Và việc **không endpoint nào trả nội dung hội thoại** (§5.3,
§11) trùng ranh giới Slack tự đặt cho Audit Logs API [13] — điểm mạnh nên nêu trong luận văn,
không phải thiếu sót.

**KLAW thiếu so với mặt bằng chung.** Không có xoá tài khoản kèm cửa sổ khôi phục công bố bằng
số ngày [6][10]. Khoá không cắt phiên Supabase (§10) trong khi bốn hệ đều cắt ngay
[5][10][12][14]. Không có 2FA cho tài khoản CMS [3][18]. Nhật ký không có chính sách lưu trữ,
không có trần xuất, không có đường đẩy ra ngoài [2][4][7][11]. Không có thao tác hàng loạt
[8][9][12], không có đường xuất dữ liệu cá nhân [10], không gửi email thật (§11) trong khi
Atlassian coi email là một phần của thao tác vô hiệu [14].

**KLAW cố ý không làm (§11).** Thanh toán trực tuyến, đọc nội dung hội thoại [13], sửa hạn mức
từ CMS, đồng bộ `admins` với `users`: giữ nguyên cả bốn — mỗi khoản đều thêm bề mặt mà không
đổi lấy gì. Gửi email thật: chấp nhận được vì đã có thông báo trong ứng dụng, nhưng ghi rõ là
lệch chuẩn có chủ đích. **Xoá tài khoản là khoản duy nhất nên xem lại**: KLAW loại nó vì cần
service-role key của Supabase, nhưng phần ẩn danh hoá phía KLAW không cần khoá đó — xem E.

## 5. Đề xuất ưu tiên

**A. Bắt buộc lý do cho *mọi* thao tác đổi trạng thái, kể cả mở khoá và đặt gói.**
Bắt chước: GitHub bắt nhập "Log reason" cho cả treo **và** bỏ treo [5]. Giá trị: hai admin đọc
lại nhật ký sau ba tháng cần biết *vì sao* mở khoá, không chỉ *ai* mở. Chi phí: **nhỏ** — thêm
một trường vào body của `POST /admin/tai-khoan/{sub}/mo-khoa` và `PATCH …/goi`, đưa vào
`chi_tiet` (đã là `JSONB`); **không migration, không endpoint mới**. → **Đưa vào gói 2B.**

**B. Trần công bố trước cho xuất CSV nhật ký.**
Bắt chước: GitHub trần 100 MB hoặc 10 phút [2]; Google trần 100.000 dòng mỗi lần tải [11]. Giá
trị: `GET /admin/nhat-ky?dinh_dang=csv` hiện không có trần; một nhật ký chỉ-ghi-thêm sẽ lớn dần
và cuối cùng một cú bấm sẽ dựng cả tiến trình. Chi phí: **nhỏ** — kẹp `limit`, ghi con số vào
giao diện và README; không migration. → **Đưa vào gói 2B.**

**C. Chính sách lưu trữ nhật ký, viết ra chứ chưa thi công.**
Bắt chước: 180 ngày ở GitHub [2], 7/30 ngày ở Entra [7], và cả hai đều nói rõ muốn giữ lâu hơn
thì phải tự đẩy ra ngoài [4][7]. Giá trị: hội đồng sẽ hỏi "nhật ký giữ bao lâu, ai xoá được".
KLAW trả lời được bằng một đoạn: giữ vô thời hạn, không có đường xoá trong `src/`, sao lưu theo
`pg_dump` của Postgres. Chi phí: **nhỏ** — một mục trong spec và README, **không mã**. Đẩy
stream ra S3 hay webhook thì **ngoài phạm vi**. → **Đưa vào gói 2B (phần chính sách);
stream ngoài phạm vi khoá luận.**

**D. Bắt buộc 2FA (TOTP) cho tài khoản CMS.**
Bắt chước: GitHub bắt buộc 2FA toàn tổ chức và còn chặn phương thức yếu [3]; Stripe cho bắt
buộc cả nhóm ở Team settings [18]. Giá trị: CMS nắm quyền đổi gói và khoá tài khoản của mọi
người dùng; mật khẩu đơn là điểm yếu nhất trong kiến trúc 2B. Chi phí: **vừa**. Payload 3.88
**không có 2FA sẵn** — danh sách tuỳ chọn `auth` chỉ có `tokenExpiration`, `maxLoginAttempts`,
`lockTime`, `cookies`, `useSessions`, `verify`, `useAPIKey`, `strategies` [19]. Có plugin cộng
đồng cho v3 (`@plutotcool/payload-plugin-two-factor`: TOTP, bí mật mã hoá AES-256-GCM, cookie
ký HMAC, middleware chặn `/admin`, MIT, v1.0.1 ngày 31/07/2026) [20] — nhưng repo mới 4 sao,
11 commit, hai người đóng góp; đặt biên xác thực của trang quản trị lên một phụ thuộc như vậy
là đổi rủi ro này lấy rủi ro khác. Cần **migration schema Payload** (ba trường ẩn) và một route
mới. → **Gói 2C**, nếu làm thì ghim phiên bản và đọc mã trước, hoặc tự viết qua
`auth.strategies`. Trong 2B, đối trọng rẻ hơn đã có: `maxLoginAttempts: 5` + `lockTime` + ghi
`dang_nhap_that_bai` (§6.2, §6.3).

**E. Ẩn danh hoá tài khoản theo yêu cầu, có cửa sổ khôi phục.**
Bắt chước: Microsoft 30 ngày rồi xoá vĩnh viễn không dừng được [6]; Google 20 ngày [10]; cả hai
tách rõ "vô hiệu" khỏi "xoá dữ liệu" [12][14]. Giá trị: nếu luận văn nhắc Nghị định
13/2023/NĐ-CP (chỉ nêu tên và số hiệu), thì phải có *một* đường đóng tài khoản, không chỉ đường
khoá. Mấu chốt: phần ẩn danh hoá phía KLAW (thay `email` bằng chuỗi băm, giữ `sub` để nhật ký
không gãy khoá ngoại) **không cần service-role key** — chỉ phần xoá tài khoản Supabase mới cần.
Chi phí: **vừa** — một cột `an_danh_luc`, một endpoint, một quy tắc hiển thị; **có migration**.
→ **Gói 2C**, mức tối thiểu: thủ công, một chiều, ghi nhật ký, không job nền tự dọn.

**F. Xuất dữ liệu của một người dùng.**
Bắt chước: Google Takeout và Data Export tool trong quy trình rời tổ chức [10]; Microsoft sao
lưu dữ liệu người đã rời [8]. Giá trị: một endpoint `GET /admin/tai-khoan/{sub}/xuat` trả JSON
gồm hồ sơ, gói, hạn, lịch sử yêu cầu — **không gồm hội thoại**, giữ nguyên ranh giới §5.3. Chi
phí: **nhỏ–vừa**, một endpoint mới, không migration (tái dùng `chi_tiet(sub)`). → **Gói 2C.**

**G. Thu hồi phiên Supabase khi khoá.** — **Ngoài phạm vi, giữ nguyên §11.** Slack đăng xuất
mọi thiết bị [12] và Google đặt lại cookie đăng nhập [10], nhưng cổng KLAW đã chặn mọi endpoint
tốn LLM và mọi endpoint tài khoản ngay tại `bao_ve` (§5.2), nên phiên còn sống chỉ cho phép
người bị khoá nhìn thấy thẻ khoá — đúng hành vi mong muốn. Đổi lại phải đưa service-role key,
tức một bí mật có quyền trên toàn bộ người dùng, vào dịch vụ chạy trên Railway. Chi phí **lớn**
so với giá trị; ghi lệch chuẩn này vào luận văn kèm lý do là câu trả lời đúng hơn.

**H. Thao tác hàng loạt.** — **Ngoài phạm vi.** Có ở cả bốn hệ [8][9][10][12], nhưng với 1–3
admin và vài trăm người dùng chưa có thao tác nào lặp đủ nhiều để cần.

**I. Phân quyền chi tiết hơn hai vai trò.** — **Ngoài phạm vi.** Stripe tách IAM Administrator
[17] và GitHub tách security manager [1] vì họ có hàng trăm admin; với ba người, vai thứ ba chỉ
thêm bề mặt kiểm thử. Một bài học vẫn nên ghi: gán nhiều vai là **hợp** quyền và dễ sinh quyền
ngoài ý muốn [17] — KLAW dùng `select` đơn trị nên đã tránh sẵn.

**J. IP allowlist cho CMS.** — **Ngoài phạm vi**, và nói rõ: **không nguồn nào trong bộ đã tải
hỗ trợ đề xuất này** (tài liệu Conditional Access của Microsoft chưa được tải). Với một CMS
chạy sau đăng nhập cookie, cùng công sức đó bỏ vào 2FA (đề xuất D) cho lợi ích lớn hơn.

## 6. Nguồn

Tất cả truy cập ngày **2026-09-08**.

1. *Roles in an organization* — GitHub Docs. https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/roles-in-an-organization
2. *Reviewing the audit log for your organization* — GitHub Docs. https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/reviewing-the-audit-log-for-your-organization
3. *Requiring two-factor authentication in your organization* — GitHub Docs. https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-two-factor-authentication-for-your-organization/requiring-two-factor-authentication-in-your-organization
4. *Streaming the audit log for your enterprise* — GitHub Enterprise Cloud Docs. https://docs.github.com/en/enterprise-cloud@latest/admin/monitoring-activity-in-your-enterprise/reviewing-audit-logs-for-your-enterprise/streaming-the-audit-log-for-your-enterprise
5. *Suspending and unsuspending users* — GitHub Enterprise Server 3.22 Docs. https://docs.github.com/enterprise/admin/articles/suspending-and-unsuspending-users
6. *Restore or remove a recently deleted user* — Microsoft Entra. https://learn.microsoft.com/en-us/entra/fundamentals/users-restore
7. *Microsoft Entra data retention* — Microsoft Entra ID. https://learn.microsoft.com/en-us/entra/identity/monitoring-health/reference-reports-data-retention
8. *Delete a user from your organization* — Microsoft 365 admin. https://learn.microsoft.com/en-us/microsoft-365/admin/add-users/delete-a-user
9. *Suspend a user temporarily* — Google Workspace Admin Help. https://support.google.com/a/answer/33312
10. *Delete or remove a user from your organization* — Google Workspace Admin Help. https://support.google.com/a/answer/33314
11. *About the audit and investigation tool* — Google Workspace Admin Help. https://support.google.com/a/answer/9725452
12. *Deactivate a member's account* — Slack Help Center. https://slack.com/help/articles/204475027-Deactivate-a-members-account
13. *Audit Logs API* — Slack Developer Docs. https://docs.slack.dev/admins/audit-logs-api/
14. *Deactivate a managed account* — Atlassian Support. https://support.atlassian.com/user-management/docs/deactivate-a-managed-account/
15. *Monitor and audit activity in your organization* — Atlassian Support. https://support.atlassian.com/security-and-access-policies/docs/monitor-and-audit-activity-in-your-organization/
16. *What activities does the audit log include?* — Atlassian Support. https://support.atlassian.com/security-and-access-policies/docs/accessing-audit-log-activities/
17. *User roles* — Stripe Documentation. https://docs.stripe.com/get-started/account/teams/roles
18. *Two-step authentication requirement* — Stripe Support. https://support.stripe.com/questions/two-step-authentication-requirement
19. *Authentication Overview* — Payload Documentation. https://payloadcms.com/docs/authentication/overview
20. *payload-plugin-two-factor* (readme, v1.0.1) — plutotcool. https://github.com/plutotcool/payload-plugin-two-factor
