# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Data Observability

**Họ và tên:** Võ Thiên Phú - 2A202600336 - Thành viên 3 — E402-Group06
**Vai trò:** Embed & Idempotency Owner
**Ngày nộp:** 2026-04-15
**Độ dài yêu cầu:** 400–650 từ

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
- `etl_pipeline.py` phần `cmd_embed_internal()` — ChromaDB setup, upsert + prune
- `eval_retrieval.py` — before/after evaluation retrieval
- `grading_run.py` — grading JSONL generation cho 3 câu gq_d10_01..03
- Quản lý `chroma_db/` và collection `day10_kb`

**Kết nối với thành viên khác:**
- Nhận cleaned CSV từ Cleaning Owner
- Chạy eval để verify quality trước khi Monitoring Owner báo cáo

**Bằng chứng (log từ `artifacts/logs/run_lab-final.log`):**
```
embed_upsert count=6 collection=day10_kb
```

---

## 2. Một quyết định kỹ thuật (100–150 từ)

**Quyết định:** dùng **upsert theo `chunk_id`** thay vì insert thuần túy hoặc delete-then-insert.

Lý do:
1. **Idempotent:** chạy lại pipeline với cùng cleaned CSV → vector không đổi
2. **Prune đúng:** sau upsert, xóa `chunk_id` không còn trong cleaned mới nhất → tránh stale vector
3. **Efficient:** upsert chỉ cập nhật vector đã thay đổi, giữ vector không đổi

Trade-off: Chroma upsert ghi đè vector cũ nếu `chunk_text` thay đổi (ví dụ: fix "14→7 ngày"). Đây là **hành vi mong muốn** — vector phải reflect nội dung mới.

Quyết định khác: **dùng `all-MiniLM-L6-v2`** thay vì OpenAI embeddings. Lab offline được (không cần API key) và đủ tốt cho Vietnamese text.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** khi chạy `ci-smoke` và `ci-smoke2` liên tiếp, Chroma collection chứa duplicate vectors cho cùng `chunk_id`.

**Metric/check phát hiện:**
- `col.count()` sau 2 run = 12 thay vì 6
- Top-k retrieval trả về 2 kết quả gần giống nhau cho cùng câu hỏi

**Fix:** đảm bảo `chunk_id` stable (không thay đổi giữa các run) bằng `_stable_chunk_id()`:
```python
def _stable_chunk_id(doc_id, chunk_text, seq):
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode()).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"
```
Verify: `ci-smoke` và `ci-smoke2` tạo cùng cleaned CSV → idempotent ✅

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Grading từ `artifacts/eval/grading_run.jsonl` (lab-final):**
```
gq_d10_01: contains_expected=true, hits_forbidden=false, top1_doc_matches=true ✅
gq_d10_02: contains_expected=true ✅
gq_d10_03: contains_expected=true, hits_forbidden=false, top1_doc_matches=true ✅
```

**Eval từ `artifacts/eval/before_after_eval.csv`:**
| Câu hỏi | Scenario | hits_forbidden | top1_doc_expected |
|----------|----------|---------------|-------------------|
| `q_refund_window` | inject-bad | YES | — |
| `q_refund_window` | eval-after-fix | NO | — |
| `q_leave_version` | eval-after-fix | NO | yes |

**Metric changed:** sau inject: `hits_forbidden=YES` cho refund → sau fix: `NO`.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ: tôi sẽ implement **embedding version tracking** — lưu embedding model version vào metadata của mỗi chunk. Khi đổi embedding model, hệ thống sẽ tự động re-embed toàn bộ collection và đo quality delta. Hiện tại vẫn phải xóa `chroma_db` thủ công nếu đổi model.
