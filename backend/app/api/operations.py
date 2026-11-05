from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.core.exceptions import NotFoundError
from sqlalchemy import text

router = APIRouter()


@router.get("/{operation_id}")
async def get_operation_status(
    operation_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get status of an async operation (for progress tracking)"""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT operation_id, capability, status, error_code, error_message,
                   created_at, started_at, completed_at
            FROM app_private.operations
            WHERE operation_id = :operation_id
        """), {"operation_id": str(operation_id)})
        row = result.fetchone()
        if not row:
            raise NotFoundError("Operation")

        # Convert row to dict properly using column names
        op = {
            "operation_id": str(row[0]),
            "capability": row[1],
            "status": row[2],
            "error_code": row[3] if len(row) > 3 else None,
            "error_message": row[4] if len(row) > 4 else None,
            "created_at": row[5] if len(row) > 5 else None,
            "started_at": row[6] if len(row) > 6 else None,
            "completed_at": row[7] if len(row) > 7 else None,
        }

        if op["capability"] == "CV_PROCESSING":
            batch_result = db.execute(text("""
                SELECT b.batch_id, b.total_files, b.processed_files, b.failed_files, b.status as batch_status
                FROM app_private.cv_batches b
                WHERE b.operation_id = :operation_id
            """), {"operation_id": str(operation_id)})
            batch_row = batch_result.fetchone()
            if batch_row:
                total = batch_row[1] or 0
                processed = batch_row[2] or 0
                failed = batch_row[3] or 0
                op["progress"] = {
                    "total": total,
                    "processed": processed,
                    "failed": failed,
                    "percent_complete": round((processed + failed) / total * 100) if total > 0 else 0
                }

        return op
    finally:
        db.close()
