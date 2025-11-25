#!/usr/bin/env python3
"""
Single-file FastAPI app with a health endpoint and PostgreSQL DB setup using SQLAlchemy.
Minimal dependencies: fastapi, uvicorn, sqlalchemy, psycopg2-binary
"""

import os
import time
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------
# App host/port (needed for local python app.py runs)
# ---------------------------------------------------
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", 8000))

# ---------------------------------------------------
# PostgreSQL connection config
# ---------------------------------------------------
DB_USER = os.getenv("POSTGRES_USER", "appuser")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "apppass")
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "appdb")

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ---------------------------------------------------
# SQLAlchemy setup
# ---------------------------------------------------
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------
# Example DB Model
# ---------------------------------------------------
class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)


# ---------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------
class EmployeeCreate(BaseModel):
    name: str

class EmployeeOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


# ---------------------------------------------------
# FastAPI App
# ---------------------------------------------------
app = FastAPI(title="FastAPI + PostgreSQL Application")


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------
# Startup event: ensure DB tables, wait for DB ready
# ---------------------------------------------------
@app.on_event("startup")
def startup_event():
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            app.state.db_ready = True
            print("DB connected and tables ensured.")
            return
        except OperationalError as e:
            app.state.db_ready = False
            wait = min(2 ** attempt, 10)
            print(f"DB not ready (attempt {attempt}/{max_retries}): {e!r}. Retrying in {wait}s...")
            time.sleep(wait)

    print("Could not connect to DB after retries. App will start but /health will report DB down.")


# ---------------------------------------------------
# Health Check
# ---------------------------------------------------
@app.get("/health", tags=["health"])
def health():
    """Returns OK + DB status."""
    response = {"status": "ok", "db": "unknown"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        response["db"] = "ok"
        return response
    except Exception:
        response["db"] = "down"
        raise HTTPException(status_code=503, detail=response)


# ---------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------
@app.post("/employees", response_model=EmployeeOut, tags=["employees"])
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    emp = Employee(name=payload.name)
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@app.get("/employees/{emp_id}", response_model=EmployeeOut, tags=["employees"])
def get_employee(emp_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


# ---------------------------------------------------
# Root endpoint
# ---------------------------------------------------
@app.get("/")
def root():
    return {"message": "Hello — FastAPI app is running. Check /health."}


# ---------------------------------------------------
# Local execution (not used in Docker)
# ---------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=APP_HOST, port=APP_PORT, reload=False, workers=1)
