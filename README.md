# VinUni HRApp — AI-Native CV Matching & Ranking

Sản phẩm AI-Native hỗ trợ sàng lọc và xếp hạng CV theo JD cho bộ phận HR VinUniversity.

---

## 📋 Tổng quan Kiến trúc Phase 1 (MVP)

Kiến trúc theo dạng **Modular Monolith**, gồm 3 tiến trình chính:

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| 🖥️ Frontend | Next.js 14 (React/TypeScript) + MUI | Giao diện người dùng song ngữ Việt/Anh cho HR, Hiring Manager, HR Lead |
| 🚀 Backend API | Python + FastAPI + Pydantic | Cung cấp REST API v1, xác thực, phân quyền và điều phối tác vụ |
| ⚙️ Worker xử lý | Python (chung codebase với API) | Xử lý upload CV, OCR, trích xuất thông tin, gọi LLM và matching bất đồng bộ |
| 🗄️ Cơ sở dữ liệu | Supabase PostgreSQL + PostgREST | Lưu dữ liệu nghiệp vụ, xác thực người dùng, lưu trữ file CV |
| 📥 Lưu trữ file | Supabase Storage (bucket private) | Lưu CV gốc và văn bản trích xuất, cấp URL truy cập có thời hạn |
| 🔐 Xác thực | Supabase Auth | Đăng nhập email/mật khẩu nội bộ, Phase 1 chưa có SSO/MFA |
| 🤖 AI/LLM | Model cục bộ vLLM (khuyến nghị) | Trích xuất tiêu chí từ JD, cấu trúc thông tin CV và đối chiếu bằng chứng |
| 📑 Queue | PostgreSQL/pgmq hoặc Redis/Celery | Điều phối các tác vụ xử lý CV và AI bất đồng bộ |

---

## ✨ Tính năng chính Phase 1

- [x] Quản lý vị trí tuyển dụng và JD tiếng Anh
- [x] AI đề xuất tiêu chí từ JD với bản nháp, chờ HR + Hiring Manager phê duyệt (dual approval)
- [x] Upload CV theo batch (tối đa 50 file, ≤ 10MB/file, tổng ≤ 250MB)
- [x] Hỗ trợ PDF văn bản, OCR PDF scan và DOCX tiếng Anh
- [x] Phát hiện file lỗi, file cần HR kiểm tra (không tự động loại)
- [x] Cảnh báo CV trùng trong cùng vị trí (qua email/số điện thoại, không tự gộp/xóa)
- [x] Đánh giá theo từng tiêu chí với trích dẫn nguyên văn từ CV (verbatim evidence)
- [x] Tính điểm trọng số và độ phủ bằng chứng **bằng mã tất định (không giao cho LLM tính toán)** để chống ảo giác
- [x] Kiểm tra độ chính xác của trích dẫn (verbatim quote verification)
- [x] Xếp hạng ứng viên trong cùng vị trí theo nguyên tắc: tiêu chí bắt buộc trước, điểm sau
- [x] 3 miền trạng thái được tách biệt rõ ràng: **File processing**, **Matching advisory**, **Application status**
- [x] AI không tự động thay đổi trạng thái tuyển dụng — chỉ HR mới có quyền cập nhật
- [x] Phân quyền theo vai trò và vị trí tuyển dụng
- [x] Audit log cho các thao tác quan trọng
- [x] Tuân thủ UI Style Guide nhận diện VinUni (màu Navy #0A2B57, đỏ #C72127, font Roboto)

---

## 📂 Cấu trúc dự án

```text
VinIT_HRApp/
├── doc/                            # Tài liệu thiết kế và nghiệp vụ
│   ├── HRA_BRD.md                  # Business Requirements Document
│   ├── HRA_PRD.md                  # Product Requirements Document
│   ├── HRA_ArchitectureDesign.md   # Kiến trúc logic tổng thể
│   ├── HRA_Phase1_Architecture.md  # Chi tiết kiến trúc Phase 1
│   ├── HRA_DatabaseDesign.md       # Thiết kế cơ sở dữ liệu
│   ├── HRA_LLM_Architecture.md     # Luồng điều phối và gọi LLM
│   ├── HRA_InterfaceDesign.md      # Thiết kế API và giao diện
│   ├── HRA_ui-style-guide.md       # Hướng dẫn style UI chuẩn VinUni
│   ├── HRA_Wireframe.md            # Wireframe màn hình
│   ├── demo_phase1.html            # Demo UI HTML tĩnh
│   └── ...
│
├── backend/                        # Backend FastAPI Python
│   ├── app/
│   │   ├── api/                    # Các router API v1
│   │   ├── core/                   # Config, logging, security, exceptions
│   │   ├── db/                     # Supabase client
│   │   ├── models/                 # (Pydantic models in schemas/)
│   │   ├── schemas/                # Pydantic schemas cho request/response
│   │   ├── services/               # Document processor, LLM client, Matching engine
│   │   ├── workers/                # Celery/async worker cho xử lý CV
│   │   └── main.py                 # Điểm vào FastAPI
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/                       # Frontend Next.js React/TypeScript
│   ├── src/
│   │   ├── app/                    # App Router Next.js
│   │   ├── components/             # React components
│   │   ├── lib/                    # Supabase client, MUI theme
│   │   ├── types/                  # TypeScript types
│   │   └── hooks/                  # Custom hooks
│   ├── package.json
│   └── Dockerfile
│
├── supabase/
│   └── migrations/                 # SQL migrations cho PostgreSQL
│       └── 00001_initial_schema.sql
│
├── docker-compose.yml              # Docker Compose cho local dev
├── .env.example                    # File cấu hình mẫu
└── README.md
```

---

## 🚀 Hướng dẫn chạy Local Development

### Yêu cầu hệ thống
- Node.js 20+
- Python 3.11+
- Docker & Docker Compose
- Supabase CLI (tùy chọn, dùng để chạy Supabase local)

### 1. Chuẩn bị môi trường

```bash
# Clone repository và chuyển vào thư mục
cd VinIT_HRApp

# Tạo file .env từ mẫu
cp .env.example .env
# Chỉnh sửa .env với các giá trị phù hợp (Supabase URL, keys, etc.)
```

### 2. Khởi động Supabase local (khuyến nghị)

```bash
# Cài đặt Supabase CLI nếu chưa có
# https://supabase.com/docs/guides/cli

# Khởi động Supabase local
supabase start

# Chạy migration tạo bảng
supabase db reset
```

*Hoặc bạn có thể dùng Supabase Cloud và điền URL/key vào `.env`.*

### 3. Chạy Backend API

```bash
cd backend

# Tạo virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Cài đặt dependencies
pip install -e .
pip install -e ".[dev]"

# Chạy server development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API sẽ chạy tại `http://localhost:8000`, tài liệu Swagger tại `http://localhost:8000/docs`.

### 4. Chạy Frontend

```bash
cd frontend

# Cài đặt dependencies
npm install

# Chạy development server
npm run dev
```

Frontend sẽ chạy tại `http://localhost:3000`.

### 5. (Tùy chọn) Chạy toàn bộ bằng Docker Compose

```bash
docker-compose up --build
```

---

## 🔒 Nguyên tắc thiết kế quan trọng

1. **Con người quyết định (Human-in-control):** Mọi kết quả AI chỉ là *tư vấn (advisory)*. HR là người duy nhất thay đổi trạng thái ứng viên. AI không tự động loại hồ sơ hay tạo shortlist.

2. **Bằng chứng trước điểm số:** Mọi nhận định đánh giá đều kèm trích dẫn nguyên văn (`verbatim_quote`) và số trang. Hệ thống tự động kiểm tra xem trích dẫn có thực sự tồn tại trong CV hay không để chống ảo giác.

3. **"Chưa rõ" không phải "Không đạt":** Trường hợp thiếu thông tin, OCR mờ hay confidence thấp được đưa vào nhóm **Cần HR xác minh**, tuyệt đối không quy thành điểm 0 hoặc tự động loại.

4. **Tách tính toán khỏi LLM:** Tất cả phép tính điểm, độ phủ và xếp hạng được thực hiện bằng mã tất định trong backend, không giao cho LLM tự tính để loại trừ 100% lỗi ảo giác số học.

5. **Phân lập theo vị trí:** Không đánh giá chéo hay xếp hạng hồ sơ giữa các vị trí khác nhau. Không trộn ngữ cảnh CV của ứng viên này với ứng viên khác.

6. **Bảo vệ dữ liệu:** Ưu tiên chạy model AI trên hạ tầng cục bộ, không gửi CV production lên cloud công cộng khi chưa có phê duyệt. Loại bỏ hoàn toàn các thông tin nhạy cảm (tuổi, giới tính, ảnh, tôn giáo) khỏi quá trình đánh giá.

---

## 🚧 Trạng thái hiện tại

Đây là bản khởi tạo cấu trúc dự án theo tài liệu thiết kế Phase 1 MVP. Các phần đang triển khai:

- [x] Cấu trúc cơ sở dữ liệu đầy đủ theo Database Design
- [x] Core config, security, logging cho backend
- [x] Document processing service (PDF, OCR, DOCX)
- [x] LLM client với structured output validation
- [x] Deterministic matching & ranking engine (scoring, quote verification, duplicate detection)
- [x] Cơ sở API FastAPI
- [x] Cấu hình frontend Next.js với theme theo UI Style Guide VinUni
- [ ] Hoàn thiện các API endpoint còn lại
- [ ] Trang Dashboard và danh sách vị trí
- [ ] Màn hình duyệt tiêu chí/rubric
- [ ] Màn hình upload CV và theo dõi tiến trình xử lý
- [ ] Trang chi tiết CV đối chiếu với bằng chứng side-by-side
- [ ] Chia sẻ shortlist cho Hiring Manager
- [ ] Dashboard báo cáo pilot
- [ ] Hàng đợi xử lý bất đồng bộ cho worker
- [ ] Row Level Security policies cho Supabase
- [ ] End-to-end testing
