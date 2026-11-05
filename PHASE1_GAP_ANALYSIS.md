# Phase 1 — trạng thái triển khai và khoảng trống

**Cập nhật:** 05/11/2026. Đối chiếu `doc/HRA_PRD.md` và `doc/HRA_Phase1_Architecture.md`. “Có trong mã” không đồng nghĩa đã triển khai hoặc nghiệm thu trên Supabase thật.

| ID | Yêu cầu | Trạng thái hiện tại |
|---|---|---|
| F1.01 | Vị trí, JD, Hiring Manager | Có tạo vị trí/JD, gán HM, chỉnh tên và mở/tạm dừng/đóng. Chưa có UI chỉnh sửa/lưu phiên bản JD sau khi tạo. |
| F1.02 | Đề xuất, duyệt HR + HM, trọng số | Có nháp, sửa nội dung/trọng số từng tiêu chí và hai nhóm (tổng 100%), HR duyệt trước, HM được gán duyệt/yêu cầu sửa, lịch sử và khóa bản đã duyệt. Hai bước kiểm tra **vai trò**, chưa bắt buộc hai tài khoản khác nhau. Chưa kiểm thử LLM thật. |
| F1.03 | Upload batch | Có giới hạn 50 file, 10 MB/file, 250 MB/lô, kiểm tra chữ ký PDF/DOCX, báo tệp không hợp lệ và tiến trình. |
| F1.04 | Trích xuất, OCR, sửa profile | Có code PDF text/DOCX và OCR PDF scan qua Tesseract tiếng Anh + Poppler; đã kiểm thử pipeline DOCX giả lập, **chưa kiểm thử OCR scan thật**. Lỗi xử lý được đánh dấu cần HR xem; chưa có UI sửa profile trích xuất. |
| F1.05 | Đánh giá và dẫn chứng | Có bốn mức; trích dẫn phải khớp văn bản sau chuẩn hóa khoảng trắng/chữ hoa-thường, số trang PDF được kiểm tra. DOCX không có số trang đáng tin cậy. Thiếu bằng chứng/độ tin cậy thấp đưa về `UNCLEAR`. |
| F1.06 | Điểm và ranking trong vị trí | Có tính điểm tất định theo trọng số của phiên bản đã duyệt, cảnh báo độ phủ thấp, ranking theo nhóm bắt buộc rồi điểm. Độ phủ hiện dựa trên trọng số có bằng chứng đáng tin cậy; quy đổi điểm và policy runtime cần HR/HM xác nhận trước pilot. |
| F1.07 | Cảnh báo trùng | Có cảnh báo trong cùng vị trí dựa trên email/số điện thoại trích xuất bằng regex; không tự gộp/xóa. Cần kiểm thử độ chính xác trên tập dữ liệu được phép. |
| F1.08 | Tám trạng thái và lịch sử | HR cập nhật theo luồng hợp lệ, lý do bắt buộc khi loại, có lịch sử/reason/note. AI không tự đổi trạng thái tuyển dụng. |
| F1.09 | Chia sẻ/feedback shortlist | Có chia sẻ cho HM được gán, tùy chọn xem CV, feedback và thu hồi; HM không được xem CV/evidence khi chỉ nhận tóm tắt. Chưa có ghi chú nội bộ HR riêng. |
| F1.10 | RBAC, audit, retention | RBAC backend và các thao tác audit chính đã được kiểm thử cục bộ, gồm thu hồi assignment/share. Migration 00003 đã áp dụng vào project được kết nối; các quyền direct đã được xác minh, chưa kiểm thử toàn bộ Supabase E2E. Audit chưa bất biến; chưa có UI/workflow xác nhận xóa/retention 12 tháng. |
| F1.11 | Cấu hình AI và bảo vệ dữ liệu | Mặc định giới hạn endpoint private; Admin UI chỉ đọc, thay cấu hình bằng env/restart. Chưa có quản lý cấu hình runtime qua UI, egress enforcement, hoặc bộ lọc nhạy cảm/anti-bias hoàn chỉnh. CV text vẫn được gửi tới model đã cấu hình. |
| F1.12 | Việt–Anh | UI hiện chủ yếu tiếng Việt, chưa có chuyển ngôn ngữ/i18n đầy đủ. |
| F1.13 | Dashboard | Số liệu lấy từ PostgreSQL theo quyền, đếm hồ sơ một lần và dùng assessment hoàn tất mới nhất. Tỷ lệ override/thời gian xử lý chưa đủ dữ liệu đáng tin cậy nên trả `null`, không tạo số giả. |

## Các mục ưu tiên trong đợt này

- **#5:** Dual approval có phân vai, khóa phiên bản và ghi lịch sử; trọng số nhóm có thể điều chỉnh trong bản nháp.
- **#7:** Polling upload, tự chạy đánh giá/ranking sau khi xử lý thành công và khôi phục theo dõi khi quay lại trang. Queue chưa khôi phục an toàn sau crash.
- **#9:** Form HM phản hồi shortlist và HR thu hồi chia sẻ.
- **#10:** Chuyển trạng thái hợp lệ trong 8 trạng thái, ghi lý do/lịch sử.
- **#11:** Dashboard, tổng số theo vị trí và nhãn tiêu chí đọc dữ liệu thật; không hiển thị số cố định.
- UI mobile có điều hướng và các danh sách vị trí, ranking, shortlist dạng thẻ; trạng thái loading/lỗi/cảnh báo rõ hơn.

## Kiểm thử và công việc còn lại

Kiểm thử hiện tại dùng database PostgreSQL cục bộ dùng một lần và LLM giả lập; có integration cho upload DOCX → đánh giá → ranking, phân quyền HR/HM/HR Lead, trọng số, trạng thái, shortlist, thu hồi và grant sau migration. Build/lint/typecheck frontend và smoke trình duyệt desktop/mobile đã chạy với dữ liệu giả. Đã áp dụng và kiểm tra quyền migration 00003 trên project được kết nối; chưa kiểm thử Supabase/LLM/OCR thật đầu-cuối hoặc Docker.

Trước khi coi Phase 1 hoàn tất theo PRD cần xử lý/ra quyết định cho các khoảng trống trong bảng, triển khai và kiểm tra bảo mật trên staging, đánh giá chất lượng AI và nhận phê duyệt nghiệp vụ. Không sử dụng dữ liệu ứng viên thật trong bản preview/thử nghiệm. Chi tiết vận hành và migration: [DEPLOYMENT.md](DEPLOYMENT.md).
