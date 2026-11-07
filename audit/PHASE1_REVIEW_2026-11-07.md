# Phase 1 Closure Review — 2026-11-07

> Mục đích: đối chiếu F1.01–F1.13 theo PRD → API → DB → Source Code → Test → Acceptance Evidence để quyết định đóng Phase 1. Báo cáo này không sửa đè các audit lịch sử. “Có trong code” không đồng nghĩa “đã nghiệm thu”.
>
> Phạm vi kiểm tra ban đầu: branch `arena/ea6e2570-vinit-hrapp`, commit nền `1326acd`, cập nhật sửa điểm tại `57b9072`. Project Supabase đã kết nối: `myrymlqdbyqmpynesiwk`.

## 1. Quy ước trạng thái

| Trạng thái | Ý nghĩa |
|---|---|
| `PASS` | Có implementation và bằng chứng kiểm thử/nghiệm thu tương ứng |
| `PARTIAL` | Đã có implementation nhưng thiếu kiểm thử, vận hành hoặc nghiệm thu đầy đủ |
| `BLOCKED` | Không thể đóng vì còn điều kiện an toàn/dữ liệu/pháp lý/vận hành chưa hoàn thành |
| `NOT TESTED` | Chưa có bằng chứng kiểm thử trên môi trường/dịch vụ thật |

## 2. Bằng chứng môi trường và kiểm thử hiện có

| Hạng mục | Bằng chứng | Trạng thái |
|---|---|---|
| Migration trên project Supabase đã kết nối | Đã kiểm tra danh sách migration: initial schema, audit fixes, operation scope, recovery/privacy, account administration, OpenAI-compatible provider secrets, departments/position codes, deterministic foundation, structured requirement specs, pgvector/BGE/LTR | `PASS` cho project đã kết nối; môi trường đích khác vẫn `NOT TESTED` |
| Backend automated tests | Tại vòng sửa công thức điểm: targeted phase1 unit + semantic/LTR đạt; cần ghi lại full-suite sau từng batch nâng cấp | `PARTIAL` |
| GitHub CI | Chưa có GitHub Actions/status checks độc lập | `BLOCKED` cho nghiệm thu phát hành |
| Supabase Auth/Storage thật | Chưa có E2E staging được ghi nhận đầy đủ | `NOT TESTED` |
| OCR scan thật | Có code và unit test mô phỏng; chưa có bộ hồ sơ scan thật được nghiệm thu | `NOT TESTED` |
| LLM/BGE thật | Có provider và cấu hình; chưa có báo cáo golden set HR trên model/endpoint thật | `NOT TESTED` |
| Legacy Supabase keys | Legacy keys vẫn là hạng mục phải đóng thủ công; connector không có thao tác deactivate legacy/revoke JWT signing secret | `BLOCKED` |

## 3. Traceability F1.01–F1.13

| ID | Yêu cầu | API/Code chính | DB/Migration | Bằng chứng hiện tại | Trạng thái | Việc cần làm để đóng |
|---|---|---|---|---|---|---|
| F1.01 | Vị trí, JD, Hiring Manager | API positions/JD, UI positions | `positions`, `jd_versions`, `position_assignments` | Có tạo/sửa vị trí, lịch sử JD, kiểm tra HM và xung đột phiên bản | `PARTIAL` | Test UI/API trên staging; bổ sung hoặc chấp nhận thiếu UI đổi HM sau tạo |
| F1.02 | Tiêu chí, dual approval, trọng số | API criteria, requirement spec | `criteria_versions`, `criteria_items.requirement_spec` tại 00009 | Có HR/HM hai bước, khóa bản duyệt, spec có cấu trúc | `PARTIAL` | Kiểm thử LLM thật và ma trận quyền phê duyệt |
| F1.03 | Upload batch | API applications/documents | `application_documents`, operations | Giới hạn file/batch, validate PDF/DOCX, theo dõi tiến trình | `PARTIAL` | E2E Storage thật và batch lớn trên staging |
| F1.04 | Trích xuất, OCR, sửa profile | document processor, profile API/UI | profile versions, document processing runs | Có PDF text/DOCX, OCR code, profile versioning | `PARTIAL` | Bộ CV scan thật, đo OCR EN/VI và lỗi trích xuất |
| F1.05 | Đánh giá và dẫn chứng | deterministic engine, LLM fallback, evidence verification | assessment runs/results/evidence | Rule-first, candidate chunks, quote span/page verification | `PARTIAL` | Golden set HR thật; đo false MATCH/NO_MATCH/unresolved |
| F1.06 | Điểm và ranking | `MatchingEngine.calculate_assessment_scores`, `rank_applications` | assessment/ranking runs/items | Đã sửa tại `57b9072`: từ `matching-v2.1`, UNCLEAR bị loại khỏi tử/mẫu của score; coverage là chỉ số riêng; LTR vẫn OFF mặc định | `PARTIAL` | HR/HM xác nhận policy; chạy golden/repeatability sau sửa; train lại LTR nếu sau này dùng |
| F1.07 | Cảnh báo trùng | duplicate detection theo email/phone | duplicate signals | Có tín hiệu trong cùng position, không tự gộp/xóa | `PARTIAL` | Test các trường hợp đổi identifier và dữ liệu thiếu |
| F1.08 | Trạng thái và lịch sử | application status API | status events/audit events | HR cập nhật theo transition, lý do khi loại, AI không tự đổi trạng thái | `PARTIAL` | RBAC matrix và audit integrity |
| F1.09 | Shortlist, feedback, ghi chú HR | shortlist API/UI | shortlist shares/items/feedback | Có chia sẻ HM, quyền xem CV, feedback, thu hồi; ghi chú append-only qua API | `PARTIAL` | Kiểm thử chia sẻ/thu hồi trên staging và quyền HM |
| F1.10 | RBAC, audit, retention | admin/account APIs, audit events | RBAC tables, audit events, retention/deletion tables | Có quản lý role/trạng thái; audit chưa bất biến; retention workflow chưa hoàn tất; legacy key chưa đóng | `BLOCKED` | Đóng legacy key; retention/deletion workflow; audit append-only/integrity; RBAC matrix |
| F1.11 | Cấu hình AI, privacy | Admin AI config, LLM/embedding providers | AI config versions, provider secret encryption | Có allowlist, mã hóa API key, redaction best effort, semantic diagnostics còn hạn chế | `BLOCKED` cho CV thật | Phê duyệt privacy/egress; E2E model thật; semantic diagnostics; đánh giá bias/prompt injection |
| F1.12 | Việt–Anh | frontend i18n | Không áp dụng | Có VI/EN, mặc định VI, test i18n | `PARTIAL` | HR review nội dung nghiệp vụ và các nhãn mới theo policy điểm |
| F1.13 | Dashboard, worker | dashboard API, worker health | operations, recovery events | Worker thread trong API, advisory lock/fencing/heartbeat/recovery; at-least-once | `PARTIAL` | Chỉ định một worker-enabled instance hoặc tách worker; monitoring/alerting; E2E recovery trên staging |

## 4. Các gate chưa được phép vượt qua

### Gate dữ liệu thật

Chưa dùng CV thật ở quy mô pilot cho tới khi:

- Legacy Supabase keys/JWT secret được đóng và kiểm chứng.
- Privacy/egress được phê duyệt cho LLM/BGE/OCR endpoints.
- Retention/deletion workflow có thể thực thi và đối soát.
- RBAC matrix và E2E Auth/Storage đạt trên staging.

### Gate LTR ACTIVE

Chưa bật `LTR_MODE=ACTIVE` cho tới khi:

- Có HR gold dataset, không chỉ weak labels.
- Train offline đạt gates và artifact được đăng ký.
- Governance có artifact hash, người phê duyệt, lý do và audit event.
- Production ACTIVE chỉ dùng registry artifact `APPROVED`; file artifact đã bị chặn ở production từ `57b9072`.
- SHADOW report chứng minh không có vi phạm mandatory/coverage gate.

### Gate production scale

Chưa tuyên bố production scale cho tới khi:

- Có CI độc lập.
- Worker được triển khai có chủ đích cho nhiều replicas hoặc tách process.
- Có monitoring/alerting, backup/restore và DR drill.
- Audit trail có cơ chế bảo vệ tính toàn vẹn.

## 5. Thứ tự nâng cấp đang thực hiện

1. Sửa công thức điểm UNCLEAR và khóa LTR file artifact ở production — đã có tại `57b9072`.
2. Đóng legacy Supabase keys — `BLOCKED` chờ thao tác Dashboard/Management API của chủ project sau khi xác nhận mọi deployment đã chuyển sang key/JWKS mới.
3. Tạo closure review này để theo dõi F1.01–F1.13.
4. Embedding cache và semantic diagnostics.
5. LTR governance migration/API.
6. RBAC test matrix, E2E staging và CI.
7. Retention/deletion workflow và audit integrity.
8. Đánh giá BGE bằng golden set; xây HR gold dataset và chạy LTR SHADOW trước ACTIVE.
