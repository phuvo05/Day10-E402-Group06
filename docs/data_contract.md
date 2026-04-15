# Data contract — Lab Day 10: Data Pipeline & Data Observability

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `data/raw/policy_export_dirty.csv` | CSV file read via `load_raw_csv()` | Duplicate chunk (id 1≡2), missing date (id 5), stale HR (id 7), invalid date format (id 10), unknown doc_id (id 9) | quarantine_records ↑, raw_records > cleaned_records |
| HR system (internal) | Export CSV batch job | Export chứa bản HR 2025 (10 ngày) song song với 2026 (12 ngày) | quarantine HR stale: `stale_hr_policy_effective_date` |
| Policy DB | Migration script (policy-v3→v4) | Refund window lỗi sync: 14 ngày thay vì 7 ngày | expectation `refund_no_stale_14d_window` FAIL |
| IT helpdesk KB | Manual export | Date format DD/MM/YYYY không chuẩn | quarantine `invalid_effective_date_format` |
| Unknown catalog | Export không rõ nguồn | doc_id `legacy_catalog_xyz_zzz` không trong allowlist | quarantine `unknown_doc_id` |
| (Tương lai) API ingest | REST/GraphQL | Timestamp drift, schema mismatch | freshness FAIL |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| `chunk_id` | string | Có | Hash ổn định: `doc_id + chunk_text + seq` → SHA256 16 chars |
| `doc_id` | string | Có | Khóa logic tài liệu nguồn (trong allowlist) |
| `chunk_text` | string | Có | Đã normalize whitespace, Unicode NFC, đã fix stale refund, không PII |
| `effective_date` | date (YYYY-MM-DD) | Có | Chuẩn hóa từ nhiều format; ISO là canonical |
| `exported_at` | datetime (ISO 8601) | Có | Thời điểm export từ nguồn |

---

## 3. Quy tắc quarantine vs drop

**Quarantine** (ghi vào `artifacts/quarantine/quarantine_{run_id}.csv`):

- `unknown_doc_id` — doc_id không trong allowlist
- `missing_effective_date` — trường ngày trống
- `invalid_effective_date_format` — không parse được sang ISO
- `stale_hr_policy_effective_date` — HR policy hiệu lực trước 2026-01-01
- `missing_chunk_text` — chunk_text trống
- `duplicate_chunk_text` — trùng nội dung (giữ bản đầu)
- `phone_number_detected` — PII: số điện thoại VN
- `email_address_detected` — PII: địa chỉ email
- `url_detected` — HTTP/HTTPS link trong chunk
- `oversized_chunk` — chunk > 2000 ký tự

**Drop (không ghi đâu):** không có — mọi reject đều quarantine để có thể audit.

**Ai approve merge lại:** Cleaning & Quality Owner + Data Steward (team lead).

---

## 4. Phiên bản & canonical

| Policy | Source of truth | Version hiện hành | Version cũ (stale) |
|--------|-----------------|-------------------|---------------------|
| `policy_refund_v4` | `data/docs/policy_refund_v4.txt` | 7 ngày làm việc | 14 ngày (v3 migration bug) |
| `hr_leave_policy` | HR system export | effective_date ≥ 2026-01-01 → 12 ngày phép năm | < 2026-01-01 → 10 ngày (bản 2025) |
| `sla_p1_2026` | `data/docs/sla_p1_2026.txt` | P1 first response 15 phút | — |
| `it_helpdesk_faq` | IT KB export | Chuẩn format ISO | DD/MM/YYYY |

**Cutoff version enforcement:** hard-coded trong `cleaning_rules.py` và `data_contract.yaml` (`hr_leave_min_effective_date: "2026-01-01"`).

---

## 5. Freshness SLA

- **SLA:** 24 giờ kể từ `latest_exported_at`
- **Alert channel:** Slack `#data-alerts` / email `data-team@company.com`
- **Owner:** Data Engineering team — `__TODO__` (cần gán người thực tế)
- **Measured at:** `publish` boundary (sau khi embed hoàn tất)

---

## 6. Quality rules (từ contract)

| Rule ID | Mô tả | Severity |
|---------|-------|----------|
| `no_duplicate_chunk_text` | Không trùng nội dung chunk | warn |
| `no_stale_refund_window` | Không chunk refund chứa 14 ngày | halt |
| `no_phone_pii` | Không PII: số điện thoại VN | halt |
| `no_email_pii` | Không PII: email | halt |
| `no_url_in_cleaned` | Không URL/http links | warn |
| `chunk_max_length_2000` | Chunk không quá 2000 ký tự | warn |
