"""
CV Processing Worker
Runs as a separate process/thread, polls the operations queue for pending tasks.
For Phase 1 MVP, implements simple polling-based task queue without requiring Celery/Redis.
"""
import time
import threading
import asyncio
import os
import json
import re
import hashlib
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.core.config import settings
from app.core.logging import get_logger
from app.services.document_processor import document_processor, DocumentType
from app.services.llm_client import llm_client, LLMError
from app.services.matching import matching_engine
from app.services.redaction import redact_text
from app.services.ai_config import (
    get_active_runtime, hydrate_runtime_secret, runtime_context, runtime_snapshot,
)
from datetime import datetime

logger = get_logger(__name__)

# Processing queue polling interval (seconds)
POLL_INTERVAL_SECONDS = 5
HEARTBEAT_SECONDS = 20


class LostOwnership(RuntimeError):
    """The connection or fencing token for an operation was lost."""


class FencedSession(Session):
    """Keep all worker writes on the connection holding its advisory lock.

    A SQLAlchemy Connection can transparently reconnect after an invalidation.
    Before every commit, check both its backend PID and its attempt token so a
    reconnected or superseded worker cannot commit stale results.
    """
    def assert_ownership(self):
        owner = self.info.get("owner")
        if not owner:
            return
        try:
            row = self.execute(text("""
                SELECT pg_backend_pid() AS pid, worker_token::text AS token
                FROM app_private.operations WHERE operation_id = :operation_id
            """), {"operation_id": owner["operation_id"]}).mappings().first()
        except Exception as exc:
            raise LostOwnership("Cannot verify worker ownership") from exc
        if not row or row["pid"] != owner["pid"] or row["token"] != owner["token"]:
            raise LostOwnership("Worker no longer owns this operation")

    def commit(self):
        self.assert_ownership()
        return super().commit()


class ProcessingWorker:
    def __init__(self):
        self.running = False
        self.thread = None
        # Continue past a page of live advisory locks on the next poll. Without
        # this cursor, 100 long-running older jobs could starve newer jobs.
        self._queue_cursor = None
        self._ensure_storage_dirs()

    def _ensure_storage_dirs(self):
        """Create local storage directories if using local storage backend"""
        if settings.STORAGE_BACKEND == "local":
            os.makedirs(os.path.join(settings.LOCAL_STORAGE_PATH, "cv-originals"), exist_ok=True)
            os.makedirs(os.path.join(settings.LOCAL_STORAGE_PATH, "cv-extracted-text"), exist_ok=True)

    def start(self):
        """Start worker in background thread"""
        if self.running:
            logger.warning("Worker already running")
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Processing worker started")

    def stop(self):
        """Stop worker gracefully"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("Processing worker stopped")

    def _run_loop(self):
        """Main worker loop - polls for pending operations"""
        logger.info("Worker entering run loop")
        while self.running:
            try:
                self._process_pending_operations()
            except Exception as e:
                logger.error("Error in worker loop", error_type=type(e).__name__)
            time.sleep(POLL_INTERVAL_SECONDS)

    def _heartbeat(self, operation_id: str, token: str, stop: threading.Event):
        """Health signal only, never a lease that can steal a live worker's job."""
        while not stop.wait(HEARTBEAT_SECONDS):
            db = SessionLocal()
            try:
                db.execute(text("""
                    UPDATE app_private.operations SET heartbeat_at = NOW()
                    WHERE operation_id = :id AND worker_token = :token AND status = 'PROCESSING'
                """), {"id": operation_id, "token": token})
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning("Worker heartbeat failed", operation_id=operation_id, error_type=type(exc).__name__)
            finally:
                db.close()

    def _process_pending_operations(self):
        """Claim one pending or abandoned operation without stealing live work.

        A session-level PostgreSQL advisory lock is held by the *same dedicated
        database connection* used for every handler transaction. PostgreSQL
        releases it when the worker process/connection dies. Heartbeat age alone
        never authorises a takeover. Existing pre-fencing workers must be drained
        before deploying this code.
        """
        connection = engine.connect()
        db = FencedSession(bind=connection, autoflush=False)
        operation_id = None
        lock_owned = False
        heartbeat_stop = threading.Event()
        heartbeat = None
        context_token = None
        try:
            cursor_filter = "" if self._queue_cursor is None else (
                "AND (created_at, operation_id) > (:cursor_time, CAST(:cursor_id AS uuid))"
            )
            cursor_params = {} if self._queue_cursor is None else {
                "cursor_time": self._queue_cursor[0], "cursor_id": str(self._queue_cursor[1])
            }
            rows = db.execute(text(f"""
                SELECT operation_id, capability, status, ai_config_id, ai_config_snapshot, created_at
                FROM app_private.operations
                WHERE status IN ('PENDING', 'PROCESSING')
                  AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING')
                  {cursor_filter}
                ORDER BY created_at, operation_id
                LIMIT 100 FOR UPDATE SKIP LOCKED
            """), cursor_params).mappings().all()
            chosen = None
            for row in rows:
                got_lock = db.execute(text("""
                    SELECT pg_try_advisory_lock(hashtextextended(:id, 418630021))
                """), {"id": str(row["operation_id"])}).scalar_one()
                if got_lock:
                    chosen = row
                    lock_owned = True
                    operation_id = str(row["operation_id"])
                    break
            if not chosen:
                self._queue_cursor = (rows[-1]["created_at"], rows[-1]["operation_id"]) if rows else None
                db.rollback()
                return
            self._queue_cursor = None

            capability, was_processing = chosen["capability"], chosen["status"] == "PROCESSING"
            token = str(uuid4())
            backend_pid = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            runtime = chosen["ai_config_snapshot"] or get_active_runtime(db)
            if chosen["ai_config_snapshot"]:
                # Snapshots are public (no provider secret). Rehydrate the
                # pinned version's key in memory only; it is never written
                # back into ai_config_snapshot below.
                runtime = hydrate_runtime_secret(db, runtime)
            snapshot = runtime_snapshot(runtime)
            db.execute(text("""
                UPDATE app_private.operations
                SET status = 'PROCESSING', started_at = COALESCE(started_at, NOW()),
                    attempt_started_at = NOW(), heartbeat_at = NOW(), worker_token = :token,
                    attempt_count = attempt_count + 1,
                    recovery_count = recovery_count + CASE WHEN :recovered THEN 1 ELSE 0 END,
                    ai_config_id = :config_id, ai_config_snapshot = CAST(:snapshot AS jsonb),
                    error_code = NULL, error_message = NULL
                WHERE operation_id = :operation_id
            """), {"operation_id": operation_id, "token": token, "recovered": was_processing,
                    "config_id": runtime.get("config_id"), "snapshot": json.dumps(snapshot)})
            if was_processing:
                db.execute(text("""
                    INSERT INTO app_private.operation_recovery_events(operation_id) VALUES (:operation_id)
                """), {"operation_id": operation_id})
            db.commit()
            context_token = runtime_context.set(runtime)
            db.info["owner"] = {"operation_id": operation_id, "pid": backend_pid, "token": token}
            logger.info("Worker claimed operation", operation_id=operation_id, capability=capability, recovered=was_processing)
            heartbeat = threading.Thread(target=self._heartbeat, args=(operation_id, token, heartbeat_stop), daemon=True)
            heartbeat.start()

            try:
                if was_processing:
                    # Only this fenced owner may reset unfinished child work.
                    db.execute(text("""
                        UPDATE app_private.assessment_runs SET status = 'FAILED', completed_at = NOW()
                        WHERE operation_id = :operation_id AND status = 'PROCESSING'
                    """), {"operation_id": operation_id})
                    if capability == "CV_PROCESSING":
                        db.execute(text("""
                            UPDATE app_private.application_documents d
                            SET file_processing_status = 'RECEIVED', processing_error = NULL
                            FROM app_private.cv_batch_items bi
                            JOIN app_private.cv_batches b ON b.batch_id = bi.batch_id
                            WHERE b.operation_id = :operation_id AND d.application_id = bi.application_id
                              AND d.file_processing_status = 'PROCESSING'
                        """), {"operation_id": operation_id})
                    db.commit()

                if capability == "CV_PROCESSING":
                    self._process_cv_batch(UUID(operation_id), db)
                elif capability == "ASSESSMENT":
                    self._run_assessments(UUID(operation_id), db)
                else:
                    self._generate_ranking(UUID(operation_id), db)

                db.execute(text("""
                    UPDATE app_private.operations SET status = 'COMPLETED', completed_at = NOW(), heartbeat_at = NOW()
                    WHERE operation_id = :operation_id AND worker_token = :token
                """), {"operation_id": operation_id, "token": token})
                db.commit()
                logger.info("Operation completed successfully", operation_id=operation_id)
            except LostOwnership:
                db.rollback()
                logger.warning("Worker lost operation ownership; no further writes", operation_id=operation_id)
            except Exception as exc:
                logger.error("Operation failed", operation_id=operation_id, error_type=type(exc).__name__)
                db.rollback()
                # A connection may have been replaced after the original error.
                # Refuse even the failure write when this worker is no longer owner.
                try:
                    db.assert_ownership()
                    if capability == "CV_PROCESSING":
                        db.execute(text("""
                            UPDATE app_private.application_documents d
                            SET file_processing_status = 'NEEDS_HR_REVIEW', processing_error = 'Lô xử lý thất bại'
                            FROM app_private.cv_batch_items bi JOIN app_private.cv_batches b ON b.batch_id = bi.batch_id
                            WHERE b.operation_id = :operation_id AND bi.application_id = d.application_id
                              AND d.file_processing_status IN ('RECEIVED', 'PROCESSING')
                        """), {"operation_id": operation_id})
                        db.execute(text("""
                            UPDATE app_private.cv_batches SET status = 'FAILED', completed_at = NOW()
                            WHERE operation_id = :operation_id AND status = 'PROCESSING'
                        """), {"operation_id": operation_id})
                    db.execute(text("""
                        UPDATE app_private.operations
                        SET status = 'FAILED', error_code = 'PROCESSING_ERROR',
                            error_message = 'Không thể xử lý tác vụ; vui lòng kiểm tra và thử lại.', completed_at = NOW()
                        WHERE operation_id = :operation_id AND worker_token = :token
                    """), {"operation_id": operation_id, "token": token})
                    db.commit()
                except LostOwnership:
                    db.rollback()
                    logger.warning("Worker could not record failure after losing ownership", operation_id=operation_id)
        finally:
            heartbeat_stop.set()
            if context_token is not None:
                runtime_context.reset(context_token)
            if heartbeat:
                heartbeat.join(timeout=2)
            db.info.pop("owner", None)
            db.close()  # rollback any unfinished transaction before unlocking
            if lock_owned:
                try:
                    connection.execute(text("SELECT pg_advisory_unlock(hashtextextended(:id, 418630021))"),
                                       {"id": operation_id})
                    connection.commit()
                except Exception:
                    # Never return a session with a possibly-held advisory lock
                    # to the pool. A broken connection is discarded instead.
                    connection.invalidate()
            connection.close()

    def _read_file_content(self, document) -> bytes:
        """Read file content from configured storage backend"""
        bucket = document["bucket"]
        storage_path = document["storage_path"]

        if settings.STORAGE_BACKEND == "local":
            full_path = os.path.join(settings.LOCAL_STORAGE_PATH, bucket, storage_path)
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"File not found at path: {full_path}")
            with open(full_path, "rb") as f:
                return f.read()
        elif settings.STORAGE_BACKEND == "supabase":
            from app.db.supabase import get_supabase_client
            supabase = get_supabase_client()
            if not supabase:
                raise RuntimeError("Supabase client is not configured")
            response = supabase.storage.from_(bucket).download(storage_path)
            return response
        else:
            raise ValueError(f"Unknown storage backend: {settings.STORAGE_BACKEND}")

    def _save_extracted_text(self, application_id: str, document_id: str, full_text: str, pages: list, attempt_token: str) -> str:
        """Persist extracted text in the configured backend so assessment can read it."""
        bucket = settings.SUPABASE_STORAGE_BUCKET_EXTRACTED
        application_id, document_id = str(application_id), str(document_id)
        relative_path = f"{application_id}/{document_id}/{attempt_token}/extracted.txt"
        pages_path = f"{application_id}/{document_id}/{attempt_token}/pages.json"
        if settings.STORAGE_BACKEND == "local":
            full_dir = os.path.join(settings.LOCAL_STORAGE_PATH, bucket, application_id, document_id, attempt_token)
            os.makedirs(full_dir, exist_ok=True)
            with open(os.path.join(settings.LOCAL_STORAGE_PATH, bucket, relative_path), "w", encoding="utf-8") as f:
                f.write(full_text)
            with open(os.path.join(settings.LOCAL_STORAGE_PATH, bucket, pages_path), "w", encoding="utf-8") as f:
                json.dump(pages, f, ensure_ascii=False)
        elif settings.STORAGE_BACKEND == "supabase":
            from app.db.supabase import get_supabase_client
            supabase = get_supabase_client()
            if not supabase:
                raise RuntimeError("Supabase storage is not configured")
            supabase.storage.from_(bucket).upload(relative_path, full_text.encode("utf-8"),
                                                   {"content-type": "text/plain; charset=utf-8", "upsert": "true"})
            supabase.storage.from_(bucket).upload(pages_path, json.dumps(pages, ensure_ascii=False).encode("utf-8"),
                                                   {"content-type": "application/json", "upsert": "true"})
        else:
            raise ValueError(f"Unknown storage backend: {settings.STORAGE_BACKEND}")
        return relative_path

    def _load_extracted_text(self, path: str) -> str:
        if not path:
            raise FileNotFoundError("No extracted text path is recorded")
        if settings.STORAGE_BACKEND == "local":
            with open(os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_EXTRACTED, path), encoding="utf-8") as f:
                return f.read()
        if settings.STORAGE_BACKEND == "supabase":
            from app.db.supabase import get_supabase_client
            supabase = get_supabase_client()
            if not supabase:
                raise RuntimeError("Supabase storage is not configured")
            return supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET_EXTRACTED).download(path).decode("utf-8")
        raise ValueError(f"Unknown storage backend: {settings.STORAGE_BACKEND}")

    def _process_cv_batch(self, operation_id: UUID, db):
        """Process all documents in a CV batch: extract text, extract profile, detect duplicates"""
        from sqlalchemy import text

        # Get batch ID for this operation
        batch_result = db.execute(text("""
            SELECT batch_id, position_id FROM app_private.cv_batches WHERE operation_id = :operation_id
        """), {"operation_id": str(operation_id)})
        batch_row = batch_result.fetchone()
        if not batch_row:
            raise Exception(f"No batch found for operation {operation_id}")

        batch_id, position_id = batch_row

        # Get all documents for applications in this batch (status RECEIVED)
        docs_result = db.execute(text("""
            SELECT d.document_id, d.application_id, d.bucket, d.storage_path,
                   d.original_filename, d.mime_type, d.size_bytes,
                   a.created_by
            FROM app_private.application_documents d
            JOIN app_private.applications a ON d.application_id = a.application_id
            JOIN app_private.cv_batch_items bi ON bi.application_id = a.application_id
            WHERE bi.batch_id = :batch_id
              AND d.file_processing_status = 'RECEIVED'
        """), {"batch_id": str(batch_id)})

        documents = [dict(zip(["document_id", "application_id", "bucket", "storage_path",
                               "original_filename", "mime_type", "size_bytes", "created_by"], row))
                     for row in docs_result.fetchall()]

        logger.info("Processing documents in batch", batch_id=batch_id, count=len(documents))

        processed_count = 0
        needs_review_count = 0
        extracted_texts = {}

        for doc in documents:
            document_id = doc["document_id"]
            application_id = doc["application_id"]
            loop = asyncio.new_event_loop()

            try:
                # Update document status to PROCESSING
                db.execute(text("""
                    UPDATE app_private.application_documents
                    SET file_processing_status = 'PROCESSING'
                    WHERE document_id = :document_id
                """), {"document_id": document_id})
                db.commit()

                # Read file
                content = self._read_file_content(doc)

                # Process document: extract text
                raw_text, raw_pages, doc_type = loop.run_until_complete(
                    document_processor.process_document(content, doc["original_filename"], doc["mime_type"])
                )
                # Identity is extracted locally, never sent to the model.  The
                # stored/model text and the evidence verifier use exactly the
                # same minimised text, including for later re-assessments.
                email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw_text)
                phone_match = re.search(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)", raw_text)
                full_text = redact_text(raw_text, detect_first_line_name=True)
                # Never persist OCR diagnostic fields, which can contain raw text.
                pages = [{"page_number": page.get("page_number"),
                          "content": redact_text(page.get("content") or "", detect_first_line_name=True)}
                         for page in raw_pages]

                # Save minimised extracted text
                db.assert_ownership()
                extracted_path = self._save_extracted_text(application_id, document_id, full_text, pages,
                                                           db.info["owner"]["token"])

                # Update document processing run
                db.execute(text("""
                    UPDATE app_private.document_processing_runs
                    SET status = 'COMPLETED',
                        extraction_type = :extraction_type,
                        processor_version = 'v1.0',
                        extracted_text_storage_path = :extracted_path
                    WHERE document_id = :document_id
                """), {
                    "document_id": document_id,
                    "extraction_type": doc_type.value,
                    "extracted_path": extracted_path
                })

                # Update document status to COMPLETED
                db.execute(text("""
                    UPDATE app_private.application_documents
                    SET file_processing_status = 'COMPLETED'
                    WHERE document_id = :document_id
                """), {"document_id": document_id})

                extracted_texts[application_id] = (full_text, pages, document_id)

                # Run profile extraction via LLM
                try:
                    candidate_profile = loop.run_until_complete(
                        llm_client.extract_candidate_profile(
                            cv_text=full_text,
                            candidate_identifier=str(application_id)
                        )
                    )

                    provider_metadata = candidate_profile.pop("_provider_metadata", {})
                    profile_prompt_version = candidate_profile.pop(
                        "_prompt_version", settings.PROFILE_PROMPT_VERSION)
                    extraction_config = {
                        "prompt_version": profile_prompt_version,
                        "provider_metadata": provider_metadata,
                        "cv_text_sha256": hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
                        "extractor": "llm-profile",
                    }
                    # Create profile version
                    profile_ver_result = db.execute(text("""
                        INSERT INTO app_private.profile_versions
                        (application_id, source_document_id, version_number, extraction_config, status, created_at)
                        VALUES
                        (:application_id, :document_id, 1, CAST(:extraction_config AS jsonb), 'COMPLETED', NOW())
                        RETURNING profile_version_id
                    """), {"application_id": application_id, "document_id": document_id,
                            "extraction_config": json.dumps(extraction_config)})
                    profile_version_id = profile_ver_result.fetchone()[0]

                    # Extract basic contact signals locally; never infer a name from the
                    # opaque candidate_identifier returned by the model.
                    display_name = os.path.splitext(doc["original_filename"])[0]
                    email = email_match.group(0).lower() if email_match else None
                    phone = re.sub(r"\D", "", phone_match.group(0)) if phone_match else None

                    # Insert profile facts
                    facts = []
                    for edu in candidate_profile.get("education", []):
                        facts.append({
                            "profile_version_id": profile_version_id,
                            "fact_type": "EDUCATION",
                            "fact_value": json.dumps(edu),
                            "source_page_number": edu.get("page_number"),
                            "confidence": 0.9
                        })
                    for work in candidate_profile.get("work_history", []):
                        facts.append({
                            "profile_version_id": profile_version_id,
                            "fact_type": "WORK_EXPERIENCE",
                            "fact_value": json.dumps(work),
                            "source_page_number": work.get("page_number"),
                            "confidence": 0.9
                        })
                    for skill in candidate_profile.get("skills", []):
                        facts.append({
                            "profile_version_id": profile_version_id,
                            "fact_type": "SKILL",
                            "fact_value": json.dumps({"name": skill}),
                            "source_page_number": None,
                            "confidence": 0.85
                        })
                    for cert in candidate_profile.get("certifications", []):
                        facts.append({
                            "profile_version_id": profile_version_id,
                            "fact_type": "CERTIFICATION",
                            "fact_value": json.dumps(cert),
                            "source_page_number": cert.get("page_number"),
                            "confidence": 0.85
                        })

                    for section, fact_type in (("languages", "LANGUAGE"), ("projects", "PROJECT")):
                        for item in candidate_profile.get(section, []):
                            value = {"name": item} if isinstance(item, str) else item
                            facts.append({
                                "profile_version_id": profile_version_id,
                                "fact_type": fact_type,
                                "fact_value": json.dumps(value),
                                "source_page_number": value.get("page_number"),
                                "confidence": 0.85,
                            })

                    if facts:
                        for fact in facts:
                            db.execute(text("""
                                INSERT INTO app_private.profile_facts
                                (profile_version_id, fact_type, fact_value, source_page_number, confidence)
                                VALUES
                                (:profile_version_id, :fact_type, CAST(:fact_value AS jsonb), :source_page_number, :confidence)
                            """), fact)

                    # Update application identity
                    db.execute(text("""
                        UPDATE app_private.application_identities
                        SET display_name = :display_name, email = :email, phone = :phone, updated_at = NOW()
                        WHERE application_id = :application_id
                    """), {
                        "application_id": application_id,
                        "display_name": display_name, "email": email, "phone": phone
                    })

                    db.commit()

                except LLMError as e:
                    logger.error("Profile extraction failed, marking for HR review",
                                application_id=application_id, error_type=type(e).__name__)
                    db.rollback()
                    db.execute(text("""
                        UPDATE app_private.application_documents
                        SET file_processing_status = 'NEEDS_HR_REVIEW', processing_error = :error
                        WHERE document_id = :document_id
                    """), {"document_id": document_id, "error": "Không thể trích xuất hồ sơ; HR cần kiểm tra"})
                    needs_review_count += 1
                    db.execute(text("UPDATE app_private.cv_batches SET failed_files = failed_files + 1 WHERE batch_id = :batch_id"), {"batch_id": batch_id})
                    db.commit()
                    loop.close()
                    continue

                processed_count += 1
                db.execute(text("UPDATE app_private.cv_batches SET processed_files = processed_files + 1 WHERE batch_id = :batch_id"), {"batch_id": batch_id})
                db.commit()
                loop.close()

            except LostOwnership:
                db.rollback()
                loop.close()
                raise
            except Exception as e:
                logger.error("Document processing failed", document_id=document_id, error_type=type(e).__name__)
                db.rollback()
                db.execute(text("""
                    UPDATE app_private.application_documents
                    SET file_processing_status = 'NEEDS_HR_REVIEW', processing_error = :error
                    WHERE document_id = :document_id
                """), {"document_id": document_id, "error": "Không thể xử lý tài liệu; HR cần kiểm tra"})
                needs_review_count += 1
                db.execute(text("UPDATE app_private.cv_batches SET failed_files = failed_files + 1 WHERE batch_id = :batch_id"), {"batch_id": batch_id})
                db.commit()
                loop.close()

        # Reconcile durable document and validation states after a crash. This
        # also resumes assessment if all documents completed in a prior attempt.
        counts = db.execute(text("""
            SELECT COUNT(*) FILTER (WHERE bi.validation_result = 'ACCEPTED' AND EXISTS (
                       SELECT 1 FROM app_private.application_documents d
                       WHERE d.application_id = bi.application_id AND d.file_processing_status = 'COMPLETED')) AS processed,
                   COUNT(*) FILTER (WHERE bi.validation_result = 'ERROR' OR EXISTS (
                       SELECT 1 FROM app_private.application_documents d WHERE d.application_id = bi.application_id
                         AND d.file_processing_status IN ('NEEDS_HR_REVIEW', 'ERROR_UNSUPPORTED'))) AS failed
            FROM app_private.cv_batch_items bi WHERE bi.batch_id = :batch_id
        """), {"batch_id": str(batch_id)}).mappings().one()
        processed_count, failed_count = int(counts["processed"]), int(counts["failed"])
        db.execute(text("""
            UPDATE app_private.cv_batches
            SET processed_files = :processed, failed_files = :failed,
                status = CASE WHEN :failed = 0 THEN 'COMPLETED' ELSE 'PARTIALLY_COMPLETED' END,
                completed_at = NOW()
            WHERE batch_id = :batch_id
        """), {"batch_id": str(batch_id), "processed": processed_count, "failed": failed_count})
        db.commit()
        logger.info("Batch processing complete", batch_id=batch_id, processed=processed_count, needs_review=failed_count)

        if processed_count:
            criteria_result = db.execute(text("""
                SELECT 1 FROM app_private.criteria_versions
                WHERE position_id = :position_id AND status = 'APPROVED' LIMIT 1
            """), {"position_id": str(position_id)})
            if criteria_result.first():
                # Finish both steps before completing the same operation; polling
                # callers therefore cannot mistake an extraction-only result for a ranking.
                self._run_assessments(operation_id, db)

    def _operation_position(self, operation_id: UUID, db) -> str:
        position_id = db.execute(text("SELECT position_id FROM app_private.operations WHERE operation_id = :operation_id"),
                                 {"operation_id": str(operation_id)}).scalar_one_or_none()
        if not position_id:
            raise RuntimeError("Operation has no associated position; cannot process safely")
        return str(position_id)

    def _run_assessments(self, operation_id: UUID, db):
        """Assess only the position explicitly associated with this operation."""
        position_id = self._operation_position(operation_id, db)
        cv = db.execute(text("""
            SELECT criteria_version_id, jd_version_id, mandatory_weight_total, nice_to_have_weight_total
            FROM app_private.criteria_versions WHERE position_id = :position_id AND status = 'APPROVED'
              AND jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :position_id ORDER BY version_number DESC LIMIT 1)
            ORDER BY version_number DESC LIMIT 1
        """), {"position_id": position_id}).mappings().first()
        if not cv:
            raise RuntimeError("Không có bộ tiêu chí đã duyệt cho vị trí này")
        criteria_version_id = str(cv["criteria_version_id"])
        criteria_rows = db.execute(text("""
            SELECT criterion_id, name, description, category, weight_in_group, expected_evidence_keywords
            FROM app_private.criteria_items WHERE criteria_version_id = :criteria_version_id ORDER BY display_order
        """), {"criteria_version_id": criteria_version_id}).mappings().all()
        criteria_items = [{**dict(row), "criterion_id": str(row["criterion_id"]),
                           "weight_in_group": float(row["weight_in_group"])} for row in criteria_rows]
        if not criteria_items:
            raise RuntimeError("Bộ tiêu chí đã duyệt không có tiêu chí nào")

        applications = db.execute(text("""
            SELECT DISTINCT ON (a.application_id) a.application_id, d.document_id,
                   processing.extracted_text_storage_path, profile.profile_version_id
            FROM app_private.applications a
            JOIN app_private.application_documents d ON d.application_id = a.application_id
            LEFT JOIN LATERAL (
                SELECT extracted_text_storage_path FROM app_private.document_processing_runs
                WHERE document_id = d.document_id AND status = 'COMPLETED'
                ORDER BY created_at DESC LIMIT 1
            ) processing ON TRUE
            LEFT JOIN LATERAL (
                SELECT profile_version_id FROM app_private.profile_versions
                WHERE application_id = a.application_id AND status = 'COMPLETED'
                ORDER BY version_number DESC LIMIT 1
            ) profile ON TRUE
            WHERE a.position_id = :position_id AND d.document_type = 'CV'
              AND d.file_processing_status = 'COMPLETED'
              AND a.application_status IN ('NEW', 'IN_REVIEW', 'SHORTLIST')
            ORDER BY a.application_id, d.created_at DESC
        """), {"position_id": position_id, "criteria_version_id": criteria_version_id}).mappings().all()
        failed_count = 0
        loop = asyncio.new_event_loop()
        try:
            for app in applications:
                application_id, document_id = str(app["application_id"]), str(app["document_id"])
                assessment_id = None
                try:
                    if not app["profile_version_id"] or not app["extracted_text_storage_path"]:
                        raise RuntimeError("Thiếu hồ sơ trích xuất hoặc văn bản CV")
                    # Old extracted files may predate minimisation. Redact again
                    # before both the AI call and exact-quote verification.
                    cv_text = redact_text(self._load_extracted_text(app["extracted_text_storage_path"]),
                                          detect_first_line_name=True)
                    facts = db.execute(text("""
                        SELECT fact_type, fact_value FROM app_private.profile_facts
                        WHERE profile_version_id = :profile_version_id
                    """), {"profile_version_id": str(app["profile_version_id"])}).mappings().all()
                    candidate_profile = {
                        "candidate_identifier": application_id,
                        "total_years_experience": 0,
                        "education": [f["fact_value"] for f in facts if f["fact_type"] == "EDUCATION"],
                        "work_history": [f["fact_value"] for f in facts if f["fact_type"] == "WORK_EXPERIENCE"],
                        "skills": [f["fact_value"].get("name") for f in facts if f["fact_type"] == "SKILL"],
                        "certifications": [f["fact_value"] for f in facts if f["fact_type"] == "CERTIFICATION"],
                        "languages": [f["fact_value"] for f in facts if f["fact_type"] == "LANGUAGE"],
                        "projects": [f["fact_value"] for f in facts if f["fact_type"] == "PROJECT"],
                    }
                    runtime_public = runtime_snapshot(runtime_context.get() or {})
                    fingerprint_payload = {
                        "version": "assessment-fingerprint-v1",
                        "application_id": application_id,
                        "position_id": position_id,
                        "jd_version_id": str(cv["jd_version_id"]),
                        "criteria_version_id": criteria_version_id,
                        "rubric": criteria_items,
                        "profile_version_id": str(app["profile_version_id"]),
                        "profile_facts": sorted(
                            ({"fact_type": f["fact_type"], "fact_value": f["fact_value"]} for f in facts),
                            key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False, default=str),
                        ),
                        "cv_text_sha256": hashlib.sha256(cv_text.encode("utf-8")).hexdigest(),
                        "ai_runtime": runtime_public,
                        "llm_seed": settings.LLM_SEED,
                        "prompt_version": settings.MATCHING_PROMPT_VERSION,
                        "matching_policy_version": matching_engine.POLICY_VERSION,
                        "deterministic_rules_version": settings.DETERMINISTIC_RULES_VERSION,
                    }
                    assessment_fingerprint = hashlib.sha256(json.dumps(
                        fingerprint_payload, sort_keys=True, ensure_ascii=False, default=str
                    ).encode("utf-8")).hexdigest()
                    existing_assessment = db.execute(text("""
                        SELECT assessment_id FROM app_private.assessment_runs
                        WHERE assessment_fingerprint = :fingerprint AND status = 'COMPLETED'
                        LIMIT 1
                    """), {"fingerprint": assessment_fingerprint}).scalar_one_or_none()
                    if existing_assessment:
                        continue
                    provider_snapshot = {
                        "runtime": runtime_public,
                        "provider_returned_model": None,
                        "system_fingerprint": None,
                    }
                    assessment_id = db.execute(text("""
                        INSERT INTO app_private.assessment_runs
                            (position_id, application_id, jd_version_id, criteria_version_id, profile_version_id,
                             policy_version, operation_id, ai_config_id, status, assessment_fingerprint,
                             matching_policy_version, prompt_version, provider_model_snapshot)
                        VALUES (:position_id, :application_id, :jd_version_id, :criteria_version_id,
                                :profile_version_id, :policy_version, :operation_id, :ai_config_id, 'PROCESSING',
                                :fingerprint, :matching_policy_version, :prompt_version,
                                CAST(:provider_snapshot AS jsonb))
                        RETURNING assessment_id
                    """), {"position_id": position_id, "application_id": application_id,
                            "jd_version_id": str(cv["jd_version_id"]), "criteria_version_id": criteria_version_id,
                            "profile_version_id": str(app["profile_version_id"]),
                            "policy_version": settings.ASSESSMENT_POLICY_VERSION,
                            "operation_id": str(operation_id),
                            "ai_config_id": (runtime_context.get() or {}).get("config_id"),
                            "fingerprint": assessment_fingerprint,
                            "matching_policy_version": matching_engine.POLICY_VERSION,
                            "prompt_version": settings.MATCHING_PROMPT_VERSION,
                            "provider_snapshot": json.dumps(provider_snapshot)}).scalar_one()
                    db.commit()
                    findings = loop.run_until_complete(llm_client.match_criterion_evidence(
                        cv_text=cv_text, candidate_profile=candidate_profile, rubric=criteria_items,
                        candidate_identifier=application_id, rubric_version=criteria_version_id))
                    provider_metadata = findings.pop("_provider_metadata", {}) if isinstance(findings, dict) else {}
                    prompt_version = findings.pop("_prompt_version", settings.MATCHING_PROMPT_VERSION) if isinstance(findings, dict) else settings.MATCHING_PROMPT_VERSION
                    provider_snapshot.update(provider_metadata or {})
                    validated = []
                    for finding in matching_engine.canonicalize_findings(
                            criteria_items, findings.get("findings", []) if isinstance(findings, dict) else []):
                        evidence = finding.get("evidence") or {}
                        quote = evidence.get("verbatim_quote") or ""
                        span = matching_engine.find_quote_span(quote, cv_text)
                        verified = span is not None
                        finding["evidence_verified"] = verified
                        if verified:
                            quote = cv_text[span[0]:span[1]]
                            evidence["verbatim_quote"] = quote
                            evidence["position_in_text"] = span[0]
                        # Page numbers are verified against extracted page text;
                        # DOCX has no reliable page boundaries and remains unpaged.
                        pages = matching_engine.quote_pages(quote, cv_text) if verified else []
                        suggested_page = evidence.get("page_number")
                        evidence["page_number"] = suggested_page if suggested_page in pages else (pages[0] if pages else None)
                        finding["evidence"] = evidence
                        if not verified and finding.get("outcome") != "UNCLEAR":
                            finding["outcome"] = "UNCLEAR"
                            finding["requires_verification"] = True
                        validated.append(finding)
                    group_weights = {"MUST_HAVE": float(cv["mandatory_weight_total"]) / 100,
                                     "NICE_TO_HAVE": float(cv["nice_to_have_weight_total"]) / 100}
                    score, coverage, match_status, results, _ = matching_engine.calculate_assessment_scores(
                        criteria_items, validated, group_weights=group_weights)
                    db.execute(text("""
                        UPDATE app_private.assessment_runs
                        SET status = 'COMPLETED', matching_status = :matching_status, matching_score = :score,
                            evidence_coverage = :coverage, completed_at = NOW(),
                            prompt_version = :prompt_version,
                            provider_model_snapshot = CAST(:provider_snapshot AS jsonb)
                        WHERE assessment_id = :assessment_id
                    """), {"assessment_id": assessment_id, "matching_status": match_status,
                            "score": score, "coverage": coverage, "prompt_version": prompt_version,
                            "provider_snapshot": json.dumps(provider_snapshot)})
                    for result in results:
                        result_id = db.execute(text("""
                            INSERT INTO app_private.criterion_assessment_results
                                (assessment_id, criterion_id, outcome, score, confidence, confidence_band,
                                 requires_hr_verification, reasoning, decision_source, evidence_strength,
                                 evidence_chunk_id, rule_version)
                            VALUES (:assessment_id, :criterion_id, :outcome, :score, :confidence, :confidence_band,
                                    :requires_verification, :reasoning, :decision_source, :evidence_strength,
                                    :evidence_chunk_id, :rule_version) RETURNING result_id
                        """), {"assessment_id": assessment_id, "criterion_id": result["criterion_id"],
                                "outcome": result["outcome"],
                                "score": result.get("score"),
                                "confidence": result.get("confidence", 0),
                                "confidence_band": result.get("confidence_band", "LOW"),
                                "requires_verification": result.get("requires_verification", result["outcome"] == "UNCLEAR"),
                                "reasoning": result.get("reasoning"),
                                "decision_source": result.get("decision_source") or "LLM",
                                "evidence_strength": result.get("evidence_strength"),
                                "evidence_chunk_id": result.get("evidence_chunk_id"),
                                "rule_version": result.get("rule_version")}).scalar_one()
                        evidence = result.get("evidence") or {}
                        if evidence.get("verbatim_quote"):
                            db.execute(text("""
                                INSERT INTO app_private.evidence_items
                                    (criterion_result_id, source_document_id, verbatim_quote, page_number,
                                     position_in_text, verification_status)
                                VALUES (:result_id, :document_id, :quote, :page_number, :position_in_text,
                                        :verification_status)
                            """), {"result_id": result_id, "document_id": document_id,
                                    "quote": evidence["verbatim_quote"], "page_number": evidence.get("page_number"),
                                    "position_in_text": evidence.get("position_in_text"),
                                    "verification_status": "VERIFIED" if result.get("evidence_verified") else "FAILED"})
                    db.commit()
                except LostOwnership:
                    db.rollback()
                    raise
                except Exception as e:
                    db.rollback()
                    failed_count += 1
                    logger.error("Assessment failed for application", application_id=application_id, error_type=type(e).__name__)
                    if assessment_id:
                        db.execute(text("""
                            UPDATE app_private.assessment_runs SET status = 'FAILED', completed_at = NOW()
                            WHERE assessment_id = :assessment_id
                        """), {"assessment_id": assessment_id})
                        db.commit()
        finally:
            loop.close()
        if failed_count:
            raise RuntimeError(f"Không thể đánh giá {failed_count} hồ sơ. Vui lòng kiểm tra kết nối AI và thử lại.")
        # Use the same operation id: completion now guarantees ranking is ready.
        self._generate_ranking(operation_id, db, criteria_version_id=criteria_version_id)

    def _generate_ranking(self, operation_id: UUID, db, criteria_version_id: Optional[str] = None):
        """Generate a snapshot for one position and one approved rubric version."""
        position_id = self._operation_position(operation_id, db)
        if criteria_version_id is None:
            criteria_version_id = db.execute(text("""
                SELECT criteria_version_id FROM app_private.criteria_versions
                WHERE position_id = :position_id AND status = 'APPROVED'
                  AND jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :position_id ORDER BY version_number DESC LIMIT 1)
                ORDER BY version_number DESC LIMIT 1
            """), {"position_id": position_id}).scalar_one_or_none()
        if not criteria_version_id:
            raise RuntimeError("Không có bộ tiêu chí đã duyệt để xếp hạng")
        already_published = db.execute(text("""
            SELECT 1 FROM app_private.ranking_runs r
            WHERE r.operation_id = :operation_id AND r.status = 'COMPLETED'
              AND NOT EXISTS (SELECT 1 FROM app_private.assessment_runs a
                  WHERE a.operation_id = :operation_id AND a.status = 'COMPLETED' AND a.completed_at > r.created_at)
            LIMIT 1
        """), {"operation_id": str(operation_id)}).first()
        if already_published:
            return
        rows = db.execute(text("""
            SELECT DISTINCT ON (a.application_id) a.application_id, i.display_name, ar.assessment_id,
                   ar.matching_status, ar.matching_score, ar.evidence_coverage
            FROM app_private.applications a
            LEFT JOIN app_private.application_identities i ON i.application_id = a.application_id
            JOIN app_private.assessment_runs ar ON ar.application_id = a.application_id
            WHERE a.position_id = :position_id AND a.application_status IN ('NEW', 'IN_REVIEW', 'SHORTLIST')
              AND ar.status = 'COMPLETED' AND ar.criteria_version_id = :criteria_version_id
              AND ar.profile_version_id = (SELECT profile_version_id FROM app_private.profile_versions
                    WHERE application_id = a.application_id AND status = 'COMPLETED' ORDER BY version_number DESC LIMIT 1)
            ORDER BY a.application_id, ar.created_at DESC, ar.assessment_id DESC
        """), {"position_id": position_id, "criteria_version_id": str(criteria_version_id)}).mappings().all()
        applications = [{"application_id": row["application_id"], "display_name": row["display_name"],
                         "latest_assessment": {"assessment_id": row["assessment_id"],
                             "matching_status": row["matching_status"], "matching_score": row["matching_score"],
                             "evidence_coverage": row["evidence_coverage"]}} for row in rows]
        ranked = matching_engine.rank_applications(applications, [])
        ranking_run_id = db.execute(text("""
            INSERT INTO app_private.ranking_runs
                (position_id, criteria_version_id, policy_version, operation_id, ai_config_id, status, completed_at)
            VALUES (:position_id, :criteria_version_id, 'v1.0', :operation_id, :ai_config_id, 'COMPLETED', NOW())
            RETURNING ranking_run_id
        """), {"position_id": position_id, "criteria_version_id": str(criteria_version_id),
                "operation_id": str(operation_id), "ai_config_id": (runtime_context.get() or {}).get("config_id")}).scalar_one()
        for item in ranked:
            assessment = item["latest_assessment"]
            db.execute(text("""
                INSERT INTO app_private.ranking_items
                    (ranking_run_id, position_id, application_id, assessment_id, rank_number,
                     ranking_status, matching_score, evidence_coverage)
                VALUES (:ranking_run_id, :position_id, :application_id, :assessment_id, :rank_number,
                        :ranking_status, :matching_score, :coverage)
            """), {"ranking_run_id": ranking_run_id, "position_id": position_id,
                    "application_id": item["application_id"], "assessment_id": assessment["assessment_id"],
                    "rank_number": item["rank_number"], "ranking_status": assessment["matching_status"],
                    "matching_score": assessment["matching_score"], "coverage": assessment["evidence_coverage"]})
        identity_rows = db.execute(text("""
            SELECT a.application_id, i.email, i.phone FROM app_private.applications a
            LEFT JOIN app_private.application_identities i ON i.application_id = a.application_id
            WHERE a.position_id = :position_id
        """), {"position_id": position_id}).mappings().all()
        identities = [{"application_id": row["application_id"], "identity": {"email": row["email"], "phone": row["phone"]}}
                      for row in identity_rows]
        for first, second, confidence, signal_type in matching_engine.detect_duplicates(identities):
            db.execute(text("""
                INSERT INTO app_private.duplicate_signals
                    (position_id, application_id_1, application_id_2, signal_type, confidence, detector_version)
                SELECT :position_id, :first, :second, :signal_type, :confidence, 'v1.0'
                WHERE NOT EXISTS (
                    SELECT 1 FROM app_private.duplicate_signals WHERE position_id = :position_id
                      AND signal_type = :signal_type
                      AND NOT (review_status = 'DISMISSED' AND COALESCE(detector_version, '') = 'identity-changed')
                      AND ((application_id_1 = :first AND application_id_2 = :second)
                           OR (application_id_1 = :second AND application_id_2 = :first))
                )
            """), {"position_id": position_id, "first": first, "second": second,
                    "signal_type": signal_type, "confidence": confidence})
        db.commit()
        logger.info("Ranking generated", position_id=position_id, ranking_run_id=ranking_run_id, count=len(ranked))


# Singleton worker instance
worker = ProcessingWorker()
