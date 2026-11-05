from fastapi import APIRouter
from . import auth, positions, criteria, applications, assessments, shortlist, dashboard, admin, operations

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(operations.router, prefix="/operations", tags=["Async Operations"])
api_router.include_router(positions.router, prefix="/positions", tags=["Positions"])
api_router.include_router(criteria.router, prefix="/criteria", tags=["Criteria & Rubric"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications & CVs"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["AI Assessment & Ranking"])
api_router.include_router(shortlist.router, prefix="/shortlist", tags=["Shortlist Sharing"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard & Reporting"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Configuration"])
