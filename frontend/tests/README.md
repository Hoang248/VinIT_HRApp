# Kiểm thử giao diện

`npm run test:i18n` chạy unit test không cần browser: dictionary, interpolation, chuyển ngôn ngữ của thông báo đang hiển thị và kiểm tra key UI có bản dịch Anh.

`npm run test:e2e:synthetic` là smoke test Playwright cho login/ngôn ngữ, lỗi đăng nhập, JD dialog, chỉnh profile, ghi chú HR, Admin AI, quyền HM, lỗi backend, tải lại/hydration và mobile. **Test có ghi dữ liệu**: tạo profile version, thêm ghi chú và kích hoạt cấu hình AI. Chỉ chạy trên hệ thống cục bộ **dùng một lần, hoàn toàn tổng hợp**, không kết nối DB/Storage/project thật và không dùng CV thật. Kiểm tra loopback và `APP_ENV=testing` chỉ giảm rủi ro; chúng **không chứng minh** database phía sau là dùng một lần. Người chạy phải tự xác minh trước.

Cần tạo sẵn backend `APP_ENV=testing` (worker tắt) và frontend proxy `/v1` tới backend đó, DB cục bộ đã có đủ migrations và dữ liệu giả. Tạo file fixture JSON riêng, không commit, gồm `hr_token`, `hm_token`, `position`, `app_b`, `app_c`; token là JWT ngắn hạn chỉ dùng cho môi trường giả. Dữ liệu test gồm vị trí `Software Engineer (dữ liệu giả)` với đơn vị `Đơn vị minh họa`, ứng viên `Ứng viên giả Bình` được chia sẻ cho HM chỉ ở chế độ summary, và `Ứng viên giả Chi` có tài liệu CV giả cho HR sửa. HR demo đồng thời có ADMIN; allowlist chứa `synthetic-local-model`, `synthetic-alternative-model` và endpoint local. Test không gọi model/worker thật.

Cài Chromium tương thích với `playwright-core` và thư viện OS cần thiết, sau đó ví dụ:

```bash
cd frontend
npm ci
# Chỉ tải Chromium vào môi trường kiểm thử khi phù hợp chính sách của bạn:
npx playwright-core install chromium
HRA_E2E_SYNTHETIC=1 \
HRA_E2E_BASE_URL=http://127.0.0.1:3000 \
HRA_E2E_HEALTH_URL=http://127.0.0.1:8001/health \
HRA_E2E_FIXTURE=/đường/dẫn/fixture-tổng-hợp.json \
  npm run test:e2e:synthetic
```

Có thể chỉ định `HRA_E2E_CHROMIUM_EXECUTABLE` cho binary có sẵn và `HRA_E2E_CHROMIUM_ARGS` là JSON array khi môi trường CI cô lập cần flags riêng. Không lưu fixture/token hay binary browser vào Git. Test này không chứng minh Supabase Auth/Storage, OCR, model thật hay tính an toàn production.
