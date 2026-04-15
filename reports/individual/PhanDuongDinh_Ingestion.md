# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Data Observability

**Họ và tên:** Phan Dương Định — E402-Group06
**MSSV** 2A202600277
**Vai trò:** Ingestion / Raw Owner
**Ngày nộp:** 2026-04-15

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
- `data/raw/policy_export_dirty.csv` — thiết kế và xây dựng raw export với đầy đủ failure modes (10 records, 5 loại failure)
- `etl_pipeline.py` phần ingest — `load_raw_csv()`, đọc file raw, đếm `raw_records`
- Quản lý cấu trúc `artifacts/logs/` và `artifacts/manifests/`
- Ghi `run_id` vào log và manifest

**Kết nối với thành viên khác:**
- Cung cấp raw data cho Cleaning Owner (cleaning_rules.py)
- Phối hợp với Embed Owner để đảm bảo schema phù hợp
- Cung cấp manifest cho Monitoring Owner (freshness check)

**Bằng chứng (log thực tế từ `artifacts/logs/run_lab-final.log`):**
```
run_id=lab-final
raw_records=10
cleaned_records=6
quarantine_records=4
```

---

## 2. Một quyết định kỹ thuật (100–150 từ)

**Quyết định:** chọn đặt `run_id` làm UTC timestamp mặc định thay vì hash ngẫu nhiên.

Lý do:
1. **Debug dễ dàng:** timestamp cho biết thời điểm chạy mà không cần tra log
2. **Reproducible:** cùng raw file + cùng timestamp = deterministic
3. **Idempotent:** cho phép override bằng `--run-id` tùy chỉnh (như `ci-smoke`, `eval-before`, `eval-after`, `lab-final`)

Một quyết định khác: **ghi log ra cả console và file**. Console để developer debug nhanh, file để artifact hệ thống CI có thể parse. Đã fix Unicode encoding issue trên Windows (cp1252) bằng `_safe_print()` — tránh `UnicodeEncodeError` khi console không hỗ trợ Unicode.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** khi chạy `inject-bad` lần đầu, Unicode character `→` trong log message gây `UnicodeEncodeError` trên Windows console (cp1252).

**Metric/check phát hiện:**
- PowerShell output: `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'`
- Ảnh hưởng: pipeline dừng không embed được

**Fix:** thêm `_safe_print()` wrapper với ASCII fallback:
```python
def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))
```
Sau đó: thay message Unicode bằng ASCII (`→` → `=>`).

---

## 4. Bằng chứng trước / sau (80–120 từ)

**run_id:** `lab-final` (pipeline chuẩn cuối cùng)

**Evidence từ `artifacts/manifests/manifest_lab-final.json`:**
```json
{
  "run_id": "lab-final",
  "raw_records": 10,
  "cleaned_records": 6,
  "quarantine_records": 4,
  "latest_exported_at": "2026-04-15T08:00:00"
}
```

**Metric changed:** `raw_records=10` → sau pipeline: `quarantine_records=4` (4 records bị reject: id 2=duplicate, id 5=missing date, id 7=stale HR, id 9=unknown doc_id)

**Freshness:** `freshness_check=PASS` với `age_hours=-2.35` — data export hôm nay.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ: tôi sẽ thêm **metadata enrichment** vào raw rows — bổ sung trường `source_system` và `ingest_timestamp` ngay tại ingest layer. Điều này giúp lineage tracking (debug "dữ liệu này đến từ đâu") dễ hơn khi có nhiều nguồn hơn (API, DB, stream).
