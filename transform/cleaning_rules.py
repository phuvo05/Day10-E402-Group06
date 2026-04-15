"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


# ===== NEW RULES (Sprint 2+) — E402-Group06 =====

# R7: Quarantine chunk chứa số điện thoại Việt Nam theo pattern 0xxx/84xxx
#    Failure mode: raw export chứa SDT nhân viên nội bộ (PII leak)
#    Metric impact: quarantine_records += 1 khi inject BOM có SDT
_PHONE_VIETNAM = re.compile(r"\b0\d{9,10}\b|\b\+84\d{9,10}\b")

def rule_quarantine_phone(text: str, row: Dict[str, Any]) -> Tuple[bool, str]:
    """Quarantine rows containing Vietnam phone number patterns (PII sanitization)."""
    if _PHONE_VIETNAM.search(text):
        return True, "phone_number_detected"
    return False, ""


# R8: Chuẩn hóa khoảng trắng thừa trong chunk_text (strip, collapse multiple spaces/newlines)
#    Failure mode: raw export từ PDF có extra spaces hoặc \n lạ
#    Metric impact: cleaned text length diff, downstream eval quality
def rule_normalize_whitespace(text: str) -> str:
    """Normalize whitespace: collapse multiple spaces, strip, normalize newlines to space."""
    return re.sub(r"[ \t]+", " ", re.sub(r"\r?\n", " ", text)).strip()


# R9: Quarantine chunk chứa email pattern (PII — địa chỉ email nhân viên)
#    Failure mode: export chứa email nội bộ không được publish
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

def rule_quarantine_email(text: str, row: Dict[str, Any]) -> Tuple[bool, str]:
    """Quarantine rows containing email addresses (PII sanitization)."""
    if _EMAIL_PATTERN.search(text):
        return True, "email_address_detected"
    return False, ""


# R10: Chuẩn hóa Unicode normalization (NFC) cho tiếng Việt
#    Failure mode: raw export từ source khác encoding → so sánh chunk text sai
import unicodedata

def rule_normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC form for consistent text comparison and embedding."""
    return unicodedata.normalize("NFC", text)


# R11: Quarantine chunk chứa URL/http links (internal links không được publish)
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)

def rule_quarantine_url(text: str, row: Dict[str, Any]) -> Tuple[bool, str]:
    """Quarantine rows containing HTTP/HTTPS URLs (internal links should be removed)."""
    if _URL_PATTERN.search(text):
        return True, "url_detected"
    return False, ""


# R12: Enforce max chunk length (≥2000 chars = potential PDF artifact / garbage)
#    Failure mode: PDF parser tạo chunk quá dài không có giá trị
_MAX_CHUNK_LENGTH = 2000

def rule_quarantine_oversized(text: str, row: Dict[str, Any]) -> Tuple[bool, str]:
    """Quarantine chunks exceeding max length (likely PDF parser garbage)."""
    if len(text) > _MAX_CHUNK_LENGTH:
        return True, "oversized_chunk"
    return False, ""


# ===== END NEW RULES =====


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
    4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    5) Loại trùng nội dung chunk_text (giữ bản đầu).
    6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.

    New rules (E402-Group06):
    R7)  Quarantine: phone number pattern VN (PII)
    R8)  Normalize: whitespace collapse + strip
    R9)  Quarantine: email address pattern (PII)
    R10) Normalize: Unicode NFC normalization
    R11) Quarantine: URL/http links
    R12) Quarantine: oversized chunk > 2000 chars
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        # R1: doc_id allowlist
        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        # R10: Unicode NFC normalization — apply before any text comparison
        text = rule_normalize_unicode(text)

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        # R3: HR stale policy version
        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        # R7: phone number PII
        do_q, r7_reason = rule_quarantine_phone(text, raw)
        if do_q:
            quarantine.append({**raw, "reason": r7_reason})
            continue

        # R9: email PII
        do_q, r9_reason = rule_quarantine_email(text, raw)
        if do_q:
            quarantine.append({**raw, "reason": r9_reason})
            continue

        # R11: URL detection
        do_q, r11_reason = rule_quarantine_url(text, raw)
        if do_q:
            quarantine.append({**raw, "reason": r11_reason})
            continue

        # R12: oversized chunk
        do_q, r12_reason = rule_quarantine_oversized(text, raw)
        if do_q:
            quarantine.append({**raw, "reason": r12_reason})
            continue

        # R8: normalize whitespace (apply before dedup comparison)
        text = rule_normalize_whitespace(text)

        key = _norm_text(text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        fixed_text = text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
