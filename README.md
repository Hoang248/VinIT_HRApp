# VinUni HRApp — hỗ trợ sàng lọc CV

Ứng dụng Phase 1 hỗ trợ HR quản lý vị trí, duyệt tiêu chí, xử lý CV và xem xếp hạng tư vấn. **AI không tự shortlist, loại hay chuyển trạng thái ứng viên**; các quyết định tuyển dụng do HR thực hiện.

## Luồng đã triển khai trong mã

1. HR tạo vị trí, JD và gán Hiring Manager; cập nhật tên, mở/tạm dừng/đóng vị trí.
2. AI đề xuất bộ tiêu chí nháp; HR chỉnh từng tiêu chí và trọng số hai nhóm (mặc định 70/30, tổng 100%), duyệt quy trình; Hiring Manager được gán duyệt chuyên môn hoặc yêu cầu sửa. Phiên bản đã duyệt được khóa.
3. HR tải lô PDF/DOCX (tối đa 50 file, 10 MB/file, 250 MB/lô); worker xử lý, đánh giá và tạo ranking trong cùng vị trí. Giao diện tự theo dõi tiến trình, kể cả sau khi quay lại trang.
4. HR xem cảnh báo lỗi/trùng, điểm và độ phủ, đối chiếu bằng chứng, cập nhật trạng thái và lý do; lịch sử quyết định chỉ hiển thị cho HR có quyền.
5. HR chia sẻ các hồ sơ shortlist cho HM được gán, chọn có/không cho xem CV. HM xem nội dung được chia sẻ và phản hồi; HR có thể thu hồi. Link CV đã ký có thể tiếp tục hoạt động tối đa 10 phút sau thu hồi.
6. Dashboard tổng hợp số liệu thật trong phạm vi người dùng được phép xem; chỉ số chưa có dữ liệu đáng tin cậy hiển thị `—`/`null` thay vì số giả.

Điểm/độ phủ được tính trong backend từ trọng số phiên bản tiêu chí đã duyệt; trích dẫn được kiểm tra khớp văn bản và số trang PDF. Độ phủ hiện tính theo **trọng số có bằng chứng đáng tin cậy**, không phải số lượng tiêu chí, và được làm tròn xuống tới 2 chữ số thập phân; thiếu bằng chứng hoặc confidence thấp được gắn `UNCLEAR`/cần xác minh. Xếp hạng chỉ gồm hồ sơ đang sàng lọc và bản tiêu chí đã duyệt mới nhất; thứ hạng là snapshot từ lần chạy gần nhất. Điểm và thứ hạng chỉ có tính tham khảo, đặc biệt khi độ phủ thấp. Công thức và policy điểm cần được HR/HM xác nhận trước pilot.

## Kiến trúc hiện tại

- **Frontend:** Next.js 15 + React + MUI, tiếng Việt; gọi API qua proxy `/v1` cùng origin.
- **Backend:** FastAPI, xác thực JWT Supabase HS256 và phân quyền nghiệp vụ theo vị trí/hồ sơ; kết nối PostgreSQL trực tiếp.
- **Worker:** thread trong process API, poll bảng PostgreSQL và gọi LLM qua endpoint tương thích OpenAI. Chưa có cơ chế lease/khôi phục task sau crash.
- **Lưu trữ:** Supabase Storage bucket private qua service role backend hoặc filesystem cục bộ dùng thử.

Các migration trong `supabase/migrations/` yêu cầu môi trường có Supabase Auth và các role tương ứng. Migration 00003 đã được áp dụng vào project Supabase được kết nối sau xác nhận; xem [DEPLOYMENT.md](DEPLOYMENT.md) về lịch sử, tác động quyền và các bước cho môi trường khác. Không reset hoặc push migration mù quáng vào dữ liệu thật.

## Chạy phát triển

Yêu cầu Node.js 22+, Python 3.11+, một Supabase/PostgreSQL đã được chuẩn bị, và endpoint LLM phù hợp nếu muốn chạy đánh giá. Với OCR PDF scan cần Tesseract tiếng Anh và Poppler.

```bash
# Backend: điền backend/.env từ mẫu, không commit secret
cd backend
cp .env.example .env
python -m venv .venv
.venv/bin/python -m pip install --upgrade "pip>=26.2" "setuptools>=84.1.0"
.venv/bin/pip install -e .
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Frontend: proxy mặc định tới backend trên cùng máy
cd frontend
cp .env.local.example .env.local
npm ci
npm run dev
```

Mở `http://localhost:3000`. Đăng nhập cần Supabase Auth thật, JWT secret tương ứng và profile/role đã cấp trong database. `/health` là liveness, `/health/ready` kiểm tra kết nối database; Swagger `/docs` chỉ bật khi `DEBUG=true`.

Có thể dùng `docker compose up --build` sau khi chuẩn bị root `.env` và các dịch vụ Supabase/LLM bên ngoài. Compose không tự tạo Supabase hay LLM; xem [DEPLOYMENT.md](DEPLOYMENT.md) trước khi sử dụng. Docker chưa được kiểm thử trong phiên này.

## Kiểm thử

```bash
(cd frontend && npm ci && npm run lint && npm run type-check && npm run build)
# Backend: xem backend/tests/README.md để tạo PostgreSQL cục bộ dùng một lần
TEST_DATABASE_URL='postgresql://postgres@127.0.0.1:55432/hra_phase1_test' \
  backend/.venv/bin/pytest -q backend/tests
```

**Các integration test xóa dữ liệu trong database thử nghiệm.** Chỉ dùng database cục bộ rỗng tên `_test`; hướng dẫn đầy đủ và giới hạn có trong [backend/tests/README.md](backend/tests/README.md).

## Chưa hoàn tất / chưa sẵn sàng production

- Chưa kiểm thử đầu-cuối với Supabase Auth/Storage, LLM thật và OCR scan; chưa có đánh giá chất lượng AI/bias trên tập pilot. CV text vẫn được gửi đến endpoint model; kiểm soát egress và bảo vệ dữ liệu nhạy cảm cần được hoàn thiện độc lập.
- Chưa có UI sửa thông tin profile ứng viên, ghi chú riêng HR, quản lý retention/xác nhận xóa hay giao diện song ngữ Việt–Anh đầy đủ. Trang Admin AI chỉ đọc; cấu hình runtime qua environment và restart.
- Chưa có phục hồi an toàn job `PROCESSING` sau crash; audit chưa được bảo đảm bất biến; access token hiện ở `localStorage`. Cần hoàn thiện vận hành và an ninh trước khi đưa vào production.
- Service-role key từng xuất hiện trong Git history **phải được thu hồi/rotate** theo kế hoạch; Supabase thật và các dịch vụ AI/Storage chưa được kiểm thử đầu-cuối. Xem [PHASE1_GAP_ANALYSIS.md](PHASE1_GAP_ANALYSIS.md) và [DEPLOYMENT.md](DEPLOYMENT.md) để biết phạm vi, các giả định và việc còn lại.
