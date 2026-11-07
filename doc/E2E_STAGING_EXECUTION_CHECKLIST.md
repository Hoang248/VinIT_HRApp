# Checklist thực thi E2E staging Phase 1

> Tài liệu này biến runbook tổng quát tại [`E2E_STAGING.md`](E2E_STAGING.md) thành checklist thực thi từng bước. Chỉ chạy trên staging tách biệt với dữ liệu tổng hợp trong `staging/synthetic`. Việc chuẩn bị checklist và dữ liệu **không** đồng nghĩa E2E đã đạt; chỉ khi có bằng chứng chạy thật và ký duyệt mới được cập nhật Closure Review.

## 1. Bộ dữ liệu đi kèm

- Manifest: `staging/synthetic/manifest.json`
- CV nguồn dạng text: `staging/synthetic/candidates/*.txt`
- Script sinh DOCX để upload:

```bash
backend/.venv/bin/python backend/scripts/generate_staging_fixtures.py --check
backend/.venv/bin/python backend/scripts/generate_staging_fixtures.py
```

DOCX sinh ra nằm trong `staging/generated/` và đã được ignore khỏi Git. Không sửa manifest thành dữ liệu thật; mọi email phải giữ miền `example.test`, số điện thoại phải là số tổng hợp chứa `000`.

Bộ dữ liệu này là **smoke/E2E fixture**, không phải HR golden set để đo chất lượng matching/BGE/LTR. Không dùng kỳ vọng trong manifest để tuyên bố accuracy production.

## 2. Vai trò thực hiện

| Vai trò | Người thực hiện | Việc chính |
|---|---|---|
| Điều phối staging | DevOps/IT | Dựng môi trường, deploy commit, ghi migration versions, cấp quyền tạm thời |
| Admin staging | Admin được chỉ định | Kiểm tra Admin APIs, audit verify, LTR governance nếu thuộc vòng chạy |
| HR Lead | HR Lead staging | Dual approval, xác nhận/thực thi retention từng case |
| HR Recruiter | HR staging | Tạo position/JD/criteria, upload CV, chạy assessment/ranking, shortlist |
| Hiring Manager | HM staging | Phê duyệt criteria, xem shortlist đúng quyền, gửi feedback |
| Người ghi bằng chứng | Điều phối hoặc QA | Điền bảng kết quả, đính kèm log/screenshot đã che dữ liệu nhạy cảm |

Không ghi mật khẩu, API key, access token hoặc service-role key vào checklist/báo cáo. Mật khẩu tài khoản staging lưu trong password manager của đội.

## 3. Preflight trước khi chạy

Đánh dấu từng mục trước khi bắt đầu:

- [ ] Ghi commit SHA của backend/frontend sẽ test: `________________`
- [ ] Ghi URL staging và xác nhận không phải production: `________________`
- [ ] Database staging đã áp migration theo thứ tự; ghi version thực tế, bắt buộc có `00012_retention_audit_integrity` nếu test retention/audit: `________________`
- [ ] Supabase project staging là project riêng hoặc đã được phê duyệt dùng cho dữ liệu tổng hợp: `________________`
- [ ] Storage buckets `cv-originals`, `cv-extracted-text` là private trên staging.
- [ ] Đã tạo các tài khoản trong manifest: Admin, HR Lead, HR Recruiter, Hiring Manager, Outsider.
- [ ] Backend staging dùng code chứa Batch 5 (`cce75b5` hoặc mới hơn) cho API `/v1/retention` và `/v1/admin/audit/verify`.
- [ ] `LTR_MODE=OFF` cho vòng E2E chức năng đầu tiên.
- [ ] Nếu chưa có phê duyệt privacy/egress: LLM/BGE dùng endpoint local/mock đã được phép trong staging; không gửi CV thật ra ngoài.
- [ ] Log của API/worker trong thời gian test được kiểm tra để bảo đảm không có CV text, prompt đầy đủ, API key hoặc access token.

## 4. Chuẩn bị dữ liệu trong ứng dụng

1. Sinh DOCX từ bộ fixture bằng script ở mục 1.
2. Đăng nhập Admin/HR Lead; tạo department `Synthetic Engineering` theo manifest nếu staging chưa có.
3. HR Recruiter tạo position `backend_open` theo JD/criteria trong manifest; gán:
   - HR Recruiter: `HR_RECRUITER`
   - Hiring Manager: `HIRING_MANAGER`
   - Outsider: không gán
4. Tạo criteria `python_backend`, `postgresql`, `docker` đúng category/trọng số trong manifest; thực hiện HR approve và HM approve bằng hai tài khoản khác nhau.
5. Upload các DOCX của `backend_open`: strong, partial, java only, Vietnamese, duplicate A/B. Không upload vào position production hoặc position chứa dữ liệu thật.
6. Tạo position `retention_due` và `retention_not_due` trên staging; upload candidate tương ứng.
   - Với `retention_not_due`: đóng position ở thời điểm hiện tại.
   - Với `retention_due`: chỉ trên database staging tách biệt và có ticket phê duyệt, điều phối mới được đặt `positions.closed_at` lùi 13 tháng sau khi position đã đóng để mô phỏng hết hạn. Ghi operator, thời gian và ticket vào bằng chứng. Tuyệt đối không làm việc này trên production/project chứa dữ liệu thật.
7. Nếu test OCR: dùng `ocr_simulated.txt` để tạo PDF scan/image-only ngoài Git bằng công cụ staging đã được phê duyệt; ghi rõ công cụ và độ phân giải. File text không tự chứng minh OCR đạt.

## 5. Kịch bản thực thi

Điền `PASS`/`FAIL`, người chạy, thời gian và liên kết bằng chứng cho từng dòng.

| ID | Kịch bản | Các bước chính | Kỳ vọng | Kết quả/Bằng chứng |
|---|---|---|---|---|
| E2E-01 | Auth/RBAC position scope | Đăng nhập từng user; mở danh sách/chi tiết `backend_open`; thử bằng Outsider | Chỉ user được gán mới thấy position/application; Outsider bị từ chối hoặc không thấy dữ liệu |  |
| E2E-02 | Admin surfaces | Gọi `/v1/admin/semantic/health`, `/v1/admin/ltr/models`, `/v1/admin/worker/health` bằng non-admin và Admin | Non-admin 403; Admin 200; health không lộ endpoint/API key/CV text |  |
| E2E-03 | JD/criteria dual approval | Sửa criteria sau APPROVED; thử approve trùng vai trò | Bản APPROVED bị khóa; HR/HM khác nhau mới hoàn tất dual approval |  |
| E2E-04 | Upload + profile | Upload DOCX strong/partial/java/Vietnamese; mở profile từng application | File hợp lệ được xử lý; profile facts truy vết về document; sửa profile tạo version mới, không trộn assessment cũ |  |
| E2E-05 | Matching theo kỳ vọng manifest | Chạy assessment cho `backend_open`; đối chiếu từng criterion | Strong/partial/java/Vietnamese khớp kỳ vọng tương đối trong manifest; UNCLEAR không bị tính như NO_MATCH trong score; quote mở đúng nguồn |  |
| E2E-06 | Scoring `matching-v2.1` | Kiểm tra case partial có Docker UNCLEAR | Score chỉ tính trên tiêu chí đã scored; coverage giảm; giao diện/API hiển thị nhu cầu HR xác minh khi coverage thấp |  |
| E2E-07 | Ranking | Chạy ranking cho `backend_open` | Ranking tôn trọng mandatory status trước score/coverage; snapshot truy vết được assessment/profile/criteria versions |  |
| E2E-08 | Duplicate signal | Đối chiếu duplicate A/B | Có tín hiệu trùng theo email/phone nếu hệ thống ghi nhận; không tự merge, không tự xóa hồ sơ |  |
| E2E-09 | Shortlist/feedback/revoke | HR chia sẻ strong cho HM với `allow_cv_view=false`, HM feedback, HR revoke | HM chỉ thấy dữ liệu được chia sẻ; không tải CV khi không có quyền; sau revoke HM mất truy cập |  |
| E2E-10 | Audit verify | Non-admin rồi Admin gọi `GET /v1/admin/audit/verify` | Non-admin 403; Admin trả `valid=true`. Nếu `false`: dừng, không sửa audit rows, mở defect |  |
| E2E-11 | Retention chưa đến hạn | Generate case cho `retention_not_due` | `created_count=0`; không có case để confirm trước hạn |  |
| E2E-12 | Retention đến hạn + phân quyền confirm | Generate cho `retention_due`; HR Recruiter thử confirm; HR Lead confirm | Có 1 case `is_due=true`; HR Recruiter không có grant bị 403; HR Lead confirm thành `SCHEDULED_FOR_DELETION` |  |
| E2E-13 | Retention execute + purge | HR Lead execute case ở E2E-12; kiểm tra application/file/audit | File gốc/extracted/pages bị xóa; profile/assessment/evidence/ranking/shortlist/embeddings/notes bị purge hoặc unlink; bằng chứng còn lại chỉ có opaque ID/counts, không có PII |  |
| E2E-14 | OCR scan | Upload PDF scan tạo từ fixture OCR; kiểm tra extracted text/profile | OCR có kết quả hoặc lỗi rõ ràng; quote/page được HR kiểm chứng thủ công; không tuyên bố chất lượng OCR chỉ từ fixture text |  |
| E2E-15 | Semantic/BGE smoke (nếu thuộc vòng) | Bật cấu hình BGE đã duyệt; kiểm tra semantic health và embeddings | Không ở `MISCONFIGURED`; có diagnostics/cache hợp lý; semantic chỉ bổ sung candidate chunks, không tự đổi rule outcome |  |
| E2E-16 | Worker recovery (nếu môi trường cho phép) | Tạo job tổng hợp, restart worker/API theo quy trình staging, theo dõi job | Job phục hồi at-least-once hoặc fail rõ; không mất mát âm thầm; không tuyên bố exactly-once |  |

## 6. Mẫu bằng chứng cần nộp

Sau khi chạy, đính kèm hoặc liên kết:

- Commit SHA, URL staging, migration versions thực tế.
- Bảng kịch bản ở mục 5 đã điền PASS/FAIL.
- Screenshot/log đã che email/token/API key/CV text ngoài dữ liệu tổng hợp.
- Provider/model LLM/BGE đã dùng (không ghi secret), hoặc ghi rõ đã dùng mock/local.
- Kết quả `GET /v1/admin/audit/verify` từ Admin staging.
- Với retention: case ID, trạng thái trước/sau, deletion job status, audit verify sau execute. Không đính kèm CV thật.
- Danh sách defect: mức độ, bước tái hiện, log liên quan, người phụ trách, quyết định chặn hay chấp nhận rủi ro.

## 7. Điều kiện ký duyệt vòng E2E

Chỉ ký PASS vòng staging khi:

- Không có rò rỉ position scope, CV hoặc assessment evidence ngoài quyền.
- Không có UNCLEAR bị tính như NO_MATCH trong status/score.
- Không có quote không hợp lệ được tính điểm.
- Retention chưa đến hạn bị chặn; retention đến hạn chỉ xóa sau confirm + execute thủ công từng case.
- Audit verify trả `valid=true`, hoặc defect integrity được mở và chặn phát hành.
- Log kiểm tra không chứa API key, access token, prompt đầy đủ hoặc CV text thật.

Ký duyệt:

| Vai trò | Họ tên | Kết luận | Ngày |
|---|---|---|---|
| Điều phối staging |  | PASS / FAIL |  |
| HR Lead |  | PASS / FAIL |  |
| Hiring Manager |  | PASS / FAIL |  |
| Admin/IT Security (nếu có dùng model thật) |  | PASS / FAIL / N/A |  |

## 8. Dọn dẹp sau test

- Xóa hoặc reset dữ liệu staging theo quy trình của môi trường; ưu tiên dùng retention workflow cho application tổng hợp đã đến hạn khi cần kiểm chứng purge.
- Thu hồi tài khoản/grant tạm thời không còn dùng.
- Không sao chép DOCX sinh ra, log hoặc screenshot chứa dữ liệu staging sang production.
- Cập nhật kết quả thật vào `audit/PHASE1_REVIEW_2026-11-07.md` và `Update_Excute_P1.md`; không cập nhật trạng thái PASS chỉ dựa trên checklist này.
