# Triển khai VinUni HRApp với Supabase

> Bản hiện tại cần kiểm thử và phê duyệt trước khi dùng với hồ sơ thật. Các kiểm thử tự động đã chạy trên PostgreSQL cục bộ với dữ liệu giả và LLM giả lập; chưa chứng minh được Supabase Storage/Auth, OCR scan, LLM thật hay Docker trong môi trường đích.

## Tình trạng project đã kết nối

Đã áp dụng `00003_phase1_operation_scope.sql` cho project `myrymlqdbyqmpynesiwk` **ngày 05/11/2026 sau khi được người dùng xác nhận**. Trước khi áp dụng, project khỏe và không có vị trí, hồ sơ hoặc tác vụ; các view cũ tương thích. Supabase ghi lịch sử:

- `20261105081853` — `initial_schema`
- `20261105082127` — `audit_fixes_indexes_rls_grants`
- `20261105131736` — `phase1_operation_scope`

Kiểm tra chỉ đọc sau migration: cột `operations.position_id` có trong `app_private` và view `public`; `anon`/`authenticated` không có `USAGE` trên `app_private` và không có SELECT/INSERT/UPDATE/DELETE trên 37 view nghiệp vụ `public`; `service_role` vẫn có quyền SELECT cần thiết. Hai bucket `cv-originals` và `cv-extracted-text` private, không có policy trên `storage.objects`; DB/Auth/REST/Storage báo healthy. Chưa kiểm thử API/Storage/LLM thật với credential runtime. Trạng thái có thể thay đổi, hãy kiểm tra lại trước triển khai.

## Trước khi triển khai

1. **Thu hồi/rotate service-role key đã từng xuất hiện trong lịch sử Git.** Thay giá trị mới trong secret manager và cấu hình backend; xóa khỏi file hiện tại không thu hồi được key cũ. Nếu đây là legacy service-role JWT, việc đổi JWT secret có thể ảnh hưởng anon key, phiên đăng nhập và các tích hợp; lập kế hoạch chuyển đổi/gián đoạn trước khi thực hiện. Xem xét phạm vi phơi lộ, logs và các client đang dùng key. Không đưa key hoặc JWT secret vào frontend hay Git.
2. Với project khác hoặc môi trường đích mới, sao lưu database, rà soát client tích hợp và thử migration trên staging có schema giống môi trường đích. Migration 00003 thêm `operations.position_id`, backfill quan hệ, tạo/cập nhật public views, và **thu hồi quyền direct đối với `app_private` và các view khỏi `anon`/`authenticated`**. Các client/PostgREST gọi trực tiếp bảng/view cũ có thể ngừng hoạt động. Thống nhất phương án rollback và chỉ chạy migration bằng quy trình được phê duyệt.
3. Đối chiếu lịch sử migration thực tế trước khi áp dụng; các version từ xa nêu trên khác tiền tố tên file local, vì vậy không chạy `supabase db push`/reset mù quáng trên project hiện hữu. **Không áp dụng lại 00003 cho project trên**; chỉ áp dụng cho môi trường khác sau phê duyệt và ghi lịch sử migration phù hợp.
4. Trên từng môi trường đích, xác minh cùng lúc: `operations.position_id` tồn tại; `anon`/`authenticated` không có `USAGE` trên `app_private` và không có quyền đọc/ghi các view nghiệp vụ `public`; `service_role` vẫn có quyền cần thiết. Kiểm thử HR/HM, thu hồi phân công và thu hồi shortlist qua API với dữ liệu giả.

Ví dụ truy vấn kiểm tra quyền (chỉ đọc):

```sql
SELECT has_schema_privilege('authenticated', 'app_private', 'USAGE') AS authenticated_private_usage,
       has_table_privilege('authenticated', 'public.applications', 'SELECT') AS authenticated_applications_select,
       has_schema_privilege('service_role', 'app_private', 'USAGE') AS service_private_usage;
-- Kỳ vọng sau 00003: false, false, true.
```

## Storage: chỉ backend truy cập trực tiếp

Giữ **cả hai bucket ở chế độ private**. CV upload/download đi qua API đã kiểm tra quyền theo vị trí và shortlist; worker dùng service role cho cả CV gốc lẫn văn bản trích xuất. **Không tạo policy cho `anon` hoặc `authenticated` đọc/ghi trực tiếp hai bucket**: policy cho HM dựa riêng trên quyền vị trí có thể bỏ qua `allow_cv_view=false`.

Kiểm tra các policy hiện có trong Dashboard → Storage → Policies hoặc `pg_policies`; nếu từng áp dụng hướng dẫn policy cũ, rà soát và loại bỏ/sửa policy cho hai bucket sau khi đánh giá tác động tới ứng dụng khác. Không xóa mù quáng policy của bucket khác. Đường link ký được backend cấp có hiệu lực tối đa 10 phút; link đã cấp có thể vẫn dùng được tới khi hết hạn sau khi quyền bị thu hồi.

## Cấu hình

- `DATABASE_URL`: kết nối PostgreSQL từ **backend**; dùng TLS cho cloud. Vai trò kết nối phải có các quyền SQL cần thiết để API/worker truy cập `app_private`; dữ liệu được phân quyền trong backend, nên không cấp credential này cho client. Hạn chế quyền và network theo nguyên tắc tối thiểu.
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`: dùng cho đăng nhập Supabase Auth ở backend. `SUPABASE_JWT_SECRET`: bí mật xác minh JWT, chỉ backend. Hiện API xác minh JWT **HS256**, audience `authenticated`, và yêu cầu `sub`/`aud`/`exp`; project dùng signing key bất đối xứng cần bổ sung JWKS/thuật toán tương ứng trước khi sử dụng.
- `SUPABASE_SERVICE_ROLE_KEY`: chỉ backend/worker; bắt buộc khi `STORAGE_BACKEND=supabase`. `local` là tùy chọn thử nghiệm, Compose lưu trong volume `cv_storage` và cần bảo vệ dữ liệu/backup phù hợp.
- `LLM_API_BASE`, `LLM_MODEL_NAME`, `LLM_API_KEY`, `ALLOW_EXTERNAL_API`: đọc từ **environment khi process khởi động**. Trang Admin chỉ đọc cấu hình của process API; bản ghi AI trong database không tự áp dụng, các endpoint đổi cấu hình trả 501. Khi đổi env phải khởi động lại API/worker và xác nhận cấu hình của mọi process.
- `ALLOW_EXTERNAL_API=false` mặc định chặn endpoint không phân giải về địa chỉ private/loopback và client không dùng proxy từ biến môi trường. Đây **không phải** kiểm soát egress đầy đủ/DNS pinning: triển khai firewall/network allowlist, TLS, giám sát và quy trình phê duyệt riêng. CV text được gửi đến endpoint AI đã cấu hình; hiện chưa có bộ khử thông tin nhạy cảm/anti-bias đủ để cam kết loại bỏ hoàn toàn. Không gửi CV thật tới dịch vụ bên ngoài nếu chưa có phê duyệt và kiểm soát dữ liệu.
- Frontend gọi `/v1` cùng origin; Next proxy tới `API_INTERNAL_URL` phía server. Không đặt URL backend localhost trong mã chạy ở trình duyệt. Trong Compose, giá trị là `http://backend:8000`; `localhost` bên trong một container không phải host máy.

Mẫu cấu hình: `.env.example` cho Compose, `backend/.env.example` và `frontend/.env.local.example` khi chạy từng dịch vụ. Các giá trị mẫu là placeholder, không phải credential.

## Khởi chạy

### Từng dịch vụ

```bash
cd backend
cp .env.example .env             # điền cấu hình an toàn, không commit
python -m venv .venv
.venv/bin/python -m pip install --upgrade "pip>=26.2" "setuptools>=84.1.0"
.venv/bin/pip install -e .
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd frontend
cp .env.local.example .env.local # API_INTERNAL_URL trỏ tới backend
npm ci
npm run dev
```

Đăng nhập cần user Supabase Auth có `app_private.user_profiles.account_status='ACTIVE'` và role/position assignment tương ứng. Provision user/role phải do quản trị viên thực hiện theo quy trình nội bộ. `/health` chỉ kiểm tra liveness; `/health/ready` kiểm tra kết nối database, không chứng minh Storage hoặc LLM hoạt động.

### Docker Compose

```bash
cp .env.example .env  # điền URL/secret cho backend, APP_ENV=production và DEBUG=false khi cần
# Đảm bảo Supabase/PostgreSQL và LLM riêng đã chạy, có thể truy cập từ container
docker compose up --build
```

Compose chỉ tạo frontend và backend; worker chạy trong process backend, không có Celery/Redis/PostgreSQL/LLM tích hợp. Cần quản lý network, TLS, backup volume, bí mật, giám sát và số worker/process. Docker build/runtime chưa được kiểm chứng trong phiên này.

## Giới hạn vận hành cần xử lý trước production

- Queue poll PostgreSQL chưa có lease/heartbeat hoặc phục hồi an toàn tác vụ `PROCESSING` sau crash. Không tự đặt lại task đang chạy khi chưa xác minh worker đã dừng và tác động tới dữ liệu; cần runbook/khôi phục được thiết kế và kiểm thử trước vận hành.
- Chưa có luồng quản lý retention/xác nhận xóa và chỉnh sửa hồ sơ ứng viên hoàn chỉnh; log audit chưa được bảo đảm bất biến. Giao diện hiện lưu access token ở `localStorage`; cần đánh giá XSS, chính sách session, log, quyền và an toàn dữ liệu trước pilot. SQLAlchemy không echo và ẩn bound parameters, nhưng vẫn cần rà soát log của toàn bộ hệ thống.
- Python dependencies hiện khai báo theo khoảng phiên bản, chưa có lockfile; kiểm soát chuỗi cung ứng và chạy quét lỗ hổng định kỳ cho image/dependencies. Ngày 05/11/2026, `npm audit --omit=dev` báo 0, nhưng full audit còn 6 cảnh báo moderate trong chuỗi công cụ lint. `pip-audit` trên môi trường backend cục bộ không báo lỗ hổng đã biết ở các dependencies được quét (bỏ qua package nội bộ editable). Các kết quả tại một thời điểm không chứng minh image triển khai an toàn.
- Thực hiện kiểm thử OCR scan (Tesseract tiếng Anh + Poppler), model thật, đánh giá chất lượng/bias và kiểm thử end-to-end Supabase với dữ liệu được phép. Kết quả AI chỉ là tham khảo; chỉ HR chuyển trạng thái tuyển dụng.
