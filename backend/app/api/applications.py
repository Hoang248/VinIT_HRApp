from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from typing import List, Optional
from uuid import UUID, uuid4
from app.core.security import get_current_user
from app.core.permissions import check_position_access, can_update_application_status
from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import (
    FileValidationError,
    InvalidStatusTransitionError,
    NotFoundError
)
from app.schemas.applications import (
    Application,
    ApplicationWithAssessment,
    ApplicationStatus,
    ApplicationStatusUpdate,
    CVBatch,
    CVUploadItem,
    FileProcessingStatus,
)
from app.schemas.common import OperationResponse
from app.db.supabase import get_supabase_client
from app.services.document_processor import document_processor
import os
import aiofiles

router = APIRouter()
logger = get_logger(__name__)

# Valid status transitions per business rules
VALID_TRANSITIONS = {
    ApplicationStatus.NEW: [ApplicationStatus.IN_REVIEW, ApplicationStatus.REJECTED_SCREENING],
    ApplicationStatus.IN_REVIEW: [ApplicationStatus.SHORTLIST, ApplicationStatus.REJECTED_SCREENING],
    ApplicationStatus.SHORTLIST: [ApplicationStatus.IN_REVIEW, ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED_SCREENING],
    ApplicationStatus.INTERVIEW: [ApplicationStatus.REJECTED_INTERVIEW, ApplicationStatus.OFFERED],
    ApplicationStatus.OFFERED: [ApplicationStatus.ACCEPTED],
    ApplicationStatus.REJECTED_SCREENING: [],  # Terminal; reopen requires special permission
    ApplicationStatus.REJECTED_INTERVIEW: [],  # Terminal
    ApplicationStatus.ACCEPTED: [],
}


@router.post("/upload-batch/{position_id}", response_model=OperationResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_cv_batch(
    position_id: UUID,
    request: Request,
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a batch of CV files for a position. Returns operation ID for async processing."""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    position_id_str = str(position_id)

    # RBAC: only HR_RECRUITER on this position (or Admin/HR Lead) can upload CVs
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER", "HIRING_MANAGER"])

    # Verify position exists and is open
    pos_result = supabase.table("positions").select("*").eq("position_id", position_id_str).single().execute()
    if not pos_result.data:
        raise NotFoundError("Position")
    if pos_result.data["status"] != "OPEN":
        raise HTTPException(status_code=400, detail="Cannot upload CVs to a closed/paused position")

    # Validate batch size
    if len(files) > settings.MAX_FILES_PER_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.MAX_FILES_PER_BATCH} files per batch allowed"
        )

    total_size = 0
    valid_files = []
    invalid_files = []

    # Create operation record
    op_result = supabase.table("operations").insert({
        "capability": "CV_PROCESSING",
        "status": "PENDING",
        "requested_by": user_id,
    }).execute()
    operation_id = op_result.data[0]["operation_id"]

    # Create batch record
    batch_result = supabase.table("cv_batches").insert({
        "position_id": position_id_str,
        "uploaded_by": user_id,
        "operation_id": operation_id,
        "status": "PROCESSING",
        "total_files": len(files),
        "total_size_bytes": 0,  # Will update after validation
    }).execute()
    batch_id = batch_result.data[0]["batch_id"]

    # Validate and upload each file
    for file in files:
        content = await file.read()
        file_size = len(content)
        total_size += file_size

        if file_size > settings.MAX_FILE_SIZE_BYTES:
            invalid_files.append({
                "original_filename": file.filename,
                "declared_mime_type": file.content_type,
                "size_bytes": file_size,
                "validation_result": "ERROR",
                "error_code": "FILE_TOO_LARGE"
            })
            continue

        try:
            # Validate file type
            await document_processor.validate_file(content, file.filename, file.content_type)

            # Create application record
            app_result = supabase.table("applications").insert({
                "position_id": position_id_str,
                "source_code": "DIRECT_UPLOAD",
                "application_status": ApplicationStatus.NEW.value,
                "created_by": user_id
            }).execute()
            application_id = app_result.data[0]["application_id"]

            # Generate storage path (internal UUID path, not using candidate name)
            file_ext = file.filename.split(".")[-1] if "." in file.filename else "pdf"
            storage_path = f"{position_id_str}/{application_id}/{uuid4()}.{file_ext}"

            # Upload file to configured storage backend
            if settings.STORAGE_BACKEND == "local":
                # Local filesystem storage
                full_dir = os.path.join(
                    settings.LOCAL_STORAGE_PATH,
                    settings.SUPABASE_STORAGE_BUCKET_CV,
                    str(position_id),
                    application_id
                )
                os.makedirs(full_dir, exist_ok=True)
                full_file_path = os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_CV, storage_path)
                async with aiofiles.open(full_file_path, "wb") as f:
                    await f.write(content)
            elif settings.STORAGE_BACKEND == "supabase":
                # Upload to Supabase Storage
                supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET_CV).upload(
                    path=storage_path,
                    file=content,
                    file_options={"content-type": file.content_type or "application/octet-stream"}
                )
            else:
                raise HTTPException(status_code=500, detail=f"Unknown storage backend: {settings.STORAGE_BACKEND}")

            # Create document record
            doc_result = supabase.table("application_documents").insert({
                "application_id": application_id,
                "document_type": "CV",
                "bucket": settings.SUPABASE_STORAGE_BUCKET_CV,
                "storage_path": storage_path,
                "original_filename": file.filename,
                "mime_type": file.content_type or "application/pdf",
                "size_bytes": file_size,
                "file_processing_status": FileProcessingStatus.RECEIVED.value
            }).execute()
            document_id = doc_result.data[0]["document_id"]

            valid_files.append({
                "batch_id": batch_id,
                "original_filename": file.filename,
                "declared_mime_type": file.content_type,
                "size_bytes": file_size,
                "validation_result": "ACCEPTED",
                "application_id": application_id
            })

            # Create empty identity record
            supabase.table("application_identities").insert({
                "application_id": application_id
            }).execute()

            # Create processing run record
            supabase.table("document_processing_runs").insert({
                "document_id": document_id,
                "operation_id": operation_id,
                "extraction_type": "INITIAL_EXTRACTION",
                "status": "PENDING"
            }).execute()

            logger.info("File accepted for processing",
                       filename=file.filename,
                       application_id=application_id,
                       batch_id=batch_id)

        except FileValidationError as e:
            invalid_files.append({
                "original_filename": file.filename,
                "declared_mime_type": file.content_type,
                "size_bytes": file_size,
                "validation_result": "ERROR",
                "error_code": str(e)
            })
            logger.warning("File validation failed", filename=file.filename, error=str(e))

    # Check total batch size
    if total_size > settings.MAX_BATCH_SIZE_BYTES:
        # Rollback? For MVP, accept but record error
        logger.warning("Batch exceeds total size limit", total_size=total_size)

    # Update batch totals
    supabase.table("cv_batches").update({
        "total_size_bytes": total_size,
        "processed_files": len(valid_files),
        "failed_files": len(invalid_files),
        "status": "COMPLETED" if len(invalid_files) == 0 else "PARTIALLY_COMPLETED"
    }).eq("batch_id", batch_id).execute()

    # Insert batch items
    all_batch_items = valid_files + invalid_files
    if all_batch_items:
        # Set batch_id on all items
        for item in all_batch_items:
            item["batch_id"] = batch_id
        supabase.table("cv_batch_items").insert(all_batch_items).execute()

    # Mark operation as processing and trigger async processing
    supabase.table("operations").update({
        "status": "PROCESSING",
        "started_at": "now()"
    }).eq("operation_id", operation_id).execute()

    # Mark operation as PENDING for worker pickup
    supabase.table("operations").update({
        "status": "PENDING"
    }).eq("operation_id", operation_id).execute()

    # Worker will automatically pick up this operation and start processing
    # No need to trigger manually; it polls every POLL_INTERVAL_SECONDS seconds

    # Log audit
    supabase.table("audit_events").insert({
        "actor_user_id": user_id,
        "action_type": "UPLOAD_CV_BATCH",
        "object_type": "CV_BATCH",
        "object_id": batch_id,
        "position_id": position_id_str,
        "outcome": "SUCCESS",
        "metadata": {"total_files": len(files), "accepted": len(valid_files), "failed": len(invalid_files)}
    }).execute()

    logger.info("CV batch created", batch_id=batch_id, total=len(files), accepted=len(valid_files), failed=len(invalid_files))

    return OperationResponse(
        operation_id=UUID(operation_id),
        status="processing",
        message=f"Đã nhận {len(valid_files)} file hợp lệ, {len(invalid_files)} file lỗi. Đang xử lý..."
    )


@router.get("", response_model=List[ApplicationWithAssessment])
async def list_applications(
    position_id: UUID = Query(...),
    status_filter: Optional[ApplicationStatus] = Query(None, alias="status"),
    matching_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List applications for a position with their latest assessment"""
    # RBAC: user must have access to this position
    await check_position_access(position_id, current_user)

    supabase = get_supabase_client()

    query = supabase.table("applications")\
        .select(
            "*, "
            "identity: application_identities(*), "
            "documents: application_documents(*), "
            "latest_assessment: assessment_runs(*)"
        )\
        .eq("position_id", str(position_id))

    if status_filter:
        query = query.eq("application_status", status_filter.value)

    offset = (page - 1) * page_size
    result = query.range(offset, offset + page_size - 1).order("created_at", desc=True).execute()

    applications = result.data or []

    # Enrich with latest assessment for each application, plus duplicate/error flags
    for app in applications:
        assessments = app.get("latest_assessment", [])
        if isinstance(assessments, list) and assessments:
            completed = [a for a in assessments if a.get("status") == "COMPLETED"]
            if completed:
                app["latest_assessment"] = sorted(completed, key=lambda x: x.get("created_at", ""))[-1]
            else:
                app["latest_assessment"] = None
        elif not isinstance(assessments, list):
            pass
        else:
            app["latest_assessment"] = None

        # Flag for files needing HR review (PROCESSING_ERROR or NEEDS_REVIEW)
        docs = app.get("documents", [])
        if isinstance(docs, list):
            app["file_processing_status"] = "COMPLETED"
            for d in docs:
                status_d = d.get("file_processing_status", "")
                if status_d in ("ERROR_UNSUPPORTED", "NEEDS_HR_REVIEW") or d.get("processing_error"):
                    app["file_processing_status"] = "NEEDS_HR_REVIEW"
                    app["file_error"] = d.get("processing_error") or f"File {status_d}"
                    break
                if status_d in ("RECEIVED", "PROCESSING"):
                    app["file_processing_status"] = "PROCESSING"
        else:
            app["file_processing_status"] = "UNKNOWN"

    # Enrich with duplicate signals (at least one PENDING duplicate for any of these apps)
    if applications:
        app_ids = [a["application_id"] for a in applications]
        try:
            dup_result = supabase.table("duplicate_signals")\
                .select("application_id_1, application_id_2")\
                .eq("position_id", str(position_id))\
                .in_("application_id_1", app_ids)\
                .eq("review_status", "PENDING")\
                .execute()
            dup_ids = set()
            for d in (dup_result.data or []):
                dup_ids.add(d["application_id_1"])
                dup_ids.add(d["application_id_2"])
            for app in applications:
                app["has_duplicate_warning"] = app["application_id"] in dup_ids
        except Exception:
            for app in applications:
                app["has_duplicate_warning"] = False

    return applications


@router.get("/{application_id}", response_model=ApplicationWithAssessment)
async def get_application(
    application_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get application details with documents, profile, and assessment results"""
    supabase = get_supabase_client()
    app_id_str = str(application_id)

    # Fetch application first to derive position_id for RBAC check
    app_check = supabase.table("applications").select("position_id").eq("application_id", app_id_str).single().execute()
    if not app_check.data:
        raise NotFoundError("Application")
    await check_position_access(
        UUID(app_check.data["position_id"]), current_user, application_id=application_id
    )

    result = supabase.table("applications")\
        .select(
            "*, "
            "identity: application_identities(*), "
            "documents: application_documents(*), "
            "profile_versions(*, profile_facts(*)), "
            "assessments: assessment_runs(*, criterion_results: criterion_assessment_results(*, evidence: evidence_items(*)))"
        )\
        .eq("application_id", app_id_str)\
        .single()\
        .execute()

    if not result.data:
        raise NotFoundError("Application")

    app_data = result.data

    # Enrich file_processing_status
    docs = app_data.get("documents", []) or []
    fps = "UNKNOWN"
    file_error = None
    if docs:
        if any(d.get("file_processing_status") == "PROCESSING" for d in docs):
            fps = "PROCESSING"
        elif any(d.get("file_processing_status") == "NEEDS_HR_REVIEW" for d in docs):
            fps = "NEEDS_HR_REVIEW"
            for d in docs:
                if d.get("file_processing_status") == "NEEDS_HR_REVIEW":
                    file_error = d.get("metadata", {}).get("error") or d.get("file_error")
                    break
        elif any(d.get("file_processing_status") == "COMPLETED" for d in docs):
            fps = "COMPLETED"
    app_data["file_processing_status"] = fps
    app_data["file_error"] = file_error

    # Duplicate warning
    identity = app_data.get("identity") or []
    app_data["has_duplicate_warning"] = bool(identity and (identity[0].get("identity_match_confidence") or 0) > 0) if isinstance(identity, list) else False

    # Sort assessments by date, get latest completed
    assessments = app_data.get("assessments", [])
    completed_assessments = [a for a in assessments if a.get("status") == "COMPLETED"]
    if completed_assessments:
        app_data["latest_assessment"] = sorted(
            completed_assessments,
            key=lambda x: x.get("created_at", "")
        )[-1]
    else:
        app_data["latest_assessment"] = None

    return app_data


@router.patch("/{application_id}/status", response_model=Application)
async def update_application_status(
    application_id: UUID,
    update: ApplicationStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update application recruitment status (HR only, validates transition matrix)"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    app_id_str = str(application_id)

    # Get current application
    app_result = supabase.table("applications").select("*").eq("application_id", app_id_str).single().execute()
    if not app_result.data:
        raise NotFoundError("Application")

    app = app_result.data

    # RBAC: only HR_RECRUITER assigned to this position (or Admin/HR Lead) can change status
    if not can_update_application_status(user_id, app["position_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be the assigned HR Recruiter to update application status"
        )
    current_status = ApplicationStatus(app["application_status"])
    new_status = update.new_status

    # Validate transition
    allowed_next = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_next:
        # Allow reopen with special permission? For MVP, just reject
        raise InvalidStatusTransitionError(current_status.value, new_status.value)

    # Update status
    update_result = supabase.table("applications").update({
        "application_status": new_status.value,
        "updated_at": "now()"
    }).eq("application_id", app_id_str).execute()

    # Record status event
    supabase.table("application_status_events").insert({
        "application_id": app_id_str,
        "previous_status": current_status.value,
        "new_status": new_status.value,
        "changed_by": user_id,
        "reason_code": update.reason,
        "note": update.note
    }).execute()

    # Log audit
    supabase.table("audit_events").insert({
        "actor_user_id": user_id,
        "action_type": "UPDATE_APPLICATION_STATUS",
        "object_type": "APPLICATION",
        "object_id": app_id_str,
        "position_id": app["position_id"],
        "outcome": new_status.value,
        "metadata": {"from": current_status.value, "to": new_status.value}
    }).execute()

    logger.info(
        "Application status updated",
        application_id=app_id_str,
        from_status=current_status.value,
        to_status=new_status.value,
        by=user_id
    )

    return update_result.data[0]


@router.get("/{application_id}/cv-download-url")
async def get_cv_download_url(
    application_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get signed time-limited URL to download original CV file (after permission check)"""
    supabase = get_supabase_client()
    app_id_str = str(application_id)

    # Get application for position_id RBAC check
    app_result = supabase.table("applications").select("position_id").eq("application_id", app_id_str).single().execute()
    if not app_result.data:
        raise NotFoundError("Application")
    # RBAC: user must have access to the position this CV belongs to
    await check_position_access(UUID(app_result.data["position_id"]), current_user)

    # Get application and its documents
    doc_result = supabase.table("application_documents")\
        .select("*")\
        .eq("application_id", app_id_str)\
        .eq("document_type", "CV")\
        .limit(1)\
        .execute()

    if not doc_result.data:
        raise NotFoundError("CV Document")

    doc = doc_result.data[0]

    # Generate access information
    try:
        if settings.STORAGE_BACKEND == "local":
            # For local development, return API URL to serve file (with auth check)
            file_url = f"{settings.API_V1_PREFIX}/applications/{application_id}/cv-file"
            return {"file_url": file_url, "filename": doc["original_filename"], "source": "local"}
        elif settings.STORAGE_BACKEND == "supabase":
            if not supabase:
                raise HTTPException(status_code=500, detail="Supabase storage is not configured")
            signed_url = supabase.storage.from_(doc["bucket"]).create_signed_url(
                path=doc["storage_path"],
                expires_in=600  # 10 minutes
            )
            return {"signed_url": signed_url, "filename": doc["original_filename"], "source": "supabase"}
        else:
            raise HTTPException(status_code=500, detail=f"Unknown storage backend: {settings.STORAGE_BACKEND}")
    except NotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to generate file access URL", error=str(e))
        raise HTTPException(status_code=500, detail="Could not generate file access URL")


@router.get("/{application_id}/cv-file")
async def serve_cv_file(
    application_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Serve CV file directly from local storage with permission check (development only)"""
    if settings.STORAGE_BACKEND != "local":
        raise HTTPException(status_code=400, detail="Local file serving is only available with local storage backend")

    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available")

    app_id_str = str(application_id)

    # Get application for RBAC check
    app_result = supabase.table("applications").select("position_id").eq("application_id", app_id_str).single().execute()
    if not app_result.data:
        raise NotFoundError("Application")
    await check_position_access(UUID(app_result.data["position_id"]), current_user)

    doc_result = supabase.table("application_documents")\
        .select("*")\
        .eq("application_id", app_id_str)\
        .eq("document_type", "CV")\
        .limit(1)\
        .execute()

    if not doc_result.data:
        raise NotFoundError("CV Document")

    doc = doc_result.data[0]

    # Build and validate path - prevent path traversal attacks
    base_storage_dir = os.path.realpath(os.path.join(settings.LOCAL_STORAGE_PATH, doc["bucket"]))
    file_path = os.path.realpath(os.path.join(base_storage_dir, doc["storage_path"]))

    # Ensure the resolved file is still within the allowed base directory
    if not file_path.startswith(base_storage_dir + os.sep) and file_path != base_storage_dir:
        logger.warning("Path traversal attempt detected", application_id=app_id_str, requested_path=doc["storage_path"])
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not os.path.isfile(file_path):
        raise NotFoundError("CV file not found on disk")

    # Sanitize filename for Content-Disposition header
    safe_filename = os.path.basename(doc["original_filename"])

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type=doc["mime_type"]
    )
