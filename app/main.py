from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import prisma
from app.routes import auth, persons, attendance, payroll, companies, users, adjustments

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not prisma.is_connected():
        await prisma.connect()
    yield
    if prisma.is_connected():
        await prisma.disconnect()

app = FastAPI(
    title="PPHAdmin API",
    description="Backend API for Employee Records & Payroll Management System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["User Management"])
app.include_router(persons.router, prefix="/api/persons", tags=["Persons (Employees & OJTs)"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance logs"])
app.include_router(payroll.router, prefix="/api/payroll", tags=["Payroll Calculations"])
app.include_router(adjustments.router, prefix="/api/payroll/adjustments", tags=["Payroll Adjustments"])
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])

@app.get("/")
def read_root():
    return {
        "status": "online",
        "app": "PPHAdmin API Server",
        "documentation": "/docs"
    }
