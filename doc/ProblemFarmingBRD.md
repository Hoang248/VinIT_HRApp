Dưới đây là checklist câu hỏi để trao đổi với các bộ phận trước khi hoàn thiện PRD.

## Cơ sở đề xuất để thảo luận

Checklist này giả định sản phẩm MVP là **trợ lý giúp HR tải CV theo lô, đối chiếu từng hồ sơ với tiêu chí tuyển dụng và xem bằng chứng trong CV**. HR vẫn tự rà soát và quyết định trạng thái ứng viên.

Để khởi đầu an toàn, đề xuất MVP **chưa tính điểm tổng, chưa xếp hạng và không tự động loại ứng viên**. Đây là định hướng để các bên xác nhận hoặc điều chỉnh, chưa phải yêu cầu đã được phê duyệt.

**P0** = cần có câu trả lời hoặc quyết định trước khi chốt PRD.  
**P1** = có thể đưa vào backlog hoặc ghi thành giả định có người chịu trách nhiệm xác minh.

---

# 1. Câu hỏi cần chốt trước khi khóa PRD

1. **Bài toán ưu tiên là gì?** Giảm thời gian đọc CV, xử lý được nhiều CV hơn, tăng tính nhất quán hay giảm nguy cơ bỏ sót ứng viên phù hợp?
2. **Ai là người dùng chính?** Recruiter, HR Lead, Hiring Manager hay nhiều nhóm cùng sử dụng?
3. **Nhóm vị trí nào sẽ tham gia pilot?** Vì sao chọn các vị trí đó?
4. **CV đến từ những kênh nào và hiện được quản lý ở đâu?** Có ATS hoặc hệ thống nào cần kết nối không?
5. **Tiêu chí sàng lọc do ai xây dựng và ai phê duyệt?**
6. **Hệ thống cần hiển thị kết quả matching như thế nào?** Đặc biệt cần phân biệt “chưa tìm thấy bằng chứng” với “có bằng chứng chưa đáp ứng”.
7. **Có thống nhất MVP không tính điểm tổng, không xếp hạng và không tự động loại ứng viên không?**
8. **Định dạng và ngôn ngữ CV nào bắt buộc phải hỗ trợ trong pilot?**
9. **Dữ liệu CV được lưu và xử lý ở đâu?** Có được dùng dịch vụ AI/OCR của bên ngoài không?
10. **Thành công của pilot được đo bằng chỉ số nào?** Baseline hiện tại là bao nhiêu?
11. **MVP gồm những chức năng nào, chức năng nào để giai đoạn sau?**
12. **Ai là người có quyền quyết định cuối cùng khi các bộ phận chưa thống nhất?**

---

# 2. Câu hỏi theo từng bộ phận

## A. Sponsor, PO và lãnh đạo HR — mục tiêu, phạm vi, ưu tiên

**Mục tiêu:** Thống nhất sản phẩm giải quyết vấn đề gì, MVP đến đâu và thế nào là thành công.

- Trong các vấn đề hiện tại, đâu là vấn đề cần ưu tiên giải quyết trước?
- Kết quả mong muốn sau khi triển khai là gì? Ví dụ: giảm thời gian HR rà soát, rút ngắn thời gian lập shortlist, tăng tính nhất quán.
- “CV chất lượng” hoặc “shortlist tốt” được hiểu thế nào? Có chỉ số hoặc ví dụ thực tế để minh họa không?
- Mục tiêu nào là **chỉ số thành công chính**, mục tiêu nào là chỉ số bổ trợ?
- Các bên có đồng ý rằng MVP chỉ **hỗ trợ HR**, không đưa ra quyết định tuyển dụng thay con người không?
- Có đồng ý chưa dùng điểm tổng/xếp hạng ứng viên trong MVP không? Nếu không, lý do và cách kiểm soát rủi ro là gì?
- Nhóm vị trí nào sẽ nằm trong pilot? Những nhóm nào rõ ràng nằm ngoài phạm vi?
- MVP cần giải quyết bước nào của quy trình: tiếp nhận CV, sàng lọc, lập shortlist hay theo dõi đến phỏng vấn?
- Những chức năng nào bắt buộc có trong bản đầu tiên? Những chức năng nào chấp nhận để sau?
- Có giới hạn về ngân sách, thời gian, hạ tầng hoặc nguồn lực triển khai không?
- Ai là người phê duyệt phạm vi cuối cùng và ai ký nghiệm thu sản phẩm?
- Nếu chưa đủ dữ liệu để chốt một yêu cầu, ai là owner và thời hạn xác minh là khi nào?

**Đầu ra cần có:** Mục tiêu sản phẩm, nhóm người dùng, nhóm pilot, phạm vi MVP, ưu tiên và cách ra quyết định.

---

## B. Recruiter/HR trực tiếp xử lý CV — quy trình và nhu cầu sử dụng

**Mục tiêu:** Hiểu công việc thực tế và xác định sản phẩm cần hỗ trợ thao tác nào.

- Quy trình hiện tại từ khi nhận CV đến khi tạo shortlist gồm những bước nào?
- Mỗi bước do ai thực hiện và đang dùng công cụ nào?
- CV đến từ những nguồn nào: ATS, email, website tuyển dụng, referral hay nguồn khác?
- Trung bình và cao điểm có bao nhiêu CV theo từng vị trí hoặc đợt tuyển?
- Hiện HR mất bao lâu cho từng công đoạn? Số liệu này đã được đo hay mới là ước lượng?
- Những thao tác nào tốn thời gian nhất hoặc thường phải làm lặp lại?
- Các trường thông tin nào cần trích xuất để hỗ trợ sàng lọc? Trường nào chỉ cần để liên hệ ứng viên?
- Có thực sự cần trích xuất địa chỉ đầy đủ, ảnh hoặc các thông tin cá nhân khác không?
- CV thường dùng định dạng nào: PDF, DOCX, CV scan, ảnh hay định dạng khác?
- Tỷ lệ CV tiếng Việt/tiếng Anh và CV scan có đáng kể không?
- HR muốn xử lý CV theo lô như thế nào: tải nhiều file một lần, gán vào vị trí, xem tiến độ, xử lý file lỗi?
- Khi hệ thống không đọc được CV hoặc trích xuất không chắc chắn, HR muốn xử lý ra sao?
- Một ứng viên có thể ứng tuyển nhiều vị trí hoặc gửi nhiều phiên bản CV không?
- “CV trùng” cần phát hiện là trùng file, trùng ứng viên trong cùng vị trí hay trùng ứng viên giữa nhiều vị trí?
- HR cần các trạng thái hồ sơ nào? Ví dụ: Mới nhận, Đang xem xét, Shortlist, Không tiếp tục, Tạm giữ.
- Khi chuyển hồ sơ sang “Không tiếp tục”, có cần chọn lý do từ danh sách không? Lý do nào phù hợp?
- HR cần lọc danh sách theo tiêu chí nào: vị trí, trạng thái, thời gian nhận, tiêu chí bắt buộc hay hồ sơ cần kiểm tra?
- Có cần chia sẻ shortlist cho Hiring Manager trong hệ thống không, hay quy trình hiện tại dùng email/tài liệu khác?
- Có thể cung cấp ví dụ CV đã được HR đánh giá phù hợp, chưa phù hợp và khó đánh giá để làm dữ liệu kiểm thử không?

**Đầu ra cần có:** Quy trình hiện tại, quy trình mục tiêu, nhu cầu màn hình/chức năng, danh sách trạng thái và các trường hợp ngoại lệ.

---

## C. Hiring Manager — tiêu chí tuyển dụng và phản hồi shortlist

**Mục tiêu:** Làm rõ ai xác định “phù hợp với vị trí” và bằng chứng nào có giá trị.

- Ai là người đề xuất tiêu chí sàng lọc cho từng vị trí: HR, Hiring Manager hay hai bên cùng làm?
- Ai có quyền phê duyệt tiêu chí trước khi bắt đầu sàng lọc?
- Các tiêu chí bắt buộc và tiêu chí ưu tiên được định nghĩa thế nào?
- Với từng tiêu chí, bằng chứng nào trong CV được xem là đủ? Có ví dụ cụ thể không?
- Bằng cấp, chứng chỉ hoặc kinh nghiệm tương đương có được chấp nhận không?
- Nếu CV không đề cập tiêu chí, có cần xem là “chưa rõ/chưa tìm thấy bằng chứng” để HR xác minh không?
- Nếu thông tin trong CV mơ hồ hoặc mâu thuẫn, ai là người quyết định cách xử lý?
- Có tiêu chí nào thường được ghi trong JD nhưng chưa đủ rõ để sàng lọc không?
- Có tiêu chí nào không được phép dùng vì không liên quan trực tiếp đến công việc không?
- Hiring Manager cần xem những gì: CV gốc, tiêu chí, bằng chứng trích dẫn, ghi chú HR hay trạng thái hồ sơ?
- Hiring Manager chỉ nên xem shortlist hay cần xem cả các hồ sơ khác?
- Hiring Manager sẽ phản hồi shortlist bằng cách nào và trong thời gian bao lâu?
- Khi không đồng ý với shortlist, cần ghi lý do hoặc tiêu chí cần rà soát lại không?
- Bộ tiêu chí có được tái sử dụng làm mẫu cho các vị trí tương tự không? Ai quản lý và cập nhật mẫu?

**Đầu ra cần có:** Cách tạo và duyệt rubric, định nghĩa tiêu chí, quyền xem và quy trình phản hồi shortlist.

---

## D. HR Lead — quy trình quản trị, báo cáo và triển khai sử dụng

**Mục tiêu:** Thống nhất cách quản lý quy trình và theo dõi hiệu quả sản phẩm.

- Có cần chuẩn hóa quy trình sàng lọc giữa các recruiter không? Phần nào cần thống nhất, phần nào được tùy theo vị trí?
- Ai quản lý mẫu tiêu chí, trạng thái hồ sơ và lý do không tiếp tục?
- Có cần lưu lịch sử thay đổi JD, tiêu chí và trạng thái ứng viên không?
- HR Lead cần xem những báo cáo nào để quản lý khối lượng và tiến độ?
- Các chỉ số như thời gian xử lý, tỷ lệ shortlist, hồ sơ lỗi hoặc số lần HR sửa kết quả được định nghĩa thế nào?
- Có định dùng dữ liệu báo cáo để đánh giá hiệu suất cá nhân HR không? Nếu có, cần cơ chế giải thích và tránh hiểu sai chỉ số ra sao?
- HR cần đào tạo hoặc hướng dẫn gì trước khi sử dụng sản phẩm?
- Ai tiếp nhận câu hỏi, lỗi hoặc đề xuất cải tiến từ người dùng?
- Pilot sẽ có bao nhiêu recruiter, bao nhiêu vị trí và kéo dài bao lâu?
- Điều kiện nào để kết luận pilot đạt yêu cầu và được mở rộng?

**Đầu ra cần có:** Quy tắc quản trị, nhu cầu báo cáo, chủ sở hữu vận hành và kế hoạch pilot.

---

## E. IT/Security — hệ thống, tích hợp và yêu cầu kỹ thuật

**Mục tiêu:** Xác định sản phẩm cần hoạt động trong môi trường nào và có thể đáp ứng các ràng buộc kỹ thuật nào.

- VinUni đang sử dụng ATS, hệ thống quản lý tài khoản hoặc công cụ lưu trữ tuyển dụng nào?
- MVP có cần tích hợp với ATS, email, SSO hoặc hệ thống nội bộ không?
- Nếu chưa tích hợp, quy trình tải CV và xuất dữ liệu thủ công có chấp nhận được trong pilot không?
- Hệ thống được phép triển khai ở hạ tầng/cloud nào? Dữ liệu được phép lưu ở khu vực nào?
- Có giới hạn nào về việc dùng nhà cung cấp bên ngoài cho lưu trữ, OCR hoặc AI không?
- Người dùng cần đăng nhập qua hệ thống nào? Có cần SSO không?
- Phân quyền cần giới hạn theo vai trò, phòng ban, vị trí tuyển dụng hay kết hợp các yếu tố này?
- Những thao tác nào cần ghi log: xem, sửa, tải, chia sẻ, xuất hoặc xóa CV?
- Có yêu cầu cụ thể nào về mã hóa, sao lưu, khôi phục dữ liệu, thời gian phục hồi sau sự cố và thời gian lưu log không?
- Cần hỗ trợ bao nhiêu người dùng đồng thời và bao nhiêu CV trong một batch/ngày?
- Thời gian xử lý chấp nhận được cho một CV hoặc một batch là bao nhiêu?
- File tải lên cần được kiểm tra bảo mật hoặc hạn chế loại file nào?
- Trình duyệt, thiết bị và chuẩn giao diện nội bộ nào cần hỗ trợ?
- Có yêu cầu kiểm thử bảo mật hoặc quy trình phê duyệt trước khi pilot không?

**Đầu ra cần có:** Danh sách hệ thống liên quan, yêu cầu tích hợp, ràng buộc hạ tầng, bảo mật và hiệu năng.

---

## F. Legal/Privacy/Compliance — dữ liệu ứng viên và việc sử dụng AI

**Mục tiêu:** Xác nhận sản phẩm được phép xử lý dữ liệu nào, vì mục đích gì và theo điều kiện nào.

- Mục đích thu thập và xử lý CV trong hệ thống cần được mô tả như thế nào?
- Ứng viên được thông báo về việc lưu trữ và sử dụng CV ra sao?
- Dữ liệu nào thực sự cần thiết cho sàng lọc? Dữ liệu nào nên tránh thu thập hoặc không dùng để matching?
- Thời hạn lưu CV, dữ liệu trích xuất và kết quả matching là bao lâu? Chính sách nào làm căn cứ?
- Nếu ứng viên yêu cầu xóa hoặc chỉnh sửa dữ liệu, quy trình và người xử lý là ai?
- Có được phép chia sẻ CV cho Hiring Manager hoặc nhà cung cấp dịch vụ không? Trong điều kiện nào?
- Có hạn chế về chuyển dữ liệu ra ngoài tổ chức hoặc ra ngoài quốc gia không?
- Nếu dùng dịch vụ AI/OCR bên ngoài, cần điều kiện gì về lưu trữ, truy cập, xóa dữ liệu và việc nhà cung cấp sử dụng dữ liệu?
- Sản phẩm có được phép tự động đưa ra quyết định ảnh hưởng đến trạng thái ứng viên không? Đề xuất MVP là không; cần xác nhận.
- Có cần đánh giá hoặc kiểm tra nguy cơ thiên lệch của tiêu chí hay kết quả matching không?
- Có cần thông tin bổ sung cho ứng viên khi hệ thống AI hỗ trợ quá trình sàng lọc không?
- Có yêu cầu riêng nào về xử lý dữ liệu nhạy cảm, audit hoặc báo cáo sự cố không?

**Đầu ra cần có:** Các điều kiện xử lý dữ liệu, quy tắc lưu/xóa, giới hạn nhà cung cấp và yêu cầu kiểm soát rủi ro. Việc diễn giải quy định cụ thể do bộ phận có thẩm quyền xác nhận.

---

## G. Data/AI/Engineering — chất lượng trích xuất và matching

**Mục tiêu:** Xác định đầu vào nào cần hỗ trợ, kết quả cần giải thích ra sao và làm thế nào kiểm chứng chất lượng.

- Có tập CV mẫu được phép dùng để thử nghiệm không? Tập này có đại diện cho các nhóm vị trí, ngôn ngữ và định dạng thực tế không?
- Các trường nào cần trích xuất trong MVP? Trường nào có thể để HR nhập hoặc xác nhận thủ công?
- Hệ thống cần chỉ ra bằng chứng trong CV ở mức nào: trích dẫn, trang, mục hay vị trí cụ thể?
- Làm thế nào phân biệt “có bằng chứng đáp ứng”, “một phần”, “chưa tìm thấy” và “có bằng chứng chưa đáp ứng”?
- Khi CV thiếu thông tin, dùng thuật ngữ không phổ biến hoặc có thông tin mâu thuẫn, kết quả cần hiển thị ra sao?
- Trường hợp nào phải chuyển sang HR kiểm tra thủ công?
- Có cần HR sửa kết quả trích xuất hoặc đánh giá matching không? Những thay đổi đó được lưu và sử dụng thế nào?
- Chất lượng trích xuất được đo theo từng trường hay theo một chỉ số tổng? Ai chuẩn bị dữ liệu chuẩn để so sánh?
- Làm thế nào kiểm tra trường hợp hệ thống đánh giá thấp một ứng viên phù hợp? Có cần ưu tiên kiểm tra nguy cơ bỏ sót này không?
- Hệ thống cần lưu phiên bản của tiêu chí, CV và kết quả matching ra sao để có thể kiểm tra lại?
- Khi thay đổi mô hình hoặc cách matching, cần kiểm thử và phê duyệt lại thế nào?
- CV hoặc tệp tải lên có thể chứa nội dung không đáng tin cậy; cần kiểm soát cách hệ thống tiếp nhận và sử dụng nội dung đó ra sao?
- Có đồng ý rằng hệ thống không được tự suy diễn thông tin không có trong CV và không được dùng CV để huấn luyện khi chưa được phê duyệt không?

**Đầu ra cần có:** Phạm vi dữ liệu, cách trình bày bằng chứng, trường hợp cần xử lý thủ công và phương pháp kiểm thử chất lượng.

---

## H. Vận hành và hỗ trợ người dùng

**Mục tiêu:** Đảm bảo sản phẩm dùng được trong quy trình thực tế, kể cả khi có lỗi.

- Khi hệ thống xử lý CV lỗi hoặc chậm, HR tiếp tục quy trình thủ công như thế nào?
- Ai là đầu mối hỗ trợ người dùng trong pilot và sau khi triển khai?
- Có cần gửi thông báo khi xử lý xong, khi có file lỗi hoặc khi Hiring Manager cần phản hồi không?
- Người dùng cần được hướng dẫn những gì để không xem gợi ý của hệ thống là quyết định cuối cùng?
- Ai chịu trách nhiệm xử lý quyền truy cập mới, người dùng nghỉ việc hoặc thay đổi vị trí phụ trách?
- Những lỗi nào cần được ghi nhận để đội sản phẩm xử lý và theo dõi?

**Đầu ra cần có:** Quy trình dự phòng, đầu mối hỗ trợ, cách hướng dẫn người dùng và xử lý lỗi.

---

# 3. Câu hỏi dùng để chốt tiêu chí nghiệm thu trong PRD

Trước khi hoàn thiện PRD, cần thống nhất cách trả lời các câu hỏi sau:

- Một CV được coi là xử lý thành công khi nào?
- Với một tiêu chí, hệ thống cần cung cấp bằng chứng gì để kết quả được xem là hữu ích?
- Độ chính xác trích xuất được đo theo từng trường nào và trên tập CV nào?
- Cách đo matching có kiểm tra trường hợp **ứng viên phù hợp nhưng hệ thống không tìm thấy bằng chứng** không?
- Ngưỡng xử lý batch và thời gian phản hồi được xác định từ khối lượng thực tế nào?
- Điều kiện phân quyền nào phải được kiểm thử?
- Những thao tác nào bắt buộc phải có audit log?
- Điều kiện nào được xem là đạt pilot, cần chỉnh sửa thêm hoặc phải dừng triển khai?
- Ai là người xác nhận kết quả UAT và phê duyệt đưa vào sử dụng?

Không nên chỉ dùng một con số “độ chính xác 90%” cho toàn sản phẩm nếu chưa thống nhất trường nào được đo, cách tính và tập dữ liệu kiểm thử.

---

# 4. Mẫu ghi nhận câu trả lời trong Discovery

Nên lập decision log để không biến giả định thành yêu cầu đã duyệt:

| Câu hỏi/Quyết định | Đề xuất mặc định | Câu trả lời cuối cùng | Owner | Trạng thái |
|---|---|---|---|---|
| Có dùng điểm tổng trong MVP không? | Không |  | PO + HR | Open |
| Ai duyệt tiêu chí? | Hiring Manager xác nhận |  | HR Lead | Open |
| Thời hạn lưu CV? | Theo chính sách được phê duyệt |  | Legal/HR | Open |
| Có tích hợp ATS trong pilot không? | Chưa tích hợp nếu chưa cần |  | PO + IT | Open |
| Định dạng CV pilot? | PDF/DOCX, xác minh CV scan |  | HR + IT | Open |

Trạng thái nên gồm: **Đã xác nhận / Giả định / Cần quyết định / Ngoài phạm vi**.

## Gợi ý tổ chức các buổi làm việc

Có thể chia thành ba nhóm trao đổi để dễ ra quyết định:

1. **HR Recruiter + HR Lead + Hiring Manager:** quy trình, tiêu chí, trạng thái và cách lập shortlist.
2. **PO/Sponsor + HR Lead:** mục tiêu, phạm vi MVP, nhóm pilot và KPI.
3. **IT/Security + Legal/Compliance + nhóm Data/AI:** dữ liệu, hạ tầng, tích hợp, bảo mật và kiểm thử chất lượng.

PRD có thể vẫn ghi nhận các câu hỏi chưa có lời giải, nhưng mỗi câu cần có **owner, trạng thái và tác động đến phạm vi**. Chỉ nên xem là hoàn thiện khi các quyết định P0 đã được chốt hoặc được ghi rõ là giả định được chấp nhận.