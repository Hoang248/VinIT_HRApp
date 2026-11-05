# Wireframe mô tả giao diện — Phase 1

**Sản phẩm:** VinUni AI-Native CV Matching & Ranking  
**Phạm vi:** Phase 1 — MVP/Pilot  
**Phiên bản:** 1.0  
**Trạng thái:** Draft — cần HR, Product, Legal/Privacy và IT/Security rà soát  
**Đường dẫn đề xuất:** `docs/interface-wireframes.md`

> Tài liệu mô tả wireframe ở mức cấu trúc và hành vi màn hình; không phải thiết kế visual cuối cùng hoặc bản đặc tả implementation. Tài liệu được xây dựng dựa trên Product Definition, Requirement Analysis, Solution Architecture và Interface Contracts hiện có — tất cả đều đang ở trạng thái draft.

## 1. Mục tiêu và phạm vi

Giao diện Phase 1 hỗ trợ HR tiếp nhận, rà soát và ưu tiên CV cho các vị trí **không phải giảng viên**. Pilot ưu tiên các vị trí IT: Software Engineer, QA, DevOps, Data Engineer và IT Support.

Giao diện cần hỗ trợ luồng chính:

1. Tạo vị trí và nhập JD.
2. Tạo tiêu chí sàng lọc dạng nháp từ JD, để HR và Hiring Manager rà soát, phê duyệt.
3. Upload trực tiếp CV theo vị trí.
4. Xem trạng thái xử lý file, matching và hồ sơ ứng tuyển một cách riêng biệt.
5. Xem matching có dẫn chứng và ranking trong **cùng một vị trí**.
6. HR tự cập nhật trạng thái ứng tuyển và chia sẻ shortlist cho Hiring Manager.
7. Theo dõi báo cáo, cấu hình quyền, quản trị AI được phê duyệt và xử lý retention/xóa dữ liệu.

### Ngoài phạm vi Phase 1

Không đưa vào wireframe Phase 1: crawl CV online, candidate portal, tự động loại hoặc shortlist, tự động đổi trạng thái ứng tuyển, email tự động cho ứng viên, ATS/HRIS integration, Talent Pool, CV rediscovery, đặt lịch phỏng vấn, video screening hoặc dự đoán khả năng nhận offer.

## 2. Nguyên tắc thiết kế

1. **HR quyết định tuyển dụng.** AI không tự loại ứng viên, shortlist, đổi trạng thái ứng tuyển, gửi quyết định cho ứng viên hoặc xóa hồ sơ.
2. **Hiển thị bằng chứng trước kết luận.** Mỗi nhận định AI cần liên kết đến đoạn CV và vị trí trong tài liệu để HR kiểm tra.
3. **Tách riêng ba nhóm trạng thái:**
   - Xử lý file.
   - Matching.
   - Hồ sơ ứng tuyển.
4. **Tách riêng điểm matching, độ phủ bằng chứng và độ tin cậy.** Không gộp thành một chỉ số chung.
5. **Không có bằng chứng hoặc độ tin cậy thấp không có nghĩa là “Chưa đáp ứng”.** Chuyển sang HR xác minh.
6. Ranking chỉ so sánh hồ sơ trong cùng một vị trí và chỉ hỗ trợ ưu tiên rà soát.
7. Không dùng tuổi, giới tính, ngoại hình/ảnh, tình trạng hôn nhân, tính cách hoặc “culture fit” để đánh giá ứng viên.
8. Phân quyền theo vai trò và vị trí. Người dùng chỉ xem được hồ sơ trong phạm vi được cấp.
9. Mặc định giao diện tiếng Việt, có tùy chọn tiếng Anh. JD và CV trong MVP bằng tiếng Anh.
10. Các ngưỡng, công thức điểm, confidence band và chỉ số báo cáo chỉ được hiển thị như giá trị vận hành sau khi được phê duyệt.

## 3. Vai trò và phạm vi truy cập

| Vai trò | Phạm vi giao diện chính |
|---|---|
| HR Recruiter | Quản lý vị trí được giao; upload và rà soát CV; xem bằng chứng, matching, ranking; tự cập nhật trạng thái ứng tuyển; chia sẻ shortlist. |
| Hiring Manager | Rà soát/phê duyệt tiêu chí chuyên môn; xem hồ sơ được chia sẻ; gửi phản hồi. Không mặc định xem toàn bộ CV của vị trí. |
| HR Lead | Xem dashboard và báo cáo tổng hợp; xem hồ sơ chi tiết chỉ khi được cấp quyền. |
| Admin | Quản lý user/quyền và cấu hình AI trong danh sách được phê duyệt. Không mặc định xem CV hoặc xác nhận xóa hồ sơ. |
| Viewer | Xem số liệu tổng hợp; không xem CV hoặc PII. |
| Legal/Privacy, IT/Security | Xem các màn hình retention, audit hoặc quản trị được cấp quyền; không mặc định có quyền xem CV. |

Quyền cụ thể tại từng vị trí vẫn cần xác nhận theo chính sách phân quyền của VinUni.

## 4. Cấu trúc điều hướng chung

### 4.1 App shell

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ VinUni AI-Native CV Matching     [VI/EN] [Tác vụ đang xử lý] [Tài khoản] │
├──────────────┬───────────────────────────────────────────────────────────┤
│ Tổng quan    │ Breadcrumb                                                │
│ Vị trí       │ Tiêu đề trang                             [Tác vụ chính] │
│ Báo cáo      │                                                           │
│              │ Nội dung trang                                            │
│ Quản trị*    │                                                           │
└──────────────┴───────────────────────────────────────────────────────────┘
* Chỉ hiển thị cho vai trò được cấp quyền
```

- Điều hướng trái hiển thị theo vai trò.
- Không có tìm kiếm CV toàn hệ thống nếu người dùng không có quyền xuyên vị trí.
- “Tác vụ đang xử lý” mở bảng theo dõi tác vụ bất đồng bộ như trích xuất CV, matching hoặc ranking.
- Tài khoản gồm thông tin người dùng, đổi ngôn ngữ và đăng xuất.

### 4.2 Điều hướng trong một vị trí

```text
[Vị trí]  Tổng quan | JD | Tiêu chí | Hồ sơ ứng tuyển | Xếp hạng | Chia sẻ shortlist
```

Tab hiển thị tùy quyền. Khi vị trí đóng, thao tác upload hoặc chạy đánh giá mới bị ẩn/vô hiệu hóa theo chính sách được duyệt.

## 5. Quy ước trạng thái trên giao diện

| Nhóm | Giá trị hiển thị | Quy tắc |
|---|---|---|
| **Xử lý file** | Đã nhận / Đang xử lý / Hoàn tất / Cần HR kiểm tra / Lỗi hoặc không hỗ trợ | Trạng thái của file và công đoạn đọc/trích xuất; không phải kết quả tuyển dụng. |
| **Matching** | Đáp ứng tiêu chí bắt buộc / Cần HR xác minh / Có dấu hiệu miss-match / Chưa đánh giá | “Có dấu hiệu miss-match” là cảnh báo để HR xem bằng chứng, không phải loại hồ sơ. |
| **Hồ sơ ứng tuyển** | Mới / Đang xem / Shortlist / Bị loại ở vòng sàng lọc / Đang phỏng vấn / Không trúng tuyển sau phỏng vấn / Trúng tuyển / Đã nhận việc | Chỉ người được cấp quyền mới cập nhật trạng thái. AI không cập nhật. |
| **Vị trí** | Draft / Open / Closed | Trạng thái vị trí, tách biệt với trạng thái hồ sơ ứng tuyển. |

Trong danh sách hồ sơ và trang chi tiết, ba nhóm trạng thái cần nằm ở các trường hoặc badge riêng; không gộp thành một nhãn “Trạng thái ứng viên”.

Nếu thiếu bằng chứng hoặc confidence thấp, UI hiển thị **“Cần HR xác minh”**. Không tự chuyển thành “Chưa đáp ứng”, không tự gán điểm 0 và không tự loại hồ sơ.

## 6. Danh mục màn hình Phase 1

| ID | Màn hình | Người dùng chính | Liên kết năng lực |
|---|---|---|---|
| S-01 | Đăng nhập | Tất cả người dùng | CAP-09 |
| S-02 | Tổng quan | HR, HR Lead, Viewer | CAP-08 |
| S-03 | Danh sách vị trí | HR | CAP-01 |
| S-04 | Tạo/sửa vị trí và JD | HR | CAP-01 |
| S-05 | Workspace một vị trí | HR, Hiring Manager theo quyền | CAP-01–08 |
| S-06 | Tiêu chí và phê duyệt | HR, Hiring Manager | CAP-01, CAP-02 |
| S-07 | Upload CV | HR | CAP-03 |
| S-08 | Kết quả xử lý batch | HR | CAP-03, CAP-05 |
| S-09 | Danh sách hồ sơ ứng tuyển | HR | CAP-03–06 |
| S-10 | Ranking trong vị trí | HR | CAP-04, CAP-05 |
| S-11 | Chi tiết hồ sơ và bằng chứng | HR; Hiring Manager nếu được chia sẻ | CAP-04, CAP-06 |
| S-12 | Cập nhật trạng thái ứng tuyển | HR | CAP-06 |
| S-13 | Tạo/chia sẻ shortlist | HR | CAP-07 |
| S-14 | Shortlist được chia sẻ và phản hồi | Hiring Manager | CAP-07 |
| S-15 | Báo cáo tuyển dụng | HR, HR Lead, Viewer theo quyền | CAP-08 |
| S-16 | Chất lượng AI/pilot | HR Lead, người được cấp quyền | CAP-08 |
| S-17 | Quản lý user và quyền | Admin | CAP-09 |
| S-18 | Cấu hình AI được phê duyệt | Admin | CAP-10 |
| S-19 | Danh sách chờ xác nhận xóa | HR được cấp quyền | CAP-11 |
| S-20 | Nhật ký audit | Người được cấp quyền | CAP-11 |
| S-21 | Bảng tác vụ đang xử lý | Người khởi tạo tác vụ | Các CAPI bất đồng bộ |

---

# 7. Mô tả wireframe chi tiết

## S-01 — Đăng nhập

```text
┌─────────────────────────────────────────────┐
│       VinUni AI-Native CV Matching          │
│                                             │
│  Email nội bộ                               │
│  [_______________________________________]  │
│                                             │
│  Mật khẩu                                   │
│  [_______________________________________]  │
│                                             │
│  [ Đăng nhập ]                 [VI / EN]   │
│                                             │
│  Truy cập theo quyền được cấp.              │
└─────────────────────────────────────────────┘
```

- MVP dùng email/mật khẩu nội bộ; không thiết kế SSO ở Phase 1.
- Không cho người dùng tự chọn vai trò tại màn hình đăng nhập.
- Lỗi đăng nhập hiển thị thông báo và hướng dẫn liên hệ bộ phận hỗ trợ nội bộ; không tiết lộ dữ liệu ứng viên.
- Chính sách MFA và quy trình đặt lại mật khẩu cần được IT/Security xác nhận.

## S-02 — Tổng quan

```text
┌────────────────────────────────────────────────────────────────────┐
│ Tổng quan                                      [ + Tạo vị trí ]    │
├────────────────┬────────────────┬────────────────┬────────────────┤
│ Vị trí đang mở │ Cần HR xem      │ File cần kiểm  │ Chờ phê duyệt  │
│       N        │       N         │ tra: N         │ tiêu chí: N    │
├──────────────────────────────────────┬─────────────────────────────┤
│ Vị trí của tôi                       │ Việc cần xử lý              │
│ Vị trí | Hồ sơ | Tiêu chí | Cập nhật │ - Duyệt tiêu chí            │
│ ...                                  │ - Kiểm tra file lỗi          │
│                                      │ - Xem cảnh báo trùng         │
└──────────────────────────────────────┴─────────────────────────────┘
```

- Số liệu chỉ tính trong phạm vi người dùng được phép xem.
- Các thẻ đếm không gộp file lỗi, matching cần xác minh và trạng thái tuyển dụng.
- “Việc cần xử lý” thay đổi theo vai trò:
  - HR: tiêu chí chờ rà soát, file cần kiểm tra, cảnh báo trùng.
  - Hiring Manager: tiêu chí chờ phê duyệt, shortlist chờ phản hồi.
  - HR Lead/Viewer: chỉ số tổng hợp theo quyền.
- Không hiển thị KPI tiết kiệm thời gian hoặc ROI như kết quả đã đạt khi chưa có baseline.

## S-03 — Danh sách vị trí

```text
┌────────────────────────────────────────────────────────────────────┐
│ Vị trí tuyển dụng                                [ + Tạo vị trí ] │
│ [Tìm theo tên vị trí________] [Trạng thái ▾] [Recruiter ▾]         │
├────────────────────────────────────────────────────────────────────┤
│ Vị trí       | Recruiter | Hiring Manager | Vị trí | Tiêu chí | CV │
│ Software Eng | ...       | ...            | Open   | Chờ duyệt| 24 │
│ QA Engineer  | ...       | ...            | Draft  | Chưa có  |  0 │
└────────────────────────────────────────────────────────────────────┘
```

- Lọc theo vị trí Draft/Open/Closed và các bộ lọc được phép.
- Bảng có thể hiển thị: tên vị trí, Recruiter, Hiring Manager, trạng thái vị trí, phiên bản/trạng thái tiêu chí, số hồ sơ, số hồ sơ cần HR xem, lần cập nhật gần nhất.
- Chỉ hiển thị vị trí nằm trong phạm vi truy cập.
- Không có hành động xóa vị trí trực tiếp từ bảng.
- Mở một dòng sẽ vào S-05.

## S-04 — Tạo/sửa vị trí và JD

```text
┌────────────────────────────────────────────────────────────────────┐
│ Tạo vị trí mới                                                     │
├────────────────────────────────────────────────────────────────────┤
│ Thông tin vị trí                                                   │
│ Tên vị trí *         [________________________________________]   │
│ Đơn vị (nếu có)      [________________________________________]   │
│ Recruiter *          [________________________________________]   │
│ Hiring Manager *     [________________________________________]   │
│                                                                    │
│ Mô tả công việc (JD) — tiếng Anh                                  │
│ [ Dán hoặc nhập nội dung JD ................................... ] │
│ [ ................................................................]│
│                                                                    │
│ [Lưu nháp] [Lưu và tạo tiêu chí nháp]                              │
└────────────────────────────────────────────────────────────────────┘
```

- `Tên vị trí`, Recruiter, Hiring Manager và nội dung JD là các trường dự kiến; danh mục trường cuối cùng cần khớp với hệ thống nhân sự hiện có.
- Wireframe mặc định JD được nhập/dán dạng văn bản. Việc hỗ trợ upload file JD là quyết định cần xác nhận, không mặc định nằm trong MVP.
- Mỗi lần lưu JD mới tạo một phiên bản JD để truy vết tiêu chí và kết quả đánh giá.
- “Lưu và tạo tiêu chí nháp” chỉ yêu cầu AI tạo đề xuất; không duyệt hoặc phát hành tiêu chí.
- Không yêu cầu người tạo nhập model hoặc threshold.

## S-05 — Workspace của một vị trí

```text
┌────────────────────────────────────────────────────────────────────┐
│ Software Engineer | Open             [Đóng vị trí] [Upload CV]    │
│ Recruiter: ...   Hiring Manager: ...   Mã vị trí: ...              │
├────────────────────────────────────────────────────────────────────┤
│ Tổng quan | JD | Tiêu chí | Hồ sơ | Xếp hạng | Shortlist | Lịch sử │
├────────────────────────────────────────────────────────────────────┤
│ JD: v3                         Tiêu chí: v2 — Chờ Hiring Manager   │
│ Hồ sơ đã nhận: N               Cần HR kiểm tra: N                  │
│ Matching cần xác minh: N       Có dấu hiệu miss-match: N            │
│                                                                    │
│ Hoạt động gần đây / Các việc cần thực hiện                         │
└────────────────────────────────────────────────────────────────────┘
```

- Header luôn giữ ngữ cảnh vị trí hiện tại.
- Các số đếm thể hiện riêng trạng thái file, matching và hồ sơ ứng tuyển.
- Nếu chưa có tiêu chí được duyệt, hiển thị banner **“Chưa thể chạy matching/ranking cho đến khi tiêu chí được phê duyệt.”**
- Thao tác đóng/mở vị trí cần theo quyền và ghi nhận lịch sử.
- Khi vị trí đóng, các tab giữ khả năng xem dữ liệu được phép; upload hoặc chạy đánh giá mới theo quy tắc được duyệt.

## S-06 — Tiêu chí và phê duyệt

```text
┌────────────────────────────────────────────────────────────────────┐
│ Tiêu chí sàng lọc — JD v3                                          │
│ Phiên bản: Draft v1       Nhãn: AI đề xuất — chưa được phê duyệt   │
├───────────────────────────────┬────────────────────────────────────┤
│ Danh sách tiêu chí             │ Phê duyệt                          │
│ [Bắt buộc] Tiêu chí 1          │ HR xác nhận: Chưa hoàn tất         │
│ Mô tả / nguồn trích từ JD      │ Hiring Manager: Chưa phê duyệt     │
│ [Ưu tiên] Tiêu chí 2           │                                    │
│ Mô tả / nguồn trích từ JD      │ [Gửi HR rà soát]                   │
│ ...                            │ [Gửi Hiring Manager phê duyệt]     │
├───────────────────────────────┴────────────────────────────────────┤
│ [Lưu nháp] [Thêm tiêu chí] [Xem trước rubric] [Tạo phiên bản mới]  │
└────────────────────────────────────────────────────────────────────┘
```

Mỗi thẻ tiêu chí hiển thị:

- Tên và mô tả tiêu chí.
- Phân loại: **Bắt buộc** hoặc **Ưu tiên**.
- Đoạn JD làm căn cứ đề xuất.
- Hướng dẫn HR xác định bằng chứng phù hợp.
- Trọng số nếu rubric đã được phê duyệt.
- Mức đánh giá theo rubric đã được phê duyệt.

Hành vi:

- Bản nháp do AI đề xuất luôn mang nhãn **“Chưa được phê duyệt”**.
- HR kiểm tra tính rõ ràng, nhất quán và phù hợp quy trình.
- Hiring Manager rà soát/phê duyệt nội dung chuyên môn.
- Chỉ hiển thị tiêu chí là **Đã duyệt** khi các bước phê duyệt bắt buộc đã hoàn tất.
- Chỉnh sửa tiêu chí hoặc JD tạo phiên bản mới; không thay đổi ngược kết quả của phiên bản cũ.
- Nếu phát hiện tiêu chí liên quan đến tuổi, giới tính, ngoại hình/ảnh, hôn nhân, tính cách hoặc “culture fit”, hiển thị cảnh báo và yêu cầu xem xét lại.
- Trọng số, rubric và cách tính tổng cần được cấu hình từ policy đã phê duyệt. Tỷ lệ Bắt buộc/Ưu tiên 70%/30% hiện chỉ là đề xuất, chưa được HR/HM/PO chốt.
- Mức đánh giá dự kiến gồm “Đáp ứng tốt / Đáp ứng / Chưa rõ / Chưa đáp ứng”. “Chưa rõ” không được tự động chuyển thành điểm 0.

## S-07 — Upload CV theo vị trí

```text
┌────────────────────────────────────────────────────────────────────┐
│ Upload CV — Software Engineer                                      │
│ Chỉ upload hồ sơ cho vị trí đang mở này.                           │
├────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Kéo thả file vào đây hoặc [Chọn file]                        │   │
│ │ PDF có văn bản, PDF scan, DOCX                                │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│ Tối đa 50 file/batch | Tổng tối đa 250 MB | Mỗi file < 10 MB      │
│                                                                    │
│ Tên file                 | Loại | Kích thước | Kiểm tra | Thao tác │
│ CV_01.pdf                | PDF  | ...        | Hợp lệ   | Bỏ chọn  │
│                                                                    │
│ [Hủy]                                      [Upload CV]             │
└────────────────────────────────────────────────────────────────────┘
```

- MVP nhận CV bằng upload trực tiếp.
- PDF có văn bản được trích xuất trực tiếp; PDF scan sử dụng OCR; DOCX trích xuất văn bản thông thường.
- PDF khóa, nội dung không đọc được hoặc quá mờ được chuyển **Cần HR kiểm tra**.
- Nếu chưa có tiêu chí được duyệt, vẫn có thể tiếp nhận file nếu được phép, nhưng UI cảnh báo rằng matching/ranking chưa chạy được.
- Hệ thống không tự gộp, ghi đè hoặc xóa các CV trùng.
- Quy tắc giới hạn hiện là **mỗi file nhỏ hơn 10 MB**, batch không quá 50 file và tổng không quá 250 MB. Đơn vị MB/MiB và cách xử lý file đúng 10 MB cần được xác nhận trước production.

## S-08 — Kết quả xử lý batch

```text
┌────────────────────────────────────────────────────────────────────┐
│ Batch upload #...                     Đang xử lý / Hoàn tất        │
│ Vị trí: Software Engineer             Đã nhận: N file              │
├────────────────────────────────────────────────────────────────────┤
│ Tên file     | Xử lý file      | Matching       | Cảnh báo | Mở     │
│ CV_01.pdf    | Hoàn tất         | Chưa đánh giá  | Không   | Xem    │
│ CV_02.pdf    | Cần HR kiểm tra  | Chưa đánh giá  | Đọc mờ  | Kiểm tra│
│ CV_03.docx   | Đang xử lý       | Chưa đánh giá  | —       | —      │
└────────────────────────────────────────────────────────────────────┘
```

- Hiển thị trạng thái theo từng file và trạng thái chung của batch.
- “Hoàn tất” trong cột xử lý file không đồng nghĩa với “đã đánh giá matching”.
- Nếu đọc file không được, hiển thị lý do dễ hiểu và hành động phù hợp, ví dụ xem file hoặc upload bản khác.
- CV có thể trùng được hiển thị dưới dạng cảnh báo, kèm liên kết đến hồ sơ có khả năng trùng trong cùng vị trí.
- Hành động chỉ cho phép HR xem xét; không có “Gộp”, “Ghi đè” hoặc “Xóa tự động”.
- Lỗi hệ thống chỉ hiển thị nút thử lại khi tác vụ được phép retry; không retry lỗi quyền hoặc lỗi dữ liệu không hợp lệ.

## S-09 — Danh sách hồ sơ ứng tuyển

```text
┌────────────────────────────────────────────────────────────────────┐
│ Hồ sơ ứng tuyển — Software Engineer                [Upload CV]     │
│ [Tìm tên/file____] [Xử lý file ▾] [Matching ▾] [Hồ sơ ▾] [Trùng ▾]│
├────────────────────────────────────────────────────────────────────┤
│ Ứng viên/file | Xử lý file | Matching | Hồ sơ ứng tuyển | Trùng  │
│ ...           | ...        | ...      | ...              | ...    │
├────────────────────────────────────────────────────────────────────┤
│ [Xem danh sách]                                      [Xếp hạng →] │
└────────────────────────────────────────────────────────────────────┘
```

- Các bộ lọc xử lý file, matching, trạng thái hồ sơ và cảnh báo trùng tách biệt.
- Số liệu, tên ứng viên và nội dung CV chỉ hiển thị theo quyền.
- Các ứng viên chưa được đánh giá vẫn có thể xuất hiện với matching **Chưa đánh giá**.
- Không có thao tác hàng loạt để AI loại, shortlist hoặc đổi trạng thái tuyển dụng.

## S-10 — Ranking trong cùng vị trí

```text
┌────────────────────────────────────────────────────────────────────┐
│ Xếp hạng — Software Engineer — chỉ so sánh trong vị trí này        │
│ Thứ tự xếp hạng chỉ hỗ trợ HR ưu tiên rà soát.                    │
│ Không tự động shortlist hoặc loại hồ sơ.                           │
├────────────────────────────────────────────────────────────────────┤
│ Hạng | Ứng viên | Điểm matching | Độ phủ bằng chứng | Confidence   │
│ 1    | ...      | ...           | ...               | ...          │
│ 2    | ...      | ...           | ...               | ...          │
├────────────────────────────────────────────────────────────────────┤
│ Chưa đủ dữ liệu để xếp hạng ổn định: N hồ sơ                      │
│ Cần HR xác minh: N hồ sơ | Chưa đánh giá: N hồ sơ                  │
└────────────────────────────────────────────────────────────────────┘
```

- Có banner cố định: **“Ranking chỉ hỗ trợ ưu tiên rà soát, không phải quyết định tuyển dụng.”**
- Nếu chính sách được phê duyệt, hiển thị riêng:
  - Thứ hạng trong vị trí.
  - Điểm matching.
  - Độ phủ bằng chứng.
  - Độ tin cậy.
  - Tình trạng đáp ứng tiêu chí bắt buộc.
- Không tạo ranking xuyên nhiều vị trí.
- Không xếp hạng ổn định hồ sơ có độ phủ dưới ngưỡng đã được phê duyệt; ngưỡng 70% hiện là đề xuất, chưa được xác nhận.
- Nếu thiếu dữ liệu hoặc không đủ bằng chứng, UI ghi rõ **“Chưa đủ dữ liệu để xếp hạng ổn định”**, không gán điểm 0.
- Có thể mở hồ sơ để xem bằng chứng và cách đánh giá. Hành động mở hồ sơ không tự thay đổi trạng thái tuyển dụng.

## S-11 — Chi tiết hồ sơ và bằng chứng

```text
┌────────────────────────────────────────────────────────────────────┐
│ Nguyễn A. | Software Engineer                                      │
│ Xử lý file: Hoàn tất | Matching: Cần HR xác minh                    │
│ Hồ sơ ứng tuyển: Đang xem          [Cập nhật trạng thái]            │
├───────────────────────────┬────────────────────────────────────────┤
│ CV gốc                    │ Tổng quan | Tiêu chí & bằng chứng      │
│                           │                                        │
│ [Trang 1 / N]             │ Điểm matching: ...                     │
│ [Hiển thị CV]             │ Độ phủ bằng chứng: ...                 │
│                           │ Độ tin cậy: ...                        │
│                           │                                        │
│                           │ [Tiêu chí bắt buộc] ...                │
│                           │ Kết quả | Bằng chứng | Trang trong CV  │
└───────────────────────────┴────────────────────────────────────────┘
```

Phần đầu trang luôn phân biệt:

1. Trạng thái xử lý file.
2. Trạng thái matching.
3. Trạng thái hồ sơ ứng tuyển.

Mỗi thẻ tiêu chí có:

- Tên tiêu chí và phân loại Bắt buộc/Ưu tiên.
- Mức đánh giá theo rubric được duyệt.
- Trích dẫn bằng chứng từ CV.
- Vị trí nguồn, ví dụ số trang hoặc đoạn.
- Confidence theo cách hiển thị đã được phê duyệt.

Các quy tắc hiển thị:

- Nếu không tìm thấy bằng chứng: **“Chưa tìm thấy bằng chứng — Cần HR xác minh.”**
- Nếu confidence thấp: hiển thị lý do cần xác minh, không chuyển thành “Chưa đáp ứng”.
- “Chưa đáp ứng” chỉ xuất hiện khi có bằng chứng đủ rõ về việc không đạt tiêu chí.
- “Có dấu hiệu miss-match” chỉ là cảnh báo cần HR kiểm tra, không phải hành động loại.
- Hồ sơ trùng hiển thị thẻ cảnh báo riêng; HR tự quyết định cách xử lý.
- Không hiển thị tuổi, giới tính, ngoại hình/ảnh, tình trạng hôn nhân hoặc tính cách như thuộc tính đánh giá.
- Mọi tóm tắt AI phải ngắn gọn, có nguồn bằng chứng và không hiển thị chain-of-thought.

## S-12 — Cập nhật trạng thái hồ sơ ứng tuyển

```text
┌──────────────────────────────────────────────────────┐
│ Cập nhật trạng thái hồ sơ                            │
│                                                      │
│ Trạng thái hiện tại: Đang xem                       │
│ Trạng thái mới:      [Chọn trạng thái hợp lệ ▾]     │
│                                                      │
│ [Ghi chú, nếu được chính sách cho phép]              │
│                                                      │
│ Thao tác này do HR thực hiện. AI không đổi trạng thái.│
│                                                      │
│ [Hủy]                                 [Xác nhận]     │
└──────────────────────────────────────────────────────┘
```

- Danh sách trạng thái gồm: Mới, Đang xem, Shortlist, Bị loại ở vòng sàng lọc, Đang phỏng vấn, Không trúng tuyển sau phỏng vấn, Trúng tuyển, Đã nhận việc.
- UI chỉ cho chọn chuyển trạng thái được cho phép theo transition matrix được duyệt.
- Với lựa chọn “Bị loại ở vòng sàng lọc”, hiển thị xác nhận rõ ràng rằng đây là quyết định của người dùng, không phải hành động do AI.
- Có thể ghi nhận người thao tác, thời điểm, trạng thái trước/sau và ghi chú nếu chính sách cho phép.
- Transition matrix và việc có bắt buộc nhập lý do hay không vẫn cần HR xác nhận.

## S-13 — Tạo và chia sẻ shortlist

```text
┌────────────────────────────────────────────────────────────────────┐
│ Chia sẻ hồ sơ với Hiring Manager                                  │
│ Người nhận: [Hiring Manager được phân công ▾]                     │
│                                                                    │
│ Chọn hồ sơ muốn chia sẻ                                            │
│ [x] Ứng viên A | Matching ... | Trạng thái hồ sơ ...               │
│ [ ] Ứng viên B | Matching ... | Trạng thái hồ sơ ...               │
│                                                                    │
│ Nội dung/ghi chú gửi kèm (nếu được phép)                           │
│ [______________________________________________________________]   │
│                                                                    │
│ [Hủy]                                    [Tạo chia sẻ]             │
└────────────────────────────────────────────────────────────────────┘
```

- HR chọn rõ hồ sơ muốn chia sẻ; không chia sẻ tự động toàn bộ hồ sơ của vị trí.
- Chỉ người nhận được phân công/cấp quyền mới xem được nội dung được chia sẻ.
- Chia sẻ shortlist không tự động chuyển trạng thái ứng tuyển sang “Shortlist”.
- Nếu HR cần đổi trạng thái ứng tuyển, thao tác đó thực hiện riêng tại S-12.
- Không thiết kế gửi email tự động trong Phase 1.

## S-14 — Shortlist được chia sẻ và phản hồi của Hiring Manager

```text
┌────────────────────────────────────────────────────────────────────┐
│ Danh sách được chia sẻ với tôi                                     │
│ Vị trí | Chia sẻ bởi | Ngày chia sẻ | Mở                          │
├────────────────────────────────────────────────────────────────────┤
│ Software Engineer | HR Recruiter | ... | [Xem shortlist]           │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ Shortlist: Software Engineer                                      │
│ Hồ sơ được chia sẻ: A, B, C                                        │
│ [Mở hồ sơ được cấp quyền]                                          │
│                                                                    │
│ Phản hồi chuyên môn                                                │
│ [______________________________________________________________]   │
│ [Gửi phản hồi]                                                     │
└────────────────────────────────────────────────────────────────────┘
```

- Hiring Manager chỉ xem các hồ sơ đã được chia sẻ và tài liệu được cấp quyền.
- Có thể gửi phản hồi theo hồ sơ hoặc nội dung chia sẻ.
- Phản hồi không tự thay đổi trạng thái tuyển dụng; HR là người cập nhật trạng thái.
- Quyền xem CV gốc của Hiring Manager cần được xác nhận rõ trước production.

## S-15 — Báo cáo tuyển dụng

```text
┌────────────────────────────────────────────────────────────────────┐
│ Báo cáo tuyển dụng                                                 │
│ [Khoảng thời gian ▾] [Vị trí ▾]                                    │
├────────────────────────────────────────────────────────────────────┤
│ Tổng hồ sơ | Vị trí đang mở | Hồ sơ cần xem | File cần kiểm tra   │
├────────────────────────────────────────────────────────────────────┤
│ Funnel trạng thái hồ sơ ứng tuyển                                  │
│ Mới → Đang xem → Shortlist → Đang phỏng vấn → Kết quả             │
├────────────────────────────────────────────────────────────────────┤
│ Các ngoại lệ                                                        │
│ Xử lý file | Matching cần HR xác minh | Cảnh báo trùng             │
└────────────────────────────────────────────────────────────────────┘
```

- Báo cáo tách funnel trạng thái tuyển dụng khỏi trạng thái file và matching.
- Viewer chỉ xem số liệu tổng hợp, không xem PII hoặc CV.
- HR/HR Lead chỉ xem dữ liệu trong phạm vi quyền.
- Định nghĩa các chỉ số, thời gian đo và cách tính funnel cần được chốt.
- Không hiển thị cam kết giảm thời gian hoặc ROI trước khi có baseline pilot.

## S-16 — Chất lượng AI và đo pilot

```text
┌────────────────────────────────────────────────────────────────────┐
│ Chất lượng AI / Pilot                                              │
│ [Vị trí ▾] [Khoảng thời gian ▾] [Phiên bản policy/model ▾]         │
├────────────────┬────────────────┬────────────────┬────────────────┤
│ Xử lý file     │ Kết quả OCR    │ Độ phủ bằng    │ Hồ sơ cần HR  │
│ ...            │ ...            │ chứng ...      │ xác minh ...  │
├────────────────────────────────────────────────────────────────────┤
│ Xu hướng theo batch / vị trí                                       │
│ [Bảng hoặc biểu đồ theo định nghĩa đã phê duyệt]                   │
│                                                                    │
│ Chỉ số chưa đủ dữ liệu: ...                                       │
└────────────────────────────────────────────────────────────────────┘
```

- Mục đích là đo chất lượng và khả năng vận hành trong pilot, không phải đánh giá năng lực tuyển dụng của ứng viên.
- Có thể hiển thị các nhóm chỉ số về xử lý file/OCR, độ phủ bằng chứng và số hồ sơ cần HR xác minh sau khi định nghĩa được thống nhất.
- Không đặt target/KPI giả định nếu chưa có baseline.
- Chỉ hiển thị breakdown theo model/policy version khi người dùng có quyền.
- Các metric cụ thể cần được HR, Product và IT/Security xác nhận.

## S-17 — Quản lý user và quyền

```text
┌────────────────────────────────────────────────────────────────────┐
│ Quản lý quyền                                                      │
│ [Tìm người dùng____] [Vai trò ▾] [Vị trí ▾]                        │
├────────────────────────────────────────────────────────────────────┤
│ Người dùng | Vai trò | Vị trí được truy cập | Trạng thái | Thao tác │
│ ...        | ...     | ...                  | ...        | [Sửa]    │
└────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────┐
│ Cập nhật quyền               │
│ Vai trò: [............. ▾]   │
│ Vị trí:  [.............]     │
│ [Lưu thay đổi]               │
└──────────────────────────────┘
```

- Admin chỉ quản lý các user và phạm vi quyền được cho phép.
- Quyền theo vị trí được thể hiện rõ, tránh cấp mặc định quyền xem CV toàn hệ thống.
- Admin không mặc định có quyền xem CV hoặc xác nhận xóa hồ sơ.
- Mọi thay đổi quyền được ghi audit.
- Khả năng tạo user mới và cơ chế cấp tài khoản cần khớp với hệ thống identity nội bộ hiện có.

## S-18 — Cấu hình AI được phê duyệt

```text
┌────────────────────────────────────────────────────────────────────┐
│ Cấu hình AI đang hoạt động                                         │
│ Model/provider: ...      Phiên bản: ...      Policy: ...           │
│ Trạng thái phê duyệt: ...                                          │
├────────────────────────────────────────────────────────────────────┤
│ Các lựa chọn được phê duyệt                                        │
│ [Chọn một cấu hình đã được phê duyệt ▾]                            │
│                                                                    │
│ Fallback: Chỉ dùng cấu hình được phê duyệt                         │
│ [Xem chi tiết policy]                                              │
│                                                                    │
│ [Hủy]                                       [Lưu cấu hình]          │
└────────────────────────────────────────────────────────────────────┘
```

- Người dùng cuối không nhập tên model, provider hoặc threshold tùy ý.
- Admin chỉ chọn từ danh sách đã được phê duyệt.
- Ưu tiên model cục bộ; API ngoài chỉ sử dụng khi được duyệt theo policy.
- Nếu dùng API ngoài để kiểm thử, việc sử dụng dữ liệu CV phải tuân theo policy, masking và phê duyệt. Masking không đồng nghĩa với ẩn danh tuyệt đối.
- Không cho phép fallback tự động sang provider chưa được duyệt.
- Thay đổi cấu hình cần tạo dấu vết audit và không tự thay đổi kết quả đánh giá cũ.

## S-19 — Danh sách chờ xác nhận xóa

```text
┌────────────────────────────────────────────────────────────────────┐
│ Hồ sơ đến hạn xem xét retention                                    │
│ Policy áp dụng: [Phiên bản policy đã duyệt]                        │
├────────────────────────────────────────────────────────────────────┤
│ Vị trí | Hồ sơ | Ngày đóng | Ngày đến hạn | Trạng thái | Mở       │
│ ...    | ...   | ...       | ...          | Chờ xác nhận | ...    │
├────────────────────────────────────────────────────────────────────┤
│ Chọn hồ sơ: [Xác nhận xóa hồ sơ đã chọn]                           │
└────────────────────────────────────────────────────────────────────┘
```

- Retention 12 tháng tính từ ngày đóng vị trí hiện là **đề xuất**, chưa được Legal/Privacy xác nhận.
- Giao diện không tự xóa dữ liệu khi đến hạn; hồ sơ chỉ vào danh sách chờ HR được cấp quyền xác nhận.
- Màn hình xác nhận xóa cần nói rõ phạm vi hồ sơ ứng tuyển và dữ liệu sẽ bị xóa theo policy đã duyệt.
- Việc xác nhận xóa một hồ sơ ứng tuyển không tự xóa hồ sơ cùng ứng viên ở vị trí khác.
- Nếu vị trí mở lại trước khi xóa, thời hạn được tính lại theo quy tắc đã nêu trong BRD.
- Admin không mặc định có quyền xác nhận xóa.
- Mọi thao tác xóa cần audit. Không cho xóa trực tiếp bằng thao tác AI.

## S-20 — Nhật ký audit

```text
┌────────────────────────────────────────────────────────────────────┐
│ Nhật ký audit                                                      │
│ [Thời gian ▾] [Người dùng ▾] [Loại thao tác ▾] [Vị trí ▾]         │
├────────────────────────────────────────────────────────────────────┤
│ Thời gian | Người thực hiện | Loại thao tác | Đối tượng | Kết quả  │
│ ...       | ...             | ...           | ...       | ...      │
└────────────────────────────────────────────────────────────────────┘
```

- Ghi nhận các thao tác quan trọng như thay đổi quyền, duyệt tiêu chí, upload, cập nhật trạng thái ứng tuyển, chia sẻ shortlist, thay đổi cấu hình AI và xác nhận xóa.
- Chỉ người được cấp quyền xem audit.
- Không hiển thị nội dung CV hoặc PII không cần thiết trong log.
- Phạm vi truy cập audit và thời hạn lưu log cần IT/Security và Legal/Privacy xác nhận.

## S-21 — Tác vụ đang xử lý

```text
┌────────────────────────────────────────────────────────────────────┐
│ Tác vụ đang xử lý                                                  │
├────────────────────────────────────────────────────────────────────┤
│ Tác vụ | Vị trí | Trạng thái tác vụ | Bắt đầu | Kết quả/thao tác   │
│ CV batch | ...  | Đang xử lý         | ...     | [Mở batch]         │
│ Matching | ...  | Hoàn tất một phần  | ...     | [Xem kết quả]      │
└────────────────────────────────────────────────────────────────────┘
```

- Trạng thái tác vụ là trạng thái xử lý kỹ thuật, không phải trạng thái file, matching hoặc hồ sơ ứng tuyển.
- Có thể dùng các nhãn thân thiện như “Đang xử lý”, “Hoàn tất”, “Hoàn tất một phần”, “Cần hành động” hoặc “Thất bại” khi được thống nhất.
- Chỉ hiện “Thử lại” nếu thao tác được phép retry theo contract và không tạo hồ sơ trùng.
- Với lỗi cần HR xử lý, hiển thị bước tiếp theo thay vì yêu cầu người dùng hiểu mã lỗi kỹ thuật.

# 8. Các luồng tương tác chính

## 8.1 Tạo vị trí và phê duyệt tiêu chí

```text
S-03 Danh sách vị trí
  → S-04 Tạo vị trí và JD
  → S-06 Tạo tiêu chí nháp từ JD
  → HR rà soát, chỉnh sửa và xác nhận
  → Hiring Manager phê duyệt tiêu chí chuyên môn
  → Hiển thị phiên bản tiêu chí Đã duyệt
```

Nếu JD hoặc tiêu chí thay đổi, tạo phiên bản mới; không sửa ngược kết quả đánh giá của phiên bản cũ.

## 8.2 Upload và rà soát CV

```text
S-05 Workspace vị trí
  → S-07 Upload CV
  → S-21 Theo dõi tác vụ
  → S-08 Kết quả batch
      ├─ Hoàn tất → có thể tiếp tục matching nếu tiêu chí đã duyệt
      ├─ Cần HR kiểm tra → mở file và xác minh
      └─ Lỗi/không hỗ trợ → xử lý file; không tự loại hồ sơ
```

## 8.3 Matching, ranking và quyết định của HR

```text
S-09 Danh sách hồ sơ
  → S-10 Ranking cùng vị trí
  → S-11 Chi tiết hồ sơ và bằng chứng
  → S-12 HR tự cập nhật trạng thái ứng tuyển
  → S-13 HR chia sẻ shortlist nếu cần
  → S-14 Hiring Manager gửi phản hồi
```

Ranking hoặc cảnh báo miss-match không tự cập nhật trạng thái ứng tuyển.

## 8.4 Retention và xóa

```text
Vị trí đóng
  → Chờ thời hạn theo retention policy đã duyệt
  → S-19 Đưa vào danh sách chờ xác nhận
  → HR được cấp quyền kiểm tra phạm vi
  → HR xác nhận xóa theo hồ sơ ứng tuyển
  → Ghi audit
```

# 9. Trạng thái rỗng, lỗi và cảnh báo cần thiết kế

| Tình huống | Nội dung UI cần thể hiện |
|---|---|
| Chưa có tiêu chí được duyệt | Cảnh báo chưa thể chạy matching/ranking; liên kết đến S-06. |
| PDF khóa, CV mờ hoặc không đọc được | “Cần HR kiểm tra”; không tự loại ứng viên. |
| Không tìm thấy bằng chứng cho tiêu chí | “Chưa tìm thấy bằng chứng — Cần HR xác minh”; không hiển thị “Chưa đáp ứng”. |
| Độ phủ bằng chứng thấp | Nêu chưa đủ dữ liệu; không tạo thứ hạng ổn định nếu chính sách đã quy định ngưỡng. |
| CV có thể trùng trong cùng vị trí | Cảnh báo và liên kết xem xét; không tự gộp hoặc xóa. |
| Tác vụ đang chạy | Hiển thị tiến trình/trạng thái và cho phép rời trang mà không tạo tác vụ lặp. |
| Không có quyền | Thông báo không có quyền xem hoặc thao tác; không tiết lộ dữ liệu bị hạn chế. |
| Không có dữ liệu theo bộ lọc | Hiển thị trạng thái rỗng và cách bỏ bộ lọc; không gây hiểu nhầm rằng không có hồ sơ trong hệ thống. |

Thông báo trạng thái nên dùng cả biểu tượng và chữ, không phụ thuộc duy nhất vào màu sắc.

# 10. Truy vết với tài liệu sản phẩm

| Nhóm màn hình | Business goals / JTBD | Capability | Acceptance criteria liên quan |
|---|---|---|---|
| S-02 Tổng quan, S-15 Báo cáo, S-16 Chất lượng AI | BG-05, JTBD-07 | CAP-08 | AC-11 |
| S-03, S-04, S-05 | BG-06, JTBD-01, JTBD-02 | CAP-01 | AC-01 |
| S-06 Tiêu chí | BG-01, BG-06, JTBD-01 | CAP-01, CAP-02 | AC-01, AC-12 |
| S-07, S-08 Upload và xử lý CV | BG-02, BG-03, JTBD-02, JTBD-05 | CAP-03 | AC-02, AC-03, AC-06 |
| S-09, S-10, S-11 Hồ sơ, bằng chứng, ranking | BG-01, BG-04, BG-07, JTBD-03, JTBD-04, JTBD-05 | CAP-04, CAP-05 | AC-04, AC-05, AC-06 |
| S-12 Cập nhật trạng thái | BG-07, BG-08, JTBD-06 | CAP-06 | AC-07 |
| S-13, S-14 Chia sẻ và phản hồi | BG-01, BG-07, JTBD-09 | CAP-07 | AC-14 |
| S-17 Quyền truy cập | BG-02, BG-08, JTBD-08 | CAP-09 | AC-08 |
| S-18 Cấu hình AI | BG-02, BG-07, JTBD-08 | CAP-10 | AC-12 |
| S-19, S-20 Retention và audit | BG-02, BG-08, JTBD-08 | CAP-11 | AC-09, AC-10 |

# 11. Các quyết định cần chốt trước khi hoàn thiện wireframe

1. Xác nhận các trường dữ liệu vị trí và nguồn thông tin vị trí hiện có.
2. JD trong MVP được nhập/dán văn bản hay có thêm upload file.
3. Rubric đánh giá, cách quy đổi điểm, độ phủ bằng chứng, confidence bands và ngưỡng xếp hạng.
4. Tỷ trọng Bắt buộc/Ưu tiên 70%/30%; hiện chưa được phê duyệt.
5. Trạng thái matching và transition matrix cho trạng thái hồ sơ ứng tuyển.
6. Có bắt buộc ghi lý do khi HR chuyển hồ sơ sang “Bị loại ở vòng sàng lọc” hay không.
7. Quyền của Hiring Manager đối với CV gốc, thông tin cá nhân và bằng chứng chi tiết.
8. Giới hạn file đúng 10 MB và cách định nghĩa MB/MiB.
9. SSO/MFA và các yêu cầu bảo mật đăng nhập.
10. Các chỉ số báo cáo, baseline và cách đo chất lượng AI trong pilot.
11. Retention 12 tháng và phạm vi dữ liệu sẽ xóa; cần Legal/Privacy phê duyệt trước production.
12. Căn cứ **Luật 91/2025** do người dùng nêu cần được Legal/Privacy đối chiếu độc lập; tài liệu này không khẳng định nội dung luật đã được xác minh.
13. Vai trò được phép xem audit và thời hạn lưu audit log.
14. Metric hoặc thao tác ghi nhận HR chỉnh sửa/phản hồi kết quả AI, nếu muốn đưa vào MVP.

**Lưu ý:** Đây là wireframe draft cho Phase 1, không phải bản nghiệm thu cuối cùng. Các điểm chưa được phê duyệt cần được giải quyết trước khi chốt UX và bắt đầu implementation.