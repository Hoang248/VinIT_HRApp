# Update Execute — Phase 1 (P1)

> File này là nhật ký thực thi cho các dev khác theo dõi các thay đổi/nâng cấp Phase 1: hạng mục đã làm, đang làm, còn chờ, bằng chứng kiểm thử và các blocker ngoài code. Mỗi batch nâng cấp từ thời điểm này phải cập nhật file này trước khi coi là hoàn tất.
>
> Branch: `arena/ea6e2570-vinit-hrapp`  
> Ngày bắt đầu vòng nâng cấp: 2026-11-07  
> Nguồn yêu cầu: review lần 2 của GPT đối với code Phase 1 tại commit nền `1326acd`, phần đánh giá/phản biện và plan nâng cấp đã thống nhất với người dùng.

## 1. Nguyên tắc thực thi

1. Làm lần lượt theo gate: sửa đúng scoring → an toàn dữ liệu → semantic vận hành → LTR governance → RBAC/CI/E2E → retention/audit → đánh giá model/dữ liệu thật.
2. Không bật BGE/LTR production chỉ vì code đã có. BGE cần endpoint thật + golden set; LTR cần HR gold dataset + phê duyệt + SHADOW.
3. Không tự ý vô hiệu hóa Supabase legacy keys/JWT secret khi chưa xác nhận mọi deployment đã chuyển sang key/JWKS mới; đây là thao tác Dashboard/Management API của chủ project.
4. Mỗi batch phải có test hoặc bằng chứng kiểm chứng tương ứng, cập nhật tài liệu liên quan và commit riêng để dev khác review được.

## 2. Tổng quan trạng thái

| Batch | Hạng mục | Trạng thái | Commit/Bằng chứng |
|---:|---|---|---|
| 0 | Đánh giá/phản biện review GPT và lập plan nâng cấp | ĐÃ LÀM | Kết luận: đồng ý phần lớn; chưa đóng Phase 1 |
| 1 | Sửa công thức matching score cho UNCLEAR; khóa LTR file artifact ở production; tạo Phase 1 Closure Review | ĐÃ LÀM | Commit `57b9072`, `1386f7e`; targeted tests đạt |
| 2 | Embedding cache + semantic diagnostics | ĐÃ LÀM | Commit `ccd9141`; semantic/LTR tests đạt |
| 3 | LTR governance: artifact hash, review events, Admin approve/reject API | ĐÃ LÀM ở code + project Supabase đã kết nối | Commit `eb674d7`; migration `00011` remote version `20261107133211` |
| 4 | RBAC test matrix + CI độc lập + khung E2E staging | ĐÃ LÀM ở code/CI — CHƯA CHẠY E2E THẬT | Commit `3d68ba2`, sửa harness `3105045`; GitHub Actions run `42379643837` đạt cả 3 job |
| 5 | Retention/deletion workflow + audit integrity | CHƯA LÀM | Xem mục 6 |
| 6 | BGE pilot bằng golden set HR; HR gold dataset cho LTR; LTR SHADOW report | CHƯA LÀM | Cần dữ liệu/HR/nguồn lực ngoài code |
| EXT-1 | Đóng legacy Supabase API keys và revoke legacy JWT secret | BLOCKED — MANUAL OPS | Connector không có thao tác deactivate/revoke; cần chủ project thao tác Dashboard/Management API |

## 3. Batch 1 — Scoring UNCLEAR + khóa LTR file production + Closure Review

### Đã thay đổi

- `backend/app/services/matching.py`
  - Từ `matching-v2.1`, `matching_score` là trung bình có trọng số chỉ trên các tiêu chí đã đủ bằng chứng để tính điểm.
  - `UNCLEAR` bị loại khỏi cả tử số và mẫu số; không còn bị tính như 0.
  - `evidence_coverage` vẫn đo phần trọng số rubric đã có bằng chứng; mandatory/coverage gate không đổi.
- `backend/app/core/config.py`
  - Tăng `MATCHING_POLICY_VERSION` từ `matching-v2.0` lên `matching-v2.1`.
- `backend/tests/test_phase1_unit.py`
  - Cập nhật kỳ vọng điểm theo công thức mới.
  - Thêm regression tests: STRONG_MATCH + UNCLEAR, không có tiêu chí được chấm, NO_MATCH đã có bằng chứng.
- `backend/app/workers/processor.py`
  - Khi `APP_ENV=production` và `LTR_MODE=ACTIVE`, chặn nạp LTR bằng `LTR_MODEL_PATH`; production ACTIVE phải dùng registry artifact đã APPROVED.
- `backend/tests/test_semantic_ltr.py`
  - Thêm test chặn file artifact ở production và cho phép ở staging.
- Tài liệu/UI:
  - `doc/MATCHING_STABILITY.md` bổ sung mục công thức điểm từ `matching-v2.1`.
  - `doc/BGE_LTR.md` đồng bộ ý nghĩa feature `matching_score` và giới hạn file artifact.
  - Nhãn chi tiết ứng viên đổi thành “Điểm trên tiêu chí đã có bằng chứng”; bổ sung bản dịch EN.
- `audit/PHASE1_REVIEW_2026-11-07.md`
  - Tạo khung Phase 1 Closure Review đối chiếu F1.01–F1.13 theo PASS/PARTIAL/BLOCKED/NOT TESTED.

### Kiểm chứng

- Targeted tests `test_phase1_unit.py` + `test_semantic_ltr.py`: đạt tại thời điểm batch 1.
- Lưu ý tương thích: artifact LTR đã train bằng `matching_score` theo policy cũ không được coi là tương thích với `matching-v2.1` cho tới khi train/đánh giá lại.

## 4. Batch 2–3 — Semantic cache/diagnostics và LTR governance

### Batch 2: Embedding cache + semantic diagnostics — ĐÃ LÀM

- `backend/app/services/embedding.py`
  - Bổ sung `parse_vector_literal` để đọc vector từ pgvector text.
- `backend/app/workers/processor.py`
  - Trước khi gọi provider, worker tra cứu vector đã lưu theo `document_id + chunk_id + chunk_text_sha256 + embedding_model + index_version`.
  - Chỉ embed các chunk còn thiếu; chỉ insert các vector mới.
  - Ghi diagnostics cho provider fallback, cache hit/miss, số chunk/query đã embed và trạng thái pgvector.
- `backend/app/services/semantic_diagnostics.py`
  - Cung cấp trạng thái cấu hình/runtime: `DISABLED`, `MISCONFIGURED`, `READY_UNVERIFIED`, `OPERATIONAL`, `OPERATIONAL_IN_MEMORY_PGVECTOR_UNAVAILABLE`, `DEGRADED_FALLBACK`.
- `backend/app/api/admin.py`
  - Thêm `GET /v1/admin/semantic/health` cho Admin; không gọi provider và không trả endpoint/API key.
- Tests/docs:
  - Test lượt semantic đầu embed toàn bộ, lượt sau dùng cache và không gọi document embedding lại.
  - Cập nhật `doc/BGE_LTR.md`, `audit/PHASE1_REVIEW_2026-11-07.md`.

### Batch 3: LTR governance — ĐÃ LÀM ở code + project đã kết nối

- `supabase/migrations/00011_ltr_model_governance.sql`
  - Thêm `artifact_sha256`, `registered_by`, `reviewed_by`, `reviewed_at`, `review_reason` vào `ltr_model_versions`.
  - Tạo bảng append-only `ltr_model_review_events` cho REGISTERED/APPROVED/REJECTED.
  - Đã áp lên Supabase project `myrymlqdbyqmpynesiwk` với version `20261107133211`; đã kiểm chứng cột/bảng/RLS.
- `backend/app/services/ltr.py`
  - Thêm `artifact_sha256` dùng canonical JSON để phê duyệt gắn với đúng nội dung artifact.
- `backend/scripts/register_ltr_model.py`
  - Đăng ký DRAFT kèm artifact hash + sự kiện REGISTERED.
  - Từ chối ghi đè cùng `model_version` bằng artifact khác.
- `backend/app/workers/processor.py`
  - Khi nạp registry artifact, kiểm tra artifact hash; hash không khớp thì không dùng model.
- `backend/app/api/admin.py`
  - Thêm `GET /v1/admin/ltr/models`.
  - Thêm `POST /v1/admin/ltr/models/{model_version}/approve` và `/reject` với lý do bắt buộc, kiểm tra DRAFT/gates/hash, ghi review event + audit event.
- Tài liệu:
  - Cập nhật `DEPLOYMENT.md` với migration `00011`.
  - Cập nhật `doc/BGE_LTR.md`: phê duyệt qua Admin API thay vì sửa SQL trực tiếp.
  - Cập nhật `audit/PHASE1_REVIEW_2026-11-07.md`.

### Kiểm chứng

- Semantic/LTR targeted tests đạt sau batch 3.
- Migration `00011` đã kiểm chứng trên project đã kết nối; môi trường đích khác vẫn phải áp/kiểm chứng riêng.

## 5. Batch 4 — RBAC matrix + CI + E2E staging

### Trạng thái: ĐÃ LÀM ở code — CHƯA CHẠY E2E THẬT

### Đã thay đổi

- `backend/tests/test_phase1_integration.py`
  - Thêm `test_rbac_matrix_position_scope_and_admin_surfaces` chạy trên PostgreSQL dùng một lần.
  - Ma trận kiểm tra: HR Lead/HR Recruiter/Hiring Manager/người không được gán theo position được phép và không được phép.
  - Kiểm tra danh sách/chi tiết application bị giới hạn theo position, dashboard chỉ trả position được phép, và người dùng không có assignment không nhận dashboard rows.
  - Kiểm tra `/v1/admin/semantic/health`, `/v1/admin/ltr/models` và `/v1/admin/worker/health` là ADMIN-only; người không phải Admin bị 403.
- `.github/workflows/ci.yml`
  - Job `backend-unit`: cài backend, chạy toàn bộ pytest không có integration database và Ruff trên các bề mặt đã nâng cấp.
  - Job `frontend`: `npm ci`, i18n tests, type-check, lint và production build.
  - Job `backend-integration`: dùng service `pgvector/pgvector:pg17`, tạo database dùng một lần, tạo auth/role stubs tối thiểu, áp toàn bộ migration theo thứ tự và chạy backend tests với `TEST_DATABASE_URL`.
  - CI không dùng Supabase project thật làm database tự động.
- `backend/tests/README.md`
  - Bổ sung migration `00010_pgvector_bge_ltr.sql` và `00011_ltr_model_governance.sql` vào danh sách áp thủ công cho test database.
  - Ghi rõ integration suite đã bao phủ thêm ma trận RBAC position/application/dashboard và các endpoint Admin semantic/LTR/worker.
- `doc/E2E_STAGING.md`
  - Thêm runbook E2E staging: điều kiện an toàn dữ liệu, chuẩn bị môi trường, kịch bản bắt buộc cho auth/RBAC, JD/criteria, upload/OCR, profile/matching/ranking, semantic, LTR governance, shortlist và worker recovery.
  - Ghi rõ bằng chứng phải lưu và điều kiện đạt; việc có runbook không đồng nghĩa E2E thật đã đạt.
- `audit/PHASE1_REVIEW_2026-11-07.md`
  - Cập nhật trạng thái CI từ chưa có workflow sang đã có workflow nhưng vẫn `PARTIAL` cho tới khi checks xanh trên GitHub và branch protection được cấu hình.
  - Cập nhật F1.10/F1.13 theo test RBAC mới; F1.10 vẫn `BLOCKED` do retention/audit integrity và legacy keys.

### Kiểm chứng

- Local không có `TEST_DATABASE_URL`: full backend đạt **90 passed, 59 skipped**; test RBAC mới sẽ được thực thi trong job CI integration dùng PostgreSQL/pgvector dùng một lần.
- Ruff phạm vi các bề mặt đã nâng cấp đạt.
- YAML của `.github/workflows/ci.yml` đã parse thành công.
- Các lần chạy GitHub Actions đầu tiên cho thấy backend-unit và frontend đạt, nhưng backend-integration thất bại ở 6 test worker. Truy vết bằng JUnit/annotations và tái hiện cục bộ cho thấy nguyên nhân không phải RBAC mới: `backend/tests/test_accounts.py::reset_disposable_database()` truncate `auth.users CASCADE`, làm mất policy `assessment-v2.0` do migration `00008` seed, nhưng chỉ khôi phục policy cũ `v1.0`. Khi worker ghi `assessment_runs.policy_version='assessment-v2.0'`, PostgreSQL trả FK violation.
- Đã sửa harness test để reset khôi phục cả `assessment-v2.0` đúng nội dung migration `00008`.
- Sau sửa, chạy full backend trên PostgreSQL dùng một lần tại local đạt **149 passed**.
- GitHub Actions run `42379643837` tại commit `3105045` đã đạt cả ba job: Backend unit tests, Frontend checks và Backend integration (disposable PostgreSQL + pgvector). URL: https://github.com/ratrichero/VinIT_HRApp/actions/runs/42379643837

### Còn lại sau Batch 4

- Chạy E2E thật trên staging tách biệt với Supabase Auth/Storage, OCR scan, LLM thật và BGE endpoint thật bằng dữ liệu tổng hợp/được phép; ghi bằng chứng theo `doc/E2E_STAGING.md`.
- Cấu hình branch protection yêu cầu các job CI chính nếu repo/production process cần.
- Không dùng CV thật cho E2E cho tới khi EXT-1/EXT-2 được đóng hoặc có phê duyệt riêng.

## 6. Batch 5 — Retention/deletion + audit integrity

### Trạng thái: CHƯA LÀM

### Phạm vi dự kiến

- Dùng các bảng retention/deletion đã có trong schema để xây workflow: tạo case đến hạn, HR xác nhận, thực thi xóa CV gốc/extracted text/profile/assessment/evidence/embeddings/shortlist artifacts, ghi deletion event không chứa PII.
- Tăng cường audit integrity: hạn chế UPDATE/DELETE audit events đối với application role, bổ sung cơ chế kiểm chứng toàn vẹn và áp dụng cho role changes, criteria approval, AI config activation, LTR approval.
- Cập nhật closure review và tài liệu vận hành sau khi có test.

## 7. Batch 6 — Đánh giá model và dữ liệu thật

### Trạng thái: CHƯA LÀM

### Điều kiện tiên quyết

- BGE: endpoint thật đã được phê duyệt privacy/egress; golden set HR cho semantic retrieval; đo Recall@5, false MATCH/NO_MATCH, unresolved rate, latency.
- LTR: HR gold dataset đủ lớn; train đạt gates; artifact APPROVED; SHADOW report không có vi phạm mandatory/coverage gate.
- Không dùng weak label từ trạng thái ứng tuyển để bật LTR ACTIVE.

## 8. Blocker ngoài code

| Mã | Hạng mục | Người/điều kiện cần | Trạng thái |
|---|---|---|---|
| EXT-1 | Deactivate legacy Supabase anon/service_role keys và revoke legacy JWT secret | Chủ project thao tác Dashboard/Management API sau khi mọi deployment dùng key/JWKS mới | BLOCKED |
| EXT-2 | Phê duyệt privacy/egress cho LLM/BGE/OCR endpoints | IT Security/Legal/HR | CHƯA CÓ BẰNG CHỨNG |
| EXT-3 | Golden set HR cho matching/BGE và HR gold dataset cho LTR | HR/HM cung cấp/chấm nhãn | CHƯA CÓ |
| EXT-4 | E2E trên môi trường staging đích | DevOps/IT chuẩn bị staging tương đương | CHƯA CÓ BẰNG CHỨNG |

## 9. Quy ước cập nhật file này

Sau mỗi batch, dev thực hiện phải bổ sung:

1. Trạng thái mới trong bảng tổng quan.
2. File/code/migration đã thay đổi.
3. Lệnh test đã chạy và kết quả.
4. Commit hash sau khi push.
5. Blocker còn lại và người/điều kiện cần để mở khóa.
