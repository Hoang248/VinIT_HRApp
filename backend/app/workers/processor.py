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
from typing import Optional
from uuid import UUID
from sqlalchemy import text
from app.db.database import SessionLocal
from app.core.config import settings
from app.core.logging import get_logger
from app.services.document_processor import document_processor, DocumentType
from app.services.llm_client import llm_client, LLMError
from app.services.matching import matching_engine
from datetime import datetime

logger = get_logger(__name__)

# Processing queue polling interval (seconds)
POLL_INTERVAL_SECONDS = 5


class ProcessingWorker:
    def __init__(self):
        self.running = False
        self.thread = None
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
                logger.error("Error in worker loop", error=str(e), exc_info=True)
            time.sleep(POLL_INTERVAL_SECONDS)

    def _process_pending_operations(self):
        """Fetch and process pending operations one at a time"""
        db = SessionLocal()
        try:
            # Find oldest pending CV processing operation
            result = db.execute(text("""
                SELECT operation_id, capability
                FROM app_private.operations
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """))
            row = result.fetchone()

            if not row:
                return  # No work to do

            operation_id = row[0]
            capability = row[1]

            logger.info("Worker picked up operation", operation_id=operation_id, capability=capability)

            # Mark as processing
            db.execute(text("""
                UPDATE app_private.operations
                SET status = 'PROCESSING', started_at = NOW()
                WHERE operation_id = :operation_id
            """), {"operation_id": str(operation_id)})
            db.commit()

            # Route to appropriate handler
            try:
                if capability == "CV_PROCESSING":
                    self._process_cv_batch(operation_id, db)
                elif capability == "ASSESSMENT":
                    self._run_assessments(operation_id, db)
                elif capability == "RANKING":
                    self._generate_ranking(operation_id, db)
                else:
                    logger.warning("Unknown operation capability", capability=capability)
                    db.execute(text("""
                        UPDATE app_private.operations
                        SET status = 'FAILED', error_message = 'Unknown capability', completed_at = NOW()
                        WHERE operation_id = :operation_id
                    """), {"operation_id": str(operation_id)})
                    db.commit()
                    return

                # Mark completed if handler didn't error
                db.execute(text("""
                    UPDATE app_private.operations
                    SET status = 'COMPLETED', completed_at = NOW()
                    WHERE operation_id = :operation_id AND status != 'FAILED'
                """), {"operation_id": str(operation_id)})
                db.commit()
                logger.info("Operation completed successfully", operation_id=operation_id)

            except Exception as e:
                logger.error("Operation failed", operation_id=operation_id, error=str(e), exc_info=True)
                db.rollback()
                db.execute(text("""
                    UPDATE app_private.operations
                    SET status = 'FAILED', error_code = 'PROCESSING_ERROR', error_message = :error, completed_at = NOW()
                    WHERE operation_id = :operation_id
                """), {"operation_id": str(operation_id), "error": str(e)[:500]})
                db.commit()

        finally:
            db.close()

    def _read_file_content(self, document) -> bytes:
        """Read file content from configured storage backend"""
        bucket = document["bucket"]
        storage_path = document["storage_path"]

        if settings.STORAGE_BACKEND == "local":
            full_path = os.path.join(settings.LOCAL_STORAGE_PATH, bucket, storage_path)
            with open(full_path, "rb") as f:
                return f.read()
        elif settings.STORAGE_BACKEND == "supabase":
            from app.db.supabase import get_supabase_client
            supabase = get_supabase_client()
            response = supabase.storage.from_(bucket).download(storage_path)
            return response
        else:
            raise ValueError(f"Unknown storage backend: {settings.STORAGE_BACKEND}")

    def _save_extracted_text(self, application_id: str, document_id: str, full_text: str, pages: list) -> str:
        """Save extracted text to storage and return path"""
        if settings.STORAGE_BACKEND == "local":
            import os
            path = f"{application_id}/{document_id}/extracted.txt"
            full_dir = os.path.join(settings.LOCAL_STORAGE_PATH, "cv-extracted-text", application_id, document_id)
            os.makedirs(full_dir, exist_ok=True)
            full_path = os.path.join(settings.LOCAL_STORAGE_PATH, "cv-extracted-text", path)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            # Also save pages metadata
            meta_path = os.path.join(settings.LOCAL_STORAGE_PATH, "cv-extracted-text", application_id, document_id, "pages.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(pages, f, ensure_ascii=False)
            return path
        return ""

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
                full_text, pages, doc_type = loop.run_until_complete(
                    document_processor.process_document(content, doc["original_filename"], doc["mime_type"])
                )

                # Save extracted text
                extracted_path = self._save_extracted_text(application_id, document_id, full_text, pages)

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
                            candidate_identifier=application_id
                        )
                    )

                    # Create profile version
                    profile_ver_result = db.execute(text("""
                        INSERT INTO app_private.profile_versions
                        (application_id, source_document_id, version_number, extraction_config, status, created_at)
                        VALUES
                        (:application_id, :document_id, 1, '{}'::jsonb, 'COMPLETED', NOW())
                        RETURNING profile_version_id
                    """), {"application_id": application_id, "document_id": document_id})
                    profile_version_id = profile_ver_result.fetchone()[0]

                    # Extract identity (name/email/phone) if present in work history/contact info
                    display_name = candidate_profile.get("candidate_identifier", "")

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

                    if facts:
                        for fact in facts:
                            db.execute(text("""
                                INSERT INTO app_private.profile_facts
                                (profile_version_id, fact_type, fact_value, source_page_number, confidence)
                                VALUES
                                (:profile_version_id, :fact_type, :fact_value::jsonb, :source_page_number, :confidence)
                            """), fact)

                    # Update application identity
                    db.execute(text("""
                        UPDATE app_private.application_identities
                        SET display_name = :display_name
                        WHERE application_id = :application_id
                    """), {
                        "application_id": application_id,
                        "display_name": display_name or doc["original_filename"].replace(".pdf", "").replace(".docx", "")
                    })

                    db.commit()

                except LLMError as e:
                    logger.error("Profile extraction failed, marking for HR review",
                                application_id=application_id, error=str(e))
                    db.rollback()
                    db.execute(text("""
                        UPDATE app_private.application_documents
                        SET file_processing_status = 'NEEDS_HR_REVIEW', processing_error = :error
                        WHERE document_id = :document_id
                    """), {"document_id": document_id, "error": f"Profile extraction failed: {str(e)[:200]}"})
                    needs_review_count += 1
                    db.commit()
                    loop.close()
                    continue

                processed_count += 1
                loop.close()

            except Exception as e:
                logger.error("Document processing failed", document_id=document_id, error=str(e))
                db.rollback()
                db.execute(text("""
                    UPDATE app_private.application_documents
                    SET file_processing_status = 'NEEDS_HR_REVIEW', processing_error = :error
                    WHERE document_id = :document_id
                """), {"document_id": document_id, "error": str(e)[:200]})
                needs_review_count += 1
                db.commit()

        # Update batch stats
        db.execute(text("""
            UPDATE app_private.cv_batches
            SET processed_files = :processed, failed_files = :needs_review,
                status = CASE WHEN :needs_review = 0 THEN 'COMPLETED' ELSE 'PARTIALLY_COMPLETED' END
            WHERE batch_id = :batch_id
        """), {
            "batch_id": str(batch_id),
            "processed": processed_count,
            "needs_review": needs_review_count
        })
        db.commit()

        # After all documents processed, if position has approved criteria, queue assessment
        criteria_result = db.execute(text("""
            SELECT criteria_version_id FROM app_private.criteria_versions
            WHERE position_id = :position_id AND status = 'APPROVED'
            ORDER BY version_number DESC LIMIT 1
        """), {"position_id": str(position_id)})
        if criteria_result.fetchone():
            # Auto queue assessment operation
            from sqlalchemy import text
            db.execute(text("""
                INSERT INTO app_private.operations (capability, status, requested_by)
                VALUES ('ASSESSMENT', 'PENDING', (SELECT created_by FROM app_private.positions WHERE position_id = :position_id))
            """), {"position_id": str(position_id)})
            db.commit()
            logger.info("Auto-queued assessment after batch processing", position_id=position_id)

        logger.info("Batch processing complete",
                    batch_id=batch_id, processed=processed_count, needs_review=needs_review_count)

    def _run_assessments(self, operation_id: UUID, db):
        """Run AI assessment for all unassessed applications"""
        from sqlalchemy import text

        # This is simplified for MVP; actual matching calls LLM and verifies quotes
        logger.info("Assessment operation would run here - Phase 2 implementation will complete the pipeline",
                   operation_id=operation_id)

        # For now, mark operation completed
        # Full implementation will:
        # 1. Load approved criteria and rubric
        # 2. For each unassessed application:
        #    a. Load extracted CV text
        #    b. Load candidate profile
        #    c. Call LLM criterion matcher
        #    d. Verify all verbatim quotes actually exist in CV text
        #    e. Run deterministic scoring
        #    f. Save assessment and criterion results
        # 3. Auto queue ranking operation

        # Placeholder - create operation for ranking
        position_result = db.execute(text("""
            SELECT position_id FROM app_private.applications LIMIT 1
        """))
        # After assessment completes, queue ranking
        db.execute(text("""
            INSERT INTO app_private.operations (capability, status)
            VALUES ('RANKING', 'PENDING')
        """))
        db.commit()

    def _generate_ranking(self, operation_id: UUID, db):
        """Generate ranking after assessments complete"""
        logger.info("Ranking generation would run here - Phase 2 will use matching_engine.rank_applications",
                   operation_id=operation_id)


# Singleton worker instance
worker = ProcessingWorker()
