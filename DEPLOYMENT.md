# Triển khai và vận hành VinUni HRApp

> Mã này **chưa sẵn sàng production**. Các test dùng PostgreSQL cục bộ dùng một lần, dữ liệu tổng hợp và AI HTTP mock; chưa chứng minh Supabase Auth/Storage, model thật, OCR scan hay Docker trong môi trường đích. Không dùng CV thật trong preview hoặc kiểm thử chưa được phê duyệt.

## Lịch sử project đã kết nối

Trên project `myrymlqdbyqmpynesiwk`, sau xác nhận của người dùng, đã áp `00003_phase1_operation_scope.sql`, `00004_recovery_and_privacy.sql` (05/11/2026 15:28 UTC) và `00005_account_administration.sql` (05/11/2026 16:36 UTC). Lịch sử remote:

| File trong repository | Version/name trên Supabase |
|---|---|
| `00001_initial_schema.sql` | `20261105081853 initial_schema` |
| `00002_audit_fixes_indexes_rls.sql` | `20261105082127 audit_fixes_indexes_rls_grants` |
| `00003_phase1_operation_scope.sql` | `20261105131736 phase1_operation_scope` |
| `00004_recovery_and_privacy.sql` | `20261105152817 recovery_and_privacy` |
| `00005_account_administration.sql` | `20261105163626 account_administration` |

Preflight trước 00005 (05/11/2026 16:36 UTC): DB/Auth/REST/Storage khỏe, không có vị trí, hồ sơ, tác vụ đang xử lý, auth user hoặc profile; một cấu hình AI ACTIVE endpoint loopback. Sau áp 00005: bảng `app_private.account_initialization` (1 row, `initialized_at` NULL → bootstrap đang mở vì chưa từng có ADMIN), hai cột `user_profiles.must_change_password` (`boolean NOT NULL DEFAULT FALSE`) và `tokens_valid_after` (`timestamptz`), function `app_private.mark_admin_initialized()` và trigger `mark_admin_initialized` trên `user_role_assignments`, RLS `ENABLE` trên `account_initialization` chỉ `service_role` được `SELECT,UPDATE`. Backfill HM không tạo thêm row do không có `position_assignments` đang hiệu lực tại thời điểm áp. Postflight xác nhận `has_table=true`, `has_must_change=true`, `has_tokens_valid=true`, `has_func=true`, `has_trigger=true`. Endpoint của cấu hình AI ACTIVE hiện tại vẫn là **loopback** (`localhost` trong container backend không phải VPS/model bên ngoài); phải chọn và kích hoạt endpoint hợp lệ từ Admin trước khi dùng AI. Tại thời điểm kiểm tra chưa có ADMIN/auth user. Chưa xác minh backup/restore, rotate key hay E2E dịch vụ thật; không thể suy ra mọi worker bên ngoài đã dừng chỉ từ snapshot này.

Mã backend hiện tại **phụ thuộc 00005** (kiểm tra trạng thái tài khoản, `must_change_password`, `tokens_valid_after` và bootstrap một lần). Đã áp xong lên project kết nối sau khi preflight không có dữ liệu xung đột; với môi trường khác phải đối chiếu schema/grants và user/role hiện có, backup/restore, thử staging và lập kế hoạch rollback riêng trước khi áp. 00005 ghi dấu bootstrap một lần (kể cả assignment ADMIN đã thu hồi cũng đóng bootstrap), không khôi phục role HM đã thu hồi và không backfill `HR_LEAD` từ position.

Schema ban đầu trên project này có một số cột AI đã tồn tại trước 00004; không giả định nội dung mọi version remote byte-for-byte giống file local. Không chạy `supabase db push`/reset mù quáng: version remote là timestamp, khác tiền tố file local. Với project/môi trường khác, đối chiếu migration thực tế, xin phê duyệt và làm staging/drain riêng theo checklist dưới đây. Hướng dẫn dựng VPS Ubuntu với Docker Compose, Nginx, TLS và vận hành: [doc/VPS_DEPLOYMENT.md](doc/VPS_DEPLOYMENT.md).

## Checklist khi áp 00004 vào môi trường khác hoặc triển khai worker mới

1. **Thu hồi/rotate service-role key từng xuất hiện trong lịch sử Git — trạng thái 05/11/2026:** key legacy `service_role` JWT từng commit trong `backend/.env.example` vẫn còn là **legacy key đang bật** trên project `myrymlqdbyqmpynesiwk` (cùng với `anon` JWT). Project đã có sẵn cặp key mới `sb_publishable_*`/`sb_secret_*` (type `publishable`/`secret`, prefix `sb_publishable_z2Ynu`/`sb_secret_rLbWw`) nhưng **chưa deactivate legacy** và **chưa revoke legacy JWT secret**. Tạo secret mới riêng lẻ không tự thu hồi legacy; nếu bật lại legacy, key lộ sẽ sống lại. Thu hồi trọn vẹn theo docs Supabase cần: (a) tạo/đổi sang dùng `sb_publishable_`/`sb_secret_` ở mọi client/backend/worker/pipeline/mobile đã lưu key cũ, (b) deactivate legacy `anon`+`service_role` cùng lúc (Dashboard **Settings → API Keys → Legacy API keys → Deactivate**, hoặc Management API `PUT /v1/projects/{ref}/api-keys/legacy?enabled=false`), (c) migrate JWT signing keys sang asymmetric và **revoke legacy JWT secret** (Dashboard **Auth → Signing Keys** hoặc Management API) — legacy JWT vẫn còn hiệu lực nếu chỉ tắt API key mà chưa revoke secret. Backend hiện tại chỉ verify `HS256` với `SUPABASE_JWT_SECRET` (audience `authenticated`) và sẽ **gãy đăng nhập** nếu chuyển sang asymmetric/JWKS khi chưa nâng cấp code. Chặn token cũ đã đăng nhập dựa trên `tokens_valid_after`/`iat` chỉ có tác dụng trong API app, không thay thế việc revoke ở Supabase. Không gửi key vào frontend, Git hay chat; đổi secret trong secret manager, rà soát log/client/phạm vi phơi lộ và drain worker cũ trước khi deactivate. Connector hiện tại không có thao tác disable legacy, nên bước deactivate/revoke phải làm thủ công trên Dashboard/Management API và được kiểm chứng qua `GET /v1/projects/{ref}/api-keys/legacy` hoặc `list_api_keys`.
2. Sao lưu, thử restore, thử migration và kịch bản crash/recovery trên staging có schema và storage tương đương; rà soát ứng dụng dùng view/grant trực tiếp. Kiểm tra lịch sử migration thực tế và lập phương án rollback đã phê duyệt. 00004 thêm cột operations/config/profile, view, bảng ghi chú HR và sự kiện recovery, RLS/grant cùng unique index cho cấu hình AI ACTIVE; dữ liệu cũ có nhiều ACTIVE cần được xử lý theo kế hoạch được duyệt **trước** khi tạo index.
3. Tạm ngừng nhận job mới tại gateway/UI, cho công việc đang chạy hoàn thành nếu có thể, sau đó dừng/drain **tất cả** API/worker phiên bản cũ. Worker được nhúng trong mỗi process API; bản cũ không dùng advisory lock và có thể ghi đồng thời với worker mới. Không chạy mixed-version workers trong/ sau migration.
4. Kết nối PostgreSQL có **session thực được giữ liên tục** trong suốt một attempt; khuyến nghị direct connection. Không dùng PgBouncer transaction/statement pooling: backend PID hoặc advisory session lock có thể đổi sau mỗi transaction. Nếu dùng pooler session mode, chỉ dùng sau khi đã xác minh độc lập khả năng pin cùng backend PID và lock trong suốt attempt, failover và timeout. Kiểm soát TLS và network ở môi trường cloud.
5. Sau phê duyệt, áp migration qua quy trình versioning của môi trường. Xác nhận bảng/cột/index/grant, cấu hình AI hợp lệ, access riêng tư của notes, backend health và staging smoke HR/HM với dữ liệu tổng hợp. Chỉ sau đó khởi động đồng nhất API/worker phiên bản mới, theo dõi queue rồi mở nhận job. Nếu cần rollback, dừng/drain worker mới trước và làm theo kế hoạch đã thử; không để worker cũ chạy trên job đang do worker mới xử lý.

Ví dụ preflight chỉ đọc (không tự sửa dữ liệu):

```sql
SELECT status, count(*) FROM app_private.ai_configuration_versions GROUP BY status;
SELECT capability, status, count(*) FROM app_private.operations GROUP BY capability, status;
SELECT has_schema_privilege('authenticated', 'app_private', 'USAGE') AS authenticated_private_usage,
       has_table_privilege('authenticated', 'public.applications', 'SELECT') AS authenticated_applications_select,
       has_schema_privilege('service_role', 'app_private', 'USAGE') AS service_private_usage;
-- Sau 00003 kỳ vọng: false, false, true. Đối chiếu mọi bảng/view cần dùng, không chỉ ví dụ.
```

## Storage và privacy

- Giữ `cv-originals` và `cv-extracted-text` **private**; upload/download đi qua backend kiểm tra quyền. Không cấp policy trực tiếp cho HM chỉ dựa trên assignment: có thể bỏ qua `allow_cv_view=false`. Kiểm tra và xử lý policy cũ theo phạm vi được phê duyệt. Link CV đã ký có thể dùng đến 10 phút sau thu hồi.
- CV gốc vẫn được lưu để người có quyền xem. Trước mỗi cuộc gọi AI, code che theo regex các identifier/thuộc tính nhạy cảm phổ biến, hạn chế profile có cấu trúc và thêm system guardrails; extracted text mới cũng lưu bản đã che. Đây là **best effort, không phải ẩn danh hoặc bảo đảm không rò rỉ**: tên không nhãn, địa chỉ, dữ liệu nhạy cảm viết tự do, OCR và biến thể ngôn ngữ có thể bị bỏ sót; che nhầm cũng có thể làm mất bằng chứng. Prompt không bảo đảm loại bỏ prompt injection hoặc bias.
- Cần đánh giá DLP/NER, chính sách retention, hợp đồng xử lý dữ liệu, kiểm thử bảo mật/bias và kiểm soát mạng độc lập trước khi xử lý hồ sơ thật. Chỉ gửi dữ liệu tới dịch vụ/model đã được phê duyệt; ưu tiên local. Ghi chú riêng HR không được truyền vào profile/prompt, nhưng không thay thế chính sách truy cập/log của toàn hệ thống.
- SQLAlchemy ẩn bound parameters, worker tránh ghi CV/prompt/exception raw, nhưng hệ điều hành, proxy, model provider, OCR và dịch vụ khác vẫn cần được rà soát logging, quyền, mã hóa và backup. Audit hiện chưa bất biến; workflow retention/xác nhận xóa chưa hoàn tất.

## Cấu hình AI và egress

- Backend/worker đọc `LLM_PROVIDER`, `LLM_MODEL_NAME`, `LLM_API_BASE`, `LLM_API_KEY`, `LLM_TEMPERATURE_DEFAULT`, `LLM_ALLOWED_MODELS`, `LLM_ALLOWED_API_BASES`, `ALLOW_EXTERNAL_API` từ environment khi khởi động. Hai allowlist là **JSON arrays**; model/endpoint mặc định cũng được tự đưa vào allowlist. Cấu hình, secret và chính sách phải nhất quán giữa tất cả process API/worker; thay env/secret cần rollout/restart theo quy trình.
- Admin có thể tạo và kích hoạt version không chứa credential trong DB; API kiểm tra role/account, allowlist và policy, kích hoạt atomic, ghi audit. Job ghim snapshot cấu hình ở attempt đầu và dùng lại khi phục hồi; tác vụ mới dùng version active. Assessment hiện bỏ qua profile/rubric đã có kết quả hoàn tất; đổi model không tự đánh giá lại hoặc thay kết quả trước đó. Cấu hình bị loại khỏi allowlist sẽ fail closed. Giao diện health chỉ cho biết policy của process trả lời, không chứng minh model hoạt động.
- Tất cả nhãn `local`, `compatible`, `openai`, `azure` dùng **cùng** endpoint OpenAI-compatible `POST /chat/completions`, JSON và `Authorization: Bearer` nếu có `LLM_API_KEY`. Không hỗ trợ trực tiếp Azure API native `api-key`/`api-version`, deployment path hoặc xác thực riêng; chỉ dùng Azure qua gateway tương thích đã phê duyệt. Một API key environment được gửi tới mọi endpoint được phép: không trộn endpoint cần các credential khác nhau trong cùng deployment; dùng gateway/secret isolation riêng khi cần.
- `ALLOW_EXTERNAL_API=false` mặc định chỉ cho endpoint phân giải thành địa chỉ private/loopback. Khi cho phép endpoint public, HTTP client yêu cầu HTTPS; URL không được chứa credential/query/fragment, client không dùng proxy từ environment. Kiểm tra DNS trước request **không pin DNS** và allowlist không thay thế firewall/egress proxy, TLS nội bộ, DLP, phê duyệt và giám sát. Không bật external chỉ để demo.

## Phục hồi worker và giám sát

Mỗi attempt giữ PostgreSQL session-level advisory lock, backend PID và token; worker xác minh fencing trước commit. Heartbeat chỉ là tín hiệu, **không phải lease** cho phép worker khác cướp job. Worker mới tự nhận job `PROCESSING` nếu lock cũ được giải phóng; cột `attempt_count`/`recovery_count`, heartbeat và event recovery được cập nhật. Hàng đợi quét theo trang để không bị kẹt sau 100 lock sống. Test cục bộ đã mô phỏng process crash, hai worker, mất DB connection, khôi phục lô và kiểm tra metric; vẫn cần diễn tập staging với topology thực.

1. Theo dõi `/v1/admin/worker/health` (chỉ ADMIN): pending, processing, heartbeat quá 2 phút, chạy quá 30 phút, thất bại/khôi phục 24 giờ và pending lâu nhất. `recoveries_24h` đếm **sự kiện còn lưu** được ghi từ khi có 00004; không backfill được lịch sử cũ, và xóa operation cũng xóa event. Thiết lập cảnh báo và liveness/monitoring bên ngoài: endpoint này **không chứng minh worker còn sống**.
2. Khi heartbeat cũ hoặc hàng đợi không tiến triển, xác minh log, process, DB connection và job với on-call; không tự reset `PROCESSING`, không dựa riêng vào thời gian. Session DB còn sống có thể giữ lock ngay cả khi worker treo hoặc mạng partition, do đó recovery có thể chậm đến khi PostgreSQL phát hiện session chết.
3. Nếu cần can thiệp, dừng worker/process đã xác minh theo quy trình, đánh giá ảnh hưởng các job khác; DBA chỉ kết thúc session PostgreSQL đã xác minh chính xác sau phê duyệt, không kill hàng loạt. Khi lock được giải phóng, worker mới nhận lại job và cập nhật attempt/event. Theo dõi tới trạng thái cuối, đối chiếu batch, assessment/ranking và phản hồi HR. Không dùng công cụ SQL để chiếm thử advisory lock trên hệ thống đang chạy nếu không hiểu và giải phóng lock.
4. Recovery là **at-least-once**, không exactly-once: cuộc gọi model có thể bị lặp và tính phí/lưu log nhiều lần. Kết quả DB được fencing/reconcile, nhưng storage có thể còn object orphan ở các attempt khác nhau. Với `cv-extracted-text`, `extracted.txt` và `pages.json` nằm trong thư mục token attempt; tham chiếu hiện hành nằm ở `document_processing_runs.extracted_text_storage_path`. Chỉ đối soát/thu gom sau thời gian chờ an toàn, backup, xác minh cả object cặp, mọi tham chiếu và job còn sống; dry-run, review thủ công, không xóa mù. CV gốc cũng cần đối soát `application_documents.storage_path` riêng.
5. Với job thất bại thực sự, khảo sát nguyên nhân (storage, model, quyền, network), khôi phục dịch vụ và dùng quy trình nghiệp vụ được phê duyệt để chạy lại. Không sửa trực tiếp DB hoặc tự coi kết quả AI là quyết định tuyển dụng.

## Khởi chạy phát triển

- `DATABASE_URL` chỉ backend/worker, có quyền SQL cần thiết trên `app_private` và SELECT các cột `id`, `email` của `auth.users` để quản lý tài khoản; không cấp cho browser. `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` dùng cho Supabase Auth backend; API hiện kiểm tra HS256/audience `authenticated`, project dùng asymmetric signing cần hỗ trợ JWKS trước. `SUPABASE_SERVICE_ROLE_KEY` chỉ backend/worker và bắt buộc khi tạo tài khoản và dùng Storage Supabase.
- `ADMIN_BOOTSTRAP_TOKEN` mặc định rỗng. Chỉ đặt token ngẫu nhiên đủ mạnh trong thời gian ngắn để khởi tạo Admin đầu tiên qua HTTPS/mạng hạn chế, sau đó xóa khỏi mọi backend và restart. Cơ chế one-time vẫn đóng sau khi Admin bị xóa/khóa; xem runbook ở [hướng dẫn VPS](doc/VPS_DEPLOYMENT.md#7-bootstrap-người-dùng-và-smoke-test). Không gửi secret/password trong chat hoặc log.
- Frontend gọi `/v1` cùng origin và Next proxy tới `API_INTERNAL_URL` phía server; không đưa địa chỉ backend localhost vào mã browser. Compose dùng `http://backend:8000`. Local Storage chỉ cho phát triển, cần backup/bảo vệ volume.

```bash
# Sau khi chuẩn bị DB, các migration được phê duyệt và backend/.env an toàn:
cd backend
python -m venv .venv
.venv/bin/python -m pip install --upgrade "pip>=26.2" "setuptools>=84.1.0"
.venv/bin/pip install -e .
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd frontend
cp .env.local.example .env.local # API_INTERNAL_URL đến backend
npm ci
npm run dev
```

`/health` là liveness, `/health/ready` chỉ kiểm tra database, không chứng minh Storage/AI. Đăng nhập cần user Supabase active và role/assignment. Compose (`cp .env.example .env`, điền secret an toàn, `docker compose up --build`) không tạo PostgreSQL/Supabase/LLM; worker chạy trong API. Docker/Compose chưa kiểm thử ở đây.

## Việc còn chặn production

Hoàn thành kiểm thử staging/e2e Auth/Storage/LLM/OCR với dữ liệu được phép; đánh giá chất lượng và bias, egress/DLP, retention/xóa, audit bất biến, bảo vệ session/XSS (`localStorage` đang chứa access token), DR/monitoring và phê duyệt pháp lý/bảo mật. Python dependencies chưa lock; cần quản lý chuỗi cung ứng và quét image định kỳ. Ngày 05/11/2026, `npm audit --omit=dev` báo 0 lỗ hổng; audit đầy đủ báo 6 moderate trong chuỗi dev-only `@typescript-eslint`/`minimatch`, cần theo dõi bản vá tương thích. Kết quả audit dependencies chỉ phản ánh thời điểm quét, không chứng minh image triển khai an toàn.
