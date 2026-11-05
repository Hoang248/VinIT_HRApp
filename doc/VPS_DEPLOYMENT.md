# Triển khai VinUni HRApp trên VPS Ubuntu

> Hướng dẫn này dành cho **staging/pilot với dữ liệu tổng hợp**, chưa phải chứng nhận production. Docker/Compose, Supabase Auth/Storage thật, OCR và model thật chưa được kiểm thử đầu-cuối trong môi trường đích. Không dùng CV thật trước khi hoàn tất kiểm thử, phê duyệt bảo mật/pháp lý, retention, bảo vệ session/XSS, backup/restore và đánh giá AI. Không đưa secret vào Git, log, ticket hay chat.

## 1. Kiến trúc và điều kiện

```text
Trình duyệt -- HTTPS :443 --> Nginx trên VPS --> 127.0.0.1:3000 frontend
                                              --> /v1 proxy nội bộ --> backend:8000
Backend + worker --> PostgreSQL/Supabase Auth + Storage; model được phê duyệt
```

Ví dụ dùng Ubuntu 24.04 LTS, DNS `hr.example.com` đã trỏ đến IP VPS, SSH quản trị và quyền `sudo`, Docker Engine 28+ với Compose plugin hiện hành, Nginx và Certbot. Mở cổng 80/443 và cổng SSH thực tế ở firewall nhà cung cấp/OS; nếu có bản ghi AAAA, IPv6 cũng phải hoạt động. Ước lượng ban đầu cho app/OCR thử nghiệm: 2 vCPU, 4 GB RAM và 30 GB ổ đĩa, sau đó đo tải; model local thường cần RAM/VRAM riêng lớn hơn nhiều. Upload tối đa 250 MB/lô có thể tăng bộ nhớ/đĩa tạm. Giới hạn truy cập staging bằng VPN/IP allowlist; không coi HTTPS là đủ bảo mật.

- Supabase/PostgreSQL, Auth, hai bucket private `cv-originals`/`cv-extracted-text` và model **phải được chuẩn bị riêng**. Compose không tạo các dịch vụ đó. Backend đang xác minh JWT `HS256` audience `authenticated`; project phát token chỉ dùng asymmetric/JWKS chưa tương thích. Kiểm tra tương thích trước, không tự thay đổi signing key của project.
- Có tài khoản Auth và profile/role tương ứng; tại lần kiểm tra project kết nối sau migration chưa có auth user/profile/ADMIN. Dùng tối thiểu hai người/tài khoản HR và HM khác nhau cho hai bước duyệt.
- Dùng PostgreSQL direct connection qua TLS; chỉ dùng session pooler sau khi xác minh session/backend PID và advisory lock được giữ xuyên các transaction. **Không dùng transaction/statement pooling** cho worker. Direct Supabase có thể cần IPv6; xác minh tuyến mạng hoặc session pooler phù hợp với project.
- `00004` đã được áp riêng vào project `myrymlqdbyqmpynesiwk`, version remote `20261105152817 recovery_and_privacy`. Với môi trường khác, trước hết đọc [lịch sử và checklist migration](../DEPLOYMENT.md#lịch-sử-project-đã-kết-nối), xin phê duyệt, thử staging/backup/restore và drain worker cũ. Tên/version remote không giống tiền tố file local; **không chạy `supabase db push`, reset hoặc migration repair mù quáng**.
- Service-role key từng xuất hiện trong lịch sử Git phải được thu hồi/rotate theo kế hoạch; đổi legacy JWT secret có thể vô hiệu hóa anon key, phiên và tích hợp. Chưa xác nhận việc rotate. Backend cần secret/DB credential; browser không được nhận service-role key hay DB URL.

## 2. Cài phần mềm trên VPS

Đây là ví dụ cho bản Ubuntu được Docker hỗ trợ; kiểm tra [tài liệu Docker Engine chính thức](https://docs.docker.com/engine/install/ubuntu/) và chính sách máy chủ trước khi chạy. Không pipe script cài đặt bên ngoài trực tiếp vào shell.

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git nginx certbot python3-certbot-nginx
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' \
  "$(dpkg --print-architecture)" "$VERSION_CODENAME" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker nginx
sudo docker version
sudo docker compose version
```

Lệnh trong tài liệu dùng `sudo docker` thay vì thêm người dùng vào nhóm `docker`: quyền Docker tương đương quyền root. Kiểm tra firewall nhà cung cấp và UFW/IPv6 theo chính sách; nếu bật UFW qua SSH, cho phép **cổng SSH đang dùng trước** để tránh tự khóa. Không dựa riêng vào UFW để chặn port Docker: chỉ bind app vào loopback và kiểm tra thêm từ một máy bên ngoài.

## 3. Lấy mã theo commit được duyệt

Dùng quyền đọc repository hợp lệ trên VPS, ví dụ SSH deploy key chỉ đọc được quản lý riêng; không đưa token vào URL hoặc shell history. Thay hai giá trị dưới đây bằng thông tin thực tế. Luôn pin SHA đã review; không deploy tự động từ đầu nhánh đang thay đổi.

```bash
REPO_URL='git@github.com:ratrichero/VinIT_HRApp.git'
RELEASE_SHA='THAY_BANG_COMMIT_SHA_DA_DUYET'
sudo install -d -o "$USER" -g "$(id -gn)" -m 0750 /opt/vinit-hrapp
git clone "$REPO_URL" /opt/vinit-hrapp
cd /opt/vinit-hrapp
git fetch origin
git checkout --detach "$RELEASE_SHA"
git rev-parse HEAD
```

## 4. Cấu hình bí mật, TLS database và AI

Lấy CA PostgreSQL của project qua kênh nhà cung cấp đã xác thực, xác minh fingerprint theo quy trình tổ chức rồi đặt nó trên VPS. CA không phải mật khẩu, nhưng không được thay bằng file chưa tin cậy. Thay đường dẫn nguồn ví dụ:

```bash
sudo install -d -m 0755 /etc/vinit-hrapp
sudo install -m 0644 /secure/path/supabase-db-ca.crt /etc/vinit-hrapp/supabase-db-ca.crt
cd /opt/vinit-hrapp
umask 077
cp .env.example .env
chmod 600 .env
${EDITOR:-nano} .env
```

Điền các giá trị thật **trong editor/secret manager**, không paste vào lệnh hay commit. Ví dụ hình dạng (không phải credential hoặc endpoint hoạt động):

```dotenv
APP_ENV=production
DEBUG=false
HRA_BACKEND_BIND=127.0.0.1
HRA_FRONTEND_BIND=127.0.0.1
HRA_DB_CA_PATH=/etc/vinit-hrapp/supabase-db-ca.crt
DATABASE_URL=postgresql://DB_USER:URL_ENCODED_PASSWORD@DB_HOST:5432/postgres?sslmode=verify-full&sslrootcert=/run/secrets/supabase-db-ca.crt
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=THAY_BANG_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=THAY_BANG_SERVICE_ROLE_KEY_DA_ROTATE
SUPABASE_JWT_SECRET=THAY_BANG_LEGACY_HS256_SECRET_TUONG_UNG
STORAGE_BACKEND=supabase
SUPABASE_STORAGE_BUCKET_CV=cv-originals
SUPABASE_STORAGE_BUCKET_EXTRACTED=cv-extracted-text
LLM_PROVIDER=local
LLM_MODEL_NAME=llama3.1:8b
LLM_API_BASE=http://10.20.0.12:11434/v1
LLM_API_KEY=
LLM_ALLOWED_MODELS=[]
LLM_ALLOWED_API_BASES=[]
ALLOW_EXTERNAL_API=false
CORS_ORIGINS=["https://hr.example.com"]
```

- Dùng DB host/user/port thực tế và tài khoản backend được cấp quyền tối thiểu cần thiết trên `app_private`, có kết nối session ổn định. Backend kết nối SQL trực tiếp, không đặt `auth.uid()` theo từng request: role DB phải được DBA cấu hình quyền table/schema **và** khả năng truy cập phù hợp với RLS (ví dụ một role backend-only được phê duyệt có BYPASSRLS); chỉ grant table cho role thường là chưa đủ. Đây là quyền mạnh, không cấp cho browser, và phải test đầy đủ nghiệp vụ. Service-role API key không tự trở thành tài khoản đăng nhập PostgreSQL. URL-encode các ký tự đặc biệt trong password; `verify-full` kiểm tra cả CA và hostname. `docker-compose.vps.yml` mount file CA host từ `HRA_DB_CA_PATH` vào `/run/secrets/supabase-db-ca.crt` chỉ đọc và báo lỗi nếu file nguồn không tồn tại. `/health/ready` chỉ chứng minh kết nối, không chứng minh quyền RLS/CRUD; kiểm tra nghiệp vụ riêng và không hạ TLS chỉ để bỏ qua lỗi.
- `SUPABASE_ANON_KEY`, service-role key và JWT secret phải thuộc đúng project; service-role/JWT secret chỉ nằm trong môi trường backend. Restrict `.env`, backups và quyền Docker; environment container có thể đọc bởi quản trị viên Docker. Không chạy `docker compose config` thông thường trong log vì có thể in secret; dùng `config --quiet`.
- `10.20.0.12` chỉ minh họa một model endpoint private đã được phép; thay bằng địa chỉ **từ container backend** có thể truy cập. `127.0.0.1`/`localhost` bên trong container là chính container backend, không phải model chạy trên host. Endpoint mặc định và model mặc định tự nằm trong allowlist; các giá trị bổ sung dùng JSON array. Nếu chưa có model thì không chạy xử lý AI.
- Cấu hình AI ACTIVE đã có trong DB được ưu tiên hơn env. Project đã kiểm tra đang có endpoint ACTIVE dạng loopback, vì vậy sau khi có ADMIN hãy vào **Admin → Cấu hình AI**, tạo/kích hoạt version với model/endpoint nằm trong allowlist và reachable từ backend. Không tự sửa hàng ACTIVE qua SQL. Thay env/secret cần restart/redeploy mọi process; job đang chạy giữ snapshot cũ. `allowed_by_this_process` không chứng minh model hoạt động.
- Nếu sử dụng endpoint public, phải được phê duyệt, dùng HTTPS và đặt `ALLOW_EXTERNAL_API=true`. Che PII và guardrails hiện chỉ best effort; egress firewall, DLP, TLS, đánh giá bias và giám sát vẫn bắt buộc. Nhãn `azure` chỉ hoạt động qua gateway OpenAI-compatible/Bearer, không hỗ trợ Azure native. Xem [chính sách AI](../DEPLOYMENT.md#cấu-hình-ai-và-egress).

## 5. Khởi chạy Compose

Thực hiện từ `/opt/vinit-hrapp`; lệnh đầu chỉ kiểm cấu hình mà không in env. File base bind `3000` và `8000` vào `127.0.0.1` theo mặc định; override VPS mount CA. Dùng một replica backend ban đầu: worker chạy trong mỗi process API.

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml config --quiet
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml ps
curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:8000/health/ready
curl --fail --silent --show-error --output /dev/null http://127.0.0.1:3000/
ss -ltn | grep -E ':(3000|8000) '
```

Phải thấy hai cổng chỉ bind `127.0.0.1`, không phải `0.0.0.0`/`::`. Từ mạng ngoài, kiểm tra 3000/8000 không truy cập được; chỉ public Nginx 80/443. `/health/ready` chỉ kiểm tra kết nối DB, không chứng minh quyền nghiệp vụ, Auth, Storage hoặc AI. Local CV volume vẫn tồn tại dù dùng Supabase Storage; **không dùng `docker compose down -v`** với dữ liệu cần giữ. Đảm bảo backup/mã hóa cho bất kỳ volume hoặc thư mục tạm nào chứa CV.

## 6. Nginx và HTTPS

Chỉnh `server_name` dưới đây thành domain thật. Mở port 80 để cấp/gia hạn chứng chỉ; chỉ bật `listen [::]:80` sau khi IPv6 VPS hoạt động. Nginx proxy **toàn bộ** request tới frontend; browser không gọi backend/localhost trực tiếp. `260m` lớn hơn 250.000.000 byte/lô cộng multipart overhead; backend vẫn áp giới hạn riêng. Tắt buffering giảm nguy cơ ghi CV vào proxy temp file nhưng vẫn cần đánh giá cấu hình/log/ổ đĩa thực tế.

```bash
sudo tee /etc/nginx/sites-available/vinit-hrapp >/dev/null <<'NGINX'
server {
    listen 80;
    # listen [::]:80;
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
        proxy_connect_timeout 10s;
        proxy_send_timeout 480s;
        proxy_read_timeout 480s;
    }
}
NGINX
# Sửa domain trong file trước khi enable; tránh xung đột site đã có.
sudo nano /etc/nginx/sites-available/vinit-hrapp
sudo ln -s /etc/nginx/sites-available/vinit-hrapp /etc/nginx/sites-enabled/vinit-hrapp
sudo nginx -t && sudo systemctl reload nginx
# Thay domain bằng domain thực tế; Certbot sẽ yêu cầu thông tin quản trị cần thiết.
sudo certbot --nginx -d hr.example.com --redirect
sudo certbot renew --dry-run
```

Kiểm tra `https://<domain>/` từ ngoài VPS, certificate/redirect và lịch gia hạn. Cấu hình hạn chế IP/VPN, chống brute force/rate limit ở gateway và giám sát theo chính sách. Không ghi request body, mật khẩu, token hay CV vào access/error log; giới hạn quyền và retention log. Các config Nginx/certificate chưa được thử trên VPS trong phiên này.

## 7. Bootstrap người dùng và smoke test

1. Tạo/invite các user qua Supabase Auth dashboard theo quy trình được duyệt; không chèn password trực tiếp bằng SQL. Xác minh login/email confirmation và thuật toán token phù hợp. Dùng ba UUID đã xác minh cho ADMIN, HR và HM; HR và HM phải là **hai tài khoản khác nhau**.
2. DBA được ủy quyền chạy ví dụ sau trong SQL Editor sau khi thay UUID và tên. `DO NOTHING` không ghi đè profile đã có và **không tự khôi phục role bị thu hồi**; kiểm tra các tài khoản/role hiện hữu riêng, ghi nhận thay đổi theo change-control. Chỉ cấp quyền cần thiết và chỉ làm trên môi trường được phê duyệt.

```sql
BEGIN;
INSERT INTO app_private.user_profiles (user_id, display_name, preferred_locale, account_status)
VALUES
  ('<ADMIN_USER_UUID>'::uuid, 'Quản trị viên', 'vi', 'ACTIVE'),
  ('<HR_USER_UUID>'::uuid, 'HR thử nghiệm', 'vi', 'ACTIVE'),
  ('<HM_USER_UUID>'::uuid, 'HM thử nghiệm', 'vi', 'ACTIVE')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO app_private.user_role_assignments (user_id, role_code)
VALUES
  ('<ADMIN_USER_UUID>'::uuid, 'ADMIN'),
  ('<HR_USER_UUID>'::uuid, 'HR_RECRUITER'),
  ('<HM_USER_UUID>'::uuid, 'HIRING_MANAGER')
ON CONFLICT (user_id, role_code) DO NOTHING;
COMMIT;
```

3. Đăng nhập ADMIN qua HTTPS, chọn và kích hoạt AI config được phép, kiểm tra worker health; kiểm tra model thật bằng dữ liệu giả được phê duyệt. HR tạo vị trí và gán HM, HR rồi HM duyệt, tải CV giả, theo dõi job/ranking, sửa profile và thử chia sẻ chỉ tóm tắt, feedback/thu hồi. Kiểm tra HM không xem được ghi chú HR, contact/CV/evidence khi chỉ có summary share. Đây là kiểm thử bắt buộc tại môi trường đích, chưa được thực hiện ở đây.
4. Thiết lập backup PostgreSQL và hai bucket, mã hóa, thử restore; giám sát liveness, readiness, worker, queue, ổ đĩa, TLS và chi phí model. Xem [runbook recovery](../DEPLOYMENT.md#phục-hồi-worker-và-giám-sát). Xem log qua `sudo docker compose -f docker-compose.yml -f docker-compose.vps.yml logs --tail=100` chỉ trong môi trường quản trị; rà/xóa dữ liệu nhạy cảm trước khi chia sẻ.

## 8. Cập nhật, rollback và sự cố

- Bật maintenance/ngừng nhận job mới; cho PENDING/PROCESSING hoàn tất, kiểm tra queue và **drain tất cả backend/worker cũ** trước migration hoặc rollout. Không chạy worker cũ đồng thời với worker mới; worker cũ không có advisory lock. Backup và thử restore DB/Storage trước thay đổi.
- Trên bản checkout sạch, `git fetch origin`, chọn SHA đã duyệt rồi dùng lại hai file Compose để `up -d --build`; kiểm tra health, version, queue và smoke test giả trước mở traffic. Không scale backend hoặc chạy thêm worker tùy tiện khi chưa đánh giá tài nguyên, kết nối DB và quy trình recovery.
- Nếu lỗi, giữ maintenance, dừng/drain worker mới và làm theo kế hoạch rollback đã thử. Không tự chạy phiên bản cũ trên job mới hoặc reset migration/DB; khôi phục từ backup có thể làm mất dữ liệu mới và cần phê duyệt. Không xóa volume/bucket để “sửa nhanh”.
- Đọc [DEPLOYMENT.md](../DEPLOYMENT.md) cho health, at-least-once, kết nối session, CV link còn hiệu lực sau revoke và thu gom orphan an toàn. Mã chưa hoàn tất retention/xóa, audit bất biến hay bảo vệ token khỏi XSS; xử lý các rào cản này trước production.
