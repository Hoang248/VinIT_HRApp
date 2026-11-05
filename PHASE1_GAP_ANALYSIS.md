# Phase 1 GAP Analysis — Rà soát toàn bộ yêu cầu Phase 1 so với implementation hiện tại

**Date:** 2026-11-05
**Source of truth:** `doc/HRA_PRD.md`, `doc/HRA_Phase1_Architecture.md` (Ma trận F1.01–F1.13)

## Bảng ánh xạ tính năng

| ID | Yêu cầu Phase 1 (PRD/Architecture) | Trạng thái | Ưu tiên fix |
|----|------------------------------------|------------|-------------|
| **F1.01** | Quản lý Vị trí & JD (tạo/mở/tạm dừng/đóng) | ✅ Có (API + UI tạo/chỉnh sửa) | — |
| | Khai báo Hiring Manager khi tạo vị trí | ✅ Có — form tạo vị trí có autocomplete HM; backend tự gán HIRING_MANAGER position_assignment + system role | — |
| **F1.02** | AI đề xuất tiêu chí từ JD | ✅ Có (nút tạo nháp + polling) | — |
| | Dual Approval: HR duyệt quy trình, HM duyệt chuyên môn (ghi rõ role người duyệt) | ⚠️ API có approve nhưng chưa enforce PENDING_HM_APPROVAL workflow; UI chưa phân tách nút theo role | 🔴 Cao |
| | Trọng số Bắt buộc 70% / Ưu tiên 30%, điều chỉnh được | ⚠️ Hiển thị trọng số nhưng UI không cho chỉnh sửa | 🟡 Trung bình (chấp nhận 70/30 fixed cho MVP) |
| | Lưu phiên bản rubric | ✅ Có (version_number) | — |
| **F1.03** | Upload CV theo batch (≤50 file, ≤10MB/file, ≤250MB) | ✅ Có (API + upload dialog) | — |
| **F1.04** | Bóc tách văn bản PDF/DOCX | ✅ Có (worker thực hiện) | — |
| | OCR PDF scan | ❌ Chưa tích hợp Tesseract/OCR | 🟢 Low (ghi chú giới hạn MVP, chờ bổ sung) |
| | File lỗi/không đọc được → "Cần HR kiểm tra" (không tự động loại) | ✅ Có — chip + banner đỏ "Cần HR xử lý CV" trên ranking và trang chi tiết; card summary riêng | — |
| | Cho phép HR chỉnh sửa thông tin trích xuất sai (tên/email/số ĐT) | ❌ Chưa có UI chỉnh sửa profile | 🟡 Trung bình (defer sang Phase 2) |
| **F1.05** | Matching có bằng chứng (4 mức + trích dẫn + số trang) | ✅ Có (side-by-side page) | — |
| | Click trích dẫn → nhảy đến trang tương ứng trong PDF | ✅ Có — click chip "Trang X" sẽ điều hướng PDF iframe đến `#page=N` | — |
| | "Chưa rõ" ≠ "Chưa đáp ứng" (phân biệt thiếu thông tin) | ✅ Logic worker đúng; UI hiển thị màu UNCLEAR | — |
| **F1.06** | Ranking theo tiêu chí bắt buộc trước điểm | ✅ Có (matching_engine.rank_applications) | — |
| | Cảnh báo độ phủ < 70% | ✅ Có (chip "Độ phủ bằng chứng thấp" + progress bar màu) | — |
| | Nút "Chạy đánh giá / Tạo xếp hạng" trên UI | ✅ Có (commit 2b48f28) — polling operation 2s, progress bar, tự làm mới khi xong | — |
| **F1.07** | Cảnh báo hồ sơ trùng lặp trong cùng vị trí | ✅ Có — backend flag `has_duplicate_warning`; UI hiển thị chip vàng + banner chi tiết; card summary "Cảnh báo trùng lặp" | — |
| **F1.08** | HR cập nhật trạng thái hồ sơ (tất cả các trạng thái NEW→INTERVIEW→ACCEPTED) | ⚠️ API hỗ trợ đủ 8 trạng thái; dialog cập nhật chỉ có vài lựa chọn đơn giản | 🟡 Trung bình |
| | AI không bao giờ tự động đổi trạng thái | ✅ Đúng thiết kế | — |
| **F1.09** | Chia sẻ Shortlist cho Hiring Manager (có phân quyền xem CV) | ✅ Có — nút "Chia sẻ Shortlist" mở dialog chọn người nhận + danh sách ứng viên + toggle cho phép xem CV; toggle shortlist từng dòng trong bảng | — |
| | Nhận xét/phản hồi của HM trên shortlist | ⚠️ API có feedback endpoint; trang `/shortlist` chưa có form nhập phản hồi | 🟡 Trung bình |
| | Ghi chú nội bộ HR (bảo mật, không chia sẻ với HM) | ❌ Chưa có bảng/UI cho ghi chú nội bộ | 🟡 Trung bình (Phase 2) |
| **F1.10** | RBAC theo vị trí | ✅ Đã implement trong audit round 2 | — |
| | Audit log cho thao tác quan trọng | ✅ Ghi audit_events từ API (xem được DB-level; UI đọc audit chưa làm) | 🟢 Low |
| | Retention 12 tháng + chờ HR xác nhận xóa | ✅ Có bảng retention schema; UI quản lý retention là Phase 2 | 🟢 Low |
| **F1.11** | Ưu tiên local model, Admin có thể cấu hình model | ✅ Có trang Admin với policy guard external_api | — |
| **F1.12** | Giao diện song ngữ Việt-Anh, mặc định tiếng Việt | ✅ Toàn bộ UI tiếng Việt; không có nút chuyển ngôn ngữ (chưa có locale en-US) → phù hợp MVP | — |
| **F1.13** | Dashboard & Báo cáo theo vai trò | ✅ Có trang Dashboard với card thống kê (một số chỉ số placeholder) | 🟡 Trung bình (số liệu thật sẽ có sau khi dữ liệu vận hành) |
| **Tín hiệu polling tiến trình** | Upload CV xong phải báo tiến trình xử lý hoàn tất | ⚠️ Có polling cho assessment; polling sau upload CV làm mới tự động chưa triển khai | 🟡 Trung bình |

## Tổng hợp công việc cần triển khai (sắp xếp theo ưu tiên)

### 🔴 Critical — Phải có để luồng chính hoạt động
1. ✅ **Nút "Chạy đánh giá & Xếp hạng"** trên trang applicants + polling tiến trình operation (commit `2b48f28`)
2. ✅ **Nút "Thêm vào Shortlist"** + luồng chia sẻ shortlist cho Hiring Manager từ UI (commit `8c2fea3`)
3. ✅ **Hiển thị cảnh báo hồ sơ trùng lặp** trên trang chi tiết ứng viên và trên danh sách xếp hạng (commit `8c2fea3`)
4. ✅ **Badge "Cần HR kiểm tra"** cho các CV lỗi không đọc được / xử lý thất bại (commit `8c2fea3`)
5. **Ghi nhận vai trò khi duyệt tiêu chí** (HR review → PENDING_HM_APPROVAL → HM duyệt) với nút hành động rõ ràng theo vai trò — còn lại
6. ✅ **Trường gán Hiring Manager** khi tạo vị trí (tự gán position_assignment + HIRING_MANAGER system role) (commit `8c2fea3`)
7. **Polling tự động** sau khi upload CV để cập nhật tiến trình xử lý và tự chuyển sang đánh giá khi hoàn tất — còn lại (hiện tại user có thể bấm Refresh hoặc "Chạy đánh giá" sau khi upload xong)

### 🟡 Trung bình — Nên có cho MVP hoàn chỉnh
8. ✅ Click trích dẫn → scroll PDF viewer đến trang tương ứng (commit `8c2fea3`)
9. Form phản hồi Hiring Manager trên trang shortlist — còn lại
10. Dialog cập nhật trạng thái hồ sơ đầy đủ 8 mức (với lý do) — còn lại
11. Cập nhật dashboard số liệu từ dữ liệu thật (số hồ sơ cần kiểm tra, coverage TB, cảnh báo trùng) — còn lại
12. ✅ Loại bỏ/ẩn nút chuyển ngôn ngữ — không có trong build hiện tại (toàn bộ mặc định tiếng Việt)

### 🟢 Low / Out of Scope cho Phase 1 (chuyển sang Phase 2)
- OCR PDF scan (Tesseract) — cần cài system dependency
- Chỉnh sửa thông tin profile ứng viên
- Ghi chú nội bộ HR
- UI quản lý retention/deletion
- i18n song ngữ đầy đủ (hiện tại hardcode tiếng Việt đã đáp ứng "mặc định tiếng Việt")

Sau khi fix các mục 🔴 Critical, luồng end-to-end sẽ là:
  Tạo vị trí (kèm HM) → AI tạo tiêu chí nháp → HR duyệt → HM duyệt → Upload CV → (polling xử lý) → Chạy đánh giá → Xem xếp hạng + cảnh báo trùng/lỗi → Đối chiếu bằng chứng → Cập nhật trạng thái → Thêm vào shortlist → Chia sẻ cho HM → HM xem & phản hồi
