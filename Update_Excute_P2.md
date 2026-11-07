# Update Execute — Phase 2

> File này ghi lại quá trình rà soát, lập plan và triển khai Phase 2 theo quy ước giống `Update_Excute_P1.md`: trạng thái tổng quan, thay đổi file/code/migration, test đã chạy và kết quả, commit hash sau khi push, blocker và điều kiện mở khóa.
>
> **Trạng thái hiện tại:** đã hoàn thành rà soát tài liệu/code và lập plan chi tiết cho batch đầu Workflow Core. **Chưa triển khai tính năng Phase 2; plan đang chờ duyệt và các quyết định nghiệp vụ D-01…D-10 đang chờ chốt.**
>
> **F2.08 SSO: TẠM TREO** theo quyết định của người dùng; không đưa vào plan ở vòng này.

## 1. Trạng thái tổng quan

| Giai đoạn | Phạm vi | Trạng thái | Bằng chứng |
|---|---|---|---|
| P2-0 | Đọc tài liệu, rà soát code/schema/API/frontend/tests F2.01–F2.07 và F2.09 | HOÀN THÀNH RÀ SOÁT | `audit/PHASE2_REVIEW_2026-11-07.md` |
| P2-0 | F2.08 SSO | TẠM TREO | Không lập plan/không thay đổi auth trong vòng này |
| P2-1 | Chốt phạm vi ưu tiên đầu tiên | ĐÃ CHỐT | Workflow cốt lõi F2.01 + F2.02; F2.07 loại khỏi vòng này; Candidate Rediscovery để cuối Phase 2 |
| P2-2 | Lập plan triển khai chi tiết batch đầu | HOÀN THÀNH — CHỜ DUYỆT PLAN | `doc/PHASE2_IMPLEMENTATION_PLAN.md` |
| P2-2.1 | Chốt quyết định nghiệp vụ D-01…D-10 trong plan batch đầu | CHỜ HR/HR LEAD DUYỆT | Mục 3 của plan chi tiết |
| P2-3 | Triển khai/test/CI batch Workflow Core | CHƯA BẮT ĐẦU | Chỉ thực hiện sau khi plan và D-01…D-10 được duyệt |

## 2. Nguyên tắc áp dụng cho Phase 2

1. Chỉ làm việc trên branch `arena/ea6e2570-vinit-hrapp`; không tự ý triển khai trước khi plan được duyệt.
2. Phase 1 vẫn chưa đóng; các DEP-01…DEP-08 tạm dừng chờ triển khai Production và không bị đóng bởi công việc Phase 2.
3. Không dùng CV/dữ liệu thật khi chưa có phê duyệt privacy/egress và kiểm chứng vận hành cần thiết.
4. Không tự suy diễn HR override, chất lượng OCR/matching hoặc hiệu quả tuyển dụng từ trạng thái hiện tại khi hệ thống chưa ghi sự kiện/dữ liệu phù hợp.
5. F2.08 SSO giữ trạng thái tạm treo cho tới khi người dùng có quyết định mở lại.
6. Candidate Rediscovery đã được chốt để ở cuối Phase 2, không thuộc batch đầu; trước khi lập plan chi tiết cho hạng mục này vẫn phải có quyết định về consent, retention và quyền tái sử dụng CV.

## 3. P2-0 — Rà soát tài liệu và code hiện tại

### 3.1. Tài liệu đã đọc

- `doc/HRA_NextPhase.md`: yêu cầu F2.01–F2.09.
- `doc/HRA_PRD.md`: mục Phase 2 và bối cảnh roadmap.
- `Update_Excute_P1.md`, `audit/PHASE1_REVIEW_2026-11-07.md`, `audit/UPGRADE_AUDIT_2026-11-07.md`: trạng thái và giới hạn của nền tảng Phase 1.
- `doc/PENDING_DEPLOYMENT.md`: các DEP còn chờ triển khai Production.

### 3.2. Phạm vi code đã đối chiếu

- Schema/migrations `00001`–`00012`.
- Backend API/services/worker: criteria, positions, shortlist, candidate details, dashboard, applications, document processor, matching, evaluation scripts và retention.
- Frontend routes/API client: dashboard, positions, applicants, applicant detail, shortlist và admin hiện có.
- Tests/scripts liên quan tới matching evaluation, document processing, dashboard, duplicate signals và retention.

### 3.3. Kết quả chính

| ID | Kết luận rà soát |
|---|---|
| F2.01 | Có criteria versioning/phê duyệt theo position; chưa có rubric library/template/clone theo job family. |
| F2.02 | Có shortlist share/feedback text và HR private notes; chưa có structured scorecard, task/deadline/reminder. |
| F2.03 | Có dashboard cơ bản; chưa có HR override tracking, funnel thời gian, processing-time và error analytics. |
| F2.04 | Có evidence verification/coverage và evaluation offline; chưa có sampling queue, inspection viewer và feedback flags. |
| F2.05 | Có exact duplicate trong cùng position; chưa có cross-position detection/history/review workflow. |
| F2.06 | Có PDF/DOCX OCR hiện tại; chưa hỗ trợ JPG/PNG độc lập và ảnh nhúng DOCX. |
| F2.07 | Có retention thủ công an toàn từng case; chưa có scheduler/cảnh báo, retention UI, exception hold, OTP/chữ ký. Cần guard case khi position mở lại. |
| F2.08 | Tạm treo. |
| F2.09 | Chưa có side-by-side comparison và custom Excel/PDF export. |

Chi tiết bằng chứng và khoảng thiếu: `audit/PHASE2_REVIEW_2026-11-07.md`.

### 3.4. File đã thay đổi ở P2-0

- Tạo `audit/PHASE2_REVIEW_2026-11-07.md`.
- Tạo `Update_Excute_P2.md`.
- Cập nhật `Update_Excute_P1.md`: ghi quyết định tạm dừng các gate Phase 1 chờ Production.
- Cập nhật `doc/PENDING_DEPLOYMENT.md`: ghi rõ rà soát Phase 2 không đóng DEP nào.

Không thay đổi code tính năng, schema/migration, API hoặc frontend ở giai đoạn rà soát này.

### 3.5. Kiểm chứng đã thực hiện

- Kiểm tra branch/worktree và mốc HEAD trước rà soát.
- Đọc tài liệu Phase 2 và đối chiếu trực tiếp schema/API/service/frontend bằng tìm kiếm mã nguồn.
- Kiểm tra `git diff --check` sau khi hoàn thành tài liệu.
- Không chạy test code vì P2-0 chỉ thay đổi tài liệu; trạng thái test của code vẫn theo bằng chứng Phase 1 đã lưu.

### 3.6. Commit

- Commit rà soát Phase 2: `7189d20` (`docs: rà soát Phase 2 và tạm dừng gate Phase 1`), đã push lên `arena/ea6e2570-vinit-hrapp`.

### 3.7. P2-2 — Plan chi tiết batch đầu Workflow Core

- Đã tạo `doc/PHASE2_IMPLEMENTATION_PLAN.md` cho F2.01 Rubric Library và F2.02 Structured Collaborative Workflow HR–HM.
- Plan đã khóa phạm vi ngoài batch đầu: F2.07 loại khỏi vòng này, Candidate Rediscovery để cuối Phase 2 và F2.08 SSO tiếp tục tạm treo.
- Plan gồm cổng quyết định D-01…D-10, thiết kế dữ liệu/API/UI dự kiến, thứ tự triển khai, kiểm thử bắt buộc, tiêu chí nghiệm thu và rủi ro.
- Chưa thay đổi code tính năng, schema/migration, API hoặc frontend; triển khai chỉ bắt đầu sau khi plan và D-01…D-10 được duyệt.
- Commit plan: `ffc8043` (`docs: lập plan batch đầu Phase 2`), đã push lên `arena/ea6e2570-vinit-hrapp`.

## 4. Quyết định đã chốt và việc còn phải duyệt

### 4.1. Quyết định phạm vi đã chốt ngày 2026-11-07

1. Ưu tiên đầu tiên: Workflow cốt lõi F2.01 + F2.02.
2. Chỉ lập plan chi tiết cho batch đầu; các nhóm Phase 2 còn lại ở mức roadmap.
3. F2.07 loại khỏi vòng triển khai này; giữ nguyên retention thủ công an toàn của Phase 1.
4. Candidate Rediscovery để ở cuối Phase 2, không thuộc batch đầu.
5. F2.08 SSO tiếp tục tạm treo.

### 4.2. Quyết định còn phải chốt trước khi triển khai batch đầu

Các quyết định D-01…D-10 tại Mục 3 của `doc/PHASE2_IMPLEMENTATION_PLAN.md`, đặc biệt:

- Job-family taxonomy, chủ sở hữu/publish template và chuẩn hóa `level_band`.
- Thang scorecard, điều kiện submit, deadline mặc định và phạm vi email reminder.
- Quyền xem scorecard và xác nhận HR private notes luôn tách khỏi HM view.

### 4.3. Quyết định để dành cho các plan sau

- Định nghĩa HR override và metric dictionary cho F2.03.
- QA sampling/reviewer/flag handling cho F2.04.
- Mức hiển thị cross-position duplicate cho F2.05.
- Ngưỡng OCR/manual review cho F2.06.
- Quyền và trường dữ liệu export cho F2.09.
- Consent/retention/quyền tái sử dụng CV cho Candidate Rediscovery cuối Phase 2.

## 5. Blocker và điều kiện mở khóa

| Mã | Hạng mục | Trạng thái | Điều kiện mở khóa |
|---|---|---|---|
| P2-B01 | Phạm vi/ưu tiên batch đầu Phase 2 | ĐÃ CHỐT | Workflow cốt lõi F2.01 + F2.02; chỉ lập plan chi tiết batch đầu |
| P2-B02 | Plan chi tiết batch Workflow Core | CHỜ DUYỆT PLAN | Người dùng duyệt `doc/PHASE2_IMPLEMENTATION_PLAN.md` |
| P2-B03 | Quyết định nghiệp vụ D-01…D-10 | CHỜ HR/HR LEAD + HM/IT | Chốt taxonomy/template ownership, chuẩn hóa level, scorecard, deadline, reminder và quyền xem |
| P2-B04 | Nội dung rubric mẫu và dữ liệu kiểm thử nghiệp vụ | CHỜ HR CUNG CẤP | Có taxonomy đã duyệt và ít nhất một rubric draft thực tế để kiểm thử |
| P2-B05 | Phase 1 Production gates đang tạm dừng | KHÔNG CHẶN LẬP PLAN | Chỉ chặn nghiệm thu Production/dữ liệu thật; không chặn thiết kế hoặc dev bằng dữ liệu tổng hợp |
| P2-B06 | SSO | TẠM TREO | Chỉ mở lại khi người dùng yêu cầu |
| P2-B07 | F2.07 Retention automation | LOẠI KHỎI VÒNG NÀY | Chỉ xét lại khi có quyết định mới; quyết định Legal về hold/OTP/chữ ký vẫn cần nếu mở lại |
| P2-B08 | Candidate Rediscovery | ĐỂ CUỐI PHASE 2 | Chỉ lập plan sau khi chốt consent, retention và quyền tái sử dụng CV |

## 6. Quy ước cập nhật file này

Sau khi plan được duyệt và mỗi batch triển khai hoàn thành, bổ sung:

1. Trạng thái mới trong bảng tổng quan.
2. File/code/migration đã thay đổi.
3. Lệnh test đã chạy và kết quả.
4. Commit hash sau khi push và CI run tương ứng nếu có.
5. Blocker còn lại và điều kiện mở khóa.
