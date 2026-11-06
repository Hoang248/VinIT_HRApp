# Triển khai VinUni HRApp trên VPS không dùng Docker

> Hướng dẫn này dành cho **staging/pilot với dữ liệu tổng hợp**, chạy trực tiếp bằng Python/Node trên Ubuntu và quản lý tiến trình bằng `systemd`. Đây chưa phải chứng nhận production. Supabase Auth/Storage thật, OCR, model thật và quy trình vận hành vẫn phải được kiểm thử đầu-cuối trong môi trường đích. Không dùng CV thật trước khi hoàn tất phê duyệt bảo mật/pháp lý, retention, backup/restore và đánh giá AI. Không đưa secret vào Git, log, ticket hay chat.

Tài liệu này thay cách chạy bằng Docker trong [`VPS_DEPLOYMENT.md`](VPS_DEPLOYMENT.md) bằng tiến trình native. Các yêu cầu về migration, quyền database, bảo mật và bootstrap vẫn tuân theo [`../DEPLOYMENT.md`](../DEPLOYMENT.md).

## 1. Kiến trúc

```text
Trình duyệt -- HTTPS :443 --> Nginx trên VPS
                                  |
                                  v
                         Next.js 127.0.0.1:3000
                                  |
                                  | proxy server-side /v1
                                  v
                         FastAPI 127.0.0.1:8000
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
          Supabase PostgreSQL/Auth/Storage   LLM endpoint được phê duyệt
```

- Chỉ Nginx nghe public trên cổng 80/443.
- Frontend và backend chỉ bind `127.0.0.1`; không mở 3000/8000 qua firewall.
- Backend là tiến trình duy nhất giữ `DATABASE_URL`, service-role key và JWT secret.
- Browser gọi `/v1` cùng origin; Next.js proxy sang backend ở phía server nên browser không cần biết địa chỉ backend.
- Worker xử lý nền chạy **trong cùng tiến trình backend**. Vì vậy bản đầu tiên chỉ chạy một tiến trình Uvicorn với `--workers 1`.
- Supabase và LLM là dịch vụ bên ngoài VPS, trừ khi LLM/Ollama được cài riêng trên chính VPS này.

## 2. Cần bao nhiêu file env?

Repo có ba file **mẫu** khác nhau vì repo hỗ trợ ba cách nạp cấu hình khác nhau. Các file đã điền giá trị thật đều bị Git bỏ qua; không phải lúc nào cũng phải dùng cả ba.

| File mẫu trong repo | File thật tương ứng | Ai đọc? | Khi chạy không Docker có cần không? |
|---|---|---|---|
| `.env.example` ở thư mục gốc | `.env` ở thư mục gốc | Docker Compose: nạp vào backend và nội suy các biến `HRA_*` | **Không.** Đây là file riêng cho Docker Compose. |
| `backend/.env.example` | `backend/.env` | FastAPI/Pydantic Settings của backend | **Có**, hoặc thay bằng một `EnvironmentFile` của systemd. Chỉ chọn một nguồn này cho backend. |
| `frontend/.env.local.example` | `frontend/.env.local` | Next.js khi chạy frontend trực tiếp | **Chỉ khi không inject bằng systemd.** Chỉ chứa `API_INTERNAL_URL`, không phải secret. |

### Cách hiểu đúng

1. **Backend có nhiều biến nhất** vì chỉ backend mới được kết nối PostgreSQL, Supabase Auth/Storage và LLM. Vì lý do đó, các secret nằm trong env của backend.
2. **Frontend gần như không có cấu hình** vì browser dùng `/v1` cùng origin. Frontend chỉ cần biết backend ở đâu qua `API_INTERNAL_URL` ở phía server.
3. **File gốc cho Docker bị trùng nhiều biến với file backend** vì Docker Compose dùng một file gốc để truyền cùng bộ cấu hình vào container backend; còn khi chạy trực tiếp, backend phải có file của riêng nó. Đây là trùng lặp để phục vụ hai chế độ chạy, không phải ba tiến trình cùng đọc ba file.
4. **Không chép secret của backend sang frontend.** Dù có thể gộp mọi biến vào một file hệ thống duy nhất, việc đó làm frontend có khả năng đọc cả `DATABASE_URL` và service-role key nếu cấu hình sai. Tách theo quyền tối thiểu an toàn hơn.

### Bộ cấu hình tối thiểu khi không dùng Docker

Chỉ cần hai nhóm:

- một file env cho backend, ví dụ `backend/.env`;
- một biến `API_INTERNAL_URL=http://127.0.0.1:8000` cho frontend, đặt ngay trong unit `systemd` ở mục 9, nên không cần thêm `frontend/.env.local`.

Không tạo `.env` ở thư mục gốc trong hướng dẫn này, trừ khi sau này quay lại Docker Compose.

## 3. Điều kiện trước khi cài

- VPS Ubuntu 24.04 LTS, quyền `sudo`, SSH đang hoạt động.
- DNS của domain, ví dụ `hr.example.com`, đã trỏ tới IP VPS. Nếu có bản ghi AAAA thì IPv6 của VPS cũng phải hoạt động.
- Ước lượng ban đầu: 2 vCPU, 4 GB RAM, 30 GB ổ đĩa cho app/OCR thử nghiệm. LLM chạy local thường cần thêm RAM/VRAM đáng kể; build frontend cũng có thể tốn RAM.
- Project Supabase đã chuẩn bị PostgreSQL, Auth và hai bucket private `cv-originals`, `cv-extracted-text`.
- Backend hiện tại phụ thuộc migration `00005_account_administration.sql`. Project `myrymlqdbyqmpynesiwk` đã áp migration này ở version remote `20261105163626` ngày 05/11/2026; môi trường khác phải đối chiếu và xin phê duyệt migration riêng, không chạy `supabase db push`/reset mù quáng.
- Một LLM endpoint tương thích OpenAI đã được phê duyệt. Nếu chưa có model reachable từ backend thì có thể deploy web/API, nhưng không chạy được xử lý AI.
- Backend hiện xác minh JWT bằng `HS256` với `SUPABASE_JWT_SECRET`, audience `authenticated`. Không tự đổi project sang signing key asymmetric/JWKS trước khi backend được nâng cấp tương ứng.
- Service-role key từng lộ trong lịch sử Git vẫn là việc bảo mật riêng phải thu hồi theo kế hoạch trong `DEPLOYMENT.md`; tạo key mới không tự thu hồi key legacy.

## 4. Cài gói hệ thống

Cài Python, Node.js, Nginx, Certbot và các thư viện hệ thống cho OCR/xử lý tài liệu:

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates curl git nginx certbot python3-certbot-nginx \
  python3 python3-venv python3-pip build-essential \
  tesseract-ocr tesseract-ocr-eng poppler-utils libmagic1 libreoffice-writer
```

Backend yêu cầu Python `>=3.11`; Python mặc định của Ubuntu 24.04 đáp ứng yêu cầu này. Cài Node.js 22 LTS theo hướng dẫn chính thức của NodeSource tại thời điểm triển khai, sau đó kiểm tra:

```bash
python3 --version
node --version
npm --version
nginx -v
```

Các gói `tesseract-ocr`, `poppler-utils`, `libmagic1` và `libreoffice-writer` tương ứng với dependency hệ thống mà bản Docker từng cài cho OCR và đọc PDF/DOCX. Thiếu chúng, API vẫn có thể khởi động nhưng xử lý một số định dạng CV sẽ lỗi.

Mở firewall theo chính sách của nhà cung cấp và hệ điều hành. Nếu dùng UFW qua SSH, phải cho phép **cổng SSH đang dùng trước** rồi mới bật:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

Không mở public cổng 3000 hoặc 8000.

## 5. Tạo user và thư mục chạy

Dùng một user hệ thống riêng, không chạy app bằng `root`:

```bash
sudo useradd --system --create-home \
  --home-dir /opt/vinit-hrapp --shell /usr/sbin/nologin vinit-hrapp \
  2>/dev/null || true
sudo install -d -o vinit-hrapp -g vinit-hrapp -m 0750 /opt/vinit-hrapp
sudo install -d -m 0755 /etc/vinit-hrapp
sudo install -d -o vinit-hrapp -g vinit-hrapp -m 0750 /var/lib/vinit-hrapp/storage
```

Nếu cần Git SSH deploy key, tạo key riêng chỉ có quyền đọc repo và đặt trong thư mục `.ssh` của user `vinit-hrapp` theo quy trình quản lý khóa của tổ chức. Không đưa personal access token vào URL clone hoặc shell history.

## 6. Lấy mã theo commit đã duyệt

Luôn deploy một commit SHA đã review, không tự động lấy đầu nhánh đang thay đổi:

```bash
APP_DIR=/opt/vinit-hrapp/app
REPO_URL='git@github.com:ratrichero/VinIT_HRApp.git'
RELEASE_SHA='THAY_BANG_COMMIT_SHA_DA_DUYET'

if [ ! -d "$APP_DIR/.git" ]; then
  sudo -u vinit-hrapp git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
sudo -u vinit-hrapp git fetch origin
sudo -u vinit-hrapp git checkout --detach "$RELEASE_SHA"
sudo -u vinit-hrapp git rev-parse HEAD
```

Thay `REPO_URL` bằng địa chỉ repo thực tế nếu khác.

## 7. Chuẩn bị CA và file env duy nhất cho backend

### 7.1. CA của PostgreSQL

Tải certificate/CA của Supabase qua kênh nhà cung cấp đã xác thực, kiểm tra theo quy trình của tổ chức rồi cài lên VPS:

```bash
sudo install -m 0644 /duong/dan/da/xac-thuc/supabase-db-ca.crt \
  /etc/vinit-hrapp/supabase-db-ca.crt
```

Khi không dùng Docker, đường dẫn trong `DATABASE_URL` phải là đường dẫn **trên VPS**:

```text
/etc/vinit-hrapp/supabase-db-ca.crt
```

Không dùng đường dẫn `/run/secrets/supabase-db-ca.crt`; đó là đường dẫn mount bên trong container của bản Docker.

### 7.2. Tạo `backend/.env`

```bash
cd /opt/vinit-hrapp/app/backend
sudo -u vinit-hrapp cp .env.example .env
sudo chmod 600 .env
sudo -u vinit-hrapp ${EDITOR:-nano} .env
```

Điền giá trị thật trực tiếp trong editor hoặc secret manager. Ví dụ dưới đây chỉ là hình dạng cấu hình, không phải credential hoạt động:

```dotenv
APP_ENV=production
APP_NAME="VinUni HRA API"
DEBUG=false
API_V1_PREFIX=/v1

# Kết nối PostgreSQL trực tiếp qua TLS. URL-encode ký tự đặc biệt trong mật khẩu.
DATABASE_URL=postgresql://DB_USER:URL_ENCODED_PASSWORD@DB_HOST:5432/postgres?sslmode=verify-full&sslrootcert=/etc/vinit-hrapp/supabase-db-ca.crt
DATABASE_POOL_SIZE=5

# Đúng project Supabase. Hai secret dưới đây chỉ nằm ở backend.
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=THAY_BANG_PUBLISHABLE_OR_ANON_KEY_CUA_PROJECT
SUPABASE_SERVICE_ROLE_KEY=THAY_BANG_SECRET_OR_SERVICE_ROLE_KEY_CHI_O_BACKEND
SUPABASE_JWT_SECRET=THAY_BANG_HS256_JWT_SECRET_TUONG_UNG

# Để trống. Chỉ đặt tạm trong cửa sổ bootstrap Admin được phê duyệt.
ADMIN_BOOTSTRAP_TOKEN=

STORAGE_BACKEND=supabase
LOCAL_STORAGE_PATH=/var/lib/vinit-hrapp/storage
SUPABASE_STORAGE_BUCKET_CV=cv-originals
SUPABASE_STORAGE_BUCKET_EXTRACTED=cv-extracted-text

LLM_PROVIDER=local
LLM_MODEL_NAME=llama3.1:8b
LLM_API_BASE=http://127.0.0.1:11434/v1
LLM_API_KEY=
LLM_TEMPERATURE_DEFAULT=0.1
LLM_ALLOWED_MODELS=[]
LLM_ALLOWED_API_BASES=[]
ALLOW_EXTERNAL_API=false

MIN_EVIDENCE_COVERAGE=0.7
CORS_ORIGINS=["https://hr.example.com"]
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

Lưu ý quan trọng:

- `LLM_API_BASE=http://127.0.0.1:11434/v1` chỉ đúng nếu Ollama/LLM server chạy **trên cùng VPS**. Nếu model ở máy khác, thay bằng địa chỉ private mà tiến trình backend truy cập được. Khi không dùng Docker, `localhost` nghĩa là chính VPS, không phải container backend.
- Cấu hình AI `ACTIVE` trong database có thể được ưu tiên hơn env. Sau khi có Admin, dùng **Admin → Cấu hình AI** để tạo/kích hoạt endpoint và model nằm trong allowlist; không sửa trực tiếp bản ghi ACTIVE bằng SQL.
- Model/endpoint mặc định từ env tự được đưa vào allowlist. Các giá trị bổ sung trong `LLM_ALLOWED_MODELS` và `LLM_ALLOWED_API_BASES` phải là JSON array.
- Không bật `ALLOW_EXTERNAL_API=true` chỉ để thử nhanh. Endpoint public phải được phê duyệt, dùng HTTPS và có kiểm soát egress/DLP phù hợp.
- Tài khoản trong `DATABASE_URL` phải có quyền nghiệp vụ cần thiết trên `app_private`, đồng thời có quyền `SELECT` trên hai cột `id`, `email` của `auth.users` để quản lý tài khoản. Đây là quyền mạnh, chỉ cấp cho backend theo phê duyệt DBA; service-role API key không tự thay thế tài khoản đăng nhập PostgreSQL.
- Không dùng PgBouncer transaction/statement pooling cho worker. Worker giữ session PostgreSQL và advisory lock trong suốt một attempt; ưu tiên direct connection hoặc session pooler đã được kiểm chứng giữ cùng backend process/session.

## 8. Cài và build ứng dụng

### 8.1. Backend Python

```bash
cd /opt/vinit-hrapp/app/backend
sudo -u vinit-hrapp python3 -m venv .venv
sudo -u vinit-hrapp .venv/bin/python -m pip install --upgrade pip setuptools
sudo -u vinit-hrapp .venv/bin/python -m pip install .
```

Kiểm tra nhanh việc nạp cấu hình mà không in secret:

```bash
curl --version >/dev/null
sudo -u vinit-hrapp .venv/bin/python -c \
  'from app.core.config import settings; print(settings.APP_ENV, settings.STORAGE_BACKEND)'
```

Không dùng lệnh in toàn bộ `settings` hoặc nội dung `.env` vào log/ticket.

### 8.2. Frontend Next.js

```bash
cd /opt/vinit-hrapp/app/frontend
sudo -u vinit-hrapp npm ci
sudo -u vinit-hrapp npm run build
```

Project đã bật `output: 'standalone'`. Bổ sung static assets và thư mục public vào bản standalone:

```bash
sudo -u vinit-hrapp rm -rf .next/standalone/.next/static .next/standalone/public
sudo -u vinit-hrapp cp -a .next/static .next/standalone/.next/static
sudo -u vinit-hrapp cp -a public .next/standalone/public
```

Không cần `frontend/.env.local` nếu biến `API_INTERNAL_URL` được đặt trong systemd ở bước tiếp theo. Nếu chạy thử bằng `npm run dev`, khi đó mới sao chép mẫu:

```bash
cp .env.local.example .env.local
```

Hai cách này là **lựa chọn thay thế**, không cần dùng đồng thời.

## 9. Tạo service systemd

### 9.1. Backend

Tạo `/etc/systemd/system/vinit-hrapp-backend.service`:

```ini
[Unit]
Description=VinUni HRApp Backend
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=vinit-hrapp
Group=vinit-hrapp
WorkingDirectory=/opt/vinit-hrapp/app/backend
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/vinit-hrapp/app/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Backend đọc `backend/.env` vì `WorkingDirectory` là thư mục `backend` và cấu hình Pydantic dùng `env_file=".env"`. Không đồng thời khai báo lại cùng một bộ secret trong unit nếu không có lý do; chỉ giữ một nguồn cấu hình để tránh giá trị bị lệch.

### 9.2. Frontend

Tạo `/etc/systemd/system/vinit-hrapp-frontend.service`:

```ini
[Unit]
Description=VinUni HRApp Frontend
Wants=network-online.target
After=network-online.target vinit-hrapp-backend.service

[Service]
Type=simple
User=vinit-hrapp
Group=vinit-hrapp
WorkingDirectory=/opt/vinit-hrapp/app/frontend/.next/standalone
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=HOSTNAME=127.0.0.1
Environment=API_INTERNAL_URL=http://127.0.0.1:8000
ExecStart=/usr/bin/node server.js
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

`API_INTERNAL_URL` không chứa `/v1` ở cuối. Route proxy của Next.js sẽ tự ghép đường dẫn `/v1/...` khi chuyển request sang backend.

### 9.3. Kích hoạt và kiểm tra local

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vinit-hrapp-backend.service
sudo systemctl enable --now vinit-hrapp-frontend.service
sudo systemctl status vinit-hrapp-backend.service --no-pager
sudo systemctl status vinit-hrapp-frontend.service --no-pager

curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:8000/health/ready
curl --fail --silent --show-error --output /dev/null http://127.0.0.1:3000/
ss -ltnp | grep -E ':(3000|8000) '
```

Kết quả kỳ vọng:

- `/health` báo backend đang sống.
- `/health/ready` báo database `connected`. Endpoint này chỉ chứng minh kết nối DB, không chứng minh quyền nghiệp vụ, Auth, Storage hay AI.
- Cả hai cổng 3000 và 8000 chỉ xuất hiện ở `127.0.0.1`.

Xem log khi service lỗi:

```bash
sudo journalctl -u vinit-hrapp-backend.service -n 200 --no-pager
sudo journalctl -u vinit-hrapp-frontend.service -n 200 --no-pager
```

Không gửi log có khả năng chứa token, đường dẫn CV hoặc nội dung hồ sơ ra kênh không được phê duyệt.

## 10. Cấu hình Nginx và HTTPS

Tạo `/etc/nginx/sites-available/vinit-hrapp`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name hr.example.com;

    client_max_body_size 260m;
    server_tokens off;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_request_buffering off;
        proxy_buffering off;
    }
}
```

Kích hoạt site và kiểm tra:

```bash
sudo ln -s /etc/nginx/sites-available/vinit-hrapp \
  /etc/nginx/sites-enabled/vinit-hrapp
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Cấp chứng chỉ Let's Encrypt và chuyển hướng sang HTTPS:

```bash
sudo certbot --nginx -d hr.example.com --redirect
sudo certbot renew --dry-run
curl --fail --silent --show-error --output /dev/null https://hr.example.com/
```

Kiểm tra từ một máy ngoài VPS:

- `https://hr.example.com` mở được và chứng chỉ hợp lệ.
- Không truy cập trực tiếp được `http://IP-VPS:3000` hoặc `http://IP-VPS:8000`.
- Upload file tổng hợp nhỏ đi qua được `/v1` mà không lỗi giới hạn kích thước của Nginx.

## 11. Bootstrap Admin và smoke test

Chỉ thực hiện phần này khi database của môi trường đích chưa từng có Admin.

1. Kiểm tra bằng quyền DBA:

   ```sql
   SELECT singleton, initialized_at, initialized_by
   FROM app_private.account_initialization;

   SELECT user_id, role_code, revoked_at
   FROM app_private.user_role_assignments
   WHERE role_code = 'ADMIN';
   ```

   Migration cũng đóng bootstrap nếu đã có bất kỳ assignment `ADMIN` nào, kể cả assignment đã thu hồi. Nếu `initialized_at` đã có giá trị, không tìm cách reset marker bằng SQL.

2. Nếu bootstrap còn mở, tạo token ngẫu nhiên mạnh bằng secret manager. Có thể tạo giá trị có ít nhất 32 byte entropy bằng:

   ```bash
   python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
   ```

   Không để token xuất hiện trong tài liệu triển khai, ticket hoặc lịch sử lệnh được chia sẻ.

3. Đặt token tạm vào `ADMIN_BOOTSTRAP_TOKEN` trong `backend/.env`, sau đó restart **chỉ backend**:

   ```bash
   sudo systemctl restart vinit-hrapp-backend.service
   ```

4. Qua HTTPS và mạng/VPN/IP allowlist tin cậy, mở trang đăng nhập của ứng dụng và chọn chức năng khởi tạo Admin đầu tiên. Tạo tài khoản Admin bằng email và mật khẩu do người vận hành quản lý trong secret manager.

5. Xóa token khỏi `backend/.env` rồi restart backend lần nữa:

   ```bash
   sudo systemctl restart vinit-hrapp-backend.service
   ```

6. Kiểm tra lại `initialized_at` đã được ghi. Từ thời điểm này, việc tạo Admin qua bootstrap phải bị đóng.

Smoke test tối thiểu bằng dữ liệu tổng hợp:

1. Admin tạo một tài khoản HR với role `HR_RECRUITER` và một tài khoản HM với role `HIRING_MANAGER`. HR và HM phải là hai người/tài khoản khác nhau cho hai bước duyệt.
2. Đăng nhập bằng tài khoản mới và xác nhận ứng dụng bắt đổi mật khẩu tạm trước khi vào nghiệp vụ.
3. HR tạo một vị trí tổng hợp và gán đúng HM.
4. Kiểm tra luồng duyệt hai bước HR/HM theo quyền của từng tài khoản.
5. Admin kiểm tra `/v1/admin/worker/health`; xác nhận hàng đợi không có job bị treo bất thường.
6. Upload CV tổng hợp, chờ worker xử lý và kiểm tra trích xuất/chấm điểm bằng model thật đã được kích hoạt.

## 12. Cập nhật và rollback

### 12.1. Cập nhật trong cửa sổ bảo trì

Worker chạy trong backend nên không rollout lẫn tiến trình cũ và mới trên cùng database đang có job.

1. Thông báo cửa sổ bảo trì, ngăn người dùng tạo job mới.
2. Với quyền Admin, kiểm tra `/v1/admin/worker/health`; chờ `processing` và `pending` về trạng thái an toàn theo quy trình vận hành.
3. Dừng frontend rồi backend:

   ```bash
   sudo systemctl stop vinit-hrapp-frontend.service
   sudo systemctl stop vinit-hrapp-backend.service
   ```

4. Checkout SHA mới, cài lại dependency và build:

   ```bash
   cd /opt/vinit-hrapp/app
   sudo -u vinit-hrapp git fetch origin
   sudo -u vinit-hrapp git checkout --detach THAY_BANG_COMMIT_SHA_MOI

   cd backend
   sudo -u vinit-hrapp .venv/bin/python -m pip install .

   cd ../frontend
   sudo -u vinit-hrapp npm ci
   sudo -u vinit-hrapp npm run build
   sudo -u vinit-hrapp cp -a .next/static/. .next/standalone/.next/static/
   sudo -u vinit-hrapp cp -a public/. .next/standalone/public/
   ```

5. Nếu release có migration mới, dừng tại đây và thực hiện quy trình migration/staging/backup/rollback đã được phê duyệt riêng. Không tự áp migration chỉ vì code mới đã được checkout.
6. Khởi động và kiểm tra:

   ```bash
   sudo systemctl start vinit-hrapp-backend.service
   curl --fail http://127.0.0.1:8000/health/ready
   sudo systemctl start vinit-hrapp-frontend.service
   curl --fail --output /dev/null http://127.0.0.1:3000/
   curl --fail --output /dev/null https://hr.example.com/
   ```

### 12.2. Rollback code

Nếu bản mới lỗi và không phụ thuộc thay đổi database không tương thích ngược:

1. Dừng frontend/backend và drain worker như trên.
2. Checkout lại SHA trước đó.
3. Cài lại backend, build lại frontend và bổ sung static/public vào standalone như bước cập nhật.
4. Khởi động backend trước, kiểm tra `/health/ready`, sau đó khởi động frontend và kiểm tra HTTPS.

Không tự rollback migration bằng cách sửa bảng migration history hoặc chạy reset. Rollback database phải theo kế hoạch đã thử trên staging.

## 13. Vận hành hằng ngày

```bash
# Trạng thái
sudo systemctl status vinit-hrapp-backend.service --no-pager
sudo systemctl status vinit-hrapp-frontend.service --no-pager

# Log trực tiếp
sudo journalctl -u vinit-hrapp-backend.service -f
sudo journalctl -u vinit-hrapp-frontend.service -f

# Restart sau khi thay backend/.env
sudo systemctl restart vinit-hrapp-backend.service

# Kiểm tra cổng public/loopback
ss -ltnp | grep -E ':(80|443|3000|8000) '
```

- Sao lưu PostgreSQL và hai bucket Supabase theo chính sách của tổ chức; phải thử restore trên staging trước khi coi backup là dùng được.
- Sao lưu an toàn file cấu hình và CA, nhưng không sao lưu secret vào Git hoặc kho không mã hóa.
- Theo dõi dung lượng đĩa vì OCR/libreoffice và file tạm có thể phát sinh dữ liệu lớn.
- Theo dõi `/v1/admin/worker/health` bằng tài khoản Admin và thiết lập giám sát ngoài ứng dụng; endpoint này không tự chứng minh worker còn sống.
- Định kỳ cập nhật Ubuntu, Node.js, Python package và kiểm tra `certbot renew`.
- Nếu đổi env, model allowlist hoặc secret, restart backend và bảo đảm mọi tiến trình backend dùng cùng cấu hình. Job đã bắt đầu có thể giữ snapshot cấu hình AI cũ.

## 14. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân hay gặp | Cách kiểm tra |
|---|---|---|
| Backend không start | `.env` sai định dạng, thiếu biến hoặc không kết nối được DB | `journalctl -u vinit-hrapp-backend.service`; kiểm tra quyền `600` và `WorkingDirectory` |
| `/health` được nhưng `/health/ready` lỗi | Sai `DATABASE_URL`, CA, hostname TLS hoặc quyền DB | Kiểm tra đường dẫn `/etc/vinit-hrapp/supabase-db-ca.crt`, `sslmode=verify-full` và kết nối direct/session phù hợp |
| Frontend mở được nhưng API báo 502 | Backend chưa chạy hoặc `API_INTERNAL_URL` sai | `curl http://127.0.0.1:8000/health`; kiểm tra biến trong frontend unit rồi restart frontend |
| Đăng nhập lỗi sau khi đổi signing key | Backend hiện chỉ hỗ trợ HS256/JWKS chưa tương thích | Không tự rotate signing key; khôi phục cấu hình đã phê duyệt và xem `DEPLOYMENT.md` |
| Upload lớn bị Nginx chặn | `client_max_body_size` nhỏ hơn lô CV | Đặt khoảng `260m` và kiểm tra giới hạn app trong backend env |
| OCR/DOCX lỗi | Thiếu gói hệ thống | Kiểm tra `tesseract`, `pdftotext`, LibreOffice và log backend |
| AI không chạy | Model endpoint không reachable hoặc config ACTIVE trỏ loopback/endpoint cũ | Kiểm tra `LLM_API_BASE` từ chính VPS và cấu hình AI ACTIVE trong Admin |
| Worker không tiến triển | DB session/lock, model/storage lỗi hoặc backend đã dừng | Kiểm tra `/v1/admin/worker/health`, journal backend và kết nối DB; không tự reset job `PROCESSING` |

## 15. Khác biệt cần nhớ so với bản Docker

| Hạng mục | Docker Compose | Không Docker |
|---|---|---|
| File env gốc | Bắt buộc có `.env` ở root | Không dùng |
| Backend env | Compose truyền root `.env` vào container | `backend/.env` hoặc một `EnvironmentFile` của systemd |
| Địa chỉ backend từ frontend | `http://backend:8000` | `http://127.0.0.1:8000` |
| `localhost` của LLM | Là container backend, thường không phải host | Là chính VPS |
| Đường dẫn CA trong DB URL | `/run/secrets/supabase-db-ca.crt` | `/etc/vinit-hrapp/supabase-db-ca.crt` |
| Quản lý tiến trình | Docker restart policy | `systemd` |
| Cập nhật | Build lại image/container | Cài package, build frontend, restart service |

Tóm lại: bản không Docker **không cần nhiều file env hơn**. Chỉ backend cần một file env chứa secret; frontend cần đúng một biến địa chỉ backend và biến đó có thể nằm trong `systemd`, không cần tạo thêm file.
