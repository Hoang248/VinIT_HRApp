#!/usr/bin/env python3
"""Register a trained LTR artifact as a DRAFT model version.

Registration never approves or activates a model.  An operator must
review the holdout metrics and explicitly update the row to APPROVED
before the worker may use it in ACTIVE mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.services.ltr import LTRModel  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", help="LTR artifact JSON written by train_ltr.py")
    args = parser.parse_args()

    raw = Path(args.artifact).read_bytes()
    artifact = json.loads(raw.decode("utf-8"))
    model = LTRModel.from_artifact(artifact)
    training = artifact.get("training") or {}
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO app_private.ltr_model_versions
                (model_version, artifact, metrics, feature_names, training_examples,
                 training_groups, data_sha256, status)
            VALUES (:model_version, CAST(:artifact AS jsonb), CAST(:metrics AS jsonb),
                    CAST(:feature_names AS jsonb), :training_examples, :training_groups,
                    :data_sha256, 'DRAFT')
            ON CONFLICT (model_version) DO NOTHING
        """), {
            "model_version": model.model_version,
            "artifact": json.dumps(artifact, ensure_ascii=False),
            "metrics": json.dumps(artifact.get("metrics") or {}, ensure_ascii=False),
            "feature_names": json.dumps(artifact.get("feature_names") or [], ensure_ascii=False),
            "training_examples": int(training.get("examples") or 0),
            "training_groups": int(training.get("groups") or 0),
            "data_sha256": training.get("data_sha256") or hashlib.sha256(raw).hexdigest(),
        })
        db.commit()
    finally:
        db.close()
    print(f"Registered LTR model {model.model_version} as DRAFT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
