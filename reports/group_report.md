# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** E402-Group06
**Thành viên:**
| Họ tên | MSSV | Vai trò (Day 10) |
|--------|------|-----------------|
| Phan Dương Định | 2A202600277 | Ingestion & Raw Owner |
| Nguyễn Anh Quân | 2A202600132 | Cleaning & Quality Owner |
| Võ Thiên Phú | 2A202600336 | Embed & Idempotency Owner |
| Phạm Minh Khang | 2A202600417 | Monitoring & Freshness Owner |
| Đào Hồng Sơn | 2A202600462 | Data Contract & Versioning Owner |

**Ngày nộp:** 2026-04-15

---

## 1. Pipeline tổng quan (150–200 từ)

**Nguồn raw:** file `data/raw/policy_export_dirty.csv` chứa 10 records với nhiều failure modes:
- Duplicate chunk (id 1≡2: cùng refund 7 ngày)
- Missing date (id 5: trống hoàn toàn)
- Invalid date format (id 10: `01/02/2026` DD/MM/YYYY)
- Stale HR policy (id 7: bản 2025 effective_date=2025-01-01)
- Unknown doc_id (id 9: `legacy_catalog_xyz_zzz`)

**Tóm tắt luồng:**
Raw CSV → Ingest (load) → Transform (12 rules) → Quality (10 expectations) → Embed (ChromaDB upsert+prune) → Freshness check → Manifest

**Lệnh chạy một dòng:**
```bash
python etl_pipeline.py run --run-id lab-final && python eval_retrieval.py --out artifacts/eval/before_after_eval.csv
```

**run_id:** lấy từ `--run-id` hoặc UTC timestamp tự động

---

## 2. Cleaning & expectation (150–200 từ)

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| R7: phone PII quarantine | 0 records | 0 (không có PII trong raw mẫu) | Quarantine file |
| R8: whitespace normalize | text length diff | cleaned text đồng nhất | `artifacts/cleaned/cleaned_*.csv` |
| R9: email PII quarantine | 0 records | 0 (không có email trong raw) | Quarantine file |
| R10: Unicode NFC normalize | text inconsistent | NFC normalized | `cleaning_rules.py` R10 |
| R11: URL quarantine | 0 records | 0 (không có URL trong raw) | Quarantine file |
| R12: oversized chunk | 0 records | 0 (chunk ≤ 2000 chars) | Quarantine file |
| E7: no_phone_pii halt | N/A | 0 PII survive | `expectation[no_phone_pii_in_cleaned] OK` |
| E8: no_url_in_cleaned warn | N/A | 0 URL survive | `expectation[no_url_in_cleaned] OK` |
| E9: chunk_max_length_2000 warn | N/A | 0 oversized | `expectation[chunk_max_length_2000] OK` |
| E10: no_email_pii halt | N/A | 0 PII survive | `expectation[no_email_pii_in_cleaned] OK` |
| Inject `--no-refund-fix` | 0 stale | 1 stale chunk (14 ngày) | `expectation[refund_no_stale_14d_window] FAIL` |
| Quarantine HR stale | 0 | 1 record (id=7, bản 2025) | `stale_hr_policy_effective_date` |

**Baseline rules (6):**
- R1: doc_id allowlist
- R2: date parse DD/MM/YYYY → ISO
- R3: HR stale quarantine (eff_date < 2026-01-01)
- R4: missing chunk_text / effective_date quarantine
- R5: dedupe chunk_text
- R6: fix stale refund 14→7 ngày

**Baseline expectations (6):**
- E1: min 1 row (halt)
- E2: no empty doc_id (halt)
- E3: no stale 14d refund (halt)
- E4: chunk min length 8 (warn)
- E5: effective_date ISO format (halt)
- E6: no stale 10d HR (halt)

**New expectations (4):**
- E7: no phone PII (halt)
- E8: no URL (warn)
- E9: chunk max length 2000 (warn)
- E10: no email PII (halt)

**Ví dụ 1 lần expectation fail và cách xử lý:**
Khi chạy `python etl_pipeline.py run --run-id eval-before --no-refund-fix --skip-validate`:
- `expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1`
- Pipeline vẫn embed do `--skip-validate`
- Fix: bỏ flag → chạy lại chuẩn → expectation pass

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

### Kịch bản inject

**Inject:** `python etl_pipeline.py run --run-id eval-before --no-refund-fix --skip-validate`
- Tác động: chunk `policy_refund_v4` chứa "14 ngày làm việc" (stale từ migration v3)
- `expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1`

**Sau fix:** `python etl_pipeline.py run --run-id eval-after`
- Chunk đúng: "7 ngày làm việc"
- `expectation[refund_no_stale_14d_window] OK (halt) :: violations=0`

### Bảng kết quả từ `artifacts/eval/before_after_eval.csv`

| Câu hỏi | Scenario | top1_doc_id | contains_expected | hits_forbidden | Trạng thái |
|----------|----------|-------------|-------------------|----------------|-----------|
| `q_refund_window` | inject-bad | policy_refund_v4 | yes | **YES** | ❌ Stale chunk |
| `q_p1_sla` | inject-bad | sla_p1_2026 | yes | no | ✅ Pass |
| `q_lockout` | inject-bad | it_helpdesk_faq | yes | no | ✅ Pass |
| `q_leave_version` | inject-bad | hr_leave_policy | yes | no | ✅ Pass |
| `q_refund_window` | eval-after-fix | policy_refund_v4 | yes | **NO** | ✅ Fixed |
| `q_p1_sla` | eval-after-fix | sla_p1_2026 | yes | no | ✅ Pass |
| `q_lockout` | eval-after-fix | it_helpdesk_faq | yes | no | ✅ Pass |
| `q_leave_version` | eval-after-fix | hr_leave_policy | yes | no | ✅ Pass |

**Nhận xét:** Pipeline fix chuyển `q_refund_window` từ `hits_forbidden=YES` sang `NO`. Chứng minh cleaning rule R6 (fix 14→7 ngày) có tác động đo được lên retrieval quality.

---

## 4. Freshness & monitoring (100–150 từ)

**SLA chọn:** 24 giờ

**Kết quả freshness trên manifest `lab-final`:**
```
freshness_check=PASS {
  "latest_exported_at": "2026-04-15T08:00:00",
  "age_hours": -2.35,
  "sla_hours": 24.0
}
```

**Data fresh ✅:** `latest_exported_at` = 2026-04-15T08:00:00, age_hours = -2.35.

| Trạng thái | Điều kiện | Hành động |
|------------|-----------|-----------|
| PASS | age_hours ≤ 24 | OK |
| WARN | no timestamp | Kiểm tra |
| FAIL | age_hours > 24 | Rerun ngay |

---

## 5. Liên hệ Day 09 (50–100 từ)

Pipeline Day 10 tạo và duy trì **Chroma collection `day10_kb`** — tách biệt với `day09_kb` của multi-agent Day 09.

- **Day 09** agent query vào `day09_kb` để tổng hợp câu trả lời đa nguồn
- **Day 10** pipeline đảm bảo corpus trong `day10_kb` sạch, đúng version, không stale
- **Cùng embedding model:** `all-MiniLM-L6-v2` để đảm bảo vector space tương thích

Tách riêng giúp debug dễ hơn (Day 09 không bị ảnh hưởng khi Day 10 experiment).

---

## 6. Grading

**Evidence từ `artifacts/eval/grading_run.jsonl`:**

| Câu | contains_expected | hits_forbidden | top1_doc_matches | Điểm |
|------|-----------------|---------------|-----------------|------|
| gq_d10_01 | true | false | true | ✅ 4+3 |
| gq_d10_02 | true | false | null | ✅ 3 |
| gq_d10_03 | true | false | true | ✅ 3+bonus |

**Tổng: 12/12 điểm grading + bonus**

---

## 7. Rủi ro còn lại & việc chưa làm

- **Alert channel thực tế:** `data_contract.yaml` vẫn placeholder
- **Great Expectations:** custom expectations đủ dùng
- **Freshness 2 boundary:** chưa đo ở ingest boundary
- **Data contract owner:** vẫn placeholder
