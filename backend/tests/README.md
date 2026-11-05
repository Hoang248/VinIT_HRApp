# Kiểm thử backend Phase 1

Các integration test tạo dữ liệu giả và chạy trên PostgreSQL thật; LLM được giả lập. **Fixture sẽ `TRUNCATE app_private.positions CASCADE`**, xóa vị trí và dữ liệu liên quan. Chỉ sử dụng cụm PostgreSQL cục bộ mới, dùng một lần, không chứa dữ liệu thật. Tuyệt đối không trỏ vào Supabase cloud hay database phát triển đang sử dụng. `conftest.py` từ chối URL không có host cục bộ tường minh hoặc tên database không kết thúc bằng `_test`, nhưng kiểm tra này không thay thế việc tự xác nhận database là dùng một lần.

## Chuẩn bị database cục bộ rỗng

Ví dụ dưới đây giả định **một cụm PostgreSQL riêng, dùng một lần** đã chạy tại `127.0.0.1:55432`, có user quản trị `postgres`, các extension `uuid-ossp` và `pgcrypto`, và bộ công cụ `psql`/`createdb`. Không chạy phần tạo role trên cụm dùng chung. Schema `auth` dưới đây chỉ là stub cho test, không phải Supabase Auth thật.

```bash
psql 'postgresql://postgres@127.0.0.1:55432/postgres' -v ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
SQL
createdb -h 127.0.0.1 -p 55432 -U postgres hra_phase1_test
psql 'postgresql://postgres@127.0.0.1:55432/hra_phase1_test' -v ON_ERROR_STOP=1 <<'SQL'
CREATE SCHEMA auth;
CREATE TABLE auth.users (id UUID PRIMARY KEY);
CREATE FUNCTION auth.uid() RETURNS UUID LANGUAGE sql STABLE AS $$ SELECT NULL::UUID $$;
SQL
for f in supabase/migrations/00001_initial_schema.sql \
         supabase/migrations/00002_audit_fixes_indexes_rls.sql \
         supabase/migrations/00003_phase1_operation_scope.sql; do
  psql 'postgresql://postgres@127.0.0.1:55432/hra_phase1_test' -v ON_ERROR_STOP=1 -f "$f"
done
```

Chạy từ gốc repository:

```bash
python -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade "pip>=26.2" "setuptools>=84.1.0"
backend/.venv/bin/pip install -e './backend[dev]'
TEST_DATABASE_URL='postgresql://postgres@127.0.0.1:55432/hra_phase1_test' \
  backend/.venv/bin/pytest -q backend/tests
```

Có thể dùng Unix socket qua tham số `host=/đường/dẫn/socket`; host phải được chỉ rõ. Không đặt `PGSERVICE`, `PGSERVICEFILE` hoặc `PGOPTIONS` khi chạy test.

Không đặt `TEST_DATABASE_URL` sẽ chỉ chạy unit test và bỏ qua integration test. Test không chứng minh việc triển khai Supabase Auth/Storage, OCR scan, mô hình AI thật, Docker hoặc chất lượng matching trên CV thật; các phần đó cần kiểm thử riêng trong môi trường được phê duyệt.
