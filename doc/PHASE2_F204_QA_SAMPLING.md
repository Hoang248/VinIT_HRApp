# F2.04 — Giám sát chất lượng OCR & AI Matching (QA sample inspection)

Nguồn yêu cầu: `doc/HRA_NextPhase.md` F2.04. Làm trước batch F2.01 + F2.02 theo quyết định ngày 11/11/2026.

## Quyết định đã chốt (11/11/2026)

| Mã | Câu hỏi | Quyết định |
| :-: | :--- | :--- |
| D-1 | "Đợt" là gì? | Một `cv_batch` |
| D-2 | "Sát ngưỡng 70%" | `0.60 ≤ evidence_coverage < 0.80` |
| D-3 | Ai kiểm định? | `HR_LEAD`, `ADMIN`; recruiter được phân công chỉ xem kết quả vị trí của mình |
| D-4 | Thêm loại cờ OCR? | Có: `OCR_ERROR`, bên cạnh `INCORRECT_EVIDENCE`, `MISSED_CONTENT` |
| D-5 | Đẩy flag lên Langfuse? | Chưa. Chỉ xuất file nội bộ đã redact, cho tới khi Langfuse tự host hoặc DEP-05 được duyệt |
| D-6 | Nhắc kiểm định hàng tuần? | Không gửi nhắc; hàng đợi và summary hiển thị số item chờ quá 7 ngày |

## Luật chọn mẫu (`qa-sampling-v1`)

| Lý do | Luật |
| :--- | :--- |
| `RANDOM` | `ceil(10%)` dân số của đợt, tối thiểu 1; chọn các hồ sơ có `sha256(sample_run_id:application_id)` nhỏ nhất, nên kiểm toán viên tái lập được mẫu mà không cần seed |
| `SINGLE_MUST_HAVE_FAIL` | Đúng 1 tiêu chí `MUST_HAVE` có outcome `NO_MATCH` (`UNCLEAR` không tính là trượt) |
| `COVERAGE_NEAR_THRESHOLD` | `evidence_coverage` trong khoảng D-2 |

Dân số là lần đánh giá `COMPLETED` mới nhất của mỗi hồ sơ trong đợt, với bộ tiêu chí đã duyệt. Mẫu được tạo tự động sau khi worker đánh giá xong (tối đa một mẫu AUTO cho mỗi đợt và mỗi phiên bản tiêu chí); HR Lead có thể tạo thêm mẫu thủ công. Lỗi khi tạo mẫu chỉ ghi log, không làm hỏng thao tác đánh giá.

## Thành phần

| Thành phần | File |
| :--- | :--- |
| Bảng `qa_sample_runs`, `qa_sample_items`, `qa_flags` | `supabase/migrations/00013_qa_sample_inspection.sql` |
| Chọn mẫu, Wilson 95% CI, tạo run | `backend/app/services/qa_sampling.py` |
| API `/v1/qa/*` (queue, item, flags, review, summary, sample-runs) | `backend/app/api/qa.py` |
| Tự tạo mẫu sau đánh giá | `backend/app/workers/processor.py` (`_create_qa_samples`) |
| Xóa dữ liệu QA khi purge hồ sơ | `backend/app/services/retention.py` |
| Xuất flag JSONL đã redact, chặn nếu còn email/SĐT | `backend/scripts/export_qa_flags.py` |
| Giao diện hàng đợi và đối soát CV gốc với bằng chứng | `frontend/src/app/qa/` |

Summary trả tỷ lệ cờ kèm khoảng tin cậy Wilson 95% và `small_sample_warning` khi số hồ sơ đã kiểm định dưới 30.

## Chưa làm

- Nối tỷ lệ flag/override vào dashboard chung (thuộc F2.03).
- Nhắc việc tự động (D-6) và đẩy dataset lên Langfuse (D-5).
- Migration `00013` chưa áp lên môi trường staging/production nào.
