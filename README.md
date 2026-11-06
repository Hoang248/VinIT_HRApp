# VinUni HRApp — hỗ trợ sàng lọc CV

Ứng dụng Phase 1 hỗ trợ HR quản lý vị trí, duyệt tiêu chí, xử lý CV và xem xếp hạng tư vấn. **AI không tự shortlist, loại hay chuyển trạng thái ứng viên**; các quyết định tuyển dụng do HR thực hiện.

## Luồng đã triển khai trong mã

1. ADMIN tạo tài khoản và phân vai trò; tài khoản mới phải đổi mật khẩu tạm thời ở lần đăng nhập đầu. HR tạo vị trí, JD và chọn Hiring Manager đang hoạt động, khác tài khoản HR; cập nhật tên, mở/tạm dừng/đóng vị trí.
2. AI đề xuất bộ tiêu chí nháp; HR chỉnh tiêu chí/trọng số (mặc định 70/30, tổng 100%), duyệt quy trình; Hiring Manager được gán duyệt chuyên môn hoặc yêu cầu sửa. Hai bước duyệt bắt buộc do **hai tài khoản khác nhau**; phiên bản đã duyệt được khóa.
3. HR tải lô PDF/DOCX (tối đa 50 file, 10 MB/file, 250 MB/lô); worker xử lý, đánh giá và tạo ranking trong cùng vị trí. Giao diện tự theo dõi tiến trình, kể cả sau khi quay lại trang.
4. HR xem cảnh báo lỗi/trùng, điểm và độ phủ, đối chiếu bằng chứng, cập nhật trạng thái và lý do; lịch sử quyết định chỉ hiển thị cho HR có quyền.
5. HR chia sẻ các hồ sơ shortlist cho HM được gán, chọn có/không cho xem CV. Chế độ chỉ tóm tắt không lộ email, số điện thoại, tệp CV hoặc bằng chứng chi tiết. HM chỉ xem bản assessment đã chia sẻ; sau khi thay đổi profile/tiêu chí, HR cần chia sẻ lại kết quả mới. Quyền xem CV là hợp của các share còn hiệu lực; bằng chứng cần một share cho phép CV của đúng bản assessment. HR có thể thu hồi; link CV đã ký có thể tiếp tục hoạt động tối đa 10 phút sau thu hồi.
6. HR tạo phiên bản JD và sửa profile ứng viên; sau khi thay đổi phải duyệt lại tiêu chí hoặc chạy lại đánh giá tương ứng. Ghi chú riêng HR không chia sẻ HM hoặc gửi AI. Dashboard chỉ tổng hợp dữ liệu trong phạm vi được phép.

Điểm/độ phủ được tính trong backend từ trọng số phiên bản tiêu chí đã duyệt; trích dẫn được kiểm tra khớp văn bản và số trang PDF. Độ phủ hiện tính theo **trọng số có bằng chứng đáng tin cậy**, không phải số lượng tiêu chí, và được làm tròn xuống tới 2 chữ số thập phân; thiếu bằng chứng hoặc confidence thấp được gắn `UNCLEAR`/cần xác minh. Xếp hạng chỉ gồm hồ sơ đang sàng lọc và bản tiêu chí đã duyệt mới nhất; thứ hạng là snapshot từ lần chạy gần nhất. Điểm và thứ hạng chỉ có tính tham khảo, đặc biệt khi độ phủ thấp. Công thức và policy điểm cần được HR/HM xác nhận trước pilot.

## Kiến trúc hiện tại

- **Frontend:** Next.js 15 + React + MUI, giao diện Việt–Anh (mặc định Việt, lưu lựa chọn trên trình duyệt); gọi API qua proxy `/v1` cùng origin. Nội dung do người dùng nhập không được dịch tự động.
- **Backend:** FastAPI, xác thực JWT Supabase HS256 và phân quyền nghiệp vụ theo vị trí/hồ sơ; kết nối PostgreSQL trực tiếp.
- **Worker:** thread trong process API, poll PostgreSQL; có advisory session lock, fencing, heartbeat và tự thử phục hồi job sau crash. Cuộc gọi AI là at-least-once, không bảo đảm chạy đúng một lần; xem [runbook](DEPLOYMENT.md#phục-hồi-worker-và-giám-sát).
- **Lưu trữ:** Supabase Storage bucket private qua service role backend hoặc filesystem cục bộ dùng thử.

Các migration trong `supabase/migrations/` yêu cầu Supabase Auth và các role tương ứng. Migration 00003 và 00004 đã áp vào project Supabase kết nối sau khi được xác nhận; version 00004 remote là `20261105152817 recovery_and_privacy`. **Mã tài khoản mới phụ thuộc 00005, hiện chỉ có trong repository và chưa được áp vào project kết nối.** Không triển khai backend mới vào database chưa có 00005. Không reset/push migration mù quáng; cần phê duyệt riêng, staging, backup và drain worker cũ theo [DEPLOYMENT.md](DEPLOYMENT.md).

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

Mở `http://localhost:3000`. Đăng nhập cần Supabase Auth thật, JWT secret tương ứng và profile/role đã cấp trong database. Khởi tạo ADMIN đầu tiên mặc định đóng; chỉ bật bằng mã ngẫu nhiên bí mật trong môi trường được bảo vệ, và chỉ thực hiện một lần. ADMIN sau đó tạo HR/HM, cấp vai trò và khóa/mở tài khoản từ **Quản lý tài khoản**. Quy trình, quyền DB và các giới hạn: [hướng dẫn bootstrap](doc/VPS_DEPLOYMENT.md#7-bootstrap-người-dùng-và-smoke-test). `/health` là liveness, `/health/ready` kiểm tra kết nối database; Swagger `/docs` chỉ bật khi `DEBUG=true`.

Có thể dùng `docker compose up --build` sau khi chuẩn bị root `.env` và các dịch vụ Supabase/LLM bên ngoài. Compose không tự tạo Supabase hay LLM; xem [hướng dẫn VPS](doc/VPS_DEPLOYMENT.md) và [DEPLOYMENT.md](DEPLOYMENT.md) trước khi sử dụng. Docker chưa được kiểm thử trong phiên này.

## Kiểm thử

```bash
(cd frontend && npm ci && npm run lint && npm run type-check && npm run test:i18n && npm run build)
# Backend: xem backend/tests/README.md để tạo PostgreSQL cục bộ dùng một lần
TEST_DATABASE_URL='postgresql://postgres@127.0.0.1:55432/hra_phase1_test' \
  backend/.venv/bin/pytest -q backend/tests
```

**Các integration test xóa dữ liệu trong database thử nghiệm.** Chỉ dùng database cục bộ rỗng tên `_test`; xem [backend/tests/README.md](backend/tests/README.md). Browser smoke có ghi dữ liệu tổng hợp, chỉ chạy trên môi trường cục bộ dùng một lần theo [frontend/tests/README.md](frontend/tests/README.md).

## Chưa hoàn tất / chưa sẵn sàng production

- Chưa kiểm thử đầu-cuối với Supabase Auth/Storage, LLM thật, OCR scan hoặc Docker; việc tạo tài khoản/đổi mật khẩu chỉ được kiểm thử với Auth giả lập. Chưa đánh giá chất lượng/bias trên tập pilot được phép. Redaction regex là **best effort**, có thể bỏ sót PII/thuộc tính nhạy cảm hoặc che nhầm; vẫn cần DLP, egress và phê duyệt độc lập.
- Chưa có workflow quên mật khẩu, mời email, đổi email, xóa user hoặc đổi HM của vị trí đã tạo. Thu hồi role HR/HM qua trang quản trị cũng thu hồi phân công tương ứng và không tự khôi phục khi cấp lại; cần quy trình DBA được phê duyệt để xử lý vị trí đang phụ trách.
- Chưa có workflow retention/xác nhận xóa; audit chưa bảo đảm bất biến; access token hiện ở `localStorage`. Worker recovery cần staging, giám sát bên ngoài, PostgreSQL session ổn định và runbook; heartbeat không chứng minh worker còn sống.
- Admin kích hoạt cấu hình trong allowlist môi trường; kết quả đã có không tự chạy lại khi đổi model (pipeline bỏ qua profile/rubric đã có assessment hoàn tất). Client chỉ hỗ trợ `/chat/completions` OpenAI-compatible với Bearer, không trực tiếp hỗ trợ giao thức Azure riêng. Không dùng CV thật khi chưa có kiểm soát và phê duyệt phù hợp.
- Service-role key từng xuất hiện trong Git history **phải được thu hồi/rotate** theo kế hoạch; Supabase thật và các dịch vụ AI/Storage chưa được kiểm thử đầu-cuối. Xem [PHASE1_GAP_ANALYSIS.md](audit/PHASE1_GAP_ANALYSIS.md) và [DEPLOYMENT.md](DEPLOYMENT.md) để biết phạm vi, các giả định và việc còn lại.
