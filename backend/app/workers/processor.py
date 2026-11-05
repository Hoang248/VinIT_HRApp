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
        """Fetch and process pending operations one at a time.
        Opens a new session for each operation to ensure proper transaction management.
        """
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

    def _save_extracted_text(self, application_id: str, document_id: str, full_text: str, pages: list) -> str:
        """Save extracted text to storage and return path (relative to bucket root)"""
        bucket = settings.SUPABASE_STORAGE_BUCKET_EXTRACTED
        if settings.STORAGE_BACKEND == "local":
            relative_path = f"{application_id}/{document_id}/extracted.txt"
            full_dir = os.path.join(settings.LOCAL_STORAGE_PATH, bucket, application_id, document_id)
            os.makedirs(full_dir, exist_ok=True)
            full_path = os.path.join(settings.LOCAL_STORAGE_PATH, bucket, relative_path)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            # Save pages metadata
            meta_path = os.path.join(settings.LOCAL_STORAGE_PATH, bucket, application_id, document_id, "pages.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(pages, f, ensure_ascii=False)
            return relative_path
        elif settings.STORAGE_BACKEND == "supabase":
            # TODO: Implement Supabase storage upload for extracted text
            relative_path = f"{application_id}/{document_id}/extracted.txt"
            return relative_path
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
        """Run AI assessment for all unassessed applications in the position"""
        from sqlalchemy import text
        from app.services.llm_client import llm_client, LLMError
        from app.services.matching import matching_engine

        logger.info("Starting assessment processing for operation", operation_id=operation_id)

        # Get the position this operation belongs to (from most recent uploaded batch)
        batch_result = db.execute(text("""
            SELECT position_id FROM app_private.cv_batches
            WHERE operation_id = :operation_id
            ORDER BY created_at DESC LIMIT 1
        """), {"operation_id": str(operation_id)})
        batch_row = batch_result.fetchone()
        if not batch_row:
            # Fallback: find position with pending applications
            pos_result = db.execute(text("""
                SELECT DISTINCT a.position_id FROM app_private.applications a
                JOIN app_private.application_documents d ON d.application_id = a.application_id
                WHERE d.file_processing_status = 'COMPLETED'
                LIMIT 1
            """))
            pos_row = pos_result.fetchone()
            if not pos_row:
                logger.warning("No position found for assessment operation", operation_id=operation_id)
                return
            position_id = pos_row[0]
        else:
            position_id = batch_row[0]

        # Get latest approved criteria for position
        criteria_result = db.execute(text("""
            SELECT cv.criteria_version_id, cv.mandatory_weight_total, cv.nice_to_have_weight_total
            FROM app_private.criteria_versions cv
            WHERE cv.position_id = :position_id AND cv.status = 'APPROVED'
            ORDER BY cv.version_number DESC LIMIT 1
        """), {"position_id": position_id})
        criteria_row = criteria_result.fetchone()
        if not criteria_row:
            logger.error("No approved criteria found for position, cannot run assessments", position_id=position_id)
            return

        criteria_version_id = criteria_row[0]

        # Get criteria items
        criteria_items_result = db.execute(text("""
            SELECT criterion_id, name, description, category, weight_in_group, expected_evidence_keywords
            FROM app_private.criteria_items
            WHERE criteria_version_id = :criteria_version_id
            ORDER BY display_order
        """), {"criteria_version_id": criteria_version_id})
        criteria_items = [dict(zip(["criterion_id", "name", "description", "category", "weight_in_group", "expected_evidence_keywords"], row))
                         for row in criteria_items_result.fetchall()]

        # Get applications with completed processing that don't have assessment yet
        apps_result = db.execute(text("""
            SELECT a.application_id, d.document_id, d.storage_path as doc_path
            FROM app_private.applications a
            JOIN app_private.application_documents d ON d.application_id = a.application_id
            LEFT JOIN app_private.assessment_runs ar ON ar.application_id = a.application_id
                AND ar.criteria_version_id = :criteria_version_id
            WHERE a.position_id = :position_id
              AND d.file_processing_status = 'COMPLETED'
              AND d.document_type = 'CV'
              AND ar.assessment_id IS NULL
        """), {
            "position_id": position_id,
            "criteria_version_id": criteria_version_id
        })
        applications = [dict(zip(["application_id", "document_id", "doc_path"], row)) for row in apps_result.fetchall()]

        logger.info(f"Found {len(applications)} applications to assess", position_id=position_id)
        loop = asyncio.new_event_loop()
        try:
            for app in applications:
                application_id = app["application_id"]
                document_id = app["document_id"]

                try:
                    # Load extracted text
                    extracted_path = os.path.join(
                        settings.LOCAL_STORAGE_PATH,
                        settings.SUPABASE_STORAGE_BUCKET_EXTRACTED,
                        application_id,
                        document_id,
                        "extracted.txt"
                    )
                    if not os.path.exists(extracted_path):
                        logger.warning("Extracted text not found for application", application_id=application_id)
                        continue

                    with open(extracted_path, "r", encoding="utf-8") as f:
                        cv_text = f.read()

                    # Create assessment run record
                    assess_result = db.execute(text("""
                        INSERT INTO app_private.assessment_runs
                        (position_id, application_id, criteria_version_id, profile_version_id,
                         policy_version, operation_id, status, created_at)
                        VALUES
                        (:position_id, :application_id, :criteria_version_id,
                         (SELECT profile_version_id FROM app_private.profile_versions WHERE application_id = :app_id LIMIT 1),
                         'v1.0', :operation_id, 'PROCESSING', NOW())
                        RETURNING assessment_id
                    """), {
                        "position_id": position_id,
                        "application_id": application_id,
                        "criteria_version_id": criteria_version_id,
                        "app_id": application_id,
                        "operation_id": str(operation_id)
                    })
                    assessment_id = assess_result.fetchone()[0]

                    # Get latest profile version
                    profile_result = db.execute(text("""
                        SELECT fact_type, fact_value FROM app_private.profile_facts pf
                        JOIN app_private.profile_versions pv ON pf.profile_version_id = pv.profile_version_id
                        WHERE pv.application_id = :application_id
                    """), {"application_id": application_id})
                    profile_facts = [dict(row) for row in profile_result.fetchall()]

                    # Build simplified candidate profile for LLM
                    candidate_profile = {
                        "candidate_identifier": application_id,
                        "total_years_experience": 0,
                        "education": [pf["fact_value"] for pf in profile_facts if pf["fact_type"] == "EDUCATION"],
                        "work_history": [pf["fact_value"] for pf in profile_facts if pf["fact_type"] == "WORK_EXPERIENCE"],
                        "skills": [pf["fact_value"].get("name") for pf in profile_facts if pf["fact_type"] == "SKILL"],
                        "certifications": [pf["fact_value"] for pf in profile_facts if pf["fact_type"] == "CERTIFICATION"]
                    }

                    # Run LLM matching
                    try:
                        findings = loop.run_until_complete(
                            llm_client.match_criterion_evidence(
                                cv_text=cv_text,
                                candidate_profile=candidate_profile,
                                rubric=criteria_items,
                                candidate_identifier=application_id,
                                rubric_version=criteria_version_id
                            )
                        )

                        # Verify verbatim quotes exist in CV text
                        valid_findings = []
                        for finding in findings.get("findings", []):
                            evidence = finding.get("evidence")
                            if evidence and evidence.get("verbatim_quote"):
                                quote_valid = matching_engine.verify_verbatim_quote(
                                    evidence["verbatim_quote"],
                                    cv_text
                                )
                                finding["evidence_verified"] = quote_valid
                                if not quote_valid and finding["outcome"] in ["STRONG_MATCH", "MATCH"]:
                                    finding["outcome"] = "UNCLEAR"
                                    finding["requires_verification"] = True
                            valid_findings.append(finding)

                        # Run deterministic scoring
                        score, coverage, matching_status, aug_findings, needs_verification = \
                            matching_engine.calculate_assessment_scores(criteria_items, valid_findings)

                        # Update assessment run with scores
                        db.execute(text("""
                            UPDATE app_private.assessment_runs
                            SET status = 'COMPLETED',
                                matching_status = :matching_status,
                                matching_score = :score,
                                evidence_coverage = :coverage,
                                confidence = 0.8,
                                completed_at = NOW()
                            WHERE assessment_id = :assessment_id
                        """), {
                            "assessment_id": assessment_id,
                            "matching_status": matching_status,
                            "score": score,
                            "coverage": coverage
                        })

                        # Save criterion results and evidence
                        for finding in aug_findings:
                            crit_res = db.execute(text("""
                                INSERT INTO app_private.criterion_assessment_results
                                (assessment_id, criterion_id, outcome, score, confidence, confidence_band,
                                 requires_hr_verification, reasoning)
                                VALUES
                                (:assessment_id, :criterion_id, :outcome, :score, 0.8, 'MEDIUM',
                                 :requires_verification, :reasoning)
                                RETURNING result_id
                            """), {
                                "assessment_id": assessment_id,
                                "criterion_id": finding["criterion_id"],
                                "outcome": finding["outcome"],
                                "score": finding.get("score"),
                                "requires_verification": finding.get("requires_verification", False),
                                "reasoning": finding.get("reasoning")
                            })
                            result_id = crit_res.fetchone()[0]

                            # Save evidence if present
                            if finding.get("evidence") and finding["evidence"].get("verbatim_quote"):
                                db.execute(text("""
                                    INSERT INTO app_private.evidence_items
                                    (criterion_result_id, source_document_id, verbatim_quote, page_number,
                                     evidence_type, verification_status)
                                    VALUES
                                    (:result_id, :document_id, :quote, :page_num,
                                     'TEXT_QUOTE', :verification_status)
                                """), {
                                    "result_id": result_id,
                                    "document_id": document_id,
                                    "quote": finding["evidence"]["verbatim_quote"],
                                    "page_num": finding["evidence"].get("page_number"),
                                    "verification_status": "VERIFIED" if finding.get("evidence_verified") else "FAILED"
                                })

                        db.commit()
                        logger.info("Assessment completed for application",
                                   application_id=application_id,
                                   score=score,
                                   coverage=coverage,
                                   status=matching_status)

                    except LLMError as e:
                        logger.error("LLM matching failed for application", application_id=application_id, error=str(e))
                        db.rollback()
                        db.execute(text("""
                            UPDATE app_private.assessment_runs
                            SET status = 'FAILED', completed_at = NOW()
                            WHERE assessment_id = :assessment_id
                        """), {"assessment_id": assessment_id})
                        db.commit()
                        continue

                except Exception as e:
                    logger.error("Assessment failed for application", application_id=application_id, error=str(e), exc_info=True)
                    db.rollback()
                    continue
        finally:
            loop.close()

        # After all assessments complete, queue ranking
        db.execute(text("""
            INSERT INTO app_private.operations (capability, status, requested_by)
            VALUES ('RANKING', 'PENDING', (SELECT created_by FROM app_private.positions WHERE position_id = :position_id))
        """), {"position_id": position_id})
        db.commit()
        logger.info("Assessment batch complete, ranking queued", position_id=position_id)

    def _generate_ranking(self, operation_id: UUID, db):
        """Generate ranking for position using matching engine"""
        from sqlalchemy import text

        logger.info("Starting ranking generation for operation", operation_id=operation_id)

        # Find position from latest completed assessment
        pos_result = db.execute(text("""
            SELECT DISTINCT position_id FROM app_private.assessment_runs
            WHERE status = 'COMPLETED'
            ORDER BY completed_at DESC LIMIT 1
        """))
        pos_row = pos_result.fetchone()
        if not pos_row:
            logger.warning("No completed assessments found for ranking")
            return
        position_id = pos_row[0]

        # Get latest approved criteria
        criteria_result = db.execute(text("""
            SELECT criteria_version_id FROM app_private.criteria_versions
            WHERE position_id = :position_id AND status = 'APPROVED'
            ORDER BY version_number DESC LIMIT 1
        """), {"position_id": position_id})
        crit_row = criteria_result.fetchone()
        if not crit_row:
            logger.error("No approved criteria for ranking", position_id=position_id)
            return
        criteria_version_id = crit_row[0]

        # Get criteria items
        crit_items_result = db.execute(text("""
            SELECT criterion_id, name, description, category, weight_in_group
            FROM app_private.criteria_items
            WHERE criteria_version_id = :criteria_version_id
        """), {"criteria_version_id": criteria_version_id})
        criteria_items = [dict(zip(["criterion_id", "name", "description", "category", "weight_in_group"], row))
                         for row in crit_items_result.fetchall()]

        # Get applications with latest assessment
        apps_result = db.execute(text("""
            SELECT
                a.application_id,
                ai.display_name,
                ar.assessment_id,
                ar.matching_status,
                ar.matching_score,
                ar.evidence_coverage
            FROM app_private.applications a
            LEFT JOIN app_private.application_identities ai ON ai.application_id = a.application_id
            JOIN (
                SELECT application_id, MAX(created_at) as latest
                FROM app_private.assessment_runs
                WHERE status = 'COMPLETED' AND position_id = :position_id
                GROUP BY application_id
            ) latest_ar ON latest_ar.application_id = a.application_id
            JOIN app_private.assessment_runs ar ON ar.application_id = a.application_id AND ar.created_at = latest_ar.latest
            WHERE a.position_id = :position_id
              AND a.application_status IN ('NEW', 'IN_REVIEW', 'SHORTLIST')
        """), {"position_id": position_id})

        applications = []
        for row in apps_result.fetchall():
            app_data = dict(zip(["application_id", "display_name", "assessment_id", "matching_status", "matching_score", "evidence_coverage"], row))
            app_data["latest_assessment"] = {
                "matching_status": app_data.pop("matching_status"),
                "matching_score": app_data.pop("matching_score"),
                "evidence_coverage": app_data.pop("evidence_coverage"),
            }
            applications.append(app_data)

        if not applications:
            logger.info("No applications to rank", position_id=position_id)
            return

        # Run deterministic ranking
        ranked = matching_engine.rank_applications(applications, criteria_items)

        # Create ranking run
        rank_run_result = db.execute(text("""
            INSERT INTO app_private.ranking_runs
            (position_id, criteria_version_id, policy_version, operation_id, status, created_at, completed_at)
            VALUES
            (:position_id, :criteria_version_id, 'v1.0', :operation_id, 'COMPLETED', NOW(), NOW())
            RETURNING ranking_run_id
        """), {
            "position_id": position_id,
            "criteria_version_id": criteria_version_id,
            "operation_id": str(operation_id)
        })
        ranking_run_id = rank_run_result.fetchone()[0]

        # Insert ranking items
        for item in ranked:
            assess = item.get("latest_assessment", {})
            db.execute(text("""
                INSERT INTO app_private.ranking_items
                (ranking_run_id, position_id, application_id, assessment_id, rank_number,
                 ranking_status, matching_score, evidence_coverage)
                VALUES
                (:ranking_run_id, :position_id, :application_id, :assessment_id, :rank_number,
                 :ranking_status, :matching_score, :coverage)
            """), {
                "ranking_run_id": ranking_run_id,
                "position_id": position_id,
                "application_id": item["application_id"],
                "assessment_id": assess.get("assessment_id"),
                "rank_number": item["rank_number"],
                "ranking_status": assess.get("matching_status"),
                "matching_score": assess.get("matching_score"),
                "coverage": assess.get("evidence_coverage")
            })

        # Detect duplicates
        duplicates = matching_engine.detect_duplicates(applications)
        for app1_id, app2_id, confidence, signal_type in duplicates:
            db.execute(text("""
                INSERT INTO app_private.duplicate_signals
                (position_id, application_id_1, application_id_2, signal_type, confidence, detector_version, review_status)
                VALUES
                (:position_id, :app1, :app2, :signal_type, :confidence, 'v1.0', 'PENDING')
            """), {
                "position_id": position_id,
                "app1": app1_id,
                "app2": app2_id,
                "signal_type": signal_type,
                "confidence": confidence
            })

        db.commit()
        logger.info("Ranking generated successfully",
                   ranking_run_id=ranking_run_id,
                   ranked_count=len(ranked),
                   duplicates=len(duplicates))


# Singleton worker instance
worker = ProcessingWorker()
