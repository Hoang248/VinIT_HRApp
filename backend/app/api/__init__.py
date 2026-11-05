from fastapi import APIRouter
from . import positions, criteria, applications, assessments, dashboard, auth

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(positions.router, prefix="/positions", tags=["Positions"])
api_router.include_router(criteria.router, prefix="/criteria", tags=["Criteria & Rubric"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications & CVs"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["AI Assessment & Ranking"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard & Reporting"])
