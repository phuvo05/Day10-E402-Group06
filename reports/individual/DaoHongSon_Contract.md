# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Data Observability

**Họ và tên:** Thành viên 5 — E402-Group06
**Vai trò:** Data Contract & Versioning Owner
**Ngày nộp:** 2026-04-15
**Độ dài yêu cầu:** 400–650 từ

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
- `docs/data_contract.md` — source map, schema cleaned, quarantine rules, versioning canonical
- `contracts/data_contract.yaml` — cấu hình contract đầy đủ (owner, SLA, alert, sources)
- `reports/group_report.md` — tổng hợp toàn bộ metrics và bằng chứng nhóm
- Quản lý versioning policy (HR 2025 vs 2026, refund v3 vs v4)

**Kết nối với thành viên khác:**
- Phối hợp với Cleaning Owner để đồng bộ rule với contract
- Cung cấp `allowed_doc_ids` cho Ingestion Owner
- Đảm bảo quarantine rules khớp với contract definition

**Bằng chứng (từ `contracts/data_contract.yaml`):**
```yaml
owner_team: "E402-Group06 — Data Engineering Team"
freshness:
  measured_at: "publish"
  sla_hours: 24
  alert_channel: "Slack #data-alerts / email data-team@company.com"
policy_versioning:
  hr_leave_min_effective_date: "2026-01-01"
  refund_v4_window_days: 7
```

---

## 2. Một quyết định kỹ thuật (100–150 từ)

**Quyết định:** đặt **version cutoff cho HR policy là `2026-01-01`** làm ranh giới cứng giữa bản cũ và mới.

Lý do:
1. **Unambiguous:** ngày cố định, không cần so sánh nội dung
2. **Audit-friendly:** ai cũng kiểm tra được — chỉ cần nhìn `effective_date`
3. **Enforceable:** cleaning rule có thể implement dễ dàng (`eff_date < 2026-01-01 → quarantine`)

Trade-off: nếu có HR policy mới vào ngày 2026-01-01, cả 2 version có cùng cutoff. Đã giải quyết bằng cách đặt `<` (strictly before) thay vì `<=`.

Quyết định khác: **không hard-code cutoff trong code** mà đặt trong `data_contract.yaml` (`hr_leave_min_effective_date`). Điều này cho phép thay đổi cutoff mà không sửa code — compliance team có thể cập nhật contract.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** HR policy có 2 version trong raw data — bản 2025 (id=7, `effective_date=2025-01-01`, 10 ngày phép) và bản 2026 (id=8, `effective_date=2026-02-01`, 12 ngày phép). Nếu không quarantine, agent có thể trả lời sai.

**Metric/check phát hiện:**
- Quarantine file: `stale_hr_policy_effective_date` cho id=7
- Expectation E6: `hr_leave_no_stale_10d_annual` pass
- `q_leave_version` eval: `top1_doc_expected=yes`

**Fix:** rule R3 quarantine tự động bắt bản cũ:
```python
if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
    quarantine.append({**raw, "reason": "stale_hr_policy_effective_date"})
```
Chỉ bản 2026 (id=8, 12 ngày) được giữ lại trong cleaned.

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Quarantine evidence từ `artifacts/quarantine/quarantine_lab-final.csv`:**
```
id=7, hr_leave_policy, "Nhân viên dưới 3 năm được 10 ngày phép năm (bản HR 2025).",
effective_date=2025-01-01, reason=stale_hr_policy_effective_date
```

**Cleaned evidence từ `artifacts/cleaned/cleaned_lab-final.csv`:**
```
id=8, hr_leave_policy, "Nhân viên dưới 3 năm được 12 ngày phép năm theo chính sách 2026.",
effective_date=2026-02-01
```

**Eval: `q_leave_version` → `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes`**

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ: tôi sẽ implement **versioned contract enforcement** — mỗi khi raw export có `effective_date` mới cho một `doc_id`, contract sẽ tự động detect và yêu cầu human approval trước khi publish. Điều này đảm bảo không có policy mới được embed mà không qua review.
