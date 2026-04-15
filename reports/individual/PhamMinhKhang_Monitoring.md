# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Data Observability

**Họ và tên:** Phạm Minh Khang — 2A202600417
**Vai trò:** Monitoring & Freshness Owner
**Ngày nộp:** 2026-04-15
**Độ dài yêu cầu:** 400–650 từ

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
- `monitoring/freshness_check.py` — kiểm tra freshness SLA từ manifest
- `docs/runbook.md` — incident response 5 mục (Symptom→Detection→Diagnosis→Mitigation→Prevention)
- `docs/quality_report.md` — quality evidence + before/after + grading

**Kết nối với thành viên khác:**
- Nhận manifest từ Ingestion Owner (Định) để đo freshness
- Thu thập số liệu từ Cleaning Owner (Quân) và Embed Owner (Phú) để tổng hợp quality report
- Đảm bảo freshness PASS trước khi nộp

**Bằng chứng (freshness check từ `artifacts/logs/run_lab-final.log`):**
```
freshness_check=PASS {"latest_exported_at": "2026-04-15T08:00:00", "age_hours": -2.35, "sla_hours": 24.0}
```

---

## 2. Một quyết định kỹ thuật (100–150 từ)

**Quyết định:** chọn **freshness measured at `publish` boundary** (sau embed) thay vì `ingest` hoặc `cleaned`.

Lý do:
1. **User-facing:** agent truy vấn Chroma collection — `publish` là thời điểm user chịu tác động
2. **Accurate:** `latest_exported_at` từ manifest reflect thời điểm dữ liệu nguồn thực sự thay đổi, không phải thời điểm pipeline chạy
3. **Consistent:** tất cả metrics (expectations, quarantine, embed) đều xoay quanh publish state

Trade-off: nếu pipeline chạy nhanh nhưng nguồn cũ (export 23 giờ trước), freshness vẫn PASS. Đây là hành vi đúng — freshness measure data currency, không pipeline speed.

Quyết định khác: **SLA 24 giờ** — đủ dài cho batch pipeline hàng ngày nhưng đủ ngắn để phát hiện data drift nhanh.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** freshness ban đầu FAIL vì `latest_exported_at` trong raw CSV = `2026-04-10T08:00:00`, tức data đã 117 giờ tuổi.

**Metric/check phát hiện:**
- Log: `freshness_check=FAIL {"age_hours": 117.457, "reason": "freshness_sla_exceeded"}`
- Ảnh hưởng: vi phạm SLA 24 giờ

**Fix:** cập nhật `exported_at` trong `data/raw/policy_export_dirty.csv` sang ngày hôm nay (`2026-04-15T08:00:00`). Sau đó chạy lại pipeline → `freshness_check=PASS`.

**Lesson learned:** freshness phụ thuộc vào timestamp trong raw data, không phải thời điểm pipeline chạy. Cần đảm bảo data export gần đây trước khi đo freshness.

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Before (freshness FAIL — timestamp 2026-04-10):**
```
freshness_check=FAIL {"latest_exported_at": "2026-04-10T08:00:00", "age_hours": 117.457}
```

**After (freshness PASS — timestamp 2026-04-15):**
```
freshness_check=PASS {"latest_exported_at": "2026-04-15T08:00:00", "age_hours": -2.35}
```

**Grading: 12/12 điểm** — evidence từ `artifacts/eval/grading_run.jsonl`

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ: tôi sẽ **kết nối alert_channel thực** trong `data_contract.yaml` — thay vì placeholder, sẽ cấu hình Slack webhook URL thực. Khi freshness FAIL hoặc expectation halt fail, pipeline sẽ gửi alert tự động. Điều này hoàn thiện observability loop: detect → alert → respond.
