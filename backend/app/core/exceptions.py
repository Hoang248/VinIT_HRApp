from fastapi import HTTPException, status


class HRAException(Exception):
    """Base exception class for HRA application"""
    def __init__(self, message: str, code: str = "error", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class FileValidationError(HRAException):
    """Raised when uploaded file fails validation"""
    def __init__(self, message: str):
        super().__init__(message, code="file_validation_error", status_code=status.HTTP_400_BAD_REQUEST)


class UnauthorizedError(HRAException):
    """Raised when user doesn't have required permissions"""
    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(message, code="unauthorized", status_code=status.HTTP_403_FORBIDDEN)


class NotFoundError(HRAException):
    """Raised when requested resource doesn't exist"""
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", code="not_found", status_code=status.HTTP_404_NOT_FOUND)


class CriteriaNotApprovedError(HRAException):
    """Raised when trying to run assessment on unapproved criteria"""
    def __init__(self):
        super().__init__(
            "Cannot run assessment: criteria have not been approved by HR and Hiring Manager",
            code="criteria_not_approved",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class InvalidStatusTransitionError(HRAException):
    """Raised when invalid application status transition is attempted"""
    def __init__(self, from_status: str, to_status: str):
        super().__init__(
            f"Invalid status transition from '{from_status}' to '{to_status}'",
            code="invalid_status_transition",
            status_code=status.HTTP_400_BAD_REQUEST
        )
