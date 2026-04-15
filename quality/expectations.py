"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7 (NEW): PII check — no phone number should survive to cleaned
    #    Failure: phone number in chunk_text = internal contact info leaked
    #    Severity: halt (PII breach is critical)
    _PHONE_VIETNAM = re.compile(r"\b0\d{9,10}\b|\b\+84\d{9,10}\b")
    bad_phone = [
        r for r in cleaned_rows
        if _PHONE_VIETNAM.search((r.get("chunk_text") or "").lower())
    ]
    ok7 = len(bad_phone) == 0
    results.append(
        ExpectationResult(
            "no_phone_pii_in_cleaned",
            ok7,
            "halt",
            f"phone_pii_count={len(bad_phone)}",
        )
    )

    # E8 (NEW): URL check — no HTTP/HTTPS links in cleaned chunks
    #    Failure: URL = internal portal link or broken link candidate
    #    Severity: warn (broken links degrade retrieval quality but don't corrupt logic)
    _URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
    bad_url = [
        r for r in cleaned_rows
        if _URL_PATTERN.search((r.get("chunk_text") or "").lower())
    ]
    ok8 = len(bad_url) == 0
    results.append(
        ExpectationResult(
            "no_url_in_cleaned",
            ok8,
            "warn",
            f"url_count={len(bad_url)}",
        )
    )

    # E9 (NEW): Chunk max length — detect oversized chunks (likely PDF parser garbage)
    #    Failure: chunk > 2000 chars = parsing artifact, not useful content
    #    Severity: warn
    _MAX_CHUNK_LEN = 2000
    oversized = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) > _MAX_CHUNK_LEN]
    ok9 = len(oversized) == 0
    results.append(
        ExpectationResult(
            "chunk_max_length_2000",
            ok9,
            "warn",
            f"oversized_chunks={len(oversized)}",
        )
    )

    # E10 (NEW): Email PII check — no email addresses in cleaned
    #    Failure: email address = internal staff contact leaked
    #    Severity: halt
    _EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", re.IGNORECASE)
    bad_email = [
        r for r in cleaned_rows
        if _EMAIL_PATTERN.search((r.get("chunk_text") or "").lower())
    ]
    ok10 = len(bad_email) == 0
    results.append(
        ExpectationResult(
            "no_email_pii_in_cleaned",
            ok10,
            "halt",
            f"email_pii_count={len(bad_email)}",
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
