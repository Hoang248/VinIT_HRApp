# Tài liệu chờ triển khai — Phase 1

> Trạng thái tại ngày 2026-11-07: các nâng cấp Batch 1–5 đã có code, test, CI và migration tương ứng; Batch 5.1 đã chuẩn bị bộ dữ liệu/checklist staging. Tài liệu này lưu riêng những phần **đã sẵn sàng ở repository nhưng chưa được triển khai hoặc chưa được nghiệm thu trên môi trường đích**. Không mục nào trong tài liệu này được coi là đã hoàn thành chỉ vì đã có code, checklist hoặc migration.
>
> Quyết định ngày 2026-11-07: các gate Phase 1 còn lại **tạm dừng, chờ triển khai Production**. Rà soát Phase 2 được thực hiện ở mức tài liệu/code nhưng không đóng bất kỳ DEP nào trong tài liệu này.

- Branch: `arena/ea6e2570-vinit-hrapp`
- Mốc code/tài liệu được audit: `dc9d020`
- Project Supabase đã kết nối: `myrymlqdbyqmpynesiwk`
- Migration remote mới nhất đã xác nhận: `20261107142027 retention_audit_integrity`
- Báo cáo audit chi tiết: [`audit/UPGRADE_AUDIT_2026-11-07.md`](../audit/UPGRADE_AUDIT_2026-11-07.md)
- Checklist chạy staging: [`doc/E2E_STAGING_EXECUTION_CHECKLIST.md`](E2E_STAGING_EXECUTION_CHECKLIST.md)

### Mapping môi trường bắt buộc trước DEP-01/DEP-03

Không được mặc định project Supabase đã kết nối là staging. Trước khi deploy hoặc
chạy E2E, DevOps/Release owner phải điền và ký xác nhận bảng sau; các ô chưa có
bằng chứng là blocker thực thi, không phải chi tiết có thể bổ sung sau.

| Thành phần | Staging cho DEP-01/DEP-02 | Môi trường phục vụ project đã kết nối cho DEP-03 |
|---|---|---|
| Mục đích môi trường | `CHƯA XÁC NHẬN — BLOCKER` | Pilot cấu hình production phục vụ thử nghiệm LLM; `APP_ENV=production` là chủ đích. Có thể coi VPS là server test, nhưng dữ liệu đã dùng không phải synthetic-only |
| Backend URL/process | `CHƯA XÁC NHẬN — BLOCKER` | VPS HRA, PM2 `hra-backend`, Uvicorn nội bộ `127.0.0.1:8005`; health từng xác nhận `ready` |
| Frontend URL/process | `CHƯA XÁC NHẬN — BLOCKER` | VPS HRA, PM2 `hra-frontend`, Next chạy trực tiếp cổng `3005`; hiện truy cập qua IP public `:3005` |
| Supabase project ref | `CHƯA XÁC NHẬN — BLOCKER` | `myrymlqdbyqmpynesiwk` |
| Migration cao nhất đã xác nhận | `CHƯA XÁC NHẬN — BLOCKER` | `20261107142027 retention_audit_integrity` |
| Backend commit đang chạy | `CHƯA XÁC NHẬN — BLOCKER` | `CHƯA XÁC NHẬN — BLOCKER` |
| Frontend commit đang chạy | `CHƯA XÁC NHẬN — BLOCKER` | `CHƯA XÁC NHẬN — BLOCKER` |
| Worker topology/số instance | `CHƯA XÁC NHẬN — BLOCKER` | PM2 có 1 `hra-backend` với worker trong cùng process và 1 `hra-frontend`; dùng chung PM2/user với NarrativeHealth |
| Loại dữ liệu được phép | Chỉ dữ liệu tổng hợp cho DEP-01 | Đã có tài khoản HR/CV phục vụ thử nghiệm LLM; dữ liệu được người vận hành cho biết có thể reset, nhưng hiện vẫn phân loại là dữ liệu thật/pilot, không phải synthetic-only |
| Provider/mode được phép | LLM local/mock đã duyệt; `LTR_MODE=OFF`; semantic `OFF` hoặc `hash` non-BGE cho smoke | Đã dùng cho thử nghiệm LLM; provider, loại dữ liệu đã gửi và phạm vi lưu trữ phía provider chưa được kiểm kê/phê duyệt theo DEP-05 |

Kết luận Gate 0 tạm thời: stack VPS + Supabase hiện tại là **pilot cấu hình production có dữ liệu HR/CV thật dùng thử**, không tự động đạt điều kiện staging synthetic cho DEP-01/DEP-02. Muốn dùng chính stack này làm staging phải có quyết định reset/reclassify chính thức, xóa/kiểm chứng dữ liệu Auth/DB/Storage, đổi nhãn môi trường và ký bằng chứng sau reset. Phương án ưu tiên là giữ stack hiện tại cho DEP-03/pilot và tạo staging tách biệt cho DEP-01/DEP-02.

## 1. Danh sách chờ triển khai/thực thi

| ID | Hạng mục chờ | Trạng thái chờ | Phụ thuộc | Chủ trì | Bằng chứng đóng hạng mục |
|---|---|---|---|---|---|
| DEP-01 | Deploy backend/frontend chứa Batch 1–5 lên staging và chạy E2E bằng dữ liệu tổng hợp | `READY_CODE — BLOCKED_ENVIRONMENT_MAPPING` | Bảng mapping môi trường đã ký, staging tách biệt, tài khoản Admin/HR Lead/HR Recruiter/HM/Outsider, deploy commit đã audit | DevOps/IT + HR/HM | Checklist E2E-01…E2E-16 đã điền PASS/FAIL/N/A hợp lệ, commit SHA, migration versions, log/screenshot đã che secret, ký duyệt |
| DEP-02 | Kiểm chứng retention/audit qua backend staging đã deploy | `READY_TO_EXECUTE` sau DEP-01 | Backend staging trỏ tới DB đã có migration `00012`, tài khoản đúng quyền | DevOps + HR Lead/Admin | `GET /v1/admin/audit/verify` trả `valid=true`; retention due/not-due/confirm/execute có case/job/audit evidence |
| DEP-03 | Triển khai code tương ứng với schema `00011`/`00012` lên môi trường phục vụ project đã kết nối, nếu môi trường đó đang chạy code cũ | `BLOCKED_ENVIRONMENT_IDENTIFICATION` | Điền cột môi trường đã kết nối trong bảng mapping, xác nhận topology/process đang chạy, cửa sổ deploy, drain worker, kế hoạch rollback | DevOps/Release owner | Phiên bản deploy thực tế, health checks, smoke test Admin/LTR/retention, xác nhận không chạy mixed-version worker |
| DEP-04 | Đóng legacy Supabase API keys và revoke legacy JWT signing secret | `BLOCKED_MANUAL_OPS` | Kiểm kê mọi client/backend/worker đã chuyển sang key/JWKS mới; restart đồng nhất | Chủ project Supabase | Dashboard/Management API xác nhận legacy disabled, legacy JWT secret revoked, login/JWKS mới hoạt động |
| DEP-05 | Phê duyệt privacy/egress cho LLM/BGE/OCR dùng dữ liệu thật | `WAITING_APPROVAL` | Provider/region/DPA, loại dữ liệu gửi, retention phía provider, DLP/redaction | IT Security/Legal/HR | Văn bản phê duyệt hoặc ticket bảo mật đã ký; cấu hình endpoint đúng phạm vi phê duyệt |
| DEP-06 | BGE pilot bằng endpoint thật và golden set HR | `WAITING_ENDPOINT_AND_DATA` | DEP-05, endpoint BGE-M3 1024 chiều có token/quota, HR golden set | IT + HR | Báo cáo Recall@5, false MATCH/NO_MATCH, unresolved rate, latency; quyết định bật/tắt semantic |
| DEP-07 | LTR SHADOW rồi mới xét ACTIVE | `WAITING_HR_GOLD_DATASET` | DEP-05 nếu dùng dữ liệu thật, HR gold dataset đủ lớn/đại diện, artifact đạt gates và được Admin approve | HR/HM + kỹ thuật | Dataset/labeling report, training gates, review event/artifact hash, SHADOW comparison chứng minh không vi phạm mandatory/coverage |
| DEP-08 | Production readiness: branch protection, monitoring/alerting, topology worker, backup/restore/DR drill | `WAITING_OPS_DECISION` | Quy trình phát hành và hạ tầng đích | DevOps/IT | Cấu hình branch protection nếu áp dụng, dashboard/alert test, quyết định worker topology, biên bản restore/DR drill |

## 2. Phần Batch 5.1 đã chuẩn bị nhưng chưa thực thi

Đã lưu trong repository:

- `staging/synthetic/manifest.json`
- `staging/synthetic/candidates/*.txt`
- `backend/scripts/generate_staging_fixtures.py`
- `backend/tests/test_staging_fixtures.py`
- `doc/E2E_STAGING_EXECUTION_CHECKLIST.md`

Cách sinh DOCX upload staging:

```bash
backend/.venv/bin/python backend/scripts/generate_staging_fixtures.py --check
backend/.venv/bin/python backend/scripts/generate_staging_fixtures.py
```

Giới hạn bắt buộc:

- Chỉ dùng dữ liệu tổng hợp `@example.test`; không thay bằng CV thật khi chưa đóng DEP-04/DEP-05 theo phạm vi áp dụng.
- Bộ fixture là dữ liệu smoke/E2E, **không** phải HR golden set để đo matching/BGE/LTR accuracy.
- File `ocr_simulated.txt` chỉ là nội dung để tạo scan ngoài Git; không tự chứng minh chất lượng OCR.
- DOCX sinh ra trong `staging/generated/` bị ignore; không commit file sinh ra chứa dữ liệu staging.

## 3. Thứ tự triển khai khuyến nghị

### Gate A — Staging readiness: DEP-01

Chưa bắt đầu nếu bảng mapping môi trường chưa được DevOps/Release owner điền và
ký xác nhận. Khi đã có staging, deploy bằng dữ liệu tổng hợp, `LTR_MODE=OFF`,
LLM local/mock đã duyệt; semantic chỉ dùng `OFF` hoặc provider `hash` non-BGE
cho smoke plumbing.

### Gate B — Data lifecycle acceptance: DEP-02

Kiểm chứng sâu retention, storage purge và audit verify qua backend staging đã
deploy. DEP-02 dùng cùng staging của Gate A nhưng ký đóng riêng.

### Gate C — Deployment alignment & security: DEP-03, sau đó DEP-04

Đồng bộ code với schema `00011`/`00012` trên môi trường đã kết nối sau khi đã
xác định rõ môi trường đó. Việc kiểm kê client/deployment cho DEP-04 có thể
chuẩn bị song song, nhưng chỉ đóng legacy keys/JWT secret sau khi mọi runtime
đã chuyển sang key/JWKS mới.

### Gate D — AI privacy & quality: DEP-05 → DEP-06 → DEP-07

Chỉ dùng dữ liệu/model thật sau phê duyệt privacy/egress. BGE pilot và LTR
SHADOW/ACTIVE là các gate độc lập; không suy chất lượng từ fixture tổng hợp.

### Gate E — Production readiness: DEP-08

Branch protection, monitoring/alerting, worker topology, backup/restore và DR
drill. Việc chuẩn bị backup/monitoring có thể bắt đầu trước DEP-03; chỉ đóng
Gate E khi có bằng chứng vận hành đầy đủ.

### Thứ tự chi tiết

1. Điền bảng mapping môi trường, chốt commit sẽ deploy và cửa sổ triển khai; xác nhận không có worker/API phiên bản cũ đang xử lý job.
2. Deploy staging theo DEP-01; ghi commit SHA, cấu hình provider ở mức không lộ secret và migration versions.
3. Chạy checklist E2E bằng dữ liệu tổng hợp; hoàn thành DEP-02 cho audit/retention.
4. Nếu môi trường phục vụ project đã kết nối còn code cũ, lên lịch DEP-03 sau khi staging đạt; không để mixed-version worker.
5. Chủ project thực hiện DEP-04 sau khi mọi deployment đã dùng key/JWKS mới.
6. Xin DEP-05 trước khi gửi dữ liệu thật tới LLM/BGE/OCR.
7. Chạy DEP-06 cho BGE; xây HR gold dataset và chạy DEP-07 ở `SHADOW`; chỉ xét `ACTIVE` sau SHADOW report đạt gate.
8. Hoàn thiện DEP-08 trước khi tuyên bố production readiness.

## 4. Lưu ý rollback và an toàn schema

- Migration `00011`/`00012` là thay đổi cộng thêm; rollback mặc định là rollback code, giữ schema để tránh mất governance/evidence. Không drop cột, bảng, trigger hoặc audit hash chain nếu chưa có kế hoạch rollback đã phê duyệt và backup đã kiểm chứng.
- Sau `00012`, audit events được trigger gán hash ngay cả khi backend cũ ghi audit. Nếu `GET /v1/admin/audit/verify` hoặc postflight SQL báo `valid=false`, dừng rollout retention và điều tra; không sửa tay audit row để làm xanh.
- Nếu backend cũ chưa có API retention/LTR governance, không coi các workflow đó là đã triển khai chỉ vì schema đã có.
- Giữ `LTR_MODE=OFF` và semantic ở cấu hình an toàn cho tới khi DEP-06/DEP-07 có bằng chứng riêng.
- Trước khi xét LTR `ACTIVE`, xử lý finding F-01 trong báo cáo audit: worker phải fail-closed khi registry artifact thiếu `artifact_sha256`, hoặc artifact phải được re-register/re-approve để luôn gắn với hash đã duyệt.

## 5. Mẫu ký nhận chờ triển khai

| ID | Người phụ trách | Ngày dự kiến | Kết quả thực tế | Liên kết bằng chứng |
|---|---|---|---|---|
| DEP-01 |  |  |  |  |
| DEP-02 |  |  |  |  |
| DEP-03 |  |  |  |  |
| DEP-04 |  |  |  |  |
| DEP-05 |  |  |  |  |
| DEP-06 |  |  |  |  |
| DEP-07 |  |  |  |  |
| DEP-08 |  |  |  |  |
