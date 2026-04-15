# Quality Report — Lab Day 10: Data Pipeline & Data Observability

**Nhóm:** E402-Group06
**run_id:** lab-final
**Ngày:** 2026-04-15

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (raw) | Sau (cleaned) | Ghi chú |
|--------|-------------|----------------|---------|
| raw_records | 10 | 10 | Từ `data/raw/policy_export_dirty.csv` |
| cleaned_records | — | 6 | Sau 4 quarantine + dedupe |
| quarantine_records | — | 4 | unknown_doc_id, stale HR, dedupe, missing date |
| Expectation halt? | — | KHÔNG | Tất cả E1–E10 pass |
| quarantine từ rule mới | — | 0 | Không có PII/URL/oversized trong bộ mẫu |

**Baseline vs. Extended:**
- Baseline (E1–E6): quarantine 4 records (id 2, 5, 7, 9)
- Extended (+E7–E10): 0 records thêm trong bộ mẫu

**Evidence từ `artifacts/logs/run_lab-final.log`:**
```
expectation[min_one_row] OK (halt) :: cleaned_rows=6
expectation[no_empty_doc_id] OK (halt) :: empty_doc_id_count=0
expectation[refund_no_stale_14d_window] OK (halt) :: violations=0
expectation[chunk_min_length_8] OK (warn) :: short_chunks=0
expectation[effective_date_iso_yyyy_mm_dd] OK (halt) :: non_iso_rows=0
expectation[hr_leave_no_stale_10d_annual] OK (halt) :: violations=0
expectation[no_phone_pii_in_cleaned] OK (halt) :: phone_pii_count=0
expectation[no_url_in_cleaned] OK (warn) :: url_count=0
expectation[chunk_max_length_2000] OK (warn) :: oversized_chunks=0
expectation[no_email_pii_in_cleaned] OK (halt) :: email_pii_count=0
```

---

## 2. Before / after retrieval (bắt buộc)

### Kịch bản inject corruption (Sprint 3)

**Inject:** `python etl_pipeline.py run --run-id eval-before --no-refund-fix --skip-validate`
- Chunk `policy_refund_v4` còn "14 ngày làm việc" trong cleaned
- **Evidence:** `expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1`

**Sau fix:** `python etl_pipeline.py run --run-id eval-after`
- Chunk đúng: "7 ngày làm việc"
- **Evidence:** `expectation[refund_no_stale_14d_window] OK (halt) :: violations=0`

### Bảng before/after từ `artifacts/eval/before_after_eval.csv`

| Câu hỏi | Scenario | top1_doc_id | contains_expected | hits_forbidden | top1_doc_expected |
|----------|----------|-------------|-------------------|----------------|-------------------|
| `q_refund_window` | inject-bad | policy_refund_v4 | yes | **YES** | — |
| `q_p1_sla` | inject-bad | sla_p1_2026 | yes | no | — |
| `q_lockout` | inject-bad | it_helpdesk_faq | yes | no | — |
| `q_leave_version` | inject-bad | hr_leave_policy | yes | no | yes |
| `q_refund_window` | eval-after-fix | policy_refund_v4 | yes | **NO** | — |
| `q_p1_sla` | eval-after-fix | sla_p1_2026 | yes | no | — |
| `q_lockout` | eval-after-fix | it_helpdesk_faq | yes | no | — |
| `q_leave_version` | eval-after-fix | hr_leave_policy | yes | no | yes |

**Nhận xét:** `q_refund_window` chuyển từ `hits_forbidden=YES` sang `NO` sau khi pipeline fix. Chứng minh cleaning rule R6 (fix 14→7 ngày) có tác động đo được lên retrieval quality.

---

## 3. Freshness & monitor

**Manifest `lab-final`:**
```
freshness_check=PASS {"latest_exported_at": "2026-04-15T08:00:00", "age_hours": -2.35, "sla_hours": 24.0}
```

**SLA chọn:** 24 giờ — data fresh ✅

| Trạng thái | Điều kiện | Hành động |
|------------|-----------|-----------|
| PASS | age_hours ≤ 24 | Dữ liệu fresh ✅ |
| WARN | no timestamp | Kiểm tra |
| FAIL | age_hours > 24 | Rerun ngay |

---

## 4. Grading Results

**Evidence từ `artifacts/eval/grading_run.jsonl`:**

| Câu | contains_expected | hits_forbidden | top1_doc_matches | Điểm |
|------|-----------------|---------------|-----------------|------|
| gq_d10_01 | true | false | true | ✅ Full (4+3) |
| gq_d10_02 | true | false | null | ✅ Full (3) |
| gq_d10_03 | true | false | true | ✅ Full (3+bonus) |

**Tổng: 12/12 điểm grading + bonus**

---

## 5. Hạn chế & việc chưa làm

- Alert channel thực tế (Slack/email) chưa kết nối
- Great Expectations framework chưa tích hợp
- Freshness chỉ đo ở publish boundary
