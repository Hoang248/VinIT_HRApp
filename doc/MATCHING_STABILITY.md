# Ổn định matching CV–JD

Tài liệu này mô tả kiến trúc matching đã triển khai theo Phase 0–2, cách đo độ lặp lại và quy trình xây dựng golden set trước khi cân nhắc semantic retrieval hoặc Learning-to-Rank.

## 1. Nguyên tắc

1. **LLM không cho điểm cuối.** Điểm, gate bắt buộc, độ phủ bằng chứng và thứ hạng do code xác định tính từ findings đã kiểm chứng.
2. **Không có bằng chứng không đồng nghĩa không đáp ứng.** Thiếu bằng chứng luôn là `UNCLEAR`/cần HR xác minh, trừ khi CV có dữ kiện đo được mâu thuẫn rõ ràng (ví dụ số năm hoặc điểm IELTS thấp hơn yêu cầu).
3. **Cùng đầu vào phải cho cùng đầu ra.** Assessment được đóng băng bằng fingerprint; chạy lại cùng fingerprint phải tái sử dụng kết quả đã lưu thay vì gọi LLM lần nữa.
4. **Mọi thay đổi hành vi đều phải tăng version.** Không âm thầm thay rule, prompt, scoring hoặc model rồi trộn với kết quả cũ.

## 2. Luồng xử lý hiện tại

```text
CV đã redaction
  -> profile facts + CV text hash
  -> assessment fingerprint
       -> đã có COMPLETED cùng fingerprint: tái sử dụng, không gọi LLM
       -> chưa có: chunk CV theo page/section/paragraph/sentence
                    -> requirement spec từ rubric đã duyệt
                    -> deterministic rule engine
                    -> LLM fallback chỉ cho tiêu chí chưa quyết định,
                       chỉ với candidate chunks của từng tiêu chí
                    -> hợp nhất findings theo đúng rubric
                    -> verify quote bằng normalized span + page/offset
                    -> score / must-have gate / evidence coverage
                    -> ranking: status -> score -> coverage -> application_id
```

### 2.1 Fingerprint

Fingerprint là SHA-256 của:

- định danh application/position;
- JD version, criteria version và toàn bộ rubric đã duyệt;
- profile version và canonical profile facts;
- SHA-256 của CV text sau redaction;
- snapshot runtime AI công khai (không chứa API key/ciphertext);
- `LLM_SEED` nếu được cấu hình;
- matching prompt version, matching policy version và deterministic rules version;
- ranking policy version, ngày đánh giá dùng cho khoảng ngày kết thúc ở hiện tại;
- trực tiếp các tham số điểm/coverage đang hiệu lực: score map, `MIN_EVIDENCE_COVERAGE`, `MIN_EVIDENCE_STRENGTH`, trọng số hai nhóm và cờ strict JSON Schema. Thay các giá trị này qua môi trường vẫn đổi fingerprint dù quên tăng version string.

Nếu một `COMPLETED` assessment có cùng fingerprint tồn tại, worker bỏ qua application đó. Muốn đánh giá lại có chủ đích, phải tạo thay đổi có version mới — ví dụ HR sửa profile, duyệt rubric mới, hoặc vận hành tăng policy/prompt/rules/model runtime — rồi chạy lại operation. Không sửa trực tiếp kết quả đã lưu.

### 2.2 Chunk và requirement spec

CV được chia thành chunk có:

- `chunk_id` ổn định theo thứ tự văn bản;
- page number nếu có marker `--- Page N ---`;
- `char_start`/`char_end` trỏ đúng vào CV text;
- section suy ra từ heading: `WORK`, `PROJECT`, `SKILL`, `EDUCATION`, `CERTIFICATION`, `LANGUAGE`, `SUMMARY` hoặc `OTHER`.

Requirement spec có dạng cấu trúc (`kind`, `terms`, `min_years`, cấp bằng, ngôn ngữ và ngưỡng IELTS/TOEIC/CEFR) và được lưu trên từng criterion. AI/HR có thể sửa spec trong bản nháp; khi HR duyệt, các spec suy luận còn thiếu được materialize vào rubric để HM duyệt đúng spec sẽ dùng khi đánh giá. Spec đã lưu là nguồn sự thật; engine chỉ suy luận bản nháp khi criterion chưa có spec.

### 2.3 Rule engine

| Loại | Quyết định xác định khi | Không quyết định khi |
|---|---|---|
| Kỹ năng | term/alias xuất hiện trong chunk liên quan với coverage đủ mạnh | chỉ xuất hiện yếu/ngoài ngữ cảnh hoặc không thấy |
| Số năm | tổng duration riêng biệt đủ, profile total, hoặc khoảng ngày đã merge đủ/không đủ | tổng duration rời rạc dưới ngưỡng nhưng chưa đáng tin cậy để kết luận thiếu |
| Bằng cấp | quote trong CV parse được cấp bằng đạt; hoặc section Education đầy đủ cho thấy cấp cao nhất thấp hơn yêu cầu | profile fact cao hơn quote CV, hoặc bằng thấp chỉ xuất hiện ngoài Education |
| Chứng chỉ | term chứng chỉ xuất hiện trong chunk liên quan | không thấy chứng chỉ |
| Ngoại ngữ | một mức nhất quán đạt hoặc thấp hơn yêu cầu, quote chứa nguyên mức đó | nhiều mức mâu thuẫn cho cùng bài test, hoặc CV chỉ nêu tên ngôn ngữ |

Rule finding có `decision_source=RULE`, `evidence_strength`, `evidence_chunk_id` và `rule_version`. Token cấu thành của một phrase (ví dụ `programming`) không tự thỏa mãn concept (`Python programming`). Quote lưu xuống evidence là exact substring lấy từ CV text; worker vẫn verify lại span/page trước khi chấm và ưu tiên occurrence thuộc chunk/page được gợi ý khi quote lặp lại.

`HYBRID` hiện là giá trị dành cho quyết định hợp nhất trong tương lai; đường code hiện tại gán từng criterion là `RULE` hoặc `LLM`, không mô tả một finding LLM thường là hybrid.

### 2.4 LLM fallback

LLM chỉ nhận các tiêu chí mà rule chưa quyết định, rubric con tương ứng và tối đa 5 candidate chunks cho từng criterion. Model phải trích quote từ các chunk đó và trả `evidence.chunk_id`; toàn bộ CV không được gửi trong fallback path. Từng finding được validate độc lập: finding lỗi enum/schema chỉ thành `UNCLEAR` cho criterion đó, không làm fail application. `LLM_STRICT_JSON_SCHEMA=true` mới yêu cầu provider enforce JSON Schema; mặc định vẫn dùng `json_object` và Pydantic validation phía client vì một số endpoint compatible không hỗ trợ strict schema. Quote không tìm được span trong CV sẽ bị hạ `UNCLEAR`.

`temperature=0` và seed tùy chọn chỉ giúp nhà cung cấp ổn định hơn theo cơ chế best-effort; chúng **không** thay thế fingerprint/rule engine.

## 3. Version phải tăng khi nào

| Thay đổi | Version cần tăng |
|---|---|
| Logic chunk/spec/rule/alias | `DETERMINISTIC_RULES_VERSION` |
| Công thức điểm/coverage/gate/ranking | `MATCHING_POLICY_VERSION` và policy trong DB nếu thay ngưỡng |
| Nội dung matching prompt | `MATCHING_PROMPT_VERSION` |
| Nội dung profile prompt | `PROFILE_PROMPT_VERSION` |
| Nội dung criteria prompt | `CRITERIA_PROMPT_VERSION` |
| Model/endpoint/seed runtime | snapshot runtime tự vào fingerprint; vẫn cần ghi release note |

Sau khi tăng version, chạy golden/repeatability, ghi kết quả vào release note rồi mới triển khai. Không dùng lại version cũ cho hành vi mới.

## 4. Đo độ ổn định

Module `backend/app/services/evaluation.py` và CLI `backend/scripts/evaluate_matching.py` đo:

- mean/max/P95 độ lệch điểm;
- số lượng và tỉ lệ criterion flip;
- exact application agreement;
- Spearman, Kendall tau-b (có hiệu chỉnh ties) và Top-5/10/20 overlap của ranking;
- tỉ lệ fingerprint reuse nếu được cung cấp số liệu operation.

### 4.1 Định dạng snapshot đầu vào

CLI nhận một list run, hoặc object:

```json
{
  "runs": [
    {
      "application_id": "app-1",
      "matching_score": 90.0,
      "evidence_coverage": 1.0,
      "assessment_fingerprint": "fp-...",
      "criterion_results": [
        {"criterion_id": "criterion-1", "outcome": "MATCH"}
      ]
    }
  ],
  "reuse": {"eligible": 20, "reused": 20},
  "rankings": {
    "baseline": ["app-1", "app-2"],
    "candidate": ["app-1", "app-2"]
  }
}
```

Các run cùng fingerprint được hiểu là forced rerun. Thứ tự thời gian được xác định tường minh bằng `run_index`/`sequence`, sau đó `created_at`; thứ tự trong file chỉ là tie-breaker cuối. Run sớm nhất của mỗi application là baseline, các run sau là rerun. Nếu không cung cấp ranking, CLI suy ranking từ score giảm dần, coverage giảm dần, rồi application_id tăng dần.

Exporter chính thức chỉ đọc `backend/scripts/export_matching_snapshot.py` xuất assessment ID, fingerprint, điểm, coverage, outcome và ranking. Exporter không xuất CV text, profile facts, quote bằng chứng hoặc provider snapshot.

### 4.2 Chạy đo

```bash
cd backend
.venv/bin/python scripts/evaluate_matching.py /path/to/snapshots.json --check
.venv/bin/python scripts/evaluate_matching.py /path/to/snapshots.json \
  --output /path/to/report.json --check
```

`--check` trả exit code `2` khi không đạt ngưỡng.

### 4.3 Ngưỡng chấp nhận

- Fingerprint reuse: **100%** với cùng fingerprint.
- Forced rerun khác fingerprint nhưng cùng nội dung nghiệp vụ: P95 score drift **≤ 2 điểm**.
- Criterion flip rate: **≤ 2%**.
- Ranking: Kendall tau mục tiêu **≥ 0.90**, Top-10 overlap **≥ 0.90**.
- Mọi `NO_MATCH` bắt buộc và mọi flip của must-have phải được HR review thủ công trước khi phát hành policy mới, kể cả khi tỉ lệ tổng đạt ngưỡng.

## 5. Golden set của HR

Fixture tổng hợp trong repo chỉ là smoke test; không chứng minh chất lượng trên CV thật. Trước pilot mở rộng, HR cần xây golden set riêng:

1. Chọn 50–100 CV đã ẩn danh/được phép sử dụng, đa dạng vị trí, ngôn ngữ EN/VI, PDF/DOCX/OCR, CV ngắn/dài và trường hợp biên.
2. Với từng tiêu chí, hai HR gán độc lập: `STRONG_MATCH`, `MATCH`, `UNCLEAR` hoặc `NO_MATCH`, kèm quote bằng chứng.
3. HR thứ ba/HR Lead phân xử khi hai nhãn khác nhau; lưu lý do phân xử.
4. Tách tập calibration để chỉnh alias/rule và holdout không được dùng chỉnh rule để báo cáo cuối.
5. Không đưa thuộc tính nhạy cảm vào nhãn hoặc dùng chúng làm feature.
6. Mỗi thay đổi rule/prompt/policy phải chạy lại toàn bộ golden set; báo cáo outcome accuracy, false MATCH, false NO_MATCH, unresolved rate và các metric ổn định ở mục 4.

Chỉ khi có nhãn HR thật đủ lớn mới cân nhắc Learning-to-Rank. Ngưỡng bắt đầu đánh giá LTR: vài trăm application đã có quyết định HR nhất quán hoặc đủ cặp so sánh pairwise; LTR chỉ xếp lại trong cùng gate/coverage hợp lệ và không được phá fingerprint/audit trail.

## 6. Giới hạn hiện tại và bước hạ tầng tiếp theo

Đã triển khai lexical/rule retrieval trong tiến trình worker. **Chưa** triển khai pgvector, embedding BGE, cross-encoder reranker hoặc NLI service; không được mô tả các thành phần này là đã hoàn thành.

Chỉ bổ sung semantic retrieval khi golden set chứng minh lexical rule bỏ sót bằng chứng do paraphrase. Khi đó bắt buộc:

- migration pgvector và bảng chunk embedding gắn với chunk hash/index version;
- pin embedding model + dimension + index version vào fingerprint;
- reranker/NLI pin version, có ngưỡng hiệu chuẩn trên holdout;
- fallback lexical khi service semantic không sẵn sàng;
- đo lại unresolved rate, false-match và độ ổn định trước phát hành.

## 7. Kiểm thử liên quan

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/test_deterministic_matching.py \
  backend/tests/test_matching_evaluation.py \
  backend/tests/test_phase1_unit.py \
  backend/tests/test_matching_audit_fixes.py
```

Integration test cần PostgreSQL cục bộ dùng một lần theo `backend/tests/README.md`; không chạy chúng trên database production/Supabase thật.
