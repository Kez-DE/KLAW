# Duyệt golden_qa — 77 câu

> **Trạng thái 2026-09-02: XONG.** Chủ dự án đã duyệt cả 77 câu; `duyet_boi: nguoi` trên toàn bộ và `test_moi_item_da_qua_review_cua_NGUOI` đã xanh.

Mỗi mục: câu hỏi, điều luật gold, và **toàn văn** điều đó (gồm Khoản/Điểm con).

Cách duyệt: đọc câu hỏi → đọc điều luật → hỏi *điều này có trả lời được câu kia không?*

- **ĐÚNG** → không cần làm gì
- **SAI** → ghi lại id và điều luật đúng
- **THIẾU** → gold đúng nhưng cần thêm điều khác

Xong hết thì đổi `da_review: true` cho các câu đã duyệt, rồi chạy `pytest -m pending_review`.

---

## 1. Công ty tôi có 50 nhân viên, trong đó có 30 nữ. Vậy công ty tôi có phải là công ty sử dụng nhiều lao động nữ không?

**145/2020/NĐ-CP > Điều 74**

```
Điều 74. Người sử dụng lao động có sử dụng nhiều lao động nữ Người sử dụng lao động có sử dụng nhiều lao động nữ là người sử dụng lao động thuộc một trong các trường hợp sau đây:
1. Sử dụng từ 10 lao động nữ đến dưới 100 lao động nữ, trong đó số lao động nữ chiếm 50% trở lên so với tổng số lao động.
2. Sử dụng từ 100 lao động nữ đến dưới 1.000 lao động nữ, trong đó số lao động nữ chiếm 30% trở lên so với tổng số lao động.
3. Sử dụng từ 1.000 lao động nữ trở lên.
```

`id=lao-000-0` · độ phủ từ khoá 57%

---

## 2. Nếu công ty tôi có 150 nhân viên, trong đó có 50 nữ, thì có được coi là công ty sử dụng nhiều lao động nữ không?

**145/2020/NĐ-CP > Điều 74**

```
Điều 74. Người sử dụng lao động có sử dụng nhiều lao động nữ Người sử dụng lao động có sử dụng nhiều lao động nữ là người sử dụng lao động thuộc một trong các trường hợp sau đây:
1. Sử dụng từ 10 lao động nữ đến dưới 100 lao động nữ, trong đó số lao động nữ chiếm 50% trở lên so với tổng số lao động.
2. Sử dụng từ 100 lao động nữ đến dưới 1.000 lao động nữ, trong đó số lao động nữ chiếm 30% trở lên so với tổng số lao động.
3. Sử dụng từ 1.000 lao động nữ trở lên.
```

`id=lao-000-1` · độ phủ từ khoá 44%

---

## 3. Nếu sếp em cứ chửi bới, xúc phạm em trước mặt mọi người thì có được không ạ? ⚠️ độ phủ từ khoá thấp — kiểm kỹ

**45/2019/QH14 > Điều 127**

```
Điều 127. Các hành vi bị nghiêm cấm khi xử lý kỷ luật lao động
1. Xâm phạm sức khỏe, danh dự, tính mạng, uy tín, nhân phẩm của người lao động.
2. Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động.
3. Xử lý kỷ luật lao động đối với người lao động có hành vi vi phạm không được quy định trong nội quy lao động hoặc không thỏa thuận trong hợp đồng lao động đã giao kết hoặc pháp luật về lao động không có quy định.
```

`id=lao-001-0` · độ phủ từ khoá 22%

---

## 4. Công ty có được trừ thẳng tiền lương của em vì đi muộn vài lần không ạ? ⚠️ độ phủ từ khoá thấp — kiểm kỹ

**45/2019/QH14 > Điều 127**

```
Điều 127. Các hành vi bị nghiêm cấm khi xử lý kỷ luật lao động
1. Xâm phạm sức khỏe, danh dự, tính mạng, uy tín, nhân phẩm của người lao động.
2. Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động.
3. Xử lý kỷ luật lao động đối với người lao động có hành vi vi phạm không được quy định trong nội quy lao động hoặc không thỏa thuận trong hợp đồng lao động đã giao kết hoặc pháp luật về lao động không có quy định.
```

`id=lao-001-1` · độ phủ từ khoá 25%

---

## 5. Từ ngày 1/1/2026, công ty tôi có được giảm lương của nhân viên làm thêm giờ hay không?

**293/2025/NĐ-CP > Điều 5**

```
Điều 5. Hiệu lực và trách nhiệm thi hành
1. Nghị định này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2026.
2. Nghị định số 74/2024/NĐ-CP ngày 30 tháng 6 năm 2024 của Chính phủ quy định mức lương tối thiểu đối với người lao động làm việc theo hợp đồng lao động hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành.
3. Bãi bỏ khoản 7 Điều 15 và Phụ lục I kèm theo của Nghị định số 128/2025/NĐ-CP ngày 11 tháng 6 năm 2025 của Chính phủ quy định về phân quyền, phân cấp trong quản lý nhà nước lĩnh vực nội vụ.
4. Người sử dụng lao động có trách nhiệm tổ chức rà soát lại các thỏa thuận trong hợp đồng lao động, thoả ước lao động tập thể và các quy chế, quy định của người sử dụng lao động để điều chỉnh, bổ sung cho phù hợp; không được xoá bỏ hoặc cắt giảm các chế độ tiền lương khi người lao động làm thêm giờ, làm việc vào ban đêm, chế độ bồi dưỡng bằng hiện vật và các chế độ khác theo quy định của pháp luật lao động. Đối với các nội dung đã thỏa thuận, cam kết trong hợp đồng lao động, thoả ước lao động tập thể hoặc các thỏa thuận hợp pháp khác có lợi hơn cho người lao động (như chế độ trả
```

`id=lao-002-0` · độ phủ từ khoá 73%

---

## 6. Nếu lương tối thiểu vùng mới thấp hơn lương cũ, công ty tôi có phải trả lương cũ cho nhân viên đã làm từ trước không?

**293/2025/NĐ-CP > Điều 5**

```
Điều 5. Hiệu lực và trách nhiệm thi hành
1. Nghị định này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2026.
2. Nghị định số 74/2024/NĐ-CP ngày 30 tháng 6 năm 2024 của Chính phủ quy định mức lương tối thiểu đối với người lao động làm việc theo hợp đồng lao động hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành.
3. Bãi bỏ khoản 7 Điều 15 và Phụ lục I kèm theo của Nghị định số 128/2025/NĐ-CP ngày 11 tháng 6 năm 2025 của Chính phủ quy định về phân quyền, phân cấp trong quản lý nhà nước lĩnh vực nội vụ.
4. Người sử dụng lao động có trách nhiệm tổ chức rà soát lại các thỏa thuận trong hợp đồng lao động, thoả ước lao động tập thể và các quy chế, quy định của người sử dụng lao động để điều chỉnh, bổ sung cho phù hợp; không được xoá bỏ hoặc cắt giảm các chế độ tiền lương khi người lao động làm thêm giờ, làm việc vào ban đêm, chế độ bồi dưỡng bằng hiện vật và các chế độ khác theo quy định của pháp luật lao động. Đối với các nội dung đã thỏa thuận, cam kết trong hợp đồng lao động, thoả ước lao động tập thể hoặc các thỏa thuận hợp pháp khác có lợi hơn cho người lao động (như chế độ trả
```

`id=lao-002-1` · độ phủ từ khoá 77%

---

## 7. Tôi ký hợp đồng với công ty hôm nay, vậy là từ lúc nào tôi bắt đầu đi làm chính thức? ⚠️ độ phủ từ khoá thấp — kiểm kỹ

**45/2019/QH14 > Điều 23**

```
Điều 23. Hiệu lực của hợp đồng lao động Hợp đồng lao động có hiệu lực kể từ ngày hai bên giao kết, trừ trường hợp hai bên có thỏa thuận hoặc pháp luật có quy định khác.
```

`id=lao-004-0` · độ phủ từ khoá 18%

---

## 8. Nếu tôi và công ty thỏa thuận là hợp đồng có hiệu lực vào tuần sau, thì có được không?

**45/2019/QH14 > Điều 23**

```
Điều 23. Hiệu lực của hợp đồng lao động Hợp đồng lao động có hiệu lực kể từ ngày hai bên giao kết, trừ trường hợp hai bên có thỏa thuận hoặc pháp luật có quy định khác.
```

`id=lao-004-1` · độ phủ từ khoá 60%

---

## 9. Nếu công ty tôi đóng cửa và tôi bị mất việc, tôi có được nhận tiền hỗ trợ gì không và bao nhiêu?

**45/2019/QH14 > Điều 47**

```
Điều 47. Trợ cấp mất việc làm
1. Người sử dụng lao động trả trợ cấp mất việc làm cho người lao động đã làm việc thường xuyên cho mình từ đủ 12 tháng trở lên mà bị mất việc làm theo quy định tại khoản 11 Điều 34 của Bộ luật này, cứ mỗi năm làm việc trả 01 tháng tiền lương nhưng ít nhất bằng 02 tháng tiền lương.
2. Thời gian làm việc để tính trợ cấp mất việc làm là tổng thời gian người lao động đã làm việc thực tế cho người sử dụng lao động trừ đi thời gian người lao động đã tham gia bảo hiểm thất nghiệp theo quy định của pháp luật về bảo hiểm thất nghiệp và thời gian làm việc đã được người sử dụng lao động chi trả trợ cấp thôi việc, trợ cấp mất việc làm.
3. Tiền lương để tính trợ cấp mất việc làm là tiền lương bình quân của 06 tháng liền kề theo hợp đồng lao động trước khi người lao động mất việc làm.
4. Chính phủ quy định chi tiết Điều này.
```

`id=lao-005-0` · độ phủ từ khoá 50%

---

## 10. Tôi làm ở công ty này được 5 năm, giờ bị cho nghỉ việc, thì tôi sẽ được nhận bao nhiêu tiền hỗ trợ mất việc?

**45/2019/QH14 > Điều 47**

```
Điều 47. Trợ cấp mất việc làm
1. Người sử dụng lao động trả trợ cấp mất việc làm cho người lao động đã làm việc thường xuyên cho mình từ đủ 12 tháng trở lên mà bị mất việc làm theo quy định tại khoản 11 Điều 34 của Bộ luật này, cứ mỗi năm làm việc trả 01 tháng tiền lương nhưng ít nhất bằng 02 tháng tiền lương.
2. Thời gian làm việc để tính trợ cấp mất việc làm là tổng thời gian người lao động đã làm việc thực tế cho người sử dụng lao động trừ đi thời gian người lao động đã tham gia bảo hiểm thất nghiệp theo quy định của pháp luật về bảo hiểm thất nghiệp và thời gian làm việc đã được người sử dụng lao động chi trả trợ cấp thôi việc, trợ cấp mất việc làm.
3. Tiền lương để tính trợ cấp mất việc làm là tiền lương bình quân của 06 tháng liền kề theo hợp đồng lao động trước khi người lao động mất việc làm.
4. Chính phủ quy định chi tiết Điều này.
```

`id=lao-005-1` · độ phủ từ khoá 60%

---

## 11. Nếu tôi thuê người giúp việc mà không làm giấy tờ gì cả, có bị phạt không?

**12/2022/NĐ-CP > Điều 30**

```
Điều 30. Vi phạm quy định về lao động là người giúp việc gia đình
1. Phạt cảnh cáo đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không giao kết hợp đồng lao động bằng văn bản với lao động là người giúp việc gia đình;
b) Không trả tiền tàu xe đi đường khi lao động là người giúp việc gia đình thôi việc về nơi cư trú, trừ trường hợp lao động là người giúp việc gia đình chấm dứt hợp đồng lao động trước thời hạn.
2. Phạt tiền từ 1.000.000 đồng đến 3.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không thông báo cho Ủy ban nhân dân xã, phường, thị trấn việc sử dụng lao động hoặc chấm dứt việc sử dụng lao động là người giúp việc gia đình theo quy định;
b) Đã bị xử phạt cảnh cáo đối với các hành vi vi phạm quy định tại khoản 1 Điều này nhưng lại tiếp tục vi phạm.
3. Phạt tiền từ 10.000.000 đồng đến 15.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Giữ giấy tờ tùy thân của lao động là người giúp việc gia đình;
b) Không trả cho lao động là người giúp việc gia đình khoản tiền bảo hiểm xã hội, bảo hiểm y tế
```

`id=lao-006-0` · độ phủ từ khoá 71%

---

## 12. Nếu tôi đuổi việc người giúp việc mà không cho tiền xe về quê thì có bị phạt không?

**12/2022/NĐ-CP > Điều 30**

```
Điều 30. Vi phạm quy định về lao động là người giúp việc gia đình
1. Phạt cảnh cáo đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không giao kết hợp đồng lao động bằng văn bản với lao động là người giúp việc gia đình;
b) Không trả tiền tàu xe đi đường khi lao động là người giúp việc gia đình thôi việc về nơi cư trú, trừ trường hợp lao động là người giúp việc gia đình chấm dứt hợp đồng lao động trước thời hạn.
2. Phạt tiền từ 1.000.000 đồng đến 3.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không thông báo cho Ủy ban nhân dân xã, phường, thị trấn việc sử dụng lao động hoặc chấm dứt việc sử dụng lao động là người giúp việc gia đình theo quy định;
b) Đã bị xử phạt cảnh cáo đối với các hành vi vi phạm quy định tại khoản 1 Điều này nhưng lại tiếp tục vi phạm.
3. Phạt tiền từ 10.000.000 đồng đến 15.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Giữ giấy tờ tùy thân của lao động là người giúp việc gia đình;
b) Không trả cho lao động là người giúp việc gia đình khoản tiền bảo hiểm xã hội, bảo hiểm y tế
```

`id=lao-006-1` · độ phủ từ khoá 71%

---

## 13. Nếu tôi làm sai gì đó ở nước ngoài, thì cán bộ ở Đại sứ quán Việt Nam có thể phạt tôi bao nhiêu tiền?

**12/2022/NĐ-CP > Điều 56**

```
Điều 56. Thẩm quyền xử phạt của người đứng đầu cơ quan đại diện ngoại giao, cơ quan lãnh sự, cơ quan khác Người đứng đầu cơ quan đại diện ngoại giao, cơ quan lãnh sự, cơ quan khác được ủy quyền thực hiện chức năng lãnh sự của nước Cộng hòa xã hội chủ nghĩa Việt Nam ở nước ngoài có quyền: Phạt tiền đến 100.000.000 đồng đối với hành vi vi phạm quy định tại điểm c khoản 9 Điều 42; điểm c khoản 8 Điều 43; điểm c khoản 7 Điều 44; điểm c khoản 6 Điều 45; khoản 1 Điều 46; điểm b khoản 2 Điều 46 Nghị định này.
```

`id=lao-009-0` · độ phủ từ khoá 58%

---

## 14. Tôi có thể bị phạt tối đa bao nhiêu nếu tôi vi phạm quy định nào đó khi làm việc với cơ quan đại diện của Việt Nam ở nước ngoài?

**12/2022/NĐ-CP > Điều 56**

```
Điều 56. Thẩm quyền xử phạt của người đứng đầu cơ quan đại diện ngoại giao, cơ quan lãnh sự, cơ quan khác Người đứng đầu cơ quan đại diện ngoại giao, cơ quan lãnh sự, cơ quan khác được ủy quyền thực hiện chức năng lãnh sự của nước Cộng hòa xã hội chủ nghĩa Việt Nam ở nước ngoài có quyền: Phạt tiền đến 100.000.000 đồng đối với hành vi vi phạm quy định tại điểm c khoản 9 Điều 42; điểm c khoản 8 Điều 43; điểm c khoản 7 Điều 44; điểm c khoản 6 Điều 45; khoản 1 Điều 46; điểm b khoản 2 Điều 46 Nghị định này.
```

`id=lao-009-1` · độ phủ từ khoá 73%

---

## 15. Tôi muốn làm việc chỉ 4 tiếng một ngày thôi thì có được không ạ?

**45/2019/QH14 > Điều 32**

```
Điều 32. Làm việc không trọn thời gian
1. Người lao động làm việc không trọn thời gian là người lao động có thời gian làm việc ngắn hơn so với thời gian làm việc bình thường theo ngày hoặc theo tuần hoặc theo tháng được quy định trong pháp luật về lao động, thỏa ước lao động tập thể hoặc nội quy lao động.
2. Người lao động thỏa thuận với người sử dụng lao động làm việc không trọn thời gian khi giao kết hợp đồng lao động.
3. Người lao động làm việc không trọn thời gian được hưởng lương; bình đẳng trong thực hiện quyền và nghĩa vụ với người lao động làm việc trọn thời gian; bình đẳng về cơ hội, không bị phân biệt đối xử, bảo đảm an toàn, vệ sinh lao động.
```

`id=lao-010-0` · độ phủ từ khoá 43%

---

## 16. Nếu tôi làm việc nửa ngày thì lương có bị cắt hết không ạ?

**45/2019/QH14 > Điều 32**

```
Điều 32. Làm việc không trọn thời gian
1. Người lao động làm việc không trọn thời gian là người lao động có thời gian làm việc ngắn hơn so với thời gian làm việc bình thường theo ngày hoặc theo tuần hoặc theo tháng được quy định trong pháp luật về lao động, thỏa ước lao động tập thể hoặc nội quy lao động.
2. Người lao động thỏa thuận với người sử dụng lao động làm việc không trọn thời gian khi giao kết hợp đồng lao động.
3. Người lao động làm việc không trọn thời gian được hưởng lương; bình đẳng trong thực hiện quyền và nghĩa vụ với người lao động làm việc trọn thời gian; bình đẳng về cơ hội, không bị phân biệt đối xử, bảo đảm an toàn, vệ sinh lao động.
```

`id=lao-010-1` · độ phủ từ khoá 57%

---

## 17. Nếu công ty tôi ký thỏa ước lao động tập thể mà không cho nhân viên biết thì có bị phạt không?

**12/2022/NĐ-CP > Điều 16**

```
Điều 16. Vi phạm quy định về thương lượng tập thể, thỏa ước lao động tập thể
1. Phạt tiền từ 1.000.000 đồng đến 3.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không gửi thỏa ước lao động tập thể đến cơ quan chuyên môn về lao động thuộc Ủy ban nhân dân cấp tỉnh nơi đặt trụ sở chính theo quy định;
b) Không trả chi phí cho việc thương lượng; ký kết; sửa đổi, bổ sung; gửi; công bố thỏa ước lao động tập thể;
c) Cung cấp thông tin không đúng thời hạn theo quy định hoặc cung cấp thông tin sai lệch về: tình hình hoạt động sản xuất, kinh doanh; nội dung khác liên quan trực tiếp đến nội dung thương lượng theo quy định khi đại diện người lao động yêu cầu để tiến hành thương lượng tập thể;
d) Không công bố thỏa ước lao động tập thể đã được ký kết cho người lao động biết.
2. Phạt tiền từ 3.000.000 đồng đến 5.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không cung cấp thông tin về: tình hình hoạt động sản xuất, kinh doanh; nội dung khác liên quan trực tiếp đến nội dung thương lượng theo quy định khi đại diện người lao động yêu
```

`id=lao-011-0` · độ phủ từ khoá 91%

---

## 18. Công ty tôi từ chối ngồi lại nói chuyện với đại diện nhân viên để bàn về quyền lợi chung thì có bị phạt không?

**12/2022/NĐ-CP > Điều 16**

```
Điều 16. Vi phạm quy định về thương lượng tập thể, thỏa ước lao động tập thể
1. Phạt tiền từ 1.000.000 đồng đến 3.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không gửi thỏa ước lao động tập thể đến cơ quan chuyên môn về lao động thuộc Ủy ban nhân dân cấp tỉnh nơi đặt trụ sở chính theo quy định;
b) Không trả chi phí cho việc thương lượng; ký kết; sửa đổi, bổ sung; gửi; công bố thỏa ước lao động tập thể;
c) Cung cấp thông tin không đúng thời hạn theo quy định hoặc cung cấp thông tin sai lệch về: tình hình hoạt động sản xuất, kinh doanh; nội dung khác liên quan trực tiếp đến nội dung thương lượng theo quy định khi đại diện người lao động yêu cầu để tiến hành thương lượng tập thể;
d) Không công bố thỏa ước lao động tập thể đã được ký kết cho người lao động biết.
2. Phạt tiền từ 3.000.000 đồng đến 5.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không cung cấp thông tin về: tình hình hoạt động sản xuất, kinh doanh; nội dung khác liên quan trực tiếp đến nội dung thương lượng theo quy định khi đại diện người lao động yêu
```

`id=lao-011-1` · độ phủ từ khoá 40%

---

## 19. Công ty tôi mới mở, tôi cần phải làm gì với mấy bạn nhân viên mới ngay từ đầu để đúng quy định của nhà nước?

**45/2019/QH14 > Điều 12**

```
Điều 12. Trách nhiệm quản lý lao động của người sử dụng lao động
1. Lập, cập nhật, quản lý, sử dụng sổ quản lý lao động bằng bản giấy hoặc bản điện tử và xuất trình khi cơ quan nhà nước có thẩm quyền yêu cầu.
2. Khai trình việc sử dụng lao động trong thời hạn 30 ngày kể từ ngày bắt đầu hoạt động, định kỳ báo cáo tình hình thay đổi về lao động trong quá trình hoạt động với cơ quan chuyên môn về lao động thuộc Ủy ban nhân dân cấp tỉnh và thông báo cho cơ quan bảo hiểm xã hội.
3. Chính phủ quy định chi tiết Điều này.
```

`id=lao-013-0` · độ phủ từ khoá 40%

---

## 20. Nếu công ty tôi có thay đổi về nhân sự, ví dụ có người nghỉ việc hay có người mới vào, thì tôi có cần báo cáo cho cơ quan chức năng không và báo cáo khi nào?

**45/2019/QH14 > Điều 12**

```
Điều 12. Trách nhiệm quản lý lao động của người sử dụng lao động
1. Lập, cập nhật, quản lý, sử dụng sổ quản lý lao động bằng bản giấy hoặc bản điện tử và xuất trình khi cơ quan nhà nước có thẩm quyền yêu cầu.
2. Khai trình việc sử dụng lao động trong thời hạn 30 ngày kể từ ngày bắt đầu hoạt động, định kỳ báo cáo tình hình thay đổi về lao động trong quá trình hoạt động với cơ quan chuyên môn về lao động thuộc Ủy ban nhân dân cấp tỉnh và thông báo cho cơ quan bảo hiểm xã hội.
3. Chính phủ quy định chi tiết Điều này.
```

`id=lao-013-1` · độ phủ từ khoá 50%

---

## 21. Công ty nhận tôi vào học việc, có được thu tiền học việc của tôi không?

**45/2019/QH14 > Điều 61**

```
Điều 61. Học nghề, tập nghề để làm việc cho người sử dụng lao động
1. Học nghề để làm việc cho người sử dụng lao động là việc người sử dụng lao động tuyển người vào để đào tạo nghề nghiệp tại nơi làm việc. Thời gian học nghề theo chương trình đào tạo của từng trình độ theo quy định của Luật Giáo dục nghề nghiệp.
2. Tập nghề để làm việc cho người sử dụng lao động là việc người sử dụng lao động tuyển người vào để hướng dẫn thực hành công việc, tập làm nghề theo vị trí việc làm tại nơi làm việc. Thời hạn tập nghề không quá 03 tháng.
3. Người sử dụng lao động tuyển người vào học nghề, tập nghề để làm việc cho mình thì không phải đăng ký hoạt động giáo dục nghề nghiệp; không được thu học phí; phải ký hợp đồng đào tạo theo quy định của Luật Giáo dục nghề nghiệp.
4. Người học nghề, người tập nghề phải đủ 14 tuổi trở lên và phải có đủ sức khỏe phù hợp với yêu cầu học nghề, tập nghề. Người học nghề, người tập nghề thuộc danh mục nghề, công việc nặng nhọc, độc hại, nguy hiểm hoặc đặc biệt nặng nhọc, độc hại, nguy hiểm do Bộ trưởng Bộ Lao động - Thương binh và Xã hội ban hành phải từ đủ 18 tuổi
```

`id=lao-014-0` · độ phủ từ khoá 71%

---

## 22. Nếu tôi đi học nghề ở công ty thì có được trả lương không?

**45/2019/QH14 > Điều 61**

```
Điều 61. Học nghề, tập nghề để làm việc cho người sử dụng lao động
1. Học nghề để làm việc cho người sử dụng lao động là việc người sử dụng lao động tuyển người vào để đào tạo nghề nghiệp tại nơi làm việc. Thời gian học nghề theo chương trình đào tạo của từng trình độ theo quy định của Luật Giáo dục nghề nghiệp.
2. Tập nghề để làm việc cho người sử dụng lao động là việc người sử dụng lao động tuyển người vào để hướng dẫn thực hành công việc, tập làm nghề theo vị trí việc làm tại nơi làm việc. Thời hạn tập nghề không quá 03 tháng.
3. Người sử dụng lao động tuyển người vào học nghề, tập nghề để làm việc cho mình thì không phải đăng ký hoạt động giáo dục nghề nghiệp; không được thu học phí; phải ký hợp đồng đào tạo theo quy định của Luật Giáo dục nghề nghiệp.
4. Người học nghề, người tập nghề phải đủ 14 tuổi trở lên và phải có đủ sức khỏe phù hợp với yêu cầu học nghề, tập nghề. Người học nghề, người tập nghề thuộc danh mục nghề, công việc nặng nhọc, độc hại, nguy hiểm hoặc đặc biệt nặng nhọc, độc hại, nguy hiểm do Bộ trưởng Bộ Lao động - Thương binh và Xã hội ban hành phải từ đủ 18 tuổi
```

`id=lao-014-1` · độ phủ từ khoá 100%

---

## 23. Nếu tôi làm việc mà sếp không trả lương thì tôi phải làm sao?

**45/2019/QH14 > Điều 97**

```
Điều 97. Kỳ hạn trả lương
1. Người lao động hưởng lương theo giờ, ngày, tuần thì được trả lương sau giờ, ngày, tuần làm việc hoặc được trả gộp do hai bên thỏa thuận nhưng không quá 15 ngày phải được trả gộp một lần.
2. Người lao động hưởng lương theo tháng được trả một tháng một lần hoặc nửa tháng một lần. Thời điểm trả lương do hai bên thỏa thuận và phải được ấn định vào một thời điểm có tính chu kỳ.
3. Người lao động hưởng lương theo sản phẩm, theo khoán được trả lương theo thỏa thuận của hai bên; nếu công việc phải làm trong nhiều tháng thì hằng tháng được tạm ứng tiền lương theo khối lượng công việc đã làm trong tháng.
4. Trường hợp vì lý do bất khả kháng mà người sử dụng lao động đã tìm mọi biện pháp khắc phục nhưng không thể trả lương đúng hạn thì không được chậm quá 30 ngày; nếu trả lương chậm từ 15 ngày trở lên thì người sử dụng lao động phải đền bù cho người lao động một khoản tiền ít nhất bằng số tiền lãi của số tiền trả chậm tính theo lãi suất huy động tiền gửi có kỳ hạn 01 tháng do ngân hàng nơi người sử dụng lao động mở tài khoản trả lương cho người lao động công bố tại 
```

**12/2022/NĐ-CP > Điều 17**

```
Điều 17. Vi phạm quy định về tiền lương
1. Phạt tiền từ 5.000.000 đồng đến 10.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không công bố công khai tại nơi làm việc trước khi thực hiện: thang lương, bảng lương; mức lao động; quy chế thưởng;
b) Không xây dựng thang lương, bảng lương hoặc định mức lao động; không áp dụng thử mức lao động trước khi ban hành chính thức;
c) Không tham khảo ý kiến của tổ chức đại diện người lao động tại cơ sở đối với nơi có tổ chức đại diện người lao động tại cơ sở khi xây dựng thang lương, bảng lương; định mức lao động; quy chế thưởng;
d) Không thông báo bảng kê trả lương hoặc có thông báo bảng kê trả lương cho người lao động nhưng không đúng theo quy định;
đ) Không trả lương bình đẳng hoặc phân biệt giới tính đối với người lao động làm công việc có giá trị như nhau.
2. Phạt tiền đối với người sử dụng lao động có một trong các hành vi: Trả lương không đúng hạn theo quy định của pháp luật; không trả hoặc trả không đủ tiền lương cho người lao động theo thỏa thuận trong hợp đồng lao động; không trả hoặc trả không đủ tiền lư
```

`id=lao-015-0` · độ phủ từ khoá 80%

---

## 24. Tôi đi học nghề mà họ không trả tiền công cho tôi thì có được không?

**12/2022/NĐ-CP > Điều 4 > Khoản 7**

```
7. Buộc người sử dụng lao động trả lương cho người lao động; người học nghề, tập nghề hoặc trả đủ tiền lương cho người lao động.
```

`id=lao-015-1` · độ phủ từ khoá 80%

---

## 25. Công ty tôi sắp cắt giảm nhân sự, họ phải thông báo cho chúng tôi biết những gì về việc ai sẽ ở lại, ai sẽ nghỉ việc và quyền lợi của chúng tôi ra sao?

**45/2019/QH14 > Điều 44**

```
Điều 44. Phương án sử dụng lao động
1. Phương án sử dụng lao động phải có những nội dung chủ yếu sau đây:
a) Số lượng và danh sách người lao động tiếp tục được sử dụng, người lao động được đào tạo lại để tiếp tục sử dụng, người lao động được chuyển sang làm việc không trọn thời gian;
b) Số lượng và danh sách người lao động nghỉ hưu;
c) Số lượng và danh sách người lao động phải chấm dứt hợp đồng lao động;
d) Quyền và nghĩa vụ của người sử dụng lao động, người lao động và các bên liên quan trong việc thực hiện phương án sử dụng lao động;
đ) Biện pháp và nguồn tài chính bảo đảm thực hiện phương án.
2. Khi xây dựng phương án sử dụng lao động, người sử dụng lao động phải trao đổi ý kiến với tổ chức đại diện người lao động tại cơ sở đối với nơi có tổ chức đại diện người lao động tại cơ sở. Phương án sử dụng lao động phải được thông báo công khai cho người lao động biết trong thời hạn 15 ngày kể từ ngày được thông qua.
```

`id=lao-017-0` · độ phủ từ khoá 60%

---

## 26. Nếu công ty tôi muốn cho một số người nghỉ việc, họ có cần bàn bạc với đại diện của chúng tôi trước không và phải báo cho mọi người biết kế hoạch này trong bao lâu?

**45/2019/QH14 > Điều 44**

```
Điều 44. Phương án sử dụng lao động
1. Phương án sử dụng lao động phải có những nội dung chủ yếu sau đây:
a) Số lượng và danh sách người lao động tiếp tục được sử dụng, người lao động được đào tạo lại để tiếp tục sử dụng, người lao động được chuyển sang làm việc không trọn thời gian;
b) Số lượng và danh sách người lao động nghỉ hưu;
c) Số lượng và danh sách người lao động phải chấm dứt hợp đồng lao động;
d) Quyền và nghĩa vụ của người sử dụng lao động, người lao động và các bên liên quan trong việc thực hiện phương án sử dụng lao động;
đ) Biện pháp và nguồn tài chính bảo đảm thực hiện phương án.
2. Khi xây dựng phương án sử dụng lao động, người sử dụng lao động phải trao đổi ý kiến với tổ chức đại diện người lao động tại cơ sở đối với nơi có tổ chức đại diện người lao động tại cơ sở. Phương án sử dụng lao động phải được thông báo công khai cho người lao động biết trong thời hạn 15 ngày kể từ ngày được thông qua.
```

`id=lao-017-1` · độ phủ từ khoá 47%

---

## 27. Tôi làm công nhân hầm lò đã được 15 năm, giờ tôi muốn nghỉ hưu sớm thì cần bao nhiêu năm đóng bảo hiểm xã hội và bao nhiêu tuổi?

**45/2019/QH14 > Điều 219 > Khoản 1**

```
1. Sửa đổi, bổ sung một số điều của Luật Bảo hiểm xã hội số 58/2014/QH13 đã được sửa đổi, bổ sung theo Luật số 84/2015/QH13 và Luật số 35/2018/QH14:
a) Sửa đổi, bổ sung Điều 54 như sau: “Điều 54. Điều kiện hưởng lương hưu 1. Người lao động quy định tại các điểm a, b, c, d, g, h và i khoản 1 Điều 2 của Luật này, trừ trường hợp quy định tại khoản 3 Điều này, khi nghỉ việc có đủ 20 năm đóng bảo hiểm xã hội trở lên thì được hưởng lương hưu nếu thuộc một trong các trường hợp sau đây: a) Đủ tuổi theo quy định tại khoản 2 Điều 169 của Bộ luật Lao động; b) Đủ tuổi theo quy định tại khoản 3 Điều 169 của Bộ luật Lao động và có đủ 15 năm làm nghề, công việc nặng nhọc, độc hại, nguy hiểm hoặc đặc biệt nặng nhọc, độc hại, nguy hiểm thuộc danh mục do Bộ Lao động - Thương binh và Xã hội ban hành hoặc có đủ 15 năm làm việc ở vùng có điều kiện kinh tế - xã hội đặc biệt khó khăn bao gồm cả thời gian làm việc ở nơi có phụ cấp khu vực hệ số 0,7 trở lên trước ngày 01 tháng 01 năm 2021; c) Người lao động có tuổi thấp hơn tối đa 10 tuổi so với tuổi nghỉ hưu của người lao động quy định tại khoản 2 Điều 169 
```

`id=lao-018-0` · độ phủ từ khoá 75%

---

## 28. Tôi bị tai nạn nghề nghiệp và nhiễm HIV, tôi đã đóng bảo hiểm xã hội được 20 năm rồi, vậy tôi có được hưởng lương hưu không?

**45/2019/QH14 > Điều 219 > Khoản 1**

```
1. Sửa đổi, bổ sung một số điều của Luật Bảo hiểm xã hội số 58/2014/QH13 đã được sửa đổi, bổ sung theo Luật số 84/2015/QH13 và Luật số 35/2018/QH14:
a) Sửa đổi, bổ sung Điều 54 như sau: “Điều 54. Điều kiện hưởng lương hưu 1. Người lao động quy định tại các điểm a, b, c, d, g, h và i khoản 1 Điều 2 của Luật này, trừ trường hợp quy định tại khoản 3 Điều này, khi nghỉ việc có đủ 20 năm đóng bảo hiểm xã hội trở lên thì được hưởng lương hưu nếu thuộc một trong các trường hợp sau đây: a) Đủ tuổi theo quy định tại khoản 2 Điều 169 của Bộ luật Lao động; b) Đủ tuổi theo quy định tại khoản 3 Điều 169 của Bộ luật Lao động và có đủ 15 năm làm nghề, công việc nặng nhọc, độc hại, nguy hiểm hoặc đặc biệt nặng nhọc, độc hại, nguy hiểm thuộc danh mục do Bộ Lao động - Thương binh và Xã hội ban hành hoặc có đủ 15 năm làm việc ở vùng có điều kiện kinh tế - xã hội đặc biệt khó khăn bao gồm cả thời gian làm việc ở nơi có phụ cấp khu vực hệ số 0,7 trở lên trước ngày 01 tháng 01 năm 2021; c) Người lao động có tuổi thấp hơn tối đa 10 tuổi so với tuổi nghỉ hưu của người lao động quy định tại khoản 2 Điều 169 
```

`id=lao-018-1` · độ phủ từ khoá 93%

---

## 29. Nếu công ty đưa tôi đi làm việc ở nước ngoài mà họ làm sai hợp đồng đã đăng ký thì họ bị phạt bao nhiêu tiền?

**12/2022/NĐ-CP > Điều 42 > Khoản 5**

```
5. Phạt tiền từ 50.000.000 đồng đến 70.000.000 đồng khi có một trong các hành vi sau đây:
a) Không duy trì một trong các điều kiện quy định tại Điều 10 của Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng theo quy định của pháp luật trong suốt quá trình hoạt động;
b) Không duy trì điều kiện quy định tại điểm b khoản 2 Điều 20 của Nghị định số 112/2021/NĐ-CP ngày 10 tháng 12 năm 2021 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng trong suốt thời gian hoạt động dịch vụ đưa người lao động Việt Nam đi làm giúp việc gia đình ở nước ngoài và trong thời gian người lao động Việt Nam do doanh nghiệp đưa đi đang làm giúp việc gia đình ở nước ngoài;
c) Thực hiện không đúng các nội dung hợp đồng cung ứng lao động đã đăng ký và được chấp thuận;
d) Không bồi thường cho người lao động về những thiệt hại do doanh nghiệp hoặc chi nhánh của doanh nghiệp gây ra theo quy định của pháp luật;
đ) Không tư vấn, hỗ trợ cho người lao động các thủ tục liên quan đến chấm dứt hợp đồng lao động, quyền lợi, ch
```

`id=lao-020-0` · độ phủ từ khoá 83%

---

## 30. Công ty môi giới xuất khẩu lao động mà quảng cáo sai sự thật về lương hoặc điều kiện làm việc cho tôi thì có bị phạt không? Nếu có thì phạt bao nhiêu?

**12/2022/NĐ-CP > Điều 42 > Khoản 5**

```
5. Phạt tiền từ 50.000.000 đồng đến 70.000.000 đồng khi có một trong các hành vi sau đây:
a) Không duy trì một trong các điều kiện quy định tại Điều 10 của Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng theo quy định của pháp luật trong suốt quá trình hoạt động;
b) Không duy trì điều kiện quy định tại điểm b khoản 2 Điều 20 của Nghị định số 112/2021/NĐ-CP ngày 10 tháng 12 năm 2021 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng trong suốt thời gian hoạt động dịch vụ đưa người lao động Việt Nam đi làm giúp việc gia đình ở nước ngoài và trong thời gian người lao động Việt Nam do doanh nghiệp đưa đi đang làm giúp việc gia đình ở nước ngoài;
c) Thực hiện không đúng các nội dung hợp đồng cung ứng lao động đã đăng ký và được chấp thuận;
d) Không bồi thường cho người lao động về những thiệt hại do doanh nghiệp hoặc chi nhánh của doanh nghiệp gây ra theo quy định của pháp luật;
đ) Không tư vấn, hỗ trợ cho người lao động các thủ tục liên quan đến chấm dứt hợp đồng lao động, quyền lợi, ch
```

`id=lao-020-1` · độ phủ từ khoá 61%

---

## 31. Nếu tôi muốn thay đổi một vài điều khoản trong hợp đồng lao động với công ty thì phải làm thế nào?

**45/2019/QH14 > Điều 33**

```
Điều 33. Sửa đổi, bổ sung hợp đồng lao động
1. Trong quá trình thực hiện hợp đồng lao động, nếu bên nào có yêu cầu sửa đổi, bổ sung nội dung hợp đồng lao động thì phải báo cho bên kia biết trước ít nhất 03 ngày làm việc về nội dung cần sửa đổi, bổ sung.
2. Trường hợp hai bên thỏa thuận được thì việc sửa đổi, bổ sung nội dung hợp đồng lao động được tiến hành bằng việc ký kết phụ lục hợp đồng lao động hoặc giao kết hợp đồng lao động mới.
3. Trường hợp hai bên không thỏa thuận được việc sửa đổi, bổ sung nội dung hợp đồng lao động thì tiếp tục thực hiện hợp đồng lao động đã giao kết.
```

`id=lao-022-0` · độ phủ từ khoá 58%

---

## 32. Công ty tôi muốn giảm lương của tôi, họ có được làm ngay không hay phải báo trước bao lâu?

**45/2019/QH14 > Điều 33**

```
Điều 33. Sửa đổi, bổ sung hợp đồng lao động
1. Trong quá trình thực hiện hợp đồng lao động, nếu bên nào có yêu cầu sửa đổi, bổ sung nội dung hợp đồng lao động thì phải báo cho bên kia biết trước ít nhất 03 ngày làm việc về nội dung cần sửa đổi, bổ sung.
2. Trường hợp hai bên thỏa thuận được thì việc sửa đổi, bổ sung nội dung hợp đồng lao động được tiến hành bằng việc ký kết phụ lục hợp đồng lao động hoặc giao kết hợp đồng lao động mới.
3. Trường hợp hai bên không thỏa thuận được việc sửa đổi, bổ sung nội dung hợp đồng lao động thì tiếp tục thực hiện hợp đồng lao động đã giao kết.
```

`id=lao-022-1` · độ phủ từ khoá 30%

---

## 33. Nếu công ty tôi cử tôi đi làm ở nước ngoài mà xảy ra chuyện gì đó với tôi, ví dụ như tai nạn hay bị bệnh nặng, mà công ty không lo liệu gì hết thì có bị phạt không?

**12/2022/NĐ-CP > Điều 43 > Khoản 6**

```
6. Phạt tiền từ 75.000.000 đồng đến 90.000.000 đồng khi có một trong các hành vi sau đây:
a) Không báo cáo hoặc không phối hợp với cơ quan đại diện Việt Nam ở nước ngoài để quản lý, bảo vệ quyền và lợi ích hợp pháp, chính đáng của người lao động trong thời gian làm việc ở nước ngoài;
b) Không thực hiện yêu cầu của cơ quan có thẩm quyền hoặc không phối hợp với cơ quan, tổ chức có liên quan của nước mà người lao động đến làm việc để giải quyết tranh chấp liên quan đến người lao động làm việc ở nước ngoài;
c) Không giải quyết vấn đề phát sinh đối với người lao động theo một trong các trường hợp sau: chết; bị tai nạn; bị xâm phạm tính mạng; bị xâm phạm sức khỏe; bị xâm phạm danh dự, nhân phẩm; bị xâm phạm tài sản; thiên tai; dịch bệnh; chiến tranh; bất ổn chính trị; suy thoái kinh tế; tình trạng khẩn cấp; vì lý do bất khả kháng khác.
```

`id=lao-023-0` · độ phủ từ khoá 47%

---

## 34. Nếu tôi đi làm ở nước ngoài mà gặp chuyện không may, ví dụ như bị tai nạn lao động, mà công ty không báo cho đại sứ quán Việt Nam để họ giúp đỡ thì có bị phạt không?

**12/2022/NĐ-CP > Điều 43 > Khoản 6**

```
6. Phạt tiền từ 75.000.000 đồng đến 90.000.000 đồng khi có một trong các hành vi sau đây:
a) Không báo cáo hoặc không phối hợp với cơ quan đại diện Việt Nam ở nước ngoài để quản lý, bảo vệ quyền và lợi ích hợp pháp, chính đáng của người lao động trong thời gian làm việc ở nước ngoài;
b) Không thực hiện yêu cầu của cơ quan có thẩm quyền hoặc không phối hợp với cơ quan, tổ chức có liên quan của nước mà người lao động đến làm việc để giải quyết tranh chấp liên quan đến người lao động làm việc ở nước ngoài;
c) Không giải quyết vấn đề phát sinh đối với người lao động theo một trong các trường hợp sau: chết; bị tai nạn; bị xâm phạm tính mạng; bị xâm phạm sức khỏe; bị xâm phạm danh dự, nhân phẩm; bị xâm phạm tài sản; thiên tai; dịch bệnh; chiến tranh; bất ổn chính trị; suy thoái kinh tế; tình trạng khẩn cấp; vì lý do bất khả kháng khác.
```

`id=lao-023-1` · độ phủ từ khoá 63%

---

## 35. Nếu công ty tôi đột nhiên đóng cửa mấy ngày vì lý do kinh doanh, tôi có được nhận lương không và bao nhiêu? ⚠️ độ phủ từ khoá thấp — kiểm kỹ

**45/2019/QH14 > Điều 99**

```
Điều 99. Tiền lương ngừng việc Trường hợp phải ngừng việc, người lao động được trả lương như sau:
1. Nếu do lỗi của người sử dụng lao động thì người lao động được trả đủ tiền lương theo hợp đồng lao động;
2. Nếu do lỗi của người lao động thì người đó không được trả lương; những người lao động khác trong cùng đơn vị phải ngừng việc thì được trả lương theo mức do hai bên thỏa thuận nhưng không được thấp hơn mức lương tối thiểu;
3. Nếu vì sự cố về điện, nước mà không do lỗi của người sử dụng lao động hoặc do thiên tai, hỏa hoạn, dịch bệnh nguy hiểm, địch họa, di dời địa điểm hoạt động theo yêu cầu của cơ quan nhà nước có thẩm quyền hoặc vì lý do kinh tế thì hai bên thỏa thuận về tiền lương ngừng việc như sau:
a) Trường hợp ngừng việc từ 14 ngày làm việc trở xuống thì tiền lương ngừng việc được thỏa thuận không thấp hơn mức lương tối thiểu;
b) Trường hợp phải ngừng việc trên 14 ngày làm việc thì tiền lương ngừng việc do hai bên thỏa thuận nhưng phải bảo đảm tiền lương ngừng việc trong 14 ngày đầu tiên không thấp hơn mức lương tối thiểu.
```

`id=lao-024-0` · độ phủ từ khoá 27%

---

## 36. Nếu tôi không đi làm được vì công ty bị ngập nước, tôi có được trả lương không?

**45/2019/QH14 > Điều 99**

```
Điều 99. Tiền lương ngừng việc Trường hợp phải ngừng việc, người lao động được trả lương như sau:
1. Nếu do lỗi của người sử dụng lao động thì người lao động được trả đủ tiền lương theo hợp đồng lao động;
2. Nếu do lỗi của người lao động thì người đó không được trả lương; những người lao động khác trong cùng đơn vị phải ngừng việc thì được trả lương theo mức do hai bên thỏa thuận nhưng không được thấp hơn mức lương tối thiểu;
3. Nếu vì sự cố về điện, nước mà không do lỗi của người sử dụng lao động hoặc do thiên tai, hỏa hoạn, dịch bệnh nguy hiểm, địch họa, di dời địa điểm hoạt động theo yêu cầu của cơ quan nhà nước có thẩm quyền hoặc vì lý do kinh tế thì hai bên thỏa thuận về tiền lương ngừng việc như sau:
a) Trường hợp ngừng việc từ 14 ngày làm việc trở xuống thì tiền lương ngừng việc được thỏa thuận không thấp hơn mức lương tối thiểu;
b) Trường hợp phải ngừng việc trên 14 ngày làm việc thì tiền lương ngừng việc do hai bên thỏa thuận nhưng phải bảo đảm tiền lương ngừng việc trong 14 ngày đầu tiên không thấp hơn mức lương tối thiểu.
```

`id=lao-024-1` · độ phủ từ khoá 67%

---

## 37. Nếu công ty em muốn đình công thì ai là người có quyền quyết định và phải làm những gì trước khi đình công ạ?

**45/2019/QH14 > Điều 201**

```
Điều 201. Lấy ý kiến về đình công
1. Trước khi tiến hành đình công, tổ chức đại diện người lao động có quyền tổ chức và lãnh đạo đình công quy định tại Điều 198 của Bộ luật này có trách nhiệm lấy ý kiến của toàn thể người lao động hoặc thành viên ban lãnh đạo của các tổ chức đại diện người lao động tham gia thương lượng.
2. Nội dung lấy ý kiến bao gồm:
a) Đồng ý hay không đồng ý đình công;
b) Phương án của tổ chức đại diện người lao động về nội dung quy định tại các điểm b, c và d khoản 2 Điều 202 của Bộ luật này.
3. Việc lấy ý kiến được thực hiện trực tiếp bằng hình thức lấy phiếu hoặc chữ ký hoặc hình thức khác.
4. Thời gian, địa điểm và cách thức tiến hành lấy ý kiến về đình công do tổ chức đại diện người lao động quyết định và phải thông báo cho người sử dụng lao động biết trước ít nhất 01 ngày. Việc lấy ý kiến không được làm ảnh hưởng đến hoạt động sản xuất, kinh doanh bình thường của người sử dụng lao động. Người sử dụng lao động không được gây khó khăn, cản trở hoặc can thiệp vào quá trình tổ chức đại diện người lao động tiến hành lấy ý kiến về đình công.
```

`id=lao-025-0` · độ phủ từ khoá 80%

---

## 38. Tôi muốn mở công ty cho thuê lại lao động, tôi cần mang giấy tờ đến đâu để xin phép và mất bao lâu thì có giấy phép?

**29/2019/NĐ-CP > Điều 9**

```
Điều 9. Trình tự, thủ tục cấp giấy phép
1. Doanh nghiệp gửi một bộ hồ sơ theo quy định tại Điều 8 Nghị định này đến Sở Lao động - Thương binh và Xã hội tỉnh, thành phố trực thuộc trung ương (sau đây gọi chung là Sở Lao động - Thương binh và Xã hội) nơi doanh nghiệp đặt trụ sở chính để đề nghị cấp giấy phép.
2. Hồ sơ đề nghị cấp giấy phép được tiếp nhận khi có đủ các giấy tờ quy định tại Điều 8 Nghị định này. Sau khi tiếp nhận hồ sơ, Sở Lao động - Thương binh và Xã hội cấp giấy biên nhận ghi rõ ngày, tháng, năm nhận hồ sơ.
3. Trong thời hạn 20 ngày làm việc kể từ ngày nhận được hồ sơ đảm bảo theo quy định, Sở Lao động - Thương binh và Xã hội thẩm tra, trình Chủ tịch Ủy ban nhân dân cấp tỉnh cấp giấy phép hoạt động cho thuê lại lao động đối với doanh nghiệp. Trường hợp hồ sơ không đảm bảo theo quy định, trong thời hạn 10 ngày làm việc kể từ ngày tiếp nhận hồ sơ, Sở Lao động - Thương binh và Xã hội có văn bản yêu cầu doanh nghiệp hoàn thiện hồ sơ.
4. Trong thời hạn 07 ngày làm việc kể từ ngày nhận được hồ sơ trình của Sở Lao động - Thương binh và Xã hội, Chủ tịch Ủy ban nhân dân cấp tỉn
```

`id=lao-026-0` · độ phủ từ khoá 47%

---

## 39. Nếu công ty tôi nộp hồ sơ xin phép cho thuê lại lao động mà bị thiếu giấy tờ, thì bao lâu tôi sẽ nhận được thông báo để bổ sung?

**29/2019/NĐ-CP > Điều 9**

```
Điều 9. Trình tự, thủ tục cấp giấy phép
1. Doanh nghiệp gửi một bộ hồ sơ theo quy định tại Điều 8 Nghị định này đến Sở Lao động - Thương binh và Xã hội tỉnh, thành phố trực thuộc trung ương (sau đây gọi chung là Sở Lao động - Thương binh và Xã hội) nơi doanh nghiệp đặt trụ sở chính để đề nghị cấp giấy phép.
2. Hồ sơ đề nghị cấp giấy phép được tiếp nhận khi có đủ các giấy tờ quy định tại Điều 8 Nghị định này. Sau khi tiếp nhận hồ sơ, Sở Lao động - Thương binh và Xã hội cấp giấy biên nhận ghi rõ ngày, tháng, năm nhận hồ sơ.
3. Trong thời hạn 20 ngày làm việc kể từ ngày nhận được hồ sơ đảm bảo theo quy định, Sở Lao động - Thương binh và Xã hội thẩm tra, trình Chủ tịch Ủy ban nhân dân cấp tỉnh cấp giấy phép hoạt động cho thuê lại lao động đối với doanh nghiệp. Trường hợp hồ sơ không đảm bảo theo quy định, trong thời hạn 10 ngày làm việc kể từ ngày tiếp nhận hồ sơ, Sở Lao động - Thương binh và Xã hội có văn bản yêu cầu doanh nghiệp hoàn thiện hồ sơ.
4. Trong thời hạn 07 ngày làm việc kể từ ngày nhận được hồ sơ trình của Sở Lao động - Thương binh và Xã hội, Chủ tịch Ủy ban nhân dân cấp tỉn
```

`id=lao-026-1` · độ phủ từ khoá 47%

---

## 40. Công ty có thể cho tôi nghỉ việc ngay lập tức nếu tôi vắng mặt ở chỗ làm quá 5 ngày mà không có lý do chính đáng không?

**45/2019/QH14 > Điều 36**

```
Điều 36. Quyền đơn phương chấm dứt hợp đồng lao động của người sử dụng lao động
1. Người sử dụng lao động có quyền đơn phương chấm dứt hợp đồng lao động trong trường hợp sau đây:
a) Người lao động thường xuyên không hoàn thành công việc theo hợp đồng lao động được xác định theo tiêu chí đánh giá mức độ hoàn thành công việc trong quy chế của người sử dụng lao động. Quy chế đánh giá mức độ hoàn thành công việc do người sử dụng lao động ban hành nhưng phải tham khảo ý kiến tổ chức đại diện người lao động tại cơ sở đối với nơi có tổ chức đại diện người lao động tại cơ sở;
b) Người lao động bị ốm đau, tai nạn đã điều trị 12 tháng liên tục đối với người làm việc theo hợp đồng lao động không xác định thời hạn hoặc đã điều trị 06 tháng liên tục đối với người làm việc theo hợp đồng lao động xác định thời hạn có thời hạn từ 12 tháng đến 36 tháng hoặc quá nửa thời hạn hợp đồng lao động đối với người làm việc theo hợp đồng lao động xác định thời hạn có thời hạn dưới 12 tháng mà khả năng lao động chưa hồi phục. Khi sức khỏe của người lao động bình phục thì người sử dụng lao động xem xét để tiếp t
```

`id=lao-028-0` · độ phủ từ khoá 67%

---

## 41. Nếu tôi làm việc không tốt và công ty có quy định đánh giá, họ có thể sa thải tôi mà không cần báo trước không?

**45/2019/QH14 > Điều 36**

```
Điều 36. Quyền đơn phương chấm dứt hợp đồng lao động của người sử dụng lao động
1. Người sử dụng lao động có quyền đơn phương chấm dứt hợp đồng lao động trong trường hợp sau đây:
a) Người lao động thường xuyên không hoàn thành công việc theo hợp đồng lao động được xác định theo tiêu chí đánh giá mức độ hoàn thành công việc trong quy chế của người sử dụng lao động. Quy chế đánh giá mức độ hoàn thành công việc do người sử dụng lao động ban hành nhưng phải tham khảo ý kiến tổ chức đại diện người lao động tại cơ sở đối với nơi có tổ chức đại diện người lao động tại cơ sở;
b) Người lao động bị ốm đau, tai nạn đã điều trị 12 tháng liên tục đối với người làm việc theo hợp đồng lao động không xác định thời hạn hoặc đã điều trị 06 tháng liên tục đối với người làm việc theo hợp đồng lao động xác định thời hạn có thời hạn từ 12 tháng đến 36 tháng hoặc quá nửa thời hạn hợp đồng lao động đối với người làm việc theo hợp đồng lao động xác định thời hạn có thời hạn dưới 12 tháng mà khả năng lao động chưa hồi phục. Khi sức khỏe của người lao động bình phục thì người sử dụng lao động xem xét để tiếp t
```

`id=lao-028-1` · độ phủ từ khoá 69%

---

## 42. Nếu tôi đi làm việc ở nước ngoài mà làm sai quy định, thì người có thẩm quyền cao nhất có thể phạt tôi bao nhiêu tiền?

**12/2022/NĐ-CP > Điều 50**

```
Điều 50. Thẩm quyền xử phạt của Cục trưởng Cục quản lý lao động ngoài nước Cục trưởng Cục quản lý lao động ngoài nước có quyền:
1. Phạt tiền đến 100.000.000 đồng đối với hành vi vi phạm hành chính trong lĩnh vực người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng quy định tại Chương IV Nghị định này.
2. Áp dụng hình thức xử phạt bổ sung quy định tại Chương IV Nghị định này.
3. Áp dụng biện pháp khắc phục hậu quả quy định tại Chương IV Nghị định này.
```

`id=lao-029-0` · độ phủ từ khoá 73%

---

## 43. Nếu tôi vi phạm quy định về việc đi làm việc ở nước ngoài, ngoài việc bị phạt tiền, tôi còn có thể bị áp dụng những hình thức xử lý nào khác không?

**12/2022/NĐ-CP > Điều 50**

```
Điều 50. Thẩm quyền xử phạt của Cục trưởng Cục quản lý lao động ngoài nước Cục trưởng Cục quản lý lao động ngoài nước có quyền:
1. Phạt tiền đến 100.000.000 đồng đối với hành vi vi phạm hành chính trong lĩnh vực người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng quy định tại Chương IV Nghị định này.
2. Áp dụng hình thức xử phạt bổ sung quy định tại Chương IV Nghị định này.
3. Áp dụng biện pháp khắc phục hậu quả quy định tại Chương IV Nghị định này.
```

`id=lao-029-1` · độ phủ từ khoá 75%

---

## 44. Nếu tôi ở lại nước ngoài trái phép sau khi hết hợp đồng mà không bị ai ép buộc, thì ai sẽ là người lập biên bản vi phạm của tôi?

**12/2022/NĐ-CP > Điều 59**

```
Điều 59. Thủ tục xử phạt đối với người lao động khi có hành vi vi phạm quy định tại khoản 1 Điều 46 Nghị định này
1. Chủ tịch Ủy ban nhân dân, Chánh thanh tra Bộ, Cục trưởng Cục Quản lý lao động ngoài nước, người đứng đầu cơ quan đại diện ngoại giao, cơ quan lãnh sự, cơ quan khác được ủy quyền thực hiện chức năng lãnh sự của Việt Nam ở nước ngoài (sau đây gọi chung là người có thẩm quyền xử phạt); công chức, viên chức đang thi hành công vụ, nhiệm vụ thanh tra, kiểm tra về người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng theo văn bản quy phạm pháp luật hoặc văn bản hành chính do cơ quan, người có thẩm quyền ban hành lập biên bản vi phạm hành chính đối với hành vi tự ý ở lại nước ngoài trái pháp luật sau khi chấm dứt hợp đồng lao động hoặc hợp đồng đào tạo nghề mà không phải do bị đe dọa, ép buộc dưới bất kỳ hình thức nào và không thuộc trường hợp bị truy cứu trách nhiệm hình sự khi có một trong các căn cứ sau đây:
a) Trực tiếp phát hiện hành vi vi phạm khi đang thi hành công vụ;
b) Nhận được văn bản thông báo của cơ quan, tổ chức có thẩm quyền của nước sở tại về hành vi 
```

`id=lao-030-0` · độ phủ từ khoá 87%

---

## 45. Khi tôi bị lập biên bản vì ở lại nước ngoài trái phép, biên bản đó sẽ được gửi đi đâu và ai sẽ là người quyết định phạt tôi?

**12/2022/NĐ-CP > Điều 59**

```
Điều 59. Thủ tục xử phạt đối với người lao động khi có hành vi vi phạm quy định tại khoản 1 Điều 46 Nghị định này
1. Chủ tịch Ủy ban nhân dân, Chánh thanh tra Bộ, Cục trưởng Cục Quản lý lao động ngoài nước, người đứng đầu cơ quan đại diện ngoại giao, cơ quan lãnh sự, cơ quan khác được ủy quyền thực hiện chức năng lãnh sự của Việt Nam ở nước ngoài (sau đây gọi chung là người có thẩm quyền xử phạt); công chức, viên chức đang thi hành công vụ, nhiệm vụ thanh tra, kiểm tra về người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng theo văn bản quy phạm pháp luật hoặc văn bản hành chính do cơ quan, người có thẩm quyền ban hành lập biên bản vi phạm hành chính đối với hành vi tự ý ở lại nước ngoài trái pháp luật sau khi chấm dứt hợp đồng lao động hoặc hợp đồng đào tạo nghề mà không phải do bị đe dọa, ép buộc dưới bất kỳ hình thức nào và không thuộc trường hợp bị truy cứu trách nhiệm hình sự khi có một trong các căn cứ sau đây:
a) Trực tiếp phát hiện hành vi vi phạm khi đang thi hành công vụ;
b) Nhận được văn bản thông báo của cơ quan, tổ chức có thẩm quyền của nước sở tại về hành vi 
```

`id=lao-030-1` · độ phủ từ khoá 79%

---

## 46. Tôi làm việc tự do, có ký hợp đồng điện tử với công ty thì có được bảo vệ không?

**337/2025/NĐ-CP > Điều 2**

```
Điều 2. Đối tượng áp dụng
1. Người lao động theo quy định tại khoản 1 Điều 3 Bộ luật Lao động giao kết, thực hiện hợp đồng lao động điện tử.
2. Người sử dụng lao động theo quy định tại khoản 2 Điều 3 Bộ luật Lao động giao kết, thực hiện hợp đồng lao động điện tử.
3. Cơ quan, tổ chức, cá nhân khác có liên quan đến việc thực hiện quy định tại Nghị định này.
```

`id=lao-031-0` · độ phủ từ khoá 57%

---

## 47. Công ty tôi muốn thuê người làm việc qua mạng và ký hợp đồng online, có được phép không?

**337/2025/NĐ-CP > Điều 2**

```
Điều 2. Đối tượng áp dụng
1. Người lao động theo quy định tại khoản 1 Điều 3 Bộ luật Lao động giao kết, thực hiện hợp đồng lao động điện tử.
2. Người sử dụng lao động theo quy định tại khoản 2 Điều 3 Bộ luật Lao động giao kết, thực hiện hợp đồng lao động điện tử.
3. Cơ quan, tổ chức, cá nhân khác có liên quan đến việc thực hiện quy định tại Nghị định này.
```

`id=lao-031-1` · độ phủ từ khoá 33%

---

## 48. Nếu công ty em với công nhân đang có chuyện bất đồng về lương mà bên hòa giải không giải quyết được thì công nhân có được phép nghỉ làm hết không ạ?

**45/2019/QH14 > Điều 199**

```
Điều 199. Trường hợp người lao động có quyền đình công Tổ chức đại diện người lao động là bên tranh chấp lao động tập thể về lợi ích có quyền tiến hành thủ tục quy định tại các điều 200, 201 và 202 của Bộ luật này để đình công trong trường hợp sau đây:
1. Hòa giải không thành hoặc hết thời hạn hòa giải quy định tại khoản 2 Điều 188 của Bộ luật này mà hòa giải viên lao động không tiến hành hòa giải;
2. Ban trọng tài lao động không được thành lập hoặc thành lập nhưng không ra quyết định giải quyết tranh chấp hoặc người sử dụng lao động là bên tranh chấp không thực hiện quyết định giải quyết tranh chấp của Ban trọng tài lao động.
```

`id=lao-033-0` · độ phủ từ khoá 40%

---

## 49. Nếu công ty em với công nhân đang có chuyện bất đồng về lương mà công ty không chịu làm theo quyết định của bên trọng tài thì công nhân có được phép nghỉ làm không ạ?

**45/2019/QH14 > Điều 199**

```
Điều 199. Trường hợp người lao động có quyền đình công Tổ chức đại diện người lao động là bên tranh chấp lao động tập thể về lợi ích có quyền tiến hành thủ tục quy định tại các điều 200, 201 và 202 của Bộ luật này để đình công trong trường hợp sau đây:
1. Hòa giải không thành hoặc hết thời hạn hòa giải quy định tại khoản 2 Điều 188 của Bộ luật này mà hòa giải viên lao động không tiến hành hòa giải;
2. Ban trọng tài lao động không được thành lập hoặc thành lập nhưng không ra quyết định giải quyết tranh chấp hoặc người sử dụng lao động là bên tranh chấp không thực hiện quyết định giải quyết tranh chấp của Ban trọng tài lao động.
```

`id=lao-033-1` · độ phủ từ khoá 35%

---

## 50. Khi đi làm, tôi cần biết những thông tin gì về công ty và công việc của mình được ghi trong giấy tờ?

**45/2019/QH14 > Điều 21**

```
Điều 21. Nội dung hợp đồng lao động
1. Hợp đồng lao động phải có những nội dung chủ yếu sau đây:
a) Tên, địa chỉ của người sử dụng lao động và họ tên, chức danh của người giao kết hợp đồng lao động bên phía người sử dụng lao động;
b) Họ tên, ngày tháng năm sinh, giới tính, nơi cư trú, số thẻ Căn cước công dân, Chứng minh nhân dân hoặc hộ chiếu của người giao kết hợp đồng lao động bên phía người lao động;
c) Công việc và địa điểm làm việc;
d) Thời hạn của hợp đồng lao động;
đ) Mức lương theo công việc hoặc chức danh, hình thức trả lương, thời hạn trả lương, phụ cấp lương và các khoản bổ sung khác;
e) Chế độ nâng bậc, nâng lương;
g) Thời giờ làm việc, thời giờ nghỉ ngơi;
h) Trang bị bảo hộ lao động cho người lao động;
i) Bảo hiểm xã hội, bảo hiểm y tế và bảo hiểm thất nghiệp;
k) Đào tạo, bồi dưỡng, nâng cao trình độ, kỹ năng nghề.
2. Khi người lao động làm việc có liên quan trực tiếp đến bí mật kinh doanh, bí mật công nghệ theo quy định của pháp luật thì người sử dụng lao động có quyền thỏa thuận bằng văn bản với người lao động về nội dung, thời hạn bảo vệ bí mật kinh doanh, bảo vệ bí 
```

`id=lao-034-0` · độ phủ từ khoá 36%

---

## 51. Nếu tôi làm việc liên quan đến bí mật của công ty, thì hợp đồng lao động cần ghi rõ những gì về việc này?

**45/2019/QH14 > Điều 21**

```
Điều 21. Nội dung hợp đồng lao động
1. Hợp đồng lao động phải có những nội dung chủ yếu sau đây:
a) Tên, địa chỉ của người sử dụng lao động và họ tên, chức danh của người giao kết hợp đồng lao động bên phía người sử dụng lao động;
b) Họ tên, ngày tháng năm sinh, giới tính, nơi cư trú, số thẻ Căn cước công dân, Chứng minh nhân dân hoặc hộ chiếu của người giao kết hợp đồng lao động bên phía người lao động;
c) Công việc và địa điểm làm việc;
d) Thời hạn của hợp đồng lao động;
đ) Mức lương theo công việc hoặc chức danh, hình thức trả lương, thời hạn trả lương, phụ cấp lương và các khoản bổ sung khác;
e) Chế độ nâng bậc, nâng lương;
g) Thời giờ làm việc, thời giờ nghỉ ngơi;
h) Trang bị bảo hộ lao động cho người lao động;
i) Bảo hiểm xã hội, bảo hiểm y tế và bảo hiểm thất nghiệp;
k) Đào tạo, bồi dưỡng, nâng cao trình độ, kỹ năng nghề.
2. Khi người lao động làm việc có liên quan trực tiếp đến bí mật kinh doanh, bí mật công nghệ theo quy định của pháp luật thì người sử dụng lao động có quyền thỏa thuận bằng văn bản với người lao động về nội dung, thời hạn bảo vệ bí mật kinh doanh, bảo vệ bí 
```

`id=lao-034-1` · độ phủ từ khoá 86%

---

## 52. Nếu tôi lén đưa 5 người đi làm ở Đài Loan mà không có giấy tờ hợp lệ thì bị phạt bao nhiêu tiền?

**12/2022/NĐ-CP > Điều 42 > Khoản 11**

```
11. Phạt tiền khi có hành vi đưa người lao động Việt Nam không có tên trong danh sách do Bộ Lao động - Thương binh và Xã hội xác nhận để đi làm việc tại Đài Loan (Trung Quốc) hoặc Nhật Bản theo một trong các mức sau đây:
a) Từ 20.000.000 đồng đến 40.000.000 đồng khi vi phạm từ 01 người đến 10 người lao động;
b) Từ 60.000.000 đồng đến 100.000.000 đồng khi vi phạm từ 11 người đến 50 người lao động;
c) Từ 150.000.000 đồng đến 180.000.000 đồng khi vi phạm trên 50 người lao động.
```

`id=lao-035-0` · độ phủ từ khoá 70%

---

## 53. Công ty tôi bị phát hiện đưa 20 người sang Nhật làm việc chui, không đúng danh sách, thì sẽ bị phạt nặng cỡ nào?

**12/2022/NĐ-CP > Điều 42 > Khoản 11**

```
11. Phạt tiền khi có hành vi đưa người lao động Việt Nam không có tên trong danh sách do Bộ Lao động - Thương binh và Xã hội xác nhận để đi làm việc tại Đài Loan (Trung Quốc) hoặc Nhật Bản theo một trong các mức sau đây:
a) Từ 20.000.000 đồng đến 40.000.000 đồng khi vi phạm từ 01 người đến 10 người lao động;
b) Từ 60.000.000 đồng đến 100.000.000 đồng khi vi phạm từ 11 người đến 50 người lao động;
c) Từ 150.000.000 đồng đến 180.000.000 đồng khi vi phạm trên 50 người lao động.
```

`id=lao-035-1` · độ phủ từ khoá 53%

---

## 54. Tôi làm việc 8 tiếng một ngày thì có được nghỉ giải lao giữa giờ không, và nếu có thì được nghỉ bao lâu?

**45/2019/QH14 > Điều 109**

```
Điều 109. Nghỉ trong giờ làm việc
1. Người lao động làm việc theo thời giờ làm việc quy định tại Điều 105 của Bộ luật này từ 06 giờ trở lên trong một ngày thì được nghỉ giữa giờ ít nhất 30 phút liên tục, làm việc ban đêm thì được nghỉ giữa giờ ít nhất 45 phút liên tục. Trường hợp người lao động làm việc theo ca liên tục từ 06 giờ trở lên thì thời gian nghỉ giữa giờ được tính vào giờ làm việc.
2. Ngoài thời gian nghỉ quy định tại khoản 1 Điều này, người sử dụng lao động bố trí cho người lao động các đợt nghỉ giải lao và ghi vào nội quy lao động.
```

`id=lao-036-0` · độ phủ từ khoá 80%

---

## 55. Nếu tôi làm ca đêm thì có được nghỉ dài hơn không ạ?

**45/2019/QH14 > Điều 109**

```
Điều 109. Nghỉ trong giờ làm việc
1. Người lao động làm việc theo thời giờ làm việc quy định tại Điều 105 của Bộ luật này từ 06 giờ trở lên trong một ngày thì được nghỉ giữa giờ ít nhất 30 phút liên tục, làm việc ban đêm thì được nghỉ giữa giờ ít nhất 45 phút liên tục. Trường hợp người lao động làm việc theo ca liên tục từ 06 giờ trở lên thì thời gian nghỉ giữa giờ được tính vào giờ làm việc.
2. Ngoài thời gian nghỉ quy định tại khoản 1 Điều này, người sử dụng lao động bố trí cho người lao động các đợt nghỉ giải lao và ghi vào nội quy lao động.
```

`id=lao-036-1` · độ phủ từ khoá 60%

---

## 56. Công ty tôi có bắt buộc phải tổ chức họp định kỳ với đại diện người lao động để bàn chuyện công ty không?

**145/2020/NĐ-CP > Điều 39**

```
Điều 39. Tổ chức đối thoại định kỳ tại nơi làm việc
1. Người sử dụng lao động có trách nhiệm phối hợp với tổ chức đại diện người lao động tại cơ sở, nhóm đại diện đối thoại của người lao động tổ chức đối thoại định kỳ theo quy định tại điểm a khoản 2 Điều 63 của Bộ luật Lao động và quy chế dân chủ ở cơ sở tại nơi làm việc.
2. Thành phần tham gia đối thoại định kỳ là đại diện hai bên theo quy định tại khoản 3 Điều 38 Nghị định này. Thời gian, địa điểm, cách thức tổ chức đối thoại định kỳ do hai bên sắp xếp phù hợp với điều kiện thực tế và theo quy chế dân chủ ở cơ sở tại nơi làm việc.
3. Chậm nhất 05 ngày làm việc trước ngày bắt đầu tổ chức đối thoại định kỳ, các bên có trách nhiệm gửi nội dung đối thoại cho bên tham gia đối thoại.
4. Đối thoại định kỳ chỉ được tiến hành khi bên người sử dụng lao động có sự tham gia của người đại diện theo pháp luật hoặc người được ủy quyền và bên người lao động có sự tham gia của trên 70% tổng số thành viên đại diện quy định tại khoản 3 Điều 38 Nghị định này. Diễn biến đối thoại phải được ghi thành biên bản và có chữ ký của người đại diện theo pháp l
```

`id=lao-037-0` · độ phủ từ khoá 69%

---

## 57. Nếu công ty tổ chức họp với đại diện người lao động thì cần có bao nhiêu người đại diện của chúng tôi tham gia thì cuộc họp mới hợp lệ?

**145/2020/NĐ-CP > Điều 39**

```
Điều 39. Tổ chức đối thoại định kỳ tại nơi làm việc
1. Người sử dụng lao động có trách nhiệm phối hợp với tổ chức đại diện người lao động tại cơ sở, nhóm đại diện đối thoại của người lao động tổ chức đối thoại định kỳ theo quy định tại điểm a khoản 2 Điều 63 của Bộ luật Lao động và quy chế dân chủ ở cơ sở tại nơi làm việc.
2. Thành phần tham gia đối thoại định kỳ là đại diện hai bên theo quy định tại khoản 3 Điều 38 Nghị định này. Thời gian, địa điểm, cách thức tổ chức đối thoại định kỳ do hai bên sắp xếp phù hợp với điều kiện thực tế và theo quy chế dân chủ ở cơ sở tại nơi làm việc.
3. Chậm nhất 05 ngày làm việc trước ngày bắt đầu tổ chức đối thoại định kỳ, các bên có trách nhiệm gửi nội dung đối thoại cho bên tham gia đối thoại.
4. Đối thoại định kỳ chỉ được tiến hành khi bên người sử dụng lao động có sự tham gia của người đại diện theo pháp luật hoặc người được ủy quyền và bên người lao động có sự tham gia của trên 70% tổng số thành viên đại diện quy định tại khoản 3 Điều 38 Nghị định này. Diễn biến đối thoại phải được ghi thành biên bản và có chữ ký của người đại diện theo pháp l
```

`id=lao-037-1` · độ phủ từ khoá 67%

---

## 58. Tôi muốn làm nội quy cho công ty thì cần chuẩn bị những giấy tờ gì để nộp lên cơ quan có thẩm quyền? ⚠️ độ phủ từ khoá thấp — kiểm kỹ

**45/2019/QH14 > Điều 120**

```
Điều 120. Hồ sơ đăng ký nội quy lao động Hồ sơ đăng ký nội quy lao động bao gồm:
1. Văn bản đề nghị đăng ký nội quy lao động;
2. Nội quy lao động;
3. Văn bản góp ý của tổ chức đại diện người lao động tại cơ sở đối với nơi có tổ chức đại diện người lao động tại cơ sở;
4. Các văn bản của người sử dụng lao động có quy định liên quan đến kỷ luật lao động và trách nhiệm vật chất (nếu có).
```

`id=lao-039-0` · độ phủ từ khoá 21%

---

## 59. Nếu công ty tôi có công đoàn thì khi làm nội quy có cần xin ý kiến của họ không? ⚠️ độ phủ từ khoá thấp — kiểm kỹ

**45/2019/QH14 > Điều 120**

```
Điều 120. Hồ sơ đăng ký nội quy lao động Hồ sơ đăng ký nội quy lao động bao gồm:
1. Văn bản đề nghị đăng ký nội quy lao động;
2. Nội quy lao động;
3. Văn bản góp ý của tổ chức đại diện người lao động tại cơ sở đối với nơi có tổ chức đại diện người lao động tại cơ sở;
4. Các văn bản của người sử dụng lao động có quy định liên quan đến kỷ luật lao động và trách nhiệm vật chất (nếu có).
```

`id=lao-039-1` · độ phủ từ khoá 25%

---

## 60. Công ty tôi không cho cán bộ công đoàn cấp trên vào làm việc để hướng dẫn anh em thành lập công đoàn thì có bị phạt không?

**12/2022/NĐ-CP > Điều 35**

```
Điều 35. Vi phạm quy định về bảo đảm thực hiện quyền của tổ chức đại diện người lao động tại cơ sở
1. Phạt tiền từ 3.000.000 đồng đến 5.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không bố trí thời gian cho thành viên ban lãnh đạo của tổ chức đại diện người lao động tại cơ sở để thực hiện nhiệm vụ của tổ chức đại diện theo quy định tại khoản 2 Điều 176 của Bộ luật Lao động mà vẫn được người sử dụng lao động trả lương;
b) Không cho cán bộ công đoàn cấp trên cơ sở vào tổ chức, doanh nghiệp để tuyên truyền, vận động, hướng dẫn người lao động thành lập, gia nhập hoặc hoạt động công đoàn;
c) Cản trở, gây khó khăn khi người lao động tiến hành các hoạt động hợp pháp nhằm thành lập, gia nhập và tham gia các hoạt động của tổ chức đại diện người lao động tại cơ sở;
d) Không cho thành viên ban lãnh đạo của tổ chức đại diện người lao động tại cơ sở tiếp cận người lao động tại nơi làm việc trong quá trình thực hiện các nhiệm vụ của tổ chức đại diện người lao động tại cơ sở mà không ảnh hưởng đến hoạt động bình thường của người sử dụng lao động.
2. Phạt tiền từ
```

`id=lao-040-0` · độ phủ từ khoá 93%

---

## 61. Nếu công ty tôi đơn phương cho một người trong ban lãnh đạo công đoàn nghỉ việc mà không bàn bạc trước với ban lãnh đạo công đoàn thì có bị phạt không?

**12/2022/NĐ-CP > Điều 35**

```
Điều 35. Vi phạm quy định về bảo đảm thực hiện quyền của tổ chức đại diện người lao động tại cơ sở
1. Phạt tiền từ 3.000.000 đồng đến 5.000.000 đồng đối với người sử dụng lao động có một trong các hành vi sau đây:
a) Không bố trí thời gian cho thành viên ban lãnh đạo của tổ chức đại diện người lao động tại cơ sở để thực hiện nhiệm vụ của tổ chức đại diện theo quy định tại khoản 2 Điều 176 của Bộ luật Lao động mà vẫn được người sử dụng lao động trả lương;
b) Không cho cán bộ công đoàn cấp trên cơ sở vào tổ chức, doanh nghiệp để tuyên truyền, vận động, hướng dẫn người lao động thành lập, gia nhập hoặc hoạt động công đoàn;
c) Cản trở, gây khó khăn khi người lao động tiến hành các hoạt động hợp pháp nhằm thành lập, gia nhập và tham gia các hoạt động của tổ chức đại diện người lao động tại cơ sở;
d) Không cho thành viên ban lãnh đạo của tổ chức đại diện người lao động tại cơ sở tiếp cận người lao động tại nơi làm việc trong quá trình thực hiện các nhiệm vụ của tổ chức đại diện người lao động tại cơ sở mà không ảnh hưởng đến hoạt động bình thường của người sử dụng lao động.
2. Phạt tiền từ
```

`id=lao-040-1` · độ phủ từ khoá 79%

---

## 62. Công ty em mới vào làm, sếp bắt làm việc gấp đôi mọi người mà lương vẫn vậy, có đúng không ạ?

**45/2019/QH14 > Điều 93**

```
Điều 93. Xây dựng thang lương, bảng lương và định mức lao động
1. Người sử dụng lao động phải xây dựng thang lương, bảng lương và định mức lao động làm cơ sở để tuyển dụng, sử dụng lao động, thỏa thuận mức lương theo công việc hoặc chức danh ghi trong hợp đồng lao động và trả lương cho người lao động.
2. Mức lao động phải là mức trung bình bảo đảm số đông người lao động thực hiện được mà không phải kéo dài thời giờ làm việc bình thường và phải được áp dụng thử trước khi ban hành chính thức.
3. Người sử dụng lao động phải tham khảo ý kiến của tổ chức đại diện người lao động tại cơ sở đối với nơi có tổ chức đại diện người lao động tại cơ sở khi xây dựng thang lương, bảng lương và định mức lao động. Thang lương, bảng lương và mức lao động phải được công bố công khai tại nơi làm việc trước khi thực hiện.
```

`id=lao-041-0` · độ phủ từ khoá 36%

---

## 63. Công ty em có bảng lương mới, nhưng em thấy có vẻ không hợp lý, họ có cần hỏi ý kiến mọi người trước khi áp dụng không ạ?

**45/2019/QH14 > Điều 93**

```
Điều 93. Xây dựng thang lương, bảng lương và định mức lao động
1. Người sử dụng lao động phải xây dựng thang lương, bảng lương và định mức lao động làm cơ sở để tuyển dụng, sử dụng lao động, thỏa thuận mức lương theo công việc hoặc chức danh ghi trong hợp đồng lao động và trả lương cho người lao động.
2. Mức lao động phải là mức trung bình bảo đảm số đông người lao động thực hiện được mà không phải kéo dài thời giờ làm việc bình thường và phải được áp dụng thử trước khi ban hành chính thức.
3. Người sử dụng lao động phải tham khảo ý kiến của tổ chức đại diện người lao động tại cơ sở đối với nơi có tổ chức đại diện người lao động tại cơ sở khi xây dựng thang lương, bảng lương và định mức lao động. Thang lương, bảng lương và mức lao động phải được công bố công khai tại nơi làm việc trước khi thực hiện.
```

`id=lao-041-1` · độ phủ từ khoá 57%

---

## 64. Nếu công ty tôi đưa người đi làm việc ở nước ngoài mà không cho họ đi học định hướng trước thì có bị phạt không?

**12/2022/NĐ-CP > Điều 44**

```
Điều 44. Vi phạm quy định về đưa người lao động Việt Nam đi làm việc ở nước ngoài của tổ chức, cá nhân Việt Nam đầu tư ra nước ngoài
1. Phạt tiền từ 500.000 đồng đến 1.500.000 đồng khi có hành vi không báo cáo định kỳ hằng năm theo quy định hoặc không báo cáo đột xuất về tình hình thực hiện đưa người lao động Việt Nam đi làm việc ở nước ngoài theo quy định của pháp luật.
2. Phạt tiền từ 1.500.000 đồng đến 2.500.000 đồng khi có hành vi không cập nhật thông tin về người lao động trên Hệ thống cơ sở dữ liệu về người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng.
3. Phạt tiền từ 5.000.000 đồng đến 10.000.000 đồng khi vi phạm với mỗi người lao động nhưng không quá 100.000.000 đồng khi có một trong các hành vi sau đây:
a) Không tổ chức để người lao động Việt Nam trước khi đi làm việc ở nước ngoài được tham gia khóa học giáo dục định hướng;
b) Không thông tin đầy đủ hoặc không thông tin chính xác hoặc không thông tin rõ ràng về một trong các nội dung: điều kiện làm việc; điều kiện sinh hoạt; quyền lợi; chế độ của người lao động làm việc tại cơ sở sản xuất, kinh doanh hoặc công tr
```

`id=lao-042-0` · độ phủ từ khoá 100%

---

## 65. Công ty tôi đưa lao động đi nước ngoài nhưng không nói rõ cho họ biết về tiền lương, chỗ ở và các quyền lợi khác thì có bị phạt không?

**12/2022/NĐ-CP > Điều 44**

```
Điều 44. Vi phạm quy định về đưa người lao động Việt Nam đi làm việc ở nước ngoài của tổ chức, cá nhân Việt Nam đầu tư ra nước ngoài
1. Phạt tiền từ 500.000 đồng đến 1.500.000 đồng khi có hành vi không báo cáo định kỳ hằng năm theo quy định hoặc không báo cáo đột xuất về tình hình thực hiện đưa người lao động Việt Nam đi làm việc ở nước ngoài theo quy định của pháp luật.
2. Phạt tiền từ 1.500.000 đồng đến 2.500.000 đồng khi có hành vi không cập nhật thông tin về người lao động trên Hệ thống cơ sở dữ liệu về người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng.
3. Phạt tiền từ 5.000.000 đồng đến 10.000.000 đồng khi vi phạm với mỗi người lao động nhưng không quá 100.000.000 đồng khi có một trong các hành vi sau đây:
a) Không tổ chức để người lao động Việt Nam trước khi đi làm việc ở nước ngoài được tham gia khóa học giáo dục định hướng;
b) Không thông tin đầy đủ hoặc không thông tin chính xác hoặc không thông tin rõ ràng về một trong các nội dung: điều kiện làm việc; điều kiện sinh hoạt; quyền lợi; chế độ của người lao động làm việc tại cơ sở sản xuất, kinh doanh hoặc công tr
```

`id=lao-042-1` · độ phủ từ khoá 75%

---

## 66. Đi làm mà em có em bé dưới 1 tuổi, em có được nghỉ thêm giờ nào trong ngày không ạ?

**145/2020/NĐ-CP > Điều 58**

```
Điều 58. Thời giờ được tính vào thời giờ làm việc được hưởng lương
1. Nghỉ giữa giờ quy định khoản 2 Điều 64 Nghị định này.
2. Nghỉ giải lao theo tính chất của công việc.
3. Nghỉ cần thiết trong quá trình lao động đã được tính trong định mức lao động cho nhu cầu sinh lý tự nhiên của con người.
4. Thời giờ nghỉ đối với lao động nữ khi mang thai hoặc nuôi con dưới 12 tháng tuổi, trong thời gian hành kinh theo quy định tại khoản 2 và khoản 4 Điều 137 của Bộ luật Lao động.
5. Thời giờ phải ngừng việc không do lỗi của người lao động.
6. Thời giờ hội họp, học tập, tập huấn do yêu cầu của người sử dụng lao động hoặc được người sử dụng lao động đồng ý.
7. Thời giờ người học nghề, tập nghề trực tiếp hoặc tham gia lao động theo quy định tại khoản 5 Điều 61 của Bộ luật Lao động.
8. Thời giờ mà người lao động là thành viên ban lãnh đạo của tổ chức đại diện người lao động tại cơ sở được sử dụng để thực hiện nhiệm vụ theo quy định tại khoản 2 và khoản 3 Điều 176 của Bộ luật Lao động.
9. Thời giờ khám sức khỏe, khám phát hiện bệnh nghề nghiệp, giám định y khoa để xác định mức độ suy giảm khả năng l
```

`id=lao-043-0` · độ phủ từ khoá 71%

---

## 67. Nếu công ty bắt em đi học lớp nghiệp vụ, thì thời gian đi học đó có được tính là đi làm và có lương không ạ?

**145/2020/NĐ-CP > Điều 58**

```
Điều 58. Thời giờ được tính vào thời giờ làm việc được hưởng lương
1. Nghỉ giữa giờ quy định khoản 2 Điều 64 Nghị định này.
2. Nghỉ giải lao theo tính chất của công việc.
3. Nghỉ cần thiết trong quá trình lao động đã được tính trong định mức lao động cho nhu cầu sinh lý tự nhiên của con người.
4. Thời giờ nghỉ đối với lao động nữ khi mang thai hoặc nuôi con dưới 12 tháng tuổi, trong thời gian hành kinh theo quy định tại khoản 2 và khoản 4 Điều 137 của Bộ luật Lao động.
5. Thời giờ phải ngừng việc không do lỗi của người lao động.
6. Thời giờ hội họp, học tập, tập huấn do yêu cầu của người sử dụng lao động hoặc được người sử dụng lao động đồng ý.
7. Thời giờ người học nghề, tập nghề trực tiếp hoặc tham gia lao động theo quy định tại khoản 5 Điều 61 của Bộ luật Lao động.
8. Thời giờ mà người lao động là thành viên ban lãnh đạo của tổ chức đại diện người lao động tại cơ sở được sử dụng để thực hiện nhiệm vụ theo quy định tại khoản 2 và khoản 3 Điều 176 của Bộ luật Lao động.
9. Thời giờ khám sức khỏe, khám phát hiện bệnh nghề nghiệp, giám định y khoa để xác định mức độ suy giảm khả năng l
```

`id=lao-043-1` · độ phủ từ khoá 80%

---

## 68. Nếu công ty môi giới việc làm ở nước ngoài thu tiền của tôi sai quy định, họ có phải trả lại tiền và lãi cho tôi không?

**12/2022/NĐ-CP > Điều 42 > Khoản 14**

```
14. Biện pháp khắc phục hậu quả
a) Buộc doanh nghiệp dịch vụ cập nhật thông tin về người lao động do doanh nghiệp đưa đi trên Hệ thống cơ sở dữ liệu về người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng theo quy định của pháp luật khi có hành vi vi phạm quy định tại điểm g khoản 1 Điều này;
b) Buộc doanh nghiệp dịch vụ đóng đủ số tiền phải đóng và khoản tiền lãi của số tiền này tính theo mức lãi suất tiền gửi không kỳ hạn cao nhất của các ngân hàng thương mại nhà nước công bố tại thời điểm xử phạt vào Quỹ hỗ trợ việc làm ngoài nước khi có hành vi vi phạm quy định tại khoản 3 Điều này;
c) Buộc doanh nghiệp dịch vụ đóng đủ số tiền người lao động đóng vào Quỹ hỗ trợ việc làm ngoài nước thông qua doanh nghiệp dịch vụ và khoản tiền lãi của số tiền này tính theo mức lãi suất tiền gửi không kỳ hạn cao nhất của các ngân hàng thương mại nhà nước công bố tại thời điểm xử phạt vào Quỹ hỗ trợ việc làm ngoài nước khi có hành vi vi phạm quy định tại khoản 4 Điều này;
d) Buộc doanh nghiệp dịch vụ bồi thường cho người lao động về những thiệt hại do doanh nghiệp, chi nhánh doanh nghiệp gâ
```

`id=lao-044-0` · độ phủ từ khoá 80%

---

## 69. Nếu công ty đưa tôi đi làm việc ở nước ngoài làm tôi bị thiệt hại, họ có phải bồi thường cho tôi không?

**12/2022/NĐ-CP > Điều 42 > Khoản 14**

```
14. Biện pháp khắc phục hậu quả
a) Buộc doanh nghiệp dịch vụ cập nhật thông tin về người lao động do doanh nghiệp đưa đi trên Hệ thống cơ sở dữ liệu về người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng theo quy định của pháp luật khi có hành vi vi phạm quy định tại điểm g khoản 1 Điều này;
b) Buộc doanh nghiệp dịch vụ đóng đủ số tiền phải đóng và khoản tiền lãi của số tiền này tính theo mức lãi suất tiền gửi không kỳ hạn cao nhất của các ngân hàng thương mại nhà nước công bố tại thời điểm xử phạt vào Quỹ hỗ trợ việc làm ngoài nước khi có hành vi vi phạm quy định tại khoản 3 Điều này;
c) Buộc doanh nghiệp dịch vụ đóng đủ số tiền người lao động đóng vào Quỹ hỗ trợ việc làm ngoài nước thông qua doanh nghiệp dịch vụ và khoản tiền lãi của số tiền này tính theo mức lãi suất tiền gửi không kỳ hạn cao nhất của các ngân hàng thương mại nhà nước công bố tại thời điểm xử phạt vào Quỹ hỗ trợ việc làm ngoài nước khi có hành vi vi phạm quy định tại khoản 4 Điều này;
d) Buộc doanh nghiệp dịch vụ bồi thường cho người lao động về những thiệt hại do doanh nghiệp, chi nhánh doanh nghiệp gâ
```

`id=lao-044-1` · độ phủ từ khoá 100%

---

## 70. Một ngày mình phải làm việc bao nhiêu tiếng thì đúng luật?

**45/2019/QH14 > Điều 105**

```
Điều 105. Thời giờ làm việc bình thường
1. Thời giờ làm việc bình thường không quá 08 giờ trong 01 ngày và không quá 48 giờ trong 01 tuần.
2. Người sử dụng lao động có quyền quy định thời giờ làm việc theo ngày hoặc tuần nhưng phải thông báo cho người lao động biết; trường hợp theo tuần thì thời giờ làm việc bình thường không quá 10 giờ trong 01 ngày và không quá 48 giờ trong 01 tuần. Nhà nước khuyến khích người sử dụng lao động thực hiện tuần làm việc 40 giờ đối với người lao động.
3. Người sử dụng lao động có trách nhiệm bảo đảm giới hạn thời gian làm việc tiếp xúc với yếu tố nguy hiểm, yếu tố có hại đúng theo quy chuẩn kỹ thuật quốc gia và pháp luật có liên quan.
```

`id=lao-hand-01` · độ phủ từ khoá 71%

---

## 71. Tôi muốn nghỉ việc thì phải báo cho công ty biết trước bao nhiêu ngày?

**45/2019/QH14 > Điều 35**

```
Điều 35. Quyền đơn phương chấm dứt hợp đồng lao động của người lao động
1. Người lao động có quyền đơn phương chấm dứt hợp đồng lao động nhưng phải báo trước cho người sử dụng lao động như sau:
a) Ít nhất 45 ngày nếu làm việc theo hợp đồng lao động không xác định thời hạn;
b) Ít nhất 30 ngày nếu làm việc theo hợp đồng lao động xác định thời hạn có thời hạn từ 12 tháng đến 36 tháng;
c) Ít nhất 03 ngày làm việc nếu làm việc theo hợp đồng lao động xác định thời hạn có thời hạn dưới 12 tháng;
d) Đối với một số ngành, nghề, công việc đặc thù thì thời hạn báo trước được thực hiện theo quy định của Chính phủ.
2. Người lao động có quyền đơn phương chấm dứt hợp đồng lao động không cần báo trước trong trường hợp sau đây:
a) Không được bố trí theo đúng công việc, địa điểm làm việc hoặc không được bảo đảm điều kiện làm việc theo thỏa thuận, trừ trường hợp quy định tại Điều 29 của Bộ luật này;
b) Không được trả đủ lương hoặc trả lương không đúng thời hạn, trừ trường hợp quy định tại khoản 4 Điều 97 của Bộ luật này;
c) Bị người sử dụng lao động ngược đãi, đánh đập hoặc có lời nói, hành vi nhục mạ,
```

`id=lao-hand-02` · độ phủ từ khoá 75%

---

## 72. Đi làm thêm giờ thì có được trả thêm tiền không, tính thế nào, và công ty được bắt làm thêm tối đa mấy giờ?

**45/2019/QH14 > Điều 107**

```
Điều 107. Làm thêm giờ
1. Thời gian làm thêm giờ là khoảng thời gian làm việc ngoài thời giờ làm việc bình thường theo quy định của pháp luật, thỏa ước lao động tập thể hoặc nội quy lao động.
2. Người sử dụng lao động được sử dụng người lao động làm thêm giờ khi đáp ứng đầy đủ các yêu cầu sau đây:
a) Phải được sự đồng ý của người lao động;
b) Bảo đảm số giờ làm thêm của người lao động không quá 50% số giờ làm việc bình thường trong 01 ngày; trường hợp áp dụng quy định thời giờ làm việc bình thường theo tuần thì tổng số giờ làm việc bình thường và số giờ làm thêm không quá 12 giờ trong 01 ngày; không quá 40 giờ trong 01 tháng;
c) Bảo đảm số giờ làm thêm của người lao động không quá 200 giờ trong 01 năm, trừ trường hợp quy định tại khoản 3 Điều này.
3. Người sử dụng lao động được sử dụng người lao động làm thêm không quá 300 giờ trong 01 năm trong một số ngành, nghề, công việc hoặc trường hợp sau đây:
a) Sản xuất, gia công xuất khẩu sản phẩm hàng dệt, may, da, giày, điện, điện tử, chế biến nông, lâm, diêm nghiệp, thủy sản;
b) Sản xuất, cung cấp điện, viễn thông, lọc dầu; cấp, thoát nướ
```

**45/2019/QH14 > Điều 98**

```
Điều 98. Tiền lương làm thêm giờ, làm việc vào ban đêm
1. Người lao động làm thêm giờ được trả lương tính theo đơn giá tiền lương hoặc tiền lương thực trả theo công việc đang làm như sau:
a) Vào ngày thường, ít nhất bằng 150%;
b) Vào ngày nghỉ hằng tuần, ít nhất bằng 200%;
c) Vào ngày nghỉ lễ, tết, ngày nghỉ có hưởng lương, ít nhất bằng 300% chưa kể tiền lương ngày lễ, tết, ngày nghỉ có hưởng lương đối với người lao động hưởng lương ngày.
2. Người lao động làm việc vào ban đêm thì được trả thêm ít nhất bằng 30% tiền lương tính theo đơn giá tiền lương hoặc tiền lương thực trả theo công việc của ngày làm việc bình thường.
3. Người lao động làm thêm giờ vào ban đêm thì ngoài việc trả lương theo quy định tại khoản 1 và khoản 2 Điều này, người lao động còn được trả thêm 20% tiền lương tính theo đơn giá tiền lương hoặc tiền lương theo công việc làm vào ban ngày của ngày làm việc bình thường hoặc của ngày nghỉ hằng tuần hoặc của ngày nghỉ lễ, tết.
4. Chính phủ quy định chi tiết Điều này.
```

`id=lao-hand-03` · độ phủ từ khoá 70%

---

## 73. Bị công ty cho nghỉ việc mà không có lý do gì thì phải kiện ai để đòi quyền lợi?

**45/2019/QH14 > Điều 41**

```
Điều 41. Nghĩa vụ của người sử dụng lao động khi đơn phương chấm dứt hợp đồng lao động trái pháp luật
1. Phải nhận người lao động trở lại làm việc theo hợp đồng lao động đã giao kết; phải trả tiền lương, đóng bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp trong những ngày người lao động không được làm việc và phải trả thêm cho người lao động một khoản tiền ít nhất bằng 02 tháng tiền lương theo hợp đồng lao động. Sau khi được nhận lại làm việc, người lao động hoàn trả cho người sử dụng lao động các khoản tiền trợ cấp thôi việc, trợ cấp mất việc làm nếu đã nhận của người sử dụng lao động. Trường hợp không còn vị trí, công việc đã giao kết trong hợp đồng lao động mà người lao động vẫn muốn làm việc thì hai bên thỏa thuận để sửa đổi, bổ sung hợp đồng lao động. Trường hợp vi phạm quy định về thời hạn báo trước quy định tại khoản 2 Điều 36 của Bộ luật này thì phải trả một khoản tiền tương ứng với tiền lương theo hợp đồng lao động trong những ngày không báo trước.
2. Trường hợp người lao động không muốn tiếp tục làm việc thì ngoài khoản tiền phải trả quy định tại khoản 1 Điều này ngườ
```

**45/2019/QH14 > Điều 187**

```
Điều 187. Thẩm quyền giải quyết tranh chấp lao động cá nhân Cơ quan, tổ chức, cá nhân có thẩm quyền giải quyết tranh chấp lao động cá nhân bao gồm:
1. Hòa giải viên lao động;
2. Hội đồng trọng tài lao động;
3. Tòa án nhân dân.
```

`id=lao-hand-04` · độ phủ từ khoá 43%

---

## 74. Lương tối thiểu vùng bây giờ là bao nhiêu một tháng?

**45/2019/QH14 > Điều 91**

```
Điều 91. Mức lương tối thiểu
1. Mức lương tối thiểu là mức lương thấp nhất được trả cho người lao động làm công việc giản đơn nhất trong điều kiện lao động bình thường nhằm bảo đảm mức sống tối thiểu của người lao động và gia đình họ, phù hợp với điều kiện phát triển kinh tế - xã hội.
2. Mức lương tối thiểu được xác lập theo vùng, ấn định theo tháng, giờ.
3. Mức lương tối thiểu được điều chỉnh dựa trên mức sống tối thiểu của người lao động và gia đình họ; tương quan giữa mức lương tối thiểu và mức lương trên thị trường; chỉ số giá tiêu dùng, tốc độ tăng trưởng kinh tế; quan hệ cung, cầu lao động; việc làm và thất nghiệp; năng suất lao động; khả năng chi trả của doanh nghiệp.
4. Chính phủ quy định chi tiết Điều này; quyết định và công bố mức lương tối thiểu trên cơ sở khuyến nghị của Hội đồng tiền lương quốc gia.
```

**293/2025/NĐ-CP > Điều 3**

```
Điều 3. Mức lương tối thiểu
1. Quy định mức lương tối thiểu tháng và mức lương tối thiểu giờ đối với người lao động làm việc cho người sử dụng lao động theo vùng như sau:
2. Danh mục địa bàn vùng I, vùng II, vùng III, vùng IV được quy định tại Phụ lục ban hành kèm theo Nghị định này.
3. Việc áp dụng địa bàn vùng được xác định theo nơi hoạt động của người sử dụng lao động như sau:
a) Người sử dụng lao động hoạt động trên địa bàn thuộc vùng nào thì áp dụng mức lương tối thiểu quy định đối với địa bàn đó.
b) Người sử dụng lao động có đơn vị, chi nhánh hoạt động trên các địa bàn có mức lương tối thiểu khác nhau thì đơn vị, chi nhánh hoạt động ở địa bàn nào, áp dụng mức lương tối thiểu quy định đối với địa bàn đó.
c) Người sử dụng lao động hoạt động trong khu công nghiệp, khu chế xuất, khu công nghệ cao, khu công nghệ số tập trung nằm trên các địa bàn có mức lương tối thiểu khác nhau thì áp dụng theo địa bàn có mức lương tối thiểu cao nhất.
d) Người sử dụng lao động hoạt động trên địa bàn có sự thay đổi tên hoặc chia thì tạm thời áp dụng mức lương tối thiểu quy định đối với địa bàn trước 
```

`id=lao-hand-05` · độ phủ từ khoá 86%

---

## 75. Tôi bị tai nạn khi đang làm việc, công ty có phải lo tiền viện phí và trả lương những ngày tôi nghỉ điều trị không?

**84/2015/QH13 > Điều 38**

```
Điều 38. Trách nhiệm của người sử dụng lao động đối với người lao động bị tai nạn lao động, bệnh nghề nghiệp Người sử dụng lao động có trách nhiệm đối với người lao động bị tai nạn lao động, bệnh nghề nghiệp như sau:
1. Kịp thời sơ cứu, cấp cứu cho người lao động bị tai nạn lao động và phải tạm ứng chi phí sơ cứu, cấp cứu và điều trị cho người lao động bị tai nạn lao động hoặc bệnh nghề nghiệp;
2. Thanh toán chi phí y tế từ khi sơ cứu, cấp cứu đến khi điều trị ổn định cho người bị tai nạn lao động hoặc bệnh nghề nghiệp như sau:
a) Thanh toán phần chi phí đồng chi trả và những chi phí không nằm trong danh mục do bảo hiểm y tế chi trả đối với người lao động tham gia bảo hiểm y tế;
b) Trả phí khám giám định mức suy giảm khả năng lao động đối với những trường hợp kết luận suy giảm khả năng lao động dưới 5% do người sử dụng lao động giới thiệu người lao động đi khám giám định mức suy giảm khả năng lao động tại Hội đồng giám định y khoa;
c) Thanh toán toàn bộ chi phí y tế đối với người lao động không tham gia bảo hiểm y tế;
3. Trả đủ tiền lương cho người lao động bị tai nạn lao động, bệnh 
```

`id=lao-hand-06` · độ phủ từ khoá 88%

---

## 76. Bây giờ bao nhiêu tuổi thì được nghỉ hưu?

**45/2019/QH14 > Điều 169**

```
Điều 169. Tuổi nghỉ hưu
1. Người lao động bảo đảm điều kiện về thời gian đóng bảo hiểm xã hội theo quy định của pháp luật về bảo hiểm xã hội được hưởng lương hưu khi đủ tuổi nghỉ hưu.
2. Tuổi nghỉ hưu của người lao động trong điều kiện lao động bình thường được điều chỉnh theo lộ trình cho đến khi đủ 62 tuổi đối với lao động nam vào năm 2028 và đủ 60 tuổi đối với lao động nữ vào năm 2035. Kể từ năm 2021, tuổi nghỉ hưu của người lao động trong điều kiện lao động bình thường là đủ 60 tuổi 03 tháng đối với lao động nam và đủ 55 tuổi 04 tháng đối với lao động nữ; sau đó, cứ mỗi năm tăng thêm 03 tháng đối với lao động nam và 04 tháng đối với lao động nữ.
3. Người lao động bị suy giảm khả năng lao động; làm nghề, công việc đặc biệt nặng nhọc, độc hại, nguy hiểm; làm nghề, công việc nặng nhọc, độc hại, nguy hiểm; làm việc ở vùng có điều kiện kinh tế - xã hội đặc biệt khó khăn có thể nghỉ hưu ở tuổi thấp hơn nhưng không quá 05 tuổi so với quy định tại khoản 2 Điều này tại thời điểm nghỉ hưu, trừ trường hợp pháp luật có quy định khác.
4. Người lao động có trình độ chuyên môn, kỹ thuật cao và 
```

**135/2020/NĐ-CP > Điều 4**

```
Điều 4. Tuổi nghỉ hưu trong điều kiện lao động bình thường Tuổi nghỉ hưu của người lao động trong điều kiện lao động bình thường theo khoản 2 Điều 169 của Bộ luật Lao động được quy định cụ thể như sau:
1. Kể từ ngày 01 tháng 01 năm 2021, tuổi nghỉ hưu của người lao động trong điều kiện lao động bình thường là đủ 60 tuổi 03 tháng đối với lao động nam và đủ 55 tuổi 04 tháng đối với lao động nữ; sau đó, cứ mỗi năm tăng thêm 03 tháng đối với lao động nam cho đến khi đủ 62 tuổi vào năm 2028 và cứ mỗi năm tăng thêm 04 tháng đối với lao động nữ cho đến khi đủ 60 tuổi vào năm 2035.
2. Lộ trình điều chỉnh tuổi nghỉ hưu của người lao động quy định tại khoản 1 Điều này được thực hiện theo bảng dưới đây: Việc đối chiếu tháng, năm sinh của người lao động tương ứng với tuổi nghỉ hưu quy định tại khoản này theo Phụ lục I ban hành kèm theo Nghị định này.
```

`id=lao-hand-07` · độ phủ từ khoá 60%

---

## 77. Công ty bắt làm thêm giờ liên tục, một tháng tối đa được bắt làm thêm bao nhiêu tiếng?

**18/2021/TT-BLĐTBXH > Điều 6**

```
Điều 6. Giới hạn giờ làm việc tiêu chuẩn hằng ngày và giờ làm thêm
1. Tổng số giờ làm việc tiêu chuẩn và số giờ làm thêm trong một ngày không quá 12 giờ.
2. Giới hạn giờ làm việc tiêu chuẩn và giờ làm thêm theo tuần, tháng được quy định như sau:
a) Tổng số giờ làm việc tiêu chuẩn và số giờ làm thêm trong một tuần không quá 72 giờ.
b) Tổng số giờ làm thêm trong một tháng không quá 40 giờ.
c) Người sử dụng lao động quyết định lựa chọn áp dụng quy định tại điểm a hoặc quy định tại điểm b khoản này, ghi vào kế hoạch thời giờ làm việc, thời giờ nghỉ ngơi trong năm quy định tại khoản 2, Điều 8 Thông tư này.
3. Tổng số giờ làm thêm trong một năm đối với mỗi người lao động không quá 300 giờ.
```

`id=lao-hand-08` · độ phủ từ khoá 40%

---
