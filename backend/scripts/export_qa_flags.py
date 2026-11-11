#!/usr/bin/env python3
"""Export F2.04 QA flags as JSONL for the rule/prompt regression set.

Each row joins a reviewer flag with the assessed criterion: rubric item name
and category, AI outcome, the reviewer's expected outcome, flag type, rules
and model fingerprints.  Identifiers are UUIDs only; candidate identity is
never read.  Reviewer notes are redacted with ``redact_text``; evidence quotes
are excluded unless ``--include-redacted-quotes`` is passed.  Before writing,
the output is scanned for e-mail addresses and phone numbers and the export
is refused if any survive redaction.

Usage:
    python scripts/export_qa_flags.py --out qa_flags.jsonl [--position-id UUID]
        [--only-new] [--mark-exported] [--include-redacted-quotes]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.services.redaction import redact_text  # noqa: E402

_EMAIL = re.compile(r"(?i)[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+")
_PHONE = re.compile(r"(?<![\w\d])\+?\d[\d .()\-]{7,}\d(?![\w\d])")


def build_row(record: Mapping[str, Any], *, include_quotes: bool) -> dict[str, Any]:
    note = record.get("note")
    row = {
        "flag_id": str(record["flag_id"]),
        "flag_type": record["flag_type"],
        "position_id": str(record["position_id"]),
        "application_id": str(record["application_id"]),
        "assessment_id": str(record["assessment_id"]),
        "criterion_id": str(record["criterion_id"]) if record.get("criterion_id") else None,
        "criterion_name": record.get("criterion_name"),
        "criterion_category": record.get("category"),
        "ai_outcome": record.get("outcome"),
        "expected_outcome": record.get("expected_outcome"),
        "sample_reasons": list(record.get("reasons") or []),
        "sampling_rules_version": record.get("sampling_rules_version"),
        "note_redacted": redact_text(note) if note else None,
        "created_at": record["created_at"].isoformat() if hasattr(record.get("created_at"), "isoformat")
        else record.get("created_at"),
    }
    if include_quotes:
        quote = record.get("verbatim_quote")
        row["evidence_quote_redacted"] = redact_text(quote) if quote else None
        row["evidence_page_number"] = record.get("page_number")
    return row


FREE_TEXT_FIELDS = ("criterion_name", "note_redacted", "evidence_quote_redacted")


def find_pii(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return flag ids whose free-text fields still contain an e-mail or phone number."""
    leaking = []
    for row in rows:
        for field in FREE_TEXT_FIELDS:
            value = row.get(field)
            if isinstance(value, str) and (_EMAIL.search(value) or _PHONE.search(value)):
                leaking.append(str(row.get("flag_id")))
                break
    return leaking


def load_records(db, *, position_id: str | None, only_new: bool) -> list[dict[str, Any]]:
    return [dict(r) for r in db.execute(text("""
        SELECT f.flag_id, f.flag_type, f.expected_outcome, f.note, f.created_at,
               i.application_id, i.assessment_id, i.reasons,
               r.position_id, r.sampling_rules_version,
               cr.criterion_id, cr.outcome, ci.name AS criterion_name, ci.category,
               e.verbatim_quote, e.page_number
        FROM app_private.qa_flags f
        JOIN app_private.qa_sample_items i ON i.sample_item_id = f.sample_item_id
        JOIN app_private.qa_sample_runs r ON r.sample_run_id = i.sample_run_id
        LEFT JOIN app_private.criterion_assessment_results cr ON cr.result_id = f.criterion_result_id
        LEFT JOIN app_private.criteria_items ci ON ci.criterion_id = cr.criterion_id
        LEFT JOIN app_private.evidence_items e ON e.evidence_id = f.evidence_id
        WHERE (CAST(:position AS UUID) IS NULL OR r.position_id = CAST(:position AS UUID))
          AND (NOT :only_new OR f.exported_at IS NULL)
        ORDER BY f.created_at, f.flag_id
    """), {"position": position_id, "only_new": only_new}).mappings().all()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--position-id")
    parser.add_argument("--only-new", action="store_true", help="Skip flags exported before")
    parser.add_argument("--mark-exported", action="store_true", help="Set exported_at after writing")
    parser.add_argument("--include-redacted-quotes", action="store_true")
    args = parser.parse_args(argv)

    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        records = load_records(db, position_id=args.position_id, only_new=args.only_new)
        rows = [build_row(r, include_quotes=args.include_redacted_quotes) for r in records]
        leaking = find_pii(rows)
        if leaking:
            print(f"Refusing export: {len(leaking)} row(s) still contain e-mail/phone after redaction: "
                  f"{', '.join(leaking[:10])}", file=sys.stderr)
            return 2
        args.out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        if args.mark_exported and rows:
            db.execute(text("UPDATE app_private.qa_flags SET exported_at = NOW() WHERE flag_id = ANY(CAST(:ids AS UUID[]))"),
                       {"ids": [row["flag_id"] for row in rows]})
            db.commit()
        print(f"Exported {len(rows)} QA flag(s) to {args.out}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
