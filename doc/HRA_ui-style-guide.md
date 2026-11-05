# Style Guide UI/UX — VinUni AI-Native CV Matching & Ranking (HRA)

| Thuộc tính | Giá trị chuẩn hóa |
|---|---|
| **Tên tài liệu** | Hướng dẫn Thiết kế Giao diện & Hệ thống Token UI/UX (UI/UX Style Guide & Design System) |
| **Phiên bản** | 1.0 — Đã xác minh & đồng bộ nhận diện từ Cổng tuyển dụng VinUniversity |
| **Nguồn đối chiếu thực tế** | Cổng tuyển dụng chính thức: `https://careerportalvinuni.talent.vn/` (VinUniversity Career Portal / Base Talent) |
| **Phạm vi áp dụng** | Ứng dụng nội bộ dành cho HR Recruiter, Hiring Manager và HR Lead tại VinUniversity |
| **Mục tiêu thiết kế** | Đồng bộ nhận diện thương hiệu học thuật quốc tế VinUni, tối ưu hóa công năng thẩm định bằng chứng, đảm bảo khả năng tiếp cận WCAG 2.2 AA |

---

## 1. Tóm tắt Kết quả Phân tích Nhận diện từ VinCareer Portal

Qua việc truy cập, bóc tách tệp CSS và tài sản đồ họa từ `https://careerportalvinuni.talent.vn/`, hệ sinh thái nhận diện số của VinUniversity Career Portal sở hữu các đặc trưng thị giác cốt lõi sau:

1. **Màu sắc chủ đạo (Brand Identity Colors):**
   * **VinUni Deep Navy (`#0A2B57`):** Màu xanh đại học truyền thống, biểu trưng cho sự uy tín, học thuật và tin cậy. Được sử dụng cho thanh điều hướng trên cùng (`.header-top`), tiêu đề tin tuyển dụng (`.job--title a`), và màu hover của nút chính.
   * **VinUni Signature Red (`#C72127`):** Màu đỏ biểu trưng của tập đoàn Vingroup và VinUniversity. Được sử dụng cho nút hành động nổi bật (`.btn-apply-main`, `.cta`), tạo điểm nhấn thị giác quyết đoán.
   * **Burgundy / Deep Crimson (`#941616`):** Màu đỏ trầm được dùng cho trạng thái kích hoạt / di chuột (`active/hover`) của menu chính và tiêu đề tin tuyển dụng.
   * **Secondary Navy (`#134D8B`) & Cyan Blue (`#2599DC`):** Màu xanh biển phụ trợ dùng cho nền footer, các liên kết phụ và trạng thái focus/hover.
2. **Typography chuẩn hóa:**
   * Phông chữ chính thức là **`Roboto`** (Google Fonts hỗ trợ bộ ký tự tiếng Việt hoàn hảo), kết hợp cùng phông hệ thống `'Segoe UI', Arial, sans-serif`.
   * Cỡ chữ chuẩn mực, phân cấp rạch ròi, đậm nét ở các tiêu đề chính và nút hành động.
3. **Hình khối & Bo góc (Shape & Radii):**
   * Nút hành động chính bo góc **`8px`** (`border-radius: 8px`).
   * Thanh tìm kiếm bo tròn pill **`30px`** (`border-radius: 30px`).
   * Thẻ menu bo góc đáy **`15px`** (`border-radius: 0 0 15px 15px`).
4. **Nguyên tắc chuyển thể từ Portal ứng viên sang Ứng dụng HR nội bộ:**
   * Kế thừa nguyên vẹn **bảng màu, typography và logo chuẩn** của VinUni.
   * Chuyển đổi bố cục từ dạng *Portal công cộng* (hero banner, danh thiếp tìm việc) sang dạng *Bảng điều khiển chuyên nghiệp (Workspace / Dashboard)* với mật độ thông tin cao, hỗ trợ đối chiếu văn bản 2 cột (Side-by-side CV Review) và thao tác nhanh bằng phím tắt.

---

## 2. Hệ thống Token Màu sắc Chuẩn hóa (Design Color Tokens)

### 2.1. Màu Thương hiệu (Brand Colors) — Trích xuất từ VinCareer

| Tên Token | Mã HEX | Giá trị RGB | Ứng dụng trong Hệ thống Nội bộ HRA |
|---|:---:|:---:|---|
| `color-brand-primary` | **`#0A2B57`** | `rgb(10, 43, 87)` | Thanh App Header chính, Tiêu đề bảng, Nhóm vị trí, Nút thứ cấp quan trọng. |
| `color-brand-accent` | **`#C72127`** | `rgb(199, 33, 39)` | Nút kêu gọi hành động chính (Primary CTA: *"Duyệt tiêu chí"*, *"Tải lên lô CV"*, *"Tạo Shortlist"*). |
| `color-brand-active` | **`#941616`** | `rgb(148, 22, 22)` | Trạng thái Active trên Sidebar/Menu, Hover của các liên kết quan trọng. |
| `color-brand-secondary` | **`#134D8B`** | `rgb(19, 77, 139)` | Nền Footer, Tiêu đề phụ, Thẻ phân loại phòng ban. |
| `color-brand-interactive` | **`#2599DC`** | `rgb(37, 153, 220)` | Liên kết nội dung, Viền khi focus ô nhập liệu (Focus Ring), Huy hiệu thông tin. |

### 2.2. Màu Trung tính & Bề mặt (Neutrals & Surfaces)

| Tên Token | Mã HEX | Ứng dụng trong Giao diện |
|---|:---:|---|
| `color-surface-background` | **`#F8FAFC`** | Nền toàn trang ứng dụng (nhẹ nhàng, chống mỏi mắt cho HR khi làm việc lâu). |
| `color-surface-card` | **`#FFFFFF`** | Nền thẻ hồ sơ, bảng dữ liệu, cửa sổ modal popup. |
| `color-surface-subtle` | **`#F3EEEE`** | Nền ô tìm kiếm, nền thanh công cụ bộ lọc (Kế thừa ô search VinCareer). |
| `color-surface-hover` | **`#F1F5F9`** | Nền khi rê chuột trên hàng bảng (Table row hover), Nền nút phụ. |
| `color-border-default` | **`#E2E8F0`** | Đường viền ngăn cách giữa các cột, viền bảng và viền thẻ. |
| `color-border-subtle` | **`#EEEEEE`** | Đường kẻ mờ phân tách giữa các mục tin. |
| `color-text-primary` | **`#112434`** | Màu chữ chính (Kế thừa từ banner VinCareer; độ tương phản cực cao trên nền trắng). |
| `color-text-secondary` | **`#475569`** | Nhãn mô tả, thông tin phụ, ngày tháng, tên phòng ban. |
| `color-text-muted` | **`#A09F9C`** | Placeholder trong ô nhập, chữ bị vô hiệu hóa (Disabled state). |

### 2.3. Màu Trạng thái Nghiệp vụ & Đánh giá AI (Semantic & Status Tokens)

Hệ thống tuân thủ nguyên tắc **Tách biệt 3 miền trạng thái** đã được định nghĩa trong [HRA_ArchitectureDesign.md](file:///d:/VinUniIT/doc/HRA_ArchitectureDesign.md):

| Miền Trạng thái | Giá trị Hiển thị | Màu chữ / Viền | Màu nền Badge | Ý nghĩa & Nguyên tắc Vận hành |
|---|---|:---:|:---:|---|
| **1. Trạng thái Tệp CV** | **Đọc thành công** | `#067647` | `#ECFDF3` | File PDF/DOCX hợp lệ, đã bóc tách xong văn bản. |
| *(File Status)* | **Đang xử lý / OCR** | `#134D8B` | `#EFF8FF` | Đang chạy bóc tách text hoặc tiến trình OCR scan. |
| | **Cần HR kiểm tra** | `#B54708` | `#FFFAEB` | File bị khóa, quá mờ hoặc lỗi font. **Không được tự động loại hồ sơ**. |
| | **File lỗi** | `#B42318` | `#FEF3F2` | File hỏng, sai định dạng hoặc vượt dung lượng 10MB. |
| **2. Nhóm Matching AI** | **Đáp ứng tiêu chí bắt buộc** | `#0A2B57` | `#E8F1FC` | Đạt 100% tiêu chí bắt buộc (Must-have). |
| *(Advisory Group)* | **Cần HR xác minh** | `#B54708` | `#FFFAEB` | Có tiêu chí bắt buộc ở mức *"Chưa rõ"* hoặc độ phủ bằng chứng $< 70\%$. |
| | **Có dấu hiệu miss-match** | `#941616` | `#FDF2F2` | Có tiêu chí bắt buộc ở mức *"Chưa đáp ứng"*. Dùng cảnh báo, **không tự ý loại**. |
| **3. Trạng thái Tuyển dụng** | **Mới (New)** | `#475467` | `#F2F4F7` | Hồ sơ mới tiếp nhận, chưa có thao tác rà soát. |
| *(Application Status)* | **Đang xem (Reviewing)** | `#175CD3` | `#EFF8FF` | HR đang mở xem chi tiết bằng chứng. |
| *(Chỉ HR được đổi)* | **Shortlist** | `#067647` | `#ECFDF3` | HR chọn vào danh sách phỏng vấn gửi Hiring Manager. |
| | **Bị loại ở sàng lọc** | `#B42318` | `#FEF3F2` | Quyết định loại chính thức có kèm lý do của HR. |

---

## 3. Typography & Kiểu chữ Chuẩn mực (Typography System)

### 3.1. Phông chữ (Font Family)
* **Phông chữ chủ đạo:** **`Roboto`** (Tải trực tiếp qua Google Fonts API: `https://fonts.googleapis.com/css?family=Roboto:300,400,500,700&subset=vietnamese,latin`).
* **Phông chữ dự phòng:** `'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif`.
* **Phông mã nguồn (Monospace):** `'Consolas', 'Courier New', monospace` (dùng hiển thị đoạn code hoặc ID kỹ thuật).

### 3.2. Bảng Phân cấp Cỡ chữ (Type Scale)

| Cấp bậc | Cỡ chữ / Line Height | Font Weight | Áp dụng trên Màn hình HRA |
|---|:---:|:---:|---|
| **Display / H1** | `28px` / `36px` | Bold (`700`) | Tiêu đề trang Dashboard, Tiêu đề Requisition lớn. |
| **Section / H2** | `22px` / `28px` | Bold (`700`) | Tiêu đề phân khu (Bảng tiêu chí, Danh sách ứng viên). |
| **Title / H3** | `18px` / `24px` | Semi-bold (`600`) | Tên ứng viên trong trang chi tiết, Tiêu đề modal dialog. |
| **Subhead / H4** | `15px` / `22px` | Bold (`700`) | Tiêu đề từng tiêu chí đánh giá, Tiêu đề nhóm matching. |
| **Body (Default)** | `14px` / `20px` | Regular (`400`) | Nội dung bằng chứng trích dẫn, văn bản form nhập liệu, bảng dữ liệu. |
| **Body Medium** | `14px` / `20px` | Medium (`500`) | Tên trường thông tin (Labels), Tiêu đề cột trong Data Table. |
| **Caption / Small** | `12px` / `16px` | Regular (`400`) | Số trang dẫn chứng (`Trang 2, dòng 14`), Ngày tháng nộp hồ sơ. |
| **Badge / Tag** | `11px` / `14px` | Bold (`700`) | Nhãn trạng thái (UPPERCASE), Mã loại tiêu chí (`MUST-HAVE`). |

---

## 4. Thư viện Tài sản Thương hiệu & Biểu tượng (Brand Assets)

Các tài sản được lấy chính xác từ CDN chính thức của cổng tuyển dụng VinUniversity:

| Tài sản | Đường dẫn CDN Thực tế | Quy cách hiển thị trên giao diện HRA |
|---|---|---|
| **Logo Header** | `https://data-talent-v2.basecdn.net/careerportalvinuni/logo.png` | Hiển thị góc trái thanh App Shell; chiều cao tối đa `42px`, nền trong suốt. |
| **Logo Footer / Mono** | `https://data-talent-v2.basecdn.net/careerportalvinuni/logo-footer.png` | Sử dụng trong trang đăng nhập nội bộ hoặc footer báo cáo in ấn. |
| **Favicon** | `https://data-talent-v2.basecdn.net/careerportalvinuni/fav.png` | Biểu tượng icon tab trình duyệt `16x16` / `32x32`. |
| **Bộ Icon Hệ thống** | **FontAwesome 5+** hoặc **Tabler Icons** | Đồng bộ với icon search (`f002`), icon tệp tin, icon người dùng trên Base Talent. |

---

## 5. Quy chuẩn Thành phần Giao diện (Component Specifications)

### 5.1. Nút bấm (Button Styles)
Kế thừa trực tiếp thông số từ `.btn-apply-main` và `.header-bottom .cta` của VinCareer:

```css
/* Nút Hành động Chính (Primary CTA Button) */
.btn-primary {
  background-color: #C72127; /* VinUni Red */
  color: #FFFFFF;
  font-family: 'Roboto', sans-serif;
  font-size: 14px;
  font-weight: 700;
  padding: 10px 20px;
  border-radius: 8px; /* Bo góc 8px chuẩn VinCareer */
  border: none;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
}
.btn-primary:hover {
  background-color: #0A2B57; /* Hover chuyển sang VinUni Navy */
  box-shadow: 0 2px 6px rgba(10, 43, 87, 0.25);
}

/* Nút Thứ cấp (Secondary Button) */
.btn-secondary {
  background-color: #FFFFFF;
  color: #0A2B57;
  font-size: 14px;
  font-weight: 600;
  padding: 9px 18px;
  border-radius: 8px;
  border: 1px solid #0A2B57;
  cursor: pointer;
}
.btn-secondary:hover {
  background-color: #F1F5F9;
}

/* Nút Nguy hiểm (Destructive Action - Xóa hồ sơ) */
.btn-danger {
  background-color: #B42318;
  color: #FFFFFF;
  border-radius: 8px;
  padding: 10px 20px;
}
```

### 5.2. Thanh Tìm kiếm & Ô Nhập liệu (Search & Input Fields)
Kế thừa thiết kế từ `.box-search .form-group .form-control` của VinCareer:
* **Thanh tìm kiếm nhanh (Global Search):** Nền `#F3EEEE`, bo góc pill tròn `30px`, icon kính lúp màu `#A09F9C` ở bên trái, chữ cỡ `14px`. Khi focus đổi nền trắng `#FFFFFF` kèm viền xanh `#2599DC`.
* **Ô nhập dữ liệu Form (Inputs):** Nền `#FFFFFF`, viền `#E2E8F0`, bo góc `6px`, đệm `8px 12px`. Khi có lỗi hiển thị viền đỏ `#C72127` kèm thông báo lỗi bên dưới.

### 5.3. Huy hiệu Trạng thái (Status Badges)
* Kích thước: Padding `4px 8px`, bo góc `4px`, chữ hoa cỡ `11px`, `font-weight: 700`.
* **Luôn đi kèm biểu tượng và nhãn chữ rõ ràng**, không chỉ phân biệt bằng màu sắc đơn thuần.

### 5.4. Thẻ Hiển thị Bằng chứng AI (Evidence Citation Card)
Khối giao diện độc quyền của sản phẩm HRA:
* **Bố cục:** Nền `#FFFFFF`, viền trái dày `4px` phân màu theo 4 mức đánh giá:
  * `STRONG_MATCH`: Viền xanh lá `#067647`.
  * `MATCH`: Viền xanh navy `#0A2B57`.
  * `UNCLEAR`: Viền cam cảnh báo `#B54708`.
  * `NO_MATCH`: Viền đỏ `#C72127`.
* **Vùng trích dẫn nguyên văn (`verbatim_quote`):** Đặt trong thẻ blockquote nền xám nhẹ `#F8FAFC`, chữ in nghiêng màu `#112434`, hiển thị huy hiệu số trang nổi bật: `[Trang 2 / Đoạn 3]`.

---

## 6. Kiến trúc Bố cục Giao diện Nội bộ (Application Shell Layout)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ [LOGO VINUNI]  AI-Native CV Screening Workspace          [🔍 Tìm kiếm...]   VI/EN  (👤 CuongTV)│
├───────────────┬──────────────────────────────────────────────────────────────────────────────┤
│ 📋 Vị trí     │ 🧭 Vị trí: Backend Engineer (REQ-IT-01)  [Trạng thái: ĐANG MỞ]               │
│ 👥 Ứng viên   │ [Tab 1: Tiêu chí đã duyệt]  [★ Tab 2: Danh sách Xếp hạng]  [Tab 3: Tải lô CV]│
│ 📊 Báo cáo    ├────────────────────────────────────────┬─────────────────────────────────────┤
│ ⚙️ Quản trị   │ BỘ LỌC & DANH SÁCH XẾP HẠNG            │ ĐỐI SOÁT CHI TIẾT & BẰNG CHỨNG      │
│               │ ────────────────────────────────────── │ ─────────────────────────────────── │
│               │ #1. Nguyễn Văn A (Điểm: 85 - Đạt 100%) │ [PDF CV Gốc]  │ [Đối chiếu Rubric] │
│               │ #2. Trần Thị B   (Điểm: 78 - Đạt 100%) │  (Trang 1/3)  │ • Python: MATCH    │
│               │ #3. Lê Văn C     (Cần HR xác minh)     │               │   Quote: "4 năm..."│
│               │                                        │ ─────────────┴──────────────────── │
│               │                                        │ [Chuyển Shortlist] [Bị loại vòng 1]│
└───────────────┴────────────────────────────────────────┴─────────────────────────────────────┘
```

* **Thanh Header (Chiều cao 60px):** Nền `#0A2B57` (VinUni Deep Navy), logo VinUniversity màu trắng, ô tìm kiếm nhanh, chuyển đổi ngôn ngữ Việt/Anh và thông tin tài khoản người dùng.
* **Thanh Sidebar (Chiều rộng 240px):** Nền `#FFFFFF`, viền phải `#E2E8F0`. Mục được chọn có nền `#FDF2F2` và vạch chỉ báo màu đỏ `#C72127` ở mép trái.
* **Khu vực Làm việc Chính (Workspace Area):** Nền `#F8FAFC`. Khi rà soát hồ sơ, chia đôi màn hình tỷ lệ **50:50** (Nửa trái hiển thị bản xem trước CV gốc; Nửa phải hiển thị các tiêu chí kèm dẫn chứng AI và nút xác nhận của HR).

---

## 7. Quy chuẩn Tiếp cận & Khả năng Dụng (Accessibility & Usability)

1. **Đạt chuẩn WCAG 2.2 Cấp độ AA:**
   * Mọi văn bản thông thường trên nền trắng hoặc xanh navy đạt tỷ lệ tương phản tối thiểu **`4.5:1`**.
   * Chữ cỡ lớn ($\ge 18\text{px}$) đạt tỷ lệ tương phản tối thiểu **`3.0:1`**.
   * Trạng thái focus của chuột và bàn phím luôn có vòng viền xanh `#2599DC` rõ nét (`2px solid`).
2. **Không phân biệt trạng thái duy nhất bằng màu sắc:**
   * Mọi huy hiệu trạng thái (Badge) đều có icon và chữ mô tả đi kèm (Ví dụ: Icon dấu tích $\checkmark$ kèm chữ "ĐẠT", Icon dấu chấm than $\triangle$ kèm chữ "CHƯA RÕ").
3. **Thao tác bàn phím (Keyboard Shortcuts):**
   * Hỗ trợ phím tắt điều hướng nhanh trong lúc HR đọc CV: `J` (Xuống ứng viên tiếp theo), `K` (Lên ứng viên trước), `S` (Đưa vào Shortlist), `R` (Đánh dấu cần xem xét).

---

## 8. Hướng dẫn Ứng dụng trên các Màn hình Cốt lõi Phase 1

1. **Màn hình Quản lý Vị trí & JD:**
   * Sử dụng bảng dữ liệu phân hàng xen kẽ trắng/xám nhẹ. Badge trạng thái vị trí dùng màu xanh `#0A2B57` (Mở) và xám `#94A3B8` (Đóng).
2. **Màn hình Duyệt Tiêu chí (Criteria Approval):**
   * Tiêu chí AI đề xuất hiển thị nhãn `BẢN NHÁP` màu vàng cam. Nút *"Phê duyệt chính thức"* dùng màu đỏ `#C72127`. Khi đã duyệt, tiêu chí chuyển sang viền xanh navy `#0A2B57` kèm tên người duyệt.
3. **Màn hình Tải lô CV (Batch Upload):**
   * Vùng kéo thả file (Dropzone) viền nét đứt màu `#2599DC`, nền xám nhạt `#F8FAFC`. Danh sách file tải lên hiển thị thanh tiến trình và icon trạng thái bóc tách. File lỗi hiển thị chữ đỏ `#B42318` kèm nút *"Kiểm tra thủ công"*.
4. **Màn hình Xếp hạng & Đối soát Bằng chứng:**
   * Bảng ứng viên hiển thị rõ 3 cột phân biệt: **Hạng ưu tiên**, **Điểm trọng số** và **% Độ phủ bằng chứng**. Tuyệt đối không dùng dải màu gradient xanh-đỏ toàn dòng gây áp lực thị giác.
   * Click vào dòng ứng viên sẽ trượt mở bảng đối chiếu bằng chứng với các trích đoạn văn bản nguyên văn từ CV gốc.