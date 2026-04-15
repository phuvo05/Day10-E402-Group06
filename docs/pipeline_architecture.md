# Kiến trúc pipeline — Lab Day 10: Data Pipeline & Data Observability

**Nhóm:** E402-Group06
**Cập nhật:** 2026-04-15

---

## 1. Sơ đồ luồng (Mermaid)

```mermaid
flowchart TD
    subgraph Ingest
        A["raw CSV export<br/>(policy_export_dirty.csv)"]
    end

    subgraph Transform["Transform / Cleaning (cleaning_rules.py)"]
        B["Load &amp; Parse CSV"]
        C1["R1: Allowlist doc_id"]
        C2["R2: Parse date<br/>DD/MM/YYYY → ISO"]
        C3["R3: HR stale quarantine<br/>(eff_date &lt; 2026-01-01)"]
        C4["R4: Missing chunk / date quarantine"]
        C5["R5: Dedupe chunk_text"]
        C6["R6: Fix refund 14→7 ngày"]
        C7["R7: Phone PII quarantine"]
        C8["R8: Normalize whitespace"]
        C9["R9: Email PII quarantine"]
        C10["R10: Unicode NFC normalize"]
        C11["R11: URL quarantine"]
        C12["R12: Oversized chunk quarantine"]
        D["cleaned CSV"]
        Q["quarantine CSV"]
    end

    subgraph Quality["Quality (quality/expectations.py)"]
        E["Expectation Suite<br/>E1–E10"]
        E_HALT["halt → pipeline stops<br/>warn → log only"]
    end

    subgraph Embed["Embed (ChromaDB)"]
        F["Upsert by chunk_id"]
        G["Prune removed chunk_ids"]
        H["Chroma Collection<br/>day10_kb"]
    end

    subgraph Monitor["Monitoring (monitoring/freshness_check.py)"]
        I["Freshness Check<br/>SLA 24h"]
        J["PASS / WARN / FAIL"]
    end

    subgraph Artifacts["Artifacts"]
        K["manifest JSON<br/>(run_id, counts, paths)"]
        L["logs/run_{run_id}.log"]
    end

    A --> B
    B --> C1 --> C2 --> C3 --> C4 --> C5 --> C6 --> C7 --> C8 --> C9 --> C10 --> C11 --> C12
    C12 --> D
    C12 --> Q
    D --> E
    E -->|halt| E_HALT
    E -->|pass| F
    D --> F
    F --> G --> H
    H --> I --> J
    B --> K
    C12 --> L

    style Ingest fill:#e1f5fe
    style Transform fill:#fff3e0
    style Quality fill:#f3e5f5
    style Embed fill:#e8f5e9
    style Monitor fill:#fff9c4
    style Artifacts fill:#fce4ec
```

**Điểm đo Freshness:** measured tại boundary `publish` (sau khi embed hoàn tất), đọc `latest_exported_at` từ manifest.
**Ghi run_id:** mỗi run tạo `artifacts/manifests/manifest_{run_id}.json` chứa UUID/timestamp.
**Quarantine:** record bị reject ghi vào `artifacts/quarantine/quarantine_{run_id}.csv` với lý do.

---

## 2. Ranh giới trách nhiệm

| Thành phần | Input | Output | Owner nhóm |
|------------|-------|--------|------------|
| Ingest | `data/raw/policy_export_dirty.csv` | List[Dict] raw rows | Ingestion Owner |
| Transform | Raw rows | `(cleaned, quarantine)` tuples | Cleaning & Quality Owner |
| Quality | Cleaned rows | `ExpectationResult[]` + halt flag | Cleaning & Quality Owner |
| Embed | `cleaned CSV` | Chroma `day10_kb` collection (upsert + prune) | Embed & Idempotency Owner |
| Monitor | Manifest JSON | PASS/WARN/FAIL freshness | Monitoring / Docs Owner |

---

## 3. Idempotency & rerun

- **Upsert strategy:** mỗi `chunk_id` được upsert vào Chroma — chạy lại với cùng cleaned CSV → vector giữ nguyên (idempotent).
- **Prune:** sau mỗi run, xóa các `chunk_id` không còn trong cleaned CSV (tránh vector stale từ record đã quarantine/dedupe).
- **Verified:** chạy `ci-smoke` và `ci-smoke2` tạo cùng `cleaned_ci-smoke.csv` → manifest khớp hoàn toàn.

**Rerun 2 lần không duplicate vector.**

---

## 4. Liên hệ Day 09

Pipeline này cung cấp corpus đã clean & embed vào Chroma collection `day10_kb` (tách khỏi Day 09 `day09_kb`).

- **Day 09** multi-agent query vào `day09_kb` để trả lời hỏi đa nguồn.
- **Day 10** pipeline là lớp data observability trước khi agent "đọc đúng version" policy.
- Hai collection dùng **cùng embedding model** (`all-MiniLM-L6-v2`) nhưng cách ly để dễ debug.

---

## 5. Rủi ro đã biết

- HR policy có 2 version (10 ngày / 12 ngày) → quarantine bản cũ là chìa khóa chất lượng.
- Refund policy có stale chunk từ migration v3 → fix 14→7 ngày.
- Nếu raw export chứa PII (phone/email) → bị quarantine tự động (R7/R9).
- Freshness SLA mặc định 24h — cần alert channel (Slack/email) khi FAIL.
- Data contract owner chưa được gán người thực tế → cần cập nhật trước khi production.
