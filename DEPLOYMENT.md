# VinUni HRApp — Triển khai lên Supabase

**Project Supabase:** `myrymlqdbyqmpynesiwk`
**Region:** `ap-southeast-1` (Singapore)
**Database:** PostgreSQL 17.11
**Date:** 2026-11-05

## ✅ Đã hoàn thành trên Supabase

### 1. Database Migrations (đã apply)
| Migration | Version | Mô tả |
|-----------|---------|-------|
| `00001_initial_schema.sql` | `20261105081853` | Tạo schema `app_private`, 37 bảng (users, positions, JD, criteria, CV batches, applications, documents, profiles, assessments, ranking, shortlist, audit), RLS policies cơ bản, indexes, helper `has_position_access()`, auto-update trigger, storage buckets `cv-originals` + `cv-extracted-text`, public views cho supabase-js client. |
| `00002_audit_fixes_indexes_rls.sql` | `20261105082127` | Bổ sung indexes cho polling operations/Ranking lookup; RLS policies cho 15 bảng còn thiếu (criterion_results, evidence, identities, status events, jd_versions, duplicate_signals, ai_config, …); phân quyền USAGE/SELECT cho role `authenticated`, full access cho `service_role`. |

**Tổng cộng:** 37 tables trong schema `app_private`, tất cả có RLS.

### 2. Storage Buckets (đã tạo)
- `cv-originals` — lưu file CV PDF/DOCX gốc (private)
- `cv-extracted-text` — lưu văn bản trích xuất (private)

### 3. Auth Configuration
- ✅ **Tắt tự do đăng ký** (`disable_signup = true`) — tài khoản phải được Admin mời vào
- ✅ **Site URL**: `http://localhost:3000` (cần cập nhật khi deploy production)
- ✅ Refresh token rotation bật mặc định
- ⚠️ **Lưu ý:** Storage bucket RLS policies phải được cấu hình qua Supabase Dashboard (Storage → Policies) vì tài khoản owner của `storage.objects` là `supabase_storage_admin`, không thể chỉnh từ SQL migration. Xem mục 6 bên dưới.

### 4. Default Data (đã seed)
| Bảng | Dữ liệu |
|------|---------|
| `assessment_policy_versions` | Policy chấm điểm v1.0 (STRONG_MATCH=100, MATCH=80, NO_MATCH=0, min_coverage=0.7) |
| `retention_policy_versions` | Policy lưu trữ 12 tháng sau khi đóng vị trí |
| `ai_policy_versions` | Policy mặc định `default-local-v1` — chỉ cho phép nhà cung cấp local, cấm external API |
| `ai_configuration_versions` | Cấu hình AI hoạt động: **Ollama local `llama3.1:8b`** tại `http://localhost:11434/v1`, status ACTIVE |

## 🔧 Bước còn lại để chạy hệ thống

### 5. Tạo tài khoản Admin đầu tiên (bắt buộc)
Vì `disable_signup = true`, bạn phải tạo user đầu tiên qua Supabase Dashboard:

1. Vào **Authentication → Users → Add user**
2. Nhập email admin (ví dụ `admin@vinuni.edu.vn`) và mật khẩu
3. Copy `user_id` (UUID) của user vừa tạo
4. Chạy SQL sau trong **SQL Editor** để cấp quyền ADMIN:

```sql
-- Thay <ADMIN_UUID> bằng user_id vừa tạo
INSERT INTO app_private.user_profiles (user_id, display_name, preferred_locale)
VALUES ('<ADMIN_UUID>', 'HR Admin', 'vi')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO app_private.user_role_assignments (user_id, role_code, granted_by)
VALUES ('<ADMIN_UUID>', 'ADMIN', '<ADMIN_UUID>')
ON CONFLICT (user_id, role_code) DO NOTHING;
```

### 6. Cấu hình Storage Policies (bắt buộc)
Vào **Storage → Policies** trong Supabase Dashboard và tạo các policy sau:

**Cho bucket `cv-originals`:**

- **INSERT (authenticated HR can upload):**
  ```sql
  bucket_id = 'cv-originals'
  AND split_part(name, '/', 1) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  ```
  Target roles: `authenticated`

- **SELECT (HR/HM with position access can read):**
  ```sql
  bucket_id = 'cv-originals'
  AND EXISTS (
    SELECT 1 FROM app_private.application_documents d
    JOIN app_private.applications a ON a.application_id = d.application_id
    WHERE d.storage_path = name
    AND (
      app_private.has_position_access(a.position_id, ARRAY['HR_RECRUITER','HR_LEAD','HIRING_MANAGER'])
      OR EXISTS (
        SELECT 1 FROM app_private.shortlist_shares ss
        JOIN app_private.shortlist_share_items si ON ss.share_id = si.share_id
        WHERE ss.shared_with = auth.uid() AND ss.status='ACTIVE' AND ss.allow_cv_view=TRUE
        AND si.application_id = d.application_id
      )
    )
  )
  ```
  Target roles: `authenticated`

**Cho bucket `cv-extracted-text`:**
- Không cho phép đọc/ghi từ phía client (service role dùng riêng cho worker). Để trống hoặc tạo policy luôn trả về `false`.

### 7. Lấy thông tin kết nối
| Thông tin | Giá trị |
|-----------|---------|
| Host | `db.myrymlqdbyqmpynesiwk.supabase.co` |
| Port | `5432` (direct) / `6543` (pooler) |
| Database | `postgres` |
| User | `postgres` |
| Password | Xem tại **Project Settings → Database → Connection string → Reset database password** |
| Supabase URL | `https://myrymlqdbyqmpynesiwk.supabase.co` |
| Anon Key | (đã điền sẵn trong `.env.example`) |
| Service Role Key | (đã điền sẵn trong `.env.example` — **không commit lên git**) |
| JWT Secret | **Project Settings → API → JWT Settings → JWT Secret** (cần copy vào backend `.env`) |

### 8. Khởi chạy backend
```bash
cd backend
cp .env.example .env
# Edit .env và điền DATABASE_URL password + SUPABASE_JWT_SECRET
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 9. Khởi chạy frontend
```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Truy cập `http://localhost:3000`, đăng nhập bằng tài khoản admin vừa tạo.

### 10. Xác nhận hệ thống hoạt động
- API health: `GET http://localhost:8000/health` → `{"status":"healthy",...}`
- DB readiness: `GET http://localhost:8000/health/ready` → `{"status":"ready","database":"connected",...}`
- Swagger docs: `http://localhost:8000/docs`
- Admin AI config: đăng nhập → vào `/admin` → phải thấy cấu hình local Ollama đang ACTIVE
- Tạo position test → upload CV PDF → chờ worker xử lý → xem xếp hạng.

## ⚠️ Lưu ý bảo mật trước production
1. **Thay đổi mật khẩu DB** lần đầu sau khi nhận project
2. **Xoá service_role key** khỏi file `.env.example` sau khi bạn copy sang `.env`; trong file ví dụ chỉ nên để placeholder
3. **Không dùng service_role key trên frontend** — chỉ dùng ở backend
4. **Thêm CORS origins** cho domain production ở `app/core/config.py` + Supabase Auth URL config
5. **Bật email verification** và SMTP trước khi mời người dùng thật
6. **Rotate JWT secret** sau khi pilot ổn định
