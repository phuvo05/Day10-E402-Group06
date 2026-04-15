# Runbook — Lab Day 10: Data Pipeline & Data Observability

**Nhóm:** E402-Group06
**Ngày:** 2026-04-15

---

## Symptom

**User / agent thấy gì?**

- Agent trả lời "14 ngày làm việc" thay vì "7 ngày làm việc" cho câu hỏi về refund window
- Agent trả lời "10 ngày phép năm" thay vì "12 ngày phép năm" cho HR leave question
- Retrieval trả về chunk trống hoặc chunk từ `legacy_catalog_xyz_zzz` (doc lạ)
- Freshness alert: `freshness_check=FAIL` — dữ liệu cũ hơn 24 giờ

**Metric báo hiệu:**
- `hits_forbidden=yes` trong `artifacts/eval/before_after_eval.csv`
- `quarantine_records` tăng đột ngột
- `expectation[refund_no_stale_14d_window] FAIL` trong log

---

## Detection

**Metric nào báo?**

1. **Freshness check:** `python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<run-id>.json`
   - → `FAIL` nếu `latest_exported_at` > 24 giờ
2. **Expectation suite:** chạy `python etl_pipeline.py run` → kiểm tra log
   - → `FAIL (halt)` nếu có expectation halt fail
3. **Eval retrieval:** `python eval_retrieval.py --out artifacts/eval/before_after_eval.csv`
   - → `hits_forbidden=yes` = chunk stale trong top-k
4. **Quarantine spike:** so sánh `quarantine_records` giữa các run
   - → tăng đột ngột = có record bất thường từ nguồn mới

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/*.json` mới nhất | Tìm `run_id`, `latest_exported_at`, `quarantine_records` |
| 2 | Mở `artifacts/quarantine/quarantine_<run_id>.csv` | Xem `reason` column — identify failure mode |
| 3 | So sánh với baseline (`ci-smoke`): raw=10, cleaned=6 | Nếu khác → có data drift |
| 4 | Chạy `python eval_retrieval.py` | Kiểm tra `hits_forbidden`, `contains_expected` |
| 5 | Kiểm tra `artifacts/logs/run_<run_id>.log` | Xem expectation results từng E1–E10 |
| 6 | Nếu `stale_hr_policy_effective_date`: kiểm tra `effective_date` raw CSV | Xác nhận version conflict |
| 7 | Nếu `invalid_effective_date_format`: kiểm tra date format raw | Xác nhận DD/MM/YYYY vs ISO |

---

## Mitigation

**Cách xử lý theo failure mode:**

### A. Refund window stale (14 ngày)
```bash
# Đã có rule fix tự động — nếu thấy 14 ngày trong cleaned:
# 1. Kiểm tra cleaning_rules.py có apply_refund_window_fix=True
python etl_pipeline.py run --run-id fix-refund
# 2. Verify: expectation[refund_no_stale_14d_window] OK
cat artifacts/logs/run_fix-refund.log | grep refund
# 3. Re-embed
python eval_retrieval.py --out artifacts/eval/eval_after_fix.csv
```

### B. HR stale policy (10 ngày phép)
```bash
# Quarantine tự động bắt bản HR cũ — verify quarantine có record id=7
# Chunk 12 ngày đã giữ lại
grep "12 ngày" artifacts/cleaned/cleaned_<run_id>.csv
# Eval: hits_forbidden=no
python eval_retrieval.py --out artifacts/eval/eval_hr_fix.csv
```

### C. Freshness FAIL
```bash
# 1. Xác định age_hours trong manifest
cat artifacts/manifests/manifest_<run_id>.json | grep age_hours
# 2. Nếu cần: rerun pipeline để refresh
python etl_pipeline.py run --run-id refresh-$(date +%Y%m%d%H%M)
# 3. Hoặc tạm banner "data stale" cho agent
```

### D. PII leak (phone/email)
```bash
# Quarantine tự động — kiểm tra
grep -E "phone_number|email_address" artifacts/quarantine/quarantine_<run_id>.csv
# Khôi phục sau khi sanitize nguồn
```

---

## Prevention

**Thêm guardrail để tránh tái diễn:**

1. **Expectation halt mới:** thêm E7 (phone PII), E10 (email PII) — halt nếu PII phát hiện
2. **Alert channel:** kết nối `alert_channel` trong `data_contract.yaml` với Slack/email
3. **Version enforcement:** `effective_date` cutoff cứng trong contract + cleaning rule
4. **Freshness monitor:** cron job chạy `freshness` command mỗi 6 giờ
5. **Before/after eval:** chạy tự động sau mỗi pipeline run để catch regression
6. **Data contract owner:** gán người chịu trách nhiệm cho từng `doc_id`

**Kết nối Day 11 (nếu có):**
- Pipeline pass/fail → webhook → agent không answer nếu freshness FAIL
- Quarantine rate alert → tự động pauze agent cho đến khi human review
