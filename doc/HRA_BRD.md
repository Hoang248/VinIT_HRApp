# Phân tích yêu cầu nghiệp vụ — HR CV & JD Ranking

> **Phiên bản:** 1.0 — Draft for Review  
> **Trạng thái:** Baseline nghiệp vụ để các bên rà soát; chưa phải tài liệu được phê duyệt cuối cùng.  
> **Phạm vi tài liệu:** Phân tích yêu cầu nghiệp vụ và sản phẩm. Không thiết kế kiến trúc, công nghệ hoặc phương án triển khai.

## Bối cảnh và phạm vi dự án

**Tên dự án:** HR CV & JD Ranking

**Bối cảnh:** HR VinUni tiếp nhận khối lượng lớn CV cho các vị trí không phải giảng viên. Việc đọc, rà soát và đối chiếu CV với JD hiện tiêu tốn thời gian, công sức; việc ưu tiên hồ sơ và đánh giá tính nhất quán cần được cải thiện.

**Mục tiêu:** Xây dựng sản phẩm AI-Native hỗ trợ chuyển JD và CV thành quy trình sàng lọc có tiêu chí rõ ràng, bằng chứng kiểm chứng được và ranking hữu ích cho HR.

**Phạm vi MVP dự kiến:**

- Pilot với các vị trí IT: Software Engineer, QA, DevOps, Data Engineer và IT Support.
- HR upload CV trực tiếp theo từng vị trí; chưa crawl CV từ nguồn online.
- CV và JD bằng tiếng Anh; giao diện tiếng Việt/tiếng Anh, mặc định tiếng Việt.
- AI đề xuất tiêu chí từ JD, trích xuất nội dung CV, đối chiếu tiêu chí và hỗ trợ xếp hạng trong **cùng một vị trí tuyển dụng**.
- HR và Hiring Manager rà soát, phê duyệt tiêu chí; HR giữ quyền quyết định trạng thái và kết quả tuyển dụng.
- MVP không tự động loại ứng viên, không tự động thay đổi trạng thái tuyển dụng và không dùng ngưỡng điểm để quyết định tuyển/loại.

---

## 1. Business Goals

| ID | Nhóm | Mục tiêu | Vì sao quan trọng | JTBD liên quan |
|---|---|---|---|---|
| **BG-01** | Chiến lược | Nâng cao tính nhất quán, chất lượng và khả năng giải thích của việc sàng lọc tuyển dụng không phải giảng viên. | Giúp các hồ sơ được đánh giá theo tiêu chí liên quan đến công việc thay vì phụ thuộc quá nhiều vào cách đọc thủ công của từng người. | JTBD-01, 03, 06, 09 |
| **BG-02** | Chiến lược | Bảo vệ dữ liệu ứng viên và duy trì cách xử lý hồ sơ có trách nhiệm. | CV chứa dữ liệu cá nhân; quyền truy cập, sử dụng và lưu trữ không phù hợp có thể gây rủi ro cho ứng viên và VinUni. | JTBD-02, 05, 08 |
| **BG-03** | Vận hành | Giảm công sức thủ công trong tiếp nhận, đọc và rà soát CV. | Khối lượng CV lớn làm HR mất nhiều thời gian vào việc tìm thông tin thay vì tập trung vào đánh giá và phối hợp tuyển dụng. Chưa có baseline để đặt mục tiêu giảm thời gian. | JTBD-02, 03, 04 |
| **BG-04** | Vận hành | Giúp HR ưu tiên hồ sơ có bằng chứng phù hợp và giảm nguy cơ bỏ sót ứng viên tiềm năng. | Tìm đúng hồ sơ trong tập lớn CV có thể khó, đặc biệt khi bằng chứng nằm rải rác trong tài liệu. | JTBD-03, 04, 05 |
| **BG-05** | Vận hành | Theo dõi được tiến độ, khối lượng và hiệu quả của quy trình tuyển dụng. | Không có baseline hoặc số liệu nhất quán thì khó xác định vấn đề hiện tại và đánh giá giá trị của sản phẩm. | JTBD-07 |
| **BG-06** | Sản phẩm | Chuyển yêu cầu trong JD thành bộ tiêu chí sàng lọc có cấu trúc và được phê duyệt. | Một rubric rõ ràng giúp HR và Hiring Manager đánh giá ứng viên theo cùng cách hiểu. | JTBD-01, 09 |
| **BG-07** | Sản phẩm | Cung cấp matching và ranking có bằng chứng, đồng thời giữ quyền quyết định ở con người. | AI chỉ tạo giá trị nếu HR hiểu được lý do gợi ý và có thể tự kiểm chứng, điều chỉnh hoặc bỏ qua kết quả. | JTBD-03, 04, 05, 06, 09 |
| **BG-08** | Sản phẩm | Quản lý trạng thái, quyền truy cập và vòng đời hồ sơ một cách có kiểm soát. | Hạn chế nhầm lẫn giữa trạng thái xử lý CV, kết quả matching và trạng thái tuyển dụng; hỗ trợ bảo vệ dữ liệu. | JTBD-02, 05, 06, 07, 08 |

---

## 2. User Personas

### 2.1 Primary User — HR Recruiter

- **Mô tả:** Người phụ trách vận hành quy trình tuyển dụng và sàng lọc CV cho các vị trí được giao.
- **Trách nhiệm:**
  - Phối hợp với Hiring Manager để làm rõ tiêu chí tuyển dụng.
  - Tiếp nhận và quản lý CV theo từng vị trí.
  - Rà soát bằng chứng, đánh giá và cập nhật trạng thái hồ sơ.
  - Chia sẻ shortlist và phối hợp với các bên liên quan.
- **Mục tiêu:**
  - Xử lý khối lượng CV hiệu quả hơn.
  - Ưu tiên đúng hồ sơ để rà soát sâu.
  - Có căn cứ rõ ràng cho đánh giá và trạng thái do HR quyết định.
- **Điểm đau:**
  - Đọc thủ công nhiều CV và tìm thông tin liên quan trong các định dạng khác nhau.
  - Khó duy trì cách hiểu tiêu chí nhất quán giữa các vị trí và người đánh giá.
  - Chưa có baseline được xác nhận để đo thời gian xử lý và hiệu quả.
- **Kỳ vọng:**
  - AI đưa ra gợi ý có bằng chứng và nêu rõ trường hợp chưa chắc chắn.
  - HR có quyền kiểm tra CV gốc, điều chỉnh đánh giá và quyết định trạng thái.
  - Dữ liệu chỉ hiển thị cho người có quyền với vị trí tương ứng.

### 2.2 Secondary Users

| Người dùng | Trách nhiệm | Mục tiêu | Điểm đau | Kỳ vọng |
|---|---|---|---|---|
| **Hiring Manager** | Xác nhận tiêu chí chuyên môn; xem shortlist được chia sẻ; cung cấp nhận xét. | Nhận được các hồ sơ phù hợp với yêu cầu của vị trí và hiểu căn cứ đánh giá. | Có thể phải rà soát nhiều CV hoặc nhận shortlist thiếu bằng chứng và tiêu chí rõ. | Chỉ xem hồ sơ thuộc vị trí phụ trách và được chia sẻ; có thể phản hồi trên shortlist. |
| **HR Lead** | Theo dõi tiến độ và hoạt động tuyển dụng ở mức tổng hợp. | Nắm được khối lượng, trạng thái và điểm nghẽn để điều phối hoạt động. | Thiếu baseline và số liệu nhất quán để so sánh. | Xem báo cáo tổng hợp; chỉ xem CV chi tiết khi được cấp quyền. |
| **Admin** | Quản lý người dùng, quyền truy cập và các cấu hình được phê duyệt. | Bảo đảm người dùng và cấu hình tuân thủ chính sách nội bộ. | Cần phân biệt quyền quản trị với quyền xem dữ liệu ứng viên. | Không mặc định có quyền xem CV hoặc xác nhận xóa hồ sơ. |
| **Viewer** | Xem số liệu tổng hợp theo phạm vi được phép. | Theo dõi tiến độ mà không tiếp cận dữ liệu cá nhân không cần thiết. | Không có nhu cầu xem CV chi tiết. | Chỉ xem dữ liệu tổng hợp; không xem CV hoặc PII. |

### 2.3 Stakeholders

- **Các phòng ban tuyển dụng:** cung cấp JD và xác nhận yêu cầu vị trí.
- **Legal/Privacy:** rà soát cơ sở xử lý dữ liệu, retention và quy định liên quan.
- **IT/Security:** xác nhận tiêu chuẩn bảo mật, xác thực và môi trường sử dụng được phê duyệt.
- **HR Product Owner/HR Lead:** sở hữu quy trình, rubric, dữ liệu pilot và tiêu chí đánh giá sản phẩm.
- **Ứng viên:** chủ thể dữ liệu; không phải người dùng trực tiếp trong MVP.
- **Nhà cung cấp model/API, nếu có:** phải tuân thủ điều kiện sử dụng dữ liệu được phê duyệt; không được mặc định sử dụng CV để huấn luyện.

---

## 3. Problem Statements

### 3.1 Operational Problems

| ID | Mô tả | Tác động hiện tại | Kết quả mong muốn |
|---|---|---|---|
| **P-O-01** | HR phải đọc và rà soát khối lượng lớn CV thủ công. | Tốn thời gian, công sức và hạn chế khả năng tập trung vào các hồ sơ cần đánh giá sâu. Chưa có baseline thời gian được xác nhận. | Tự động hỗ trợ tìm và trình bày thông tin liên quan, để HR ưu tiên việc rà soát. |
| **P-O-02** | CV có nhiều định dạng và chất lượng khác nhau, gồm PDF scan, file bị khóa hoặc nội dung khó đọc. | Có nguy cơ bỏ sót nội dung, phải kiểm tra thủ công hoặc xử lý lại. | Nhận diện rõ trạng thái đọc file; chuyển trường hợp lỗi hoặc chưa rõ cho HR kiểm tra, không tự loại hồ sơ. |
| **P-O-03** | Việc theo dõi hồ sơ trùng hoặc thông tin trạng thái giữa các vị trí chưa được mô tả đầy đủ trong hiện trạng. | Có thể phát sinh rà soát trùng lặp hoặc nhầm lẫn trạng thái; tần suất hiện chưa được đo. | Cảnh báo hồ sơ có dấu hiệu trùng trong cùng một vị trí; tách riêng trạng thái xử lý, matching và tuyển dụng. |
| **P-O-04** | Chưa có cơ chế baseline hiệu quả đã được xác nhận. | Không thể định lượng chính xác thời gian hiện tại hoặc mức cải thiện sau pilot. | Thu thập số liệu pilot và chốt KPI sau khi hiểu baseline. |

### 3.2 Decision Problems

| ID | Mô tả | Tác động hiện tại | Kết quả mong muốn |
|---|---|---|---|
| **P-D-01** | HR và Hiring Manager có thể diễn giải yêu cầu trong JD khác nhau nếu tiêu chí chưa rõ. | Đánh giá giữa các vị trí hoặc người đánh giá có thể thiếu nhất quán. | Tiêu chí và rubric được làm rõ, rà soát và phê duyệt trước khi sử dụng. |
| **P-D-02** | Bằng chứng cho từng yêu cầu nằm trong nhiều phần của CV. | HR phải tìm thủ công; khó kiểm tra nhanh căn cứ cho từng đánh giá. | Mỗi nhận định matching có bằng chứng truy về CV gốc. |
| **P-D-03** | Thiếu cách ưu tiên hồ sơ rõ ràng trong cùng một vị trí. | HR có thể phải xử lý hồ sơ theo thứ tự tiếp nhận hoặc đánh giá thủ công; nguy cơ bỏ sót hồ sơ phù hợp. | Có ranking giải thích được để hỗ trợ thứ tự rà soát, không phải quyết định tuyển dụng. |
| **P-D-04** | Chưa có quy tắc rõ để phân biệt “không tìm thấy bằng chứng” với “có bằng chứng không đáp ứng”. | Có nguy cơ đánh giá thấp hồ sơ chỉ vì nội dung không được trích xuất hoặc không thể xác minh. | Trường hợp thiếu bằng chứng hoặc confidence thấp phải được chuyển HR xác minh; không tự hiểu là không đáp ứng. |

### 3.3 Product Problems

| ID | Mô tả | Tác động hiện tại | Kết quả mong muốn |
|---|---|---|---|
| **P-P-01** | Công cụ CRM hoặc công cụ hiện tại và quy trình xử lý end-to-end chưa được xác nhận trong discovery. | Có nguy cơ bỏ sót bước nghiệp vụ hoặc lặp lại chức năng đã có. | Xác minh hệ thống và quy trình hiện hành trước khi chốt yêu cầu sản phẩm. |
| **P-P-02** | Nếu AI đưa ra điểm hoặc kết luận mà không có bằng chứng và cơ chế kiểm soát, người dùng có thể quá tin vào kết quả. | Rủi ro quyết định sai hoặc hiểu nhầm rằng AI đã quyết định tuyển/loại. | Hiển thị bằng chứng, mức độ chưa rõ và giới hạn quyền của AI; HR giữ quyền quyết định. |
| **P-P-03** | Quyền truy cập, thời hạn lưu hồ sơ và chính sách dùng dữ liệu với dịch vụ ngoài còn cần được xác nhận. | Rủi ro về quyền riêng tư, tuân thủ và truy cập không phù hợp. | Có chính sách được phê duyệt, quyền tối thiểu, retention rõ ràng và điều kiện sử dụng model được kiểm soát. |

---

## 4. Job To Be Done (JTBD)

JTBD mô tả kết quả người dùng muốn đạt được, không phải danh sách thao tác giao diện hay công việc thủ công.

| ID | JTBD — Job statement | Kích hoạt | Kết quả mong đợi | Vai trò chính | Journey | Business Goal |
|---|---|---|---|---|---|---|
| **JTBD-01** | Khi một vị trí được mở hoặc JD thay đổi, tôi muốn các yêu cầu chuyên môn được hiểu theo cách thống nhất để việc đánh giá ứng viên nhất quán. | Mở vị trí mới hoặc cập nhật JD. | Bộ tiêu chí rõ ràng, liên quan công việc và được phê duyệt. | HR, Hiring Manager | UJ-01 | BG-01, BG-06, BG-07 |
| **JTBD-02** | Khi hồ sơ ứng tuyển đến theo số lượng lớn, tôi muốn tập hồ sơ theo vị trí được quản lý rõ và đáng tin cậy để không bỏ sót hoặc xử lý nhầm hồ sơ. | CV được tiếp nhận cho một vị trí. | Hồ sơ gắn đúng vị trí, trạng thái xử lý rõ và ngoại lệ được nhận diện. | HR Recruiter | UJ-02 | BG-02, BG-03, BG-08 |
| **JTBD-03** | Khi cần đánh giá ứng viên, tôi muốn nhìn thấy thông tin và bằng chứng liên quan đến từng tiêu chí để đánh giá có căn cứ. | CV đã được tiếp nhận và cần sàng lọc. | HR hiểu ứng viên đáp ứng, chưa rõ hay có dấu hiệu không đáp ứng dựa trên bằng chứng. | HR Recruiter | UJ-03 | BG-01, BG-03, BG-04, BG-06, BG-07 |
| **JTBD-04** | Khi có nhiều hồ sơ trong cùng một vị trí, tôi muốn biết hồ sơ nào nên được ưu tiên rà soát để sử dụng thời gian hiệu quả hơn. | Tập CV của vị trí đủ lớn để cần ưu tiên. | Ranking trong cùng vị trí, có thể kiểm chứng và không tự quyết định kết quả. | HR Recruiter | UJ-03 | BG-03, BG-04, BG-07 |
| **JTBD-05** | Khi file, bằng chứng hoặc nhận diện hồ sơ chưa rõ, tôi muốn biết trường hợp nào cần xác minh để không loại nhầm ứng viên. | CV lỗi, thiếu dữ liệu, confidence thấp hoặc có dấu hiệu trùng. | Ngoại lệ được cảnh báo và chuyển HR xử lý thủ công. | HR Recruiter | UJ-02, UJ-03 | BG-02, BG-04, BG-07, BG-08 |
| **JTBD-06** | Khi đã rà soát ứng viên, tôi muốn trạng thái và nhận xét của các bên được ghi nhận rõ để những người liên quan hiểu đúng kết quả sàng lọc. | HR ra quyết định sàng lọc hoặc chia sẻ shortlist. | Trạng thái do con người cập nhật; Hiring Manager xem được shortlist thuộc phạm vi được chia sẻ. | HR Recruiter, Hiring Manager | UJ-04 | BG-01, BG-07, BG-08 |
| **JTBD-07** | Khi cần điều phối tuyển dụng, tôi muốn biết tiến độ và khối lượng xử lý để nhận diện điểm nghẽn và đánh giá hiệu quả. | HR Lead cần theo dõi hoạt động hoặc đánh giá pilot. | Số liệu tổng hợp theo vai trò, vị trí và giai đoạn. | HR Lead | UJ-05 | BG-05, BG-08 |
| **JTBD-08** | Khi xử lý dữ liệu ứng viên, tôi muốn hồ sơ chỉ được truy cập và lưu theo chính sách được duyệt để bảo vệ dữ liệu và trách nhiệm của VinUni. | Hồ sơ được tạo, sử dụng, vị trí đóng hoặc đến hạn lưu. | Quyền, retention và xác nhận xóa được kiểm soát theo hồ sơ ứng tuyển. | HR, Admin, Legal/Privacy | UJ-06 | BG-02, BG-08 |
| **JTBD-09** | Khi đánh giá ứng viên cho vị trí phụ trách, tôi muốn xác nhận tiêu chí chuyên môn và hiểu bằng chứng của shortlist để có thể đưa ra nhận xét phù hợp. | JD được chuẩn bị hoặc HR chia sẻ shortlist. | Hiring Manager đóng góp vào rubric và phản hồi trên hồ sơ được phép xem. | Hiring Manager | UJ-01, UJ-04 | BG-01, BG-06, BG-07 |

### 4.1 User Journey — ánh xạ JTBD

| Journey | Giai đoạn hành trình | JTBD |
|---|---|---|
| **UJ-01** | Làm rõ nhu cầu vị trí, JD và tiêu chí | JTBD-01, JTBD-09 |
| **UJ-02** | Tiếp nhận CV và xử lý lỗi/ngoại lệ | JTBD-02, JTBD-05 |
| **UJ-03** | Đọc bằng chứng, matching và ưu tiên hồ sơ | JTBD-03, JTBD-04, JTBD-05 |
| **UJ-04** | HR ghi nhận quyết định và phối hợp với Hiring Manager | JTBD-06, JTBD-09 |
| **UJ-05** | Theo dõi tiến độ và hiệu quả | JTBD-07 |
| **UJ-06** | Quản lý quyền truy cập, retention và xóa hồ sơ | JTBD-08 |

---

## 5. JTBD Decomposition

Phần này mô tả workflow hiện tại theo thông tin đã có; không đề xuất thiết kế lại workflow.

### JTBD-01 — Thống nhất tiêu chí tuyển dụng

- **User Tasks:** UT-01, UT-02, UT-03.
- **Current Workflow:** HR và Hiring Manager phối hợp dựa trên JD để thống nhất yêu cầu; cách lưu tiêu chí và mức độ chuẩn hóa hiện cần xác minh.
- **Pain Points:** P-D-01.
- **AI Opportunities:** AIC-01 có thể đề xuất bản nháp tiêu chí từ JD; không được tự phê duyệt.
- **Expected Benefits:** Tiêu chí rõ, giảm khác biệt trong cách diễn giải và tạo căn cứ chung cho sàng lọc.

### JTBD-02 — Quản lý tập CV theo vị trí

- **User Tasks:** UT-04, UT-05.
- **Current Workflow:** HR tiếp nhận và quản lý CV theo vị trí; kênh tiếp nhận và hệ thống hiện tại chưa được xác nhận.
- **Pain Points:** P-O-01, P-O-02, P-P-03.
- **AI Opportunities:** AIC-02 hỗ trợ cấu trúc nội dung CV; AIC-06 cảnh báo file có khả năng trùng.
- **Expected Benefits:** Giảm công tìm thông tin và phát hiện sớm file cần HR kiểm tra.

### JTBD-03 — Đánh giá bằng chứng trong CV

- **User Tasks:** UT-06, UT-07.
- **Current Workflow:** HR đọc CV và so sánh thủ công với JD; cách ghi nhận bằng chứng hiện tại chưa được mô tả đầy đủ.
- **Pain Points:** P-O-01, P-D-02, P-D-04.
- **AI Opportunities:** AIC-02 trích xuất thông tin; AIC-03 đối chiếu từng tiêu chí; AIC-05 nhận diện trường hợp chưa chắc chắn.
- **Expected Benefits:** HR tìm được căn cứ nhanh hơn, hiểu rõ phần nào đáp ứng và phần nào cần xác minh.

### JTBD-04 — Ưu tiên hồ sơ trong cùng vị trí

- **User Tasks:** UT-09.
- **Current Workflow:** HR phải tự ưu tiên hồ sơ; hiện chưa có baseline về cách ưu tiên hoặc hiệu quả của cách làm này.
- **Pain Points:** P-O-01, P-D-03.
- **AI Opportunities:** AIC-03 và AIC-04 tạo ranking có thể giải thích trong cùng một vị trí.
- **Expected Benefits:** HR có thứ tự rà soát hữu ích hơn, nhưng vẫn tự xác minh và quyết định.

### JTBD-05 — Xử lý hồ sơ chưa rõ hoặc có dấu hiệu bất thường

- **User Tasks:** UT-05, UT-08.
- **Current Workflow:** Cách xử lý hiện tại với PDF scan, file lỗi, bằng chứng thiếu và CV trùng cần xác minh.
- **Pain Points:** P-O-02, P-O-03, P-D-04, P-P-02.
- **AI Opportunities:** AIC-05 chuyển trường hợp thiếu bằng chứng hoặc confidence thấp cho HR; AIC-06 cảnh báo hồ sơ trùng.
- **Expected Benefits:** Hạn chế loại nhầm, giảm rà soát trùng và làm rõ trách nhiệm xử lý ngoại lệ.

### JTBD-06 — Ghi nhận quyết định và chia sẻ shortlist

- **User Tasks:** UT-10, UT-11.
- **Current Workflow:** HR ghi nhận kết quả sàng lọc và phối hợp với Hiring Manager; công cụ và cách cập nhật trạng thái hiện cần xác minh.
- **Pain Points:** P-P-01, P-P-02.
- **AI Opportunities:** AI chỉ có thể hỗ trợ trình bày lại bằng chứng; không cần AI để quyết định hoặc cập nhật trạng thái.
- **Expected Benefits:** Trạng thái tuyển dụng rõ ràng, quyết định có người chịu trách nhiệm và shortlist được chia sẻ đúng phạm vi.

### JTBD-07 — Theo dõi tiến độ và hiệu quả

- **User Tasks:** UT-12.
- **Current Workflow:** Chưa có baseline thời gian xử lý; cách lập báo cáo hiện tại chưa được xác nhận.
- **Pain Points:** P-O-04.
- **AI Opportunities:** Không cần AI cho số liệu cơ bản; báo cáo nên dựa trên số liệu nghiệp vụ có thể kiểm tra.
- **Expected Benefits:** Có căn cứ đánh giá pilot và xác định điểm nghẽn trước khi đặt KPI.

### JTBD-08 — Quản lý quyền và vòng đời dữ liệu

- **User Tasks:** UT-13, UT-14.
- **Current Workflow:** Chính sách retention 12 tháng từ ngày đóng vị trí đã được đề xuất; cách vận hành, quyền xác nhận xóa và hệ thống hiện tại cần xác minh.
- **Pain Points:** P-P-03.
- **AI Opportunities:** Không cần AI để quyết định quyền hoặc xóa hồ sơ; cần giới hạn dữ liệu AI được phép truy cập.
- **Expected Benefits:** Truy cập đúng người, lưu và xóa theo chính sách được phê duyệt.

### JTBD-09 — Hiring Manager xác nhận tiêu chí và xem shortlist

- **User Tasks:** UT-02, UT-03, UT-11.
- **Current Workflow:** Hiring Manager góp ý yêu cầu chuyên môn và phối hợp đánh giá shortlist; chi tiết luồng chia sẻ hiện cần xác minh.
- **Pain Points:** P-D-01, P-P-01.
- **AI Opportunities:** AIC-01 tạo bản nháp tiêu chí; AIC-03 trình bày bằng chứng theo rubric đã được duyệt.
- **Expected Benefits:** Hiring Manager xem xét đúng phạm vi và phản hồi dựa trên tiêu chí thống nhất.

---

## 6. User Tasks — công việc thủ công hiện tại

> Yêu cầu có nhắc CRM, nhưng chưa xác nhận VinUni đang dùng CRM cụ thể nào hoặc toàn bộ thao tác diễn ra trong cùng một hệ thống. Danh sách dưới đây phản ánh các công việc thủ công hiện biết trong CRM hoặc các công cụ tuyển dụng hiện hành; cần HR xác nhận lại. Phần này chỉ ghi nhận hiện trạng, không thiết kế lại workflow.

| ID | Vai trò chính | Công việc thủ công hiện tại | Mức độ xác nhận |
|---|---|---|---|
| **UT-01** | HR | Tiếp nhận nhu cầu vị trí, quản lý thông tin vị trí và gắn JD với vị trí. | Vị trí/JD được đưa vào quy trình; công cụ cụ thể cần xác minh. |
| **UT-02** | HR, Hiring Manager | Trao đổi và làm rõ yêu cầu chuyên môn trong JD. | Đã xác nhận HR và Hiring Manager cùng xây dựng tiêu chí. |
| **UT-03** | HR, Hiring Manager | Xác nhận tiêu chí bắt buộc/ưu tiên và phê duyệt nội dung theo trách nhiệm. | Vai trò phê duyệt đã được xác định; cách ghi nhận hiện tại cần xác minh. |
| **UT-04** | HR | Tiếp nhận CV và tập hợp hồ sơ theo vị trí. | Khối lượng CV lớn đã được nêu; kênh tiếp nhận hiện tại chưa rõ. |
| **UT-05** | HR | Mở, đọc và kiểm tra CV; xử lý thủ công các file scan, bị khóa hoặc khó đọc. | Nhu cầu hỗ trợ các định dạng đã được xác nhận; tần suất từng loại cần đo. |
| **UT-06** | HR | Tìm thông tin trong CV và so sánh thủ công với JD. | Đã xác nhận là vấn đề cốt lõi. |
| **UT-07** | HR | Ghi nhận bằng chứng, nhận xét hoặc nội dung chưa rõ để phục vụ sàng lọc. | Cách ghi nhận và nơi lưu hiện cần xác minh. |
| **UT-08** | HR | Kiểm tra hồ sơ lặp lại hoặc quyết định cách xử lý khi có dấu hiệu trùng. | Nhu cầu cảnh báo trùng đã được nêu; cách làm hiện tại chưa xác nhận. |
| **UT-09** | HR | Ưu tiên hồ sơ cần rà soát trước trong tập CV của một vị trí. | Có nhu cầu ranking; baseline và cách ưu tiên hiện tại chưa được đo. |
| **UT-10** | HR | Cập nhật trạng thái hồ sơ ứng tuyển sau khi HR ra quyết định. | Các trạng thái nghiệp vụ đã được xác định; công cụ hiện tại cần xác minh. |
| **UT-11** | HR, Hiring Manager | Chia sẻ shortlist, nhận phản hồi và ghi nhận nhận xét. | Vai trò phối hợp đã được xác định; chi tiết luồng hiện tại cần xác minh. |
| **UT-12** | HR, HR Lead | Theo dõi số lượng hồ sơ, trạng thái và lập báo cáo tiến độ. | Chưa có baseline hiệu quả; cách lập báo cáo hiện tại chưa rõ. |
| **UT-13** | Admin, HR | Quản lý người dùng, quyền xem hồ sơ và cấu hình được phê duyệt. | Yêu cầu sản phẩm đã xác định; quy trình quản trị hiện tại cần xác minh. |
| **UT-14** | HR | Theo dõi ngày đóng vị trí, danh sách hồ sơ đến hạn và xác nhận xóa. | Chính sách nghiệp vụ dự kiến đã nêu; cách vận hành hiện tại và người có quyền cần xác minh. |

---

## 7. Risk Analysis

### 7.1 Business Risks

| ID | Mô tả | Tác động | Giảm thiểu |
|---|---|---|---|
| **BR-01** | Không có baseline thời gian và chất lượng sàng lọc. | Khó chứng minh hiệu quả hoặc xác định đúng KPI. | Đo baseline và thống nhất cách lấy mẫu trong pilot trước khi đặt mục tiêu giảm thời gian. |
| **BR-02** | Mở rộng nhiều nhóm vị trí hoặc tính năng trước khi pilot IT ổn định. | Scope bị phân tán, rubric và dữ liệu đánh giá không đủ sâu. | Giữ MVP ở các nhóm IT; mở rộng theo kết quả pilot và phê duyệt của HR. |
| **BR-03** | Chính sách retention và căn cứ pháp lý chưa được Legal/Privacy xác nhận. | Rủi ro áp dụng chính sách lưu/xóa không phù hợp. | Legal/Privacy rà soát trước khi dùng dữ liệu production; không tuyên bố tuân thủ chỉ dựa trên thông tin nghiệp vụ. |
| **BR-04** | HR và Hiring Manager không thống nhất rubric hoặc cách quy đổi điểm. | Ranking khó được tin cậy và khó so sánh. | Chốt rubric, mức đánh giá, trọng số và định nghĩa điểm trước khi pilot. |

### 7.2 Technical Risks

| ID | Mô tả | Tác động | Giảm thiểu |
|---|---|---|---|
| **TR-01** | PDF scan, file mờ, file khóa hoặc cấu trúc CV đa dạng làm giảm chất lượng trích xuất. | Bằng chứng thiếu hoặc sai có thể ảnh hưởng matching. | Đưa file không đọc được hoặc chưa chắc chắn vào “Cần HR kiểm tra”; đánh giá riêng theo loại file. |
| **TR-02** | AI có thể kết luận sai, tạo bằng chứng không phù hợp hoặc đánh giá thiếu một ứng viên đáp ứng tiêu chí bắt buộc. | Nguy cơ xếp hạng sai hoặc ảnh hưởng quyết định sàng lọc. | Kiểm thử với nhãn HR/Hiring Manager; hiển thị bằng chứng; không tự động loại; áp dụng ngưỡng pilot đã được phê duyệt. |
| **TR-03** | Dữ liệu CV có thể bị gửi tới dịch vụ bên ngoài hoặc được nhà cung cấp dùng ngoài mục đích cho phép. | Rủi ro quyền riêng tư và uy tín. | Ưu tiên model cục bộ; API bên ngoài chỉ dùng cho kiểm thử giai đoạn đầu; dùng dữ liệu tổng hợp hoặc đã khử định danh khi có thể; mask PII và không cho phép huấn luyện nếu chưa được phê duyệt. |
| **TR-04** | Cảnh báo trùng có thể nhầm giữa CV giống nhau và ứng viên giống nhau. | Có thể gây rà soát trùng hoặc làm người dùng hiểu nhầm hồ sơ. | Chỉ cảnh báo trong cùng vị trí; HR quyết định; không tự gộp, ghi đè hoặc xóa. |

### 7.3 User Risks

| ID | Mô tả | Tác động | Giảm thiểu |
|---|---|---|---|
| **UR-01** | Người dùng quá tin vào điểm hoặc ranking của AI. | AI có thể trở thành quyết định ngầm dù sản phẩm không được thiết kế để tự tuyển/loại. | Hiển thị bằng chứng và giới hạn sử dụng; không có ngưỡng tuyển/loại tự động; HR cập nhật trạng thái thủ công. |
| **UR-02** | Người dùng không tin kết quả vì gợi ý thiếu bằng chứng hoặc rubric không rõ. | Giảm mức sử dụng hoặc phải làm lại hoàn toàn bằng thủ công. | HR/Hiring Manager duyệt rubric; trình bày rõ bằng chứng, “Chưa rõ” và trường hợp cần xác minh. |
| **UR-03** | Quyền truy cập không phù hợp với vai trò hoặc vị trí. | Người dùng có thể xem dữ liệu không cần thiết hoặc bị ngăn khỏi hồ sơ cần xử lý. | Quyền theo vai trò và vị trí; áp dụng quyền tối thiểu; kiểm tra quyền trong pilot. |

### 7.4 Hackathon Risks

> Chưa có thông tin xác nhận dự án được triển khai dưới hình thức hackathon. Các rủi ro dưới đây chỉ áp dụng nếu có prototype/hackathon.

| ID | Mô tả | Tác động | Giảm thiểu |
|---|---|---|---|
| **HR-01** | Thời gian ngắn và dữ liệu demo không đại diện cho CV/JD thực tế. | Demo có thể hoạt động tốt nhưng không phản ánh chất lượng khi dùng thật. | Phân biệt rõ demo với pilot; đánh giá sau đó trên tập dữ liệu được HR gắn nhãn và phê duyệt. |
| **HR-02** | Prototype bị hiểu nhầm là sẵn sàng production. | Dữ liệu thật có thể được đưa vào khi chưa duyệt bảo mật, pháp lý hoặc chất lượng AI. | Gắn nhãn trạng thái prototype; không dùng CV production hoặc quyết định tuyển dụng thật trước các cổng phê duyệt. |

---

## 8. Functional Requirements

### 8.1 Vị trí và tiêu chí

- **FR-01 — Must:** Hệ thống phải cho phép quản lý vị trí tuyển dụng, JD, đơn vị phụ trách, trạng thái đóng/mở và phạm vi người dùng được giao.
- **FR-02 — Must:** AI có thể tạo **bản nháp** tiêu chí từ JD. Bản nháp phải được đánh dấu rõ là chưa phê duyệt và không được dùng để chấm/ranking chính thức trước khi duyệt.
- **FR-03 — Must:** Hiring Manager phê duyệt nội dung chuyên môn; HR xác nhận tiêu chí rõ ràng, nhất quán và phù hợp quy trình. Lưu được người phê duyệt và phiên bản tiêu chí.
- **FR-04 — Must:** Tiêu chí phải phân loại **Bắt buộc** hoặc **Ưu tiên**, có rubric gồm “Đáp ứng tốt / Đáp ứng / Chưa rõ / Chưa đáp ứng”. Trọng số mặc định là 70% Bắt buộc và 30% Ưu tiên; được điều chỉnh nhưng tổng phải bằng 100%. Cách phân bổ điểm giữa các tiêu chí và quy đổi điểm cuối cùng cần HR/Hiring Manager phê duyệt.

### 8.2 Tiếp nhận và xử lý CV

- **FR-05 — Must:** HR phải upload CV trực tiếp theo từng vị trí. MVP hỗ trợ PDF và DOCX, CV tiếng Anh; không crawl CV online. Một batch tối đa 50 file, tổng dung lượng tối đa 250 MB và mỗi file phải **nhỏ hơn 10 MB**.
- **FR-06 — Must:** PDF có văn bản được trích xuất trực tiếp; PDF scan được hỗ trợ OCR; DOCX được trích xuất văn bản thông thường, không yêu cầu OCR DOCX. MVP không hỗ trợ OCR cho ảnh CV rời.
- **FR-07 — Must:** Hệ thống phải thể hiện riêng trạng thái xử lý file: **Đã nhận / Đang xử lý / Hoàn tất / Cần HR kiểm tra / Lỗi hoặc không hỗ trợ**. PDF bị khóa, CV không đọc được hoặc quá mờ phải được chuyển **Cần HR kiểm tra**, không tự động loại.
- **FR-08 — Must:** Hệ thống cảnh báo CV giống hệt hoặc có dấu hiệu cùng ứng viên **trong cùng một vị trí**. Cảnh báo không được tự gộp, ghi đè hoặc xóa hồ sơ.
- **FR-09 — Must:** Hệ thống hỗ trợ trích xuất thông tin nghề nghiệp liên quan như kinh nghiệm, kỹ năng, học vấn và chứng chỉ. Thông tin cá nhân không liên quan đến công việc không được dùng để matching hoặc xếp hạng.

### 8.3 Matching và ranking

- **FR-10 — Must:** Với mỗi tiêu chí được phê duyệt, hệ thống phải trình bày mức đánh giá và bằng chứng tương ứng trong CV để HR có thể kiểm tra CV gốc.
- **FR-11 — Must:** Hệ thống phải phân biệt rõ:
  - **Đáp ứng tiêu chí bắt buộc** khi có đủ bằng chứng phù hợp.
  - **Cần HR xác minh** khi thiếu bằng chứng hoặc confidence thấp.
  - **Có dấu hiệu miss-match** khi có bằng chứng rõ ràng cho thấy tiêu chí bắt buộc chưa được đáp ứng.
  - **Chưa đánh giá** khi chưa có kết quả.
  
  “Có dấu hiệu miss-match” chỉ là cảnh báo để HR kiểm tra, không phải trạng thái “Bị loại”. Không tìm thấy bằng chứng không được hiểu là “Chưa đáp ứng”.
- **FR-12 — Must:** Hệ thống chỉ xếp hạng hồ sơ **trong cùng một vị trí**, dựa trên tiêu chí và trọng số đã được phê duyệt. Không xếp hạng giữa các vị trí và không dùng ngưỡng điểm để tự quyết định tuyển/loại.
- **FR-13 — Must:** Hệ thống phải thể hiện riêng điểm matching, độ phủ bằng chứng và trạng thái/mức độ chưa chắc chắn. Đề xuất ban đầu về quy đổi điểm là “Đáp ứng tốt = 100, Đáp ứng = 80, Chưa đáp ứng = 0, Chưa rõ = không tính điểm”; đây là đề xuất cần HR/Hiring Manager phê duyệt. Ngưỡng độ phủ dưới 70% để hiển thị **“Chưa đủ dữ liệu để xếp hạng ổn định”** cũng cần được phê duyệt và không phải ngưỡng tuyển dụng.
- **FR-14 — Must:** HR phải có màn hình danh sách để ưu tiên rà soát và màn hình chi tiết có bằng chứng, nhận định theo tiêu chí và CV gốc.

### 8.4 Trạng thái và phối hợp tuyển dụng

- **FR-15 — Must:** Hệ thống phải tách ba nhóm trạng thái:
  1. **Xử lý file:** Đã nhận, Đang xử lý, Hoàn tất, Cần HR kiểm tra, Lỗi/không hỗ trợ.
  2. **Matching:** Đáp ứng tiêu chí bắt buộc, Cần HR xác minh, Có dấu hiệu miss-match, Chưa đánh giá.
  3. **Hồ sơ ứng tuyển:** Mới, Đang xem, Shortlist, Bị loại ở vòng sàng lọc, Đang phỏng vấn, Không trúng tuyển sau phỏng vấn, Trúng tuyển, Đã nhận việc.
  
  Chỉ người dùng có quyền mới được cập nhật trạng thái tuyển dụng. AI không được tự cập nhật các trạng thái này.
- **FR-16 — Must:** HR có thể chia sẻ shortlist và nhận phản hồi của Hiring Manager trong phạm vi vị trí được giao. Hiring Manager không mặc định được xem toàn bộ CV của vị trí.
- **FR-17 — Must:** Phân quyền theo vai trò và vị trí:
  - HR Recruiter: xem hồ sơ/matching/ranking và cập nhật trạng thái trong vị trí được giao.
  - Hiring Manager: duyệt tiêu chí chuyên môn, xem shortlist được chia sẻ.
  - HR Lead: xem dashboard tổng hợp; xem CV chi tiết chỉ khi được cấp quyền.
  - Admin: quản lý user/quyền/cấu hình được duyệt; không mặc định xem CV hoặc xác nhận xóa.
  - Viewer: chỉ xem số liệu tổng hợp, không xem CV/PII.
  - HR được cấp quyền là người xác nhận xóa hồ sơ.
- **FR-18 — Must:** MVP dùng email và mật khẩu nội bộ. SSO không thuộc MVP.

### 8.5 Dữ liệu, retention và đo lường

- **FR-19 — Must:** Chỉ cho phép sử dụng model/API đã được phê duyệt. Ưu tiên model cục bộ; API bên ngoài chỉ dùng để kiểm thử ở giai đoạn đầu. Nếu dùng API phải có biện pháp mask PII; mask không được xem là ẩn danh tuyệt đối. Không cho phép nhà cung cấp dùng CV để huấn luyện nếu chưa được phê duyệt.
- **FR-20 — Must, pending Legal/Privacy:** Thời hạn lưu dự kiến là 12 tháng tính từ ngày đóng vị trí; theo quyết định nghiệp vụ hiện tại, áp dụng cả hồ sơ chưa có kết quả và không có thời hạn riêng cho hồ sơ Trúng tuyển/Đã nhận việc.
- **FR-21 — Must, pending Legal/Privacy:** Khi đến hạn, hệ thống đưa hồ sơ vào danh sách chờ; không tự động xóa nếu HR chưa xác nhận.
- **FR-22 — Must:** Nếu vị trí được mở lại trước khi hồ sơ bị xóa, bộ đếm retention được tính lại từ lần đóng vị trí tiếp theo.
- **FR-23 — Must:** Xóa theo từng hồ sơ ứng tuyển; không tự xóa hồ sơ của cùng ứng viên ở các vị trí khác.
- **FR-24 — Must:** Ghi nhận các sự kiện kiểm toán quan trọng như phê duyệt tiêu chí, thay đổi trạng thái tuyển dụng, điều chỉnh kết quả AI, thay đổi quyền, cấu hình model và xác nhận xóa.
- **FR-25 — Must:** HR Lead có dashboard số liệu tổng hợp theo vị trí và trạng thái; xem CV chi tiết chỉ khi được cấp quyền.
- **FR-26 — Must:** Pilot phải ghi nhận dữ liệu cần thiết để đo baseline và hiệu quả, tối thiểu gồm thời gian rà soát mẫu, tỷ lệ hồ sơ cần HR kiểm tra, mức HR điều chỉnh gợi ý AI và chất lượng ranking. Chưa đặt KPI giảm thời gian cố định trước khi có baseline.
- **FR-27 — Must:** Giao diện hỗ trợ tiếng Việt và tiếng Anh; tiếng Việt là ngôn ngữ mặc định. CV và JD trong MVP dùng tiếng Anh.

---

## 9. Non-Functional Requirements

| ID | Nhóm | Yêu cầu | Trạng thái |
|---|---|---|---|
| **NFR-01** | Performance | Hệ thống phải hiển thị trạng thái xử lý theo file và cho HR biết file nào đang xử lý hoặc cần kiểm tra. Chưa có SLA thời gian xử lý được phê duyệt; thời gian mục tiêu cần xác định trong pilot. | Chưa chốt ngưỡng thời gian. |
| **NFR-02** | Security | Quyền truy cập phải dựa trên vai trò và vị trí; áp dụng nguyên tắc quyền tối thiểu. Viewer không xem CV/PII; Admin không mặc định xem CV hoặc xóa hồ sơ. | Chi tiết theo tiêu chuẩn nội bộ VinUni cần xác nhận. |
| **NFR-03** | Deployment | Chỉ sử dụng trong môi trường được VinUni phê duyệt. Pilot giới hạn theo vị trí, người dùng và dữ liệu đã được duyệt; chỉ mở rộng khi các phê duyệt bảo mật, Legal/Privacy và chất lượng AI hoàn tất. | Không quy định kiến trúc hoặc cách triển khai. |
| **NFR-04** | Scalability | MVP phải hỗ trợ batch tối đa 50 file, tổng tối đa 250 MB và mỗi file nhỏ hơn 10 MB. Khối lượng sau pilot và nhu cầu mở rộng nhóm vị trí cần được xác định bằng số liệu thực tế. | Có giới hạn MVP; chưa có mục tiêu tăng trưởng dài hạn. |
| **NFR-05** | Maintainability | Rubric, trọng số, tiêu chí được duyệt và lựa chọn model được quản lý có kiểm soát, có phiên bản và truy vết thay đổi. Mọi thay đổi ảnh hưởng kết quả AI cần được đánh giá lại trước khi mở rộng sử dụng. | Yêu cầu nghiệp vụ; không quy định cách triển khai. |
| **NFR-06** | Usability | Giao diện song ngữ, mặc định tiếng Việt; phân biệt rõ bằng chứng, điểm matching, độ phủ, trạng thái file, matching và tuyển dụng. Ước lượng ban đầu 30 giây–2 phút cho danh sách, 2–5 phút xem chi tiết và 1–2 phút xem shortlist chỉ là giả định trải nghiệm, không phải SLA hoặc acceptance criteria. | Cần kiểm tra qua pilot. |
| **NFR-07** | Auditability | Có thể truy xuất người thực hiện, thời điểm, vị trí, phiên bản tiêu chí và thay đổi liên quan đến phê duyệt, trạng thái, quyền và xóa hồ sơ. | Nội dung và thời hạn lưu audit cần chốt. |
| **NFR-08** | Reliability / Data Integrity | Lỗi từng file phải hiển thị rõ, không làm mất trạng thái các file khác trong batch. Cảnh báo trùng không được tự gộp, ghi đè hoặc xóa hồ sơ. | Cần xác nhận quy trình xử lý lỗi và khôi phục. |
| **NFR-09** | Privacy | Nếu dùng API bên ngoài để test, ưu tiên dữ liệu tổng hợp hoặc đã khử định danh; mask PII khi cần thiết. Không gửi dữ liệu production tới dịch vụ ngoài nếu chưa có phê duyệt phù hợp. | Phụ thuộc phê duyệt Legal/Privacy và IT/Security. |

---

## 10. AI Requirements

### 10.1 AI Capability Map

| ID | Năng lực AI | Phạm vi | Business Goals |
|---|---|---|---|
| **AIC-01** | Hiểu JD và đề xuất bản nháp tiêu chí | Đề xuất, không tự phê duyệt. | BG-01, BG-06, BG-07 |
| **AIC-02** | Trích xuất và cấu trúc nội dung CV | Tập trung vào thông tin nghề nghiệp liên quan. | BG-03, BG-04, BG-08 |
| **AIC-03** | Matching theo từng tiêu chí và trình bày bằng chứng | Chỉ dùng tiêu chí đã được duyệt. | BG-01, BG-03, BG-04, BG-06, BG-07 |
| **AIC-04** | Xếp hạng hồ sơ trong cùng một vị trí | Hỗ trợ ưu tiên rà soát; không tự quyết định tuyển dụng. | BG-03, BG-04, BG-07 |
| **AIC-05** | Nhận diện không chắc chắn và chuyển trường hợp cần HR xác minh | Không coi thiếu bằng chứng là không đáp ứng. | BG-02, BG-04, BG-07, BG-08 |
| **AIC-06** | Cảnh báo CV có khả năng trùng trong cùng vị trí | Chỉ cảnh báo; HR quyết định cách xử lý. | BG-03, BG-08 |

### 10.2 Yêu cầu AI theo năng lực

- **Planning:** AI chỉ được đánh giá CV theo JD và bộ tiêu chí đã được HR/Hiring Manager duyệt. AI không tự tạo hoặc thay đổi quy trình tuyển dụng, không tự chuyển ứng viên sang vòng tiếp theo.
- **Tool Calling:** Các hành động AI được giới hạn ở việc đọc dữ liệu được phép trong vị trí hiện tại, trích xuất thông tin, tạo bản nháp, matching, ranking và cảnh báo. AI không được tự cập nhật trạng thái ứng tuyển, xóa hồ sơ, gửi quyết định cho ứng viên hoặc truy cập CV thuộc vị trí không được phép.
- **Context Management:** Khi đánh giá, AI chỉ được dùng JD, phiên bản rubric đã duyệt và CV thuộc cùng vị trí. Không trộn dữ liệu giữa ứng viên hoặc giữa các vị trí. Chỉ dùng dữ liệu cần thiết cho đánh giá.
- **Explainability:** Mỗi nhận định phải gắn với bằng chứng trong CV khi có thể. Hiển thị riêng điểm matching, độ phủ bằng chứng và trạng thái chưa rõ/confidence. HR phải truy ngược được nhận định về CV gốc.
- **Reasoning:** Nhận định phải dựa trên tiêu chí được duyệt và bằng chứng có trong CV; không suy diễn thông tin chưa có. Không tìm thấy bằng chứng hoặc confidence thấp phải thành “Cần HR xác minh”, không được coi là “Chưa đáp ứng”. Không cần hiển thị reasoning nội bộ ẩn của model; cần hiển thị lý do ngắn gọn, có căn cứ và kiểm chứng được.
- **Personalization:** Chỉ cá nhân hóa theo yêu cầu, rubric và trọng số đã được phê duyệt cho từng vị trí. Không cá nhân hóa theo sở thích riêng của người đánh giá, thuộc tính nhạy cảm hoặc lịch sử quyết định chưa được duyệt.
- **Human Approval:** HR/Hiring Manager duyệt tiêu chí; HR xác minh ngoại lệ và cập nhật trạng thái tuyển dụng. AI không tự động loại, shortlist hoặc thay đổi kết quả tuyển dụng.

### 10.3 Giới hạn đánh giá AI

AI không được dùng các thông tin sau để đánh giá ứng viên:

- Tuổi, giới tính, ngoại hình hoặc ảnh.
- Tình trạng hôn nhân.
- “Culture fit”, tính cách hoặc các thuộc tính cá nhân không liên quan trực tiếp đến công việc.

### 10.4 Đề xuất đánh giá chất lượng AI cho pilot

Các chỉ số dưới đây là **đề xuất ban đầu**, chưa được HR/Hiring Manager phê duyệt:

- Tập dữ liệu mục tiêu khoảng 300 cặp CV–JD–rubric; tối thiểu đề xuất 200 cặp nếu dữ liệu cho phép.
- Bao phủ các nhóm Software Engineer, QA, DevOps, Data Engineer và IT Support nếu đủ dữ liệu.
- Có nhãn HR/Hiring Manager; tách dữ liệu kiểm thử theo vị trí/JD; ghi nhận và xử lý bất đồng giữa người đánh giá.
- Chỉ số đề xuất:
  - F1 ≥ 0,85 cho trích xuất kỹ năng, kinh nghiệm, học vấn và chứng chỉ.
  - Macro-F1 ≥ 0,80 cho matching theo tiêu chí.
  - Tỷ lệ ứng viên được chuyên gia xác nhận đáp ứng tiêu chí bắt buộc nhưng AI kết luận “Chưa đáp ứng” ≤ 5%.
  - Ít nhất 90% nhận định “Chưa đáp ứng” có bằng chứng phù hợp.
  - Ít nhất 95% bằng chứng trích dẫn hỗ trợ nhận định tương ứng.
  - NDCG@5 ≥ 0,75 cho ranking.
  - 100% file không đọc được được chuyển sang “Cần HR kiểm tra”.
  - 0 trường hợp AI tự cập nhật trạng thái tuyển dụng.
- Các ngưỡng này phải được xem xét lại sau khi HR đánh giá chất lượng tập dữ liệu; không phải tiêu chí nghiệm thu cuối cùng ở trạng thái hiện tại.

---

## 11. Requirement Traceability Matrix

| Business Goal | JTBD | User Tasks | Pain Points | AI Opportunity | Functional Requirements |
|---|---|---|---|---|---|
| BG-01, BG-06, BG-07 | JTBD-01 | UT-01, UT-02, UT-03 | P-D-01 | AIC-01 | FR-01–FR-04 |
| BG-02, BG-03, BG-08 | JTBD-02 | UT-04, UT-05 | P-O-01, P-O-02, P-P-03 | AIC-02, AIC-06 | FR-05–FR-09, FR-17, FR-19 |
| BG-01, BG-03, BG-04, BG-06, BG-07 | JTBD-03 | UT-06, UT-07 | P-O-01, P-D-02, P-D-04 | AIC-02, AIC-03, AIC-05 | FR-09–FR-11, FR-14 |
| BG-03, BG-04, BG-07 | JTBD-04 | UT-09 | P-O-01, P-D-03 | AIC-03, AIC-04 | FR-12–FR-14 |
| BG-02, BG-04, BG-07, BG-08 | JTBD-05 | UT-05, UT-08 | P-O-02, P-O-03, P-D-04, P-P-02 | AIC-05, AIC-06 | FR-07, FR-08, FR-11, FR-13 |
| BG-01, BG-07, BG-08 | JTBD-06 | UT-10, UT-11 | P-P-01, P-P-02 | AIC-03 chỉ hỗ trợ bằng chứng; không dùng AI để cập nhật trạng thái | FR-15, FR-16, FR-24 |
| BG-05, BG-08 | JTBD-07 | UT-12 | P-O-04 | Không cần AI; số liệu tổng hợp phải kiểm tra được | FR-25, FR-26 |
| BG-02, BG-08 | JTBD-08 | UT-13, UT-14 | P-P-03, P-P-02 | Không cần AI để quyết định quyền hoặc xóa dữ liệu | FR-17–FR-24 |
| BG-01, BG-06, BG-07 | JTBD-09 | UT-02, UT-03, UT-11 | P-D-01, P-P-01 | AIC-01, AIC-03 | FR-02–FR-04, FR-16 |

---

## 12. Requirement Summary

### Top 5 business priorities

1. Chuẩn hóa cách HR và Hiring Manager diễn giải tiêu chí tuyển dụng.
2. Giảm công sức đọc và đối chiếu CV thủ công; đo baseline trước khi đặt KPI.
3. Giúp HR ưu tiên hồ sơ phù hợp và giảm nguy cơ bỏ sót ứng viên.
4. Bảo đảm kết quả AI có bằng chứng và không thay thế quyết định của HR.
5. Quản lý dữ liệu, quyền truy cập và vòng đời hồ sơ có kiểm soát.

### Top 5 product priorities

1. Quản lý JD, vị trí và tiêu chí đã được phê duyệt.
2. Upload và xử lý batch CV PDF/DOCX, có nhận diện file lỗi và ngoại lệ.
3. Matching theo tiêu chí với bằng chứng kiểm chứng được.
4. Ranking trong cùng vị trí, kèm điểm, độ phủ bằng chứng và cảnh báo chưa chắc chắn.
5. Tách trạng thái file, matching và tuyển dụng; hỗ trợ phân quyền, audit và retention.

### Top 5 AI capabilities

1. Đề xuất bản nháp tiêu chí từ JD — **AIC-01**.
2. Trích xuất thông tin nghề nghiệp từ CV — **AIC-02**.
3. Matching từng tiêu chí với bằng chứng trong CV — **AIC-03**.
4. Ranking trong cùng vị trí — **AIC-04**.
5. Nhận diện trường hợp chưa chắc chắn và CV có dấu hiệu trùng — **AIC-05, AIC-06**.

### Recommended MVP scope

- Pilot tuyển dụng non-faculty với các nhóm IT đã nêu.
- CV/JD tiếng Anh; giao diện song ngữ, mặc định tiếng Việt.
- Upload trực tiếp PDF/DOCX theo giới hạn batch và file.
- AI tạo bản nháp tiêu chí; HR/Hiring Manager duyệt trước khi sử dụng.
- Trích xuất nội dung, matching theo tiêu chí và hiển thị bằng chứng.
- Ranking chỉ trong cùng vị trí; không tự động tuyển, loại hoặc cập nhật trạng thái.
- Cảnh báo file không đọc được, thiếu bằng chứng hoặc có dấu hiệu trùng để HR xác minh.
- Phân quyền theo vai trò/vị trí, dashboard cơ bản, audit và pilot measurement.
- Retention 12 tháng từ ngày đóng vị trí là yêu cầu nghiệp vụ dự kiến, cần Legal/Privacy xác nhận trước khi áp dụng production.

### Hướng phát triển sau MVP — chưa thuộc MVP

1. **Tái sàng lọc kho CV theo JD mới:** chỉ dùng hồ sơ còn được phép tái sử dụng và chưa đến hạn xóa; cần xác nhận với Legal/Privacy về consent, thông báo và retention.
2. **Thư viện JD/rubric template:** bắt đầu với nhóm IT, sau đó xem xét Admin, Marketing, Finance và Student Affairs; mẫu phải được HR/Hiring Manager rà soát theo từng vị trí.
3. **Booking phỏng vấn:** quản lý lịch, xác nhận, nhắc và đổi lịch; không thuộc MVP.
4. **Đánh giá online/offline:** bài đánh giá gắn với công việc, có rubric và không tự động loại ứng viên.
5. **Tự động hỗ trợ feedback:** AI có thể soạn nháp/tổng hợp feedback; HR duyệt trước khi gửi.
6. **Đo lường hiệu quả nâng cao:** phân tích funnel và kết quả tuyển dụng sau khi có baseline và dữ liệu phù hợp.

