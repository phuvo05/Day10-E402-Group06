# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Data Observability

**Họ và tên:** Nguyễn Anh Quân — E402-Group06
**Vai trò:** Cleaning & Quality Owner
**Ngày nộp:** 2026-04-15
**Độ dài yêu cầu:** 400–650 từ

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
- `transform/cleaning_rules.py` — thiết kế và implement 12 rules (6 baseline + 6 mới)
- `quality/expectations.py` — thiết kế và implement 10 expectations (6 baseline + 4 mới)
- Định nghĩa quarantine logic và reason codes
- Quản lý `artifacts/quarantine/` outputs

**Kết nối với thành viên khác:**
- Nhận raw rows từ Ingestion Owner
- Cung cấp cleaned rows cho Embed Owner
- Phối hợp với Monitoring Owner để phân biệt halt vs warn

**Bằng chứng (log thực tế từ `artifacts/logs/run_lab-final.log`):**
```
expectation[refund_no_stale_14d_window] OK (halt) :: violations=0
expectation[no_phone_pii_in_cleaned] OK (halt) :: phone_pii_count=0
expectation[no_email_pii_in_cleaned] OK (halt) :: email_pii_count=0
```

---

## 2. Một quyết định kỹ thuật (100–150 từ)

**Quyết định 1:** chọn **halt** cho E7 (phone PII) và E10 (email PII) thay vì warn.

Lý do:
1. **PII breach nghiêm trọng hơn data quality thông thường** — để lộ SDT/email nhân viên là vi phạm compliance
2. **Warn không đủ để dừng pipeline** — có thể embed PII vào vector store trước khi ai phát hiện
3. **`--skip-validate`** cho phép demo có chủ đích mà vẫn có safeguard

**Quyết định 2:** **rule order** — chạy R7 (phone) → R9 (email) → R11 (URL) → R12 (oversized) → R8 (whitespace) → dedup → refund fix. Order quan trọng vì normalization sau PII check đảm bảo PII không bị "che" bởi whitespace.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** chunk id=10 (`it_helpdesk_faq`) có `effective_date=01/02/2026` — format DD/MM/YYYY không parse được ISO check trong expectations (E5).

**Metric/check phát hiện:**
- Phát hiện qua: quarantine CSV có `invalid_effective_date_format` cho id=10
- Pipeline vẫn chạy vì date được normalize trong cleaning (R2: `01/02/2026` → `2026-02-01`)
- Nhưng **cleaned chunk** đúng format ISO → expectation E5 pass

**Fix đã có sẵn:** `_normalize_effective_date()` xử lý DD/MM/YYYY trước khi ghi cleaned CSV. Không cần thêm logic.

**Lesson learned:** luôn để cleaning xử lý format issues **trước** khi expectations validate output — nếu không expectation sẽ false-positive fail.

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Inject (`eval-before`):**
```
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1
```

**Sau fix (`eval-after`):**
```
expectation[refund_no_stale_14d_window] OK (halt) :: violations=0
```

**Eval từ `artifacts/eval/before_after_eval.csv`:**
| Câu hỏi | Scenario | hits_forbidden |
|----------|----------|---------------|
| `q_refund_window` | inject-bad | YES |
| `q_refund_window` | eval-after-fix | NO |

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ: tôi sẽ **tích hợp Great Expectations** để thay thế custom expectations. GE có pre-built validators (như `expect_column_values_to_match_regex`) giúp quản lý expectations có version control tốt hơn. Quan trọng hơn, GE có built-in Data Docs để generate HTML quality report tự động.
